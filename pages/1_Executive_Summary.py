import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# =========================================================
# 1. PAGE SETUP
# =========================================================
st.set_page_config(
    page_title="Solvent Analysis",
    page_icon="🧪",
    layout="wide"
)

st.title("🧪 Solvent Sensitivity & Recommendation System")
st.caption(
    "Historical solvent analysis by Resin, Vendor, Solvent Type, "
    "Initial Viscosity Zone, and actual viscosity reduction."
)
st.markdown("---")


# =========================================================
# 2. CONFIGURATION
# =========================================================
MIN_RECORDS_FOR_REFERENCE = 3
MIN_RECORDS_FOR_RECOMMENDATION = 5
MIN_RECORDS_RELIABLE = 10

HIGH_RATIO_WARNING_PERCENT = 10.0
VERY_HIGH_RATIO_WARNING_PERCENT = 15.0

STAGE_1_PERCENT = 0.60
STAGE_2_PERCENT = 0.25
STAGE_3_PERCENT = 0.15


# =========================================================
# 3. DATA CHECK
# =========================================================
if "raw_data_loaded" not in st.session_state or not st.session_state["raw_data_loaded"]:
    st.warning("⚠️ Please upload data on the main page first.")
    st.stop()

if "group_a_data" not in st.session_state:
    st.error("❌ Group A data is not available.")
    st.stop()

group_a_raw = st.session_state["group_a_data"].copy()
rejected_data = st.session_state.get("rejected_data", pd.DataFrame())


# =========================================================
# 4. HELPER FUNCTIONS
# =========================================================
def safe_quantile(series, q, default=np.nan):
    clean_series = pd.to_numeric(series, errors="coerce").dropna()

    if clean_series.empty:
        return default

    return clean_series.quantile(q)


def generate_dynamic_bins(series):
    """Create viscosity zones using quartiles."""
    numeric_series = pd.to_numeric(series, errors="coerce")

    if numeric_series.dropna().nunique() < 2:
        return pd.Series(["Unknown"] * len(series), index=series.index)

    try:
        return pd.qcut(
            numeric_series,
            q=4,
            duplicates="drop"
        )
    except Exception:
        try:
            return pd.cut(
                numeric_series,
                bins=4,
                duplicates="drop"
            )
        except Exception:
            return pd.Series(["Unknown"] * len(series), index=series.index)


def format_viscosity_zone(interval_value):
    """Convert interval to integer text, e.g. 60–100."""
    if isinstance(interval_value, pd.Interval):
        left_value = int(round(interval_value.left))
        right_value = int(round(interval_value.right))
        return f"{left_value}–{right_value}"

    return str(interval_value)


def get_zone_lower_bound(interval_value):
    if isinstance(interval_value, pd.Interval):
        return int(round(interval_value.left))

    return 999999


def get_data_confidence(record_count):
    if record_count >= MIN_RECORDS_RELIABLE:
        return "Reliable", "✅"

    if record_count >= MIN_RECORDS_FOR_RECOMMENDATION:
        return "Usable with Caution", "⚠️"

    if record_count >= MIN_RECORDS_FOR_REFERENCE:
        return "Limited Data", "🟡"

    return "Insufficient Data", "🔴"


def get_recommendation_confidence(record_count, match_type):
    if record_count >= MIN_RECORDS_RELIABLE and match_type == "strict":
        return "High Confidence", "green"

    if record_count >= MIN_RECORDS_FOR_RECOMMENDATION and match_type in [
        "strict",
        "drop_match",
        "zone"
    ]:
        return "Medium Confidence", "orange"

    return "Low Confidence", "red"


def get_zone_for_current_viscosity(zone_df, current_viscosity):
    matched = zone_df[
        (zone_df["Zone_Lower"] <= current_viscosity) &
        (zone_df["Zone_Upper"] >= current_viscosity)
    ].copy()

    if not matched.empty:
        return matched.iloc[0]

    return None


# =========================================================
# 5. DATA PREPARATION
# =========================================================
required_columns = [
    "添加重量",
    "塗料重量",
    "黏度(秒)",
    "黏度(秒)_1",
    "Resin",
    "Vendor"
]

missing_columns = [
    col for col in required_columns
    if col not in group_a_raw.columns
]

if missing_columns:
    st.error(f"❌ Missing required columns: {', '.join(missing_columns)}")
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
        group_a[col] = pd.to_numeric(group_a[col], errors="coerce")

