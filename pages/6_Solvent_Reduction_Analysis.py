import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
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
# WEIGHT LOGIC
# Source column 塗料重量 is the total weight after solvent addition.
# Preserve the source value and calculate the original paint weight separately.
# ---------------------------------------------------------
df["Mixture_Weight_kg"] = df["塗料重量"]
df["Base_Paint_Weight_kg"] = df["Mixture_Weight_kg"] - df["添加重量"]

df["Delta_V"] = df["黏度(秒)"] - df["黏度(秒)_1"]
df["Solvent_Ratio_Percent"] = np.where(
    df["Base_Paint_Weight_kg"] > 0,
    df["添加重量"] / df["Base_Paint_Weight_kg"] * 100,
    np.nan,
)
df["Viscosity_Sensitivity"] = np.where(
    df["Solvent_Ratio_Percent"] > 0,
    df["Delta_V"] / df["Solvent_Ratio_Percent"],
    np.nan,
)

# Strict validation after reconstructing the original paint weight
df = df[
    (df["Base_Paint_Weight_kg"] > 0)
    & (df["添加重量"] > 0)
    & (df["黏度(秒)"] > 0)
    & (df["黏度(秒)_1"] > 0)
    & (df["Delta_V"] > 0)
].copy()

if df.empty:
    st.warning("⚠️ No valid dilution records remain after data cleaning.")
    st.stop()

# ==========================================
# 2.1 TIME PARSING & RECORD SELECTION LOGIC
# ==========================================
date_col = next((c for c in ["攪拌日期", "調整日期", "生產日期", "Date"] if c in df.columns), None)
time_col = next((c for c in ["攪拌時間(迄)", "攪拌時間", "Time"] if c in df.columns), None)

if date_col:
    date_part = pd.to_datetime(df[date_col], errors="coerce")
    df["_Analysis_Date"] = date_part
else:
    date_part = pd.Series(pd.NaT, index=df.index)
    df["_Analysis_Date"] = pd.NaT

if time_col:
    time_text = (
        df[time_col]
        .fillna("")
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(":", "", regex=False)
        .str.zfill(4)
    )
    valid_time = time_text.str.fullmatch(r"\d{4}")
    hours = pd.to_numeric(time_text.str[:2], errors="coerce")
    minutes = pd.to_numeric(time_text.str[2:4], errors="coerce")
    valid_time &= hours.between(0, 23) & minutes.between(0, 59)
    time_delta = pd.to_timedelta(
        np.where(valid_time, hours * 60 + minutes, np.nan), unit="m"
    )
    df["_Analysis_DateTime"] = date_part.dt.normalize() + time_delta
else:
    df["_Analysis_DateTime"] = date_part

# Preserve source row order as a final tie-breaker when timestamps are missing/equal.
df["_Source_Order"] = np.arange(len(df))
df = df.sort_values(
    ["Batch_ID", "Bucket_Number", "_Analysis_DateTime", "_Source_Order"],
    ascending=True,
    na_position="first",
)

# PS30213X8: every row is an independent adjustment and must be retained.
# Other paint codes: repeated rows for the same batch + bucket are cumulative
# adjustments, therefore only the final chronological record is representative.
special_paint_codes = {"PS30213X8"}
is_special_paint = df["Paint_Code"].isin(special_paint_codes)

df_standard = (
    df.loc[~is_special_paint]
    .drop_duplicates(subset=["Batch_ID", "Bucket_Number"], keep="last")
    .copy()
)
df_special = df.loc[is_special_paint].copy()

df = pd.concat([df_standard, df_special], ignore_index=True)
df = df.sort_values(
    ["_Analysis_DateTime", "Batch_ID", "Bucket_Number", "_Source_Order"],
    ascending=True,
    na_position="last",
).reset_index(drop=True)

# ==========================================
# 3. CORE LOGIC HELPER
# ==========================================
def build_summary(source_df, group_cols):
    if source_df.empty: return pd.DataFrame()
    
    agg_dict = {
        "Adjustment_Records": ("Paint_Code", "size"),
        "Historical_Batches": ("Batch_ID", "nunique"),
        "Total_Paint_kg": ("Base_Paint_Weight_kg", "sum"),
        "Total_Solvent_kg": ("添加重量", "sum"),
        "Median_Paint_kg": ("Base_Paint_Weight_kg", "median"),
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


def apply_professional_layout(fig, title_text=None, subtitle_text=None, height=None):
    """Apply a cleaner business-style Plotly layout with black text."""
    if title_text is not None:
        title_html = f"<b>{title_text}</b>"
        if subtitle_text:
            title_html += f"<br><sup>{subtitle_text}</sup>"
        fig.update_layout(
            title=dict(
                text=title_html,
                x=0.0,
                xanchor="left",
                font=dict(size=22, color="#000000"),
            )
        )

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#000000", size=13),
        hoverlabel=dict(
            bgcolor="white",
            font=dict(color="#000000", size=12),
            bordercolor="#D1D5DB",
        ),
        legend=dict(
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="rgba(0,0,0,0)",
            font=dict(color="#000000", size=12),
            title=dict(font=dict(color="#000000", size=12)),
        ),
        margin=dict(l=70, r=40, t=110, b=70),
    )
    if height is not None:
        fig.update_layout(height=height)

    fig.update_xaxes(
        showline=True,
        linewidth=1.2,
        linecolor="#111827",
        mirror=False,
        ticks="outside",
        tickfont=dict(color="#000000", size=12),
        title_font=dict(color="#000000", size=14),
        gridcolor="#E5E7EB",
        zeroline=False,
    )
    fig.update_yaxes(
        showline=True,
        linewidth=1.2,
        linecolor="#111827",
        mirror=False,
        ticks="outside",
        tickfont=dict(color="#000000", size=12),
        title_font=dict(color="#000000", size=14),
        gridcolor="#E5E7EB",
        zerolinecolor="#D1D5DB",
    )
    return fig


