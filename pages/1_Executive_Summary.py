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
st.markdown(
    "Analyze solvent efficiency, environmental impact, and recommend staged solvent addition."
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
    """Calculate quantile safely after removing invalid values."""
    clean_series = pd.to_numeric(series, errors="coerce").dropna()

    if clean_series.empty:
        return default

    return clean_series.quantile(q)


def generate_dynamic_bins(series):
    """
    Create viscosity zones by quartile.
    If insufficient variation exists, return Unknown.
    """
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
    """Convert interval to an integer range such as 60–100."""
    if isinstance(interval_value, pd.Interval):
        left_value = int(round(interval_value.left))
        right_value = int(round(interval_value.right))
        return f"{left_value}–{right_value}"

    return str(interval_value)


def get_zone_lower_bound(interval_value):
    """Return the lower bound for sorting viscosity zones."""
    if isinstance(interval_value, pd.Interval):
        return int(round(interval_value.left))

    return 999999


def get_data_confidence(record_count):
    """
    Return data quality classification based on number of records.
    """
    if record_count >= MIN_RECORDS_RELIABLE:
        return "Reliable", "✅"

    if record_count >= MIN_RECORDS_FOR_RECOMMENDATION:
        return "Usable with Caution", "⚠️"

    if record_count >= MIN_RECORDS_FOR_REFERENCE:
        return "Limited Data", "🟡"

    return "Insufficient Data", "🔴"


def get_recommendation_confidence(record_count, match_type):
    """
    Evaluate recommendation confidence from record count and matching condition.
    """
    if record_count >= MIN_RECORDS_RELIABLE and match_type == "strict":
        return "High Confidence", "green"

    if record_count >= MIN_RECORDS_FOR_RECOMMENDATION and match_type in ["strict", "partial"]:
        return "Medium Confidence", "orange"

    return "Low Confidence", "red"


def get_zone_for_current_viscosity(zone_df, current_viscosity):
    """
    Find the SOP zone containing current viscosity.
    """
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

# Main calculations
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

# Keep only valid adjustment records
analysis_df = group_a[
    (group_a["添加重量"] > 0) &
    (group_a["塗料重量"] > 0) &
    (group_a["Solvent_Ratio_Percent"] > 0) &
    (group_a["Delta_V"] > 0) &
    (group_a["Sensitivity"] > 0)
].copy()

# Remove extreme sensitivity outliers globally: P1–P99
if not analysis_df.empty:
    p01 = analysis_df["Sensitivity"].quantile(0.01)
    p99 = analysis_df["Sensitivity"].quantile(0.99)

    analysis_df = analysis_df[
        (analysis_df["Sensitivity"] >= p01) &
        (analysis_df["Sensitivity"] <= p99)
    ].copy()

if analysis_df.empty:
    st.warning(
        "⚠️ No valid solvent-adjustment records found. "
        "Please check solvent weight, paint weight, and viscosity columns."
    )
    st.stop()


# =========================================================
# 6. CREATE SOP ZONES
# =========================================================
matrix_df = analysis_df.copy()

matrix_df["_Viscosity_Zone_Interval"] = (
    matrix_df.groupby(["Resin", "Vendor"])["黏度(秒)"]
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

# Zone-specific SOP statistics
sop_zone_df = (
    matrix_df
    .groupby(
        [
            "Resin",
            "Vendor",
            "Viscosity_Zone",
            "Zone_Lower",
            "Zone_Upper",
            "Zone_Sort"
        ],
        dropna=False,
        observed=False
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

sop_zone_df["Data_Confidence"] = sop_zone_df[
    "Records_in_Zone"
].apply(
    lambda x: get_data_confidence(x)[0]
)

sop_zone_df["Confidence_Icon"] = sop_zone_df[
    "Records_in_Zone"
].apply(
    lambda x: get_data_confidence(x)[1]
)

# Flag very high historical solvent usage
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

# Only retain zone summary rows with at least 3 records
sop_zone_df = sop_zone_df[
    sop_zone_df["Records_in_Zone"] >= MIN_RECORDS_FOR_REFERENCE
].copy()


# =========================================================
# 7. GLOBAL KPI
# =========================================================
st.subheader("💡 Global Key Performance Indicators")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Records", f"{len(group_a):,}")

with col2:
    st.metric("Valid Adjustment Records", f"{len(analysis_df):,}")

with col3:
    st.metric(
        "Total Paint Processed",
        f"{group_a['塗料重量'].sum():,.2f} kg"
    )

with col4:
    st.metric(
        "Rejected / Invalid Records",
        f"{len(rejected_data):,}"
    )

st.markdown("---")


# =========================================================
# 8. FILTERS
# =========================================================
available_resins = sorted(
    analysis_df["Resin"].dropna().astype(str).unique().tolist()
)

available_vendors = sorted(
    analysis_df["Vendor"].dropna().astype(str).unique().tolist()
)

filter_col1, filter_col2 = st.columns(2)

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

filtered_data = analysis_df[
    (analysis_df["Resin"].astype(str) == str(selected_resin)) &
    (analysis_df["Vendor"].astype(str) == str(selected_vendor))
].copy()

filtered_sop = sop_zone_df[
    (sop_zone_df["Resin"].astype(str) == str(selected_resin)) &
    (sop_zone_df["Vendor"].astype(str) == str(selected_vendor))
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
        st.info("No valid data available for the selected Resin and Vendor.")

    else:
        col_heat1, col_heat2 = st.columns(2)

        with col_heat1:
            st.markdown("#### Formula Efficiency: Initial Viscosity vs. Solvent Ratio")

            solvent_bins = [0, 2, 4, 6, 8, 10, 12, 15, 20, 30, 50]
            viscosity_bins = [0, 50, 70, 90, 110, 130, 150, 170, 190, 210, 250, 500]

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
                margin=dict(l=20, r=20, t=30, b=20)
            )

            st.plotly_chart(fig_heatmap, use_container_width=True)

        with col_heat2:
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
                    )["Sensitivity"]
                    .median()
                    .reset_index()
                )

                pivot_env = heatmap_env.pivot(
                    index="Hum_Bin",
                    columns="Temp_Bin",
                    values="Sensitivity"
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
                    margin=dict(l=20, r=20, t=30, b=20)
                )

                st.plotly_chart(fig_env, use_container_width=True)

        st.caption(
            "Environmental charts are observational. Results may also be affected by paint formulation, "
            "paint batch, operator, solvent type, mixing time, and production conditions."
        )


# =========================================================
# TASK 2: RECOMMENDATION ENGINE + SOP MATRIX
# =========================================================
with tab_ai:
    st.markdown("### 🧠 Solvent Recommendation Engine")

    if filtered_sop.empty:
        st.warning(
            "⚠️ No SOP zone with sufficient data is available for the selected Resin and Vendor."
        )

    else:
        col_i1, col_i2, col_i3, col_i4, col_i5 = st.columns(5)

        with col_i1:
            curr_viscosity = st.number_input(
                "Current Tank Viscosity (s)",
                value=55.00,
                step=1.00,
                format="%.2f"
            )

        with col_i2:
            target_viscosity = st.number_input(
                "Target Viscosity (s)",
                value=52.00,
                step=1.00,
                format="%.2f"
            )

        with col_i3:
            curr_temp = st.number_input(
                "Shop Temperature (°C)",
                value=32.00,
                step=1.00,
                format="%.2f"
            )

        with col_i4:
            curr_humidity = st.number_input(
                "Shop Humidity (%)",
                value=85.00,
                step=1.00,
                format="%.2f"
            )

        with col_i5:
            paint_qty = st.number_input(
                "Total Paint Weight (kg)",
                value=200.00,
                min_value=1.00,
                step=10.00,
                format="%.2f"
            )

        if target_viscosity >= curr_viscosity:
            st.info("✅ Target viscosity is already achieved. No solvent addition is required.")

        else:
            viscosity_drop = curr_viscosity - target_viscosity

            selected_zone = get_zone_for_current_viscosity(
                filtered_sop,
                curr_viscosity
            )

            # First priority: use current viscosity zone
            if selected_zone is not None:
                zone_data = filtered_data[
                    (filtered_data["黏度(秒)"] >= selected_zone["Zone_Lower"]) &
                    (filtered_data["黏度(秒)"] <= selected_zone["Zone_Upper"])
                ].copy()

            else:
                zone_data = filtered_data.copy()

            # Match similar environment
            strict_data = zone_data[
                (zone_data["溫度"] >= curr_temp - 5) &
                (zone_data["溫度"] <= curr_temp + 5) &
                (zone_data["濕度"] >= curr_humidity - 10) &
                (zone_data["濕度"] <= curr_humidity + 10)
            ].copy()

            expected_sensitivity = np.nan
            reference_data = pd.DataFrame()
            match_type = ""

            # Priority 1: Viscosity zone + environment
            if len(strict_data) >= MIN_RECORDS_FOR_RECOMMENDATION:
                expected_sensitivity = strict_data["Sensitivity"].median()
                reference_data = strict_data
                match_type = "strict"

            # Priority 2: Viscosity zone only
            elif len(zone_data) >= MIN_RECORDS_FOR_RECOMMENDATION:
                expected_sensitivity = zone_data["Sensitivity"].median()
                reference_data = zone_data
                match_type = "partial"

            # Priority 3: Resin + Vendor overall
            elif len(filtered_data) >= MIN_RECORDS_FOR_RECOMMENDATION:
                expected_sensitivity = filtered_data["Sensitivity"].median()
                reference_data = filtered_data
                match_type = "general"

            if pd.isna(expected_sensitivity) or expected_sensitivity <= 0:
                st.error(
                    "❌ Insufficient valid records for automatic recommendation. "
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

                required_ratio = viscosity_drop / expected_sensitivity
                total_solvent_kg = paint_qty * required_ratio / 100

                stage_1_kg = total_solvent_kg * STAGE_1_PERCENT
                stage_2_kg = total_solvent_kg * STAGE_2_PERCENT
                stage_3_kg = total_solvent_kg * STAGE_3_PERCENT

                p10_warning = (
                    not pd.isna(historical_floor_p10)
                    and target_viscosity < historical_floor_p10
                )

                p90_warning = (
                    not pd.isna(historical_ratio_p90)
                    and required_ratio > historical_ratio_p90
                )

                p95_warning = (
                    not pd.isna(historical_ratio_p95)
                    and required_ratio > historical_ratio_p95
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
                        <p><b>Required Viscosity Reduction:</b> {viscosity_drop:.2f} s</p>
                        <p><b>Historical Sensitivity Used:</b> {expected_sensitivity:.2f} s/%</p>
                        <p><b>Calculated Solvent Ratio:</b> {required_ratio:.2f}%</p>
                        <p><b>Reference Records:</b> {sample_size}</p>
                        <p><b>Matching Level:</b> {match_type.title()}</p>
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
                        f"{STAGE_1_PERCENT * 100:.0f}% of calculated total"
                    )

                with stage_col2:
                    st.metric(
                        "Stage 2: After Re-check",
                        f"{stage_2_kg:.2f} kg",
                        f"{STAGE_2_PERCENT * 100:.0f}% of calculated total"
                    )

                with stage_col3:
                    st.metric(
                        "Stage 3: Fine Adjustment",
                        f"{stage_3_kg:.2f} kg",
                        f"{STAGE_3_PERCENT * 100:.0f}% of calculated total"
                    )

                st.info(
                    "Operating instruction: add Stage 1, mix completely, measure viscosity again, "
                    "then add Stage 2 and Stage 3 only when necessary."
                )

                st.markdown("#### Historical Operating Boundary")

                ref_col1, ref_col2, ref_col3 = st.columns(3)

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
                        "Historical Ratio P95",
                        f"{historical_ratio_p95:.2f}%"
                        if not pd.isna(historical_ratio_p95)
                        else "N/A"
                    )

                if p10_warning:
                    st.warning(
                        f"⚠️ Target viscosity ({target_viscosity:.2f}s) is lower than the historical "
                        f"P10 level ({historical_floor_p10:.2f}s). Use only staged adjustment."
                    )

                if p90_warning:
                    st.warning(
                        f"⚠️ Required solvent ratio ({required_ratio:.2f}%) exceeds historical P90 "
                        f"({historical_ratio_p90:.2f}%). Verify after Stage 1."
                    )

                if p95_warning:
                    st.error(
                        f"🚨 Required solvent ratio ({required_ratio:.2f}%) exceeds historical P95 "
                        f"({historical_ratio_p95:.2f}%). Automatic recommendation should not be treated as final."
                    )

    # =====================================================
    # SOP MATRIX
    # =====================================================
    st.markdown("---")
    st.markdown("### 📚 SOP Coefficient Matrix")

    st.caption(
        "Each row is calculated within the specific Resin + Vendor + Initial Viscosity Zone."
    )

    sop_display = sop_zone_df.copy()

    sop_display = sop_display.rename(columns={
        "Viscosity_Zone": "Initial Viscosity Range",
        "Typical_Target_V": "Typical Target V (s)",
        "Historical_Low_V_P10": "Historical Low V P10 (s)",
        "Historical_Ratio_P90": "Historical Ratio P90 (%)",
        "Historical_Ratio_P95": "Historical Ratio P95 (%)",
        "Median_Sensitivity": "Median Sensitivity (s/%)",
        "Solvent_Percent_per_1s": "Solvent % per 1s Drop",
        "Factor_kg_per_100kg_per_1s": "Factor (kg per 100kg paint / 1s)",
        "Records_in_Zone": "Records in Zone",
        "Ratio_Risk_Flag": "Ratio Risk"
    })

    display_columns = [
        "Resin",
        "Vendor",
        "Initial Viscosity Range",
        "Typical Target V (s)",
        "Historical Low V P10 (s)",
        "Historical Ratio P90 (%)",
        "Historical Ratio P95 (%)",
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
        "Median Sensitivity (s/%)",
        "Solvent % per 1s Drop",
        "Factor (kg per 100kg paint / 1s)"
    ]

    sop_display[numeric_sop_columns] = sop_display[
        numeric_sop_columns
    ].round(2)

    # Rebuild sorting key from lower number in text zone
    sop_display["Zone_Sort"] = (
        sop_display["Initial Viscosity Range"]
        .str.extract(r"(\d+)", expand=False)
        .astype(float)
    )

    sop_display = sop_display.sort_values(
        by=["Resin", "Vendor", "Zone_Sort"]
    ).drop(columns=["Zone_Sort"])

    st.dataframe(
        sop_display,
        column_config={
            "Typical Target V (s)": st.column_config.NumberColumn(format="%.2f"),
            "Historical Low V P10 (s)": st.column_config.NumberColumn(format="%.2f"),
            "Historical Ratio P90 (%)": st.column_config.NumberColumn(format="%.2f"),
            "Historical Ratio P95 (%)": st.column_config.NumberColumn(format="%.2f"),
            "Median Sensitivity (s/%)": st.column_config.NumberColumn(format="%.2f"),
            "Solvent % per 1s Drop": st.column_config.NumberColumn(format="%.2f"),
            "Factor (kg per 100kg paint / 1s)": st.column_config.NumberColumn(format="%.2f")
        },
        use_container_width=True,
        hide_index=True
    )

    st.markdown(
        """
        **Interpretation rule**

        - ✅ Reliable: at least 10 records; suitable as a main operating reference.  
        - ⚠️ Usable with Caution: 5–9 records; use staged addition and recheck viscosity.  
        - 🟡 Limited Data: 3–4 records; display for reference only, not for automatic decision.  
        - 🚨 Very High Ratio: Historical P90 solvent ratio is unusually high and needs data review.
        """
    )

    csv = sop_display.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        label="📥 Download Improved SOP Coefficient Matrix as CSV",
        data=csv,
        file_name="Improved_SOP_Coefficient_Matrix.csv",
        mime="text/csv"
    )
