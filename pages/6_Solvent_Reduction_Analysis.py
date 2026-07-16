import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

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
# Clean Text Columns
text_cols = ["Vendor", "Resin", "Solvent_Type", "塗料批號", "線別", "塗裝位置"]
for col in text_cols:
    df[col] = df.get(col, "Unknown").fillna("Unknown").astype(str).str.strip()

df["Paint_Code"] = df.get("塗料編號", pd.Series("Unknown", index=df.index)).fillna("Unknown").astype(str).str.strip().str.upper()
df["Solvent_Type"] = df["Solvent_Type"].str.upper()

invalid_vals = {"", "NAN", "NONE", "NULL", "N/A", "NA", "-", "--"}
df.replace(list(invalid_vals), "Unknown", inplace=True)

df["Batch_ID"] = df["塗料批號"]
pos_map = {"TP": "Primer", "正底漆": "Primer", "BP": "Primer", "背底漆": "Primer", "TF": "Top Finish", "正面漆": "Top Finish", "BF": "Back Finish", "背面漆": "Back Finish"}
df["Position_UI"] = df["塗裝位置"].map(pos_map).fillna(df["塗裝位置"])

# Clean Numeric Columns
num_cols = ["塗料重量", "添加重量", "黏度(秒)", "黏度(秒)_1"]
for col in num_cols:
    df[col] = pd.to_numeric(df.get(col, np.nan), errors="coerce")

df["Delta_V"] = df["黏度(秒)"] - df["黏度(秒)_1"]
df["Solvent_Ratio_Percent"] = np.where(df["塗料重量"] > 0, df["添加重量"] / df["塗料重量"] * 100, np.nan)
df["Viscosity_Sensitivity"] = np.where(df["Solvent_Ratio_Percent"] > 0, df["Delta_V"] / df["Solvent_Ratio_Percent"], np.nan)

# Keep valid records
df = df[(df["塗料重量"]>0) & (df["添加重量"]>0) & (df["黏度(秒)"]>0) & (df["黏度(秒)_1"]>0) & (df["Delta_V"]>0)].copy()

if df.empty:
    st.warning("⚠️ No valid dilution records remain after data cleaning. (無有效紀錄)")
    st.stop()

# Date Parsing & Filter: ONLY Paint Codes with >= 2 Years of Data
date_col = next((c for c in ["攪拌日期", "調整日期", "生產日期", "Date"] if c in df.columns), None)
if date_col:
    df["_Analysis_Date"] = pd.to_datetime(df[date_col], errors="coerce")
    
    # Calculate duration per paint code
    duration_df = df.dropna(subset=["_Analysis_Date"]).groupby("Paint_Code")["_Analysis_Date"].agg(["min", "max"])
    duration_df["Duration_Days"] = (duration_df["max"] - duration_df["min"]).dt.days
    
    # Filter >= 730 days (2 years)
    valid_paints = duration_df[duration_df["Duration_Days"] >= 730].index
    df = df[df["Paint_Code"].isin(valid_paints)].copy()
    
    if df.empty:
        st.warning("⚠️ No paint codes found with 2 or more years of historical data. (無符合兩年以上歷史資料的塗料編號)")
        st.stop()
else:
    st.info("ℹ️ No date column found. Skipping the '2-year history' filter. (未找到日期欄位，跳過兩年以上資料篩選)")

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

def apply_filter(col_obj, label, col_name):
    options = ["All"] + sorted([str(x) for x in df[col_name].unique() if x != "Unknown"])
    selected = col_obj.selectbox(label, options)
    return filter_df[filter_df[col_name] == selected] if selected != "All" else filter_df

filter_df = apply_filter(col1, "Vendor (供應商)", "Vendor")
filter_df = apply_filter(col2, "Resin Type (樹脂種類)", "Resin")
filter_df = apply_filter(col3, "Coating Position (塗裝位置)", "Position_UI")
filter_df = apply_filter(col4, "Solvent Type (稀釋劑種類)", "Solvent_Type")

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

# ==========================================
# 5. ANALYSIS PERIOD & OVERVIEW
# ==========================================
st.markdown("---")
if "_Analysis_Date" in filter_df.columns and not filter_df["_Analysis_Date"].isna().all():
    min_date = filter_df["_Analysis_Date"].min().strftime("%Y-%m-%d")
    max_date = filter_df["_Analysis_Date"].max().strftime("%Y-%m-%d")
    period_label = f"{min_date} ➔ {max_date}"
else:
    period_label = "All available data (全部歷史資料)"

st.info(f"📅 **資料期間 (Analysis Period):** {period_label} ｜ 📊 **符合條件紀錄數 (Valid Records):** {len(filter_df):,} 筆")
st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 6. TABS & VISUALIZATION
# ==========================================
tab_ranking, tab_detail, tab_line = st.tabs([
    "1️⃣ 塗料消耗排名 (Paint Code Ranking)", 
    "2️⃣ 塗料詳細分析 (Paint Code Details)", 
    "3️⃣ 產線黏度比較 (Line Comparison)"
])

