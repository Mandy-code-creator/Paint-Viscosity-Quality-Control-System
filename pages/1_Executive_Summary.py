import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from io import BytesIO
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT


# =========================================================
# EXPORT HISTORICAL CHART TO WORD (ROBUST SAFE VERSION)
# =========================================================
def export_chart_to_word(
    fig,
    selected_resin,
    selected_vendor,
    selected_solvent,
    system_df
):
    doc = Document()

    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width = Inches(11.69)
    section.page_height = Inches(8.27)

    section.top_margin = Inches(0.45)
    section.bottom_margin = Inches(0.45)
    section.left_margin = Inches(0.45)
    section.right_margin = Inches(0.45)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    title_run = title.add_run("Historical Viscosity Transition Analysis")
    title_run.bold = True
    title_run.font.size = Pt(18)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER

    subtitle_run = subtitle.add_run(
        f"Resin: {selected_resin} | "
        f"Vendor: {selected_vendor} | "
        f"Solvent Type: {selected_solvent}"
    )
    subtitle_run.font.size = Pt(10)

    doc.add_paragraph("")

    table = doc.add_table(rows=2, cols=4)
    table.style = "Table Grid"

    headers = [
        "Valid Batches",
        "Median Sensitivity",
        "P10-P90 Ratio Range",
        "Maximum Viscosity Drop"
    ]

    values = [
        f"{len(system_df):,}",
        f"{system_df['Sensitivity'].median():.2f} s/%",
        (
            f"{system_df['Solvent_Ratio_Percent'].quantile(0.10):.1f}%"
            f" - "
            f"{system_df['Solvent_Ratio_Percent'].quantile(0.90):.1f}%"
        ),
        f"{system_df['Delta_V'].max():.1f} s"
    ]

    for i, header in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = header
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(9)

    for i, value in enumerate(values):
        cell = table.cell(1, i)
        cell.text = value
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.font.size = Pt(9)

    doc.add_paragraph("")

    try:
        chart_png = fig.to_image(
            format="png",
            width=1500,
            height=850,
            scale=2
        )
        chart_stream = BytesIO(chart_png)
        chart_paragraph = doc.add_paragraph()
        chart_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        chart_paragraph.add_run().add_picture(
            chart_stream,
            width=Inches(10.4)
        )
    except Exception as e:
        error_paragraph = doc.add_paragraph()
        error_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        error_run = error_paragraph.add_run(
            "\n[⚠️ CHART IMAGE EXPORT FAILED]\n"
            "Server environment is missing 'kaleido' library to render dynamic charts into static PNGs.\n"
            "Please add 'kaleido==0.1.0.post1' to your requirements.txt."
        )
        error_run.bold = True

    note = doc.add_paragraph()
    note_run = note.add_run(
        "Note: Orange points represent viscosity before solvent addition. "
        "Blue points represent viscosity after solvent addition. "
        "The dotted line connects the same mixing batch."
    )
    note_run.italic = True
    note_run.font.size = Pt(9)

    output = BytesIO()
    doc.save(output)
    output.seek(0)

    return output.getvalue()


# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Intelligent SOP System",
    page_icon="⚙️",
    layout="wide"
)

# Ensure data is loaded
if "raw_data_loaded" not in st.session_state or not st.session_state["raw_data_loaded"]:
    st.warning("⚠️ Please upload data on the main page first.")
    st.stop()


