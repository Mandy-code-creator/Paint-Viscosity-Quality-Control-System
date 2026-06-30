import streamlit as st
import pandas as pd
import numpy as np
import graphviz
import io
import matplotlib.pyplot as plt

from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH


# =========================================================
# PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="Solvent Hierarchy",
    page_icon="🌳",
    layout="wide"
)

st.title("🌳 Solvent Consumption Hierarchy")
st.markdown(
    "Coil-level analysis of solvent utilization mapping from Vendor "
    "to specific Resin, Coating Position, and Solvent types."
)


# =========================================================
# 1. DATA LOADING
# =========================================================
if not st.session_state.get("raw_data_loaded", False):
    st.warning("⚠️ No data loaded. Please upload your dataset on the Main App page.")
    st.stop()

group_a = st.session_state.get("group_a_data", pd.DataFrame()).copy()

if group_a.empty:
    st.error("❌ The dataset is empty. Please check the uploaded file.")
    st.stop()


# =========================================================
# 2. SIDEBAR FILTERS & DATA MAPPING
# =========================================================
st.sidebar.header("🔍 Hierarchy Filters")

if "塗裝位置" not in group_a.columns:
    group_a["塗裝位置"] = "Unknown"

pos_mapping = {
    "TP": "Primer",
    "正底漆": "Primer",
    "BP": "Primer",
    "背底漆": "Primer",
    "TF": "Top Finish",
    "正面漆": "Top Finish",
    "BF": "Back Finish",
    "背面漆": "Back Finish"
}

group_a["Position_UI"] = group_a["塗裝位置"].map(pos_mapping).fillna(
    group_a["塗裝位置"]
)

for col in ["Vendor", "Resin", "Solvent_Type"]:
    if col not in group_a.columns:
        group_a[col] = "Unknown"


# -------------------------
# Vendor Filter
# -------------------------
vendor_list = sorted(group_a["Vendor"].dropna().unique().tolist())

if not vendor_list:
    st.warning("⚠️ No Vendor data available.")
    st.stop()

selected_vendor = st.sidebar.selectbox(
    "Select Vendor:",
    vendor_list
)

vendor_df = group_a[
    group_a["Vendor"] == selected_vendor
].copy()


# -------------------------
# Resin Filter
# -------------------------
resin_filter_list = ["All Resins"] + sorted(
    vendor_df["Resin"].dropna().unique().tolist()
)

selected_resin_filter = st.sidebar.selectbox(
    "Select Resin Group:",
    resin_filter_list
)

if selected_resin_filter != "All Resins":
    vendor_df = vendor_df[
        vendor_df["Resin"] == selected_resin_filter
    ].copy()


# -------------------------
# Coating Position Filter
# -------------------------
position_list = ["All Positions"] + sorted(
    vendor_df["Position_UI"].dropna().unique().tolist()
)

selected_position = st.sidebar.selectbox(
    "Select Coating Position:",
    position_list
)

filtered_df = vendor_df.copy()

if selected_position != "All Positions":
    filtered_df = filtered_df[
        filtered_df["Position_UI"] == selected_position
    ].copy()


# Grade A-B filter
if "Grade" in filtered_df.columns:
    filtered_df = filtered_df[
        filtered_df["Grade"].isin(["A", "B", "A-B"])
    ].copy()

if filtered_df.empty:
    st.warning(
        f"⚠️ No valid data available for Vendor: {selected_vendor}, "
        f"Resin: {selected_resin_filter}, "
        f"Position: {selected_position}."
    )
    st.stop()


# =========================================================
# 3. DATA CLEANING & CALCULATIONS
# =========================================================
required_cols = ["塗料重量", "添加重量", "黏度(秒)", "黏度(秒)_1"]

if not all(col in filtered_df.columns for col in required_cols):
    st.error(
        f"❌ Missing required columns: {', '.join(required_cols)}"
    )
    st.stop()

