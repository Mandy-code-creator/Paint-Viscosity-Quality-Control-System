import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import io

# ==========================================
# WORD EXPORT LIBRARY (Check if installed)
# ==========================================
try:
    from docx import Document
    from docx.shared import Inches
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

# ==========================================
# 1. PAGE CONFIGURATION & DATA LOAD
# ==========================================
st.set_page_config(page_title="Solvent Reduction Analysis", page_icon="🎨", layout="wide")
st.title("🎨 稀釋劑減量機會分析 (Solvent Reduction Opportunity)")

if not st.session_state.get("raw_data_loaded", False) or st.session_state.get("group_a_data") is None:
    st.warning("⚠️ Please return to the Main App page and upload the raw data first. (尚未載入資料，請先返回首頁載入)")
    st.stop()

df = st.session_state["group_a_data"].copy()

# ==========================================
# 2. DATA CLEANING & PREPARATION
# ==========================================
text_cols = ["Vendor", "Resin", "Solvent_Type", "塗料批號", "線別", "塗裝位置"]
for col in text_cols:
    df[col] = df.get(col, "Unknown").fillna("Unknown").astype(str).str.strip()

df["Paint_Code"] = df.get("塗料編號", pd.Series("Unknown", index=df.index)).fillna("Unknown").astype(str).str.strip().str.upper()
df["Solvent_Type"] = df["Solvent_Type"].str.upper()

invalid_vals = {"", "NAN", "NONE", "NULL", "N/A", "NA", "-", "--"}
df.replace(list(invalid_vals), "Unknown", inplace=True)

# Standardize Identifiers
df["Batch_ID"] = df["塗料批號"]
df["Bucket_Number"] = df.get("塗料桶號", pd.Series("Unknown", index=df.index)).fillna("Unknown").astype(str).str.strip()

pos_map = {"TP": "Primer", "正底漆": "Primer", "BP": "Primer", "背底漆": "Primer", "TF": "Top Finish", "正面漆": "Top Finish", "BF": "Back Finish", "背面漆": "Back Finish"}
df["Position_UI"] = df["塗裝位置"].map(pos_map).fillna(df["塗裝位置"])

num_cols = ["塗料重量", "添加重量", "黏度(秒)", "黏度(秒)_1", "溫度"]
for col in num_cols:
    df[col] = pd.to_numeric(df.get(col, np.nan), errors="coerce")

# ---------------------------------------------------------
# NEW LOGIC: Subtract solvent weight from total mixture 
# to get the exact base paint weight before calculations.
# ---------------------------------------------------------
df["塗料重量"] = df["塗料重量"] - df["添加重量"]

df["Delta_V"] = df["黏度(秒)"] - df["黏度(秒)_1"]
df["Solvent_Ratio_Percent"] = np.where(df["塗料重量"] > 0, df["添加重量"] / df["塗料重量"] * 100, np.nan)
df["Viscosity_Sensitivity"] = np.where(df["Solvent_Ratio_Percent"] > 0, df["Delta_V"] / df["Solvent_Ratio_Percent"], np.nan)

# Strict filter ensuring base paint weight is greater than 0 after deduction
df = df[(df["塗料重量"]>0) & (df["添加重量"]>0) & (df["黏度(秒)"]>0) & (df["黏度(秒)_1"]>0) & (df["Delta_V"]>0)].copy()

if df.empty:
    st.warning("⚠️ No valid dilution records remain after data cleaning.")
    st.stop()

# ==========================================
# 2.1 TIME PARSING & DEDUPLICATION LOGIC
# ==========================================
date_col = next((c for c in ["攪拌日期", "調整日期", "生產日期", "Date"] if c in df.columns), None)
time_col = next((c for c in ["攪拌時間", "攪拌時間(迄)", "Time"] if c in df.columns), None)

sort_cols = ["Batch_ID", "Bucket_Number"]
if date_col:
    df["_Analysis_Date"] = pd.to_datetime(df[date_col], errors="coerce")
    sort_cols.append("_Analysis_Date")
else:
    df["_Analysis_Date"] = pd.NaT

if time_col:
    sort_cols.append(time_col)

# Sort entire dataset chronologically
df = df.sort_values(by=sort_cols, ascending=True)

# Identify special paint codes drawn from large drums over multiple days
special_paint_codes = ["PS30213X8"]
is_special_paint = df["Paint_Code"].isin(special_paint_codes)

# Process Standard Paint Codes
df_standard = df[~is_special_paint].copy()
df_standard = df_standard.drop_duplicates(
    subset=["Batch_ID", "Bucket_Number"], 
    keep="last"
)

# Process Special Paint Codes
df_special = df[is_special_paint].copy()
if not df_special.empty:
    df_special["Operation_Date"] = df_special["_Analysis_Date"].dt.date
    df_special = df_special.drop_duplicates(
        subset=["Batch_ID", "Bucket_Number", "Operation_Date"], 
        keep="last"
    )
    df_special = df_special.drop(columns=["Operation_Date"])

# Merge and Restore Chronological Order
df = pd.concat([df_standard, df_special], ignore_index=True)
df = df.sort_values(by=["Batch_ID", "Bucket_Number", "_Analysis_Date"])

