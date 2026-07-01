import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import matplotlib.pyplot as plt

from io import BytesIO
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT


# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="Viscosity Optimization System",
    page_icon="⚙️",
    layout="wide"
)


# =========================================================
# CONSTANTS
# =========================================================
CORE_REQUIRED_COLUMNS = [
    "塗料批號",
    "塗料編號",
    "黏度(秒)",
    "稀釋劑",
    "黏度(秒)_1",
    "添加重量",
    "塗料重量",
    "塗裝位置"
]

SYSTEM_GROUP_COLS = [
    "Resin",
    "Position_UI",
    "Vendor",
    "Solvent_Type"
]

OUTLIER_GROUP_COLS = [
    "Resin",
    "Position_UI",
    "Vendor",
    "Solvent_Type",
    "Initial_Viscosity_Zone"
]


# =========================================================
# HELPER FUNCTIONS
# =========================================================
def assign_viscosity_zone(viscosity):
    if pd.isna(viscosity):
        return "Unknown"

    if viscosity <= 70:
        return "<=70 s"
    elif viscosity <= 90:
        return "71-90 s"
    elif viscosity <= 110:
        return "91-110 s"
    elif viscosity <= 130:
        return "111-130 s"
    else:
        return ">130 s"


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
    elif zone.startswith(">130"):
        return 5

    return 99


def get_data_status(record_count, batch_count):
    if record_count >= 30 and batch_count >= 10:
        return "🟢 可作為標準SOP"

    if record_count >= 10 and batch_count >= 5:
        return "🟡 僅供現場參考"

    return "🔴 資料不足，不建議自動計算"


def get_data_status_short(record_count, batch_count):
    if record_count >= 30 and batch_count >= 10:
        return "Standard SOP"

    if record_count >= 10 and batch_count >= 5:
        return "Reference Only"

    return "Insufficient Data"


def reset_execution_states():
    st.session_state["exec_curr_visc"] = 0.0
    st.session_state["exec_lsl"] = 0.0
    st.session_state["exec_usl"] = 0.0
    st.session_state["exec_order_weight"] = 0.0
    st.session_state["calculation_done"] = False