for col in required_cols:
    filtered_df[col] = pd.to_numeric(
        filtered_df[col],
        errors="coerce"
    )

# Keep valid dilution records only
filtered_df = filtered_df[
    (filtered_df["塗料重量"] > 0)
    & (filtered_df["添加重量"] > 0)
    & (filtered_df["黏度(秒)"] > filtered_df["黏度(秒)_1"])
].copy()

if filtered_df.empty:
    st.warning("⚠️ No valid dilution records after data cleaning.")
    st.stop()


# Viscosity reduction
filtered_df["Delta_V"] = (
    filtered_df["黏度(秒)"]
    - filtered_df["黏度(秒)_1"]
)

# ---------------------------------------------------------
# NEW LOGIC:
# Dilution base = actual paint weight only
# No 120 kg operating paint is included
# ---------------------------------------------------------
filtered_df["Dilution_Base_kg"] = filtered_df["塗料重量"]

# Solvent ratio (%)
filtered_df["Solvent_Ratio_Percent"] = (
    filtered_df["添加重量"]
    / filtered_df["塗料重量"]
) * 100

# kg solvent required for each 1-second viscosity reduction
filtered_df["Kg_per_1s"] = (
    filtered_df["添加重量"]
    / filtered_df["Delta_V"]
)

# Dilution efficiency
filtered_df["Dilution_Efficiency"] = (
    filtered_df["Delta_V"]
    / filtered_df["Solvent_Ratio_Percent"]
)

filtered_df = filtered_df.replace(
    [np.inf, -np.inf],
    np.nan
).dropna(
    subset=[
        "Solvent_Ratio_Percent",
        "Delta_V",
        "Kg_per_1s",
        "Dilution_Efficiency"
    ]
)

if filtered_df.empty:
    st.warning("⚠️ No valid records remain after calculations.")
    st.stop()


# =========================================================
# 4. HIERARCHY SUMMARY
# =========================================================
def calculate_advanced_metrics(group):

    if len(group) < 5:
        return pd.Series({
            "Opt_Eff": group["Dilution_Efficiency"].median(),
            "Sat_Limit": np.nan
        })

    bins = [0, 3, 5, 7, 9, 11, np.inf]
    labels = ["0-3", "3-5", "5-7", "7-9", "9-11", ">11"]
    midpoints = [1.5, 4, 6, 8, 10, 12]

    df_calc = group.copy()

    df_calc["Ratio_Bin"] = pd.cut(
        df_calc["Solvent_Ratio_Percent"],
        bins=bins,
        labels=labels,
        include_lowest=True
    )

    summary = df_calc.groupby(
        "Ratio_Bin",
        observed=False
    ).agg(
        Records=("Dilution_Efficiency", "size"),
        Median_Efficiency=("Dilution_Efficiency", "median")
    ).reset_index()

    summary["Ratio_Midpoint"] = midpoints

    summary = summary[
        summary["Records"] >= 3
    ].copy()

    if summary.empty:
        return pd.Series({
            "Opt_Eff": group["Dilution_Efficiency"].median(),
            "Sat_Limit": group["Solvent_Ratio_Percent"].quantile(0.95)
        })

    baseline_eff = summary["Median_Efficiency"].iloc[0]

    summary["Efficiency_Retention_Percent"] = (
        summary["Median_Efficiency"]
        / baseline_eff
    ) * 100

    stop_rows = summary[
        summary["Efficiency_Retention_Percent"] <= 50
    ]

    stop_ratio = (
        stop_rows["Ratio_Midpoint"].iloc[0]
        if not stop_rows.empty
        else group["Solvent_Ratio_Percent"].quantile(0.95)
    )

    return pd.Series({
        "Opt_Eff": baseline_eff,
        "Sat_Limit": stop_ratio
    })


tree_base = filtered_df.groupby(
    ["Resin", "Position_UI", "Solvent_Type"],
    observed=False
).agg(
    Total_Paint=("塗料重量", "sum"),
    Total_Solvent=("添加重量", "sum"),
    Avg_Visc_Before=("黏度(秒)", "mean"),
    Avg_Visc_After=("黏度(秒)_1", "mean")
).reset_index()