# ==========================================
# 3. CORE LOGIC HELPER
# ==========================================
def build_summary(source_df, group_cols):
    if source_df.empty: return pd.DataFrame()
    
    agg_dict = {
        "Adjustment_Records": ("Paint_Code", "size"),
        "Historical_Batches": ("Batch_ID", "nunique"),
        "Total_Paint_kg": ("塗料重量", "sum"),
        "Total_Solvent_kg": ("添加重量", "sum"),
        "Median_Paint_kg": ("塗料重量", "median"),
        "Median_Solvent_kg": ("添加重量", "median"),
        "Median_Ratio_Percent": ("Solvent_Ratio_Percent", "median"),
        "Median_Before_Viscosity": ("黏度(秒)", "median"),
        "Median_After_Viscosity": ("黏度(秒)_1", "median"),
        "Median_Viscosity_Drop": ("Delta_V", "median"),
        "Median_Dilution_Efficiency": ("Viscosity_Sensitivity", "median"),
    }
    if "線別" not in group_cols:
        agg_dict["Production_Lines"] = ("線別", lambda x: x[x != "Unknown"].nunique())

    summary = source_df.groupby(group_cols, dropna=False).agg(**agg_dict).reset_index()
    summary["Weighted_Ratio_Percent"] = np.where(summary["Total_Paint_kg"] > 0, summary["Total_Solvent_kg"] / summary["Total_Paint_kg"] * 100, np.nan)
    return summary

# ==========================================
# 4. GLOBAL FILTERS
# ==========================================
st.markdown("---")
st.subheader("🔍 全局篩選條件 (Global Filters)")

filter_df = df.copy()
col1, col2, col3, col4, col5 = st.columns(5)

vendor_opts = ["All"] + sorted([str(x) for x in filter_df["Vendor"].unique() if x != "Unknown"])
selected_vendor = col1.selectbox("Vendor (供應商)", vendor_opts)
if selected_vendor != "All": filter_df = filter_df[filter_df["Vendor"] == selected_vendor]

resin_opts = ["All"] + sorted([str(x) for x in filter_df["Resin"].unique() if x != "Unknown"])
selected_resin = col2.selectbox("Resin Type (樹脂種類)", resin_opts)
if selected_resin != "All": filter_df = filter_df[filter_df["Resin"] == selected_resin]

pos_opts = ["All"] + sorted([str(x) for x in filter_df["Position_UI"].unique() if x != "Unknown"])
selected_position = col3.selectbox("Coating Position (塗裝位置)", pos_opts)
if selected_position != "All": filter_df = filter_df[filter_df["Position_UI"] == selected_position]

solvent_opts = ["All"] + sorted([str(x) for x in filter_df["Solvent_Type"].unique() if x != "Unknown"])
selected_solvent = col4.selectbox("Solvent Type (稀釋劑種類)", solvent_opts)
if selected_solvent != "All": filter_df = filter_df[filter_df["Solvent_Type"] == selected_solvent]

line_opts = sorted([str(x) for x in filter_df["線別"].unique() if x != "Unknown"])
selected_lines = col5.multiselect("Production Line (產線)", line_opts, default=line_opts)

if selected_lines:
    filter_df = filter_df[filter_df["線別"].isin(selected_lines)]
else:
    st.warning("⚠️ Please select at least one production line. (請至少選擇一條產線)")
    st.stop()

if filter_df.empty:
    st.warning("⚠️ No records match the global analysis filters. (無符合篩選條件的資料)")
    st.stop()

st.markdown("---")
if "_Analysis_Date" in filter_df.columns and not filter_df["_Analysis_Date"].isna().all():
    min_date = filter_df["_Analysis_Date"].min().strftime("%Y-%m-%d")
    max_date = filter_df["_Analysis_Date"].max().strftime("%Y-%m-%d")
    period_label = f"{min_date} ➔ {max_date}"
else:
    period_label = "All available data (全部歷史資料)"

st.info(f"📅 **資料期間 (Analysis Period):** {period_label} ｜ 📊 **符合條件紀錄數 (Valid Records):** {len(filter_df):,} 筆")
filter_details = f"Vendor: {selected_vendor} | Resin: {selected_resin} | Position: {selected_position} | Solvent: {selected_solvent}"
st.markdown("<br>", unsafe_allow_html=True)

# Initialize Dictionary to store charts for HTML export
exported_figs = {}

# ==========================================
# 5. HIERARCHICAL OVERVIEW (TREEMAP)
# ==========================================
st.subheader("🗂️ 塗料階層總覽 (Hierarchical Overview)")
st.markdown("Hierarchy: **Vendor ➔ Resin ➔ Position ➔ Solvent Type ➔ Paint Code**. Box size represents total solvent usage (kg).")

# Prepare Treemap data
tree_df = filter_df.groupby(["Vendor", "Resin", "Position_UI", "Solvent_Type", "Paint_Code"]).agg(
    添加重量=("添加重量", "sum"),
    Delta_V=("Delta_V", "median"), 
    Solvent_Ratio_Percent=("Solvent_Ratio_Percent", "median")
).reset_index()
tree_df = tree_df[tree_df["添加重量"] > 0]

fig_tree = px.treemap(
    tree_df,
    path=[px.Constant("Total"), "Vendor", "Resin", "Position_UI", "Solvent_Type", "Paint_Code"],
    values="添加重量", 
    color="Resin",  
    color_discrete_sequence=px.colors.qualitative.Pastel,
    custom_data=["Delta_V", "Solvent_Ratio_Percent"],
    title=f"Hierarchical Breakdown of Solvent Usage (kg)<br><sup>Filters: {filter_details}</sup>",
    height=700
)

# Update Labels and Tooltips
fig_tree.update_traces(
    texttemplate="<b>%{label}</b><br>%{value:,.0f} kg",
    hovertemplate="<b>%{label}</b><br>Solvent Usage: %{value:,.1f} kg<br>Visc Drop: ~%{customdata[0]:.1f} s<br>Solvent Added: ~%{customdata[1]:.1f}%",
    root_color="#f8f9fa"
)
fig_tree.update_layout(margin=dict(t=90, l=10, r=10, b=10)) 

