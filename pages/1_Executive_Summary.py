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


# =========================================================
# PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="Intelligent SOP System",
    page_icon="⚙️",
    layout="wide"
)

if (
    "raw_data_loaded" not in st.session_state
    or not st.session_state["raw_data_loaded"]
):
    st.warning("⚠️ Please upload data on the main page first.")
    st.stop()


# =========================================================
# DATA PROCESSING & CLEANSING
# =========================================================
@st.cache_data
def process_data(df):
    data = df.copy()

    if data.empty:
        return data

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

    data["Dilution_Base"] = data["塗料重量"] + 120

    data["Solvent_Ratio_Percent"] = (
        data["添加重量"] / data["Dilution_Base"]
    ) * 100

    data["Sensitivity"] = (
        data["Delta_V"]
        / data["Solvent_Ratio_Percent"].replace(0, np.nan)
    )

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

    system_batch_counts = (
        data.groupby(
            ["Resin", "Vendor", "Solvent_Type"]
        )["塗料批號"]
        .transform("nunique")
    )

    data = data[system_batch_counts >= 30].copy()

    if data.empty:
        return data

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


# =========================================================
# SATURATION / DIMINISHING RETURNS ANALYSIS
# =========================================================
def build_saturation_profile(df):

    ratio_bins = [0, 3, 5, 7, 9, 11, np.inf]

    ratio_labels = [
        "0-3%",
        "3-5%",
        "5-7%",
        "7-9%",
        "9-11%",
        ">11%"
    ]

    sat_df = df.copy()

    sat_df["Ratio_Zone"] = pd.cut(
        sat_df["Solvent_Ratio_Percent"],
        bins=ratio_bins,
        labels=ratio_labels,
        include_lowest=True,
        right=False
    )

    profile = sat_df.groupby(
        "Ratio_Zone",
        observed=False
    ).agg(
        Records=("塗料批號", "nunique"),
        Ratio_Median=("Solvent_Ratio_Percent", "median"),
        Ratio_Min=("Solvent_Ratio_Percent", "min"),
        Ratio_Max=("Solvent_Ratio_Percent", "max"),
        DeltaV_Median=("Delta_V", "median"),
        Sensitivity_Median=("Sensitivity", "median"),
        Sensitivity_P25=("Sensitivity", lambda x: x.quantile(0.25)),
        Sensitivity_P75=("Sensitivity", lambda x: x.quantile(0.75))
    ).reset_index()

    valid_profile = profile[
        (profile["Records"] >= 5)
        & (profile["Sensitivity_Median"] > 0)
    ].copy()

    profile["Efficiency_vs_Baseline_%"] = np.nan
    profile["Saturation_Status"] = "Insufficient Data"

    warning_ratio = np.nan
    saturation_ratio = np.nan
    baseline_sensitivity = np.nan

    if not valid_profile.empty:
        baseline_row = valid_profile.iloc[0]

        baseline_sensitivity = baseline_row["Sensitivity_Median"]

        profile["Efficiency_vs_Baseline_%"] = (
            profile["Sensitivity_Median"]
            / baseline_sensitivity
            * 100
        )

        for idx, row in profile.iterrows():

            if (
                row["Records"] < 5
                or pd.isna(row["Efficiency_vs_Baseline_%"])
            ):
                continue

            efficiency = row["Efficiency_vs_Baseline_%"]

            if efficiency <= 50:
                profile.loc[idx, "Saturation_Status"] = (
                    "🔴 Saturation Zone"
                )

                if pd.isna(saturation_ratio):
                    saturation_ratio = row["Ratio_Min"]

            elif efficiency <= 70:
                profile.loc[idx, "Saturation_Status"] = (
                    "🟠 Diminishing Returns"
                )

                if pd.isna(warning_ratio):
                    warning_ratio = row["Ratio_Min"]

            else:
                profile.loc[idx, "Saturation_Status"] = (
                    "🟢 Normal Efficiency"
                )

    return {
        "profile": profile,
        "baseline_sensitivity": baseline_sensitivity,
        "warning_ratio": warning_ratio,
        "saturation_ratio": saturation_ratio
    }