# --- 2. DATA PROCESSING & CLEANSING ---
@st.cache_data
def process_data(df):
    data = df.copy()

    if data.empty:
        return data

    # Logic: Filter Valid Group A Records
    data = data[
        (data["添加重量"] > 0)
        & (data["塗料重量"] > 0)
        & (data["黏度(秒)"] > data["黏度(秒)_1"])
        & (data["Resin"].notna())
        & (data["Vendor"].notna())
        & (data["Solvent_Type"].notna())
    ]

    if data.empty:
        return data

    data["Delta_V"] = data["黏度(秒)"] - data["黏度(秒)_1"]
    data = data[data["Delta_V"] > 0]

    if data.empty:
        return data

    # Logic: Standard Formulas for Historical Data
    data["Dilution_Base"] = data["塗料重量"] + 120
    data["Solvent_Ratio_Percent"] = (
        data["添加重量"] / data["Dilution_Base"]
    ) * 100

    data["Sensitivity"] = (
        data["Delta_V"]
        / data["Solvent_Ratio_Percent"].replace(0, np.nan)
    )

    # Logic: Viscosity Zones
    def assign_zone(v):
        if v <= 70:
            return "<=70 s"
        elif v <= 90:
            return "71-90 s"
        elif v <= 110:
            return "91-110 s"
        elif v <= 130:
            return "111-130 s"
        else:
            return ">130 s"

    data["Initial_Viscosity_Zone"] = data["黏度(秒)"].apply(assign_zone)

    # STRICT STATISTICAL RULE: n >= 30 BATCHES
    system_batch_counts = (
        data.groupby(
            ["Resin", "Vendor", "Solvent_Type"]
        )["塗料批號"]
        .transform("nunique")
    )

    data = data[system_batch_counts >= 30].copy()

    if data.empty:
        return data

    # Logic: P1-P99 Outlier Filtering
    q01 = (
        data.groupby(
            ["Resin", "Vendor", "Solvent_Type"]
        )["Sensitivity"]
        .transform(lambda x: x.quantile(0.01))
    )

    q99 = (
        data.groupby(
            ["Resin", "Vendor", "Solvent_Type"]
        )["Sensitivity"]
        .transform(lambda x: x.quantile(0.99))
    )

    data_clean = data[
        data["Sensitivity"].between(q01, q99)
    ].copy()

    return data_clean


master_df = process_data(st.session_state["group_a_data"])

if master_df.empty or "Resin" not in master_df.columns:
    st.error(
        "⚠️ No valid historical data available. All systems failed to meet "
        "the strict statistical requirement (n ≥ 30 batches) or basic SOP "
        "logic constraints."
    )
    st.stop()


# --- STATE MANAGEMENT ---
def reset_execution_states():
    st.session_state["exec_curr_visc"] = 0.0
    st.session_state["exec_lsl"] = 0.0
    st.session_state["exec_usl"] = 0.0
    st.session_state["exec_order_weight"] = 0.0
    st.session_state["calculation_done"] = False


# --- GLOBAL FILTERS ---
st.title("⚙️ AI-Assisted Viscosity Optimization System")

st.markdown(
    "Automated recommendation engine governed by historical safety thresholds, "
    "strictly filtered for statistical significance (n ≥ 30)."
)

st.markdown("---")

col_f1, col_f2, col_f3 = st.columns(3)

with col_f1:
    selected_resin = st.selectbox(
        "Select Resin:",
        sorted(master_df["Resin"].unique()),
        on_change=reset_execution_states
    )

with col_f2:
    selected_vendor = st.selectbox(
        "Select Vendor:",
        sorted(
            master_df[
                master_df["Resin"] == selected_resin
            ]["Vendor"].unique()
        ),
        on_change=reset_execution_states
    )

with col_f3:
    selected_solvent = st.selectbox(
        "Select Solvent Type:",
        sorted(
            master_df[
                (master_df["Resin"] == selected_resin)
                & (master_df["Vendor"] == selected_vendor)
            ]["Solvent_Type"].unique()
        ),
        on_change=reset_execution_states
    )

system_df = master_df[
    (master_df["Resin"] == selected_resin)
    & (master_df["Vendor"] == selected_vendor)
    & (master_df["Solvent_Type"] == selected_solvent)
]

if system_df.empty:
    st.error("No valid historical data available for this configuration.")
    st.stop()


# --- TABS ARCHITECTURE ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Tab 1: Historical Analysis",
    "🎯 Tab 2: SOP Recommendation",
    "🔬 Tab 3: Engineering Matrix",
    "🖨️ Tab 4: Master Shop Floor SOP"
])


