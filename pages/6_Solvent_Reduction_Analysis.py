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
st.title("🎨 Solvent Reduction Opportunity Analysis")

if not st.session_state.get("raw_data_loaded", False) or st.session_state.get("group_a_data") is None:
    st.warning("⚠️ Please return to the Main App page and upload the raw data first.")
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
    """Apply a clean business-style Plotly layout with black text."""
    annotations = list(fig.layout.annotations) if fig.layout.annotations else []

    if title_text is not None:
        fig.update_layout(
            title=dict(
                text=f"<b>{title_text}</b>",
                x=0.0,
                xanchor="left",
                y=0.985,
                yanchor="top",
                font=dict(size=22, color="#000000"),
                pad=dict(t=0, b=0),
            )
        )

    if subtitle_text:
        annotations.append(
            dict(
                x=0.0,
                y=1.105,
                xref="paper",
                yref="paper",
                text=subtitle_text,
                showarrow=False,
                xanchor="left",
                yanchor="bottom",
                align="left",
                font=dict(size=13, color="#000000"),
            )
        )

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#000000", size=13),
        annotations=annotations,
        hoverlabel=dict(
            bgcolor="white",
            font=dict(color="#000000", size=12),
            bordercolor="#D1D5DB",
        ),
        legend=dict(
            bgcolor="rgba(255,255,255,0.95)",
            bordercolor="rgba(0,0,0,0)",
            font=dict(color="#000000", size=12),
            title=dict(font=dict(color="#000000", size=12)),
        ),
        margin=dict(l=85, r=45, t=175, b=85),
    )
    if height is not None:
        fig.update_layout(height=height)

    fig.update_xaxes(
        showline=True,
        linewidth=1.2,
        linecolor="#111827",
        mirror=True,
        ticks="outside",
        tickfont=dict(color="#000000", size=12),
        title=dict(font=dict(color="#000000", size=14)),
        gridcolor="#E5E7EB",
        zeroline=False,
    )
    fig.update_yaxes(
        showline=True,
        linewidth=1.2,
        linecolor="#111827",
        mirror=True,
        ticks="outside",
        tickfont=dict(color="#000000", size=12),
        title=dict(font=dict(color="#000000", size=14)),
        gridcolor="#E5E7EB",
        zerolinecolor="#D1D5DB",
    )
    return fig


def create_decision_matrix_png(plot_df, target_opportunity_limit):
    """Create a Word-exportable decision matrix chart using Matplotlib (no Kaleido)."""
    fig, ax = plt.subplots(figsize=(10.5, 6.5), dpi=180)

    export_colors = {
        "Quick Wins": "#1D4ED8",
        "Secondary": "#60A5FA",
        "Standardize First": "#F97316",
        "Ignore": "#FDBA74",
    }
    export_labels = {
        "Quick Wins": "Quick Wins",
        "Secondary": "Secondary",
        "Standardize First": "Standardize First",
        "Ignore": "Ignore",
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
                label=export_labels.get(strategy, strategy),
                zorder=3,
            )

        max_y = max(float(plot_df["Estimated_Reduction_kg"].max()), 1.0)
        ax.axvline(2.5, color="#DC2626", linestyle=(0, (4, 4)), linewidth=1.2, zorder=2)
        ax.axhline(target_opportunity_limit, color="#DC2626", linestyle=(0, (4, 4)), linewidth=1.2, zorder=2)

        important = plot_df.copy()
        important["Label_Priority"] = 0
        important.loc[important["Strategy_Quadrant"] == "Quick Wins", "Label_Priority"] = 4
        important.loc[important["Strategy_Quadrant"] == "Standardize First", "Label_Priority"] = 3
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

        ax.text(2.55, max_y * 1.06, "High Stability Zone", fontsize=10, color="black", ha="left", va="bottom",
                bbox=dict(facecolor="white", edgecolor="#DC2626", linewidth=0.8, pad=2))
        ax.text(3.35, target_opportunity_limit + max_y * 0.015, f"High Reduction Threshold: {target_opportunity_limit:,.0f} kg",
                fontsize=10, color="black", ha="right", va="bottom",
                bbox=dict(facecolor="white", edgecolor="#DC2626", linewidth=0.8, pad=2))

        ax.set_xlim(-0.45, 3.45)
        ax.set_ylim(-max_y * 0.05, max_y * 1.15)

    fig.suptitle(
        "Pilot Paint Code Decision Matrix",
        x=0.08, y=0.985, ha="left", va="top",
        fontsize=16, fontweight="bold", color="black"
    )
    fig.text(
        0.08, 0.94,
        "X-axis = High-Stability Indicator Count (0-3); Y-axis = Estimated Solvent Reduction Opportunity; Bubble Size = Total Solvent Usage",
        fontsize=10.5, color="black", ha="left", va="top"
    )
    ax.set_xlabel("Number of High-Stability Indicators (0-3)", fontsize=11.5, color="black")
    ax.set_ylabel("Estimated Solvent Reduction Opportunity (kg)", fontsize=11.5, color="black")
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
            by_label.values(), by_label.keys(), ncol=4,
            loc="upper left", bbox_to_anchor=(0, 1.09),
            frameon=False, fontsize=9.5,
            handletextpad=0.5, columnspacing=1.2
        )
        for txt in leg.get_texts():
            txt.set_color("black")

    fig.patch.set_facecolor("white")
    fig.subplots_adjust(left=0.10, right=0.98, bottom=0.12, top=0.78)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white", dpi=220)
    plt.close(fig)
    buf.seek(0)
    return buf