if "Solvent_Type" not in group_a.columns:
    group_a["Solvent_Type"] = "Unknown"

if "溫度" not in group_a.columns:
    group_a["溫度"] = np.nan

if "濕度" not in group_a.columns:
    group_a["濕度"] = np.nan

if "塗料批號" not in group_a.columns:
    group_a["塗料批號"] = group_a.index.astype(str)

group_a["Solvent_Type"] = (
    group_a["Solvent_Type"]
    .fillna("Unknown")
    .astype(str)
    .str.strip()
)

group_a["Resin"] = (
    group_a["Resin"]
    .fillna("Unknown")
    .astype(str)
    .str.strip()
)

group_a["Vendor"] = (
    group_a["Vendor"]
    .fillna("Unknown")
    .astype(str)
    .str.strip()
)

# Core calculations
group_a["Solvent_Ratio_Percent"] = (
    group_a["添加重量"]
    / group_a["塗料重量"].replace(0, np.nan)
) * 100

group_a["Delta_V"] = (
    group_a["黏度(秒)"]
    - group_a["黏度(秒)_1"]
)

group_a["Sensitivity"] = (
    group_a["Delta_V"]
    / group_a["Solvent_Ratio_Percent"].replace(0, np.nan)
)

# Valid adjustment records only
analysis_df = group_a[
    (group_a["添加重量"] > 0) &
    (group_a["塗料重量"] > 0) &
    (group_a["Solvent_Ratio_Percent"] > 0) &
    (group_a["Delta_V"] > 0) &
    (group_a["Sensitivity"] > 0)
].copy()

# Remove global extreme sensitivity outliers
if not analysis_df.empty:
    sensitivity_p01 = analysis_df["Sensitivity"].quantile(0.01)
    sensitivity_p99 = analysis_df["Sensitivity"].quantile(0.99)

    analysis_df = analysis_df[
        (analysis_df["Sensitivity"] >= sensitivity_p01) &
        (analysis_df["Sensitivity"] <= sensitivity_p99)
    ].copy()

if analysis_df.empty:
    st.warning(
        "⚠️ No valid solvent-adjustment records found. "
        "Please check solvent quantity, paint quantity, and viscosity data."
    )
    st.stop()


# =========================================================
# 6. CREATE SOP MATRIX BY RESIN + VENDOR + SOLVENT TYPE
# =========================================================
matrix_df = analysis_df.copy()

matrix_df["_Viscosity_Zone_Interval"] = (
    matrix_df
    .groupby(["Resin", "Vendor", "Solvent_Type"])["黏度(秒)"]
    .transform(generate_dynamic_bins)
)

matrix_df["Viscosity_Zone"] = (
    matrix_df["_Viscosity_Zone_Interval"]
    .apply(format_viscosity_zone)
)

matrix_df["Zone_Lower"] = (
    matrix_df["_Viscosity_Zone_Interval"]
    .apply(
        lambda x: int(round(x.left))
        if isinstance(x, pd.Interval)
        else np.nan
    )
)

matrix_df["Zone_Upper"] = (
    matrix_df["_Viscosity_Zone_Interval"]
    .apply(
        lambda x: int(round(x.right))
        if isinstance(x, pd.Interval)
        else np.nan
    )
)

matrix_df["Zone_Sort"] = (
    matrix_df["_Viscosity_Zone_Interval"]
    .apply(get_zone_lower_bound)
)