# =========================================================
# DATA PROCESSING
# =========================================================
@st.cache_data
def process_data(df):
    data = df.copy()

    if data.empty:
        return data

    # -----------------------------------------------------
    # REQUIRED COLUMN CHECK
    # -----------------------------------------------------
    missing_cols = [
        col for col in CORE_REQUIRED_COLUMNS
        if col not in data.columns
    ]

    if missing_cols:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(missing_cols)
        )

    # -----------------------------------------------------
    # STANDARDIZE TEXT COLUMNS
    # -----------------------------------------------------
    text_cols = [
        "塗料批號",
        "塗料編號",
        "稀釋劑",
        "塗裝位置"
    ]

    for col in text_cols:
        data[col] = data[col].astype(str).str.strip()

    # Keep solvent field consistent
    data["Solvent_Type"] = data["稀釋劑"].astype(str).str.strip()

    # -----------------------------------------------------
    # POSITION MAPPING
    # Keep TP / BP / TF / BF separate
    # -----------------------------------------------------
    position_map = {
        "TP": "正底漆 (TP)",
        "正底漆": "正底漆 (TP)",

        "BP": "背底漆 (BP)",
        "背底漆": "背底漆 (BP)",

        "TF": "正面漆 (TF)",
        "正面漆": "正面漆 (TF)",

        "BF": "背面漆 (BF)",
        "背面漆": "背面漆 (BF)"
    }

    data["Position_UI"] = (
        data["塗裝位置"]
        .map(position_map)
        .fillna(data["塗裝位置"])
    )

    # -----------------------------------------------------
    # ENSURE Resin / Vendor EXIST
    # These should normally be created in load_data()
    # -----------------------------------------------------
    if "Resin" not in data.columns:
        data["Resin"] = "Unknown"

    if "Vendor" not in data.columns:
        data["Vendor"] = "Unknown"

    data["Resin"] = data["Resin"].astype(str).str.strip()
    data["Vendor"] = data["Vendor"].astype(str).str.strip()

    # -----------------------------------------------------
    # NUMERIC CONVERSION
    # -----------------------------------------------------
    numeric_cols = [
        "黏度(秒)",
        "黏度(秒)_1",
        "添加重量",
        "塗料重量"
    ]

    for col in numeric_cols:
        data[col] = pd.to_numeric(
            data[col],
            errors="coerce"
        )

    # -----------------------------------------------------
    # BASIC VALID RECORD FILTER
    # Each row remains one actual adjustment record.
    # No grouping by paint batch.
    # -----------------------------------------------------
    data = data[
        (data["添加重量"] > 0)
        & (data["塗料重量"] > 0)
        & (data["黏度(秒)"].notna())
        & (data["黏度(秒)_1"].notna())
        & (data["黏度(秒)"] > data["黏度(秒)_1"])
        & (data["Solvent_Type"].notna())
        & (data["Solvent_Type"] != "")
        & (data["Resin"].notna())
        & (data["Vendor"].notna())
        & (data["Position_UI"].notna())
    ].copy()

    if data.empty:
        return data

    # -----------------------------------------------------
    # CORE CALCULATIONS
    # -----------------------------------------------------
    data["Delta_V"] = (
        data["黏度(秒)"]
        - data["黏度(秒)_1"]
    )

    data["Solvent_Ratio_Percent"] = (
        data["添加重量"]
        / data["塗料重量"]
    ) * 100

    data["Sensitivity"] = (
        data["Delta_V"]
        / data["Solvent_Ratio_Percent"].replace(0, np.nan)
    )

    data = data[
        data["Sensitivity"].notna()
        & np.isfinite(data["Sensitivity"])
        & (data["Sensitivity"] > 0)
    ].copy()

    if data.empty:
        return data

    # -----------------------------------------------------
    # INITIAL VISCOSITY ZONE
    # -----------------------------------------------------
    data["Initial_Viscosity_Zone"] = (
        data["黏度(秒)"]
        .apply(assign_viscosity_zone)
    )

    # -----------------------------------------------------
    # RECORD-LEVEL OUTLIER CONTROL
    # Only apply P1-P99 if zone has >=20 records.
    # Small groups are kept intact.
    # -----------------------------------------------------
    zone_record_count = (
        data.groupby(OUTLIER_GROUP_COLS)["塗料批號"]
        .transform("size")
    )

    q01 = (
        data.groupby(OUTLIER_GROUP_COLS)["Sensitivity"]
        .transform(lambda x: x.quantile(0.01))
    )

    q99 = (
        data.groupby(OUTLIER_GROUP_COLS)["Sensitivity"]
        .transform(lambda x: x.quantile(0.99))
    )

    use_outlier_filter = zone_record_count >= 20

    keep_mask = (
        (~use_outlier_filter)
        | data["Sensitivity"].between(q01, q99)
    )

    data["Outlier_Filter_Applied"] = use_outlier_filter
    data["Outlier_Kept"] = keep_mask

    data_clean = data[keep_mask].copy()

    return data_clean