# ==========================================
# 4. GLOBAL FILTERS
# ==========================================
st.markdown("---")
st.subheader("🔍 Global Filters")

filter_df = df.copy()
col1, col2, col3, col4, col5 = st.columns(5)

vendor_opts = ["All"] + sorted([str(x) for x in filter_df["Vendor"].unique() if x != "Unknown"])
selected_vendor = col1.selectbox("Vendor", vendor_opts)
if selected_vendor != "All": filter_df = filter_df[filter_df["Vendor"] == selected_vendor]

resin_opts = ["All"] + sorted([str(x) for x in filter_df["Resin"].unique() if x != "Unknown"])
selected_resin = col2.selectbox("Resin Type", resin_opts)
if selected_resin != "All": filter_df = filter_df[filter_df["Resin"] == selected_resin]

pos_opts = ["All"] + sorted([str(x) for x in filter_df["Position_UI"].unique() if x != "Unknown"])
selected_position = col3.selectbox("Coating Position", pos_opts)
if selected_position != "All": filter_df = filter_df[filter_df["Position_UI"] == selected_position]

solvent_opts = ["All"] + sorted([str(x) for x in filter_df["Solvent_Type"].unique() if x != "Unknown"])
selected_solvent = col4.selectbox("Solvent Type", solvent_opts)
if selected_solvent != "All": filter_df = filter_df[filter_df["Solvent_Type"] == selected_solvent]

line_opts = sorted([str(x) for x in filter_df["線別"].unique() if x != "Unknown"])
selected_lines = col5.multiselect("Production Line", line_opts, default=line_opts)

if selected_lines:
    filter_df = filter_df[filter_df["線別"].isin(selected_lines)]
else:
    st.warning("⚠️ Please select at least one production line.")
    st.stop()

if filter_df.empty:
    st.warning("⚠️ No records match the global analysis filters.")
    st.stop()

st.markdown("---")
if "_Analysis_Date" in filter_df.columns and not filter_df["_Analysis_Date"].isna().all():
    min_date = filter_df["_Analysis_Date"].min().strftime("%Y-%m-%d")
    max_date = filter_df["_Analysis_Date"].max().strftime("%Y-%m-%d")
    period_label = f"{min_date} ➔ {max_date}"
else:
    period_label = "All available data"

st.info(f"📅 **Analysis Period:** {period_label} | 📊 **Valid Records:** {len(filter_df):,}")
filter_details = f"Vendor: {selected_vendor} | Resin: {selected_resin} | Position: {selected_position} | Solvent: {selected_solvent}"
st.markdown("<br>", unsafe_allow_html=True)