# =========================================================
# LOAD DATA
# =========================================================
master_df = process_data(st.session_state["group_a_data"])

if master_df.empty or "Resin" not in master_df.columns:
    st.error(
        "⚠️ No valid historical data available. All systems failed to meet "
        "the strict statistical requirement (n ≥ 30 batches) or basic SOP "
        "logic constraints."
    )
    st.stop()


# =========================================================
# STATE MANAGEMENT
# =========================================================
def reset_execution_states():
    st.session_state["exec_curr_visc"] = 0.0
    st.session_state["exec_lsl"] = 0.0
    st.session_state["exec_usl"] = 0.0
    st.session_state["exec_order_weight"] = 0.0
    st.session_state["calculation_done"] = False


# =========================================================
# GLOBAL FILTERS
# =========================================================
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


# =========================================================
# SATURATION ANALYSIS RESULT FOR SELECTED SYSTEM
# =========================================================
saturation_result = build_saturation_profile(system_df)

saturation_profile = saturation_result["profile"]
baseline_sensitivity = saturation_result["baseline_sensitivity"]
saturation_warning_ratio = saturation_result["warning_ratio"]
saturation_limit_ratio = saturation_result["saturation_ratio"]


# =========================================================
# TABS
# =========================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Tab 1: Historical Analysis",
    "🎯 Tab 2: SOP Recommendation",
    "🔬 Tab 3: Engineering Matrix",
    "🖨️ Tab 4: Master Shop Floor SOP"
])


# =========================================================
# TAB 1: HISTORICAL ANALYSIS
# =========================================================
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
        hovermode="closest"
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


