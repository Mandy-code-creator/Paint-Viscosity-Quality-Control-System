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
# 2. DATA CHECK
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
# 3. HELPER FUNCTIONS
# =========================================================
def safe_quantile(series, q, default=np.nan):
    """Return a quantile safely after removing invalid values."""
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


def calculate_confidence_label(sample_size, match_type):
    """Return confidence label based on matching quality and sample size."""
    if sample_size >= 10 and match_type == "strict":
        return "High Confidence", "green"

    if sample_size >= 5 and match_type in ["strict", "partial"]:
        return "Medium Confidence", "orange"

    return "Low Confidence", "red"


# =========================================================
# 4. DATA PREPARATION
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

# Convert numeric fields
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

# Create missing optional fields
if "Solvent_Type" not in group_a.columns:
    group_a["Solvent_Type"] = "Unknown"

if "溫度" not in group_a.columns:
    group_a["溫度"] = np.nan

if "濕度" not in group_a.columns:
    group_a["濕度"] = np.nan

if "塗料批號" not in group_a.columns:
    group_a["塗料批號"] = group_a.index.astype(str)

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

# Valid records only
analysis_df = group_a[
    (group_a["添加重量"] > 0) &
    (group_a["塗料重量"] > 0) &
    (group_a["Solvent_Ratio_Percent"] > 0) &
    (group_a["Delta_V"] > 0) &
    (group_a["Sensitivity"] > 0)
].copy()

# Remove extreme sensitivity outliers: P1 to P99
if not analysis_df.empty:
    sensitivity_p01 = analysis_df["Sensitivity"].quantile(0.01)
    sensitivity_p99 = analysis_df["Sensitivity"].quantile(0.99)

    analysis_df = analysis_df[
        (analysis_df["Sensitivity"] >= sensitivity_p01) &
        (analysis_df["Sensitivity"] <= sensitivity_p99)
    ].copy()


# =========================================================
# 5. GLOBAL KPI
# =========================================================
st.subheader("💡 Global Key Performance Indicators")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total Records",
        f"{len(group_a):,}"
    )

with col2:
    st.metric(
        "Valid Adjustment Records",
        f"{len(analysis_df):,}"
    )

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

if analysis_df.empty:
    st.warning(
        "⚠️ No valid solvent-adjustment records found. "
        "Please check solvent weight, paint weight, and viscosity data."
    )
    st.stop()