st.plotly_chart(fig_tree, use_container_width=True)
exported_figs["1. Hierarchical Treemap"] = fig_tree
st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 6. TABS & VISUALIZATION
# ==========================================
tab_ranking, tab_detail, tab_line, tab_pilot = st.tabs([
    "1️⃣ 塗料消耗排名 (Top 10 Paint Code Ranking)", 
    "2️⃣ 塗料詳細分析 (Paint Code Details)", 
    "3️⃣ 產線黏度比較 (Line Comparison)",
    "4️⃣ 試用色號評估 (Pilot Paint Code Evaluation)"
])

# ----- TAB 1: RANKING -----
with tab_ranking:
    st.subheader("1. Paint Code Solvent Consumption (Top 10)")
    
    full_summary_df = build_summary(filter_df, ["Vendor", "Resin", "Position_UI", "Paint_Code", "Solvent_Type"])
    summary_df = full_summary_df.sort_values("Total_Solvent_kg", ascending=False).head(10).reset_index(drop=True)
    summary_df.insert(0, "Rank", np.arange(1, len(summary_df) + 1))

    chart_height = max(450, len(summary_df) * 32)
    
    ch1, ch2 = st.columns(2)
    with ch1:
        # Biểu đồ này chỉ hiển thị trên app, KHÔNG xuất ra báo cáo
        df_melt = summary_df.melt(id_vars="Paint_Code", value_vars=["Total_Paint_kg", "Total_Solvent_kg"])
        df_melt["variable"] = df_melt["variable"].map({"Total_Paint_kg": "塗料 (Paint)", "Total_Solvent_kg": "稀釋劑 (Solvent)"})
        
        fig1 = px.bar(
            df_melt, x="value", y="Paint_Code", color="variable", barmode="group", orientation='h', 
            height=chart_height, color_discrete_map={"塗料 (Paint)": "#5B8FF9", "稀釋劑 (Solvent)": "#F6BD16"}
        )
        fig1.update_yaxes(dtick=1, title="", categoryorder="total ascending")
        fig1.update_xaxes(title="Weight (kg)")
        fig1.update_layout(title="Paint vs Solvent Usage", legend_title_text="", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig1, use_container_width=True)
        # Đã xóa exported_figs["2. Paint vs Solvent (kg)"] = fig1

    with ch2:
        # Biểu đồ này chỉ hiển thị trên app, KHÔNG xuất ra báo cáo
        sorted_df = summary_df.sort_values("Weighted_Ratio_Percent", ascending=True)
        fig2 = px.bar(
            sorted_df, x="Weighted_Ratio_Percent", y="Paint_Code", orientation='h', text_auto='.2f', 
            height=chart_height, color_discrete_sequence=["#5B8FF9"]
        )
        fig2.update_traces(textposition="outside", cliponaxis=False)
        fig2.update_yaxes(dtick=1, title="")
        fig2.update_xaxes(title="Ratio (%)")
        fig2.update_layout(title="Weighted Solvent Ratio (%)")
        st.plotly_chart(fig2, use_container_width=True)
        # Đã xóa exported_figs["3. Weighted Solvent Ratio"] = fig2

    st.markdown("---")
    
    # Dual Axis Chart
    fig_dual = go.Figure()
    
    # Cột Paint (kg) - Thêm text hiển thị giá trị
    fig_dual.add_trace(go.Bar(
        x=summary_df["Paint_Code"], 
        y=summary_df["Total_Paint_kg"], 
        name="Paint (kg)", 
        marker_color="#5B8FF9", 
        yaxis="y1",
        text=summary_df["Total_Paint_kg"].apply(lambda x: f"{x:,.0f}"), # Định dạng số có dấu phẩy
        textposition="auto"
    ))
    
    # Cột Solvent (kg) - Thêm text hiển thị giá trị
    fig_dual.add_trace(go.Bar(
        x=summary_df["Paint_Code"], 
        y=summary_df["Total_Solvent_kg"], 
        name="Solvent (kg)", 
        marker_color="#F6BD16", 
        yaxis="y1",
        text=summary_df["Total_Solvent_kg"].apply(lambda x: f"{x:,.0f}"), # Định dạng số có dấu phẩy
        textposition="auto"
    ))
    
    # Implementation of the Deep Sky Blue visual standard
    fig_dual.add_trace(go.Scatter(
        x=summary_df["Paint_Code"], 
        y=summary_df["Weighted_Ratio_Percent"], 
        name="Solvent Ratio (%)", 
        mode="lines+markers", 
        line=dict(color="DeepSkyBlue", width=3), 
        marker=dict(size=8), 
        yaxis="y2"
    ))
    
    for i, row in summary_df.iterrows():
        fig_dual.add_annotation(
            x=row["Paint_Code"], y=row["Weighted_Ratio_Percent"],
            text=f"<b>{row['Weighted_Ratio_Percent']:.2f}%</b>", 
            xref="x", yref="y2", showarrow=False, yshift=18, 
            font=dict(color="black", size=12), bgcolor="rgba(255, 255, 255, 0.85)", borderpad=2
        )

    fig_dual.update_layout(
        title=f"Paint & Solvent Usage vs. Solvent Ratio<br><sup>Filters Applied: {filter_details}</sup>",
        xaxis=dict(title="Paint Code"),
        yaxis=dict(title="Weight (kg)", side="left", showgrid=False),
        yaxis2=dict(
            title="Solvent Ratio (%)", 
            overlaying="y", 
            side="right", 
            showgrid=False, 
            range=[0, summary_df["Weighted_Ratio_Percent"].max() * 1.25]
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=600,
        uniformtext_minsize=8, 
        uniformtext_mode='hide' # Tự động ẩn text nếu cột quá nhỏ không đủ chỗ chứa
    )
    st.plotly_chart(fig_dual, use_container_width=True)
    exported_figs["4. Dual Axis Usage vs Ratio"] = fig_dual

# ----- TAB 2: DETAILS -----
with tab_detail:
    st.subheader("2. Paint Code Details")
    selected_code = st.selectbox("Select Paint Code", summary_df["Paint_Code"].unique())
    detail_df = filter_df[filter_df["Paint_Code"] == selected_code].copy()
    detail_title_filter = f"{filter_details} | Paint Code: {selected_code}"

    ch3, ch4 = st.columns(2)
    with ch3:
        detail_df = detail_df.reset_index(drop=True)
        detail_df["Record_Index"] = detail_df.index + 1
        
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=detail_df["Record_Index"], y=detail_df["黏度(秒)"], mode="lines+markers", name="Before Viscosity", marker=dict(color="#5B8FF9", size=8), yaxis="y1"))
        fig3.add_trace(go.Scatter(x=detail_df["Record_Index"], y=detail_df["黏度(秒)_1"], mode="lines+markers", name="After Viscosity", marker=dict(color="#5AD8A6", size=8), yaxis="y1"))
        
        if "溫度" in detail_df.columns and not detail_df["溫度"].isna().all():
            fig3.add_trace(go.Scatter(x=detail_df["Record_Index"], y=detail_df["溫度"], mode="lines+markers", name="Temperature (°C)", marker=dict(color="#F6BD16", size=8, symbol="diamond"), line=dict(color="#F6BD16", width=2, dash="dot"), yaxis="y2"))
            chart_title = "Viscosity & Temperature Variation (Before vs After)"
        else:
            chart_title = "Viscosity Variation (Before vs After)"
        
        fig3.update_layout(
            title=f"{chart_title}<br><sup>Filters: {detail_title_filter}</sup>",
            xaxis_title="Record Output Sequence", yaxis=dict(title="Viscosity (s)", side="left"),
            yaxis2=dict(title="Temperature (°C)", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig3, use_container_width=True)
        exported_figs["5. Viscosity & Temperature Variation"] = fig3

    with ch4:
        line_usage = build_summary(detail_df, ["線別"]).sort_values("Total_Solvent_kg")
        fig4 = px.bar(line_usage, x="Total_Solvent_kg", y="線別", text="Weighted_Ratio_Percent", orientation='h', title=f"Solvent Usage by Line<br><sup>Filters: {detail_title_filter}</sup>", color_discrete_sequence=["#5B8FF9"])
        fig4.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
        fig4.update_yaxes(title="")
        fig4.update_xaxes(title="Total Solvent (kg)")
        st.plotly_chart(fig4, use_container_width=True)
        exported_figs["6. Solvent Usage by Line"] = fig4

# ----- TAB 3: LINE COMPARISON -----
with tab_line:
    st.subheader("3. Production Line Comparison")
    comp_code = st.selectbox("Select Paint Code for Line Comparison", summary_df["Paint_Code"].unique(), key="line_comp")
    comp_df = filter_df[filter_df["Paint_Code"] == comp_code]
    line_summary = build_summary(comp_df, ["線別"]).sort_values("線別")

    if len(line_summary) >= 2:
        ch5, ch6 = st.columns(2)
        with ch5:
            fig5 = go.Figure()
            for i, row in line_summary.iterrows():
                fig5.add_trace(go.Scatter(x=[row["Median_After_Viscosity"], row["Median_Before_Viscosity"]], y=[row["線別"], row["線別"]], mode="lines+markers", marker=dict(size=12), name=row["線別"]))
            fig5.update_layout(title="Viscosity Drop (Before vs After)", xaxis_title="Viscosity (s)", yaxis_title="")
            st.plotly_chart(fig5, use_container_width=True)
            exported_figs["7. Line Comparison - Viscosity Drop"] = fig5

        with ch6:
            fig6 = px.bar(line_summary.sort_values("Weighted_Ratio_Percent"), x="Weighted_Ratio_Percent", y="線別", orientation='h', text_auto='.2f', title="Weighted Solvent Ratio", color_discrete_sequence=["#5AD8A6"])
            fig6.update_yaxes(title="")
            st.plotly_chart(fig6, use_container_width=True)
            exported_figs["8. Line Comparison - Solvent Ratio"] = fig6

# ----- TAB 4: PILOT PAINT CODE EVALUATION -----
with tab_pilot:
    st.subheader("4. 試用色號評估 (Pilot Paint Code Evaluation)")

    st.markdown(
        "依據塗料使用量、稀釋劑用量、添加比例穩定性及歷史資料量，"
        "評估適合優先試用預調漆的色號。"
    )

    # ------------------------------------------------------
    # Evaluation settings
    # 添加比例穩定率 is the main stability indicator.
    # Relative IQR and CV are retained only for engineering reference.
    # ------------------------------------------------------
    set1, set2, set3 = st.columns(3)

    with set1:
        min_pilot_records = st.number_input(
            "最低歷史紀錄數",
            min_value=5,
            value=20,
            step=1,
            key="pilot_min_records_simple"
        )

    with set2:
        stable_coverage_limit = st.number_input(
            "添加比例穩定率下限",
            min_value=0.30,
            max_value=1.00,
            value=0.70,
            step=0.05,
            format="%.2f",
            key="pilot_stable_coverage_limit_simple"
        )

    with set3:
        top_n_pilot = st.number_input(
            "顯示色號數",
            min_value=3,
            max_value=30,
            value=10,
            step=1,
            key="pilot_top_n_simple"
        )

    STABLE_BAND_PERCENT_POINT = 2.0

    st.caption(
        "添加比例穩定率＝落在該色號添加比例中位數 ±2 個百分點內的紀錄占比。"
        "穩定率越高，代表歷史添加比例越集中，越適合評估預調漆。"
    )

    # ------------------------------------------------------
    # Robust helper functions
    # ------------------------------------------------------
    def safe_cv(series):
        values = pd.to_numeric(series, errors="coerce").dropna()
        if len(values) < 2 or values.mean() <= 0:
            return np.nan
        return values.std(ddof=1) / values.mean()

    def relative_iqr(series):
        values = pd.to_numeric(series, errors="coerce").dropna()
        if values.empty:
            return np.nan

        median_value = values.median()
        if median_value <= 0:
            return np.nan

        return (
            values.quantile(0.75) - values.quantile(0.25)
        ) / median_value

    def stable_coverage(series):
        values = pd.to_numeric(series, errors="coerce").dropna()
        if values.empty:
            return np.nan

        median_value = values.median()
        lower_limit = median_value - STABLE_BAND_PERCENT_POINT
        upper_limit = median_value + STABLE_BAND_PERCENT_POINT

        return values.between(
            lower_limit,
            upper_limit,
            inclusive="both"
        ).mean()

    # ------------------------------------------------------
    # Build paint-code evaluation table
    # ------------------------------------------------------
    pilot_df = (
        filter_df
        .groupby(
            [
                "Vendor",
                "Resin",
                "Position_UI",
                "Solvent_Type",
                "Paint_Code"
            ],
            dropna=False
        )
        .agg(
            Historical_Records=("Paint_Code", "size"),
            Historical_Batches=("Batch_ID", "nunique"),
            Total_Paint_kg=("塗料重量", "sum"),
            Total_Solvent_kg=("添加重量", "sum"),
            Median_Ratio_Percent=(
                "Solvent_Ratio_Percent",
                "median"
            ),
            Ratio_P10=(
                "Solvent_Ratio_Percent",
                lambda x: x.quantile(0.10)
            ),
            Ratio_P25=(
                "Solvent_Ratio_Percent",
                lambda x: x.quantile(0.25)
            ),
            Ratio_P75=(
                "Solvent_Ratio_Percent",
                lambda x: x.quantile(0.75)
            ),
            Ratio_P90=(
                "Solvent_Ratio_Percent",
                lambda x: x.quantile(0.90)
            ),
            Relative_IQR=(
                "Solvent_Ratio_Percent",
                relative_iqr
            ),
            Stable_Coverage=(
                "Solvent_Ratio_Percent",
                stable_coverage
            ),
            Ratio_CV=(
                "Solvent_Ratio_Percent",
                safe_cv
            ),
            Median_Before_Viscosity=("黏度(秒)", "median"),
            Before_Viscosity_P25=(
                "黏度(秒)",
                lambda x: x.quantile(0.25)
            ),
            Before_Viscosity_P75=(
                "黏度(秒)",
                lambda x: x.quantile(0.75)
            ),
            Median_After_Viscosity=("黏度(秒)_1", "median"),
            After_Viscosity_P25=(
                "黏度(秒)_1",
                lambda x: x.quantile(0.25)
            ),
            After_Viscosity_P75=(
                "黏度(秒)_1",
                lambda x: x.quantile(0.75)
            ),
            Median_Viscosity_Drop=("Delta_V", "median"),
            Production_Lines=(
                "線別",
                lambda x: x[x != "Unknown"].nunique()
            )
        )
        .reset_index()
    )

    pilot_df["Weighted_Ratio_Percent"] = np.where(
        pilot_df["Total_Paint_kg"] > 0,
        pilot_df["Total_Solvent_kg"]
        / pilot_df["Total_Paint_kg"]
        * 100,
        np.nan
    )

    pilot_df["Ratio_IQR"] = (
        pilot_df["Ratio_P75"] - pilot_df["Ratio_P25"]
    )

    pilot_df["Ratio_P10_P90_Range"] = (
        pilot_df["Ratio_P90"] - pilot_df["Ratio_P10"]
    )

    pilot_df["Before_Viscosity_IQR"] = (
        pilot_df["Before_Viscosity_P75"]
        - pilot_df["Before_Viscosity_P25"]
    )

    pilot_df["After_Viscosity_IQR"] = (
        pilot_df["After_Viscosity_P75"]
        - pilot_df["After_Viscosity_P25"]
    )

    # ------------------------------------------------------
    # Score construction
    # ------------------------------------------------------
    def minmax_score(series, reverse=False):
        values = pd.to_numeric(series, errors="coerce")
        valid = values.dropna()

        if valid.empty:
            score = pd.Series(0.0, index=series.index)
        elif valid.max() == valid.min():
            score = pd.Series(100.0, index=series.index)
        else:
            score = (
                (values - valid.min())
                / (valid.max() - valid.min())
                * 100
            )

        score = score.fillna(0)

        if reverse:
            score = 100 - score

        return score.clip(0, 100)

    pilot_df["Usage_Score"] = minmax_score(
        pilot_df["Total_Solvent_kg"]
    )

    pilot_df["Paint_Volume_Score"] = minmax_score(
        pilot_df["Total_Paint_kg"]
    )

    pilot_df["Ratio_Need_Score"] = minmax_score(
        pilot_df["Weighted_Ratio_Percent"]
    )

    # Main stability score: directly use 添加比例穩定率.
    # Relative IQR and CV remain available only in the engineering detail table.
    pilot_df["Stability_Score"] = (
        pilot_df["Stable_Coverage"]
        .fillna(0)
        .clip(0, 1)
        * 100
    )

    pilot_df["Data_Support_Score"] = minmax_score(
        pilot_df["Historical_Records"]
    )

    # Final score:
    # 30% solvent-use opportunity
    # 20% paint-use impact
    # 20% dilution need
    # 20% robust stability
    # 10% data support
    pilot_df["Pilot_Score"] = (
        pilot_df["Usage_Score"] * 0.30
        + pilot_df["Paint_Volume_Score"] * 0.20
        + pilot_df["Ratio_Need_Score"] * 0.20
        + pilot_df["Stability_Score"] * 0.20
        + pilot_df["Data_Support_Score"] * 0.10
    )

    pilot_df["Data_Qualified"] = (
        pilot_df["Historical_Records"] >= min_pilot_records
    )

    pilot_df["Stability_Qualified"] = (
        pilot_df["Stable_Coverage"].notna()
        & (pilot_df["Stable_Coverage"] >= stable_coverage_limit)
    )

    def classify_stability(value):
        if pd.isna(value):
            return "資料不足"
        if value >= 0.80:
            return "穩定"
        if value >= 0.70:
            return "尚可"
        return "不穩定"

    pilot_df["Stability_Level"] = (
        pilot_df["Stable_Coverage"]
        .apply(classify_stability)
    )

    def classify_pilot(row):
        if not row["Data_Qualified"]:
            return "暫不建議"

        if (
            row["Pilot_Score"] >= 70
            and row["Stability_Qualified"]
        ):
            return "優先試用"

        if (
            row["Pilot_Score"] >= 45
            and row["Stable_Coverage"] >= 0.60
        ):
            return "可進一步評估"

        return "暫不建議"

    pilot_df["Evaluation_Result"] = pilot_df.apply(
        classify_pilot,
        axis=1
    )

    pilot_df = pilot_df.sort_values(
        ["Pilot_Score", "Total_Solvent_kg"],
        ascending=[False, False]
    ).reset_index(drop=True)

    pilot_df.insert(
        0,
        "Pilot_Rank",
        np.arange(1, len(pilot_df) + 1)
    )

    pilot_top_df = pilot_df.head(
        int(top_n_pilot)
    ).copy()

    # ------------------------------------------------------
    # KPI summary
    # ------------------------------------------------------
    qualified_count = int(pilot_df["Data_Qualified"].sum())
    priority_count = int(
        (pilot_df["Evaluation_Result"] == "優先試用").sum()
    )
    best_code = (
        pilot_df.iloc[0]["Paint_Code"]
        if not pilot_df.empty
        else "-"
    )

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    kpi1.metric("Evaluated Paint Codes", f"{len(pilot_df):,}")
    kpi2.metric("Data-Qualified Codes", f"{qualified_count:,}")
    kpi3.metric("Priority Pilot Codes", f"{priority_count:,}")
    kpi4.metric("Top Candidate", best_code)

    st.caption(
        "評分權重：稀釋劑總用量30%、塗料使用量20%、添加比例需求20%、"
        "添加比例穩定率20%、歷史資料量10%。"
    )

    # ------------------------------------------------------
    # Main chart: Pilot ranking
    # ------------------------------------------------------
    color_map = {
        "優先試用": "#2F6B6D",
        "可進一步評估": "#6F8FAF",
        "暫不建議": "#C9C5BE"
    }

    pilot_chart_df = (
        pilot_top_df
        .sort_values("Pilot_Score", ascending=True)
        .copy()
    )

    pilot_chart_df["Chart_Label"] = pilot_chart_df.apply(
        lambda row: (
            f"分數 {row['Pilot_Score']:.1f}  ｜  "
            f"稀釋劑 {row['Total_Solvent_kg']:,.0f} kg  ｜  "
            f"添加比例 {row['Weighted_Ratio_Percent']:.1f}%  ｜  "
            f"穩定率 {row['Stable_Coverage']:.0%}"
        ),
        axis=1
    )

    fig_pilot_score = px.bar(
        pilot_chart_df,
        x="Pilot_Score",
        y="Paint_Code",
        orientation="h",
        color="Evaluation_Result",
        color_discrete_map=color_map,
        text="Chart_Label",
        custom_data=[
            "Total_Solvent_kg",
            "Total_Paint_kg",
            "Weighted_Ratio_Percent",
            "Stable_Coverage",
            "Stability_Level",
            "Historical_Records"
        ],
        title=(
            "各色號預調漆試用優先順序"
            f"<br><sup>分數越高代表越適合優先評估｜{filter_details}</sup>"
        ),
        height=max(560, len(pilot_top_df) * 56)
    )

    fig_pilot_score.update_traces(
        texttemplate="%{text}",
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "試用優先分數：%{x:.1f}<br>"
            "稀釋劑總用量：%{customdata[0]:,.1f} kg<br>"
            "塗料總用量：%{customdata[1]:,.1f} kg<br>"
            "加權添加比例：%{customdata[2]:.2f}%<br>"
            "添加比例穩定率：%{customdata[3]:.1%}<br>"
            "穩定度：%{customdata[4]}<br>"
            "歷史紀錄數：%{customdata[5]:,.0f}"
            "<extra></extra>"
        )
    )

    fig_pilot_score.update_xaxes(
        title="試用優先分數",
        range=[0, 110],
        showline=True,
        linewidth=1.2,
        linecolor="#4B5563",
        mirror=True,
        showgrid=True,
        gridcolor="#E5E7EB"
    )

    fig_pilot_score.update_yaxes(
        title="",
        showline=True,
        linewidth=1.5,
        linecolor="black",
        mirror=True
    )

    fig_pilot_score.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=110, r=430, t=145, b=80),
        bargap=0.28,
        font=dict(
            family="Arial, Microsoft JhengHei, sans-serif",
            size=12,
            color="#334155"
        ),
        title=dict(
            x=0.0,
            xanchor="left",
            y=0.98,
            yanchor="top",
            font=dict(size=18, color="#1F2937")
        ),
        legend_title_text="評估結果",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.10,
            xanchor="right",
            x=1,
            bgcolor="rgba(255,255,255,0)",
            font=dict(size=11)
        )
    )

    st.plotly_chart(fig_pilot_score, use_container_width=True)

    st.info(
        "圖中數字依序為："
        "① 試用優先分數；"
        "② 稀釋劑歷史總用量；"
        "③ 加權添加比例；"
        "④ 添加比例穩定率。"
        "分數越高代表越適合優先評估預調漆；"
        "穩定率越高代表歷史添加比例越集中。"
    )

    exported_figs["9. Paint Code Pilot Priority Ranking"] = fig_pilot_score

    # ------------------------------------------------------
    # Detailed evaluation table
    # ------------------------------------------------------

    # ------------------------------------------------------
    st.markdown("---")
    st.markdown("### 色號試用評估明細")

    pilot_output = pilot_df[
        [
            "Pilot_Rank",
            "Paint_Code",
            "Evaluation_Result",
            "Pilot_Score",
            "Historical_Records",
            "Historical_Batches",
            "Total_Paint_kg",
            "Total_Solvent_kg",
            "Weighted_Ratio_Percent",
            "Median_Ratio_Percent",
            "Ratio_P25",
            "Ratio_P75",
            "Stable_Coverage",
            "Stability_Level",
            "Relative_IQR",
            "Ratio_CV",
            "Median_Before_Viscosity",
            "Median_After_Viscosity",
            "After_Viscosity_P25",
            "After_Viscosity_P75",
            "Median_Viscosity_Drop",
            "Production_Lines"
        ]
    ].copy()

    pilot_output = pilot_output.rename(columns={
        "Pilot_Rank": "排名",
        "Paint_Code": "色號",
        "Evaluation_Result": "評估結果",
        "Pilot_Score": "試用優先分數",
        "Historical_Records": "歷史紀錄數",
        "Historical_Batches": "歷史批號數",
        "Total_Paint_kg": "塗料總用量",
        "Total_Solvent_kg": "稀釋劑總用量",
        "Weighted_Ratio_Percent": "加權添加比例",
        "Median_Ratio_Percent": "添加比例中位數",
        "Ratio_P25": "添加比例P25",
        "Ratio_P75": "添加比例P75",
        "Stable_Coverage": "添加比例穩定率",
        "Stability_Level": "添加比例穩定度",
        "Relative_IQR": "相對四分位距（參考）",
        "Ratio_CV": "添加比例CV（參考）",
        "Median_Before_Viscosity": "添加前黏度中位數",
        "Median_After_Viscosity": "添加後黏度中位數",
        "After_Viscosity_P25": "添加後黏度P25",
        "After_Viscosity_P75": "添加後黏度P75",
        "Median_Viscosity_Drop": "降黏幅度中位數",
        "Production_Lines": "使用產線數"
    })

    pilot_output["添加比例穩定率"] = (
        pilot_output["添加比例穩定率"] * 100
    )

    st.dataframe(
        pilot_output,
        column_config={
            "排名": st.column_config.NumberColumn("排名", format="%d"),
            "試用優先分數": st.column_config.ProgressColumn(
                "試用優先分數",
                min_value=0,
                max_value=100,
                format="%.1f"
            ),
            "歷史紀錄數": st.column_config.NumberColumn(
                "歷史紀錄數",
                format="%d"
            ),
            "歷史批號數": st.column_config.NumberColumn(
                "歷史批號數",
                format="%d"
            ),
            "塗料總用量": st.column_config.NumberColumn(
                "塗料總用量 (kg)",
                format="%.1f"
            ),
            "稀釋劑總用量": st.column_config.NumberColumn(
                "稀釋劑總用量 (kg)",
                format="%.1f"
            ),
            "加權添加比例": st.column_config.NumberColumn(
                "加權添加比例 (%)",
                format="%.1f"
            ),
            "添加比例中位數": st.column_config.NumberColumn(
                "添加比例中位數 (%)",
                format="%.1f"
            ),
            "添加比例P25": st.column_config.NumberColumn(
                "添加比例P25 (%)",
                format="%.1f"
            ),
            "添加比例P75": st.column_config.NumberColumn(
                "添加比例P75 (%)",
                format="%.1f"
            ),
            "添加比例穩定率": st.column_config.NumberColumn(
                "添加比例穩定率 (%)",
                format="%.1f"
            ),
            "添加比例穩定度": st.column_config.TextColumn(
                "添加比例穩定度"
            ),
            "相對四分位距（參考）": st.column_config.NumberColumn(
                "相對四分位距（參考）",
                format="%.1f"
            ),
            "添加比例CV（參考）": st.column_config.NumberColumn(
                "添加比例CV（參考）",
                format="%.1f"
            ),
            "添加前黏度中位數": st.column_config.NumberColumn(
                "添加前黏度中位數 (秒)",
                format="%.1f"
            ),
            "添加後黏度中位數": st.column_config.NumberColumn(
                "添加後黏度中位數 (秒)",
                format="%.1f"
            ),
            "添加後黏度P25": st.column_config.NumberColumn(
                "添加後黏度P25 (秒)",
                format="%.1f"
            ),
            "添加後黏度P75": st.column_config.NumberColumn(
                "添加後黏度P75 (秒)",
                format="%.1f"
            ),
            "降黏幅度中位數": st.column_config.NumberColumn(
                "降黏幅度中位數 (秒)",
                format="%.1f"
            ),
            "使用產線數": st.column_config.NumberColumn(
                "使用產線數",
                format="%d"
            )
        },
        use_container_width=True,
        hide_index=True
    )

    # ------------------------------------------------------
    # Automatic conclusion
    # ------------------------------------------------------
    st.markdown("---")
    st.markdown("### 評估結論")

    if pilot_df.empty:
        st.warning("目前篩選條件下無可評估色號。")
    else:
        top_row = pilot_df.iloc[0]

        st.success(
            f"目前優先候選色號為 **{top_row['Paint_Code']}**，"
            f"試用優先分數為 **{top_row['Pilot_Score']:.1f} 分**。"
        )

        st.markdown(
            f"""
            - 歷史塗料使用量：**{top_row['Total_Paint_kg']:,.1f} kg**
            - 歷史稀釋劑使用量：**{top_row['Total_Solvent_kg']:,.1f} kg**
            - 加權添加比例：**{top_row['Weighted_Ratio_Percent']:.2f}%**
            - 添加比例中位數：**{top_row['Median_Ratio_Percent']:.2f}%**
            - 添加比例穩定率：**{top_row['Stable_Coverage']:.1%}**
            - 添加比例穩定度：**{top_row['Stability_Level']}**
            - CV（工程參考）：**{top_row['Ratio_CV']:.3f}**
            - 歷史有效紀錄：**{int(top_row['Historical_Records'])} 筆**
            - 評估結果：**{top_row['Evaluation_Result']}**
            """
        )

        if top_row["Evaluation_Result"] == "優先試用":
            st.info(
                "建議優先與供應商確認預調漆出貨黏度範圍，"
                "並以小批量進行現場試用，驗證進廠後直接使用或"
                "減少再次添加稀釋劑的可行性。"
            )
        elif top_row["Evaluation_Result"] == "可進一步評估":
            st.info(
                "建議先確認添加比例變動原因、批次差異及黏度規格，"
                "待資料穩定後再進行預調漆試用。"
            )
        else:
            st.warning(
                "目前資料量、使用量或添加比例穩定性尚不足，"
                "暫不建議直接導入預調漆試用。"
            )

    pilot_csv = pilot_output.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        label="下載試用色號評估表 CSV",
        data=pilot_csv,
        file_name="試用色號評估表.csv",
        mime="text/csv"
    )


