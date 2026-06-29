import streamlit as st
import pandas as pd
import numpy as np
import graphviz
import io
import plotly.graph_objects as go

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
    "to specific Resin and Solvent types."
)


# =========================================================
# 1. DATA LOADING & SAFE CHECK
# =========================================================
if not st.session_state.get("raw_data_loaded", False):
    st.warning("⚠️ No data loaded. Please upload your dataset on the Main App page.")
    st.stop()

group_a = st.session_state.get("group_a_data", pd.DataFrame()).copy()

if group_a.empty:
    st.error("❌ The dataset is empty. Please check the uploaded file.")
    st.stop()


# =========================================================
# 2. SIDEBAR FILTERS
# =========================================================
st.sidebar.header("🔍 Hierarchy Filters")

for col in ["Vendor", "Resin", "Solvent_Type"]:
    if col not in group_a.columns:
        group_a[col] = "Unknown"

vendor_list = sorted(group_a["Vendor"].dropna().unique().tolist())

if not vendor_list:
    st.warning("⚠️ No Vendor data available.")
    st.stop()

selected_vendor = st.sidebar.selectbox(
    "Select Vendor:",
    vendor_list
)

filtered_df = group_a[
    group_a["Vendor"] == selected_vendor
].copy()

if "Grade" in filtered_df.columns:
    filtered_df = filtered_df[
        filtered_df["Grade"].isin(["A", "B", "A-B"])
    ].copy()

if filtered_df.empty:
    st.warning(f"⚠️ No valid data available for {selected_vendor}.")
    st.stop()


# =========================================================
# 3. DATA CLEANING & METRIC CALCULATIONS
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

# Only valid dilution records
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

# Include 120 kg operating paint retained in the line
filtered_df["Dilution_Base_kg"] = (
    filtered_df["塗料重量"] + 120
)

# Solvent ratio (%)
filtered_df["Solvent_Ratio_Percent"] = (
    filtered_df["添加重量"]
    / filtered_df["Dilution_Base_kg"]
) * 100

# kg solvent needed per 1 second viscosity reduction
filtered_df["Kg_per_1s"] = (
    filtered_df["添加重量"]
    / filtered_df["Delta_V"]
)

# solvent ratio needed per 1 second viscosity reduction
filtered_df["Pct_per_1s"] = (
    filtered_df["Solvent_Ratio_Percent"]
    / filtered_df["Delta_V"]
)

# Dilution efficiency:
# Viscosity reduction obtained for every 1% solvent ratio
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
        "Pct_per_1s",
        "Dilution_Efficiency"
    ]
)

if filtered_df.empty:
    st.warning("⚠️ No valid records remain after calculations.")
    st.stop()


# =========================================================
# 4. HIERARCHY SUMMARY
# =========================================================
tree_summary = filtered_df.groupby(
    ["Resin", "Solvent_Type"],
    observed=False
).agg(
    Total_Paint=("塗料重量", "sum"),
    Total_Solvent=("添加重量", "sum"),
    Avg_Kg_per_1s=("Kg_per_1s", "mean"),
    Avg_Pct_per_1s=("Pct_per_1s", "mean"),
    Avg_Visc_Before=("黏度(秒)", "mean"),
    Avg_Visc_After=("黏度(秒)_1", "mean")
).reset_index()

tree_summary = tree_summary[
    tree_summary["Total_Paint"] > 0
].sort_values(
    by="Total_Paint",
    ascending=False
)

if tree_summary.empty:
    st.info("No valid paint consumption data available.")
    st.stop()


# =========================================================
# 5. GRAPHVIZ HIERARCHY
# =========================================================
graph = graphviz.Digraph(engine="dot")

graph.attr(
    rankdir="LR",
    splines="curved",
    nodesep="0.2",
    ranksep="1.0",
    bgcolor="transparent"
)

graph.attr(
    "node",
    shape="none",
    margin="0",
    width="0",
    height="0",
    fontname="Arial"
)

graph.attr(
    "edge",
    color="#A0A0A0",
    penwidth="1.5",
    arrowsize="0.8"
)

total_vendor_paint = tree_summary["Total_Paint"].sum()
total_vendor_solv = tree_summary["Total_Solvent"].sum()
avg_delta_v = filtered_df["Delta_V"].mean()
total_dilution_base = filtered_df["Dilution_Base_kg"].sum()

