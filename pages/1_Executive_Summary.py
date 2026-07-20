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
# GLOBAL CONFIGURATION
# =========================================================
MIN_REFERENCE_RECORDS = 5        # Minimum adjustment records to use zone-specific reference
FIRST_ADD_PERCENT = 0.60         # First addition = 60% of calculated total
MIXING_TIME_MINUTES = 5


# =========================================================
# EXPORT HISTORICAL CHART TO WORD
# EXPORT HISTORICAL CHART TO WORD - STABLE VERSION
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
    section.top_margin = Inches(0.35)
    section.bottom_margin = Inches(0.35)
    section.left_margin = Inches(0.40)
    section.right_margin = Inches(0.40)

    # =====================================================
    # REPORT TITLE
    # =====================================================
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(2)

    title_run = title.add_run("Historical Viscosity Transition Analysis")
    title_run.bold = True
    title_run.font.size = Pt(16)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(5)

    subtitle_run = subtitle.add_run(
        f"Resin: {selected_resin} | Position: {selected_pos} | "
        f"Vendor: {selected_vendor} | Solvent Type: {selected_solvent}"
    )
    subtitle_run.font.size = Pt(9)

    # =====================================================
    # KPI TABLE
    # =====================================================
    table = doc.add_table(rows=2, cols=5)
    table.style = "Table Grid"

    headers = [
        "Valid Paint Batches",
        "Valid Paint Buckets",
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
            f" - {system_df['Solvent_Ratio_Percent'].quantile(0.90):.1f}%"
        ),
        f"{system_df['Delta_V'].max():.1f} s"
    ]

    for i, header in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = header

        for paragraph in cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.space_after = Pt(0)

            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(8)

    for i, value in enumerate(values):
        cell = table.cell(1, i)
        cell.text = value

        for paragraph in cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.space_after = Pt(0)

            for run in paragraph.runs:
                run.font.size = Pt(8)

    # =====================================================
    # CHART
    # =====================================================
    try:
        # Fixed canvas. Do NOT use tight_layout or subplots_adjust.
        fig = plt.figure(figsize=(9.7, 4.45), facecolor="white")

        # Fixed axes position: [left, bottom, width, height]
        ax = fig.add_axes([0.10, 0.18, 0.86, 0.55])

        # ----- Chart title, same style as app -----
        fig.text(
            0.5,
            0.95,
            "Viscosity Transition by Solvent Ratio",
            ha="center",
            va="center",
            fontsize=14,
            fontweight="bold"
        )

        fig.text(
            0.5,
            0.89,
            f"Resin: {selected_resin} | Position: {selected_pos} | "
            f"Vendor: {selected_vendor} | Solvent: {selected_solvent}",
            ha="center",
            va="center",
            fontsize=11,
            fontweight="bold"
        )

        # ----- Connector lines -----
        for _, row in system_df.iterrows():
            ax.plot(
                [
                    row["Solvent_Ratio_Percent"],
                    row["Solvent_Ratio_Percent"]
                ],
                [
                    row["黏度(秒)"],
                    row["黏度(秒)_1"]
                ],
                linestyle=":",
                linewidth=0.7,
                color="lightgray",
                zorder=1
            )

        # ----- Before viscosity -----
        before_points = ax.scatter(
            system_df["Solvent_Ratio_Percent"],
            system_df["黏度(秒)"],
            s=30,
            color="#ED7D31",
            edgecolors="white",
            linewidths=0.4,
            label="Initial Viscosity (Before)",
            zorder=3
        )

        # ----- After viscosity -----
        after_points = ax.scatter(
            system_df["Solvent_Ratio_Percent"],
            system_df["黏度(秒)_1"],
            s=30,
            color="#4472C4",
            edgecolors="white",
            linewidths=0.4,
            label="Final Viscosity (After)",
            zorder=3
        )

        ax.set_xlabel("Solvent Blending Ratio (%)", fontsize=10)
        ax.set_ylabel("Viscosity (seconds)", fontsize=10)

        ax.tick_params(
            axis="both",
            labelsize=9
        )

        ax.grid(
            True,
            linestyle="--",
            linewidth=0.5,
            alpha=0.45
        )

        # Legend is outside data area, between subtitle and plot.
        fig.legend(
            handles=[before_points, after_points],
            labels=[
                "Initial Viscosity (Before)",
                "Final Viscosity (After)"
            ],
            loc="upper center",
            bbox_to_anchor=(0.5, 0.855),
            ncol=2,
            frameon=False,
            fontsize=9
        )

        chart_stream = BytesIO()

        # Important: do not use bbox_inches="tight"
        fig.savefig(
            chart_stream,
            format="png",
            dpi=220,
            facecolor="white"
        )

        chart_stream.seek(0)
        plt.close(fig)

        chart_paragraph = doc.add_paragraph()
        chart_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        chart_paragraph.paragraph_format.space_before = Pt(5)
        chart_paragraph.paragraph_format.space_after = Pt(2)

        chart_paragraph.add_run().add_picture(
            chart_stream,
            width=Inches(9.55)
        )

    except Exception as e:
        error_paragraph = doc.add_paragraph()
        error_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

        error_run = error_paragraph.add_run(
            f"[CHART EXPORT FAILED] {str(e)}"
        )
        error_run.bold = True

    # =====================================================
    # NOTE
    # =====================================================
    note = doc.add_paragraph()
    note.paragraph_format.space_before = Pt(0)
    note.paragraph_format.space_after = Pt(0)

    note_run = note.add_run(
        "Note: Orange points represent viscosity before solvent addition. "
        "Blue points represent viscosity after solvent addition. "
        "The dotted line connects the initial and final viscosity of the same paint bucket."
    )
    note_run.italic = True
    note_run.font.size = Pt(8)

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

if not st.session_state.get("raw_data_loaded", False):
    st.warning("⚠️ Please upload data on the main page first.")
    st.stop()


# =========================================================
# HELPER FUNCTIONS
# =========================================================
def get_viscosity_zone(value):
    """Engineering viscosity zone used in Tabs 1–3."""
    if pd.isna(value):
        return "Unknown"

    if value <= 70:
        return "<=70 s"
    elif value <= 90:
        return "71-90 s"
    elif value <= 110:
        return "91-110 s"
    elif value <= 130:
        return "111-130 s"
    else:
        return ">130 s"


def get_zone_order(zone):
    """Sort order for viscosity zones."""
    zone = str(zone)

    if zone.startswith("<=70"):
        return 1
    elif zone.startswith("71-90"):
        return 2
    elif zone.startswith("91-110"):
        return 3
    elif zone.startswith("111-130"):
        return 4
    elif zone.startswith("130-") or zone.startswith(">130"):
        return 5

    return 99


def get_temperature_zone(value):
    """Optional temperature grouping for analysis."""
    if pd.isna(value):
        return "Unknown"

    if value < 20:
        return "<20°C"
    elif value < 25:
        return "20-24.9°C"
    elif value < 30:
        return "25-29.9°C"
    elif value < 35:
        return "30-34.9°C"
    else:
        return ">=35°C"


