import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt

from io import BytesIO
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT


# =========================================================
# EXPORT HISTORICAL CHART TO WORD
# =========================================================
def export_chart_to_word(
    selected_resin,
    selected_pos,
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
        f"Position: {selected_pos} | "
        f"Vendor: {selected_vendor} | "
        f"Solvent Type: {selected_solvent}"
    )
    subtitle_run.font.size = Pt(10)

    doc.add_paragraph("")

    table = doc.add_table(rows=2, cols=5)
    table.style = "Table Grid"

    headers = [
        "Valid Paint Batches",
        "Valid Adjustment Records",
        "Median Sensitivity",
        "P10-P90 Ratio Range",
        "Maximum Viscosity Drop"
    ]

    values = [
        f"{system_df['塗料批號'].nunique():,}",
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
        fig, ax = plt.subplots(figsize=(10.2, 5.2))

        for _, row in system_df.iterrows():
            ratio = row["Solvent_Ratio_Percent"]
            visc_before = row["黏度(秒)"]
            visc_after = row["黏度(秒)_1"]

            ax.plot(
                [ratio, ratio],
                [visc_before, visc_after],
                linestyle=":",
                linewidth=0.8,
                color="lightgray",
                zorder=1
            )

        ax.scatter(
            system_df["Solvent_Ratio_Percent"],
            system_df["黏度(秒)"],
            s=35,
            color="#ED7D31",
            edgecolors="white",
            linewidths=0.5,
            label="Initial Viscosity (Before)",
            zorder=3
        )

        ax.scatter(
            system_df["Solvent_Ratio_Percent"],
            system_df["黏度(秒)_1"],
            s=35,
            color="#4472C4",
            edgecolors="white",
            linewidths=0.5,
            label="Final Viscosity (After)",
            zorder=3
        )

        ax.set_title(
            "Viscosity Transition by Solvent Ratio\n"
            f"Resin: {selected_resin} | Position: {selected_pos} | "
            f"Vendor: {selected_vendor} | Solvent: {selected_solvent}",
            fontsize=14,
            fontweight="bold",
            pad=16
        )

        ax.set_xlabel("Solvent Blending Ratio (%)", fontsize=10)
        ax.set_ylabel("Viscosity (seconds)", fontsize=10)

        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)

        ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, 1.02),
            ncol=2,
            frameon=False
        )

        plt.tight_layout()

        chart_stream = BytesIO()
        fig.savefig(chart_stream, format="png", dpi=260, bbox_inches="tight")
        chart_stream.seek(0)
        plt.close(fig)

        chart_paragraph = doc.add_paragraph()
        chart_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        chart_paragraph.add_run().add_picture(chart_stream, width=Inches(9.6))

    except Exception as e:
        error_paragraph = doc.add_paragraph()
        error_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        error_run = error_paragraph.add_run(f"\n[CHART EXPORT FAILED]\n{str(e)}")
        error_run.bold = True

    note = doc.add_paragraph()
    note_run = note.add_run(
        "Note: Orange points represent viscosity before solvent addition. "
        "Blue points represent viscosity after solvent addition. "
        "The dotted line connects the same adjustment record."
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

    if "塗裝位置" not in data.columns:
        data["塗裝位置"] = "Unknown"

    pos_mapping = {
        "TP": "Primer", "正底漆": "Primer",
        "BP": "Primer", "背底漆": "Primer",
        "TF": "Top Finish", "正面漆": "Top Finish",
        "BF": "Back Finish", "背面漆": "Back Finish"
    }

    data["Position_UI"] = (
        data["塗裝位置"]
        .map(pos_mapping)
        .fillna(data["塗裝位置"])
    )

    data = data[
        (data["添加重量"] > 0)
        & (data["塗料重量"] > 0)
        & (data["黏度(秒)"] > data["黏度(秒)_1"])
        & (data["Resin"].notna())
        & (data["Position_UI"].notna())
        & (data["Vendor"].notna())
        & (data["Solvent_Type"].notna())
    ]

    if data.empty:
        return data

    data["Delta_V"] = data["黏度(秒)"] - data["黏度(秒)_1"]
    data = data[data["Delta_V"] > 0]

    if data.empty:
        return data

    data["Dilution_Base"] = data["塗料重量"]

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
            ["Resin", "Position_UI", "Vendor", "Solvent_Type"]
        )["塗料批號"]
        .transform("nunique")
    )

    data = data[system_batch_counts >= 30].copy()

    if data.empty:
        return data

    q01 = (
        data.groupby(
            ["Resin", "Position_UI", "Vendor", "Solvent_Type"]
        )["Sensitivity"]
        .transform(lambda x: x.quantile(0.01))
    )

    q99 = (
        data.groupby(
            ["Resin", "Position_UI", "Vendor", "Solvent_Type"]
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
        Adjustment_Records=("塗料批號", "size"),
        Paint_Batches=("塗料批號", "nunique"),
        Ratio_Median=("Solvent_Ratio_Percent", "median"),
        Ratio_Min=("Solvent_Ratio_Percent", "min"),
        Ratio_Max=("Solvent_Ratio_Percent", "max"),
        DeltaV_Median=("Delta_V", "median"),
        Sensitivity_Median=("Sensitivity", "median"),
        Sensitivity_P25=("Sensitivity", lambda x: x.quantile(0.25)),
        Sensitivity_P75=("Sensitivity", lambda x: x.quantile(0.75))
    ).reset_index()

    valid_profile = profile[
        (profile["Adjustment_Records"] >= 5)
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
                row["Adjustment_Records"] < 5
                or pd.isna(row["Efficiency_vs_Baseline_%"])
            ):
                continue

            efficiency = row["Efficiency_vs_Baseline_%"]

            if efficiency <= 50:
                profile.loc[idx, "Saturation_Status"] = "🔴 Saturation Zone"

                if pd.isna(saturation_ratio):
                    saturation_ratio = row["Ratio_Min"]

            elif efficiency <= 70:
                profile.loc[idx, "Saturation_Status"] = "🟠 Diminishing Returns"

                if pd.isna(warning_ratio):
                    warning_ratio = row["Ratio_Min"]

            else:
                profile.loc[idx, "Saturation_Status"] = "🟢 Normal Efficiency"

    return {
        "profile": profile,
        "baseline_sensitivity": baseline_sensitivity,
        "warning_ratio": warning_ratio,
        "saturation_ratio": saturation_ratio
    }


# =========================================================
# =========================================================
# LOAD DATA
# =========================================================
group_a_data = st.session_state.get("group_a_data")

if group_a_data is None or group_a_data.empty:
    st.warning("⚠️ 請先於首頁重新上傳原始資料檔案。")
    st.stop()

master_df = process_data(group_a_data)

# process_data có thể trả về空 DataFrame，
# 若所有資料未達 n ≥ 30 或被過濾，避免後續 KeyError
if master_df is None or master_df.empty:
    st.warning(
        "⚠️ 無可用歷史資料。可能原因：\n\n"
        "1. 資料未達系統門檻（至少 30 個不同塗料批號）。\n\n"
        "2. 資料在有效性篩選或極端值篩選後已無剩餘紀錄。\n\n"
        "3. 請按首頁「Clear Data & Upload New File」後重新上傳。"
    )
    st.stop()

required_columns = [
    "Resin",
    "Position_UI",
    "Vendor",
    "Solvent_Type",
    "塗料批號",
    "黏度(秒)",
    "黏度(秒)_1",
    "添加重量",
    "塗料重量"
]

missing_columns = [
    col for col in required_columns
    if col not in master_df.columns
]

if missing_columns:
    st.error(
        "⚠️ 資料欄位不足："
        + "、".join(missing_columns)
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

col_f1, col_f2, col_f3, col_f4 = st.columns(4)

with col_f1:
    selected_resin = st.selectbox(
        "Select Resin:",
        sorted(master_df["Resin"].unique()),
        on_change=reset_execution_states
    )

with col_f2:
    selected_pos = st.selectbox(
        "Select Position:",
        sorted(
            master_df[
                master_df["Resin"] == selected_resin
            ]["Position_UI"].unique()
        ),
        on_change=reset_execution_states
    )

with col_f3:
    selected_vendor = st.selectbox(
        "Select Vendor:",
        sorted(
            master_df[
                (master_df["Resin"] == selected_resin)
                & (master_df["Position_UI"] == selected_pos)
            ]["Vendor"].unique()
        ),
        on_change=reset_execution_states
    )

with col_f4:
    selected_solvent = st.selectbox(
        "Select Solvent Type:",
        sorted(
            master_df[
                (master_df["Resin"] == selected_resin)
                & (master_df["Position_UI"] == selected_pos)
                & (master_df["Vendor"] == selected_vendor)
            ]["Solvent_Type"].unique()
        ),
        on_change=reset_execution_states
    )

system_df = master_df[
    (master_df["Resin"] == selected_resin)
    & (master_df["Position_UI"] == selected_pos)
    & (master_df["Vendor"] == selected_vendor)
    & (master_df["Solvent_Type"] == selected_solvent)
]

if system_df.empty:
    st.error("No valid historical data available for this configuration.")
    st.stop()


# =========================================================
# SATURATION ANALYSIS RESULT
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

    unique_batch_count = system_df["塗料批號"].nunique()
    adjustment_record_count = len(system_df)

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Valid Paint Batches (n ≥ 30)",
        f"{unique_batch_count:,}",
        help="Number of unique paint batch numbers (塗料批號)."
    )

    c2.metric(
        "Valid Adjustment Records",
        f"{adjustment_record_count:,}",
        help=(
            "Each record represents one valid solvent adjustment. "
            "One paint batch may have multiple adjustment records."
        )
    )

    c3.metric(
        "Median Sensitivity",
        f"{system_df['Sensitivity'].median():.2f} s/%"
    )

    c4.metric(
        "P10 - P90 Ratio Range",
        f"{system_df['Solvent_Ratio_Percent'].quantile(0.1):.1f}% - "
        f"{system_df['Solvent_Ratio_Percent'].quantile(0.9):.1f}%"
    )

    c5.metric(
        "Max Drop (Delta V)",
        f"{system_df['Delta_V'].max():.1f} s"
    )

    fig_scatter = go.Figure()
    plot_df = system_df.reset_index(drop=True).copy()

    for _, row in plot_df.iterrows():
        fig_scatter.add_trace(
            go.Scatter(
                x=[
                    row["Solvent_Ratio_Percent"],
                    row["Solvent_Ratio_Percent"]
                ],
                y=[
                    row["黏度(秒)"],
                    row["黏度(秒)_1"]
                ],
                mode="lines",
                line=dict(
                    color="rgba(120,120,120,0.35)",
                    width=1.4,
                    dash="dot"
                ),
                customdata=[
                    [row["塗料批號"], row["Delta_V"]],
                    [row["塗料批號"], row["Delta_V"]]
                ],
                hovertemplate=(
                    "<b>Batch: %{customdata[0]}</b><br>"
                    "Viscosity Drop: %{customdata[1]:.1f}s"
                    "<extra></extra>"
                ),
                showlegend=False
            )
        )

    fig_scatter.add_trace(
        go.Scatter(
            x=plot_df["Solvent_Ratio_Percent"],
            y=plot_df["黏度(秒)"],
            mode="markers",
            name="Initial Viscosity (Before)",
            marker=dict(
                color="#ED7D31",
                size=8,
                opacity=0.85,
                line=dict(width=0.8, color="white")
            ),
            customdata=plot_df[
                [
                    "黏度(秒)_1",
                    "Delta_V",
                    "Initial_Viscosity_Zone",
                    "塗料批號"
                ]
            ].values,
            hovertemplate=(
                "<b>Batch: %{customdata[3]}</b><br>"
                "<b>Zone: %{customdata[2]}</b><br>"
                "Solvent Ratio: %{x:.2f}%<br>"
                "Initial Visc (Before): %{y:.1f}s<br>"
                "Final Visc (After): %{customdata[0]:.1f}s<br>"
                "Viscosity Drop (Delta V): %{customdata[1]:.1f}s"
                "<extra></extra>"
            )
        )
    )

    fig_scatter.add_trace(
        go.Scatter(
            x=plot_df["Solvent_Ratio_Percent"],
            y=plot_df["黏度(秒)_1"],
            mode="markers",
            name="Final Viscosity (After)",
            marker=dict(
                color="#4472C4",
                size=8,
                opacity=0.85,
                line=dict(width=0.8, color="white")
            ),
            customdata=plot_df[
                [
                    "黏度(秒)",
                    "Delta_V",
                    "Initial_Viscosity_Zone",
                    "塗料批號"
                ]
            ].values,
            hovertemplate=(
                "<b>Batch: %{customdata[3]}</b><br>"
                "<b>Zone: %{customdata[2]}</b><br>"
                "Solvent Ratio: %{x:.2f}%<br>"
                "Initial Visc (Before): %{customdata[0]:.1f}s<br>"
                "Final Visc (After): %{y:.1f}s<br>"
                "Viscosity Drop (Delta V): %{customdata[1]:.1f}s"
                "<extra></extra>"
            )
        )
    )

    chart_title = (
        f"Viscosity Transition by Solvent Ratio<br>"
        f"<sup>Resin: {selected_resin} | Position: {selected_pos} | "
        f"Vendor: {selected_vendor} | Solvent: {selected_solvent}</sup>"
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
        selected_resin=selected_resin,
        selected_pos=selected_pos,
        selected_vendor=selected_vendor,
        selected_solvent=selected_solvent,
        system_df=system_df
    )

    file_name = (
        f"Viscosity_Transition_"
        f"{selected_resin}_{selected_pos}_{selected_vendor}_{selected_solvent}.docx"
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

                    dilution_base = order_weight
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
                            "sys_pos": selected_pos,
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
        "Filtered by selected Resin, Position & Vendor."
    )

    def generate_matrix(df):
        grouped = df.groupby(
            "Initial_Viscosity_Zone",
            observed=False
        ).agg(
            Adjustment_Records=("塗料批號", "size"),
            Paint_Batches=("塗料批號", "nunique"),
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
            "Adjustment_Records": st.column_config.NumberColumn(
                "有效調整紀錄數",
                format="%d"
            ),
            "Paint_Batches": st.column_config.NumberColumn(
                "涉及塗料批號數",
                format="%d"
            ),
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
            "Each ratio zone needs at least 5 valid adjustment records."
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
                "Adjustment_Records": st.column_config.NumberColumn(
                    "有效調整紀錄數",
                    format="%d"
                ),
                "Paint_Batches": st.column_config.NumberColumn(
                    "涉及塗料批號數",
                    format="%d"
                ),
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
# TAB 4: MASTER SHOP FLOOR REFERENCE TABLE
# =========================================================
with tab4:
    st.markdown("### 🖨️ 現場歷史加料參考表")

    st.warning(
        "依相同條件查詢 → 添加參考稀釋劑量 → 混合5分鐘 → 量測黏度。"
        "不得超過飽和停止比例。"
    )

    st.caption(
        "註：稀釋劑添加比例計算基準為實際塗料重量，"
        "不包含管線內運轉塗料。"
    )

    matrix_df = master_df.copy()

    if matrix_df.empty:
        st.warning("無可用歷史資料。")
        st.stop()

    def create_worker_viscosity_zone(df):
        temp_df = df.copy()

        group_cols = [
            "Resin",
            "Position_UI",
            "Vendor",
            "Solvent_Type"
        ]

        system_max_visc = (
            temp_df.groupby(group_cols)["黏度(秒)"]
            .transform("max")
        )

        def base_zone(visc):
            if visc <= 70:
                return "<=70"
            elif visc <= 90:
                return "71-90"
            elif visc <= 110:
                return "91-110"
            elif visc <= 130:
                return "111-130"
            else:
                return ">130"

        temp_df["Worker_Viscosity_Zone"] = (
            temp_df["黏度(秒)"]
            .apply(base_zone)
        )

        high_visc_mask = temp_df["黏度(秒)"] > 130

        temp_df.loc[
            high_visc_mask,
            "Worker_Viscosity_Zone"
        ] = (
            "130-"
            + system_max_visc.loc[high_visc_mask]
            .round(1)
            .astype(str)
        )

        return temp_df

    matrix_df = create_worker_viscosity_zone(matrix_df)

    def format_actual_range(p25, p75):
        if pd.isna(p25) or pd.isna(p75):
            return "-"

        p25 = round(float(p25), 1)
        p75 = round(float(p75), 1)

        if abs(p25 - p75) < 0.05:
            return f"{p25:.1f}"

        return f"{p25:.1f} - {p75:.1f}"

    worker_sop = matrix_df.groupby(
        [
            "Resin",
            "Position_UI",
            "Vendor",
            "Solvent_Type",
            "Worker_Viscosity_Zone"
        ],
        observed=False
    ).agg(
        Adjustment_Records=("塗料批號", "size"),

        History_Batches=("塗料批號", "nunique"),

        Ref_Start_Visc=(
            "黏度(秒)",
            "median"
        ),

        Ref_Paint_Weight_kg=(
            "塗料重量",
            "median"
        ),

        Ref_Solvent_Add_kg=(
            "添加重量",
            "median"
        ),

        Ref_Solvent_Ratio=(
            "Solvent_Ratio_Percent",
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

        Ratio_P90=(
            "Solvent_Ratio_Percent",
            lambda x: x.quantile(0.90)
        ),

        Ratio_P95=(
            "Solvent_Ratio_Percent",
            lambda x: x.quantile(0.95)
        )
    ).reset_index()

    # Only show zones with at least 5 valid adjustment records
    worker_sop = worker_sop[
        worker_sop["Adjustment_Records"] >= 5
    ].copy()

    if worker_sop.empty:
        st.warning(
            "無足夠歷史資料可建立現場參考表。"
            "每個條件組合至少需要5筆有效調整紀錄。"
        )
        st.stop()

    worker_sop["Final_Visc_P25_P75"] = worker_sop.apply(
        lambda row: format_actual_range(
            row["Final_Visc_P25"],
            row["Final_Visc_P75"]
        ),
        axis=1
    )

    saturation_summary = []

    system_keys = matrix_df[
        [
            "Resin",
            "Position_UI",
            "Vendor",
            "Solvent_Type"
        ]
    ].drop_duplicates()

    for _, system_row in system_keys.iterrows():
        resin_value = system_row["Resin"]
        pos_value = system_row["Position_UI"]
        vendor_value = system_row["Vendor"]
        solvent_value = system_row["Solvent_Type"]

        temp_system_df = matrix_df[
            (matrix_df["Resin"] == resin_value)
            & (matrix_df["Position_UI"] == pos_value)
            & (matrix_df["Vendor"] == vendor_value)
            & (matrix_df["Solvent_Type"] == solvent_value)
        ].copy()

        temp_saturation = build_saturation_profile(temp_system_df)

        saturation_summary.append({
            "Resin": resin_value,
            "Position_UI": pos_value,
            "Vendor": vendor_value,
            "Solvent_Type": solvent_value,
            "Saturation_Warning_Ratio": temp_saturation["warning_ratio"],
            "Saturation_Stop_Ratio": temp_saturation["saturation_ratio"]
        })

    saturation_summary_df = pd.DataFrame(saturation_summary)

    worker_sop = worker_sop.merge(
        saturation_summary_df,
        on=[
            "Resin",
            "Position_UI",
            "Vendor",
            "Solvent_Type"
        ],
        how="left"
    )

    worker_sop["Saturation_Warning_Ratio"] = (
        worker_sop["Saturation_Warning_Ratio"]
        .fillna(worker_sop["Ratio_P90"])
    )

    worker_sop["Saturation_Stop_Ratio"] = (
        worker_sop["Saturation_Stop_Ratio"]
        .fillna(worker_sop["Ratio_P95"])
    )

    worker_sop["Saturation_Stop_Ratio"] = np.maximum(
        worker_sop["Saturation_Stop_Ratio"],
        worker_sop["Saturation_Warning_Ratio"]
    )

    worker_sop["塗裝位置"] = worker_sop["Position_UI"].map({
        "Primer": "底漆 (P)",
        "Top Finish": "正面漆 (TF)",
        "Back Finish": "背面漆 (BF)"
    }).fillna(worker_sop["Position_UI"])

    worker_output = worker_sop[
        [
            "Resin",
            "塗裝位置",
            "Vendor",
            "Solvent_Type",
            "Worker_Viscosity_Zone",
            "Adjustment_Records",
            "History_Batches",
            "Ref_Start_Visc",
            "Ref_Paint_Weight_kg",
            "Ref_Solvent_Add_kg",
            "Ref_Solvent_Ratio",
            "Final_Visc_P25_P75",
            "Saturation_Warning_Ratio",
            "Saturation_Stop_Ratio"
        ]
    ].copy()

    worker_output.rename(
        columns={
            "Resin": "樹脂種類",
            "Vendor": "塗料供應商",
            "Solvent_Type": "稀釋劑種類",
            "Worker_Viscosity_Zone": "初始黏度區間",
            "Adjustment_Records": "有效調整紀錄數",
            "History_Batches": "涉及塗料批號數",
            "Ref_Start_Visc": "參考起始黏度",
            "Ref_Paint_Weight_kg": "參考塗料使用量",
            "Ref_Solvent_Add_kg": "參考稀釋劑添加量",
            "Ref_Solvent_Ratio": "參考稀釋劑添加比例",
            "Final_Visc_P25_P75": "歷史最終黏度範圍",
            "Saturation_Warning_Ratio": "飽和警戒比例",
            "Saturation_Stop_Ratio": "飽和停止比例"
        },
        inplace=True
    )

    def get_zone_order(zone):
        zone = str(zone)

        if zone.startswith("<=70"):
            return 1
        elif zone.startswith("71-90"):
            return 2
        elif zone.startswith("91-110"):
            return 3
        elif zone.startswith("111-130"):
            return 4
        elif zone.startswith("130-"):
            return 5

        return 99

    worker_output["_zone_order"] = (
        worker_output["初始黏度區間"]
        .apply(get_zone_order)
    )

    worker_output = worker_output.sort_values(
        by=[
            "樹脂種類",
            "塗裝位置",
            "塗料供應商",
            "稀釋劑種類",
            "_zone_order"
        ]
    ).drop(columns="_zone_order")

    st.dataframe(
        worker_output,
        column_config={
            "初始黏度區間": st.column_config.TextColumn(
                "初始黏度區間 (秒)"
            ),

            "有效調整紀錄數": st.column_config.NumberColumn(
                "有效調整紀錄數",
                format="%d"
            ),

            "涉及塗料批號數": st.column_config.NumberColumn(
                "涉及塗料批號數",
                format="%d"
            ),

            "參考起始黏度": st.column_config.NumberColumn(
                "參考起始黏度 (秒)",
                format="%.1f"
            ),

            "參考塗料使用量": st.column_config.NumberColumn(
                "參考塗料使用量 (kg)",
                format="%.1f"
            ),

            "參考稀釋劑添加量": st.column_config.NumberColumn(
                "參考稀釋劑添加量 (kg)",
                format="%.1f"
            ),

            "參考稀釋劑添加比例": st.column_config.NumberColumn(
                "參考稀釋劑添加比例 (%)",
                format="%.2f"
            ),

            "歷史最終黏度範圍": st.column_config.TextColumn(
                "歷史最終黏度範圍 (秒, P25–P75)"
            ),

            "飽和警戒比例": st.column_config.NumberColumn(
                "飽和警戒比例 (%)",
                format="%.2f"
            ),

            "飽和停止比例": st.column_config.NumberColumn(
                "飽和停止比例 (%)",
                format="%.2f"
            )
        },
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "「有效調整紀錄數」為實際用於計算中位數、P90/P95的調整資料筆數；"
        "「涉及塗料批號數」為這些紀錄涵蓋的不同塗料批號數。"
    )

    st.caption(
        "「歷史最終黏度範圍」為相同條件下歷史最終黏度的中間50%分布，"
        "僅供現場調整參考，非產品規格上下限。"
    )

    st.caption(
        "「130–Max」表示該樹脂、塗裝位置、供應商及稀釋劑組合中，"
        "歷史實際出現的最高初始黏度範圍；"
        "飽和停止比例仍以歷史效率分析或P95作為安全限制。"
    )

    csv_export = worker_output.to_csv(
        index=False
    ).encode("utf-8-sig")

    st.download_button(
        label="下載現場歷史加料參考表 CSV",
        data=csv_export,
        file_name="現場歷史加料參考表.csv",
        mime="text/csv"
    )