avg_solvent_ratio = (
    total_vendor_solv / total_dilution_base * 100
    if total_dilution_base > 0
    else 0
)

date_cols = [
    col for col in filtered_df.columns
    if "date" in col.lower()
    or "日期" in col.lower()
    or "time" in col.lower()
]

date_range_str = "All Available Data"

if date_cols:
    date_col = date_cols[0]

    try:
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

center_html = f"""
<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4">
    <TR>
        <TD BGCOLOR="#00BFFF" STYLE="ROUNDED" ALIGN="CENTER">
            <FONT COLOR="white" POINT-SIZE="18">
                <B>VENDOR: {selected_vendor}</B>
            </FONT>
        </TD>
    </TR>
    <TR>
        <TD BGCOLOR="#F8F9FA" STYLE="ROUNDED" ALIGN="CENTER">
            <FONT POINT-SIZE="12" COLOR="#333333">
                Period: <B>{date_range_str}</B><BR/>
                <B>{total_vendor_paint:,.0f} kg</B> Paint Used<BR/>
                Visc Reduction: <B>{avg_delta_v:.1f} s</B><BR/>
                <B>{total_vendor_solv:,.0f} kg</B> Solvent Added<BR/>
            </FONT>
            <FONT COLOR="#D9534F" POINT-SIZE="13">
                <B>Avg. Solvent Ratio: {avg_solvent_ratio:.2f}%</B>
            </FONT>
        </TD>
    </TR>
</TABLE>
"""

graph.node("Root", f"<{center_html}>")

for resin in tree_summary["Resin"].unique():
    resin_id = f"resin_{resin}"

    resin_data = tree_summary[
        tree_summary["Resin"] == resin
    ].copy()

    resin_paint_sum = resin_data["Total_Paint"].sum()
    resin_solvent_sum = resin_data["Total_Solvent"].sum()

    resin_html = f"""
    <TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="2">
        <TR>
            <TD BGCOLOR="#E6F2FF" STYLE="ROUNDED"
                BORDER="1" COLOR="#00BFFF" ALIGN="CENTER">
                <FONT COLOR="#005A9E" POINT-SIZE="14">
                    <B>RESIN: {resin}</B>
                </FONT><BR/>
                <FONT COLOR="#555555" POINT-SIZE="11">
                    {resin_paint_sum:,.0f} kg Paint
                </FONT><BR/>
                <FONT COLOR="#D9534F" POINT-SIZE="11">
                    {resin_solvent_sum:,.0f} kg Solvent
                </FONT>
            </TD>
        </TR>
    </TABLE>
    """

    graph.node(resin_id, f"<{resin_html}>")
    graph.edge("Root", resin_id)

    for idx, row in resin_data.iterrows():
        solvent = row["Solvent_Type"]
        leaf_id = f"leaf_{resin}_{solvent}_{idx}"

        leaf_html = f"""
        <TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="2">
            <TR>
                <TD ALIGN="CENTER" BGCOLOR="white" STYLE="ROUNDED"
                    BORDER="1" COLOR="#CCCCCC">
                    <B>
                        <FONT COLOR="#333333">
                            SOLVENT: {solvent}
                        </FONT>
                    </B><BR/>
                    <FONT COLOR="#888888" POINT-SIZE="10">
                        Visc Before: {row["Avg_Visc_Before"]:.1f} s
                    </FONT><BR/>
                    <FONT COLOR="#888888" POINT-SIZE="10">
                        Visc After: {row["Avg_Visc_After"]:.1f} s
                    </FONT><BR/>
                    <FONT COLOR="#00BFFF">
                        {row["Avg_Kg_per_1s"]:.2f} kg / 1s
                    </FONT><BR/>
                    <FONT COLOR="#D9534F">
                        {row["Avg_Pct_per_1s"]:.2f}% / 1s
                    </FONT>
                </TD>
            </TR>
        </TABLE>
        """

        graph.node(leaf_id, f"<{leaf_html}>")
        graph.edge(resin_id, leaf_id)

st.graphviz_chart(
    graph,
    use_container_width=False
)


# =========================================================
# 6. SATURATION ANALYSIS
# =========================================================
st.markdown("---")
st.subheader("📉 Dilution Efficiency & Saturation Analysis")

st.caption(
    "Dilution Efficiency = Viscosity Drop ÷ Solvent Blending Ratio. "
    "A lower value means additional solvent gives less viscosity reduction."
)