advanced_metrics = filtered_df.groupby(
    ["Resin", "Position_UI", "Solvent_Type"],
    observed=False
).apply(
    calculate_advanced_metrics
).reset_index()


tree_summary = pd.merge(
    tree_base,
    advanced_metrics,
    on=["Resin", "Position_UI", "Solvent_Type"]
)

tree_summary = tree_summary[
    tree_summary["Total_Paint"] > 0
].sort_values(
    by=["Resin", "Total_Paint"],
    ascending=[True, False]
)

if tree_summary.empty:
    st.warning("⚠️ No valid paint consumption data available.")
    st.stop()


# =========================================================
# 5. GRAPHVIZ HIERARCHY
# =========================================================
graph = graphviz.Digraph(engine="dot")

graph.attr(
    rankdir="LR",
    splines="curved",
    nodesep="0.2",
    ranksep="0.6",
    bgcolor="transparent"
)

graph.attr(
    "node",
    shape="none",
    margin="0",
    fontname="Arial"
)

graph.attr(
    "edge",
    color="#B0B0B0",
    penwidth="1.2",
    arrowsize="0.7"
)


# ---------------------------------------------------------
# Vendor totals calculated directly from filtered_df
# ---------------------------------------------------------
total_vendor_paint = filtered_df["塗料重量"].sum()
total_vendor_solv = filtered_df["添加重量"].sum()
avg_delta_v = filtered_df["Delta_V"].mean()

avg_solvent_ratio = (
    total_vendor_solv / total_vendor_paint * 100
    if total_vendor_paint > 0
    else 0
)

st.sidebar.caption(
    f"Check: {total_vendor_solv:,.1f} kg solvent ÷ "
    f"{total_vendor_paint:,.1f} kg paint "
    f"= {avg_solvent_ratio:.2f}%"
)


# Date range
date_range_str = "All Available Data"

date_cols = [
    col for col in filtered_df.columns
    if "date" in col.lower()
    or "日期" in col.lower()
    or "time" in col.lower()
]

if date_cols:
    try:
        date_col = date_cols[0]

        min_date = pd.to_datetime(
            filtered_df[date_col],
            errors="coerce"
        ).min()

        max_date = pd.to_datetime(
            filtered_df[date_col],
            errors="coerce"
        ).max()

        if pd.notna(min_date) and pd.notna(max_date):

            min_date_str = min_date.strftime("%b %Y")
            max_date_str = max_date.strftime("%b %Y")

            if min_date_str == max_date_str:
                date_range_str = min_date_str
            else:
                date_range_str = f"{min_date_str} - {max_date_str}"

    except Exception:
        date_range_str = "All Available Data"


# Root Node
center_html = f"""
<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="6">
    <TR>
        <TD BGCOLOR="#00BFFF" STYLE="ROUNDED" ALIGN="CENTER">
            <FONT COLOR="white" POINT-SIZE="12">
                <B>VENDOR: {selected_vendor}</B>
            </FONT>
        </TD>
    </TR>

    <TR>
        <TD BGCOLOR="#F8F9FA" STYLE="ROUNDED" ALIGN="CENTER">
            <FONT POINT-SIZE="10" COLOR="#333333">
                Period: <B>{date_range_str}</B><BR/>
                <B>{total_vendor_paint:,.0f} kg</B> Paint Used<BR/>
                Visc Reduction: <B>{avg_delta_v:.1f} s</B><BR/>
                <B>{total_vendor_solv:,.0f} kg</B> Solvent Added<BR/>
            </FONT>

            <FONT COLOR="#D9534F" POINT-SIZE="11">
                <B>Avg. Solvent Ratio: {avg_solvent_ratio:.2f}%</B>
            </FONT>
        </TD>
    </TR>
</TABLE>
"""