def create_decision_matrix_png(plot_df, target_opportunity_limit):
    """Create a Word-exportable decision matrix chart using Matplotlib (no Kaleido)."""
    fig, ax = plt.subplots(figsize=(10.5, 6.5), dpi=180)

    export_colors = {
        "優先試用 (Quick Wins)": "#1D4ED8",
        "次要評估 (Secondary)": "#60A5FA",
        "需先標準化 (Standardize First)": "#F97316",
        "暫不考慮 (Ignore)": "#FDBA74",
    }

    if plot_df.empty:
        ax.text(0.5, 0.5, "No data available", ha="center", va="center", fontsize=12, color="black")
    else:
        max_solvent = max(float(plot_df["Total_Solvent_kg"].max()), 1.0)
        sizes = 30 + (plot_df["Total_Solvent_kg"] / max_solvent) * 650

        for strategy, subdf in plot_df.groupby("Strategy_Quadrant"):
            ax.scatter(
                subdf["Matrix_X"],
                subdf["Estimated_Reduction_kg"],
                s=sizes.loc[subdf.index],
                c=export_colors.get(strategy, "#9CA3AF"),
                edgecolors="white",
                linewidths=1.0,
                alpha=0.85,
                label=strategy,
                zorder=3,
            )

        max_y = max(float(plot_df["Estimated_Reduction_kg"].max()), 1.0)
        ax.axvline(2.5, color="#DC2626", linestyle=(0, (4, 4)), linewidth=1.2, zorder=2)
        ax.axhline(target_opportunity_limit, color="#DC2626", linestyle=(0, (4, 4)), linewidth=1.2, zorder=2)

        important = plot_df.copy()
        important["Label_Priority"] = 0
        important.loc[important["Strategy_Quadrant"] == "優先試用 (Quick Wins)", "Label_Priority"] = 4
        important.loc[important["Strategy_Quadrant"] == "需先標準化 (Standardize First)", "Label_Priority"] = 3
        important.loc[important["Estimated_Reduction_kg"] >= target_opportunity_limit * 1.8, "Label_Priority"] = np.maximum(
            important.loc[important["Estimated_Reduction_kg"] >= target_opportunity_limit * 1.8, "Label_Priority"], 2
        )
        important.loc[important["High_Stability_Count"] == 3, "Label_Priority"] = np.maximum(
            important.loc[important["High_Stability_Count"] == 3, "Label_Priority"], 1
        )
        important = important[important["Label_Priority"] > 0].sort_values(
            ["Label_Priority", "Estimated_Reduction_kg", "Total_Solvent_kg"], ascending=[False, False, False]
        )
        important["Label_Rank_In_X"] = important.groupby("High_Stability_Count").cumcount()
        important = important[important["Label_Rank_In_X"] < 3].head(12)

        x_offsets = [0.00, -0.12, 0.12]
        y_offsets = [180, 320, 460]
        for _, row in important.iterrows():
            rank = int(row["Label_Rank_In_X"]) % 3
            ax.annotate(
                row["Paint_Code"],
                xy=(row["Matrix_X"], row["Estimated_Reduction_kg"]),
                xytext=(row["Matrix_X"] + x_offsets[rank], row["Estimated_Reduction_kg"] + y_offsets[rank]),
                textcoords="data",
                fontsize=9,
                color="black",
                ha="center",
                va="bottom",
                bbox=dict(boxstyle="round,pad=0.20", facecolor="white", edgecolor="#9CA3AF", linewidth=0.8),
                arrowprops=dict(arrowstyle="-", color="#9CA3AF", lw=0.8),
                zorder=4,
            )

        ax.text(2.55, max_y * 1.06, "高穩定區", fontsize=10, color="black", ha="left", va="bottom",
                bbox=dict(facecolor="white", edgecolor="#DC2626", linewidth=0.8, pad=2))
        ax.text(3.35, target_opportunity_limit + max_y * 0.015, f"高減量機會門檻：{target_opportunity_limit:,.0f} kg",
                fontsize=10, color="black", ha="right", va="bottom",
                bbox=dict(facecolor="white", edgecolor="#DC2626", linewidth=0.8, pad=2))

        ax.set_xlim(-0.45, 3.45)
        ax.set_ylim(-max_y * 0.05, max_y * 1.15)

    ax.set_title("試用色號決策矩陣", fontsize=16, fontweight="bold", color="black", pad=18)
    ax.text(0.0, 1.02, "X軸＝高穩定指標數（0–3）；Y軸＝預估稀釋劑減量機會；氣泡大小＝稀釋劑總用量",
            transform=ax.transAxes, fontsize=10.5, color="black", ha="left", va="bottom")
    ax.set_xlabel("高穩定指標數 (0–3)", fontsize=11.5, color="black")
    ax.set_ylabel("預估稀釋劑減量機會 (kg)", fontsize=11.5, color="black")
    ax.set_xticks([0, 1, 2, 3])
    ax.tick_params(axis="both", colors="black", labelsize=10)
    ax.grid(axis="y", color="#E5E7EB", linewidth=0.8)
    ax.set_facecolor("white")

    # Four-sided professional frame
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("#111827")
        spine.set_linewidth(1.2)

    handles, labels = ax.get_legend_handles_labels()
    if handles:
        by_label = dict(zip(labels, handles))
        leg = ax.legend(
            by_label.values(), by_label.keys(), ncol=2, loc="upper left", bbox_to_anchor=(0, 1.0),
            frameon=False, fontsize=9.5
        )
        for txt in leg.get_texts():
            txt.set_color("black")

    fig.patch.set_facecolor("white")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white", dpi=220)
    plt.close(fig)
    buf.seek(0)
    return buf

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

    with ch2:
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

    st.markdown("---")
    
    # Dual Axis Chart
    fig_dual = go.Figure()
    
    fig_dual.add_trace(go.Bar(
        x=summary_df["Paint_Code"], 
        y=summary_df["Total_Paint_kg"], 
        name="Paint (kg)", 
        marker_color="#5B8FF9", 
        yaxis="y1",
        text=summary_df["Total_Paint_kg"].apply(lambda x: f"{x:,.0f}"), 
        textposition="auto"
    ))
    
    fig_dual.add_trace(go.Bar(
        x=summary_df["Paint_Code"], 
        y=summary_df["Total_Solvent_kg"], 
        name="Solvent (kg)", 
        marker_color="#F6BD16", 
        yaxis="y1",
        text=summary_df["Total_Solvent_kg"].apply(lambda x: f"{x:,.0f}"),
        textposition="auto"
    ))
    
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
        uniformtext_mode='hide' 
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

    # ---------------------------------------------------------
    # DATA AUDIT TABLE (CONSISTENCY TRACEABILITY)
    # ---------------------------------------------------------
    st.markdown("---")
    st.markdown("### 📊 添加比例一致性明細 (Ratio Consistency Audit)")
    st.markdown("以中位數與 MAD 建立資料驅動範圍，不再使用人工設定的固定 ±2%。")

    def median_absolute_deviation(series):
        values = pd.to_numeric(series, errors="coerce").dropna()
        if values.empty:
            return np.nan
        median_value = values.median()
        return float(np.median(np.abs(values - median_value)))

    if not detail_df.empty:
        ratio_values = detail_df["Solvent_Ratio_Percent"].dropna()
        median_ratio = ratio_values.median()
        ratio_mad = median_absolute_deviation(ratio_values)
        tolerance = max(1.0, 1.5 * ratio_mad) if pd.notna(ratio_mad) else 1.0
        lower_bound = max(0.0, median_ratio - tolerance)
        upper_bound = median_ratio + tolerance

        st.info(
            f"🎯 **Median:** {median_ratio:.2f}% ｜ "
            f"**MAD:** {ratio_mad:.2f}% ｜ "
            f"**一致範圍:** {lower_bound:.2f}%～{upper_bound:.2f}%"
        )

        audit_cols = ["_Analysis_DateTime", "Batch_ID", "Bucket_Number", "Solvent_Ratio_Percent", "Viscosity_Sensitivity"]
        audit_df = detail_df[audit_cols].copy()

        def evaluate_consistency(val):
            if pd.isna(val):
                return "⚠️ N/A"
            return "✅ 一致" if lower_bound <= val <= upper_bound else "⚠️ 偏離"

        audit_df["Consistency_Status"] = audit_df["Solvent_Ratio_Percent"].apply(evaluate_consistency)
        valid_records = audit_df.dropna(subset=["Solvent_Ratio_Percent"])
        consistent_count = (valid_records["Consistency_Status"] == "✅ 一致").sum()
        total_count = len(valid_records)
        ratio_consistency = consistent_count / total_count * 100 if total_count else 0

        st.success(
            f"📈 **添加比例一致率:** {consistent_count}/{total_count} 筆位於資料驅動範圍內 "
            f"➔ **{ratio_consistency:.1f}%**"
        )

        audit_df["Solvent_Ratio_Percent"] = audit_df["Solvent_Ratio_Percent"].map(
            lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A"
        )
        audit_df["Viscosity_Sensitivity"] = audit_df["Viscosity_Sensitivity"].map(
            lambda x: f"{x:.2f} s/%" if pd.notna(x) else "N/A"
        )

        st.dataframe(
            audit_df,
            column_config={
                "_Analysis_DateTime": "調整時間",
                "Batch_ID": "塗料批號",
                "Bucket_Number": "塗料桶號",
                "Solvent_Ratio_Percent": "稀釋劑添加比例",
                "Viscosity_Sensitivity": "降黏效率",
                "Consistency_Status": "一致性判定",
            },
            use_container_width=True,
            hide_index=True,
        )

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
    else:
        used_line = line_summary["線別"].iloc[0] if not line_summary.empty else "Unknown"
        st.info(f"ℹ️ Paint code **{comp_code}** is currently only used on line **{used_line}**. Comparison requires data from at least two production lines. (此色號僅在單一產線使用，無法進行比較)")