# ==========================================
# TAB 1: HISTORICAL ANALYSIS
# ==========================================
with tab1:
    st.markdown("### Historical Performance Review")

    st.markdown(
        "Validate data stability before enforcing automated SOPs. "
        "*Hover over points to trace individual batches from their "
        "Initial (Orange) to Final (Blue) state.*"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Valid Batches (n ≥ 30)", len(system_df))
    c2.metric(
        "Median Sensitivity",
        f"{system_df['Sensitivity'].median():.2f} s/%"
    )
    c3.metric(
        "P10 - P90 Ratio Range",
        f"{system_df['Solvent_Ratio_Percent'].quantile(0.1):.1f}% - "
        f"{system_df['Solvent_Ratio_Percent'].quantile(0.9):.1f}%"
    )
    c4.metric(
        "Max Drop (Delta V)",
        f"{system_df['Delta_V'].max():.1f} s"
    )

    fig_scatter = go.Figure()

    x_lines = []
    y_lines = []

    for _, row in system_df.iterrows():
        x_lines.extend([
            row["Solvent_Ratio_Percent"],
            row["Solvent_Ratio_Percent"],
            None
        ])

        y_lines.extend([
            row["黏度(秒)"],
            row["黏度(秒)_1"],
            None
        ])

    fig_scatter.add_trace(
        go.Scatter(
            x=x_lines,
            y=y_lines,
            mode="lines",
            line=dict(
                color="lightgray",
                width=1.5,
                dash="dot"
            ),
            hoverinfo="skip",
            showlegend=False
        )
    )

    fig_scatter.add_trace(
        go.Scatter(
            x=system_df["Solvent_Ratio_Percent"],
            y=system_df["黏度(秒)"],
            mode="markers",
            name="Initial Viscosity (Before)",
            marker=dict(
                color="#ED7D31",
                size=9,
                line=dict(width=1, color="white")
            ),
            customdata=system_df[
                [
                    "黏度(秒)_1",
                    "Delta_V",
                    "Initial_Viscosity_Zone"
                ]
            ].values,
            hovertemplate=(
                "<b>Zone: %{customdata[2]}</b><br>"
                "Solvent Ratio: %{x:.2f}%<br>"
                "Initial Visc (Before): %{y:.1f}s 🌟<br>"
                "Final Visc (After): %{customdata[0]:.1f}s<br>"
                "Viscosity Drop (Delta V): %{customdata[1]:.1f}s"
                "<extra></extra>"
            )
        )
    )

    fig_scatter.add_trace(
        go.Scatter(
            x=system_df["Solvent_Ratio_Percent"],
            y=system_df["黏度(秒)_1"],
            mode="markers",
            name="Final Viscosity (After)",
            marker=dict(
                color="#4472C4",
                size=9,
                line=dict(width=1, color="white")
            ),
            customdata=system_df[
                [
                    "黏度(秒)",
                    "Delta_V",
                    "Initial_Viscosity_Zone"
                ]
            ].values,
            hovertemplate=(
                "<b>Zone: %{customdata[2]}</b><br>"
                "Solvent Ratio: %{x:.2f}%<br>"
                "Initial Visc (Before): %{customdata[0]:.1f}s<br>"
                "Final Visc (After): %{y:.1f}s 🌟<br>"
                "Viscosity Drop (Delta V): %{customdata[1]:.1f}s"
                "<extra></extra>"
            )
        )
    )

    chart_title = (
        f"Viscosity Transition by Solvent Ratio<br>"
        f"<sup>Resin: {selected_resin} | "
        f"Vendor: {selected_vendor} | "
        f"Solvent: {selected_solvent}</sup>"
    )

    fig_scatter.update_layout(
        title=dict(
            text=chart_title,
            x=0.5,
            xanchor="center",
            y=0.97,
            yanchor="top",
            font=dict(size=18, color="#1F3855")
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=620,
        margin=dict(l=70, r=50, t=95, b=70),
        xaxis=dict(
            title="Solvent Blending Ratio (%)",
            showgrid=True,
            gridcolor="#EAEAEA",
            linecolor="black",
            linewidth=1.5,
            showline=True,
            mirror=True,
            ticks="outside"
        ),
        yaxis=dict(
            title="Viscosity (seconds)",
            showgrid=True,
            gridcolor="#EAEAEA",
            linecolor="black",
            linewidth=1.5,
            showline=True,
            mirror=True,
            ticks="outside"
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.07,
            xanchor="center",
            x=0.5
        ),
        hovermode="closest",
        shapes=[
            dict(
                type="rect",
                xref="paper",
                yref="paper",
                x0=0,
                y0=0,
                x1=1,
                y1=1,
                line=dict(
                    color="#1F3855",
                    width=1.5
                ),
                fillcolor="rgba(0,0,0,0)"
            )
        ]
    )

    st.plotly_chart(fig_scatter, use_container_width=True)

    word_data = export_chart_to_word(
        fig=fig_scatter,
        selected_resin=selected_resin,
        selected_vendor=selected_vendor,
        selected_solvent=selected_solvent,
        system_df=system_df
    )

    file_name = (
        f"Viscosity_Transition_"
        f"{selected_resin}_{selected_vendor}_{selected_solvent}.docx"
    )

    st.download_button(
        label="📄 Export Historical Chart to Word",
        data=word_data,
        file_name=file_name,
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        )
    )


# ==========================================
# TAB 2: SOP RECOMMENDATION
# ==========================================
with tab2:
    st.markdown("### Process Parameter Configuration")

    for key in [
        "exec_curr_visc",
        "exec_lsl",
        "exec_usl",
        "exec_order_weight"
    ]:
        if key not in st.session_state:
            st.session_state[key] = 0.0

    col_i1, col_i2, col_i3, col_i4 = st.columns(4)

    with col_i1:
        curr_visc = st.number_input(
            "Current Viscosity (s)",
            value=st.session_state["exec_curr_visc"],
            step=1.0,
            key="iv"
        )

    with col_i2:
        app_lsl = st.number_input(
            "Approved Target LSL (s)",
            value=st.session_state["exec_lsl"],
            step=1.0,
            key="ilsl"
        )

    with col_i3:
        app_usl = st.number_input(
            "Approved Target USL (s)",
            value=st.session_state["exec_usl"],
            step=1.0,
            key="iusl"
        )

    with col_i4:
        order_weight = st.number_input(
            "Order Paint Weight (kg)",
            value=st.session_state["exec_order_weight"],
            step=10.0,
            key="iow"
        )

    st.markdown("---")

    if st.button("🚀 Calculate Optimized SOP", type="primary"):
        if (
            curr_visc <= 0
            or app_lsl <= 0
            or app_usl <= 0
            or order_weight <= 0
        ):
            st.error("⚠️ All input parameters must be strictly greater than 0.")

        elif app_lsl >= app_usl:
            st.error("⚠️ LSL must be strictly less than USL.")

        else:
            target_center = (app_lsl + app_usl) / 2
            required_drop = curr_visc - target_center

            if required_drop <= 0:
                st.success(
                    "✅ Current viscosity is already within or below the target range. "
                    "No solvent required."
                )
                st.session_state["calculation_done"] = False

            else:
                def get_zone_str(v):
                    if v <= 70:
                        return "<=70 s"
                    elif v <= 90:
                        return "71-90 s"
                    elif v <= 110:
                        return "91-110 s"
                    elif v <= 130:
                        return "111-130 s"
                    else:
                        return ">130 s"

                curr_zone = get_zone_str(curr_visc)

                zone_data = system_df[
                    system_df["Initial_Viscosity_Zone"] == curr_zone
                ]

                if len(zone_data) >= 5:
                    ref_data = zone_data
                    record_count = len(zone_data)
                    ref_source = f"Zone-Specific ({curr_zone})"
                else:
                    ref_data = system_df
                    record_count = len(system_df)
                    ref_source = "Overall System Fallback"

                if record_count >= 10:
                    conf_msg = "🟢 Reliable"
                elif record_count >= 5:
                    conf_msg = "🟡 Usable with Caution"
                else:
                    conf_msg = "🔴 Insufficient Data"

                if record_count < 5:
                    st.error(
                        "🚨 **SYSTEM BLOCKED:** Insufficient historical data "
                        "(<5 records) to generate safe automation. Manual "
                        "Process Engineer verification required."
                    )
                    st.session_state["calculation_done"] = False

                else:
                    ref_sensitivity = ref_data["Sensitivity"].median()
                    ref_ratio_p90 = ref_data["Solvent_Ratio_Percent"].quantile(0.9)
                    ref_ratio_p95 = ref_data["Solvent_Ratio_Percent"].quantile(0.95)
                    ref_drop_p90 = ref_data["Delta_V"].quantile(0.9)
                    ref_drop_max = ref_data["Delta_V"].max()

                    dilution_base = order_weight + 120
                    required_ratio = required_drop / ref_sensitivity
                    recommended_solvent = dilution_base * (required_ratio / 100)
                    max_total_solvent = dilution_base * (ref_ratio_p90 / 100)

                    risk_status = ""
                    risk_color = ""
                    blocked = False

                    if required_ratio > ref_ratio_p95 or required_drop > ref_drop_max:
                        risk_status = (
                            "🚨 CRITICAL OVERLOAD: Target exceeds P95 Safe Limits."
                        )
                        risk_color = "red"
                        blocked = True

                    elif (
                        ref_ratio_p90 < required_ratio <= ref_ratio_p95
                    ) or (
                        ref_drop_p90 < required_drop <= ref_drop_max
                    ):
                        risk_status = (
                            "⚠️ DIMINISHING RETURNS WARNING: Target exceeds "
                            "P90 Optimal Zone. Extra supervision required."
                        )
                        risk_color = "orange"

                    else:
                        risk_status = (
                            "✅ NORMAL OPERATION: Target within P90 "
                            "historical bounds."
                        )
                        risk_color = "green"

                    st.markdown(
                        f"### Assessment: "
                        f"<span style='color:{risk_color}'>{risk_status}</span>",
                        unsafe_allow_html=True
                    )

                    if blocked:
                        st.error(
                            "Execution automatically blocked by Safety Constraints. "
                            "Please escalate to Process Engineer."
                        )
                        st.session_state["calculation_done"] = False

                    else:
                        st.session_state.update({
                            "calculation_done": True,
                            "calc_curr_visc": curr_visc,
                            "calc_lsl": app_lsl,
                            "calc_usl": app_usl,
                            "calc_order_weight": order_weight,
                            "calc_base": dilution_base,
                            "calc_req_drop": required_drop,
                            "calc_sensitivity": ref_sensitivity,
                            "calc_ref_source": ref_source,
                            "calc_conf": conf_msg,
                            "calc_records": record_count,
                            "calc_rec_solvent": recommended_solvent,
                            "calc_max_solvent": max_total_solvent,
                            "sys_resin": selected_resin,
                            "sys_vendor": selected_vendor,
                            "sys_solvent": selected_solvent,
                            "calc_risk": risk_status
                        })

                        col_r1, col_r2, col_r3 = st.columns(3)

                        col_r1.metric(
                            "Required Viscosity Drop",
                            f"{required_drop:.1f} s"
                        )

                        col_r2.metric(
                            "Reference Sensitivity",
                            f"{ref_sensitivity:.2f} s/%",
                            help=f"Source: {ref_source} (n={record_count})"
                        )

                        col_r3.metric("Data Confidence", conf_msg)

                        st.success(
                            f"**Calculated Total Recommendation:** "
                            f"`{recommended_solvent:.2f} kg` "
                            f"(Absolute Limit: {max_total_solvent:.2f} kg)"
                        )

                        st.markdown(
                            "### 🛠️ Execution Protocol (3-Stage Addition)"
                        )

                        st.markdown(
                            f"""
                            * **Step 1 (60%):** Add `{recommended_solvent * 0.60:.2f} kg` -> Agitate & Measure.
                            * **Step 2 (25%):** Add `{recommended_solvent * 0.25:.2f} kg` -> Only if > USL.
                            * **Step 3 (15%):** Add up to `{recommended_solvent * 0.15:.2f} kg` -> Fine Micro-Adjustment.
                            """
                        )


# ==========================================
# TAB 3: ENGINEERING MATRIX
# ==========================================
with tab3:
    st.markdown("### 🔬 Comprehensive Engineering Matrix")

    st.markdown(
        "Full operational baseline matrix for safety boundary definitions. "
        "Filtered by selected Resin & Vendor."
    )

    def generate_matrix(df):
        grouped = df.groupby(
            "Initial_Viscosity_Zone",
            observed=False
        ).agg(
            Records=("塗料批號", "nunique"),
            Sensitivity_Median=("Sensitivity", "median"),
            Ratio_Median=("Solvent_Ratio_Percent", "median"),
            Ratio_P90=(
                "Solvent_Ratio_Percent",
                lambda x: x.quantile(0.9)
            ),
            Ratio_P95=(
                "Solvent_Ratio_Percent",
                lambda x: x.quantile(0.95)
            ),
            Drop_Median=("Delta_V", "median"),
            Drop_P90=("Delta_V", lambda x: x.quantile(0.9)),
            Drop_Max=("Delta_V", "max")
        ).reset_index()

        return grouped

    eng_matrix = generate_matrix(system_df)

    st.dataframe(
        eng_matrix,
        column_config={
            "Records": st.column_config.NumberColumn(format="%d"),
            "Sensitivity_Median": st.column_config.NumberColumn(
                "Median Sensitivity (s/%)",
                format="%.2f"
            ),
            "Ratio_Median": st.column_config.NumberColumn(
                "Median Ratio %",
                format="%.2f"
            ),
            "Ratio_P90": st.column_config.NumberColumn(
                "P90 Ratio %",
                format="%.2f"
            ),
            "Ratio_P95": st.column_config.NumberColumn(
                "P95 Ratio %",
                format="%.2f"
            ),
            "Drop_Median": st.column_config.NumberColumn(
                "Median Drop (s)",
                format="%.1f"
            ),
            "Drop_P90": st.column_config.NumberColumn(
                "P90 Drop (s)",
                format="%.1f"
            ),
            "Drop_Max": st.column_config.NumberColumn(
                "Max Drop (s)",
                format="%.1f"
            )
        },
        use_container_width=True,
        hide_index=True
    )


# ==========================================
# TAB 4: MASTER SHOP FLOOR SOP
# ==========================================
with tab4:
    st.markdown("### 🖨️ Master Shop Floor SOP Matrix")

    st.markdown(
        "*A simplified, global lookup table covering ALL statistically "
        "validated systems (n ≥ 30). Designed to be printed and attached "
        "to mixing stations for quick operator reference.*"
    )

    st.info(
        "💡 **DILUTION BASE RULE:** Always calculate solvent based on "
        "**Dilution Base (Order Weight + 120kg minimum operating paint)**. "
        "Do not multiply by Order Weight alone."
    )

    matrix_df = master_df.copy()

    sop_grouped = matrix_df.groupby(
        [
            "Resin",
            "Vendor",
            "Solvent_Type",
            "Initial_Viscosity_Zone"
        ],
        observed=False
    ).agg(
        Valid_Batches=("塗料批號", "nunique"),
        Target_Visc=("黏度(秒)_1", "median"),
        Optimal_Sens=("Sensitivity", "median"),
        Max_Safe_Ratio=("Solvent_Ratio_Percent", "max")
    ).reset_index()

    sop_grouped = sop_grouped[
        (sop_grouped["Valid_Batches"] >= 5)
        & (sop_grouped["Optimal_Sens"] > 0)
    ]

    sop_grouped["Practical_Factor"] = (
        10.0 / sop_grouped["Optimal_Sens"]
    )

    sop_output = sop_grouped[
        [
            "Resin",
            "Vendor",
            "Solvent_Type",
            "Initial_Viscosity_Zone",
            "Valid_Batches", 
            "Target_Visc",
            "Practical_Factor",
            "Max_Safe_Ratio"
        ]
    ].copy()

    sop_output.rename(
        columns={
            "Solvent_Type": "Solvent",
            "Initial_Viscosity_Zone": "Input Viscosity Range",
            "Valid_Batches": "Valid Batches",
            "Target_Visc": "Typical Target (s)",
            "Practical_Factor": (
                "Add kg (per 100kg Dilution Base / 10s drop)"
            ),
            "Max_Safe_Ratio": "Max Safe Limit (%)"
        },
        inplace=True
    )

    st.dataframe(
        sop_output.sort_values(
            by=[
                "Resin",
                "Vendor",
                "Solvent",
                "Input Viscosity Range"
            ]
        ),
        column_config={
            "Valid Batches": st.column_config.NumberColumn(
                format="%d"
            ),
            "Typical Target (s)": st.column_config.NumberColumn(
                format="%.1f"
            ),
            "Add kg (per 100kg Dilution Base / 10s drop)": (
                st.column_config.NumberColumn(format="%.2f kg")
            ),
            "Max Safe Limit (%)": st.column_config.NumberColumn(
                format="%.1f%%"
            )
        },
        use_container_width=True,
        hide_index=True
    )

    csv_export = sop_output.to_csv(index=False).encode("utf-8")

    st.download_button(
        "📥 Download Printable SOP Matrix (CSV)",
        data=csv_export,
        file_name="Shop_Floor_Master_SOP_Validated.csv",
        mime="text/csv"
    )