# =========================================================
# SATURATION ANALYSIS
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

    if sat_df.empty:
        return {
            "profile": pd.DataFrame(),
            "baseline_sensitivity": np.nan,
            "warning_ratio": np.nan,
            "saturation_ratio": np.nan
        }

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

    profile["Efficiency_vs_Baseline_%"] = np.nan
    profile["Saturation_Status"] = "Insufficient Data"

    valid_profile = profile[
        (profile["Adjustment_Records"] >= 5)
        & (profile["Paint_Batches"] >= 3)
        & (profile["Sensitivity_Median"] > 0)
    ].copy()

    baseline_sensitivity = np.nan
    warning_ratio = np.nan
    saturation_ratio = np.nan

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
                or row["Paint_Batches"] < 3
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
# WORD EXPORT
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

    title_run = title.add_run("Historical Viscosity Adjustment Analysis")
    title_run.bold = True
    title_run.font.size = Pt(18)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER

    subtitle_run = subtitle.add_run(
        f"Resin: {selected_resin} | "
        f"Position: {selected_pos} | "
        f"Vendor: {selected_vendor} | "
        f"Solvent: {selected_solvent}"
    )
    subtitle_run.font.size = Pt(10)

    doc.add_paragraph("")

    table = doc.add_table(rows=2, cols=5)
    table.style = "Table Grid"

    headers = [
        "Adjustment Records",
        "Paint Batches",
        "Median Sensitivity",
        "P10-P90 Ratio Range",
        "Maximum Viscosity Drop"
    ]

    values = [
        f"{len(system_df):,}",
        f"{system_df['塗料批號'].nunique():,}",
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
            before_v = row["黏度(秒)"]
            after_v = row["黏度(秒)_1"]

            ax.plot(
                [ratio, ratio],
                [before_v, after_v],
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
            label="Initial Viscosity",
            zorder=3
        )

        ax.scatter(
            system_df["Solvent_Ratio_Percent"],
            system_df["黏度(秒)_1"],
            s=35,
            color="#4472C4",
            edgecolors="white",
            linewidths=0.5,
            label="Final Viscosity",
            zorder=3
        )

        ax.set_title(
            "Viscosity Transition by Solvent Ratio\n"
            f"Resin: {selected_resin} | "
            f"Position: {selected_pos} | "
            f"Vendor: {selected_vendor} | "
            f"Solvent: {selected_solvent}",
            fontsize=14,
            fontweight="bold",
            pad=16
        )

        ax.set_xlabel("Solvent Ratio (%)", fontsize=10)
        ax.set_ylabel("Viscosity (seconds)", fontsize=10)

        ax.grid(
            True,
            linestyle="--",
            linewidth=0.5,
            alpha=0.5
        )

        ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, 1.02),
            ncol=2,
            frameon=False
        )

        plt.tight_layout()

        chart_stream = BytesIO()

        fig.savefig(
            chart_stream,
            format="png",
            dpi=260,
            bbox_inches="tight"
        )

        chart_stream.seek(0)
        plt.close(fig)

        chart_paragraph = doc.add_paragraph()
        chart_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

        chart_paragraph.add_run().add_picture(
            chart_stream,
            width=Inches(9.6)
        )

    except Exception as e:
        error_paragraph = doc.add_paragraph()
        error_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

        error_run = error_paragraph.add_run(
            f"\n[CHART EXPORT FAILED]\n{str(e)}"
        )
        error_run.bold = True

    note = doc.add_paragraph()

    note_run = note.add_run(
        "Note: Each point pair represents one valid historical adjustment "
        "record. Orange = before adjustment. Blue = after adjustment."
    )

    note_run.italic = True
    note_run.font.size = Pt(9)

    output = BytesIO()
    doc.save(output)
    output.seek(0)

    return output.getvalue()


# =========================================================
# LOAD DATA
# =========================================================
if not st.session_state.get("raw_data_loaded", False):
    st.warning("⚠️ Please upload data on the main page first.")
    st.stop()

try:
    master_df = process_data(
        st.session_state["group_a_data"]
    )

except ValueError as e:
    st.error(f"⚠️ Data structure error: {str(e)}")
    st.stop()

if master_df.empty:
    st.error(
        "⚠️ No valid historical adjustment records are available "
        "after data validation."
    )
    st.stop()


# =========================================================
# TITLE
# =========================================================
st.title("⚙️ Viscosity Optimization & SOP System")

st.markdown(
    "This system analyzes each valid solvent adjustment record separately. "
    "Paint batch count is shown only as a data coverage indicator."
)

st.markdown("---")


# =========================================================
# GLOBAL FILTERS
# =========================================================
col_f1, col_f2, col_f3, col_f4 = st.columns(4)