col1, col2 = st.columns(2)

with col1:
    resin_options = sorted(
        filtered_df["Resin"].dropna().unique().tolist()
    )

    selected_resin = st.selectbox(
        "Select Resin for Saturation Analysis:",
        resin_options,
        key="saturation_resin"
    )

analysis_resin_df = filtered_df[
    filtered_df["Resin"] == selected_resin
].copy()

with col2:
    solvent_options = sorted(
        analysis_resin_df["Solvent_Type"].dropna().unique().tolist()
    )

    selected_solvent = st.selectbox(
        "Select Solvent for Saturation Analysis:",
        solvent_options,
        key="saturation_solvent"
    )

saturation_df = analysis_resin_df[
    analysis_resin_df["Solvent_Type"] == selected_solvent
].copy()

# Variables retained for Word export
fig_efficiency = None
baseline_efficiency = None
warning_ratio = None
stop_ratio = None

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

    # Each interval requires at least 3 records
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

        efficiency_summary["Efficiency_Retention_Percent"] = (
            efficiency_summary["Median_Efficiency"]
            / baseline_efficiency
            * 100
        )

        warning_rows = efficiency_summary[
            efficiency_summary["Efficiency_Retention_Percent"] <= 70
        ]

        stop_rows = efficiency_summary[
            efficiency_summary["Efficiency_Retention_Percent"] <= 50
        ]

        # Fallback historical guardrails
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

        fig_efficiency = go.Figure()

        fig_efficiency.add_trace(
            go.Scatter(
                x=efficiency_summary["Ratio_Midpoint"],
                y=efficiency_summary["Median_Efficiency"],
                mode="lines+markers+text",
                text=efficiency_summary["Records"].astype(str),
                textposition="top center",
                hovertemplate=(
                    "Ratio Range: %{customdata[0]}<br>"
                    "Median Efficiency: %{y:.2f} s/%<br>"
                    "Records: %{customdata[1]}<extra></extra>"
                ),
                customdata=np.column_stack([
                    efficiency_summary["Ratio_Bin"].astype(str),
                    efficiency_summary["Records"]
                ])
            )
        )

        x_max = max(
            efficiency_summary["Ratio_Midpoint"].max() + 1,
            stop_ratio + 1
        )

        # Warning and Stop overlap
        if abs(stop_ratio - warning_ratio) < 0.2:
            fig_efficiency.add_vline(
                x=stop_ratio,
                line_color="red",
                line_width=3,
                line_dash="dash",
                annotation_text=(
                    f"Saturation Limit: {stop_ratio:.1f}%"
                ),
                annotation_position="top right",
                annotation_font_color="red"
            )

            fig_efficiency.add_vrect(
                x0=stop_ratio,
                x1=x_max,
                fillcolor="red",
                opacity=0.08,
                line_width=0
            )

        # Warning and Stop are separate
        else:
            fig_efficiency.add_vline(
                x=warning_ratio,
                line_color="orange",
                line_width=2,
                line_dash="dash",
                annotation_text=f"Warning: {warning_ratio:.1f}%",
                annotation_position="top left",
                annotation_font_color="orange"
            )

            fig_efficiency.add_vline(
                x=stop_ratio,
                line_color="red",
                line_width=3,
                line_dash="dot",
                annotation_text=f"Stop: {stop_ratio:.1f}%",
                annotation_position="top right",
                annotation_font_color="red"
            )

            fig_efficiency.add_vrect(
                x0=warning_ratio,
                x1=stop_ratio,
                fillcolor="orange",
                opacity=0.08,
                line_width=0
            )

            fig_efficiency.add_vrect(
                x0=stop_ratio,
                x1=x_max,
                fillcolor="red",
                opacity=0.10,
                line_width=0
            )

        # Professional chart frame
        fig_efficiency.update_xaxes(
            showline=True,
            linewidth=1.5,
            linecolor="black",
            mirror=True,
            showgrid=True,
            gridcolor="#E6E6E6"
        )

        fig_efficiency.update_yaxes(
            showline=True,
            linewidth=1.5,
            linecolor="black",
            mirror=True,
            showgrid=True,
            gridcolor="#E6E6E6"
        )

        fig_efficiency.update_layout(
            title=(
                "Dilution Efficiency vs Solvent Ratio<br>"
                f"<sup>Resin: {selected_resin} | "
                f"Vendor: {selected_vendor} | "
                f"Solvent: {selected_solvent}</sup>"
            ),
            xaxis_title="Solvent Blending Ratio (%)",
            yaxis_title="Median Dilution Efficiency (seconds / %)",
            template="plotly_white",
            paper_bgcolor="white",
            plot_bgcolor="white",
            height=560,
            showlegend=False,
            margin=dict(l=70, r=55, t=95, b=75),
            shapes=[
                dict(
                    type="rect",
                    xref="paper",
                    yref="paper",
                    x0=0,
                    y0=0,
                    x1=1,
                    y1=1,
                    line=dict(color="black", width=1.2),
                    fillcolor="rgba(0,0,0,0)"
                )
            ]
        )

        st.plotly_chart(
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

        st.caption(
            "A lower dilution-efficiency value indicates that the same "
            "solvent ratio causes less viscosity reduction, suggesting the "
            "system may be approaching saturation."
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
# 7. WORD EXPORT - A4 REPORT
# =========================================================
st.markdown("---")

if fig_efficiency is None:
    st.info(
        "Word export will include the hierarchy chart only because the "
        "saturation chart has insufficient data."
    )

try:
    graph.attr(dpi="300")
    graph_png = graph.pipe(format="png")

    if not graph_png:
        st.error("❌ Unable to create hierarchy image.")
        st.stop()

    graph_stream = io.BytesIO(graph_png)

    doc = Document()

    # A4 portrait format
    section = doc.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.top_margin = Inches(0.55)
    section.bottom_margin = Inches(0.55)
    section.left_margin = Inches(0.60)
    section.right_margin = Inches(0.60)

    # Title
    title = doc.add_heading(
        "Solvent Consumption & Viscosity Control Report",
        level=0
    )
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub_1 = doc.add_paragraph()
    sub_1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_1.add_run(
        f"Vendor: {selected_vendor}"
    ).bold = True

    sub_2 = doc.add_paragraph()
    sub_2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_2.add_run(
        f"Analysis Period: {date_range_str}"
    )

    # Hierarchy image
    doc.add_heading("1. Solvent Consumption Hierarchy", level=1)

    hierarchy_p = doc.add_paragraph()
    hierarchy_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    hierarchy_p.add_run().add_picture(
        graph_stream,
        width=Inches(7.0)
    )

    hierarchy_caption = doc.add_paragraph(
        "Figure 1. Solvent consumption hierarchy by resin and solvent type."
    )
    hierarchy_caption.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Saturation chart only if it can be generated
    if fig_efficiency is not None:
        try:
            chart_png = fig_efficiency.to_image(
                format="png",
                width=1600,
                height=900,
                scale=2
            )

            chart_stream = io.BytesIO(chart_png)

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
                f"(Resin: {selected_resin}; Solvent: {selected_solvent})."
            )
            chart_caption.alignment = WD_ALIGN_PARAGRAPH.CENTER

            doc.add_heading("3. Key Results", level=1)

            result_table = doc.add_table(rows=1, cols=3)
            result_table.style = "Table Grid"

            header_cells = result_table.rows[0].cells
            header_cells[0].text = "Baseline Efficiency"
            header_cells[1].text = "Warning Ratio"
            header_cells[2].text = "Stop Ratio"

            result_cells = result_table.add_row().cells
            result_cells[0].text = f"{baseline_efficiency:.2f} s/%"
            result_cells[1].text = f"{warning_ratio:.2f}%"
            result_cells[2].text = f"{stop_ratio:.2f}%"

            doc.add_paragraph(
                "Interpretation: A lower dilution-efficiency value means "
                "that additional solvent produces less viscosity reduction. "
                "The saturation limit is used as a reference to avoid "
                "excessive solvent addition."
            )

        except Exception as chart_error:
            doc.add_paragraph(
                "Note: Saturation chart could not be exported. "
                "Please ensure Kaleido is installed."
            )
            st.warning(
                f"⚠️ Saturation chart was not added to Word: {chart_error}"
            )

    doc_io = io.BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)

    st.download_button(
        label="📄 Download A4 Word Report",
        data=doc_io,
        file_name=(
            f"Solvent_Viscosity_Report_"
            f"{selected_vendor}_{selected_resin}_{selected_solvent}.docx"
        ),
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        )
    )

except Exception as e:
    st.error(f"❌ Word report export failed: {e}")
    st.exception(e)

