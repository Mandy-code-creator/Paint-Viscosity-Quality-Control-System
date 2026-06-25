```python
import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np


# =========================================================
# [S00] PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="Solvent Analysis",
    page_icon="🧪",
    layout="wide"
)

st.title("🧪 Solvent Sensitivity & SOP Recommendation System")
st.caption(
    "Historical dilution analysis grouped by Resin, Vendor, "
    "Solvent Type, and Initial Viscosity Zone."
)
st.markdown("---")


# =========================================================
# [S01] GLOBAL CONSTANTS
# =========================================================
MIN_OPERATING_PAINT_KG = 120.0

MIN_RECORDS_FOR_REFERENCE = 3
MIN_RECORDS_FOR_RECOMMENDATION = 5
MIN_RECORDS_RELIABLE = 10

STAGE_1_PERCENT = 0.60
STAGE_2_PERCENT = 0.25
STAGE_3_PERCENT = 0.15

VISCOSITY_ZONE_ORDER = [
    "≤70 s",
    "71–90 s",
    "91–110 s",
    "111–130 s",
    ">130 s"
]


# =========================================================
# [S02] DATA VALIDATION
# =========================================================
if (
    "raw_data_loaded" not in st.session_state
    or not st.session_state["raw_data_loaded"]
):
    st.warning("⚠️ Please upload data on the main page first.")
    st.stop()

if "group_a_data" not in st.session_state:
    st.error("❌ Group A data is not available.")
    st.stop()

group_a_raw = st.session_state["group_a_data"].copy()
rejected_data = st.session_state.get("rejected_data", pd.DataFrame())


# =========================================================
# [S03] HELPER FUNCTIONS
# =========================================================
def safe_quantile(series, q, default=np.nan):
    clean_series = pd.to_numeric(series, errors="coerce").dropna()

    if clean_series.empty:
        return default

    return clean_series.quantile(q)


def normalize_text(series, default_value="Unknown"):
    return (
        series.fillna(default_value)
        .astype(str)
        .str.strip()
        .replace("", default_value)
    )


def get_data_confidence(record_count):
    if record_count >= MIN_RECORDS_RELIABLE:
        return "Reliable", "✅"

    if record_count >= MIN_RECORDS_FOR_RECOMMENDATION:
        return "Usable with Caution", "⚠️"

    if record_count >= MIN_RECORDS_FOR_REFERENCE:
        return "Limited Data", "🟡"

    return "Insufficient Data", "🔴"


def get_recommendation_confidence(record_count, match_type):
    if record_count >= MIN_RECORDS_RELIABLE and match_type == "zone":
        return "High Confidence", "green"

    if record_count >= MIN_RECORDS_FOR_RECOMMENDATION and match_type in [
        "zone",
        "general"
    ]:
        return "Medium Confidence", "orange"

    return "Low Confidence", "red"


def create_viscosity_zone(series):
    return pd.cut(
        pd.to_numeric(series, errors="coerce"),
        bins=[-np.inf, 70, 90, 110, 130, np.inf],
        labels=[
            "≤70 s",
            "71–90 s",
            "91–110 s",
            "111–130 s",
            ">130 s"
        ],
        include_lowest=True
    )


def get_zone_sort_value(zone):
    zone_map = {
        "≤70 s": 1,
        "71–90 s": 2,
        "91–110 s": 3,
        "111–130 s": 4,
        ">130 s": 5
    }

    return zone_map.get(str(zone), 999)


def get_current_viscosity_zone(current_viscosity):
    if current_viscosity <= 70:
        return "≤70 s"

    if current_viscosity <= 90:
        return "71–90 s"

    if current_viscosity <= 110:
        return "91–110 s"

    if current_viscosity <= 130:
        return "111–130 s"

    return ">130 s"


# =========================================================
# [S04] DATA PREPROCESSING
# =========================================================
required_columns = [
    "Resin",
    "Vendor",
    "稀釋劑",
    "黏度(秒)",
    "黏度(秒)_1",
    "添加重量",
    "塗料重量"
]

missing_columns = [
    col
    for col in required_columns
    if col not in group_a_raw.columns
]

if missing_columns:
    st.error(
        f"❌ Missing required columns: {', '.join(missing_columns)}"
    )
    st.stop()

group_a = group_a_raw.copy()

numeric_columns = [
    "添加重量",
    "塗料重量",
    "黏度(秒)",
    "黏度(秒)_1",
    "溫度",
    "濕度"
]

for col in numeric_columns:
    if col in group_a.columns:
        group_a[col] = pd.to_numeric(
            group_a[col],
            errors="coerce"
        )

if "溫度" not in group_a.columns:
    group_a["溫度"] = np.nan

if "濕度" not in group_a.columns:
    group_a["濕度"] = np.nan

if "塗料批號" not in group_a.columns:
    group_a["塗料批號"] = group_a.index.astype(str)

group_a["Resin"] = normalize_text(group_a["Resin"])
group_a["Vendor"] = normalize_text(group_a["Vendor"])
group_a["Solvent_Type"] = normalize_text(group_a["稀釋劑"])


# =========================================================
# [S05] CORE CALCULATIONS
# =========================================================

# ---------------------------------------------------------
# [S05.01] Dilution calculation base paint
# 塗料重量 = order paint quantity
# Dilution Base = 塗料重量 + 120 kg
# ---------------------------------------------------------
group_a["Minimum_Operating_Paint_kg"] = MIN_OPERATING_PAINT_KG

group_a["Dilution_Base_Paint_kg"] = (
    group_a["塗料重量"]
    + group_a["Minimum_Operating_Paint_kg"]
)

# ---------------------------------------------------------
# [S05.02] Solvent ratio
# ---------------------------------------------------------
group_a["Solvent_Ratio_Percent"] = (
    group_a["添加重量"]
    / group_a["Dilution_Base_Paint_kg"].replace(0, np.nan)
) * 100

# ---------------------------------------------------------
# [S05.03] Viscosity reduction
# ---------------------------------------------------------
group_a["Delta_V"] = (
    group_a["黏度(秒)"]
    - group_a["黏度(秒)_1"]
)

# ---------------------------------------------------------
# [S05.04] Solvent sensitivity
# ---------------------------------------------------------
group_a["Sensitivity"] = (
    group_a["Delta_V"]
    / group_a["Solvent_Ratio_Percent"].replace(0, np.nan)
)

# ---------------------------------------------------------
# [S05.05] Fixed initial viscosity zones
# ---------------------------------------------------------
group_a["Viscosity_Zone"] = create_viscosity_zone(
    group_a["黏度(秒)"]
)

group_a["Zone_Sort"] = group_a["Viscosity_Zone"].apply(
    get_zone_sort_value
)


# =========================================================
# [S06] VALID RECORD FILTER
# =========================================================
analysis_df = group_a[
    (group_a["添加重量"] > 0) &
    (group_a["塗料重量"] > 0) &
    (group_a["Dilution_Base_Paint_kg"] > 0) &
    (group_a["Solvent_Ratio_Percent"] > 0) &
    (group_a["Delta_V"] > 0) &
    (group_a["Sensitivity"] > 0) &
    (group_a["Resin"] != "Unknown") &
    (group_a["Vendor"] != "Unknown") &
    (group_a["Solvent_Type"] != "Unknown")
].copy()

# ---------------------------------------------------------
# [S06.01] Remove global sensitivity outliers
# ---------------------------------------------------------
if not analysis_df.empty:
    sensitivity_p01 = analysis_df["Sensitivity"].quantile(0.01)
    sensitivity_p99 = analysis_df["Sensitivity"].quantile(0.99)

    analysis_df = analysis_df[
        (analysis_df["Sensitivity"] >= sensitivity_p01) &
        (analysis_df["Sensitivity"] <= sensitivity_p99)
    ].copy()

if analysis_df.empty:
    st.warning(
        "⚠️ No valid dilution records found. "
        "Please check paint quantity, solvent quantity, viscosity, "
        "Resin, Vendor, and Solvent Type."
    )
    st.stop()


# =========================================================
# [S07] SOP MATRIX BUILD
# Grouping:
# Resin + Vendor + Solvent Type + Initial Viscosity Zone
# =========================================================
sop_matrix = (
    analysis_df
    .groupby(
        [
            "Resin",
            "Vendor",
            "Solvent_Type",
            "Viscosity_Zone",
            "Zone_Sort"
        ],
        observed=False,
        dropna=False
    )
    .agg(
        Typical_Target_V=("黏度(秒)_1", "median"),

        Historical_Low_V_P10=(
            "黏度(秒)_1",
            lambda x: safe_quantile(x, 0.10)
        ),

        Historical_High_V_P90=(
            "黏度(秒)_1",
            lambda x: safe_quantile(x, 0.90)
        ),

        Historical_Ratio_Median=(
            "Solvent_Ratio_Percent",
            "median"
        ),

        Historical_Ratio_P90=(
            "Solvent_Ratio_Percent",
            lambda x: safe_quantile(x, 0.90)
        ),

        Historical_Ratio_P95=(
            "Solvent_Ratio_Percent",
            lambda x: safe_quantile(x, 0.95)
        ),

        Typical_Viscosity_Drop=(
            "Delta_V",
            "median"
        ),

        Viscosity_Drop_P10=(
            "Delta_V",
            lambda x: safe_quantile(x, 0.10)
        ),

        Viscosity_Drop_P90=(
            "Delta_V",
            lambda x: safe_quantile(x, 0.90)
        ),

        Max_Historical_Drop=(
            "Delta_V",
            "max"
        ),

        Median_Sensitivity=(
            "Sensitivity",
            "median"
        ),

        Sensitivity_Std=(
            "Sensitivity",
            "std"
        ),

        Records_in_Zone=(
            "塗料批號",
            "size"
        )
    )
    .reset_index()
)

# ---------------------------------------------------------
# [S07.01] Solvent factor per 1 second viscosity reduction
# ---------------------------------------------------------
sop_matrix["Factor_kg_per_100kg_per_1s"] = np.where(
    sop_matrix["Median_Sensitivity"] > 0,
    1 / sop_matrix["Median_Sensitivity"],
    np.nan
)

# ---------------------------------------------------------
# [S07.02] Draft SOP coefficients
# ---------------------------------------------------------
sop_matrix["Typical_Total_Coeff_kg_per_100kg"] = (
    sop_matrix["Historical_Ratio_Median"]
)

sop_matrix["Draft_Stage_1_Coeff_kg_per_100kg"] = (
    sop_matrix["Typical_Total_Coeff_kg_per_100kg"]
    * STAGE_1_PERCENT
)

sop_matrix["Draft_Stage_2_Coeff_kg_per_100kg"] = (
    sop_matrix["Typical_Total_Coeff_kg_per_100kg"]
    * STAGE_2_PERCENT
)

sop_matrix["Draft_Fine_Adjust_Coeff_kg_per_100kg"] = (
    sop_matrix["Typical_Total_Coeff_kg_per_100kg"]
    * STAGE_3_PERCENT
)

sop_matrix["Draft_Max_Total_Coeff_kg_per_100kg"] = (
    sop_matrix["Historical_Ratio_P90"]
)

# ---------------------------------------------------------
# [S07.03] Data confidence
# ---------------------------------------------------------
sop_matrix["Data_Confidence"] = (
    sop_matrix["Records_in_Zone"]
    .apply(lambda x: get_data_confidence(x)[0])
)

sop_matrix["Confidence_Icon"] = (
    sop_matrix["Records_in_Zone"]
    .apply(lambda x: get_data_confidence(x)[1])
)

sop_matrix = sop_matrix[
    sop_matrix["Records_in_Zone"]
    >= MIN_RECORDS_FOR_REFERENCE
].copy()


# =========================================================
# [S08] KPI AREA
# =========================================================
st.subheader("💡 Historical Mixing Data Overview")

kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

with kpi_col1:
    st.metric(
        "Total Records",
        f"{len(group_a):,}"
    )

with kpi_col2:
    st.metric(
        "Valid Adjustment Records",
        f"{len(analysis_df):,}"
    )

with kpi_col3:
    st.metric(
        "Total Order Paint",
        f"{group_a['塗料重量'].sum():,.2f} kg"
    )

with kpi_col4:
    st.metric(
        "Rejected / Invalid Records",
        f"{len(rejected_data):,}"
    )

st.info(
    f"Calculation rule: Dilution Base Paint = 塗料重量 + "
    f"{MIN_OPERATING_PAINT_KG:.0f} kg."
)

st.markdown("---")


# =========================================================
# [S09] MAIN FILTERS
# Resin → Vendor → Solvent Type
# =========================================================
filter_col1, filter_col2, filter_col3 = st.columns(3)

available_resins = sorted(
    analysis_df["Resin"]
    .dropna()
    .unique()
    .tolist()
)

with filter_col1:
    selected_resin = st.selectbox(
        "Select Resin",
        available_resins
    )

available_vendors = sorted(
    analysis_df.loc[
        analysis_df["Resin"] == selected_resin,
        "Vendor"
    ]
    .dropna()
    .unique()
    .tolist()
)

with filter_col2:
    selected_vendor = st.selectbox(
        "Select Vendor",
        available_vendors
    )

available_solvents = sorted(
    analysis_df.loc[
        (
            analysis_df["Resin"] == selected_resin
        ) &
        (
            analysis_df["Vendor"] == selected_vendor
        ),
        "Solvent_Type"
    ]
    .dropna()
    .unique()
    .tolist()
)

with filter_col3:
    selected_solvent = st.selectbox(
        "Select Solvent Type",
        available_solvents
    )

filtered_data = analysis_df[
    (analysis_df["Resin"] == selected_resin) &
    (analysis_df["Vendor"] == selected_vendor) &
    (analysis_df["Solvent_Type"] == selected_solvent)
].copy()

filtered_sop = sop_matrix[
    (sop_matrix["Resin"] == selected_resin) &
    (sop_matrix["Vendor"] == selected_vendor) &
    (sop_matrix["Solvent_Type"] == selected_solvent)
].copy()


# =========================================================
# [S10] TAB 1 - HISTORICAL ANALYSIS
# =========================================================
# [S10.01] Create tabs
tab_analysis, tab_sop, tab_matrix = st.tabs([
    "📊 Historical Analysis",
    "🧠 SOP Recommendation",
    "📚 SOP Matrix"
])

# ---------------------------------------------------------
# [S10.02] Historical charts
# ---------------------------------------------------------
with tab_analysis:
    st.markdown("### 📊 Historical Dilution Behavior")

    if filtered_data.empty:
        st.info("No valid records for the selected group.")

    else:
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.markdown(
                "#### Solvent Ratio vs. Viscosity Reduction"
            )

            fig_ratio_delta = px.scatter(
                filtered_data,
                x="Solvent_Ratio_Percent",
                y="Delta_V",
                color="Viscosity_Zone",
                category_orders={
                    "Viscosity_Zone": VISCOSITY_ZONE_ORDER
                },
                hover_data=[
                    "黏度(秒)",
                    "黏度(秒)_1",
                    "添加重量",
                    "塗料重量",
                    "Dilution_Base_Paint_kg",
                    "溫度",
                    "濕度"
                ],
                labels={
                    "Solvent_Ratio_Percent": "Solvent Ratio (%)",
                    "Delta_V": "Viscosity Drop (s)",
                    "Viscosity_Zone": "Initial Viscosity Zone"
                }
            )

            fig_ratio_delta.update_layout(
                margin=dict(l=20, r=20, t=35, b=20)
            )

            st.plotly_chart(
                fig_ratio_delta,
                use_container_width=True
            )

        with chart_col2:
            st.markdown(
                "#### Viscosity Drop by Initial Viscosity Zone"
            )

            fig_delta_box = px.box(
                filtered_data,
                x="Viscosity_Zone",
                y="Delta_V",
                points="all",
                category_orders={
                    "Viscosity_Zone": VISCOSITY_ZONE_ORDER
                },
                labels={
                    "Viscosity_Zone": "Initial Viscosity Zone",
                    "Delta_V": "Actual Viscosity Drop (s)"
                }
            )

            fig_delta_box.update_layout(
                margin=dict(l=20, r=20, t=35, b=20)
            )

            st.plotly_chart(
                fig_delta_box,
                use_container_width=True
            )

        chart_col3, chart_col4 = st.columns(2)

        with chart_col3:
            st.markdown(
                "#### Solvent Ratio vs. Dilution Efficiency"
            )

            fig_efficiency = px.scatter(
                filtered_data,
                x="Solvent_Ratio_Percent",
                y="Sensitivity",
                color="Viscosity_Zone",
                category_orders={
                    "Viscosity_Zone": VISCOSITY_ZONE_ORDER
                },
                hover_data=[
                    "黏度(秒)",
                    "黏度(秒)_1",
                    "Delta_V"
                ],
                labels={
                    "Solvent_Ratio_Percent": "Solvent Ratio (%)",
                    "Sensitivity": "Sensitivity (s / %)",
                    "Viscosity_Zone": "Initial Viscosity Zone"
                }
            )

            fig_efficiency.update_layout(
                margin=dict(l=20, r=20, t=35, b=20)
            )

            st.plotly_chart(
                fig_efficiency,
                use_container_width=True
            )

        with chart_col4:
            st.markdown(
                "#### After-Dilution Viscosity Distribution"
            )

            fig_after_v = px.box(
                filtered_data,
                x="Viscosity_Zone",
                y="黏度(秒)_1",
                points="all",
                category_orders={
                    "Viscosity_Zone": VISCOSITY_ZONE_ORDER
                },
                labels={
                    "Viscosity_Zone": "Initial Viscosity Zone",
                    "黏度(秒)_1": "After-Dilution Viscosity (s)"
                }
            )

            fig_after_v.update_layout(
                margin=dict(l=20, r=20, t=35, b=20)
            )

            st.plotly_chart(
                fig_after_v,
                use_container_width=True
            )

        st.caption(
            "This page shows historical dilution behavior only. "
            "The current dataset does not include surface quality PASS/NG, "
            "gloss, color difference, film thickness, or appearance defects."
        )


# =========================================================
# [S11] TAB 2 - SOP RECOMMENDATION
# =========================================================
with tab_sop:
    st.markdown("### 🧠 Solvent Recommendation")

    if filtered_data.empty:
        st.warning(
            "⚠️ No valid history exists for the selected "
            "Resin, Vendor, and Solvent Type."
        )

    elif filtered_sop.empty:
        st.warning(
            "⚠️ No viscosity zone has at least 3 records "
            "for this group."
        )

    else:
        # -------------------------------------------------
        # [S11.01] User inputs
        # -------------------------------------------------
        input_col1, input_col2, input_col3, input_col4 = st.columns(4)

        with input_col1:
            current_viscosity = st.number_input(
                "Current Viscosity (s)",
                value=90.00,
                step=1.00,
                format="%.2f"
            )

        with input_col2:
            approved_lsl = st.number_input(
                "Approved Viscosity Lower Limit (s)",
                value=float(
                    filtered_data["黏度(秒)_1"]
                    .quantile(0.25)
                ),
                step=1.00,
                format="%.2f"
            )

        with input_col3:
            approved_usl = st.number_input(
                "Approved Viscosity Upper Limit (s)",
                value=float(
                    filtered_data["黏度(秒)_1"]
                    .quantile(0.75)
                ),
                step=1.00,
                format="%.2f"
            )

        with input_col4:
            order_paint_weight = st.number_input(
                "Order Paint Weight (kg)",
                value=80.00,
                min_value=0.00,
                step=1.00,
                format="%.2f"
            )

        # -------------------------------------------------
        # [S11.02] Dilution base calculation
        # -------------------------------------------------
        dilution_base_paint = (
            order_paint_weight
            + MIN_OPERATING_PAINT_KG
        )

        base_col1, base_col2, base_col3 = st.columns(3)

        with base_col1:
            st.metric(
                "Order Paint Weight",
                f"{order_paint_weight:.2f} kg"
            )

        with base_col2:
            st.metric(
                "Minimum Operating Paint",
                f"{MIN_OPERATING_PAINT_KG:.2f} kg"
            )

        with base_col3:
            st.metric(
                "Dilution Calculation Total",
                f"{dilution_base_paint:.2f} kg"
            )

        # -------------------------------------------------
        # [S11.03] Recommendation calculation
        # -------------------------------------------------
        if approved_lsl >= approved_usl:
            st.error(
                "❌ Approved lower limit must be less than "
                "approved upper limit."
            )

        else:
            target_viscosity = (
                approved_lsl
                + approved_usl
            ) / 2

            required_delta_v = (
                current_viscosity
                - target_viscosity
            )

            if required_delta_v <= 0:
                st.success(
                    "✅ Current viscosity is already within or "
                    "below the target range."
                )

            else:
                current_zone = get_current_viscosity_zone(
                    current_viscosity
                )

                zone_data = filtered_data[
                    filtered_data["Viscosity_Zone"].astype(str)
                    == current_zone
                ].copy()

                expected_sensitivity = np.nan
                reference_data = pd.DataFrame()
                match_type = ""

                if len(zone_data) >= MIN_RECORDS_FOR_RECOMMENDATION:
                    expected_sensitivity = zone_data[
                        "Sensitivity"
                    ].median()

                    reference_data = zone_data
                    match_type = "zone"

                elif len(filtered_data) >= MIN_RECORDS_FOR_RECOMMENDATION:
                    expected_sensitivity = filtered_data[
                        "Sensitivity"
                    ].median()

                    reference_data = filtered_data
                    match_type = "general"

                if (
                    pd.isna(expected_sensitivity)
                    or expected_sensitivity <= 0
                ):
                    st.error(
                        "❌ Insufficient historical records for "
                        "automatic recommendation. At least 5 valid "
                        "records are required."
                    )

                else:
                    record_count = len(reference_data)

                    confidence_label, confidence_color = (
                        get_recommendation_confidence(
                            record_count,
                            match_type
                        )
                    )

                    required_ratio = (
                        required_delta_v
                        / expected_sensitivity
                    )

                    total_solvent_kg = (
                        dilution_base_paint
                        * required_ratio
                        / 100
                    )

                    stage_1_kg = (
                        total_solvent_kg
                        * STAGE_1_PERCENT
                    )

                    stage_2_kg = (
                        total_solvent_kg
                        * STAGE_2_PERCENT
                    )

                    stage_3_kg = (
                        total_solvent_kg
                        * STAGE_3_PERCENT
                    )

                    ratio_p90 = safe_quantile(
                        reference_data["Solvent_Ratio_Percent"],
                        0.90
                    )

                    ratio_p95 = safe_quantile(
                        reference_data["Solvent_Ratio_Percent"],
                        0.95
                    )

                    drop_p90 = safe_quantile(
                        reference_data["Delta_V"],
                        0.90
                    )

                    max_drop = safe_quantile(
                        reference_data["Delta_V"],
                        1.00
                    )

                    # -------------------------------------
                    # [S11.04] Recommendation result card
                    # -------------------------------------
                    st.markdown(
                        f"""
                        <div style="
                            background-color:#F8F9FA;
                            padding:20px;
                            border-radius:8px;
                            border-left:6px solid #4472C4;
                            margin-top:15px;
                        ">
                            <h3 style="margin-top:0;">
                                Recommended Total Solvent:
                                <span style="color:#4472C4;">
                                    {total_solvent_kg:.2f} kg
                                </span>
                            </h3>
                            <p><b>Main SOP Group:</b> {selected_resin} + {selected_vendor} + {selected_solvent}</p>
                            <p><b>Matched Viscosity Zone:</b> {current_zone}</p>
                            <p><b>Target Center:</b> {target_viscosity:.2f} s</p>
                            <p><b>Required Viscosity Drop:</b> {required_delta_v:.2f} s</p>
                            <p><b>Historical Sensitivity Used:</b> {expected_sensitivity:.2f} s/%</p>
                            <p><b>Calculated Solvent Ratio:</b> {required_ratio:.2f}%</p>
                            <p><b>Reference Records:</b> {record_count}</p>
                            <p>
                                <b>Confidence:</b>
                                <span style="color:{confidence_color}; font-weight:bold;">
                                    {confidence_label}
                                </span>
                            </p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    # -------------------------------------
                    # [S11.05] Staged addition result
                    # -------------------------------------
                    st.markdown(
                        "#### Recommended Staged Addition"
                    )

                    stage_col1, stage_col2, stage_col3 = st.columns(3)

                    with stage_col1:
                        st.metric(
                            "Stage 1: Initial Addition",
                            f"{stage_1_kg:.2f} kg",
                            f"{STAGE_1_PERCENT * 100:.0f}% of total"
                        )

                    with stage_col2:
                        st.metric(
                            "Stage 2: After Re-check",
                            f"{stage_2_kg:.2f} kg",
                            f"{STAGE_2_PERCENT * 100:.0f}% of total"
                        )

                    with stage_col3:
                        st.metric(
                            "Stage 3: Fine Adjustment",
                            f"{stage_3_kg:.2f} kg",
                            f"{STAGE_3_PERCENT * 100:.0f}% of total"
                        )

                    # -------------------------------------
                    # [S11.06] Historical safety references
                    # -------------------------------------
                    st.markdown(
                        "#### Historical Safety Reference"
                    )

                    ref_col1, ref_col2, ref_col3, ref_col4 = st.columns(4)

                    with ref_col1:
                        st.metric(
                            "Historical Ratio P90",
                            (
                                f"{ratio_p90:.2f}%"
                                if not pd.isna(ratio_p90)
                                else "N/A"
                            )
                        )

                    with ref_col2:
                        st.metric(
                            "Historical Ratio P95",
                            (
                                f"{ratio_p95:.2f}%"
                                if not pd.isna(ratio_p95)
                                else "N/A"
                            )
                        )

                    with ref_col3:
                        st.metric(
                            "Historical Drop P90",
                            (
                                f"{drop_p90:.2f} s"
                                if not pd.isna(drop_p90)
                                else "N/A"
                            )
                        )

                    with ref_col4:
                        st.metric(
                            "Historical Max Drop",
                            (
                                f"{max_drop:.2f} s"
                                if not pd.isna(max_drop)
                                else "N/A"
                            )
                        )

                    # -------------------------------------
                    # [S11.07] Warning rules
                    # -------------------------------------
                    if (
                        not pd.isna(ratio_p90)
                        and required_ratio > ratio_p90
                    ):
                        st.warning(
                            "⚠️ Required solvent ratio exceeds historical "
                            "P90. Use staged addition and re-check viscosity "
                            "after every step."
                        )

                    if (
                        not pd.isna(ratio_p95)
                        and required_ratio > ratio_p95
                    ):
                        st.error(
                            "🚨 Required solvent ratio exceeds historical "
                            "P95. QE / process engineer confirmation is required."
                        )

                    if (
                        not pd.isna(drop_p90)
                        and required_delta_v > drop_p90
                    ):
                        st.warning(
                            "⚠️ Required viscosity reduction exceeds "
                            "historical P90 range."
                        )

                    if (
                        not pd.isna(max_drop)
                        and required_delta_v > max_drop
                    ):
                        st.error(
                            "🚨 Required viscosity reduction exceeds "
                            "maximum historical record. Do not use this "
                            "as an automatic final instruction."
                        )


# =========================================================
# [S12] TAB 3 - SOP MATRIX EXPORT
# =========================================================
with tab_matrix:
    st.markdown("### 📚 SOP Coefficient Matrix")

    st.caption(
        "Main SOP grouping: Resin + Vendor + Solvent Type + "
        "Initial Viscosity Zone."
    )

    if filtered_sop.empty:
        st.warning(
            "⚠️ No SOP matrix records for the selected group."
        )

    else:
        # -------------------------------------------------
        # [S12.01] Rename display columns
        # -------------------------------------------------
        sop_display = filtered_sop.copy()

        sop_display = sop_display.rename(columns={
            "Viscosity_Zone": "Initial Viscosity Range",
            "Typical_Target_V": "Typical Target V (s)",
            "Historical_Low_V_P10": "Historical After V P10 (s)",
            "Historical_High_V_P90": "Historical After V P90 (s)",
            "Historical_Ratio_Median": "Historical Ratio Median (%)",
            "Historical_Ratio_P90": "Historical Ratio P90 (%)",
            "Historical_Ratio_P95": "Historical Ratio P95 (%)",
            "Typical_Viscosity_Drop": "Typical Viscosity Drop (s)",
            "Viscosity_Drop_P10": "Viscosity Drop P10 (s)",
            "Viscosity_Drop_P90": "Viscosity Drop P90 (s)",
            "Max_Historical_Drop": "Max Historical Drop (s)",
            "Median_Sensitivity": "Median Sensitivity (s/%)",
            "Sensitivity_Std": "Sensitivity Std",
            "Factor_kg_per_100kg_per_1s": "Factor (kg/100kg/1s)",
            "Typical_Total_Coeff_kg_per_100kg": "Historical Total Coeff. (kg/100kg)",
            "Draft_Stage_1_Coeff_kg_per_100kg": "Draft Stage 1 Coeff. (kg/100kg)",
            "Draft_Stage_2_Coeff_kg_per_100kg": "Draft Stage 2 Coeff. (kg/100kg)",
            "Draft_Fine_Adjust_Coeff_kg_per_100kg": "Draft Fine Adjust Coeff. (kg/100kg)",
            "Draft_Max_Total_Coeff_kg_per_100kg": "Draft Max Total Coeff. (kg/100kg)",
            "Records_in_Zone": "Records"
        })

        # -------------------------------------------------
        # [S12.02] SOP display columns
        # -------------------------------------------------
        display_columns = [
            "Resin",
            "Vendor",
            "Solvent_Type",
            "Initial Viscosity Range",
            "Typical Target V (s)",
            "Historical After V P10 (s)",
            "Historical After V P90 (s)",
            "Historical Ratio Median (%)",
            "Historical Ratio P90 (%)",
            "Historical Ratio P95 (%)",
            "Typical Viscosity Drop (s)",
            "Viscosity Drop P10 (s)",
            "Viscosity Drop P90 (s)",
            "Max Historical Drop (s)",
            "Median Sensitivity (s/%)",
            "Sensitivity Std",
            "Factor (kg/100kg/1s)",
            "Draft Stage 1 Coeff. (kg/100kg)",
            "Draft Stage 2 Coeff. (kg/100kg)",
            "Draft Fine Adjust Coeff. (kg/100kg)",
            "Draft Max Total Coeff. (kg/100kg)",
            "Records",
            "Data_Confidence",
            "Confidence_Icon"
        ]

        numeric_columns = [
            "Typical Target V (s)",
            "Historical After V P10 (s)",
            "Historical After V P90 (s)",
            "Historical Ratio Median (%)",
            "Historical Ratio P90 (%)",
            "Historical Ratio P95 (%)",
            "Typical Viscosity Drop (s)",
            "Viscosity Drop P10 (s)",
            "Viscosity Drop P90 (s)",
            "Max Historical Drop (s)",
            "Median Sensitivity (s/%)",
            "Sensitivity Std",
            "Factor (kg/100kg/1s)",
            "Draft Stage 1 Coeff. (kg/100kg)",
            "Draft Stage 2 Coeff. (kg/100kg)",
            "Draft Fine Adjust Coeff. (kg/100kg)",
            "Draft Max Total Coeff. (kg/100kg)"
        ]

        sop_display = sop_display[
            display_columns + ["Zone_Sort"]
        ].copy()

        sop_display[numeric_columns] = (
            sop_display[numeric_columns]
            .round(2)
        )

        # -------------------------------------------------
        # [S12.03] Sort and display matrix
        # -------------------------------------------------
        sop_display = sop_display.sort_values(
            by=[
                "Resin",
                "Vendor",
                "Solvent_Type",
                "Zone_Sort"
            ]
        ).drop(columns=["Zone_Sort"])

        st.dataframe(
            sop_display,
            column_config={
                col: st.column_config.NumberColumn(format="%.2f")
                for col in numeric_columns
            },
            use_container_width=True,
            hide_index=True
        )

        # -------------------------------------------------
        # [S12.04] Explanation and CSV export
        # -------------------------------------------------
        st.markdown(
            """
            **Data reliability rule**

            - ✅ Reliable: at least 10 records; suitable as main operating reference.  
            - ⚠️ Usable with Caution: 5–9 records; use staged addition and recheck.  
            - 🟡 Limited Data: 3–4 records; reference only, not automatic control.  

            **Important note**

            This matrix is based on historical mixing behavior only.
            The current dataset does not include gloss, ΔE, film thickness,
            appearance defects, or PASS/NG results.
            """
        )

        csv = sop_display.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            label="📥 Download SOP Matrix as CSV",
            data=csv,
            file_name="Resin_Vendor_Solvent_SOP_Matrix.csv",
            mime="text/csv"
        )
```