# SOP summary: every metric calculated separately inside each zone
sop_zone_df = (
    matrix_df
    .groupby(
        [
            "Resin",
            "Vendor",
            "Solvent_Type",
            "Viscosity_Zone",
            "Zone_Lower",
            "Zone_Upper",
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

        Historical_Ratio_P90=(
            "Solvent_Ratio_Percent",
            lambda x: safe_quantile(x, 0.90)
        ),

        Historical_Ratio_P95=(
            "Solvent_Ratio_Percent",
            lambda x: safe_quantile(x, 0.95)
        ),

        Typical_Viscosity_Drop=("Delta_V", "median"),

        Viscosity_Drop_P10=(
            "Delta_V",
            lambda x: safe_quantile(x, 0.10)
        ),

        Viscosity_Drop_P90=(
            "Delta_V",
            lambda x: safe_quantile(x, 0.90)
        ),

        Max_Historical_Drop=("Delta_V", "max"),

        Median_Sensitivity=("Sensitivity", "median"),

        Sensitivity_Std=("Sensitivity", "std"),

        Records_in_Zone=("塗料批號", "nunique")
    )
    .reset_index()
)

sop_zone_df["Solvent_Percent_per_1s"] = np.where(
    sop_zone_df["Median_Sensitivity"] > 0,
    1 / sop_zone_df["Median_Sensitivity"],
    np.nan
)

sop_zone_df["Factor_kg_per_100kg_per_1s"] = (
    sop_zone_df["Solvent_Percent_per_1s"]
)

sop_zone_df["Data_Confidence"] = (
    sop_zone_df["Records_in_Zone"]
    .apply(lambda x: get_data_confidence(x)[0])
)

sop_zone_df["Confidence_Icon"] = (
    sop_zone_df["Records_in_Zone"]
    .apply(lambda x: get_data_confidence(x)[1])
)

sop_zone_df["Ratio_Risk_Flag"] = np.select(
    [
        sop_zone_df["Historical_Ratio_P90"] >= VERY_HIGH_RATIO_WARNING_PERCENT,
        sop_zone_df["Historical_Ratio_P90"] >= HIGH_RATIO_WARNING_PERCENT
    ],
    [
        "🚨 Very High Ratio",
        "⚠️ High Ratio"
    ],
    default="Normal"
)

# Display zones only when at least 3 unique batches exist
sop_zone_df = sop_zone_df[
    sop_zone_df["Records_in_Zone"] >= MIN_RECORDS_FOR_REFERENCE
].copy()


# =========================================================
# 7. GLOBAL KPI
# =========================================================
st.subheader("💡 Global Key Performance Indicators")

kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

with kpi_col1:
    st.metric("Total Records", f"{len(group_a):,}")

with kpi_col2:
    st.metric("Valid Adjustment Records", f"{len(analysis_df):,}")

with kpi_col3:
    st.metric(
        "Total Paint Processed",
        f"{group_a['塗料重量'].sum():,.2f} kg"
    )

with kpi_col4:
    st.metric(
        "Rejected / Invalid Records",
        f"{len(rejected_data):,}"
    )

st.markdown("---")


# =========================================================
# 8. GLOBAL FILTERS
# =========================================================
available_resins = sorted(analysis_df["Resin"].unique().tolist())
available_vendors = sorted(analysis_df["Vendor"].unique().tolist())
available_solvents = sorted(analysis_df["Solvent_Type"].unique().tolist())

filter_col1, filter_col2, filter_col3 = st.columns(3)

with filter_col1:
    selected_resin = st.selectbox(
        "Select Resin",
        available_resins
    )

with filter_col2:
    selected_vendor = st.selectbox(
        "Select Vendor",
        available_vendors
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

filtered_sop = sop_zone_df[
    (sop_zone_df["Resin"] == selected_resin) &
    (sop_zone_df["Vendor"] == selected_vendor) &
    (sop_zone_df["Solvent_Type"] == selected_solvent)
].copy()


# =========================================================
# 9. TABS
# =========================================================
tab_env, tab_ai = st.tabs([
    "🌡️ Task 1: Sensitivity & Environment",
    "🧠 Task 2: Solvent Recommendation & SOP Matrix"
])


# =========================================================
# TASK 1: SENSITIVITY & ENVIRONMENT
# =========================================================
with tab_env:
    st.markdown("### 🌡️ Process Sensitivity & Environmental Impact")

    if filtered_data.empty:
        st.info(
            "No valid records for the selected Resin, Vendor, and Solvent Type."
        )

    else:
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.markdown(
                "#### Formula Efficiency: Initial Viscosity vs. Solvent Ratio"
            )

            solvent_bins = [0, 2, 4, 6, 8, 10, 12, 15, 20, 30, 50]
            viscosity_bins = [
                0, 50, 70, 90, 110, 130,
                150, 170, 190, 210, 250, 500
            ]

            heatmap_df = filtered_data.copy()

            heatmap_df["Solvent_Bin"] = pd.cut(
                heatmap_df["Solvent_Ratio_Percent"],
                bins=solvent_bins,
                include_lowest=True
            )

            heatmap_df["Initial_V_Bin"] = pd.cut(
                heatmap_df["黏度(秒)"],
                bins=viscosity_bins,
                include_lowest=True
            )

            heatmap_data = (
                heatmap_df
                .groupby(
                    ["Initial_V_Bin", "Solvent_Bin"],
                    observed=False
                )
                .agg(
                    Median_Sensitivity=("Sensitivity", "median"),
                    Median_Delta_V=("Delta_V", "median"),
                    Records=("塗料批號", "nunique")
                )
                .reset_index()
            )

            pivot_table = heatmap_data.pivot(
                index="Initial_V_Bin",
                columns="Solvent_Bin",
                values="Median_Sensitivity"
            )

            pivot_table.index = pivot_table.index.astype(str)
            pivot_table.columns = pivot_table.columns.astype(str)

            fig_heatmap = px.imshow(
                pivot_table.astype(float),
                text_auto=".2f",
                aspect="auto",
                color_continuous_scale="Blues",
                labels={
                    "x": "Solvent Ratio (%)",
                    "y": "Initial Viscosity (s)",
                    "color": "Median Sensitivity (s/%)"
                }
            )

            fig_heatmap.update_layout(
                margin=dict(l=20, r=20, t=35, b=20)
            )

            st.plotly_chart(fig_heatmap, use_container_width=True)

        with chart_col2:
            st.markdown(
                "#### Historical Viscosity Reduction Distribution"
            )

            fig_delta = px.box(
                filtered_data,
                x="Viscosity_Zone",
                y="Delta_V",
                points="all",
                labels={
                    "Viscosity_Zone": "Initial Viscosity Zone",
                    "Delta_V": "Actual Viscosity Drop (s)"
                }
            )

            fig_delta.update_layout(
                margin=dict(l=20, r=20, t=35, b=20)
            )

            st.plotly_chart(fig_delta, use_container_width=True)

        st.markdown("#### Weather Impact: Temperature vs. Humidity")

        env_data = filtered_data.dropna(
            subset=["溫度", "濕度"]
        ).copy()

        if env_data.empty:
            st.info("No valid temperature and humidity data available.")

        else:
            temp_bins = [10, 15, 20, 25, 30, 35, 40, 50]
            hum_bins = [20, 30, 40, 50, 60, 70, 80, 90, 100]

            env_data["Temp_Bin"] = pd.cut(
                env_data["溫度"],
                bins=temp_bins,
                include_lowest=True
            )

            env_data["Hum_Bin"] = pd.cut(
                env_data["濕度"],
                bins=hum_bins,
                include_lowest=True
            )

            heatmap_env = (
                env_data
                .groupby(
                    ["Hum_Bin", "Temp_Bin"],
                    observed=False
                )
                .agg(
                    Median_Sensitivity=("Sensitivity", "median"),
                    Median_Delta_V=("Delta_V", "median")
                )
                .reset_index()
            )

            pivot_env = heatmap_env.pivot(
                index="Hum_Bin",
                columns="Temp_Bin",
                values="Median_Sensitivity"
            )

            pivot_env.index = pivot_env.index.astype(str)
            pivot_env.columns = pivot_env.columns.astype(str)

            fig_env = px.imshow(
                pivot_env.astype(float),
                text_auto=".2f",
                aspect="auto",
                color_continuous_scale="Oranges",
                labels={
                    "x": "Temperature (°C)",
                    "y": "Humidity (%)",
                    "color": "Median Sensitivity (s/%)"
                }
            )

            fig_env.update_layout(
                margin=dict(l=20, r=20, t=35, b=20)
            )

            st.plotly_chart(fig_env, use_container_width=True)

        st.caption(
            "Environmental charts are observational. Actual performance may also be affected "
            "by paint batch, mixing duration, operator, production line, and other conditions."
        )


# =========================================================
# TASK 2: RECOMMENDATION ENGINE + SOP MATRIX
# =========================================================
with tab_ai:
    st.markdown("### 🧠 Solvent Recommendation Engine")

    if filtered_data.empty:
        st.warning(
            "⚠️ No valid history exists for the selected Resin, Vendor, and Solvent Type."
        )

    elif filtered_sop.empty:
        st.warning(
            "⚠️ No viscosity zone has at least 3 records for the selected condition."
        )

    else:
        input_col1, input_col2, input_col3, input_col4, input_col5 = st.columns(5)

        with input_col1:
            curr_viscosity = st.number_input(
                "Current Tank Viscosity (s)",
                value=55.00,
                step=1.00,
                format="%.2f"
            )

        with input_col2:
            target_viscosity = st.number_input(
                "Target Viscosity (s)",
                value=52.00,
                step=1.00,
                format="%.2f"
            )

        with input_col3:
            curr_temp = st.number_input(
                "Shop Temperature (°C)",
                value=32.00,
                step=1.00,
                format="%.2f"
            )

        with input_col4:
            curr_humidity = st.number_input(
                "Shop Humidity (%)",
                value=85.00,
                step=1.00,
                format="%.2f"
            )

        with input_col5:
            paint_qty = st.number_input(
                "Total Paint Weight (kg)",
                value=200.00,
                min_value=1.00,
                step=10.00,
                format="%.2f"
            )

        if target_viscosity >= curr_viscosity:
            st.info(
                "✅ Target viscosity is already achieved. "
                "No solvent addition is required."
            )

        else:
            required_delta_v = curr_viscosity - target_viscosity

            selected_zone = get_zone_for_current_viscosity(
                filtered_sop,
                curr_viscosity
            )

            if selected_zone is not None:
                zone_data = filtered_data[
                    (filtered_data["黏度(秒)"] >= selected_zone["Zone_Lower"]) &
                    (filtered_data["黏度(秒)"] <= selected_zone["Zone_Upper"])
                ].copy()
            else:
                zone_data = filtered_data.copy()

            # Similar historical viscosity drop:
            # minimum ±5 seconds, or ±20% of required reduction
            drop_tolerance = max(5, required_delta_v * 0.20)

            drop_match_data = zone_data[
                (zone_data["Delta_V"] >= required_delta_v - drop_tolerance) &
                (zone_data["Delta_V"] <= required_delta_v + drop_tolerance)
            ].copy()

            strict_data = drop_match_data[
                (drop_match_data["溫度"] >= curr_temp - 5) &
                (drop_match_data["溫度"] <= curr_temp + 5) &
                (drop_match_data["濕度"] >= curr_humidity - 10) &
                (drop_match_data["濕度"] <= curr_humidity + 10)
            ].copy()

            expected_sensitivity = np.nan
            reference_data = pd.DataFrame()
            match_type = ""

            # Priority 1:
            # Resin + Vendor + Solvent + Zone + Similar Delta V + Similar Environment
            if len(strict_data) >= MIN_RECORDS_FOR_RECOMMENDATION:
                expected_sensitivity = strict_data["Sensitivity"].median()
                reference_data = strict_data
                match_type = "strict"

            # Priority 2:
            # Resin + Vendor + Solvent + Zone + Similar Delta V
            elif len(drop_match_data) >= MIN_RECORDS_FOR_RECOMMENDATION:
                expected_sensitivity = drop_match_data["Sensitivity"].median()
                reference_data = drop_match_data
                match_type = "drop_match"

            # Priority 3:
            # Resin + Vendor + Solvent + Zone
            elif len(zone_data) >= MIN_RECORDS_FOR_RECOMMENDATION:
                expected_sensitivity = zone_data["Sensitivity"].median()
                reference_data = zone_data
                match_type = "zone"

            # Priority 4:
            # Resin + Vendor + Solvent overall
            elif len(filtered_data) >= MIN_RECORDS_FOR_RECOMMENDATION:
                expected_sensitivity = filtered_data["Sensitivity"].median()
                reference_data = filtered_data
                match_type = "general"

            if pd.isna(expected_sensitivity) or expected_sensitivity <= 0:
                st.error(
                    "❌ Insufficient valid historical records for automatic recommendation. "
                    "At least 5 records are required."
                )

            else:
                sample_size = len(reference_data)

                confidence_label, confidence_color = get_recommendation_confidence(
                    sample_size,
                    match_type
                )

                historical_floor_p10 = safe_quantile(
                    reference_data["黏度(秒)_1"],
                    0.10
                )

                historical_ratio_p90 = safe_quantile(
                    reference_data["Solvent_Ratio_Percent"],
                    0.90
                )

                historical_ratio_p95 = safe_quantile(
                    reference_data["Solvent_Ratio_Percent"],
                    0.95
                )

                historical_drop_p10 = safe_quantile(
                    reference_data["Delta_V"],
                    0.10
                )

                historical_drop_p90 = safe_quantile(
                    reference_data["Delta_V"],
                    0.90
                )

                historical_drop_max = safe_quantile(
                    reference_data["Delta_V"],
                    1.00
                )

                required_ratio = required_delta_v / expected_sensitivity
                total_solvent_kg = paint_qty * required_ratio / 100

                stage_1_kg = total_solvent_kg * STAGE_1_PERCENT
                stage_2_kg = total_solvent_kg * STAGE_2_PERCENT
                stage_3_kg = total_solvent_kg * STAGE_3_PERCENT

                p10_viscosity_warning = (
                    not pd.isna(historical_floor_p10)
                    and target_viscosity < historical_floor_p10
                )

                p90_ratio_warning = (
                    not pd.isna(historical_ratio_p90)
                    and required_ratio > historical_ratio_p90
                )

                p95_ratio_warning = (
                    not pd.isna(historical_ratio_p95)
                    and required_ratio > historical_ratio_p95
                )

                drop_p90_warning = (
                    not pd.isna(historical_drop_p90)
                    and required_delta_v > historical_drop_p90
                )

                drop_max_warning = (
                    not pd.isna(historical_drop_max)
                    and required_delta_v > historical_drop_max
                )

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
                        <p><b>Required Viscosity Drop:</b> {required_delta_v:.2f} s</p>
                        <p><b>Historical Sensitivity Used:</b> {expected_sensitivity:.2f} s/%</p>
                        <p><b>Calculated Solvent Ratio:</b> {required_ratio:.2f}%</p>
                        <p><b>Reference Records:</b> {sample_size}</p>
                        <p><b>Matching Level:</b> {match_type.replace("_", " ").title()}</p>
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

                st.markdown("#### Recommended Staged Addition")

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

                st.info(
                    "Add Stage 1 first, mix completely, measure viscosity again, "
                    "then add Stage 2 and Stage 3 only if required."
                )

                st.markdown("#### Historical Reference Used")

                ref_col1, ref_col2, ref_col3, ref_col4 = st.columns(4)

                with ref_col1:
                    st.metric(
                        "Historical Low V P10",
                        f"{historical_floor_p10:.2f} s"
                        if not pd.isna(historical_floor_p10)
                        else "N/A"
                    )

                with ref_col2:
                    st.metric(
                        "Historical Ratio P90",
                        f"{historical_ratio_p90:.2f}%"
                        if not pd.isna(historical_ratio_p90)
                        else "N/A"
                    )

                with ref_col3:
                    st.metric(
                        "Historical Drop P90",
                        f"{historical_drop_p90:.2f} s"
                        if not pd.isna(historical_drop_p90)
                        else "N/A"
                    )

                with ref_col4:
                    st.metric(
                        "Historical Max Drop",
                        f"{historical_drop_max:.2f} s"
                        if not pd.isna(historical_drop_max)
                        else "N/A"
                    )

                if p10_viscosity_warning:
                    st.warning(
                        f"⚠️ Target viscosity ({target_viscosity:.2f}s) is lower than historical "
                        f"P10 viscosity ({historical_floor_p10:.2f}s). "
                        "Use staged addition only."
                    )

                if p90_ratio_warning:
                    st.warning(
                        f"⚠️ Required solvent ratio ({required_ratio:.2f}%) exceeds historical P90 "
                        f"({historical_ratio_p90:.2f}%). Verify viscosity after Stage 1."
                    )

                if p95_ratio_warning:
                    st.error(
                        f"🚨 Required solvent ratio ({required_ratio:.2f}%) exceeds historical P95 "
                        f"({historical_ratio_p95:.2f}%). Do not treat this as a final automatic recommendation."
                    )

                if drop_p90_warning:
                    st.warning(
                        f"⚠️ Required viscosity reduction ({required_delta_v:.2f}s) exceeds the "
                        f"historical P90 drop ({historical_drop_p90:.2f}s). "
                        "This target is outside the common historical operating range."
                    )

                if drop_max_warning:
                    st.error(
                        f"🚨 Required viscosity reduction ({required_delta_v:.2f}s) exceeds the "
                        f"maximum historical drop ({historical_drop_max:.2f}s). "
                        "The model is extrapolating beyond historical evidence."
                    )

    # =====================================================
    # SOP MATRIX
    # =====================================================
    st.markdown("---")
    st.markdown("### 📚 SOP Coefficient Matrix")

    st.caption(
        "Metrics are calculated within Resin + Vendor + Solvent Type + Initial Viscosity Zone."
    )

    sop_display = sop_zone_df.copy()

    sop_display = sop_display.rename(columns={
        "Viscosity_Zone": "Initial Viscosity Range",
        "Typical_Target_V": "Typical Target V (s)",
        "Historical_Low_V_P10": "Historical Low V P10 (s)",
        "Historical_Ratio_P90": "Historical Ratio P90 (%)",
        "Historical_Ratio_P95": "Historical Ratio P95 (%)",
        "Typical_Viscosity_Drop": "Typical Viscosity Drop (s)",
        "Viscosity_Drop_P10": "Viscosity Drop P10 (s)",
        "Viscosity_Drop_P90": "Viscosity Drop P90 (s)",
        "Max_Historical_Drop": "Max Historical Drop (s)",
        "Median_Sensitivity": "Median Sensitivity (s/%)",
        "Solvent_Percent_per_1s": "Solvent % per 1s Drop",
        "Factor_kg_per_100kg_per_1s": "Factor (kg per 100kg paint / 1s)",
        "Records_in_Zone": "Records in Zone",
        "Ratio_Risk_Flag": "Ratio Risk"
    })

    display_columns = [
        "Resin",
        "Vendor",
        "Solvent_Type",
        "Initial Viscosity Range",
        "Typical Target V (s)",
        "Historical Low V P10 (s)",
        "Historical Ratio P90 (%)",
        "Historical Ratio P95 (%)",
        "Typical Viscosity Drop (s)",
        "Viscosity Drop P10 (s)",
        "Viscosity Drop P90 (s)",
        "Max Historical Drop (s)",
        "Median Sensitivity (s/%)",
        "Solvent % per 1s Drop",
        "Factor (kg per 100kg paint / 1s)",
        "Records in Zone",
        "Data_Confidence",
        "Confidence_Icon",
        "Ratio Risk"
    ]

    sop_display = sop_display[display_columns].copy()

    numeric_sop_columns = [
        "Typical Target V (s)",
        "Historical Low V P10 (s)",
        "Historical Ratio P90 (%)",
        "Historical Ratio P95 (%)",
        "Typical Viscosity Drop (s)",
        "Viscosity Drop P10 (s)",
        "Viscosity Drop P90 (s)",
        "Max Historical Drop (s)",
        "Median Sensitivity (s/%)",
        "Solvent % per 1s Drop",
        "Factor (kg per 100kg paint / 1s)"
    ]

    sop_display[numeric_sop_columns] = (
        sop_display[numeric_sop_columns]
        .round(2)
    )

    sop_display["Zone_Sort"] = (
        sop_display["Initial Viscosity Range"]
        .str.extract(r"(\d+)", expand=False)
        .astype(float)
    )

    sop_display = sop_display.sort_values(
        by=["Resin", "Vendor", "Solvent_Type", "Zone_Sort"]
    ).drop(columns=["Zone_Sort"])

    st.dataframe(
        sop_display,
        column_config={
            "Typical Target V (s)": st.column_config.NumberColumn(format="%.2f"),
            "Historical Low V P10 (s)": st.column_config.NumberColumn(format="%.2f"),
            "Historical Ratio P90 (%)": st.column_config.NumberColumn(format="%.2f"),
            "Historical Ratio P95 (%)": st.column_config.NumberColumn(format="%.2f"),
            "Typical Viscosity Drop (s)": st.column_config.NumberColumn(format="%.2f"),
            "Viscosity Drop P10 (s)": st.column_config.NumberColumn(format="%.2f"),
            "Viscosity Drop P90 (s)": st.column_config.NumberColumn(format="%.2f"),
            "Max Historical Drop (s)": st.column_config.NumberColumn(format="%.2f"),
            "Median Sensitivity (s/%)": st.column_config.NumberColumn(format="%.2f"),
            "Solvent % per 1s Drop": st.column_config.NumberColumn(format="%.2f"),
            "Factor (kg per 100kg paint / 1s)": st.column_config.NumberColumn(format="%.2f")
        },
        use_container_width=True,
        hide_index=True
    )

    st.markdown(
        """
        **Data reliability rule**

        - ✅ Reliable: at least 10 records; suitable as main operating reference.  
        - ⚠️ Usable with Caution: 5–9 records; use staged addition and recheck.  
        - 🟡 Limited Data: 3–4 records; reference only, not automatic control.  
        - 🚨 Very High Ratio: P90 solvent ratio is unusually high and should be reviewed.  
        """
    )

    csv = sop_display.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        label="📥 Download SOP Coefficient Matrix as CSV",
        data=csv,
        file_name="Solvent_SOP_Coefficient_Matrix.csv",
        mime="text/csv"
    )