# ----- TAB 4: PILOT PAINT CODE EVALUATION -----
with tab_pilot:
    st.subheader("4. 試用色號評估矩陣 (Pilot Paint Code Matrix)")
    st.markdown(
        "以預估減量機會及三項歷史穩定指標找出適合先進行減量試用的色號。"
        "各指標依相同製程條件下的歷史分布，以 P33／P67 分成高、中、低三組，"
        "不使用人工設定的 50–30–20 權重或固定 20% 門檻。"
    )

    set1, set2, set3 = st.columns(3)
    with set1:
        min_pilot_records = st.number_input(
            "最低歷史紀錄數", min_value=5, value=20, step=1
        )
    with set2:
        target_opportunity_limit = st.number_input(
            "高減量機會門檻 (kg)", min_value=0.0, value=500.0, step=100.0
        )
    with set3:
        min_peer_codes = st.number_input(
            "同條件最低比較色號數", min_value=3, value=5, step=1,
            help="同一 Vendor、Resin、Position、Solvent Type 至少需有此數量的色號，才使用組內 P33/P67；不足時改用全體合格色號分布。"
        )

    st.info(
        "判定原則：添加比例一致率越高越好；降黏效率相對變異越低越好；"
        "添加比例時間趨勢的絕對值越低越好。三項皆屬高穩定，才判定為高穩定。"
    )

    def robust_mad(series):
        values = pd.to_numeric(series, errors="coerce").dropna()
        if values.empty:
            return np.nan
        median_value = values.median()
        return float(np.median(np.abs(values - median_value)))

    def ratio_consistency(series):
        values = pd.to_numeric(series, errors="coerce").dropna()
        if len(values) < 5:
            return np.nan
        median_value = values.median()
        mad = robust_mad(values)
        tolerance = max(1.0, 1.5 * mad)
        lower = max(0.0, median_value - tolerance)
        upper = median_value + tolerance
        return values.between(lower, upper, inclusive="both").mean()

    def robust_relative_variation(series):
        values = pd.to_numeric(series, errors="coerce").dropna()
        if len(values) < 5:
            return np.nan
        median_value = values.median()
        if median_value <= 0:
            return np.nan
        return robust_mad(values) / median_value

    group_keys = ["Vendor", "Resin", "Position_UI", "Solvent_Type", "Paint_Code"]
    peer_keys = ["Vendor", "Resin", "Position_UI", "Solvent_Type"]

    pilot_df = filter_df.groupby(group_keys, dropna=False).agg(
        Historical_Records=("Paint_Code", "size"),
        Historical_Batches=("Batch_ID", "nunique"),
        Total_Paint_kg=("Base_Paint_Weight_kg", "sum"),
        Total_Solvent_kg=("添加重量", "sum"),
        Median_Ratio_Percent=("Solvent_Ratio_Percent", "median"),
        Ratio_Consistency=("Solvent_Ratio_Percent", ratio_consistency),
        Ratio_Robust_Variation=("Solvent_Ratio_Percent", robust_relative_variation),
        Median_Efficiency=("Viscosity_Sensitivity", "median"),
        Efficiency_Relative_Variation=("Viscosity_Sensitivity", robust_relative_variation),
    ).reset_index()

    def trend_per_10_records(group):
        temp = group.dropna(subset=["Solvent_Ratio_Percent"]).sort_values(
            ["_Analysis_DateTime", "_Source_Order"], na_position="last"
        )
        if len(temp) < 5:
            return np.nan
        x = np.arange(len(temp), dtype=float)
        y = temp["Solvent_Ratio_Percent"].to_numpy(dtype=float)
        return float(np.polyfit(x, y, 1)[0] * 10)

    trend_df = (
        filter_df.groupby(group_keys, dropna=False)
        .apply(trend_per_10_records)
        .reset_index(name="Ratio_Trend_Per_10_Records")
    )
    pilot_df = pilot_df.merge(trend_df, on=group_keys, how="left")
    pilot_df["Abs_Ratio_Trend_Per_10_Records"] = pilot_df[
        "Ratio_Trend_Per_10_Records"
    ].abs()

    pilot_df["Weighted_Ratio_Percent"] = np.where(
        pilot_df["Total_Paint_kg"] > 0,
        pilot_df["Total_Solvent_kg"] / pilot_df["Total_Paint_kg"] * 100,
        np.nan,
    )

    # Only sufficiently covered paint codes participate in benchmarking.
    eligible_df = pilot_df[
        pilot_df["Historical_Records"] >= min_pilot_records
    ].copy()

    # Reduction benchmark: P25 weighted solvent ratio achieved by comparable paint codes.
    benchmark_df = (
        eligible_df.groupby(peer_keys, dropna=False)["Weighted_Ratio_Percent"]
        .quantile(0.25)
        .reset_index(name="Benchmark_Ratio_Percent")
    )
    pilot_df = pilot_df.merge(benchmark_df, on=peer_keys, how="left")
    pilot_df["Estimated_Reduction_kg"] = (
        pilot_df["Total_Solvent_kg"]
        - pilot_df["Total_Paint_kg"] * pilot_df["Benchmark_Ratio_Percent"] / 100
    ).clip(lower=0)

    # ------------------------------------------------------
    # DATA-DRIVEN STABILITY BENCHMARKS
    # ------------------------------------------------------
    metric_rules = {
        "Ratio_Consistency": "higher",
        "Efficiency_Relative_Variation": "lower",
        "Abs_Ratio_Trend_Per_10_Records": "lower",
    }

    # Global fallback thresholds derived only from eligible paint codes.
    global_thresholds = {}
    for metric in metric_rules:
        valid = pd.to_numeric(eligible_df[metric], errors="coerce").dropna()
        global_thresholds[metric] = {
            "P33": valid.quantile(0.33) if not valid.empty else np.nan,
            "P67": valid.quantile(0.67) if not valid.empty else np.nan,
        }

    peer_stats = (
        eligible_df.groupby(peer_keys, dropna=False)
        .agg(
            Peer_Code_Count=("Paint_Code", "nunique"),
            Ratio_Consistency_P33=("Ratio_Consistency", lambda x: x.dropna().quantile(0.33)),
            Ratio_Consistency_P67=("Ratio_Consistency", lambda x: x.dropna().quantile(0.67)),
            Efficiency_Variation_P33=("Efficiency_Relative_Variation", lambda x: x.dropna().quantile(0.33)),
            Efficiency_Variation_P67=("Efficiency_Relative_Variation", lambda x: x.dropna().quantile(0.67)),
            Trend_Abs_P33=("Abs_Ratio_Trend_Per_10_Records", lambda x: x.dropna().quantile(0.33)),
            Trend_Abs_P67=("Abs_Ratio_Trend_Per_10_Records", lambda x: x.dropna().quantile(0.67)),
        )
        .reset_index()
    )
    pilot_df = pilot_df.merge(peer_stats, on=peer_keys, how="left")

    def select_thresholds(row, metric):
        use_peer = pd.notna(row.get("Peer_Code_Count")) and row["Peer_Code_Count"] >= min_peer_codes
        mapping = {
            "Ratio_Consistency": ("Ratio_Consistency_P33", "Ratio_Consistency_P67"),
            "Efficiency_Relative_Variation": ("Efficiency_Variation_P33", "Efficiency_Variation_P67"),
            "Abs_Ratio_Trend_Per_10_Records": ("Trend_Abs_P33", "Trend_Abs_P67"),
        }
        p33_col, p67_col = mapping[metric]
        if use_peer and pd.notna(row.get(p33_col)) and pd.notna(row.get(p67_col)):
            return row[p33_col], row[p67_col], "同條件分布"
        return (
            global_thresholds[metric]["P33"],
            global_thresholds[metric]["P67"],
            "全體分布",
        )

    def classify_by_distribution(value, p33, p67, direction):
        if pd.isna(value) or pd.isna(p33) or pd.isna(p67):
            return "資料不足"
        if direction == "higher":
            if value >= p67:
                return "高穩定"
            if value >= p33:
                return "中等穩定"
            return "低穩定"
        if value <= p33:
            return "高穩定"
        if value <= p67:
            return "中等穩定"
        return "低穩定"

    def evaluate_stability_row(row):
        ratio_p33, ratio_p67, ratio_source = select_thresholds(row, "Ratio_Consistency")
        eff_p33, eff_p67, eff_source = select_thresholds(row, "Efficiency_Relative_Variation")
        trend_p33, trend_p67, trend_source = select_thresholds(row, "Abs_Ratio_Trend_Per_10_Records")

        ratio_level = classify_by_distribution(
            row["Ratio_Consistency"], ratio_p33, ratio_p67, "higher"
        )
        efficiency_level = classify_by_distribution(
            row["Efficiency_Relative_Variation"], eff_p33, eff_p67, "lower"
        )
        trend_level = classify_by_distribution(
            row["Abs_Ratio_Trend_Per_10_Records"], trend_p33, trend_p67, "lower"
        )

        levels = [ratio_level, efficiency_level, trend_level]
        if "資料不足" in levels:
            overall = "資料不足"
            high_count = np.nan
        else:
            high_count = sum(level == "高穩定" for level in levels)
            if high_count == 3:
                overall = "高穩定"
            elif "低穩定" not in levels:
                overall = "中等穩定"
            else:
                overall = "低穩定"

        sources = {ratio_source, eff_source, trend_source}
        benchmark_source = "同條件分布" if sources == {"同條件分布"} else "全體分布補充"

        return pd.Series({
            "Ratio_Stability_Level": ratio_level,
            "Efficiency_Stability_Level": efficiency_level,
            "Trend_Stability_Level": trend_level,
            "High_Stability_Count": high_count,
            "Stability_Level": overall,
            "Stability_Benchmark_Source": benchmark_source,
            "Ratio_P33_Used": ratio_p33,
            "Ratio_P67_Used": ratio_p67,
            "Efficiency_P33_Used": eff_p33,
            "Efficiency_P67_Used": eff_p67,
            "Trend_P33_Used": trend_p33,
            "Trend_P67_Used": trend_p67,
        })

    stability_result = pilot_df.apply(evaluate_stability_row, axis=1)
    pilot_df = pd.concat([pilot_df, stability_result], axis=1)
    pilot_df = pilot_df[pilot_df["Historical_Records"] >= min_pilot_records].copy()

    def classify_quadrant(row):
        high_opportunity = row["Estimated_Reduction_kg"] >= target_opportunity_limit
        high_stability = row["Stability_Level"] == "高穩定"
        if high_opportunity and high_stability:
            return "優先試用 (Quick Wins)"
        if high_opportunity and not high_stability:
            return "需先標準化 (Standardize First)"
        if not high_opportunity and high_stability:
            return "次要評估 (Secondary)"
        return "暫不考慮 (Ignore)"

    if not pilot_df.empty:
        pilot_df["Strategy_Quadrant"] = pilot_df.apply(classify_quadrant, axis=1)

        color_map = {
            "優先試用 (Quick Wins)": "#1D4ED8",
            "需先標準化 (Standardize First)": "#F97316",
            "次要評估 (Secondary)": "#60A5FA",
            "暫不考慮 (Ignore)": "#FDBA74",
        }

        # X-axis shows the number of indicators classified as high stability (0–3).
        # Use slight horizontal jitter only for display, so bubbles and labels do not stack.
        plot_df = pilot_df.dropna(subset=["High_Stability_Count"]).copy()

        if not plot_df.empty:
            plot_df = plot_df.sort_values(
                ["High_Stability_Count", "Estimated_Reduction_kg", "Total_Solvent_kg"],
                ascending=[True, False, False],
            ).reset_index(drop=True)

            jitter_pattern = [0.00, -0.14, 0.14, -0.22, 0.22, -0.30, 0.30]

            # Avoid groupby.apply() here because Pandas 3.x may exclude
            # the grouping column from each group.
            plot_df["Display_Order_In_X"] = (
                plot_df.groupby("High_Stability_Count").cumcount()
            )
            plot_df["Matrix_X"] = (
                plot_df["High_Stability_Count"].astype(float)
                + plot_df["Display_Order_In_X"].map(
                    lambda i: jitter_pattern[int(i) % len(jitter_pattern)]
                )
            )

            fig_matrix = px.scatter(
                plot_df,
                x="Matrix_X",
                y="Estimated_Reduction_kg",
                size="Total_Solvent_kg",
                size_max=38,
                color="Strategy_Quadrant",
                color_discrete_map=color_map,
                hover_name="Paint_Code",
                custom_data=[
                    "High_Stability_Count",
                    "Total_Solvent_kg",
                    "Weighted_Ratio_Percent",
                    "Benchmark_Ratio_Percent",
                    "Estimated_Reduction_kg",
                    "Ratio_Consistency",
                    "Ratio_Stability_Level",
                    "Efficiency_Relative_Variation",
                    "Efficiency_Stability_Level",
                    "Ratio_Trend_Per_10_Records",
                    "Trend_Stability_Level",
                    "Historical_Records",
                    "Stability_Benchmark_Source",
                ],
                title=None,
                height=720,
            )

            fig_matrix.update_traces(
                mode="markers",
                marker=dict(opacity=0.82, line=dict(width=1.3, color="white")),
                hovertemplate=(
                    "<b>%{hovertext}</b><br>──────────────────<br>"
                    "高穩定指標數: %{customdata[0]:.0f}/3<br>"
                    "預估減量機會: %{customdata[4]:,.1f} kg<br>"
                    "稀釋劑總用量: %{customdata[1]:,.1f} kg<br>"
                    "目前加權比例: %{customdata[2]:.2f}%<br>"
                    "同條件基準比例: %{customdata[3]:.2f}%<br>"
                    "添加比例一致率: %{customdata[5]:.1%}（%{customdata[6]}）<br>"
                    "降黏效率相對變異: %{customdata[7]:.3f}（%{customdata[8]}）<br>"
                    "每10筆比例趨勢: %{customdata[9]:+.2f} 個百分點（%{customdata[10]}）<br>"
                    "歷史紀錄數: %{customdata[11]:,.0f} 筆<br>"
                    "比較基準: %{customdata[12]}<extra></extra>"
                ),
            )

            apply_professional_layout(
                fig_matrix,
                title_text="試用色號決策矩陣",
                subtitle_text="X軸＝高穩定指標數（0–3）；Y軸＝預估稀釋劑減量機會；氣泡大小＝稀釋劑總用量",
                height=720,
            )

            fig_matrix.update_xaxes(
                title="高穩定指標數 (0–3)",
                tickmode="array",
                tickvals=[0, 1, 2, 3],
                ticktext=["0", "1", "2", "3"],
                range=[-0.45, 3.45],
                mirror=True,
                showline=True,
                linecolor="#111827",
                linewidth=1.2,
            )
            max_y = max(float(plot_df["Estimated_Reduction_kg"].max()), 1.0)
            fig_matrix.update_yaxes(
                title="預估稀釋劑減量機會 (kg)",
                range=[-max_y * 0.05, max_y * 1.15],
                mirror=True,
                showline=True,
                linecolor="#111827",
                linewidth=1.2,
            )
            fig_matrix.update_layout(
                legend=dict(
                    title="策略分類",
                    orientation="h",
                    yanchor="bottom",
                    y=1.08,
                    xanchor="left",
                    x=0.0,
                    font=dict(color="#000000", size=12),
                    title_font=dict(color="#000000", size=12),
                )
            )

            fig_matrix.add_vline(
                x=2.5, line_dash="dash", line_color="#D62728", line_width=1.6, opacity=0.85
            )
            fig_matrix.add_hline(
                y=target_opportunity_limit, line_dash="dash", line_color="#D62728",
                line_width=1.6, opacity=0.85
            )
            fig_matrix.add_annotation(
                x=2.52, y=max_y * 1.08, text="高穩定區", showarrow=False,
                font=dict(size=12, color="#000000"), bgcolor="rgba(255,255,255,0.9)",
                bordercolor="#D62728", borderwidth=1, borderpad=3
            )
            fig_matrix.add_annotation(
                x=3.36, y=target_opportunity_limit,
                text=f"高減量機會門檻：{target_opportunity_limit:,.0f} kg",
                showarrow=False, xanchor="right", yanchor="bottom",
                font=dict(size=12, color="#000000"), bgcolor="rgba(255,255,255,0.9)",
                bordercolor="#D62728", borderwidth=1, borderpad=3
            )

            # Label only the most important points and stagger annotations to avoid overlap.
            plot_df["Label_Priority"] = 0
            plot_df.loc[plot_df["Strategy_Quadrant"] == "優先試用 (Quick Wins)", "Label_Priority"] = 4
            plot_df.loc[plot_df["Strategy_Quadrant"] == "需先標準化 (Standardize First)", "Label_Priority"] = 3
            plot_df.loc[plot_df["Estimated_Reduction_kg"] >= target_opportunity_limit * 1.8, "Label_Priority"] = np.maximum(
                plot_df.loc[plot_df["Estimated_Reduction_kg"] >= target_opportunity_limit * 1.8, "Label_Priority"],
                2,
            )
            plot_df.loc[plot_df["High_Stability_Count"] == 3, "Label_Priority"] = np.maximum(
                plot_df.loc[plot_df["High_Stability_Count"] == 3, "Label_Priority"],
                1,
            )

            label_df = plot_df[plot_df["Label_Priority"] > 0].copy()
            if not label_df.empty:
                label_df = label_df.sort_values(
                    ["Label_Priority", "Estimated_Reduction_kg", "Total_Solvent_kg"],
                    ascending=[False, False, False],
                )
                label_df["Label_Rank_In_X"] = label_df.groupby("High_Stability_Count").cumcount()
                label_df = label_df[label_df["Label_Rank_In_X"] < 3].head(12)

                x_shift_pattern = [0, -32, 32]
                y_shift_pattern = [-24, -42, -60]

                for _, row in label_df.iterrows():
                    rank_in_x = int(row["Label_Rank_In_X"])
                    fig_matrix.add_annotation(
                        x=float(row["Matrix_X"]),
                        y=float(row["Estimated_Reduction_kg"]),
                        text=str(row["Paint_Code"]),
                        showarrow=True,
                        arrowhead=0,
                        arrowcolor="rgba(0,0,0,0.35)",
                        arrowwidth=1,
                        ax=x_shift_pattern[rank_in_x % len(x_shift_pattern)],
                        ay=y_shift_pattern[rank_in_x % len(y_shift_pattern)],
                        font=dict(size=12, color="#000000"),
                        bgcolor="rgba(255,255,255,0.96)",
                        bordercolor="rgba(0,0,0,0.25)",
                        borderwidth=1,
                        borderpad=3,
                        align="center",
                    )

            matrix_export_plot_df = plot_df.copy()
            st.plotly_chart(fig_matrix, use_container_width=True)
            exported_figs["9. Decision Matrix"] = fig_matrix
        else:
            st.warning("⚠️ 穩定指標資料不足，無法繪製決策矩陣。")

        st.markdown("---")
        st.markdown("### 評估結果明細")
        out_cols = [
            "Paint_Code", "Strategy_Quadrant", "Stability_Level",
            "High_Stability_Count", "Stability_Benchmark_Source",
            "Estimated_Reduction_kg", "Total_Solvent_kg",
            "Weighted_Ratio_Percent", "Benchmark_Ratio_Percent",
            "Ratio_Consistency", "Ratio_Stability_Level",
            "Efficiency_Relative_Variation", "Efficiency_Stability_Level",
            "Ratio_Trend_Per_10_Records", "Trend_Stability_Level",
            "Historical_Records", "Historical_Batches",
        ]
        display_df = pilot_df[out_cols].sort_values(
            ["Strategy_Quadrant", "Estimated_Reduction_kg"], ascending=[True, False]
        )
        display_df["Ratio_Consistency"] = display_df["Ratio_Consistency"] * 100

        st.dataframe(
            display_df,
            column_config={
                "Paint_Code": "色號",
                "Strategy_Quadrant": "策略分類",
                "Stability_Level": "整體穩定判定",
                "High_Stability_Count": st.column_config.NumberColumn("高穩定指標數", format="%.0f/3"),
                "Stability_Benchmark_Source": "穩定比較基準",
                "Estimated_Reduction_kg": st.column_config.NumberColumn("預估減量機會 (kg)", format="%.1f"),
                "Total_Solvent_kg": st.column_config.NumberColumn("稀釋劑總用量 (kg)", format="%.1f"),
                "Weighted_Ratio_Percent": st.column_config.NumberColumn("目前加權比例 (%)", format="%.2f"),
                "Benchmark_Ratio_Percent": st.column_config.NumberColumn("同條件基準比例 (%)", format="%.2f"),
                "Ratio_Consistency": st.column_config.NumberColumn("添加比例一致率 (%)", format="%.1f"),
                "Ratio_Stability_Level": "添加比例判定",
                "Efficiency_Relative_Variation": st.column_config.NumberColumn("降黏效率相對變異", format="%.3f"),
                "Efficiency_Stability_Level": "降黏效率判定",
                "Ratio_Trend_Per_10_Records": st.column_config.NumberColumn("每10筆比例趨勢", format="%+.2f"),
                "Trend_Stability_Level": "時間趨勢判定",
                "Historical_Records": "紀錄數",
                "Historical_Batches": "歷史批數",
            },
            use_container_width=True,
            hide_index=True,
        )

        quick_wins = display_df[
            display_df["Strategy_Quadrant"] == "優先試用 (Quick Wins)"
        ]
        if not quick_wins.empty:
            top_code = quick_wins.iloc[0]
            st.success(
                f"✅ 建議優先試用：{top_code['Paint_Code']}；"
                f"三項穩定指標皆屬高穩定，"
                f"預估減量機會約 {top_code['Estimated_Reduction_kg']:.1f} kg。"
            )
        else:
            st.info("目前沒有同時達到高減量機會且三項穩定指標皆屬高穩定的色號。")

        with st.expander("查看本次分析使用的 P33／P67 判定基準"):
            threshold_rows = []
            for metric, label, direction in [
                ("Ratio_Consistency", "添加比例一致率", "越高越好"),
                ("Efficiency_Relative_Variation", "降黏效率相對變異", "越低越好"),
                ("Abs_Ratio_Trend_Per_10_Records", "時間趨勢絕對值", "越低越好"),
            ]:
                threshold_rows.append({
                    "指標": label,
                    "方向": direction,
                    "全體P33": global_thresholds[metric]["P33"],
                    "全體P67": global_thresholds[metric]["P67"],
                })
            st.dataframe(pd.DataFrame(threshold_rows), use_container_width=True, hide_index=True)
    else:
        display_df = pd.DataFrame()
        st.warning("⚠️ 歷史紀錄數不足，無法產生矩陣分析。")