with col_f1:
    selected_resin = st.selectbox(
        "Select Resin:",
        sorted(master_df["Resin"].dropna().unique()),
        on_change=reset_execution_states
    )

with col_f2:
    available_positions = sorted(
        master_df[
            master_df["Resin"] == selected_resin
        ]["Position_UI"].dropna().unique()
    )

    selected_pos = st.selectbox(
        "Select Position:",
        available_positions,
        on_change=reset_execution_states
    )

with col_f3:
    available_vendors = sorted(
        master_df[
            (master_df["Resin"] == selected_resin)
            & (master_df["Position_UI"] == selected_pos)
        ]["Vendor"].dropna().unique()
    )

    selected_vendor = st.selectbox(
        "Select Vendor:",
        available_vendors,
        on_change=reset_execution_states
    )

with col_f4:
    available_solvents = sorted(
        master_df[
            (master_df["Resin"] == selected_resin)
            & (master_df["Position_UI"] == selected_pos)
            & (master_df["Vendor"] == selected_vendor)
        ]["Solvent_Type"].dropna().unique()
    )

    selected_solvent = st.selectbox(
        "Select Solvent Type:",
        available_solvents,
        on_change=reset_execution_states
    )


# =========================================================
# FILTERED SYSTEM DATA
# =========================================================
system_df = master_df[
    (master_df["Resin"] == selected_resin)
    & (master_df["Position_UI"] == selected_pos)
    & (master_df["Vendor"] == selected_vendor)
    & (master_df["Solvent_Type"] == selected_solvent)
].copy()

if system_df.empty:
    st.error("⚠️ No records found for this selected system.")
    st.stop()

system_record_count = len(system_df)
system_batch_count = system_df["塗料批號"].nunique()
system_status = get_data_status(
    system_record_count,
    system_batch_count
)

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
    st.markdown("### Historical Adjustment Record Analysis")

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "有效調整紀錄數",
        f"{system_record_count:,}"
    )

    c2.metric(
        "涉及塗料批號數",
        f"{system_batch_count:,}"
    )

    c3.metric(
        "Median Sensitivity",
        f"{system_df['Sensitivity'].median():.2f} s/%"
    )

    c4.metric(
        "P10-P90 Ratio Range",
        f"{system_df['Solvent_Ratio_Percent'].quantile(0.1):.1f}% - "
        f"{system_df['Solvent_Ratio_Percent'].quantile(0.9):.1f}%"
    )

    c5.metric(
        "Data Status",
        get_data_status_short(
            system_record_count,
            system_batch_count
        )
    )

    st.info(
        f"資料評估：{system_status}"
    )

    fig_scatter = go.Figure()

    for _, row in system_df.iterrows():
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
                    width=1.2,
                    dash="dot"
                ),
                showlegend=False,
                hoverinfo="skip"
            )
        )

    fig_scatter.add_trace(
        go.Scatter(
            x=system_df["Solvent_Ratio_Percent"],
            y=system_df["黏度(秒)"],
            mode="markers",
            name="Initial Viscosity",
            marker=dict(
                color="#ED7D31",
                size=8,
                opacity=0.85,
                line=dict(width=0.8, color="white")
            ),
            customdata=system_df[
                [
                    "塗料批號",
                    "黏度(秒)_1",
                    "Delta_V",
                    "Initial_Viscosity_Zone"
                ]
            ].values,
            hovertemplate=(
                "<b>Paint Batch: %{customdata[0]}</b><br>"
                "Initial Viscosity: %{y:.1f}s<br>"
                "Final Viscosity: %{customdata[1]:.1f}s<br>"
                "Drop: %{customdata[2]:.1f}s<br>"
                "Zone: %{customdata[3]}<br>"
                "Solvent Ratio: %{x:.2f}%"
                "<extra></extra>"
            )
        )
    )

    fig_scatter.add_trace(
        go.Scatter(
            x=system_df["Solvent_Ratio_Percent"],
            y=system_df["黏度(秒)_1"],
            mode="markers",
            name="Final Viscosity",
            marker=dict(
                color="#4472C4",
                size=8,
                opacity=0.85,
                line=dict(width=0.8, color="white")
            ),
            customdata=system_df[
                [
                    "塗料批號",
                    "黏度(秒)",
                    "Delta_V",
                    "Initial_Viscosity_Zone"
                ]
            ].values,
            hovertemplate=(
                "<b>Paint Batch: %{customdata[0]}</b><br>"
                "Initial Viscosity: %{customdata[1]:.1f}s<br>"
                "Final Viscosity: %{y:.1f}s<br>"
                "Drop: %{customdata[2]:.1f}s<br>"
                "Zone: %{customdata[3]}<br>"
                "Solvent Ratio: %{x:.2f}%"
                "<extra></extra>"
            )
        )
    )

    fig_scatter.update_layout(
        title=dict(
            text=(
                "Viscosity Transition by Solvent Ratio<br>"
                f"<sup>{selected_resin} | {selected_pos} | "
                f"{selected_vendor} | {selected_solvent} | "
                f"Records={system_record_count}, "
                f"Batches={system_batch_count}</sup>"
            ),
            x=0.5,
            xanchor="center"
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=620,
        margin=dict(l=70, r=50, t=95, b=70),
        xaxis=dict(
            title="Solvent Ratio (%)",
            showgrid=True,
            gridcolor="#EAEAEA",
            linecolor="black",
            showline=True
        ),
        yaxis=dict(
            title="Viscosity (seconds)",
            showgrid=True,
            gridcolor="#EAEAEA",
            linecolor="black",
            showline=True
        ),
        legend=dict(
            orientation="h",
            y=1.08,
            x=0.5,
            xanchor="center"
        )
    )

    st.plotly_chart(
        fig_scatter,
        use_container_width=True
    )

    word_data = export_chart_to_word(
        selected_resin=selected_resin,
        selected_pos=selected_pos,
        selected_vendor=selected_vendor,
        selected_solvent=selected_solvent,
        system_df=system_df
    )

    st.download_button(
        label="📄 Export Historical Chart to Word",
        data=word_data,
        file_name=(
            f"Viscosity_Transition_"
            f"{selected_resin}_{selected_pos}_"
            f"{selected_vendor}_{selected_solvent}.docx"
        ),
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        )
    )