# Initialize Dictionary to store charts for HTML export
exported_figs = {}

# ==========================================
# 5. HIERARCHICAL OVERVIEW (TREEMAP)
# ==========================================
st.subheader("🗂️ Hierarchical Overview")
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
    "1️⃣ Top 10 Paint Code Ranking", 
    "2️⃣ Paint Code Details", 
    "3️⃣ Line Comparison",
    "4️⃣ Pilot Paint Code Evaluation"
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
        df_melt["variable"] = df_melt["variable"].map({"Total_Paint_kg": "Paint", "Total_Solvent_kg": "Solvent"})
        
        fig1 = px.bar(
            df_melt, x="value", y="Paint_Code", color="variable", barmode="group", orientation='h', 
            height=chart_height, color_discrete_map={"Paint": "#5B8FF9", "Solvent": "#F6BD16"}
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
    st.markdown("### 📊 Ratio Consistency Audit")
    st.markdown("The consistency range is derived from the median and MAD instead of a manually fixed ±2% band.")

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
            f"**Consistency Range:** {lower_bound:.2f}% to {upper_bound:.2f}%"
        )

        audit_cols = ["_Analysis_DateTime", "Batch_ID", "Bucket_Number", "Solvent_Ratio_Percent", "Viscosity_Sensitivity"]
        audit_df = detail_df[audit_cols].copy()

        def evaluate_consistency(val):
            if pd.isna(val):
                return "⚠️ N/A"
            return "✅ Consistent" if lower_bound <= val <= upper_bound else "⚠️ Outside Range"

        audit_df["Consistency_Status"] = audit_df["Solvent_Ratio_Percent"].apply(evaluate_consistency)
        valid_records = audit_df.dropna(subset=["Solvent_Ratio_Percent"])
        consistent_count = (valid_records["Consistency_Status"] == "✅ Consistent").sum()
        total_count = len(valid_records)
        ratio_consistency = consistent_count / total_count * 100 if total_count else 0

        st.success(
            f"📈 **Ratio Consistency:** {consistent_count}/{total_count} records are within the data-driven range "
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
                "_Analysis_DateTime": "Adjustment Time",
                "Batch_ID": "Paint Batch ID",
                "Bucket_Number": "Bucket Number",
                "Solvent_Ratio_Percent": "Solvent Ratio",
                "Viscosity_Sensitivity": "Dilution Efficiency",
                "Consistency_Status": "Consistency Status",
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
        st.info(f"ℹ️ Paint code **{comp_code}** is currently only used on line **{used_line}**. Comparison requires data from at least two production lines.")

# ----- TAB 4: PILOT PAINT CODE EVALUATION -----
with tab_pilot:
    st.subheader("4. Pilot Paint Code Evaluation Matrix")
    st.markdown(
        "Use estimated reduction opportunity and three historical stability indicators to identify suitable pilot paint codes. "
        "Each indicator is classified into high, medium, or low stability using P33/P67 from comparable process conditions. "
        "No subjective 50–30–20 weighting or fixed 20% threshold is used."
    )

    set1, set2, set3 = st.columns(3)
    with set1:
        min_pilot_records = st.number_input(
            "Minimum Historical Records", min_value=5, value=20, step=1
        )
    with set2:
        target_opportunity_limit = st.number_input(
            "High Reduction Opportunity Threshold (kg)", min_value=0.0, value=500.0, step=100.0
        )
    with set3:
        min_peer_codes = st.number_input(
            "Minimum Comparable Paint Codes", min_value=3, value=5, step=1,
            help="At least this many paint codes are required within the same Vendor, Resin, Position, and Solvent Type group to use peer-group P33/P67. Otherwise, the overall eligible distribution is used."
        )

    st.info(
        "Evaluation rule: higher ratio consistency is better; lower relative variation in dilution efficiency is better; "
        "a smaller absolute time trend is better. Overall High Stability requires all three indicators to be classified as High Stability."
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
            return row[p33_col], row[p67_col], "Peer Group Distribution"
        return (
            global_thresholds[metric]["P33"],
            global_thresholds[metric]["P67"],
            "Overall Distribution",
        )

    def classify_by_distribution(value, p33, p67, direction):
        if pd.isna(value) or pd.isna(p33) or pd.isna(p67):
            return "Insufficient Data"
        if direction == "higher":
            if value >= p67:
                return "High Stability"
            if value >= p33:
                return "Medium Stability"
            return "Low Stability"
        if value <= p33:
            return "High Stability"
        if value <= p67:
            return "Medium Stability"
        return "Low Stability"

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
        if "Insufficient Data" in levels:
            overall = "Insufficient Data"
            high_count = np.nan
        else:
            high_count = sum(level == "High Stability" for level in levels)
            if high_count == 3:
                overall = "High Stability"
            elif "Low Stability" not in levels:
                overall = "Medium Stability"
            else:
                overall = "Low Stability"

        sources = {ratio_source, eff_source, trend_source}
        benchmark_source = "Peer Group Distribution" if sources == {"Peer Group Distribution"} else "Overall Distribution Fallback"

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
        high_stability = row["Stability_Level"] == "High Stability"
        if high_opportunity and high_stability:
            return "Quick Wins"
        if high_opportunity and not high_stability:
            return "Standardize First"
        if not high_opportunity and high_stability:
            return "Secondary"
        return "Ignore"

    if not pilot_df.empty:
        pilot_df["Strategy_Quadrant"] = pilot_df.apply(classify_quadrant, axis=1)

        color_map = {
            "Quick Wins": "#1D4ED8",
            "Standardize First": "#F97316",
            "Secondary": "#60A5FA",
            "Ignore": "#FDBA74",
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
                    "High-Stability Indicators: %{customdata[0]:.0f}/3<br>"
                    "Estimated Reduction Opportunity: %{customdata[4]:,.1f} kg<br>"
                    "Total Solvent Usage: %{customdata[1]:,.1f} kg<br>"
                    "Current Weighted Ratio: %{customdata[2]:.2f}%<br>"
                    "Peer Benchmark Ratio: %{customdata[3]:.2f}%<br>"
                    "Ratio Consistency: %{customdata[5]:.1%} (%{customdata[6]})<br>"
                    "Efficiency Relative Variation: %{customdata[7]:.3f} (%{customdata[8]})<br>"
                    "Ratio Trend per 10 Records: %{customdata[9]:+.2f} percentage points (%{customdata[10]})<br>"
                    "Historical Records: %{customdata[11]:,.0f}<br>"
                    "Benchmark Source: %{customdata[12]}<extra></extra>"
                ),
            )

            apply_professional_layout(
                fig_matrix,
                title_text="Pilot Paint Code Decision Matrix",
                subtitle_text="X-axis = High-Stability Indicator Count (0–3); Y-axis = Estimated Solvent Reduction Opportunity; Bubble Size = Total Solvent Usage",
                height=720,
            )

            fig_matrix.update_xaxes(
                title=dict(
                    text="High-Stability Indicator Count (0–3)",
                    font=dict(color="#000000", size=14),
                    standoff=18,
                ),
                tickmode="array",
                tickvals=[0, 1, 2, 3],
                ticktext=["0", "1", "2", "3"],
                tickfont=dict(color="#000000", size=12),
                range=[-0.45, 3.45],
                mirror=True,
                showline=True,
                linecolor="#111827",
                linewidth=1.2,
            )
            max_y = max(float(plot_df["Estimated_Reduction_kg"].max()), 1.0)
            fig_matrix.update_yaxes(
                title=dict(
                    text="Estimated Solvent Reduction Opportunity (kg)",
                    font=dict(color="#000000", size=14),
                    standoff=18,
                ),
                tickfont=dict(color="#000000", size=12),
                range=[-max_y * 0.05, max_y * 1.15],
                mirror=True,
                showline=True,
                linecolor="#111827",
                linewidth=1.2,
            )
            fig_matrix.update_layout(
                legend=dict(
                    title=None,
                    orientation="h",
                    yanchor="bottom",
                    y=1.015,
                    xanchor="left",
                    x=0.0,
                    font=dict(color="#000000", size=12),
                    itemclick="toggle",
                    itemdoubleclick="toggleothers",
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
                x=2.52, y=max_y * 1.08, text="High Stability Zone", showarrow=False,
                font=dict(size=12, color="#000000"), bgcolor="rgba(255,255,255,0.9)",
                bordercolor="#D62728", borderwidth=1, borderpad=3
            )
            fig_matrix.add_annotation(
                x=3.36, y=target_opportunity_limit,
                text=f"High Reduction Threshold: {target_opportunity_limit:,.0f} kg",
                showarrow=False, xanchor="right", yanchor="bottom",
                font=dict(size=12, color="#000000"), bgcolor="rgba(255,255,255,0.9)",
                bordercolor="#D62728", borderwidth=1, borderpad=3
            )

            # Label only the most important points and stagger annotations to avoid overlap.
            plot_df["Label_Priority"] = 0
            plot_df.loc[plot_df["Strategy_Quadrant"] == "Quick Wins", "Label_Priority"] = 4
            plot_df.loc[plot_df["Strategy_Quadrant"] == "Standardize First", "Label_Priority"] = 3
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
            st.warning("⚠️ Insufficient stability data to generate the decision matrix.")

        st.markdown("---")
        st.markdown("### Evaluation Details")
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
                "Paint_Code": "Paint Code",
                "Strategy_Quadrant": "Strategy",
                "Stability_Level": "Overall Stability",
                "High_Stability_Count": st.column_config.NumberColumn("High-Stability Indicators", format="%.0f/3"),
                "Stability_Benchmark_Source": "Benchmark Source",
                "Estimated_Reduction_kg": st.column_config.NumberColumn("Estimated Reduction Opportunity (kg)", format="%.1f"),
                "Total_Solvent_kg": st.column_config.NumberColumn("Total Solvent Usage (kg)", format="%.1f"),
                "Weighted_Ratio_Percent": st.column_config.NumberColumn("Current Weighted Ratio (%)", format="%.2f"),
                "Benchmark_Ratio_Percent": st.column_config.NumberColumn("Peer Benchmark Ratio (%)", format="%.2f"),
                "Ratio_Consistency": st.column_config.NumberColumn("Ratio Consistency (%)", format="%.1f"),
                "Ratio_Stability_Level": "Ratio Stability",
                "Efficiency_Relative_Variation": st.column_config.NumberColumn("Efficiency Relative Variation", format="%.3f"),
                "Efficiency_Stability_Level": "Efficiency Stability",
                "Ratio_Trend_Per_10_Records": st.column_config.NumberColumn("Ratio Trend per 10 Records", format="%+.2f"),
                "Trend_Stability_Level": "Trend Stability",
                "Historical_Records": "Records",
                "Historical_Batches": "Historical Batches",
            },
            use_container_width=True,
            hide_index=True,
        )

        quick_wins = display_df[
            display_df["Strategy_Quadrant"] == "Quick Wins"
        ]
        if not quick_wins.empty:
            top_code = quick_wins.iloc[0]
            st.success(
                f"✅ Recommended pilot: {top_code['Paint_Code']}. "
                f"All three stability indicators are classified as High Stability, "
                f"with an estimated reduction opportunity of approximately {top_code['Estimated_Reduction_kg']:.1f} kg."
            )
        else:
            st.info("No paint code currently meets both the high reduction opportunity threshold and High Stability for all three indicators.")

        with st.expander("View P33/P67 Thresholds Used in This Analysis"):
            threshold_rows = []
            for metric, label, direction in [
                ("Ratio_Consistency", "Ratio Consistency", "Higher is better"),
                ("Efficiency_Relative_Variation", "Efficiency Relative Variation", "Lower is better"),
                ("Abs_Ratio_Trend_Per_10_Records", "Absolute Time Trend", "Lower is better"),
            ]:
                threshold_rows.append({
                    "Indicator": label,
                    "Direction": direction,
                    "Overall P33": global_thresholds[metric]["P33"],
                    "Overall P67": global_thresholds[metric]["P67"],
                })
            st.dataframe(pd.DataFrame(threshold_rows), use_container_width=True, hide_index=True)
    else:
        display_df = pd.DataFrame()
        st.warning("⚠️ Insufficient historical records to generate the matrix analysis.")