# =========================================================
# 6. TWO TASKS ONLY
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

    available_resins = sorted(
        analysis_df["Resin"].dropna().astype(str).unique().tolist()
    )

    available_vendors = sorted(
        analysis_df["Vendor"].dropna().astype(str).unique().tolist()
    )

    col_f1, col_f2 = st.columns(2)

    with col_f1:
        selected_resin = st.selectbox(
            "Select Resin",
            available_resins
        )

    with col_f2:
        selected_vendors = st.multiselect(
            "Select Vendor(s)",
            available_vendors,
            default=available_vendors
        )

    filtered_data = analysis_df[
        (analysis_df["Resin"].astype(str) == str(selected_resin)) &
        (analysis_df["Vendor"].astype(str).isin(selected_vendors))
    ].copy()

    if filtered_data.empty:
        st.info("No valid data available for the selected Resin and Vendor.")
    else:
        col_heat1, col_heat2 = st.columns(2)

        # -------------------------------------------------
        # Heatmap 1: Initial viscosity vs solvent ratio
        # -------------------------------------------------
        with col_heat1:
            st.markdown("#### Formula Efficiency: Initial Viscosity vs. Solvent Ratio")

            solvent_bins = [0, 2, 4, 6, 8, 10, 12, 15, 20, 30, 50]
            viscosity_bins = [0, 50, 70, 90, 110, 130, 150, 170, 190, 210, 250, 500]

            filtered_data["Solvent_Bin"] = pd.cut(
                filtered_data["Solvent_Ratio_Percent"],
                bins=solvent_bins,
                include_lowest=True
            )

            filtered_data["Initial_V_Bin"] = pd.cut(
                filtered_data["黏度(秒)"],
                bins=viscosity_bins,
                include_lowest=True
            )

            heatmap_data = (
                filtered_data
                .groupby(
                    ["Initial_V_Bin", "Solvent_Bin"],
                    observed=False
                )["Sensitivity"]
                .median()
                .reset_index()
            )

            pivot_table = heatmap_data.pivot(
                index="Initial_V_Bin",
                columns="Solvent_Bin",
                values="Sensitivity"
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

            st.plotly_chart(
                fig_heatmap,
                use_container_width=True
            )

        # -------------------------------------------------
        # Heatmap 2: Temperature vs humidity
        # -------------------------------------------------
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

                st.plotly_chart(
                    fig_env,
                    use_container_width=True
                )

        st.caption(
            "Note: The environment heatmap is observational. Results may also be affected by paint formula, "
            "paint batch, solvent type, operator, and production conditions."
        )


# =========================================================
# TASK 2: RECOMMENDATION ENGINE + SOP MATRIX
# =========================================================
with tab_ai:
    st.markdown("### 🧠 Solvent Recommendation Engine")

    st.caption(
        "The system recommends solvent addition based on historical records with similar "
        "Resin, Vendor, viscosity, temperature, and humidity."
    )

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
        coil_paint_qty = st.number_input(
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

        base_subset = analysis_df[
            (analysis_df["Resin"].astype(str) == str(selected_resin)) &
            (analysis_df["Vendor"].astype(str).isin(selected_vendors))
        ].copy()

        # Similar initial viscosity: ±15 seconds
        visc_mask = (
            (base_subset["黏度(秒)"] >= curr_viscosity - 15) &
            (base_subset["黏度(秒)"] <= curr_viscosity + 15)
        )

        # Similar environment: Temp ±5°C and Humidity ±10%
        weather_mask = (
            (base_subset["溫度"] >= curr_temp - 5) &
            (base_subset["溫度"] <= curr_temp + 5) &
            (base_subset["濕度"] >= curr_humidity - 10) &
            (base_subset["濕度"] <= curr_humidity + 10)
        )

        subset_strict = base_subset[visc_mask & weather_mask].copy()
        subset_partial = base_subset[visc_mask].copy()
        subset_general = base_subset.copy()

        expected_sensitivity = np.nan
        selected_subset = pd.DataFrame()
        match_type = ""

        # Require at least 5 records for recommendation
        if len(subset_strict) >= 5:
            expected_sensitivity = subset_strict["Sensitivity"].median()
            selected_subset = subset_strict
            match_type = "strict"

        elif len(subset_partial) >= 5:
            expected_sensitivity = subset_partial["Sensitivity"].median()
            selected_subset = subset_partial
            match_type = "partial"

        elif len(subset_general) >= 5:
            expected_sensitivity = subset_general["Sensitivity"].median()
            selected_subset = subset_general
            match_type = "general"

        if pd.isna(expected_sensitivity) or expected_sensitivity <= 0:
            st.error(
                "❌ Unable to calculate recommendation. "
                "At least 5 valid historical records are required."
            )

        else:
            sample_size = len(selected_subset)

            confidence_label, confidence_color = calculate_confidence_label(
                sample_size,
                match_type
            )

            historical_floor_p10 = safe_quantile(
                selected_subset["黏度(秒)_1"],
                0.10
            )

            historical_ratio_p90 = safe_quantile(
                selected_subset["Solvent_Ratio_Percent"],
                0.90
            )

            historical_ratio_p95 = safe_quantile(
                selected_subset["Solvent_Ratio_Percent"],
                0.95
            )

            theoretical_ratio = viscosity_drop / expected_sensitivity
            theoretical_solvent_kg = coil_paint_qty * theoretical_ratio / 100

            # Staged Addition: 65% first, then max 35%
            stage_1_ratio = theoretical_ratio * 0.65
            stage_1_kg = coil_paint_qty * stage_1_ratio / 100

            stage_2_ratio = theoretical_ratio * 0.35
            stage_2_kg = coil_paint_qty * stage_2_ratio / 100

            floor_warning = (
                not pd.isna(historical_floor_p10)
                and target_viscosity < historical_floor_p10
            )

            ratio_warning = (
                not pd.isna(historical_ratio_p90)
                and theoretical_ratio > historical_ratio_p90
            )

            critical_ratio_warning = (
                not pd.isna(historical_ratio_p95)
                and theoretical_ratio > historical_ratio_p95
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
                        Recommended Total Addition:
                        <span style="color:#4472C4;">
                            {theoretical_solvent_kg:.2f} kg
                        </span>
                    </h3>
                    <p><b>Required Viscosity Reduction:</b> {viscosity_drop:.2f} s</p>
                    <p><b>Historical Median Sensitivity:</b> {expected_sensitivity:.2f} s per 1% solvent</p>
                    <p><b>Calculated Solvent Ratio:</b> {theoretical_ratio:.2f}%</p>
                    <p><b>Matched Historical Records:</b> {sample_size}</p>
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

            st.markdown("#### Recommended Addition Method")

            col_stage1, col_stage2 = st.columns(2)

            with col_stage1:
                st.metric(
                    "Stage 1 Addition",
                    f"{stage_1_kg:.2f} kg",
                    f"{stage_1_ratio:.2f}% of paint weight"
                )

            with col_stage2:
                st.metric(
                    "Stage 2 Maximum Addition",
                    f"{stage_2_kg:.2f} kg",
                    f"{stage_2_ratio:.2f}% of paint weight"
                )

            st.info(
                "Operation instruction: Add Stage 1 first, mix thoroughly, measure viscosity again, "
                "then add Stage 2 gradually only if needed."
            )

            st.markdown("#### Historical Safety Reference")

            col_ref1, col_ref2, col_ref3 = st.columns(3)

            with col_ref1:
                st.metric(
                    "Historical Low Viscosity P10",
                    f"{historical_floor_p10:.2f} s"
                    if not pd.isna(historical_floor_p10)
                    else "N/A"
                )

            with col_ref2:
                st.metric(
                    "Historical Solvent Ratio P90",
                    f"{historical_ratio_p90:.2f}%"
                    if not pd.isna(historical_ratio_p90)
                    else "N/A"
                )

            with col_ref3:
                st.metric(
                    "Historical Solvent Ratio P95",
                    f"{historical_ratio_p95:.2f}%"
                    if not pd.isna(historical_ratio_p95)
                    else "N/A"
                )

            if floor_warning:
                st.warning(
                    f"⚠️ Target viscosity ({target_viscosity:.2f}s) is below the historical P10 "
                    f"viscosity reference ({historical_floor_p10:.2f}s). "
                    "Do not add the full calculated amount at once."
                )

            if ratio_warning:
                st.warning(
                    f"⚠️ Calculated solvent ratio ({theoretical_ratio:.2f}%) exceeds historical P90 "
                    f"({historical_ratio_p90:.2f}%). "
                    "Use staged addition and re-check viscosity after each addition."
                )

            if critical_ratio_warning:
                st.error(
                    f"🚨 Calculated solvent ratio ({theoretical_ratio:.2f}%) exceeds historical P95 "
                    f"({historical_ratio_p95:.2f}%). "
                    "This may indicate saturation risk or insufficient matching data."
                )

    # =====================================================
    # SOP MATRIX
    # =====================================================
    st.markdown("---")
    st.markdown("### 📚 SOP Coefficient Matrix")

    st.caption(
        "The matrix is grouped only by Resin, Vendor, and Initial Viscosity Range."
    )

    matrix_df = analysis_df.copy()

    matrix_df["Viscosity_Zone"] = (
        matrix_df.groupby("Resin")["黏度(秒)"]
        .transform(generate_dynamic_bins)
    )

    target_viscosity_map = (
        matrix_df
        .groupby(
            ["Resin", "Vendor"],
            dropna=False
        )
        .agg(
            Typical_Target_Viscosity=("黏度(秒)_1", "median"),
            Historical_Low_V_P10=(
                "黏度(秒)_1",
                lambda x: safe_quantile(x, 0.10)
            ),
            Historical_Ratio_P90=(
                "Solvent_Ratio_Percent",
                lambda x: safe_quantile(x, 0.90)
            ),
            Total_Group_Samples=("塗料批號", "nunique")
        )
        .reset_index()
    )

    sensitivity_map = (
        matrix_df
        .groupby(
            ["Resin", "Vendor", "Viscosity_Zone"],
            observed=False,
            dropna=False
        )
        .agg(
            Median_Sensitivity=("Sensitivity", "median"),
            Records_in_Zone=("塗料批號", "nunique")
        )
        .reset_index()
    )

    # Keep zones with at least 3 records
    sensitivity_map = sensitivity_map[
        (sensitivity_map["Median_Sensitivity"] > 0) &
        (sensitivity_map["Records_in_Zone"] >= 3)
    ].copy()

    sop_grouped = sensitivity_map.merge(
        target_viscosity_map,
        on=["Resin", "Vendor"],
        how="left"
    )

    if sop_grouped.empty:
        st.info("No SOP coefficient matrix can be generated from the current data.")

    else:
        sop_grouped["Solvent % per 1s Drop"] = (
            1 / sop_grouped["Median_Sensitivity"]
        )

        sop_grouped["Factor (kg per 100kg paint / 1s)"] = (
            sop_grouped["Solvent % per 1s Drop"]
        )

        sop_display = sop_grouped.rename(columns={
            "Viscosity_Zone": "Initial Viscosity Range",
            "Typical_Target_Viscosity": "Typical Target V (s)",
            "Historical_Low_V_P10": "Historical Low V P10 (s)",
            "Historical_Ratio_P90": "Historical Ratio P90 (%)",
            "Median_Sensitivity": "Median Sensitivity (s/%)",
            "Records_in_Zone": "Records in Zone",
            "Total_Group_Samples": "Total Group Samples"
        })

        sop_display = sop_display[
            [
                "Resin",
                "Vendor",
                "Initial Viscosity Range",
                "Typical Target V (s)",
                "Historical Low V P10 (s)",
                "Historical Ratio P90 (%)",
                "Median Sensitivity (s/%)",
                "Solvent % per 1s Drop",
                "Factor (kg per 100kg paint / 1s)",
                "Records in Zone",
                "Total Group Samples"
            ]
        ].copy()

        numeric_sop_columns = [
            "Typical Target V (s)",
            "Historical Low V P10 (s)",
            "Historical Ratio P90 (%)",
            "Median Sensitivity (s/%)",
            "Solvent % per 1s Drop",
            "Factor (kg per 100kg paint / 1s)"
        ]

        sop_display[numeric_sop_columns] = (
            sop_display[numeric_sop_columns].round(2)
        )

        st.dataframe(
            sop_display.sort_values(
                by=["Resin", "Vendor", "Initial Viscosity Range"]
            ),
            column_config={
                "Typical Target V (s)": st.column_config.NumberColumn(format="%.2f"),
                "Historical Low V P10 (s)": st.column_config.NumberColumn(format="%.2f"),
                "Historical Ratio P90 (%)": st.column_config.NumberColumn(format="%.2f"),
                "Median Sensitivity (s/%)": st.column_config.NumberColumn(format="%.2f"),
                "Solvent % per 1s Drop": st.column_config.NumberColumn(format="%.2f"),
                "Factor (kg per 100kg paint / 1s)": st.column_config.NumberColumn(format="%.2f")
            },
            use_container_width=True,
            hide_index=True
        )

        csv = sop_display.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            label="📥 Download SOP Coefficient Matrix as CSV",
            data=csv,
            file_name="SOP_Master_Coefficient_Matrix.csv",
            mime="text/csv"
        )