# ==========================================
# 7. EXPORT INTERACTIVE HTML REPORT
# ==========================================
st.markdown("---")
st.subheader("📄 Export Report")

export_col1, export_col2 = st.columns(2)

with export_col1:
    st.info("💡 匯出 Word 報告會使用 Matplotlib 產生圖檔，不使用 Kaleido。")
    if HAS_DOCX and st.button("📥 Generate & Download Word Report", type="primary"):
        with st.spinner("⏳ Generating Word report..."):
            try:
                doc = Document()
                doc.add_heading("各色號稀釋劑使用分析與評估", level=0)
                p = doc.add_paragraph()
                p.add_run(f"分析日期：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                p.add_run(f"篩選條件：{filter_details}\n")
                p.add_run("說明：本報告圖表以 Matplotlib 匯出，不使用 Kaleido。")

                if 'matrix_export_plot_df' in locals() and not matrix_export_plot_df.empty:
                    doc.add_heading("1. 試用色號決策矩陣", level=1)
                    chart_buffer = create_decision_matrix_png(matrix_export_plot_df, target_opportunity_limit)
                    doc.add_picture(chart_buffer, width=Inches(6.8))
                else:
                    doc.add_paragraph("無可匯出的決策矩陣資料。")

                if 'display_df' in locals() and not display_df.empty:
                    doc.add_heading("2. 評估結果摘要表", level=1)
                    export_table_df = display_df.copy().head(15)
                    export_table_df = export_table_df[[
                        "Paint_Code", "Strategy_Quadrant", "Stability_Level",
                        "Estimated_Reduction_kg", "Total_Solvent_kg",
                        "Weighted_Ratio_Percent", "Benchmark_Ratio_Percent",
                        "Historical_Records"
                    ]]
                    export_table_df = export_table_df.rename(columns={
                        "Paint_Code": "色號",
                        "Strategy_Quadrant": "策略分類",
                        "Stability_Level": "穩定判定",
                        "Estimated_Reduction_kg": "預估減量機會(kg)",
                        "Total_Solvent_kg": "稀釋劑總用量(kg)",
                        "Weighted_Ratio_Percent": "目前加權比例(%)",
                        "Benchmark_Ratio_Percent": "同條件基準比例(%)",
                        "Historical_Records": "紀錄數",
                    })
                    table = doc.add_table(rows=1, cols=len(export_table_df.columns))
                    table.style = "Table Grid"
                    hdr_cells = table.rows[0].cells
                    for j, col in enumerate(export_table_df.columns):
                        hdr_cells[j].text = str(col)
                    for _, row in export_table_df.iterrows():
                        cells = table.add_row().cells
                        for j, col in enumerate(export_table_df.columns):
                            val = row[col]
                            if isinstance(val, float):
                                if "比例" in str(col):
                                    cells[j].text = f"{val:.2f}"
                                else:
                                    cells[j].text = f"{val:.1f}"
                            else:
                                cells[j].text = str(val)

                word_buffer = io.BytesIO()
                doc.save(word_buffer)
                word_buffer.seek(0)
                st.download_button(
                    label="💾 Download Word Report (.docx)",
                    data=word_buffer,
                    file_name=f"Solvent_Report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
                st.success("✅ Word report generated successfully!")
            except Exception as e:
                st.error(f"❌ Error generating Word report: {e}")
    elif not HAS_DOCX:
        st.warning("python-docx 未安裝，無法匯出 Word 報告。")

with export_col2:
    st.info("💡 如需保留互動功能，也可同時匯出 HTML 報告。")
    if st.button("📥 Generate & Download HTML Report"):
        with st.spinner("⏳ Generating HTML report..."):
            try:
                pilot_table_html = display_df.to_html(index=False, classes="summary-table") if 'display_df' in locals() else "<p>No data available.</p>"
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
                        .table-container {{ background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 30px; overflow-x: auto; }}
                        .summary-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
                        .summary-table th {{ background-color: #2F6B6D; color: white; padding: 10px 8px; border: 1px solid #d9e1e8; text-align: center; }}
                        .summary-table td {{ padding: 9px 8px; border: 1px solid #d9e1e8; text-align: center; }}
                        .summary-table tr:nth-child(even) {{ background-color: #f7f9fb; }}
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
                    fig_html = fig.to_html(full_html=False, include_plotlyjs=inc_js, default_width="100%", default_height="600px")
                    html_content += f"""
                    <h2>{fig_title}</h2>
                    <div class="chart-container">
                        {fig_html}
                    </div>
                    """
                html_content += f"""
                    <h2>試用色號評估摘要表</h2>
                    <div class="table-container">
                        {pilot_table_html}
                    </div>
                """
                html_content += """
                </body>
                </html>
                """
                html_buffer = io.BytesIO(html_content.encode('utf-8'))
                st.download_button(
                    label="💾 Download Interactive Report (.html)",
                    data=html_buffer,
                    file_name=f"Solvent_Report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.html",
                    mime="text/html"
                )
                st.success("✅ HTML report generated successfully!")
            except Exception as e:
                st.error(f"❌ Error generating HTML report: {e}")