# =========================================================
# TAB 2: SOP RECOMMENDATION
# =========================================================
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

                    ref_ratio_p90 = ref_data[
                        "Solvent_Ratio_Percent"
                    ].quantile(0.9)

                    ref_ratio_p95 = ref_data[
                        "Solvent_Ratio_Percent"
                    ].quantile(0.95)

                    ref_drop_p90 = ref_data["Delta_V"].quantile(0.9)
                    ref_drop_max = ref_data["Delta_V"].max()

                    dilution_base = order_weight + 120
                    required_ratio = required_drop / ref_sensitivity

                    recommended_solvent = (
                        dilution_base * (required_ratio / 100)
                    )

                    max_total_solvent = (
                        dilution_base * (ref_ratio_p90 / 100)
                    )

                    risk_status = ""
                    risk_color = ""
                    blocked = False
                    saturation_note = ""

                    # Existing P90 / P95 / Max Drop safety logic
                    if (
                        required_ratio > ref_ratio_p95
                        or required_drop > ref_drop_max
                    ):
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

                    # New saturation screening logic
                    if (
                        not pd.isna(saturation_limit_ratio)
                        and required_ratio >= saturation_limit_ratio
                    ):
                        risk_status = (
                            "🚨 SATURATION LIMIT REACHED: Historical data shows "
                            "very low dilution efficiency in this range."
                        )
                        risk_color = "red"
                        blocked = True

                        saturation_note = (
                            f"Required ratio: {required_ratio:.2f}% | "
                            f"Historical saturation limit: "
                            f"{saturation_limit_ratio:.2f}%"
                        )

                    elif (
                        not blocked
                        and not pd.isna(saturation_warning_ratio)
                        and required_ratio >= saturation_warning_ratio
                    ):
                        risk_status = (
                            "⚠️ DIMINISHING RETURNS WARNING: Historical dilution "
                            "efficiency has started declining."
                        )
                        risk_color = "orange"

                        saturation_note = (
                            f"Required ratio: {required_ratio:.2f}% | "
                            f"Diminishing-return threshold: "
                            f"{saturation_warning_ratio:.2f}%"
                        )

                    st.markdown(
                        f"### Assessment: "
                        f"<span style='color:{risk_color}'>{risk_status}</span>",
                        unsafe_allow_html=True
                    )

                    if saturation_note:
                        st.warning(
                            f"📉 Saturation screening: {saturation_note}"
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

                        col_r3.metric(
                            "Data Confidence",
                            conf_msg
                        )

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


# =========================================================
# TAB 3: ENGINEERING MATRIX
# =========================================================
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

    st.markdown("---")
    st.markdown("### 📉 Solvent Saturation / Diminishing Returns Analysis")

    st.markdown(
        "This analysis checks whether higher solvent ratios still deliver "
        "proportional viscosity reduction."
    )

    if pd.isna(baseline_sensitivity):
        st.warning(
            "⚠️ Insufficient zone-level data for saturation analysis. "
            "Each ratio zone needs at least 5 valid batches."
        )

    else:
        col_sat1, col_sat2, col_sat3 = st.columns(3)

        col_sat1.metric(
            "Baseline Sensitivity",
            f"{baseline_sensitivity:.2f} s/%"
        )

        col_sat2.metric(
            "Diminishing Returns Threshold",
            (
                f"{saturation_warning_ratio:.2f}%"
                if not pd.isna(saturation_warning_ratio)
                else "Not Detected"
            )
        )

        col_sat3.metric(
            "Saturation Limit",
            (
                f"{saturation_limit_ratio:.2f}%"
                if not pd.isna(saturation_limit_ratio)
                else "Not Detected"
            )
        )

        st.dataframe(
            saturation_profile,
            column_config={
                "Records": st.column_config.NumberColumn(format="%d"),
                "Ratio_Median": st.column_config.NumberColumn(
                    "Median Ratio (%)",
                    format="%.2f"
                ),
                "Ratio_Min": st.column_config.NumberColumn(
                    "Min Ratio (%)",
                    format="%.2f"
                ),
                "Ratio_Max": st.column_config.NumberColumn(
                    "Max Ratio (%)",
                    format="%.2f"
                ),
                "DeltaV_Median": st.column_config.NumberColumn(
                    "Median Delta V (s)",
                    format="%.2f"
                ),
                "Sensitivity_Median": st.column_config.NumberColumn(
                    "Median Sensitivity (s/%)",
                    format="%.2f"
                ),
                "Sensitivity_P25": st.column_config.NumberColumn(
                    "Sensitivity P25",
                    format="%.2f"
                ),
                "Sensitivity_P75": st.column_config.NumberColumn(
                    "Sensitivity P75",
                    format="%.2f"
                ),
                "Efficiency_vs_Baseline_%": st.column_config.NumberColumn(
                    "Efficiency vs Baseline (%)",
                    format="%.1f%%"
                )
            },
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# =========================================================
# =========================================================
# TAB 4: SHOP FLOOR QUICK SOP
# =========================================================
with tab4:
    st.markdown("### 🖨️ 現場快速加料SOP")

    st.warning(
        "操作順序：查詢相同條件 → 添加參考稀釋劑量 → 混合5分鐘 → "
        "量測黏度 → 與參考範圍比較。不得超過飽和停止添加量。"
    )

    st.caption(
        "註：系統內部計算已包含管線內120 kg運轉塗料；"
        "表中「訂單塗料重量」僅為本次訂單塗料重量。"
    )

    matrix_df = master_df.copy()

    # =====================================================
    # 1. ORDER PAINT WEIGHT RANGE
    # 塗料重量 = 訂單塗料重量
    # Operating base = 訂單塗料重量 + 120 kg line hold-up
    # =====================================================
    weight_bins = [0, 25, 50, 80, 120, 200, np.inf]

    weight_labels = [
        "0-25 kg",
        "26-50 kg",
        "51-80 kg",
        "81-120 kg",
        "121-200 kg",
        ">200 kg"
    ]

    matrix_df["Order_Paint_Weight_Range"] = pd.cut(
        matrix_df["塗料重量"],
        bins=weight_bins,
        labels=weight_labels,
        include_lowest=True,
        right=True
    )

    # =====================================================
    # 2. HISTORICAL LOOKUP TABLE
    # Same Resin + Vendor + Solvent + Initial Viscosity + Weight Range
    # =====================================================
    worker_sop = matrix_df.groupby(
        [
            "Resin",
            "Vendor",
            "Solvent_Type",
            "Initial_Viscosity_Zone",
            "Order_Paint_Weight_Range"
        ],
        observed=False
    ).agg(
        Valid_Batches=("塗料批號", "nunique"),

        Typical_Order_Paint_Weight=(
            "塗料重量",
            "median"
        ),

        Ref_Start_Visc=(
            "黏度(秒)",
            "median"
        ),

        Ref_Final_Visc=(
            "黏度(秒)_1",
            "median"
        ),

        Final_Visc_P25=(
            "黏度(秒)_1",
            lambda x: x.quantile(0.25)
        ),

        Final_Visc_P75=(
            "黏度(秒)_1",
            lambda x: x.quantile(0.75)
        ),

        # Direct historical kg addition
        Ref_Solvent_Add_kg=(
            "添加重量",
            "median"
        ),

        Median_Solvent_Ratio=(
            "Solvent_Ratio_Percent",
            "median"
        ),

        P90_Solvent_Ratio=(
            "Solvent_Ratio_Percent",
            lambda x: x.quantile(0.90)
        ),

        P95_Solvent_Ratio=(
            "Solvent_Ratio_Percent",
            lambda x: x.quantile(0.95)
        )
    ).reset_index()

    # Minimum records for worker reference
    worker_sop = worker_sop[
        worker_sop["Valid_Batches"] >= 5
    ].copy()

    if worker_sop.empty:
        st.warning(
            "無足夠歷史資料可建立現場SOP。每個條件組合至少需要5筆有效資料。"
        )
        st.stop()

    # =====================================================
    # 3. OPERATING BASE
    # =====================================================
    worker_sop["Operating_Dilution_Base"] = (
        worker_sop["Typical_Order_Paint_Weight"] + 120
    )

    # =====================================================
    # 4. SATURATION LIMITS BY SYSTEM
    # Resin + Vendor + Solvent
    # =====================================================
    saturation_summary = []

    system_keys = matrix_df[
        ["Resin", "Vendor", "Solvent_Type"]
    ].drop_duplicates()

    for _, system_row in system_keys.iterrows():

        resin_value = system_row["Resin"]
        vendor_value = system_row["Vendor"]
        solvent_value = system_row["Solvent_Type"]

        temp_system_df = matrix_df[
            (matrix_df["Resin"] == resin_value)
            & (matrix_df["Vendor"] == vendor_value)
            & (matrix_df["Solvent_Type"] == solvent_value)
        ].copy()

        temp_saturation = build_saturation_profile(temp_system_df)

        saturation_summary.append({
            "Resin": resin_value,
            "Vendor": vendor_value,
            "Solvent_Type": solvent_value,
            "Saturation_Warning_Ratio": temp_saturation["warning_ratio"],
            "Saturation_Stop_Ratio": temp_saturation["saturation_ratio"]
        })

    saturation_summary_df = pd.DataFrame(saturation_summary)

    worker_sop = worker_sop.merge(
        saturation_summary_df,
        on=["Resin", "Vendor", "Solvent_Type"],
        how="left"
    )

    # If saturation is not statistically detected:
    # P90 = warning guardrail
    # P95 = stop guardrail
    worker_sop["Warning_Ratio"] = (
        worker_sop["Saturation_Warning_Ratio"]
        .fillna(worker_sop["P90_Solvent_Ratio"])
    )

    worker_sop["Stop_Ratio"] = (
        worker_sop["Saturation_Stop_Ratio"]
        .fillna(worker_sop["P95_Solvent_Ratio"])
    )

    worker_sop["Stop_Ratio"] = np.maximum(
        worker_sop["Stop_Ratio"],
        worker_sop["Warning_Ratio"]
    )

    # Convert saturation ratio to kg
    worker_sop["Saturation_Warning_kg"] = (
        worker_sop["Operating_Dilution_Base"]
        * worker_sop["Warning_Ratio"]
        / 100
    )

    worker_sop["Saturation_Stop_kg"] = (
        worker_sop["Operating_Dilution_Base"]
        * worker_sop["Stop_Ratio"]
        / 100
    )

    # =====================================================
    # 5. SIMPLE HISTORICAL RESULT CHECK RULE
    # =====================================================
    worker_sop["Operation_Instruction"] = (
        "添加參考稀釋劑量 → 混合5分鐘 → 量測黏度"
    )

    worker_sop["Result_Check"] = (
        "量測結果應落於參考最終黏度範圍內"
    )

    # =====================================================
    # 6. FINAL OPERATOR TABLE
    # =====================================================
    worker_output = worker_sop[
        [
            "Resin",
            "Vendor",
            "Solvent_Type",
            "Initial_Viscosity_Zone",
            "Order_Paint_Weight_Range",
            "Valid_Batches",

            "Ref_Start_Visc",
            "Ref_Solvent_Add_kg",
            "Ref_Final_Visc",
            "Final_Visc_P25",
            "Final_Visc_P75",

            "Saturation_Warning_kg",
            "Saturation_Stop_kg",

            "Operation_Instruction",
            "Result_Check"
        ]
    ].copy()

    # Combine P25-P75 final viscosity range
    worker_output["Final_Viscosity_Reference_Range"] = (
        worker_output["Final_Visc_P25"].round(1).astype(str)
        + " - "
        + worker_output["Final_Visc_P75"].round(1).astype(str)
        + " 秒"
    )

    worker_output.drop(
        columns=[
            "Final_Visc_P25",
            "Final_Visc_P75"
        ],
        inplace=True
    )

    worker_output.rename(
        columns={
            "Resin": "樹脂種類",
            "Vendor": "塗料供應商",
            "Solvent_Type": "稀釋劑種類",
            "Initial_Viscosity_Zone": "初始黏度範圍",
            "Order_Paint_Weight_Range": "訂單塗料重量範圍",
            "Valid_Batches": "歷史批數",

            "Ref_Start_Visc": "參考起始黏度(秒)",
            "Ref_Solvent_Add_kg": "參考稀釋劑添加量(kg)",
            "Ref_Final_Visc": "參考最終黏度(秒)",
            "Final_Viscosity_Reference_Range": "最終黏度參考範圍",

            "Saturation_Warning_kg": "飽和警戒添加量(kg)",
            "Saturation_Stop_kg": "飽和停止添加量(kg)",

            "Operation_Instruction": "操作指示",
            "Result_Check": "結果判定"
        },
        inplace=True
    )

    worker_output = worker_output.sort_values(
        by=[
            "樹脂種類",
            "塗料供應商",
            "稀釋劑種類",
            "初始黏度範圍",
            "訂單塗料重量範圍"
        ]
    )

    st.dataframe(
        worker_output,
        column_config={
            "歷史批數": st.column_config.NumberColumn(
                format="%d"
            ),

            "參考起始黏度(秒)": st.column_config.NumberColumn(
                format="%.1f 秒"
            ),

            "參考稀釋劑添加量(kg)": st.column_config.NumberColumn(
                format="%.2f kg"
            ),

            "參考最終黏度(秒)": st.column_config.NumberColumn(
                format="%.1f 秒"
            ),

            "飽和警戒添加量(kg)": st.column_config.NumberColumn(
                format="%.2f kg"
            ),

            "飽和停止添加量(kg)": st.column_config.NumberColumn(
                format="%.2f kg"
            )
        },
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "判定原則：量測黏度高於參考範圍時，稀釋效果不足，追加前請確認；"
        "低於參考範圍時，停止追加。任何情況不得超過飽和停止添加量。"
    )

    csv_export = worker_output.to_csv(
        index=False
    ).encode("utf-8-sig")

    st.download_button(
        "下載現場快速SOP CSV",
        data=csv_export,
        file_name="現場黏度快速SOP.csv",
        mime="text/csv"
    )