graph.node("Root", f"<{center_html}>")


# Resin → Position → Solvent
for resin in tree_summary["Resin"].unique():

    resin_id = f"resin_{resin}"

    resin_data = tree_summary[
        tree_summary["Resin"] == resin
    ].copy()

    resin_paint_sum = resin_data["Total_Paint"].sum()
    resin_solvent_sum = resin_data["Total_Solvent"].sum()

    resin_html = f"""
    <TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="5">
        <TR>
            <TD BGCOLOR="#E6F2FF" STYLE="ROUNDED"
                BORDER="1" COLOR="#00BFFF" ALIGN="CENTER">

                <FONT COLOR="#005A9E" POINT-SIZE="11">
                    <B>RESIN: {resin}</B>
                </FONT><BR/>

                <FONT COLOR="#555555" POINT-SIZE="10">
                    {resin_paint_sum:,.0f} kg Paint
                </FONT><BR/>

                <FONT COLOR="#D9534F" POINT-SIZE="10">
                    {resin_solvent_sum:,.0f} kg Solvent
                </FONT>
            </TD>
        </TR>
    </TABLE>
    """

    graph.node(resin_id, f"<{resin_html}>")
    graph.edge("Root", resin_id)

    for pos in resin_data["Position_UI"].unique():

        pos_id = f"pos_{resin}_{pos}"

        pos_data = resin_data[
            resin_data["Position_UI"] == pos
        ].copy()

        pos_paint_sum = pos_data["Total_Paint"].sum()

        pos_html = f"""
        <TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4">
            <TR>
                <TD BGCOLOR="#FFF7ED" STYLE="ROUNDED"
                    BORDER="1" COLOR="#F97316" ALIGN="CENTER">

                    <FONT COLOR="#C2410C" POINT-SIZE="10">
                        <B>POS: {pos}</B>
                    </FONT><BR/>

                    <FONT COLOR="#555555" POINT-SIZE="9">
                        {pos_paint_sum:,.0f} kg
                    </FONT>
                </TD>
            </TR>
        </TABLE>
        """

        graph.node(pos_id, f"<{pos_html}>")
        graph.edge(resin_id, pos_id)

        for idx, row in pos_data.iterrows():

            solvent = row["Solvent_Type"]

            leaf_id = f"leaf_{resin}_{pos}_{solvent}_{idx}"

            sat_limit_display = (
                f"{row['Sat_Limit']:.1f}%"
                if pd.notna(row["Sat_Limit"])
                else "N/A"
            )

            leaf_html = f"""
            <TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="5">
                <TR>
                    <TD ALIGN="CENTER" BGCOLOR="white"
                        STYLE="ROUNDED" BORDER="1" COLOR="#CCCCCC">

                        <FONT COLOR="#333333" POINT-SIZE="10">
                            <B>SOLVENT: {solvent}</B>
                        </FONT><BR/>

                        <FONT COLOR="#555555" POINT-SIZE="9">
                            Visc: {row["Avg_Visc_Before"]:.1f}s
                            &rarr;
                            {row["Avg_Visc_After"]:.1f}s
                        </FONT><BR/>

                        <FONT COLOR="#00BFFF" POINT-SIZE="9">
                            <B>Opt. Eff: {row["Opt_Eff"]:.2f} s/%</B>
                        </FONT><BR/>

                        <FONT COLOR="#D9534F" POINT-SIZE="9">
                            <B>Sat. Limit: {sat_limit_display}</B>
                        </FONT>
                    </TD>
                </TR>
            </TABLE>
            """

            graph.node(leaf_id, f"<{leaf_html}>")
            graph.edge(pos_id, leaf_id)


st.graphviz_chart(
    graph,
    use_container_width=True
)


# =========================================================
# 6. SATURATION ANALYSIS
# =========================================================
st.markdown("---")
st.subheader("📉 Dilution Efficiency & Saturation Analysis")

