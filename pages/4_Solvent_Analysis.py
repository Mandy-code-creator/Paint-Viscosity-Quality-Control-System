```python
import streamlit as st
import pandas as pd
import numpy as np
import graphviz
import io
import plotly.graph_objects as go
from docx import Document
from docx.shared import Inches

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Solvent Hierarchy", page_icon="🌳", layout="wide")

st.title("🌳 Solvent Consumption Hierarchy")
st.markdown(
    "Coil-level analysis of solvent utilization mapping from Vendor "
    "to specific Resin and Solvent types."
)

# --- 1. DATA LOADING & SAFE CHECK ---
if not st.session_state.get("raw_data_loaded", False):
    st.warning("⚠️ No data loaded. Please upload your dataset on the Main App page.")
    st.stop()

group_a = st.session_state.get("group_a_data", pd.DataFrame()).copy()

if group_a.empty:
    st.error("❌ The dataset is empty. Please check the uploaded file.")
    st.stop()

# --- 2. SIDEBAR FILTERS ---
st.sidebar.header("🔍 Hierarchy Filters")

for col in ["Vendor", "Resin", "Solvent_Type"]:
    if col not in group_a.columns:
        group_a[col] = "Unknown"

vendor_list = sorted(group_a["Vendor"].dropna().unique().tolist())
selected_vendor = st.sidebar.selectbox("Select Vendor:", vendor_list)

filtered_df = group_a[group_a["Vendor"] == selected_vendor].copy()

if "Grade" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["Grade"].isin(["A", "B", "A-B"])]

if filtered_df.empty:
    st.warning(f"⚠️ No valid coil data available for {selected_vendor}.")
    st.stop()

# --- 3. METRIC CALCULATIONS ---
required_cols = ["塗料重量", "添加重量", "黏度(秒)", "黏度(秒)_1"]

if not all(col in filtered_df.columns for col in required_cols):
    st.error(f"❌ Missing required columns: {', '.join(required_cols)}")
    st.stop()

# Convert to numeric safely
for col in required_cols:
    filtered_df[col] = pd.to_numeric(filtered_df[col], errors="coerce")

# Keep valid dilution records only
filtered_df = filtered_df[
    (filtered_df["塗料重量"] > 0)
    & (filtered_df["添加重量"] > 0)
    & (filtered_df["黏度(秒)"] > filtered_df["黏度(秒)_1"])
].copy()

if filtered_df.empty:
    st.warning("⚠️ No valid dilution records after data cleaning.")
    st.stop()

# Main calculation logic
filtered_df["Delta_V"] = (
    filtered_df["黏度(秒)"] - filtered_df["黏度(秒)_1"]
)

# Calculation basis includes 120 kg operating paint inside the line
filtered_df["Dilution_Base_kg"] = filtered_df["塗料重量"] + 120

filtered_df["Solvent_Ratio_Percent"] = (
    filtered_df["添加重量"] / filtered_df["Dilution_Base_kg"]
) * 100

filtered_df["Kg_per_1s"] = (
    filtered_df["添加重量"] / filtered_df["Delta_V"]
)

# Amount of solvent ratio required for 1-second viscosity reduction
filtered_df["Pct_per_1s"] = (
    filtered_df["Solvent_Ratio_Percent"] / filtered_df["Delta_V"]
)

# Dilution efficiency: viscosity reduction achieved by each 1% solvent ratio
filtered_df["Dilution_Efficiency"] = (
    filtered_df["Delta_V"] / filtered_df["Solvent_Ratio_Percent"]
)

# Remove invalid / infinite values
filtered_df = filtered_df.replace([np.inf, -np.inf], np.nan).dropna(
    subset=[
        "Solvent_Ratio_Percent",
        "Delta_V",
        "Kg_per_1s",
        "Pct_per_1s",
        "Dilution_Efficiency",
    ]
)

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
].sort_values(by="Total_Paint", ascending=False)

if tree_summary.empty:
    st.info("No valid paint consumption data available to render the hierarchy.")
    st.stop()

# --- 4. RENDER GRAPHVIZ ---
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

# --- 4.1 ROOT NODE ---
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
    if "date" in col.lower() or "日期" in col.lower() or "time" in col.lower()
]

if date_cols:
    date_col = date_cols[0]
    try:
        min_date = pd.to_datetime(filtered_df[date_col]).min().strftime("%b %Y")
        max_date = pd.to_datetime(filtered_df[date_col]).max().strftime("%b %Y")
        date_range_str = (
            f"{min_date} - {max_date}"
            if min_date != max_date
            else min_date
        )
    except Exception:
        date_range_str = "All Available Data"
else:
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

# --- 4.2 CHILD NODES ---
unique_resins = tree_summary["Resin"].unique()

for resin in unique_resins:
    resin_id = f"resin_{resin}"
    resin_data = tree_summary[tree_summary["Resin"] == resin]

    resin_paint_sum = resin_data["Total_Paint"].sum()
    resin_solvent_sum = resin_data["Total_Solvent"].sum()

    resin_html = f"""
    <TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="2">
        <TR>
            <TD BGCOLOR="#E6F2FF" STYLE="ROUNDED" BORDER="1"
                COLOR="#00BFFF" ALIGN="CENTER">
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

st.graphviz_chart(graph, use_container_width=False)

# =========================================================
# 5. SATURATION ANALYSIS CHART
# =========================================================
st.markdown("---")
st.subheader("📉 Dilution Efficiency & Saturation Analysis")
st.caption(
    "Dilution Efficiency = Viscosity Drop ÷ Solvent Blending Ratio. "
    "A lower value means that adding more solvent produces less viscosity reduction."
)

col1, col2 = st.columns(2)

with col1:
    resin_options = sorted(filtered_df["Resin"].dropna().unique().tolist())
    selected_resin = st.selectbox(
        "Select Resin for Saturation Analysis:",
        resin_options
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
        solvent_options
    )

saturation_df = analysis_resin_df[
    analysis_resin_df["Solvent_Type"] == selected_solvent
].copy()

if len(saturation_df) < 5:
    st.warning(
        "⚠️ Historical records are insufficient for saturation analysis "
        "(minimum 5 records required)."
    )
else:
    # Group dilution ratio into intervals
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
        Median_Efficiency=("Dilution_Efficiency", "median"),
        Mean_Efficiency=("Dilution_Efficiency", "mean")
    ).reset_index()

    efficiency_summary["Ratio_Midpoint"] = midpoints
    efficiency_summary = efficiency_summary[
        efficiency_summary["Records"] >= 3
    ].copy()

    if efficiency_summary.empty:
        st.warning(
            "⚠️ Each solvent-ratio interval has insufficient records "
            "to calculate a reliable efficiency trend."
        )
    else:
        # Baseline = first valid ratio interval
        baseline_efficiency = efficiency_summary[
            "Median_Efficiency"
        ].iloc[0]

        efficiency_summary["Efficiency_Retention_Percent"] = (
            efficiency_summary["Median_Efficiency"]
            / baseline_efficiency
            * 100
        )

        # Warning: efficiency falls to <= 70% of baseline
        warning_rows = efficiency_summary[
            efficiency_summary["Efficiency_Retention_Percent"] <= 70
        ]

        # Stop: efficiency falls to <= 50% of baseline
        stop_rows = efficiency_summary[
            efficiency_summary["Efficiency_Retention_Percent"] <= 50
        ]

        # If no obvious saturation decline is found,
        # use P90 and P95 as conservative historical guardrails.
        ratio_p90 = saturation_df["Solvent_Ratio_Percent"].quantile(0.90)
        ratio_p95 = saturation_df["Solvent_Ratio_Percent"].quantile(0.95)

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

        # Chart
        fig_efficiency = go.Figure()

        fig_efficiency.add_trace(
            go.Scatter(
                x=efficiency_summary["Ratio_Midpoint"],
                y=efficiency_summary["Median_Efficiency"],
                mode="lines+markers+text",
                text=efficiency_summary["Records"].astype(str),
                textposition="top center",
                name="Median Dilution Efficiency",
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

        fig_efficiency.add_vline(
            x=warning_ratio,
            line_dash="dash",
            annotation_text=f"Warning: {warning_ratio:.1f}%",
            annotation_position="top left"
        )

        fig_efficiency.add_vline(
            x=stop_ratio,
            line_dash="dot",
            annotation_text=f"Stop: {stop_ratio:.1f}%",
            annotation_position="top right"
        )

        fig_efficiency.update_layout(
            title=(
                f"Dilution Efficiency vs Solvent Ratio<br>"
                f"<sup>Resin: {selected_resin} | "
                f"Vendor: {selected_vendor} | "
                f"Solvent: {selected_solvent}</sup>"
            ),
            xaxis_title="Solvent Blending Ratio (%)",
            yaxis_title="Median Dilution Efficiency (seconds / %)",
            template="plotly_white",
            height=520,
            showlegend=False,
            margin=dict(l=60, r=40, t=90, b=60)
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
            "Interpretation: when the dilution efficiency declines, "
            "additional solvent produces less viscosity reduction. "
            "The Warning Ratio indicates that the operator should re-check "
            "viscosity before adding more solvent; the Stop Ratio indicates "
            "that continued addition is not recommended."
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
# 6. WORD EXPORT
# =========================================================
try:
    graph.attr(dpi="300")
    png_data = graph.pipe(format="png")

    if not png_data:
        st.error("Lỗi: Không tạo được dữ liệu ảnh từ Graphviz.")
        st.stop()

    image_stream = io.BytesIO(png_data)

    doc = Document()
    doc.add_heading(
        f"Solvent Consumption & Viscosity Control: {selected_vendor}",
        0
    )
    doc.add_paragraph("Report Level: Coil-Level Data")
    doc.add_paragraph("Quality Filter: Grade A-B and above")
    doc.add_picture(image_stream, width=Inches(6.5))

    doc_io = io.BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)

    col_empty, col_btn = st.columns([4, 1])

    with col_btn:
        st.download_button(
            label="📄 Download Word Report",
            data=doc_io,
            file_name=f"Solvent_Report_{selected_vendor}.docx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            )
        )

except Exception as e:
    st.error(f"Đã xảy ra lỗi khi tạo file Word: {e}")
    st.exception(e)
```