# ----- TAB 1: RANKING -----
with tab_ranking:
    st.subheader("1. Paint Code Solvent Consumption")
    summary_df = build_summary(filter_df, ["Vendor", "Resin", "Position_UI", "Paint_Code", "Solvent_Type"])
    summary_df = summary_df.sort_values("Total_Solvent_kg", ascending=False).reset_index(drop=True)
    summary_df.insert(0, "Rank", np.arange(1, len(summary_df) + 1))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Paint Codes", f"{summary_df['Paint_Code'].nunique():,}")
    c2.metric("Historical Batches", f"{summary_df['Historical_Batches'].sum():,.0f}")
    c3.metric("Total Solvent Usage", f"{summary_df['Total_Solvent_kg'].sum():,.0f} kg")
    
    overall_ratio = (summary_df["Total_Solvent_kg"].sum() / summary_df["Total_Paint_kg"].sum() * 100) if summary_df["Total_Paint_kg"].sum() > 0 else 0
    c4.metric("Overall Weighted Ratio", f"{overall_ratio:.2f}%")

    st.markdown("---")
    
    chart_height = max(500, len(summary_df) * 35)
    
    ch1, ch2 = st.columns(2)
    with ch1:
        st.markdown("#### Paint vs Solvent (kg)")
        df_melt = summary_df.melt(id_vars="Paint_Code", value_vars=["Total_Paint_kg", "Total_Solvent_kg"])
        df_melt["variable"] = df_melt["variable"].map({"Total_Paint_kg": "塗料 (Paint)", "Total_Solvent_kg": "稀釋劑 (Solvent)"})
        
        fig1 = px.bar(
            df_melt, x="value", y="Paint_Code", color="variable", barmode="group", orientation='h', 
            height=chart_height,
            color_discrete_map={"塗料 (Paint)": "#1F77B4", "稀釋劑 (Solvent)": "#FF7F0E"}
        )
        fig1.update_yaxes(dtick=1, title="")
        fig1.update_xaxes(title="Weight (kg)")
        fig1.update_layout(legend_title_text="", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig1, use_container_width=True)

    with ch2:
        st.markdown("#### Weighted Solvent Ratio (%)")
        sorted_df = summary_df.sort_values("Weighted_Ratio_Percent", ascending=True)
        fig2 = px.bar(
            sorted_df, x="Weighted_Ratio_Percent", y="Paint_Code", orientation='h', text_auto='.2f', 
            height=chart_height, color_discrete_sequence=["#1F77B4"]
        )
        fig2.update_traces(textposition="outside", cliponaxis=False)
        fig2.update_yaxes(dtick=1, title="")
        fig2.update_xaxes(title="Ratio (%)")
        st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(summary_df.style.format(precision=2), use_container_width=True)

# ----- TAB 2: DETAILS -----
with tab_detail:
    st.subheader("2. Paint Code Details")
    selected_code = st.selectbox("Select Paint Code", filter_df["Paint_Code"].unique())
    detail_df = filter_df[filter_df["Paint_Code"] == selected_code]
    
    st.write(f"**Total Records:** {len(detail_df)} | **Batches:** {detail_df['Batch_ID'].nunique()} | **Lines:** {detail_df['線別'].nunique()}")
    
    ch3, ch4 = st.columns(2)
    with ch3:
        fig3 = px.scatter(detail_df, x="黏度(秒)", y="Solvent_Ratio_Percent", color="線別", title="Before Viscosity vs Solvent Ratio")
        st.plotly_chart(fig3, use_container_width=True)
    with ch4:
        line_usage = build_summary(detail_df, ["線別"]).sort_values("Total_Solvent_kg")
        fig4 = px.bar(line_usage, x="Total_Solvent_kg", y="線別", text="Weighted_Ratio_Percent", orientation='h', title="Solvent Usage by Line")
        fig4.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
        fig4.update_yaxes(title="")
        st.plotly_chart(fig4, use_container_width=True)

# ----- TAB 3: LINE COMPARISON -----
with tab_line:
    st.subheader("3. Production Line Comparison")
    comp_code = st.selectbox("Select Paint Code for Line Comparison", filter_df["Paint_Code"].unique(), key="line_comp")
    comp_df = filter_df[filter_df["Paint_Code"] == comp_code]
    line_summary = build_summary(comp_df, ["線別"]).sort_values("線別")

    if len(line_summary) < 2:
        st.warning("⚠️ Need at least two lines selected to compare.")
    else:
        ch5, ch6 = st.columns(2)
        with ch5:
            fig5 = go.Figure()
            for i, row in line_summary.iterrows():
                fig5.add_trace(go.Scatter(x=[row["Median_After_Viscosity"], row["Median_Before_Viscosity"]], y=[row["線別"], row["線別"]], mode="lines+markers", marker=dict(size=12), name=row["線別"]))
            fig5.update_layout(title="Viscosity Drop (Before vs After)", xaxis_title="Viscosity (s)", yaxis_title="")
            st.plotly_chart(fig5, use_container_width=True)

        with ch6:
            fig6 = px.bar(line_summary.sort_values("Weighted_Ratio_Percent"), x="Weighted_Ratio_Percent", y="線別", orientation='h', text_auto='.2f', title="Weighted Solvent Ratio")
            fig6.update_yaxes(title="")
            st.plotly_chart(fig6, use_container_width=True)

        st.dataframe(line_summary.style.format(precision=2), use_container_width=True)