# =========================================================
# TAB 2: SOP RECOMMENDATION
# =========================================================
with tab2:
    st.markdown("### SOP Recommendation")

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
            "Actual Paint Weight (kg)",
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
            st.error("⚠️ All input values must be greater than 0.")

        elif app_lsl >= app_usl:
            st.error("⚠️ Target LSL must be lower than Target USL.")

        else:
            target_center = (app_lsl + app_usl) / 2
            required_drop = curr_visc - target_center

            if required_drop <= 0:
                st.success(
                    "✅ Current viscosity is already within or below target range."
                )

            else:
                curr_zone = assign_viscosity_zone(curr_visc)

                zone_df = system_df[
                    system_df["Initial_Viscosity_Zone"] == curr_zone
                ].copy()

                zone_records = len(zone_df)
                zone_batches = zone_df["塗料批號"].nunique()

                if zone_records >= 5 and zone_batches >= 3:
                    ref_data = zone_df
                    ref_source = f"Zone Specific: {curr_zone}"

                else:
                    ref_data = system_df
                    ref_source = "Overall System Fallback"

                ref_records = len(ref_data)
                ref_batches = ref_data["塗料批號"].nunique()

                if ref_records < 5 or ref_batches < 3:
                    st.error(
                        "🚨 Insufficient historical data for automated SOP. "
                        "Manual process engineer verification required."
                    )

                else:
                    ref_sensitivity = ref_data["Sensitivity"].median()

                    required_ratio = (
                        required_drop / ref_sensitivity
                    )

                    recommended_solvent = (
                        order_weight
                        * required_ratio
                        / 100
                    )

                    ratio_p90 = ref_data[
                        "Solvent_Ratio_Percent"
                    ].quantile(0.90)

                    ratio_p95 = ref_data[
                        "Solvent_Ratio_Percent"
                    ].quantile(0.95)

                    drop_p90 = ref_data["Delta_V"].quantile(0.90)
                    drop_max = ref_data["Delta_V"].max()

                    risk_status = "✅ NORMAL OPERATION"
                    risk_color = "green"
                    blocked = False

                    if (
                        required_ratio > ratio_p95
                        or required_drop > drop_max
                    ):
                        risk_status = "🚨 CRITICAL OVERLOAD"
                        risk_color = "red"
                        blocked = True

                    elif (
                        required_ratio > ratio_p90
                        or required_drop > drop_p90
                    ):
                        risk_status = "⚠️ DIMINISHING RETURNS WARNING"
                        risk_color = "orange"

                    if (
                        not pd.isna(saturation_limit_ratio)
                        and required_ratio >= saturation_limit_ratio
                    ):
                        risk_status = "🚨 SATURATION LIMIT REACHED"
                        risk_color = "red"
                        blocked = True

                    elif (
                        not blocked
                        and not pd.isna(saturation_warning_ratio)
                        and required_ratio >= saturation_warning_ratio
                    ):
                        risk_status = "⚠️ DIMINISHING RETURNS WARNING"
                        risk_color = "orange"

                    st.markdown(
                        f"### Assessment: "
                        f"<span style='color:{risk_color}'>"
                        f"{risk_status}"
                        f"</span>",
                        unsafe_allow_html=True
                    )

                    c1, c2, c3, c4 = st.columns(4)

                    c1.metric(
                        "Required Drop",
                        f"{required_drop:.1f} s"
                    )

                    c2.metric(
                        "Reference Sensitivity",
                        f"{ref_sensitivity:.2f} s/%"
                    )

                    c3.metric(
                        "Reference Records",
                        f"{ref_records:,}"
                    )

                    c4.metric(
                        "Reference Paint Batches",
                        f"{ref_batches:,}"
                    )

                    st.caption(
                        f"Reference source: {ref_source}"
                    )

                    if blocked:
                        st.error(
                            "⛔ Recommendation blocked. Required condition "
                            "exceeds historical safe operating limits."
                        )

                    else:
                        st.success(
                            f"Recommended total solvent: "
                            f"{recommended_solvent:.2f} kg "
                            f"({required_ratio:.2f}%)"
                        )

                        st.markdown("### 3-Stage Addition Protocol")

                        st.markdown(
                            f"""
                            1. **Step 1 — 60%:** Add `{recommended_solvent * 0.60:.2f} kg`  
                            2. **Step 2 — 25%:** Add `{recommended_solvent * 0.25:.2f} kg` only if still above USL  
                            3. **Step 3 — 15%:** Add up to `{recommended_solvent * 0.15:.2f} kg` for micro-adjustment  
                            """
                        )