st.caption(
    "Dilution Efficiency = Viscosity Drop ÷ Solvent Blending Ratio. "
    "Lower values indicate that additional solvent produces less "
    "viscosity reduction."
)

col1, col2, col3 = st.columns(3)

with col1:
    resin_options = sorted(
        filtered_df["Resin"].dropna().unique().tolist()
    )

    selected_resin = st.selectbox(
        "Select Resin for Saturation Analysis:",
        resin_options,
        key="sat_resin"
    )

analysis_resin_df = filtered_df[
    filtered_df["Resin"] == selected_resin
].copy()

with col2:
    pos_options = sorted(
        analysis_resin_df["Position_UI"].dropna().unique().tolist()
    )

    selected_pos = st.selectbox(
        "Select Position:",
        pos_options,
        key="sat_pos"
    )

analysis_pos_df = analysis_resin_df[
    analysis_resin_df["Position_UI"] == selected_pos
].copy()

with col3:
    solvent_options = sorted(
        analysis_pos_df["Solvent_Type"].dropna().unique().tolist()
    )

    selected_solvent = st.selectbox(
        "Select Solvent:",
        solvent_options,
        key="sat_solvent"
    )

saturation_df = analysis_pos_df[
    analysis_pos_df["Solvent_Type"] == selected_solvent
].copy()

fig_efficiency = None
baseline_efficiency = None
warning_ratio = None
stop_ratio = None
baseline_range_label = "N/A"
baseline_records = 0


if len(saturation_df) < 5:

    st.warning(
        "⚠️ Historical records are insufficient for saturation analysis "
        "(minimum 5 records required)."
    )

