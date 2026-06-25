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
# TAB 4: PRINTED WORKER LOOKUP SOP
# =========================================================
with tab4:
    st.markdown("### 🖨️ Master Shop Floor SOP")

    st.markdown(
        """
        Bảng tra cứu nhanh cho công nhân không sử dụng dashboard.

        **Cách tra:** Chọn đúng Resin + Vendor + Solvent + khoảng độ nhớt ban đầu
        + khoảng khối lượng sơn đơn hàng.

        **Lưu ý quan trọng:** Cột `Order Paint Weight` chỉ là lượng sơn của đơn hàng.
        Hệ thống luôn tính thêm **120 kg sơn vận hành còn tồn trong line** khi quy đổi
        tỷ lệ dung môi sang kg.
        """
    )

    st.warning(
        """
        ⚠️ **Quy tắc bắt buộc**

        1. Chỉ thêm **Stage 1**, sau đó khuấy hoàn toàn tối thiểu 5 phút và đo lại độ nhớt.  
        2. Chỉ thêm Stage 2 khi độ nhớt sau đo vẫn lớn hơn USL.  
        3. Chỉ thêm Stage 3 khi được phép và tổng dung môi chưa vượt giới hạn Stop.  
        4. Khi đạt vùng Saturation / Stop Ratio: **dừng thêm dung môi và liên hệ Process Engineer**.
        """
    )

    st.info(
        """
        **Cơ sở tính toán**

        `Operating Dilution Base = Order Paint Weight + 120 kg line hold-up`

        `Typical Total Solvent = Operating Dilution Base × Median Historical Solvent Ratio`

        Các mức dung môi Stage 1 / 2 / 3 được giới hạn bởi vùng giảm hiệu suất
        và ngưỡng bão hòa đã được phân tích từ dữ liệu lịch sử.
        """
    )

    matrix_df = master_df.copy()

    # =====================================================
    # 1. ORDER PAINT WEIGHT RANGE
    # 塗料重量 = lượng sơn đơn hàng, chưa bao gồm 120 kg trong line
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
    # 2. WORKER LOOKUP BASE TABLE
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

        # 塗料重量 chỉ là khối lượng sơn đơn hàng
        Typical_Order_Paint_Weight=("塗料重量", "median"),

        # Độ nhớt sau pha lịch sử tham khảo
        Typical_Target_Visc=("黏度(秒)_1", "median"),

        # Tỷ lệ được tính theo Dilution_Base = 塗料重量 + 120
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
        ),

        Median_Viscosity_Drop=("Delta_V", "median"),
        P90_Viscosity_Drop=(
            "Delta_V",
            lambda x: x.quantile(0.90)
        ),
        Max_Viscosity_Drop=("Delta_V", "max")
    ).reset_index()

    # Giữ lại các nhóm có dữ liệu đủ dùng cho công nhân
    worker_sop = worker_sop[
        worker_sop["Valid_Batches"] >= 5
    ].copy()

    if worker_sop.empty:
        st.warning(
            "⚠️ Không có nhóm dữ liệu nào đủ tối thiểu 5 batch để tạo bảng SOP công nhân."
        )
        st.stop()

    # =====================================================
    # 3. OPERATING DILUTION BASE
    # Order Paint Weight + 120 kg paint remaining in line
    # =====================================================
    worker_sop["Operating_Dilution_Base"] = (
        worker_sop["Typical_Order_Paint_Weight"] + 120
    )

    # Quy đổi tỷ lệ dung môi lịch sử thành kg
    # Dùng Operating Dilution Base để đảm bảo luôn tính 120 kg line hold-up
    worker_sop["Typical_Total_Solvent_kg"] = (
        worker_sop["Operating_Dilution_Base"]
        * worker_sop["Median_Solvent_Ratio"]
        / 100
    )

    worker_sop["P90_Total_Solvent_kg"] = (
        worker_sop["Operating_Dilution_Base"]
        * worker_sop["P90_Solvent_Ratio"]
        / 100
    )

    worker_sop["P95_Total_Solvent_kg"] = (
        worker_sop["Operating_Dilution_Base"]
        * worker_sop["P95_Solvent_Ratio"]
        / 100
    )

    # =====================================================
    # 4. BUILD SATURATION THRESHOLD BY SYSTEM
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

    # Nếu chưa phát hiện saturation rõ ràng:
    # P90 = cảnh báo, P95 = dừng / cần phê duyệt kỹ sư
    worker_sop["Warning_Ratio"] = (
        worker_sop["Saturation_Warning_Ratio"]
        .fillna(worker_sop["P90_Solvent_Ratio"])
    )

    worker_sop["Stop_Ratio"] = (
        worker_sop["Saturation_Stop_Ratio"]
        .fillna(worker_sop["P95_Solvent_Ratio"])
    )

    # Bảo đảm Stop Ratio không nhỏ hơn Warning Ratio
    worker_sop["Stop_Ratio"] = np.maximum(
        worker_sop["Stop_Ratio"],
        worker_sop["Warning_Ratio"]
    )

    # =====================================================
    # 5. CONVERT SATURATION RATIO INTO MAXIMUM KG
    # =====================================================
    worker_sop["Warning_Max_Solvent_kg"] = (
        worker_sop["Operating_Dilution_Base"]
        * worker_sop["Warning_Ratio"]
        / 100
    )

    worker_sop["Stop_Max_Solvent_kg"] = (
        worker_sop["Operating_Dilution_Base"]
        * worker_sop["Stop_Ratio"]
        / 100
    )

    # Lượng lịch sử được phép dùng để lên kế hoạch:
    # Không vượt ngưỡng Warning ngay từ đầu.
    worker_sop["Safe_Planned_Total_kg"] = np.minimum(
        worker_sop["Typical_Total_Solvent_kg"],
        worker_sop["Warning_Max_Solvent_kg"]
    )

    # =====================================================
    # 6. STAGED ADDITION WITH SATURATION GUARDRAIL
    # =====================================================

    # Stage 1: 60% của lượng an toàn, không được vượt Warning Max
    worker_sop["Stage_1_Add_kg"] = np.minimum(
        worker_sop["Safe_Planned_Total_kg"] * 0.60,
        worker_sop["Warning_Max_Solvent_kg"]
    )

    # Stage 2: Chỉ được thêm đến ngưỡng Warning
    stage2_planned = worker_sop["Safe_Planned_Total_kg"] * 0.25
    stage2_remaining = (
        worker_sop["Warning_Max_Solvent_kg"]
        - worker_sop["Stage_1_Add_kg"]
    )

    worker_sop["Stage_2_Max_Add_kg"] = np.minimum(
        stage2_planned,
        stage2_remaining
    ).clip(lower=0)

    # Stage 3: chỉ được dùng khi đo lại vẫn > USL
    # Tổng Stage 1+2+3 tuyệt đối không vượt Stop Max.
    stage3_planned = worker_sop["Safe_Planned_Total_kg"] * 0.15
    stage3_remaining = (
        worker_sop["Stop_Max_Solvent_kg"]
        - worker_sop["Stage_1_Add_kg"]
        - worker_sop["Stage_2_Max_Add_kg"]
    )

    worker_sop["Stage_3_Max_Add_kg"] = np.minimum(
        stage3_planned,
        stage3_remaining
    ).clip(lower=0)

    worker_sop["Maximum_Allowed_Total_kg"] = (
        worker_sop["Stop_Max_Solvent_kg"]
    )

    # =====================================================
    # 7. SATURATION STATUS / INSTRUCTION
    # =====================================================
    worker_sop["Saturation_Control_Status"] = np.select(
        [
            worker_sop["Typical_Total_Solvent_kg"]
            >= worker_sop["Stop_Max_Solvent_kg"],

            worker_sop["Typical_Total_Solvent_kg"]
            >= worker_sop["Warning_Max_Solvent_kg"]
        ],
        [
            "🔴 STOP: Historical demand reaches saturation limit",
            "🟠 CAUTION: Historical demand enters diminishing-return zone"
        ],
        default="🟢 NORMAL: Historical demand within efficient operating zone"
    )

    worker_sop["Stage_1_Action"] = (
        "Add Stage 1 → Mix ≥5 min → Measure viscosity"
    )

    worker_sop["Stage_2_Condition"] = (
        "Only if measured viscosity remains above USL "
        "and total solvent stays ≤ Warning Max"
    )

    worker_sop["Stage_3_Condition"] = (
        "Only if still above USL after Stage 2; "
        "never exceed Stop Max"
    )

    worker_sop["Escalation_Rule"] = (
        "If viscosity is still above USL at Stop Max: "
        "STOP and contact Process Engineer"
    )

    # =====================================================
    # 8. FINAL WORKER SOP OUTPUT
    # =====================================================
    worker_output = worker_sop[
        [
            "Resin",
            "Vendor",
            "Solvent_Type",
            "Initial_Viscosity_Zone",
            "Order_Paint_Weight_Range",
            "Valid_Batches",

            "Typical_Order_Paint_Weight",
            "Operating_Dilution_Base",

            "Typical_Target_Visc",
            "Median_Viscosity_Drop",
            "P90_Viscosity_Drop",
            "Max_Viscosity_Drop",

            "Median_Solvent_Ratio",
            "Warning_Ratio",
            "Stop_Ratio",

            "Typical_Total_Solvent_kg",
            "Warning_Max_Solvent_kg",
            "Maximum_Allowed_Total_kg",

            "Stage_1_Add_kg",
            "Stage_1_Action",

            "Stage_2_Max_Add_kg",
            "Stage_2_Condition",

            "Stage_3_Max_Add_kg",
            "Stage_3_Condition",

            "Saturation_Control_Status",
            "Escalation_Rule"
        ]
    ].copy()

    worker_output.rename(
        columns={
            "Solvent_Type": "Solvent",
            "Initial_Viscosity_Zone": "Initial Viscosity Range",
            "Order_Paint_Weight_Range": "Order Paint Weight Range",
            "Valid_Batches": "Valid Batches",

            "Typical_Order_Paint_Weight": "Typical Order Paint Weight (kg)",
            "Operating_Dilution_Base": (
                "Operating Dilution Base (Order + 120 kg Line Hold-up)"
            ),

            "Typical_Target_Visc": "Typical After Viscosity (s)",
            "Median_Viscosity_Drop": "Median Viscosity Drop (s)",
            "P90_Viscosity_Drop": "P90 Viscosity Drop (s)",
            "Max_Viscosity_Drop": "Maximum Historical Drop (s)",

            "Median_Solvent_Ratio": "Median Solvent Ratio (%)",
            "Warning_Ratio": "Warning Ratio (%)",
            "Stop_Ratio": "Stop Ratio (%)",

            "Typical_Total_Solvent_kg": "Typical Planned Total Solvent (kg)",
            "Warning_Max_Solvent_kg": "Warning Max Total Solvent (kg)",
            "Maximum_Allowed_Total_kg": "Stop Max Total Solvent (kg)",

            "Stage_1_Add_kg": "Stage 1 Add (kg)",
            "Stage_1_Action": "Stage 1 Action",

            "Stage_2_Max_Add_kg": "Stage 2 Max Add (kg)",
            "Stage_2_Condition": "Stage 2 Condition",

            "Stage_3_Max_Add_kg": "Stage 3 Max Add (kg)",
            "Stage_3_Condition": "Stage 3 Condition",

            "Saturation_Control_Status": "Saturation Control",
            "Escalation_Rule": "Escalation Rule"
        },
        inplace=True
    )

    worker_output = worker_output.sort_values(
        by=[
            "Resin",
            "Vendor",
            "Solvent",
            "Initial Viscosity Range",
            "Order Paint Weight Range"
        ]
    )

    st.dataframe(
        worker_output,
        column_config={
            "Valid Batches": st.column_config.NumberColumn(
                format="%d"
            ),

            "Typical Order Paint Weight (kg)": st.column_config.NumberColumn(
                format="%.1f kg"
            ),

            "Operating Dilution Base (Order + 120 kg Line Hold-up)": (
                st.column_config.NumberColumn(
                    format="%.1f kg"
                )
            ),

            "Typical After Viscosity (s)": st.column_config.NumberColumn(
                format="%.1f s"
            ),

            "Median Viscosity Drop (s)": st.column_config.NumberColumn(
                format="%.1f s"
            ),

            "P90 Viscosity Drop (s)": st.column_config.NumberColumn(
                format="%.1f s"
            ),

            "Maximum Historical Drop (s)": st.column_config.NumberColumn(
                format="%.1f s"
            ),

            "Median Solvent Ratio (%)": st.column_config.NumberColumn(
                format="%.2f%%"
            ),

            "Warning Ratio (%)": st.column_config.NumberColumn(
                format="%.2f%%"
            ),

            "Stop Ratio (%)": st.column_config.NumberColumn(
                format="%.2f%%"
            ),

            "Typical Planned Total Solvent (kg)": st.column_config.NumberColumn(
                format="%.2f kg"
            ),

            "Warning Max Total Solvent (kg)": st.column_config.NumberColumn(
                format="%.2f kg"
            ),

            "Stop Max Total Solvent (kg)": st.column_config.NumberColumn(
                format="%.2f kg"
            ),

            "Stage 1 Add (kg)": st.column_config.NumberColumn(
                format="%.2f kg"
            ),

            "Stage 2 Max Add (kg)": st.column_config.NumberColumn(
                format="%.2f kg"
            ),

            "Stage 3 Max Add (kg)": st.column_config.NumberColumn(
                format="%.2f kg"
            )
        },
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")
    st.markdown("### 📘 Manual Calculation Note")

    st.markdown(
        """
        **1. Operating Dilution Base**  
        `= Order Paint Weight + 120 kg line hold-up`

        **2. Typical Planned Total Solvent**  
        `= Operating Dilution Base × Median Historical Solvent Ratio`

        **3. Warning Maximum Total Solvent**  
        `= Operating Dilution Base × Warning Ratio`

        **4. Stop Maximum Total Solvent**  
        `= Operating Dilution Base × Stop Ratio`

        **5. Staged Addition**  
        `Stage 1 = 60% of safe planned solvent`  
        `Stage 2 = up to 25%, only below Warning Max`  
        `Stage 3 = up to 15%, only below Stop Max`

        **Important:** Khi đã đạt Stop Max mà độ nhớt vẫn vượt USL, không được tiếp tục
        thêm dung môi. Cần kiểm tra nhiệt độ, thời gian khuấy, batch sơn, dung môi,
        điều kiện line hoặc liên hệ Process Engineer.
        """
    )

    csv_export = worker_output.to_csv(
        index=False
    ).encode("utf-8-sig")

    st.download_button(
        "📥 Download Printable Worker SOP (CSV)",
        data=csv_export,
        file_name="Master_Shop_Floor_Viscosity_SOP.csv",
        mime="text/csv"
    )