# ==========================================
# 7. EXPORT INTERACTIVE HTML REPORT
# ==========================================
st.markdown("---")
st.subheader("📄 Export Report")

st.info("💡 The report is exported as an interactive HTML file to preserve exact chart dimensions and functionality. (報告將匯出為互動式 HTML 檔案)")

if st.button("📥 Generate & Download Report", type="primary"):
    with st.spinner("⏳ Generating HTML report..."):
        try:
            html_content = f"""
            <html>
            <head>
                <meta charset="utf-8">
                <title>各色號稀釋劑使用分析與評估(Solvent Reduction Opportunity Report)</title>
                <style>
                    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; background-color: #f0f2f6; }}
                    h1 {{ color: #1f77b4; text-align: center; font-size: 32px; }}
                    h2 {{ color: #2c3e50; border-bottom: 2px solid #bdc3c7; padding-bottom: 8px; margin-top: 50px; font-size: 20px; }}
                    .info-box {{ background-color: #ffffff; padding: 20px; border-radius: 10px; margin-bottom: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-left: 5px solid #1f77b4; }}
                    .info-box p {{ margin: 8px 0; font-size: 16px; color: #333; }}
                    .chart-container {{ background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 30px; width: 100%; overflow: hidden; }}
                </style>
            </head>
            <body>
                <h1>📊各色號稀釋劑使用分析與評估 </h1>
                <div class="info-box">
                    <p><strong>🕒 分析日期 (Analysis Date):</strong> {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p><strong>🔍 篩選條件 (Filters Applied):</strong> {filter_details}</p>
                </div>
            """

            for i, (fig_title, fig) in enumerate(exported_figs.items()):
                inc_js = 'cdn' if i == 0 else False
                
                fig_html = fig.to_html(
                    full_html=False, 
                    include_plotlyjs=inc_js, 
                    default_width="100%", 
                    default_height="600px"
                )
                
                html_content += f"""
                <h2>{fig_title}</h2>
                <div class="chart-container">
                    {fig_html}
                </div>
                """

            html_content += """
            </body>
            </html>
            """

            html_buffer = io.BytesIO(html_content.encode('utf-8'))
            
            st.success("✅ Report generated successfully!")
            
            st.download_button(
                label="💾 Download Interactive Report (.html)",
                data=html_buffer,
                file_name=f"Solvent_Report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.html",
                mime="text/html"
            )

        except Exception as e:
            st.error(f"❌ Error generating report: {e}")