else:

    bins = [0, 3, 5, 7, 9, 11, np.inf]
    labels = ["0–3%", "3–5%", "5–7%", "7–9%", "9–11%", ">11%"]
    midpoints = [1.5, 4, 6, 8, 10, 12]

    saturation_df["Ratio_Bin"] = pd.cut(
        saturation_df["Solvent_Ratio_Percent"],
        bins=bins,
        labels=labels,
        include_lowest=True
    )

    efficiency_summary = saturation_df.groupby(
        "Ratio_Bin",
        observed=False
    ).agg(
        Records=("Dilution_Efficiency", "size"),
        Median_Efficiency=("Dilution_Efficiency", "median")
    ).reset_index()

    efficiency_summary["Ratio_Midpoint"] = midpoints

    efficiency_summary = efficiency_summary[
        efficiency_summary["Records"] >= 3
    ].copy()

    if efficiency_summary.empty:

        st.warning(
            "⚠️ Not enough records in each solvent-ratio interval."
        )

    else:

        baseline_efficiency = efficiency_summary[
            "Median_Efficiency"
        ].iloc[0]

        baseline_records = efficiency_summary[
            "Records"
        ].iloc[0]

        baseline_range_label = efficiency_summary[
            "Ratio_Bin"
        ].iloc[0]

        efficiency_summary["Efficiency_Retention_Percent"] = (
            efficiency_summary["Median_Efficiency"]
            / baseline_efficiency
        ) * 100

        warning_rows = efficiency_summary[
            efficiency_summary["Efficiency_Retention_Percent"] <= 70
        ]

        stop_rows = efficiency_summary[
            efficiency_summary["Efficiency_Retention_Percent"] <= 50
        ]

        ratio_p90 = saturation_df[
            "Solvent_Ratio_Percent"
        ].quantile(0.90)

        ratio_p95 = saturation_df[
            "Solvent_Ratio_Percent"
        ].quantile(0.95)

        warning_ratio = (
            warning_rows["Ratio_Midpoint"].iloc[0]
            if not warning_rows.empty
            else ratio_p90
        )

        stop_ratio = (
            stop_rows["Ratio_Midpoint"].iloc[0]
            if not stop_rows.empty
            else ratio_p95
        )

        stop_ratio = max(stop_ratio, warning_ratio)

        fig_efficiency, ax = plt.subplots(
            figsize=(11.5, 5.8),
            dpi=180
        )

        x_values = efficiency_summary["Ratio_Midpoint"]
        y_values = efficiency_summary["Median_Efficiency"]
        record_values = efficiency_summary["Records"]

        ax.plot(
            x_values,
            y_values,
            marker="o",
            linewidth=2,
            markersize=6,
            color="#4F6DFF"
        )

        for x, y, record in zip(
            x_values,
            y_values,
            record_values
        ):
            ax.annotate(
                str(record),
                xy=(x, y),
                xytext=(0, 10),
                textcoords="offset points",
                ha="center",
                fontsize=8,
                color="#4A4A4A",
                bbox=dict(
                    facecolor="white",
                    edgecolor="none",
                    pad=1.5,
                    alpha=0.85
                )
            )

        x_min = min(0, x_values.min() - 1)
        x_max = max(x_values.max() + 1, stop_ratio + 1)

        y_min_orig, y_max_orig = ax.get_ylim()
        y_range = y_max_orig - y_min_orig

        y_max = y_max_orig + y_range * 0.15
        y_min = y_min_orig - y_range * 0.15

        ax.set_ylim(y_min, y_max)

        alert_color = "red"

        if abs(stop_ratio - warning_ratio) < 0.2:

            ax.axvline(
                stop_ratio,
                color=alert_color,
                linestyle="--",
                linewidth=2.2
            )

            ax.axvspan(
                stop_ratio,
                x_max,
                color=alert_color,
                alpha=0.10
            )

            ax.annotate(
                f"Saturation Limit: {stop_ratio:.1f}%",
                xy=(
                    stop_ratio,
                    y_max_orig + y_range * 0.08
                ),
                xytext=(8, 0),
                textcoords="offset points",
                color=alert_color,
                fontsize=10,
                fontweight="bold",
                va="center",
                ha="left",
                bbox=dict(
                    facecolor="white",
                    edgecolor=alert_color,
                    boxstyle="round,pad=0.3",
                    alpha=0.9
                )
            )

        else:

            ax.axvline(
                warning_ratio,
                color=alert_color,
                linestyle=":",
                linewidth=2
            )

            ax.axvline(
                stop_ratio,
                color=alert_color,
                linestyle="--",
                linewidth=2.2
            )

            ax.axvspan(
                warning_ratio,
                stop_ratio,
                color=alert_color,
                alpha=0.05
            )

            ax.axvspan(
                stop_ratio,
                x_max,
                color=alert_color,
                alpha=0.10
            )

            ax.annotate(
                f"Warning: {warning_ratio:.1f}%",
                xy=(
                    warning_ratio,
                    y_max_orig + y_range * 0.08
                ),
                xytext=(-8, 0),
                textcoords="offset points",
                color=alert_color,
                fontsize=10,
                fontweight="bold",
                va="center",
                ha="right",
                bbox=dict(
                    facecolor="white",
                    edgecolor="none",
                    alpha=0.8
                )
            )

            ax.annotate(
                f"Stop: {stop_ratio:.1f}%",
                xy=(
                    stop_ratio,
                    y_max_orig + y_range * 0.08
                ),
                xytext=(8, 0),
                textcoords="offset points",
                color=alert_color,
                fontsize=10,
                fontweight="bold",
                va="center",
                ha="left",
                bbox=dict(
                    facecolor="white",
                    edgecolor=alert_color,
                    boxstyle="round,pad=0.3",
                    alpha=0.9
                )
            )

        ax.text(
            0.02,
            0.04,
            "ℹ️ Note: Numbers above data points indicate the total record count.",
            transform=ax.transAxes,
            fontsize=9,
            color="#333333",
            bbox=dict(
                facecolor="white",
                edgecolor="#CCCCCC",
                pad=5,
                alpha=0.9
            ),
            va="bottom",
            ha="left"
        )

        ax.set_title(
            "Dilution Efficiency vs Solvent Ratio\n"
            f"Resin: {selected_resin} | "
            f"Position: {selected_pos} | "
            f"Solvent: {selected_solvent}",
            fontsize=13,
            fontweight="bold",
            loc="left",
            pad=14
        )

        ax.set_xlabel(
            "Solvent Blending Ratio (%)",
            fontsize=10
        )

        ax.set_ylabel(
            "Median Dilution Efficiency (seconds / %)",
            fontsize=10
        )

        ax.set_xlim(x_min, x_max)

        ax.grid(
            True,
            linestyle="--",
            linewidth=0.6,
            alpha=0.45
        )

        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(1.2)
            spine.set_color("black")

        ax.tick_params(
            axis="both",
            labelsize=9
        )

        fig_efficiency.tight_layout()

        st.pyplot(
            fig_efficiency,
            use_container_width=True
        )

        kpi1, kpi2, kpi3 = st.columns(3)

        kpi1.metric(
            "Baseline Efficiency",
            f"{baseline_efficiency:.2f} s/%"
        )

        kpi2.metric(
            "Saturation Warning Ratio",
            f"{warning_ratio:.2f}%"
        )

        kpi3.metric(
            "Saturation Stop Ratio",
            f"{stop_ratio:.2f}%"
        )

        with st.expander(
            f"🧮 Sample Calculation: How is Baseline "
            f"{baseline_efficiency:.2f} determined?"
        ):

            st.markdown(f"""
            **Step 1: Coil-level Calculation**

            * **Solvent Ratio (%)** = `[Solvent Added / Paint Weight] × 100`
            * **Viscosity Drop (ΔV)** = `Viscosity Before - Viscosity After`
            * **Dilution Efficiency** = `ΔV / Solvent Ratio`

            **Step 2: Group Aggregation (Median)**

            * The system identifies the optimal starting range: **{baseline_range_label}**.
            * There are **{baseline_records}** historical records.
            * The system calculates the Median efficiency.
            * **Calculated Baseline** = **{baseline_efficiency:.2f} seconds per 1% solvent added**.
            """)

        st.caption(
            "The shaded area represents the saturation / stop zone. "
            "After this point, further solvent addition is not recommended."
        )

        with st.expander("View Saturation Analysis Data"):

            display_efficiency = efficiency_summary[
                [
                    "Ratio_Bin",
                    "Records",
                    "Median_Efficiency",
                    "Efficiency_Retention_Percent"
                ]
            ].copy()

            display_efficiency.columns = [
                "Solvent Ratio Range",
                "Records",
                "Median Efficiency (s/%)",
                "Efficiency Retention (%)"
            ]

            st.dataframe(
                display_efficiency,
                use_container_width=True,
                hide_index=True
            )