def format_range(p25, p75, decimals=1):
    """Format P25-P75 range for display."""
    if pd.isna(p25) or pd.isna(p75):
        return "-"

    p25 = round(float(p25), decimals)
    p75 = round(float(p75), decimals)

    if abs(p25 - p75) < 0.05:
        return f"{p25:.{decimals}f}"

    return f"{p25:.{decimals}f} - {p75:.{decimals}f}"


def reset_execution_states():
    """Reset SOP execution calculator when filters are changed."""
    keys_to_reset = [
        "sop_calculated",
        "sop_result",
        "step2_result",
        "step1_added_kg",
        "step1_after_visc"
    ]

    for key in keys_to_reset:
        st.session_state[key] = None


# =========================================================
# DATA CLEANSING
# =========================================================
@st.cache_data(show_spinner=False)
def prepare_valid_records(df):
    """
    Convert raw rows into valid historical adjustment records.

    Confirmed source-data rules
    ---------------------------
    General paint codes:
    1. The same paint batch + paint bucket may contain multiple rows because
       solvent was added more than once.
    2. 添加重量 is cumulative; therefore use the LAST cumulative value.
    3. 塗料重量 includes cumulative solvent already added.
    4. Initial viscosity = FIRST 黏度(秒).
    5. Final viscosity = LAST 黏度(秒)_1.

    Special paint code PS30213X8:
    1. 塗料桶號 identifies a large source tank.
    2. Paint is drawn from that source tank into separate small mixing buckets.
    3. Even when batch and bucket number repeat, every row is an independent
       first-time mixing record.
    4. Therefore PS30213X8 rows must NOT be merged.

    Ratio definition
    ----------------
        Original_Paint_Weight = 塗料重量 - 添加重量
        Solvent_Ratio_Percent = 添加重量 / Original_Paint_Weight * 100
    """
    data = df.copy()

    if data.empty:
        return data

    SPECIAL_INDEPENDENT_PAINT_CODES = {
        "PS30213X8"
    }

    required_columns = [
        "添加重量",
        "塗料重量",
        "黏度(秒)",
        "黏度(秒)_1",
        "Resin",
        "Vendor",
        "Solvent_Type",
        "塗料批號",
        "塗料桶號",
        "塗料編號"
    ]

    missing_columns = [
        col for col in required_columns
        if col not in data.columns
    ]

    if missing_columns:
        return pd.DataFrame()

    numeric_columns = [
        "添加重量",
        "塗料重量",
        "黏度(秒)",
        "黏度(秒)_1"
    ]

    if "溫度" in data.columns:
        numeric_columns.append("溫度")

    for col in numeric_columns:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    if "塗裝位置" not in data.columns:
        data["塗裝位置"] = "Unknown"

    position_mapping = {
        "TP": "Primer",
        "正底漆": "Primer",
        "BP": "Primer",
        "背底漆": "Primer",
        "TF": "Top Finish",
        "正面漆": "Top Finish",
        "BF": "Back Finish",
        "背面漆": "Back Finish"
    }

    data["Position_UI"] = (
        data["塗裝位置"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .map(position_mapping)
        .fillna(data["塗裝位置"])
    )

    data["塗料編號"] = (
        data["塗料編號"]
        .astype(str)
        .str.strip()
    )

    data = data[
        (data["添加重量"] > 0)
        & (data["塗料重量"] > 0)
        & (data["黏度(秒)"].notna())
        & (data["黏度(秒)_1"].notna())
        & (data["Resin"].notna())
        & (data["Vendor"].notna())
        & (data["Solvent_Type"].notna())
        & (data["塗料批號"].notna())
        & (data["塗料桶號"].notna())
        & (data["塗料編號"].notna())
    ].copy()

    if data.empty:
        return data

    data["_Original_Row_Order"] = np.arange(len(data))

    # =====================================================
    # 1. SPECIAL CODE: EACH ROW IS AN INDEPENDENT MIX
    # =====================================================
    special_df = data[
        data["塗料編號"].isin(SPECIAL_INDEPENDENT_PAINT_CODES)
    ].copy()

    if not special_df.empty:
        special_df["Raw_Adjustment_Rows"] = 1
        special_df["Cumulative_Add_Decreased"] = False
        special_df["Cumulative_Solvent_Added"] = special_df["添加重量"]
        special_df["Final_Mixture_Weight"] = special_df["塗料重量"]
        special_df["Original_Paint_Weight"] = (
            special_df["Final_Mixture_Weight"]
            - special_df["Cumulative_Solvent_Added"]
        )
        special_df["Dilution_Base"] = special_df["Original_Paint_Weight"]

    # =====================================================
    # 2. NORMAL CODES: MERGE MULTIPLE ROWS OF SAME BUCKET
    # =====================================================
    normal_df = data[
        ~data["塗料編號"].isin(SPECIAL_INDEPENDENT_PAINT_CODES)
    ].copy()

    if not normal_df.empty:
        sort_cols = []

        if "攪拌日期" in normal_df.columns:
            normal_df["_Sort_Date"] = pd.to_datetime(
                normal_df["攪拌日期"],
                errors="coerce"
            )
            sort_cols.append("_Sort_Date")

        if "攪拌時間(起)" in normal_df.columns:
            time_text = (
                normal_df["攪拌時間(起)"]
                .astype(str)
                .str.replace(r"\.0$", "", regex=True)
                .str.replace(":", "", regex=False)
                .str.strip()
                .str.zfill(4)
            )
            normal_df["_Sort_Start_Time"] = pd.to_numeric(
                time_text,
                errors="coerce"
            )
            sort_cols.append("_Sort_Start_Time")

        sort_cols.append("_Original_Row_Order")

        bucket_group_cols = [
            "塗料批號",
            "塗料桶號",
            "塗料編號"
        ]

        if "攪拌日期" in normal_df.columns:
            bucket_group_cols.insert(0, "攪拌日期")

        for optional_key in [
            "Solvent_Type",
            "Position_UI"
        ]:
            if optional_key in normal_df.columns:
                bucket_group_cols.append(optional_key)

        normal_df = normal_df.sort_values(
            bucket_group_cols + sort_cols,
            kind="stable"
        )

        normal_df["_Previous_Cumulative_Add"] = (
            normal_df
            .groupby(bucket_group_cols, dropna=False)["添加重量"]
            .shift(1)
        )

        normal_df["_Cumulative_Add_Decreased"] = (
            normal_df["_Previous_Cumulative_Add"].notna()
            & (
                normal_df["添加重量"]
                < normal_df["_Previous_Cumulative_Add"]
            )
        )

        agg_map = {
            "黏度(秒)": "first",
            "黏度(秒)_1": "last",
            "添加重量": "last",
            "塗料重量": "last",
            "Resin": "first",
            "Vendor": "first",
            "塗裝位置": "first",
            "_Original_Row_Order": "size",
            "_Cumulative_Add_Decreased": "max"
        }

        if "溫度" in normal_df.columns:
            agg_map["溫度"] = "median"

        for optional_col in [
            "稀釋劑",
            "稀釋劑批號",
            "稀釋劑桶號",
            "攪拌時間(起)",
            "攪拌時間(迄)"
        ]:
            if (
                optional_col in normal_df.columns
                and optional_col not in bucket_group_cols
            ):
                agg_map[optional_col] = "last"

        normal_bucket_df = (
            normal_df
            .groupby(
                bucket_group_cols,
                dropna=False,
                as_index=False
            )
            .agg(agg_map)
        )

        normal_bucket_df = normal_bucket_df.rename(columns={
            "_Original_Row_Order": "Raw_Adjustment_Rows",
            "_Cumulative_Add_Decreased": "Cumulative_Add_Decreased"
        })

        normal_bucket_df["Cumulative_Solvent_Added"] = (
            normal_bucket_df["添加重量"]
        )

        normal_bucket_df["Final_Mixture_Weight"] = (
            normal_bucket_df["塗料重量"]
        )

        normal_bucket_df["Original_Paint_Weight"] = (
            normal_bucket_df["Final_Mixture_Weight"]
            - normal_bucket_df["Cumulative_Solvent_Added"]
        )

        normal_bucket_df["Dilution_Base"] = (
            normal_bucket_df["Original_Paint_Weight"]
        )
    else:
        normal_bucket_df = pd.DataFrame()

    # =====================================================
    # 3. COMBINE BOTH LOGICS
    # =====================================================
    frames = []

    if not normal_bucket_df.empty:
        frames.append(normal_bucket_df)

    if not special_df.empty:
        frames.append(special_df)

    if not frames:
        return pd.DataFrame()

    bucket_df = pd.concat(
        frames,
        ignore_index=True,
        sort=False
    )

    # =====================================================
    # 4. COMMON CALCULATIONS
    # =====================================================
    bucket_df["Delta_V"] = (
        bucket_df["黏度(秒)"]
        - bucket_df["黏度(秒)_1"]
    )

    bucket_df["Solvent_Ratio_Percent"] = (
        bucket_df["Cumulative_Solvent_Added"]
        / bucket_df["Dilution_Base"].replace(0, np.nan)
        * 100
    )

    bucket_df["Sensitivity"] = (
        bucket_df["Delta_V"]
        / bucket_df["Solvent_Ratio_Percent"].replace(0, np.nan)
    )

    bucket_df = bucket_df[
        (bucket_df["Cumulative_Add_Decreased"] == False)
        & (bucket_df["Original_Paint_Weight"] > 0)
        & (bucket_df["黏度(秒)"] > bucket_df["黏度(秒)_1"])
        & (bucket_df["Delta_V"] > 0)
        & (bucket_df["Solvent_Ratio_Percent"] > 0)
        & bucket_df["Sensitivity"].notna()
        & np.isfinite(bucket_df["Sensitivity"])
        & (bucket_df["Sensitivity"] > 0)
    ].copy()

    if bucket_df.empty:
        return bucket_df

    bucket_df["Initial_Viscosity_Zone"] = (
        bucket_df["黏度(秒)"]
        .apply(get_viscosity_zone)
    )

    if "溫度" in bucket_df.columns:
        bucket_df["Temperature_Zone"] = (
            bucket_df["溫度"]
            .apply(get_temperature_zone)
        )
    else:
        bucket_df["溫度"] = np.nan
        bucket_df["Temperature_Zone"] = "Unknown"

    bucket_df["Record_Logic"] = np.where(
        bucket_df["塗料編號"].isin(SPECIAL_INDEPENDENT_PAINT_CODES),
        "Independent row - large source tank",
        "Merged by paint batch and paint bucket"
    )

    return bucket_df.copy()


@st.cache_data(show_spinner=False)
def build_master_system_data(valid_df):
    """
    Tabs 1–3 use all valid historical records.
    No minimum batch-count restriction is applied.
    """
    return valid_df.copy()


# =========================================================
# SATURATION / DIMINISHING RETURNS ANALYSIS
# =========================================================
def build_saturation_profile(df):
    """
    Compare efficiency across solvent-ratio zones.

    Important:
    This function should be called using records from the SAME
    Initial_Viscosity_Zone whenever possible.
    """
    if df.empty:
        return {
            "profile": pd.DataFrame(),
            "baseline_sensitivity": np.nan,
            "warning_ratio": np.nan,
            "saturation_ratio": np.nan
        }

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

    profile = (
        sat_df
        .groupby("Ratio_Zone", observed=False)
        .agg(
            Adjustment_Records=("塗料批號", "size"),
            Paint_Batches=("塗料批號", "nunique"),
            Ratio_Median=("Solvent_Ratio_Percent", "median"),
            Ratio_Min=("Solvent_Ratio_Percent", "min"),
            Ratio_Max=("Solvent_Ratio_Percent", "max"),
            DeltaV_Median=("Delta_V", "median"),
            Sensitivity_Median=("Sensitivity", "median"),
            Sensitivity_P25=("Sensitivity", lambda x: x.quantile(0.25)),
            Sensitivity_P75=("Sensitivity", lambda x: x.quantile(0.75))
        )
        .reset_index()
    )

    profile["Efficiency_vs_Baseline_%"] = np.nan
    profile["Saturation_Status"] = "Insufficient Data"

    valid_profile = profile[
        (profile["Adjustment_Records"] >= MIN_REFERENCE_RECORDS)
        & (profile["Sensitivity_Median"] > 0)
        & (profile["Sensitivity_Median"].notna())
    ].copy()

    baseline_sensitivity = np.nan
    warning_ratio = np.nan
    saturation_ratio = np.nan

    if not valid_profile.empty:
        valid_profile = valid_profile.sort_values("Ratio_Min")

        baseline_sensitivity = valid_profile.iloc[0]["Sensitivity_Median"]

        if baseline_sensitivity > 0:
            profile["Efficiency_vs_Baseline_%"] = (
                profile["Sensitivity_Median"]
                / baseline_sensitivity
                * 100
            )

        for idx, row in profile.iterrows():
            if (
                row["Adjustment_Records"] < MIN_REFERENCE_RECORDS
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
# REFERENCE DATA SELECTION
# =========================================================
def get_reference_data(system_df, current_viscosity):
    """
    Prefer same initial-viscosity zone.
    Fall back to full system if the zone has insufficient records.
    """
    current_zone = get_viscosity_zone(current_viscosity)

    zone_df = system_df[
        system_df["Initial_Viscosity_Zone"] == current_zone
    ].copy()

    if len(zone_df) >= MIN_REFERENCE_RECORDS:
        return {
            "reference_df": zone_df,
            "reference_source": f"Zone-Specific ({current_zone})",
            "current_zone": current_zone,
            "record_count": len(zone_df),
            "batch_count": zone_df["塗料批號"].nunique()
        }

    return {
        "reference_df": system_df.copy(),
        "reference_source": "Overall System Fallback",
        "current_zone": current_zone,
        "record_count": len(system_df),
        "batch_count": system_df["塗料批號"].nunique()
    }


def get_safety_limits(reference_df, saturation_result):
    """
    P90 = warning limit.
    P95 / saturation threshold = stop limit.

    The lower limit is always selected when saturation evidence exists.
    """
    if reference_df.empty:
        return {
            "warning_ratio": np.nan,
            "stop_ratio": np.nan,
            "ratio_p90": np.nan,
            "ratio_p95": np.nan,
            "drop_p90": np.nan,
            "drop_max": np.nan
        }

    ratio_p90 = reference_df["Solvent_Ratio_Percent"].quantile(0.90)
    ratio_p95 = reference_df["Solvent_Ratio_Percent"].quantile(0.95)

    drop_p90 = reference_df["Delta_V"].quantile(0.90)
    drop_max = reference_df["Delta_V"].max()

    warning_ratio = ratio_p90
    stop_ratio = ratio_p95

    sat_warning = saturation_result.get("warning_ratio", np.nan)
    sat_stop = saturation_result.get("saturation_ratio", np.nan)

    if not pd.isna(sat_warning):
        warning_ratio = min(warning_ratio, sat_warning)

    if not pd.isna(sat_stop):
        stop_ratio = min(stop_ratio, sat_stop)

    # Stop must never be lower than warning.
    stop_ratio = max(stop_ratio, warning_ratio)

    return {
        "warning_ratio": warning_ratio,
        "stop_ratio": stop_ratio,
        "ratio_p90": ratio_p90,
        "ratio_p95": ratio_p95,
        "drop_p90": drop_p90,
        "drop_max": drop_max
    }


def get_temperature_check(reference_df, current_temperature):
    """
    Environmental warning only.
    Temperature is not directly used to change solvent quantity.
    """
    if reference_df.empty or pd.isna(current_temperature):
        return {
            "available": False,
            "median": np.nan,
            "p25": np.nan,
            "p75": np.nan,
            "warning": False
        }

    temp_data = reference_df["溫度"].dropna()

    if len(temp_data) < MIN_REFERENCE_RECORDS:
        return {
            "available": False,
            "median": np.nan,
            "p25": np.nan,
            "p75": np.nan,
            "warning": False
        }

    temp_median = temp_data.median()
    temp_p25 = temp_data.quantile(0.25)
    temp_p75 = temp_data.quantile(0.75)

    warning = (
        current_temperature < (temp_p25 - 3)
        or current_temperature > (temp_p75 + 3)
    )

    return {
        "available": True,
        "median": temp_median,
        "p25": temp_p25,
        "p75": temp_p75,
        "warning": warning
    }


# =========================================================
# LOAD DATA
# =========================================================
group_a_data = st.session_state.get("group_a_data")

if group_a_data is None or group_a_data.empty:
    st.warning(
        "⚠️ No valid Group A data found. "
        "Please upload the source file again from the main page."
    )
    st.stop()

valid_df = prepare_valid_records(group_a_data)
master_df = build_master_system_data(valid_df)

if master_df.empty:
    st.warning(
        "⚠️ 無可用歷史資料，請確認是否具有有效加料前後黏度資料。"
    )
    st.stop()


# =========================================================
# PAGE TITLE
# =========================================================
st.title("⚙️ AI-Assisted Viscosity Optimization System")

st.markdown(
    "Historical-data-based solvent recommendation system. "
    "The system recommends only the first safe addition, then requires "
    "re-measurement before calculating any additional solvent."
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
        master_df.loc[
            master_df["Resin"] == selected_resin,
            "Position_UI"
        ].dropna().unique()
    )

    selected_pos = st.selectbox(
        "Select Position:",
        available_positions,
        on_change=reset_execution_states
    )

with col_f3:
    available_vendors = sorted(
        master_df.loc[
            (master_df["Resin"] == selected_resin)
            & (master_df["Position_UI"] == selected_pos),
            "Vendor"
        ].dropna().unique()
    )

    selected_vendor = st.selectbox(
        "Select Vendor:",
        available_vendors,
        on_change=reset_execution_states
    )

with col_f4:
    available_solvents = sorted(
        master_df.loc[
            (master_df["Resin"] == selected_resin)
            & (master_df["Position_UI"] == selected_pos)
            & (master_df["Vendor"] == selected_vendor),
            "Solvent_Type"
        ].dropna().unique()
    )

    selected_solvent = st.selectbox(
        "Select Solvent Type:",
        available_solvents,
        on_change=reset_execution_states
    )

system_df = master_df[
    (master_df["Resin"] == selected_resin)
    & (master_df["Position_UI"] == selected_pos)
    & (master_df["Vendor"] == selected_vendor)
    & (master_df["Solvent_Type"] == selected_solvent)
].copy()

if system_df.empty:
    st.error("No valid historical data available for this configuration.")
    st.stop()


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
        "Historical records are shown only for the selected "
        "Resin × Position × Vendor × Solvent Type system."
    )

    unique_batch_count = system_df["塗料批號"].nunique()
    adjustment_record_count = len(system_df)

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
    "Valid Paint Batches",
    f"{unique_batch_count:,}"
    )

    c2.metric(
        "Valid Paint Buckets",
        f"{adjustment_record_count:,}"
    )

    c3.metric(
        "Median Sensitivity",
        f"{system_df['Sensitivity'].median():.2f} s/%"
    )

    c4.metric(
        "P10 - P90 Ratio Range",
        (
            f"{system_df['Solvent_Ratio_Percent'].quantile(0.10):.1f}% - "
            f"{system_df['Solvent_Ratio_Percent'].quantile(0.90):.1f}%"
        )
    )

    c5.metric(
        "Maximum Viscosity Drop",
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
                    [row["塗料批號"], row["Delta_V"]]
                ] * 2,
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
                    "塗料批號",
                    "溫度"
                ]
            ].values,
            hovertemplate=(
                "<b>Batch: %{customdata[3]}</b><br>"
                "<b>Initial Zone: %{customdata[2]}</b><br>"
                "Temperature: %{customdata[4]:.1f}°C<br>"
                "Solvent Ratio: %{x:.2f}%<br>"
                "Initial Viscosity: %{y:.1f}s<br>"
                "Final Viscosity: %{customdata[0]:.1f}s<br>"
                "Viscosity Drop: %{customdata[1]:.1f}s"
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
                    "塗料批號",
                    "溫度"
                ]
            ].values,
            hovertemplate=(
                "<b>Batch: %{customdata[3]}</b><br>"
                "<b>Initial Zone: %{customdata[2]}</b><br>"
                "Temperature: %{customdata[4]:.1f}°C<br>"
                "Solvent Ratio: %{x:.2f}%<br>"
                "Initial Viscosity: %{customdata[0]:.1f}s<br>"
                "Final Viscosity: %{y:.1f}s<br>"
                "Viscosity Drop: %{customdata[1]:.1f}s"
                "<extra></extra>"
            )
        )
    )

    chart_title = (
        "Viscosity Transition by Solvent Ratio<br>"
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

    st.plotly_chart(
        fig_scatter,
        use_container_width=True
    )

    word_data = export_chart_to_word(
        selected_resin,
        selected_pos,
        selected_vendor,
        selected_solvent,
        system_df
    )

    file_name = (
        f"Viscosity_Transition_"
        f"{selected_resin}_{selected_pos}_"
        f"{selected_vendor}_{selected_solvent}.docx"
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
    st.markdown("### 現場稀釋劑添加 SOP 計算")

    st.info(
        "操作原則：只有當目前黏度高於規格上限（USL）時才可計算。"
        "第一次僅添加建議總量的 60%，攪拌後必須重新量測，再計算下一步。"
    )

    input_col1, input_col2, input_col3, input_col4, input_col5 = st.columns(5)

    with input_col1:
        current_visc = st.number_input(
            "Current Viscosity (s)",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key="current_viscosity_input"
        )

    with input_col2:
        target_lsl = st.number_input(
            "Approved Target LSL (s)",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key="target_lsl_input"
        )

    with input_col3:
        target_usl = st.number_input(
            "Approved Target USL (s)",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key="target_usl_input"
        )

    with input_col4:
        actual_paint_weight = st.number_input(
            "Actual Paint Weight (kg)",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key="actual_paint_weight_input"
        )

    with input_col5:
        current_temperature = st.number_input(
            "Current Temperature (°C)",
            min_value=0.0,
            value=0.0,
            step=0.5,
            key="current_temperature_input"
        )

    st.markdown("---")

    if st.button(
        "🚀 Calculate First Addition",
        type="primary",
        use_container_width=True
    ):
        st.session_state["sop_calculated"] = False
        st.session_state["sop_result"] = None
        st.session_state["step2_result"] = None

        if (
            current_visc <= 0
            or target_lsl <= 0
            or target_usl <= 0
            or actual_paint_weight <= 0
        ):
            st.error("⚠️ 請輸入完整且大於 0 的黏度、規格及實際塗料重量。")

        elif target_lsl >= target_usl:
            st.error("⚠️ LSL 必須小於 USL。")

        elif current_visc < target_lsl:
            st.error(
                "🚨 目前黏度低於規格下限（LSL）。"
                "不可添加稀釋劑，請通知製程工程師確認。"
            )

        elif current_visc <= target_usl:
            st.success(
                "✅ 目前黏度已在規格範圍內，不需添加稀釋劑。"
            )

        else:
            target_center = (target_lsl + target_usl) / 2
            required_drop = current_visc - target_center

            reference_info = get_reference_data(
                system_df,
                current_visc
            )

            reference_df = reference_info["reference_df"]

            if len(reference_df) < MIN_REFERENCE_RECORDS:
                st.error(
                    "🚨 歷史有效紀錄不足，系統無法提供安全建議。"
                    "請通知製程工程師。"
                )

            else:
                saturation_result = build_saturation_profile(reference_df)
                safety_limits = get_safety_limits(
                    reference_df,
                    saturation_result
                )

                ref_sensitivity = reference_df["Sensitivity"].median()
                sensitivity_p25 = reference_df["Sensitivity"].quantile(0.25)
                sensitivity_p75 = reference_df["Sensitivity"].quantile(0.75)

                required_ratio = required_drop / ref_sensitivity
                recommended_total_kg = (
                    actual_paint_weight
                    * required_ratio
                    / 100
                )

                first_add_kg = (
                    recommended_total_kg
                    * FIRST_ADD_PERCENT
                )

                first_add_ratio = (
                    required_ratio
                    * FIRST_ADD_PERCENT
                )

                warning_ratio = safety_limits["warning_ratio"]
                stop_ratio = safety_limits["stop_ratio"]

                blocked = False
                risk_status = ""
                risk_color = "green"

                if (
                    required_ratio > stop_ratio
                    or required_drop > safety_limits["drop_max"]
                ):
                    blocked = True
                    risk_status = (
                        "🚨 超過歷史停止比例或最大降黏範圍，"
                        "不可執行自動加料。"
                    )
                    risk_color = "red"

                elif (
                    required_ratio > warning_ratio
                    or required_drop > safety_limits["drop_p90"]
                ):
                    risk_status = (
                        "⚠️ 已進入警戒區，必須採分段添加並於每次添加後重新量測。"
                    )
                    risk_color = "orange"

                else:
                    risk_status = (
                        "✅ 正常作業區：建議第一次添加後重新量測。"
                    )
                    risk_color = "green"

                temperature_check = get_temperature_check(
                    reference_df,
                    current_temperature
                )

                st.markdown(
                    f"### 評估結果："
                    f"<span style='color:{risk_color}'>{risk_status}</span>",
                    unsafe_allow_html=True
                )

                if temperature_check["available"]:
                    st.caption(
                        f"歷史參考溫度："
                        f"{temperature_check['p25']:.1f} - "
                        f"{temperature_check['p75']:.1f}°C "
                        f"(Median: {temperature_check['median']:.1f}°C)"
                    )

                    if temperature_check["warning"]:
                        st.warning(
                            "⚠️ 目前溫度與歷史參考溫度差異較大。"
                            "本次建議僅可作為第一次添加起點，"
                            "必須以重新量測結果為準。"
                        )

                if blocked:
                    st.error(
                        "系統已阻擋自動加料。請檢查原料狀態、"
                        "塗料批次、溫度、攪拌時間或通知製程工程師。"
                    )

                else:
                    if reference_info["record_count"] >= 20:
                        confidence = "🟢 Historical Reference Available"
                    elif reference_info["record_count"] >= MIN_REFERENCE_RECORDS:
                        confidence = "🟡 Limited Historical Reference"
                    else:
                        confidence = "🟠 Insufficient Historical Support"

                    result_col1, result_col2, result_col3, result_col4 = st.columns(4)

                    result_col1.metric(
                        "Required Viscosity Drop",
                        f"{required_drop:.1f} s"
                    )

                    result_col2.metric(
                        "Estimated Total Ratio",
                        f"{required_ratio:.2f}%"
                    )

                    result_col3.metric(
                        "Warning / Stop Ratio",
                        f"{warning_ratio:.2f}% / {stop_ratio:.2f}%"
                    )

                    result_col4.metric(
                        "Data Confidence",
                        confidence
                    )

                    st.success(
                        f"### 第一次添加建議：{first_add_kg:.2f} kg"
                    )

                    st.markdown(
                        f"""
                        **現場操作：**

                        1. 實際塗料重量：`{actual_paint_weight:.1f} kg`  
                        2. 建議總添加比例：`{required_ratio:.2f}%`  
                        3. 第一次添加比例：`{first_add_ratio:.2f}%`  
                        4. 第一次添加量：`{first_add_kg:.2f} kg`  
                        5. 添加後攪拌至少：`{MIXING_TIME_MINUTES} 分鐘`  
                        6. 攪拌後重新量測黏度，再使用下方功能計算下一步。  
                        """
                    )

                    st.session_state["sop_calculated"] = True
                    st.session_state["sop_result"] = {
                        "initial_visc": current_visc,
                        "target_lsl": target_lsl,
                        "target_usl": target_usl,
                        "target_center": target_center,
                        "actual_paint_weight": actual_paint_weight,
                        "reference_source": reference_info["reference_source"],
                        "reference_record_count": reference_info["record_count"],
                        "reference_batch_count": reference_info["batch_count"],
                        "reference_sensitivity": ref_sensitivity,
                        "sensitivity_p25": sensitivity_p25,
                        "sensitivity_p75": sensitivity_p75,
                        "warning_ratio": warning_ratio,
                        "stop_ratio": stop_ratio,
                        "estimated_total_ratio": required_ratio,
                        "estimated_total_kg": recommended_total_kg,
                        "first_add_ratio": first_add_ratio,
                        "first_add_kg": first_add_kg
                    }

    # -----------------------------------------------------
    # STEP 2: RECALCULATE AFTER FIRST ADDITION
    # -----------------------------------------------------
    if st.session_state.get("sop_calculated", False):
        sop_result = st.session_state.get("sop_result")

        if sop_result:
            st.markdown("---")
            st.markdown("### 🔁 第二次計算：第一次添加後重新量測")

            st.caption(
                "請輸入實際第一次添加量與攪拌後的實測黏度。"
                "系統會使用本桶塗料實際反應重新估算後續添加量。"
            )

            step_col1, step_col2 = st.columns(2)

            with step_col1:
                actual_step1_kg = st.number_input(
                    "Actual First Addition (kg)",
                    min_value=0.0,
                    value=float(sop_result["first_add_kg"]),
                    step=0.1,
                    key="actual_step1_kg_input"
                )

            with step_col2:
                measured_after_step1 = st.number_input(
                    "Measured Viscosity After First Addition (s)",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    key="measured_after_step1_input"
                )

            if st.button(
                "Calculate Additional Solvent",
                type="secondary",
                use_container_width=True
            ):
                st.session_state["step2_result"] = None

                if actual_step1_kg <= 0 or measured_after_step1 <= 0:
                    st.error(
                        "⚠️ 請輸入第一次實際添加量與添加後實測黏度。"
                    )

                elif measured_after_step1 < sop_result["target_lsl"]:
                    st.error(
                        "🚨 添加後黏度已低於 LSL。"
                        "不可再添加稀釋劑，請通知製程工程師。"
                    )

                elif measured_after_step1 <= sop_result["target_usl"]:
                    st.success(
                        "✅ 添加後黏度已落入規格範圍，不需再添加稀釋劑。"
                    )

                elif measured_after_step1 >= sop_result["initial_visc"]:
                    st.error(
                        "🚨 第一次添加後黏度未下降。"
                        "請確認稀釋劑種類、攪拌時間、量測方法及原料狀態。"
                    )

                else:
                    actual_step1_ratio = (
                        actual_step1_kg
                        / sop_result["actual_paint_weight"]
                        * 100
                    )

                    observed_drop = (
                        sop_result["initial_visc"]
                        - measured_after_step1
                    )

                    observed_sensitivity = (
                        observed_drop
                        / actual_step1_ratio
                    )

                    safe_sensitivity = np.clip(
                        observed_sensitivity,
                        sop_result["sensitivity_p25"],
                        sop_result["sensitivity_p75"]
                    )

                    remaining_drop = (
                        measured_after_step1
                        - sop_result["target_center"]
                    )

                    additional_ratio = (
                        remaining_drop
                        / safe_sensitivity
                    )

                    additional_kg = (
                        sop_result["actual_paint_weight"]
                        * additional_ratio
                        / 100
                    )

                    total_ratio_after_step2 = (
                        actual_step1_ratio
                        + additional_ratio
                    )

                    remaining_ratio_to_stop = (
                        sop_result["stop_ratio"]
                        - actual_step1_ratio
                    )

                    second_step_blocked = False

                    if remaining_ratio_to_stop <= 0:
                        second_step_blocked = True
                        st.error(
                            "🚨 第一次添加後已接近或超過停止比例。"
                            "不可繼續添加稀釋劑。"
                        )

                    elif total_ratio_after_step2 > sop_result["stop_ratio"]:
                        second_step_blocked = True

                        max_additional_kg = (
                            sop_result["actual_paint_weight"]
                            * remaining_ratio_to_stop
                            / 100
                        )

                        st.error(
                            f"🚨 計算後仍需要 {additional_kg:.2f} kg，"
                            f"但距離停止比例僅剩 {max_additional_kg:.2f} kg。"
                            "不可繼續自動加料，請通知製程工程師。"
                        )

                    elif total_ratio_after_step2 > sop_result["warning_ratio"]:
                        st.warning(
                            "⚠️ 第二次添加後將進入警戒比例。"
                            "請將建議添加量再拆分成小量添加，"
                            "每次添加後均需重新量測。"
                        )

                    if not second_step_blocked:
                        step2_col1, step2_col2, step2_col3, step2_col4 = st.columns(4)

                        step2_col1.metric(
                            "Observed Sensitivity",
                            f"{observed_sensitivity:.2f} s/%"
                        )

                        step2_col2.metric(
                            "Safe Sensitivity Used",
                            f"{safe_sensitivity:.2f} s/%"
                        )

                        step2_col3.metric(
                            "Additional Ratio",
                            f"{additional_ratio:.2f}%"
                        )

                        step2_col4.metric(
                            "Additional Solvent",
                            f"{additional_kg:.2f} kg"
                        )

                        st.success(
                            f"### 建議下一次添加：{additional_kg:.2f} kg"
                        )

                        st.markdown(
                            """
                            **重要：** 此數值為第二次理論估算值。
                            若已進入警戒比例，請分成更小份量添加，
                            每次添加後均須重新量測黏度。
                            """
                        )

                        st.session_state["step2_result"] = {
                            "observed_sensitivity": observed_sensitivity,
                            "safe_sensitivity": safe_sensitivity,
                            "additional_ratio": additional_ratio,
                            "additional_kg": additional_kg,
                            "total_ratio_after_step2": total_ratio_after_step2
                        }


# =========================================================
# TAB 3: ENGINEERING MATRIX
# =========================================================
with tab3:
    st.markdown("### 🔬 Engineering Matrix")

    st.markdown(
        "This page is for engineering review. "
        "Tab 2 should be used for actual shop-floor execution."
    )

    eng_matrix = (
        system_df
        .groupby("Initial_Viscosity_Zone", observed=False)
        .agg(
            Adjustment_Records=("塗料批號", "size"),
            Paint_Batches=("塗料批號", "nunique"),
            Sensitivity_Median=("Sensitivity", "median"),
            Sensitivity_P25=("Sensitivity", lambda x: x.quantile(0.25)),
            Sensitivity_P75=("Sensitivity", lambda x: x.quantile(0.75)),
            Ratio_Median=("Solvent_Ratio_Percent", "median"),
            Ratio_P90=("Solvent_Ratio_Percent", lambda x: x.quantile(0.90)),
            Ratio_P95=("Solvent_Ratio_Percent", lambda x: x.quantile(0.95)),
            Drop_Median=("Delta_V", "median"),
            Drop_P90=("Delta_V", lambda x: x.quantile(0.90)),
            Drop_Max=("Delta_V", "max"),
            Temp_Median=("溫度", "median"),
            Temp_P25=("溫度", lambda x: x.quantile(0.25)),
            Temp_P75=("溫度", lambda x: x.quantile(0.75))
        )
        .reset_index()
    )

    eng_matrix["_zone_order"] = (
        eng_matrix["Initial_Viscosity_Zone"]
        .apply(get_zone_order)
    )

    eng_matrix = (
        eng_matrix
        .sort_values("_zone_order")
        .drop(columns="_zone_order")
    )

    st.dataframe(
        eng_matrix,
        column_config={
            "Initial_Viscosity_Zone": st.column_config.TextColumn(
                "Initial Viscosity Zone"
            ),
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
            "Sensitivity_P25": st.column_config.NumberColumn(
                "Sensitivity P25",
                format="%.2f"
            ),
            "Sensitivity_P75": st.column_config.NumberColumn(
                "Sensitivity P75",
                format="%.2f"
            ),
            "Ratio_Median": st.column_config.NumberColumn(
                "Median Total Ratio (%)",
                format="%.2f"
            ),
            "Ratio_P90": st.column_config.NumberColumn(
                "Warning Ratio P90 (%)",
                format="%.2f"
            ),
            "Ratio_P95": st.column_config.NumberColumn(
                "Stop Ratio P95 (%)",
                format="%.2f"
            ),
            "Drop_Median": st.column_config.NumberColumn(
                "Median Drop (s)",
                format="%.1f"
            ),
            "Drop_P90": st.column_config.NumberColumn(
                "Drop P90 (s)",
                format="%.1f"
            ),
            "Drop_Max": st.column_config.NumberColumn(
                "Maximum Drop (s)",
                format="%.1f"
            ),
            "Temp_Median": st.column_config.NumberColumn(
                "Median Temperature (°C)",
                format="%.1f"
            ),
            "Temp_P25": st.column_config.NumberColumn(
                "Temperature P25 (°C)",
                format="%.1f"
            ),
            "Temp_P75": st.column_config.NumberColumn(
                "Temperature P75 (°C)",
                format="%.1f"
            )
        },
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")
    st.markdown("### 📉 Saturation / Diminishing Returns by Initial Viscosity Zone")

    available_zones = sorted(
        system_df["Initial_Viscosity_Zone"].dropna().unique(),
        key=get_zone_order
    )

    selected_sat_zone = st.selectbox(
        "Select Initial Viscosity Zone for Saturation Analysis:",
        available_zones,
        key="saturation_zone_selector"
    )

    saturation_df = system_df[
        system_df["Initial_Viscosity_Zone"] == selected_sat_zone
    ].copy()

    saturation_result = build_saturation_profile(saturation_df)

    saturation_profile = saturation_result["profile"]

    sat_col1, sat_col2, sat_col3, sat_col4 = st.columns(4)

    sat_col1.metric(
        "Zone Records",
        f"{len(saturation_df):,}"
    )

    sat_col2.metric(
        "Baseline Sensitivity",
        (
            f"{saturation_result['baseline_sensitivity']:.2f} s/%"
            if not pd.isna(saturation_result["baseline_sensitivity"])
            else "Not Detected"
        )
    )

    sat_col3.metric(
        "Diminishing Return Threshold",
        (
            f"{saturation_result['warning_ratio']:.2f}%"
            if not pd.isna(saturation_result["warning_ratio"])
            else "Not Detected"
        )
    )

    sat_col4.metric(
        "Saturation Stop Threshold",
        (
            f"{saturation_result['saturation_ratio']:.2f}%"
            if not pd.isna(saturation_result["saturation_ratio"])
            else "Not Detected"
        )
    )

    if saturation_profile.empty:
        st.warning("No saturation profile available for this viscosity zone.")

    else:
        st.dataframe(
            saturation_profile,
            column_config={
                "Ratio_Zone": st.column_config.TextColumn(
                    "Solvent Ratio Zone"
                ),
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
                    "Minimum Ratio (%)",
                    format="%.2f"
                ),
                "Ratio_Max": st.column_config.NumberColumn(
                    "Maximum Ratio (%)",
                    format="%.2f"
                ),
                "DeltaV_Median": st.column_config.NumberColumn(
                    "Median Drop (s)",
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
                ),
                "Saturation_Status": st.column_config.TextColumn(
                    "Efficiency Status"
                )
            },
            use_container_width=True,
            hide_index=True
        )

    st.caption(
        "飽和分析已依初始黏度區間分開計算，避免將高黏度與低黏度調整紀錄直接混合比較。"
    )


# =========================================================
# TAB 4: MASTER SHOP FLOOR SOP
# =========================================================
with tab4:
    st.markdown("### 🖨️ 現場歷史加料參考 SOP")

    st.warning(
        "操作順序：查詢相同條件 → 輸入實際塗料重量 → "
        "依建議首次添加比例加料 → 攪拌5分鐘 → 重新量測。"
        "累積添加比例不得超過停止比例。"
    )

    st.caption(
        "註：稀釋劑比例以實際塗料重量為基準。"
        "歷史中位添加量僅作為資料驗證，不得視為固定加料量。"
    )

    # Tab 4 uses all valid Group A records.
    matrix_df = valid_df.copy()

    if matrix_df.empty:
        st.warning("無有效 Group A 調整資料可建立現場 SOP。")
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
            temp_df
            .groupby(group_cols)["黏度(秒)"]
            .transform("max")
        )

        def worker_zone(viscosity):
            if viscosity <= 70:
                return "<=70"
            elif viscosity <= 90:
                return "71-90"
            elif viscosity <= 110:
                return "91-110"
            elif viscosity <= 130:
                return "111-130"
            else:
                return ">130"

        temp_df["Worker_Viscosity_Zone"] = (
            temp_df["黏度(秒)"]
            .apply(worker_zone)
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

    group_cols_worker = [
        "Resin",
        "Position_UI",
        "Vendor",
        "Solvent_Type",
        "Worker_Viscosity_Zone"
    ]

    worker_sop = (
        matrix_df
        .groupby(group_cols_worker, observed=False)
        .agg(
            Adjustment_Records=("塗料批號", "size"),
            History_Batches=("塗料批號", "nunique"),
            Ref_Start_Visc=("黏度(秒)", "median"),
            Ref_Paint_Weight_kg=("塗料重量", "median"),
            Ref_Solvent_Add_kg=("添加重量", "median"),
            Historical_Total_Ratio=("Solvent_Ratio_Percent", "median"),
            First_Add_Ratio=(
                "Solvent_Ratio_Percent",
                lambda x: x.median() * FIRST_ADD_PERCENT
            ),
            Final_Visc_P25=("黏度(秒)_1", lambda x: x.quantile(0.25)),
            Final_Visc_P75=("黏度(秒)_1", lambda x: x.quantile(0.75)),
            Ratio_P90=("Solvent_Ratio_Percent", lambda x: x.quantile(0.90)),
            Ratio_P95=("Solvent_Ratio_Percent", lambda x: x.quantile(0.95)),
            Temperature_P25=("溫度", lambda x: x.quantile(0.25)),
            Temperature_P75=("溫度", lambda x: x.quantile(0.75))
        )
        .reset_index()
    )

    # Keep all valid historical combinations as references.
    # Low batch count does not automatically mean that the data is unusable.
    if worker_sop.empty:
        st.warning("無有效歷史資料可建立現場參考表。")
        st.stop()

    worker_sop["Historical_Final_Visc_Range"] = (
        worker_sop.apply(
            lambda row: format_range(
                row["Final_Visc_P25"],
                row["Final_Visc_P75"],
                decimals=1
            ),
            axis=1
        )
    )

    worker_sop["Historical_Temp_Range"] = (
        worker_sop.apply(
            lambda row: format_range(
                row["Temperature_P25"],
                row["Temperature_P75"],
                decimals=1
            ),
            axis=1
        )
    )

    # -----------------------------------------------------
    # Calculate warning / stop ratios per exact worker zone
    # -----------------------------------------------------
    saturation_summary = []

    system_keys = matrix_df[
        [
            "Resin",
            "Position_UI",
            "Vendor",
            "Solvent_Type",
            "Worker_Viscosity_Zone"
        ]
    ].drop_duplicates()

    for _, system_row in system_keys.iterrows():
        temp_zone_df = matrix_df[
            (matrix_df["Resin"] == system_row["Resin"])
            & (matrix_df["Position_UI"] == system_row["Position_UI"])
            & (matrix_df["Vendor"] == system_row["Vendor"])
            & (matrix_df["Solvent_Type"] == system_row["Solvent_Type"])
            & (
                matrix_df["Worker_Viscosity_Zone"]
                == system_row["Worker_Viscosity_Zone"]
            )
        ].copy()

        temp_saturation = build_saturation_profile(temp_zone_df)
        temp_limits = get_safety_limits(
            temp_zone_df,
            temp_saturation
        )

        saturation_summary.append({
            "Resin": system_row["Resin"],
            "Position_UI": system_row["Position_UI"],
            "Vendor": system_row["Vendor"],
            "Solvent_Type": system_row["Solvent_Type"],
            "Worker_Viscosity_Zone": system_row["Worker_Viscosity_Zone"],
            "Saturation_Warning_Ratio": temp_limits["warning_ratio"],
            "Saturation_Stop_Ratio": temp_limits["stop_ratio"]
        })

    saturation_summary_df = pd.DataFrame(saturation_summary)

    worker_sop = worker_sop.merge(
        saturation_summary_df,
        on=[
            "Resin",
            "Position_UI",
            "Vendor",
            "Solvent_Type",
            "Worker_Viscosity_Zone"
        ],
        how="left"
    )

    # Fallback when no saturation profile can be detected.
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

    worker_sop["塗裝位置"] = (
        worker_sop["Position_UI"]
        .map({
            "Primer": "底漆 (P)",
            "Top Finish": "正面漆 (TF)",
            "Back Finish": "背面漆 (BF)"
        })
        .fillna(worker_sop["Position_UI"])
    )

    # =========================================================
    # Worker SOP output table
    # =========================================================
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
            "Historical_Total_Ratio",
            "First_Add_Ratio",
            "Historical_Final_Visc_Range",
            "Historical_Temp_Range",
            "Saturation_Warning_Ratio",
            "Saturation_Stop_Ratio"
        ]
    ].copy()

    worker_output = worker_output.rename(columns={
        "Resin": "樹脂種類",
        "Vendor": "塗料供應商",
        "Solvent_Type": "稀釋劑種類",
        "Worker_Viscosity_Zone": "初始黏度區間",
        "Adjustment_Records": "有效調整紀錄數",
        "History_Batches": "涉及塗料批號數",
        "Ref_Start_Visc": "參考起始黏度",
        "Historical_Total_Ratio": "歷史總添加比例",
        "First_Add_Ratio": "建議首次添加比例",
        "Historical_Final_Visc_Range": "歷史最終黏度範圍",
        "Historical_Temp_Range": "歷史參考溫度範圍",
        "Saturation_Warning_Ratio": "累積添加警戒比例",
        "Saturation_Stop_Ratio": "累積添加停止比例"
    })

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
            "歷史總添加比例": st.column_config.NumberColumn(
                "歷史總添加比例 (%)",
                format="%.2f"
            ),
            "建議首次添加比例": st.column_config.NumberColumn(
                "建議首次添加比例 (%)",
                format="%.2f"
            ),
            "歷史最終黏度範圍": st.column_config.TextColumn(
                "歷史最終黏度範圍 (P25-P75)"
            ),
            "歷史參考溫度範圍": st.column_config.TextColumn(
                "歷史參考溫度範圍 (°C, P25-P75)"
            ),
            "累積添加警戒比例": st.column_config.NumberColumn(
                "累積添加警戒比例 (%)",
                format="%.2f"
            ),
            "累積添加停止比例": st.column_config.NumberColumn(
                "累積添加停止比例 (%)",
                format="%.2f"
            )
        },
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")
    st.markdown("### 現場 SOP 使用方式")

    st.markdown(
        """
        1. 先確認樹脂、塗裝位置、供應商及稀釋劑種類。  
        2. 量測目前黏度，查詢相對應的初始黏度區間。  
        3. 輸入或秤量實際塗料重量。  
        4. 第一次添加量 = 實際塗料重量 × 建議首次添加比例 ÷ 100。  
        5. 攪拌至少 5 分鐘後重新量測黏度。  
        6. 若仍高於 USL，回到 Tab 2 依實測結果計算下一次添加量。  
        7. 累積添加比例不得超過「累積添加停止比例」。  
        """
    )

    st.caption(
        "「歷史總添加比例」與「歷史最終黏度範圍」僅用於工程確認及現場參考。"
        "實際作業應以 Tab 2 的目前黏度、規格範圍、實際塗料重量及重新量測結果為準。"
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