# =========================================================
# TAB 3: ENGINEERING MATRIX
# =========================================================
with tab3:
    st.markdown("### Engineering Matrix by Initial Viscosity Zone")

    engineering_matrix = (
        system_df.groupby(
            "Initial_Viscosity_Zone",
            observed=False
        )
        .agg(
            Adjustment_Records=("塗料批號", "size"),
            Paint_Batches=("塗料批號", "nunique"),
            Median_Sensitivity=("Sensitivity", "median"),
            Median_Ratio=("Solvent_Ratio_Percent", "median"),
            Ratio_P90=(
                "Solvent_Ratio_Percent",
                lambda x: x.quantile(0.90)
            ),
            Ratio_P95=(
                "Solvent_Ratio_Percent",
                lambda x: x.quantile(0.95)
            ),
            Median_Drop=("Delta_V", "median"),
            Drop_P90=(
                "Delta_V",
                lambda x: x.quantile(0.90)
            ),
            Max_Drop=("Delta_V", "max")
        )
        .reset_index()
    )

    engineering_matrix["Data_Status"] = engineering_matrix.apply(
        lambda row: get_data_status_short(
            row["Adjustment_Records"],
            row["Paint_Batches"]
        ),
        axis=1
    )

    engineering_matrix["_zone_order"] = (
        engineering_matrix["Initial_Viscosity_Zone"]
        .apply(get_zone_order)
    )

    engineering_matrix = (
        engineering_matrix
        .sort_values("_zone_order")
        .drop(columns="_zone_order")
    )

    st.dataframe(
        engineering_matrix,
        column_config={
            "Adjustment_Records": st.column_config.NumberColumn(
                "有效調整紀錄數",
                format="%d"
            ),
            "Paint_Batches": st.column_config.NumberColumn(
                "涉及塗料批號數",
                format="%d"
            ),
            "Median_Sensitivity": st.column_config.NumberColumn(
                "Median Sensitivity (s/%)",
                format="%.2f"
            ),
            "Median_Ratio": st.column_config.NumberColumn(
                "Median Ratio (%)",
                format="%.2f"
            ),
            "Ratio_P90": st.column_config.NumberColumn(
                "P90 Ratio (%)",
                format="%.2f"
            ),
            "Ratio_P95": st.column_config.NumberColumn(
                "P95 Ratio (%)",
                format="%.2f"
            ),
            "Median_Drop": st.column_config.NumberColumn(
                "Median Drop (s)",
                format="%.1f"
            ),
            "Drop_P90": st.column_config.NumberColumn(
                "P90 Drop (s)",
                format="%.1f"
            ),
            "Max_Drop": st.column_config.NumberColumn(
                "Max Drop (s)",
                format="%.1f"
            )
        },
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")
    st.markdown("### Solvent Saturation / Diminishing Returns")

    if saturation_profile.empty:
        st.warning("No saturation profile available.")

    else:
        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Baseline Sensitivity",
            (
                f"{baseline_sensitivity:.2f} s/%"
                if not pd.isna(baseline_sensitivity)
                else "Not Detected"
            )
        )

        c2.metric(
            "Diminishing Return Threshold",
            (
                f"{saturation_warning_ratio:.2f}%"
                if not pd.isna(saturation_warning_ratio)
                else "Not Detected"
            )
        )

        c3.metric(
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
                "Efficiency_vs_Baseline_%": st.column_config.NumberColumn(
                    "Efficiency vs Baseline (%)",
                    format="%.1f%%"
                )
            },
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# TAB 4: MASTER SHOP FLOOR SOP
# =========================================================
with tab4:
    st.markdown("### 🖨️ 現場歷史加料參考表")

    st.warning(
        "依相同條件查詢 → 依建議比例添加稀釋劑 → 攪拌5分鐘 → 再量測黏度。"
    )

    st.caption(
        "本表以每一筆有效調整紀錄計算中位數與P90/P95；"
        "塗料批號數僅作為資料覆蓋度與可信度判斷。"
    )

    worker_sop = (
        master_df.groupby(
            SYSTEM_GROUP_COLS + ["Initial_Viscosity_Zone"],
            observed=False
        )
        .agg(
            Adjustment_Records=("塗料批號", "size"),
            Paint_Batches=("塗料批號", "nunique"),
            Ref_Start_Visc=("黏度(秒)", "median"),
            Ref_Paint_Weight_kg=("塗料重量", "median"),
            Ref_Solvent_Add_kg=("添加重量", "median"),
            Ref_Solvent_Ratio=("Solvent_Ratio_Percent", "median"),
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
        )
        .reset_index()
    )

    worker_sop["Data_Status"] = worker_sop.apply(
        lambda row: get_data_status(
            row["Adjustment_Records"],
            row["Paint_Batches"]
        ),
        axis=1
    )

    worker_sop = worker_sop[
        worker_sop["Adjustment_Records"] >= 5
    ].copy()

    def format_range(p25, p75):
        if pd.isna(p25) or pd.isna(p75):
            return "-"

        if abs(float(p25) - float(p75)) < 0.05:
            return f"{float(p25):.1f}"

        return f"{float(p25):.1f} - {float(p75):.1f}"

    worker_sop["歷史最終黏度範圍"] = worker_sop.apply(
        lambda row: format_range(
            row["Final_Visc_P25"],
            row["Final_Visc_P75"]
        ),
        axis=1
    )

    saturation_summary = []

    system_keys = master_df[SYSTEM_GROUP_COLS].drop_duplicates()

    for _, row in system_keys.iterrows():
        temp_system = master_df[
            (master_df["Resin"] == row["Resin"])
            & (master_df["Position_UI"] == row["Position_UI"])
            & (master_df["Vendor"] == row["Vendor"])
            & (master_df["Solvent_Type"] == row["Solvent_Type"])
        ].copy()

        temp_sat = build_saturation_profile(temp_system)

        saturation_summary.append({
            "Resin": row["Resin"],
            "Position_UI": row["Position_UI"],
            "Vendor": row["Vendor"],
            "Solvent_Type": row["Solvent_Type"],
            "Saturation_Warning_Ratio": temp_sat["warning_ratio"],
            "Saturation_Stop_Ratio": temp_sat["saturation_ratio"]
        })

    saturation_summary_df = pd.DataFrame(saturation_summary)

    worker_sop = worker_sop.merge(
        saturation_summary_df,
        on=SYSTEM_GROUP_COLS,
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

    worker_output = worker_sop[
        [
            "Resin",
            "Position_UI",
            "Vendor",
            "Solvent_Type",
            "Initial_Viscosity_Zone",
            "Adjustment_Records",
            "Paint_Batches",
            "Data_Status",
            "Ref_Start_Visc",
            "Ref_Paint_Weight_kg",
            "Ref_Solvent_Add_kg",
            "Ref_Solvent_Ratio",
            "歷史最終黏度範圍",
            "Saturation_Warning_Ratio",
            "Saturation_Stop_Ratio"
        ]
    ].copy()

    worker_output.rename(
        columns={
            "Resin": "樹脂種類",
            "Position_UI": "塗裝位置",
            "Vendor": "塗料供應商",
            "Solvent_Type": "稀釋劑種類",
            "Initial_Viscosity_Zone": "初始黏度區間",
            "Adjustment_Records": "有效調整紀錄數",
            "Paint_Batches": "涉及塗料批號數",
            "Data_Status": "資料狀態",
            "Ref_Start_Visc": "參考起始黏度",
            "Ref_Paint_Weight_kg": "參考塗料使用量",
            "Ref_Solvent_Add_kg": "參考稀釋劑添加量",
            "Ref_Solvent_Ratio": "參考稀釋劑添加比例",
            "Saturation_Warning_Ratio": "飽和警戒比例",
            "Saturation_Stop_Ratio": "飽和停止比例"
        },
        inplace=True
    )

    worker_output["_zone_order"] = (
        worker_output["初始黏度區間"]
        .apply(get_zone_order)
    )

    worker_output = (
        worker_output
        .sort_values(
            by=[
                "樹脂種類",
                "塗裝位置",
                "塗料供應商",
                "稀釋劑種類",
                "_zone_order"
            ]
        )
        .drop(columns="_zone_order")
    )

    st.dataframe(
        worker_output,
        column_config={
            "有效調整紀錄數": st.column_config.NumberColumn(
                "有效調整紀錄數",
                format="%d"
            ),
            "涉及塗料批號數": st.column_config.NumberColumn(
                "涉及塗料批號數",
                format="%d"
            ),
            "參考起始黏度": st.column_config.NumberColumn(
                "參考起始黏度 (s)",
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

    csv_export = worker_output.to_csv(
        index=False
    ).encode("utf-8-sig")

    st.download_button(
        label="下載現場歷史加料參考表 CSV",
        data=csv_export,
        file_name="現場歷史加料參考表.csv",
        mime="text/csv"
    )