# ==========================================
# 7. EXPORT INTERACTIVE HTML REPORT
# ==========================================
st.markdown("---")
st.subheader("📄 Export Report")

export_col1, export_col2 = st.columns(2)

with export_col1:
    st.info("💡 Word export uses Matplotlib to generate chart images. Kaleido is not used.")
    if HAS_DOCX and st.button("📥 Generate & Download Word Report", type="primary"):
        with st.spinner("⏳ Generating Word report..."):
            try:
                doc = Document()
                doc.add_heading("Solvent Reduction Opportunity Analysis", level=0)
                p = doc.add_paragraph()
                p.add_run(f"Analysis Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                p.add_run(f"Filters Applied: {filter_details}\n")
                p.add_run("Note: Charts in this report are exported with Matplotlib. Kaleido is not used.")

                if 'matrix_export_plot_df' in locals() and not matrix_export_plot_df.empty:
                    doc.add_heading("1. Pilot Paint Code Decision Matrix", level=1)
                    chart_buffer = create_decision_matrix_png(matrix_export_plot_df, target_opportunity_limit)
                    doc.add_picture(chart_buffer, width=Inches(6.8))
                else:
                    doc.add_paragraph("No decision matrix data is available for export.")

                if 'display_df' in locals() and not display_df.empty:
                    doc.add_heading("2. Evaluation Summary", level=1)
                    export_table_df = display_df.copy().head(15)
                    export_table_df = export_table_df[[
                        "Paint_Code", "Strategy_Quadrant", "Stability_Level",
                        "Estimated_Reduction_kg", "Total_Solvent_kg",
                        "Weighted_Ratio_Percent", "Benchmark_Ratio_Percent",
                        "Historical_Records"
                    ]]
                    strategy_export_map = {
                        "Quick Wins": "Quick Wins",
                        "Secondary": "Secondary",
                        "Standardize First": "Standardize First",
                        "Ignore": "Ignore",
                    }
                    stability_export_map = {
                        "High Stability": "High Stability",
                        "Medium Stability": "Medium Stability",
                        "Low Stability": "Low Stability",
                        "Insufficient Data": "Insufficient Data",
                    }
                    export_table_df["Strategy_Quadrant"] = export_table_df["Strategy_Quadrant"].map(strategy_export_map).fillna(export_table_df["Strategy_Quadrant"])
                    export_table_df["Stability_Level"] = export_table_df["Stability_Level"].map(stability_export_map).fillna(export_table_df["Stability_Level"])
                    export_table_df = export_table_df.rename(columns={
                        "Paint_Code": "Paint Code",
                        "Strategy_Quadrant": "Strategy",
                        "Stability_Level": "Stability Level",
                        "Estimated_Reduction_kg": "Estimated Reduction (kg)",
                        "Total_Solvent_kg": "Total Solvent Usage (kg)",
                        "Weighted_Ratio_Percent": "Current Weighted Ratio (%)",
                        "Benchmark_Ratio_Percent": "Peer Benchmark Ratio (%)",
                        "Historical_Records": "Historical Records",
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
                                if "Ratio" in str(col):
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
        st.warning("python-docx is not installed, so Word export is unavailable.")

with export_col2:
    st.info("💡 Export an HTML report to preserve interactive chart functionality.")
    if st.button("📥 Generate & Download HTML Report"):
        with st.spinner("⏳ Generating HTML report..."):
            try:
                pilot_table_html = display_df.to_html(index=False, classes="summary-table") if 'display_df' in locals() else "<p>No data available.</p>"
                html_content = f"""
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>Solvent Reduction Opportunity Report</title>
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
                    <h1>📊 Solvent Reduction Opportunity Report</h1>
                    <div class="info-box">
                        <p><strong>🕒 Analysis Date:</strong> {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        <p><strong>🔍 Filters Applied:</strong> {filter_details}</p>
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
                    <h2>Pilot Paint Code Evaluation Summary</h2>
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