# =========================================================
# 7. WORD EXPORT - A4 FORMAT
# =========================================================
st.markdown("---")

try:

    graph.attr(dpi="300")

    graph_png = graph.pipe(format="png")

    if not graph_png:
        st.error("❌ Unable to create hierarchy image.")
        st.stop()

    graph_stream = io.BytesIO(graph_png)

    doc = Document()

    section = doc.sections[0]

    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)

    section.top_margin = Inches(0.55)
    section.bottom_margin = Inches(0.55)
    section.left_margin = Inches(0.60)
    section.right_margin = Inches(0.60)

    title = doc.add_heading(
        "Solvent Consumption & Viscosity Control Report",
        level=0
    )

    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    report_vendor = doc.add_paragraph()
    report_vendor.alignment = WD_ALIGN_PARAGRAPH.CENTER
    report_vendor.add_run(
        f"Vendor: {selected_vendor}"
    ).bold = True

    report_period = doc.add_paragraph()
    report_period.alignment = WD_ALIGN_PARAGRAPH.CENTER
    report_period.add_run(
        f"Analysis Period: {date_range_str}"
    )

    doc.add_heading(
        "1. Solvent Consumption Hierarchy",
        level=1
    )

    hierarchy_p = doc.add_paragraph()
    hierarchy_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    hierarchy_p.add_run().add_picture(
        graph_stream,
        width=Inches(7.0)
    )

    hierarchy_caption = doc.add_paragraph(
        "Figure 1. Solvent consumption hierarchy by resin, "
        "position, and solvent type."
    )

    hierarchy_caption.alignment = WD_ALIGN_PARAGRAPH.CENTER

    if fig_efficiency is not None:

        chart_stream = io.BytesIO()

        fig_efficiency.savefig(
            chart_stream,
            format="png",
            dpi=300,
            bbox_inches="tight",
            facecolor="white"
        )

        chart_stream.seek(0)

        doc.add_heading(
            "2. Dilution Efficiency & Saturation Analysis",
            level=1
        )

        chart_p = doc.add_paragraph()
        chart_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        chart_p.add_run().add_picture(
            chart_stream,
            width=Inches(7.0)
        )

        chart_caption = doc.add_paragraph(
            "Figure 2. Dilution efficiency versus solvent blending ratio "
            f"(Resin: {selected_resin}; "
            f"Position: {selected_pos}; "
            f"Solvent: {selected_solvent})."
        )

        chart_caption.alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_heading(
            "3. Key Results",
            level=1
        )

        result_table = doc.add_table(
            rows=1,
            cols=3
        )

        result_table.style = "Table Grid"

        header_cells = result_table.rows[0].cells

        header_cells[0].text = "Baseline Efficiency"
        header_cells[1].text = "Warning Ratio"
        header_cells[2].text = "Stop Ratio"

        value_cells = result_table.add_row().cells

        value_cells[0].text = f"{baseline_efficiency:.2f} s/%"
        value_cells[1].text = f"{warning_ratio:.2f}%"
        value_cells[2].text = f"{stop_ratio:.2f}%"

        doc.add_paragraph(
            "Interpretation: When dilution efficiency decreases, "
            "additional solvent produces less viscosity reduction. "
            "The red shaded saturation zone is used as a reference "
            "to avoid excessive solvent addition."
        )

        doc.add_heading(
            "4. 基準數據判定與計算範例 "
            "(Baseline Sample Calculation)",
            level=1
        )

        doc.add_paragraph(
            f"為確保客觀性，系統自動捕捉第一個具備完整統計意義的區間作為基準"
            f"（即 {baseline_range_label}，包含 {baseline_records} 卷歷史有效紀錄）。"
            f"為排除極端值干擾，系統提取該區間內稀釋效率之"
            f"「中位數 (Median)」做為 100% 黃金基準線。"
        )

        doc.add_paragraph(
            f"• 基準效率 (Baseline Efficiency) = "
            f"{baseline_efficiency:.2f} (秒/%)"
        )

        calc_formula = doc.add_paragraph()

        calc_formula.add_run(
            "單卷 (Coil-level) 效率計算底層公式：\n"
        ).bold = True

        calc_formula.add_run(
            "1. 溶劑比例 (%) = [ 添加重量 / 塗料重量 ] × 100\n"
            "2. 降黏幅度 (ΔV) = 稀釋前黏度 - 稀釋後黏度\n"
            "3. 稀釋效率 (s/%) = ΔV / 溶劑比例"
        )

    else:

        doc.add_paragraph(
            "Note: Saturation chart was not generated because "
            "the selected material condition does not have "
            "sufficient historical data."
        )

    doc_io = io.BytesIO()

    doc.save(doc_io)

    doc_io.seek(0)

    st.download_button(
        label="📄 Download A4 Word Report",
        data=doc_io,
        file_name=(
            f"Solvent_Viscosity_Report_"
            f"{selected_vendor}_"
            f"{selected_resin}_"
            f"{selected_pos}_"
            f"{selected_solvent}.docx"
        ),
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        )
    )

except Exception as e:

    st.error(f"❌ Word report export failed: {e}")
    st.exception(e)
