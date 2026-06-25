import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# =========================================================
# [S00] PAGE CONFIGURATION
# =========================================================
st.set_page_config(page_title="Solvent Analysis", page_icon="🧪", layout="wide")
st.title("🧪 Solvent Sensitivity & SOP Recommendation System")
st.caption("Historical dilution analysis: Resin + Vendor + Solvent Type + Initial Viscosity Zone")
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
VISCOSITY_ZONE_ORDER = ["≤70 s", "71–90 s", "91–110 s", "111–130 s", ">130 s"]

# =========================================================
# [S02] HELPER FUNCTIONS
# =========================================================
def safe_quantile(series, q, default=np.nan):
    values = pd.to_numeric(series, errors="coerce").dropna()
    return default if values.empty else values.quantile(q)

def normalize_text(series, default="Unknown"):
    return series.fillna(default).astype(str).str.strip().replace("", default)

def get_confidence(n):
    if n >= MIN_RECORDS_RELIABLE:
        return "Reliable", "✅"
    if n >= MIN_RECORDS_FOR_RECOMMENDATION:
        return "Usable with Caution", "⚠️"
    if n >= MIN_RECORDS_FOR_REFERENCE:
        return "Limited Data", "🟡"
    return "Insufficient Data", "🔴"

def viscosity_zone(value):
    if value <= 70:
        return "≤70 s"
    if value <= 90:
        return "71–90 s"
    if value <= 110:
        return "91–110 s"
    if value <= 130:
        return "111–130 s"
    return ">130 s"

def zone_sort(zone):
    return {z: i + 1 for i, z in enumerate(VISCOSITY_ZONE_ORDER)}.get(str(zone), 999)

def zone_summary(data, metric):
    result = (
        data.groupby(["Viscosity_Zone", "Zone_Sort"], observed=False)
        .agg(
            Median=(metric, "median"),
            P10=(metric, lambda x: safe_quantile(x, 0.10)),
            P90=(metric, lambda x: safe_quantile(x, 0.90)),
            Records=(metric, "size"),
        )
        .reset_index()
    )
    result = result[result["Records"] > 0].copy()
    result["Err_Plus"] = (result["P90"] - result["Median"]).clip(lower=0)
    result["Err_Minus"] = (result["Median"] - result["P10"]).clip(lower=0)
    return result.sort_values("Zone_Sort")

# =========================================================
# [S03] DATA VALIDATION
# =========================================================
if not st.session_state.get("raw_data_loaded", False):
    st.warning("⚠️ Please upload data on the main page first.")
    st.stop()
if "group_a_data" not in st.session_state:
    st.error("❌ Group A data is not available.")
    st.stop()

raw = st.session_state["group_a_data"].copy()
rejected_data = st.session_state.get("rejected_data", pd.DataFrame())

required = ["Resin", "Vendor", "稀釋劑", "黏度(秒)", "黏度(秒)_1", "添加重量", "塗料重量"]
missing = [c for c in required if c not in raw.columns]
if missing:
    st.error("❌ Missing required columns: " + ", ".join(missing))
    st.stop()

# =========================================================
# [S04] DATA PREPROCESSING
# =========================================================
df = raw.copy()
for c in ["添加重量", "塗料重量", "黏度(秒)", "黏度(秒)_1", "溫度", "濕度"]:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    else:
        df[c] = np.nan
if "塗料批號" not in df.columns:
    df["塗料批號"] = df.index.astype(str)

df["Resin"] = normalize_text(df["Resin"])
df["Vendor"] = normalize_text(df["Vendor"])
df["Solvent_Type"] = normalize_text(df["稀釋劑"])

# =========================================================
# [S05] CORE CALCULATIONS
# =========================================================
# [S05.01] Dilution Base = 塗料重量 + 120 kg
df["Minimum_Operating_Paint_kg"] = MIN_OPERATING_PAINT_KG
df["Dilution_Base_Paint_kg"] = df["塗料重量"] + MIN_OPERATING_PAINT_KG

# [S05.02] Ratio / Delta V / Sensitivity
df["Solvent_Ratio_Percent"] = df["添加重量"] / df["Dilution_Base_Paint_kg"].replace(0, np.nan) * 100
df["Delta_V"] = df["黏度(秒)"] - df["黏度(秒)_1"]
df["Sensitivity"] = df["Delta_V"] / df["Solvent_Ratio_Percent"].replace(0, np.nan)

# [S05.03] Fixed viscosity zone
df["Viscosity_Zone"] = pd.cut(
    df["黏度(秒)"],
    bins=[-np.inf, 70, 90, 110, 130, np.inf],
    labels=VISCOSITY_ZONE_ORDER,
    include_lowest=True,
)
df["Zone_Sort"] = df["Viscosity_Zone"].apply(zone_sort)

# =========================================================
# [S06] VALID RECORD FILTER
# =========================================================
analysis_df = df[
    (df["添加重量"] > 0)
    & (df["塗料重量"] > 0)
    & (df["Solvent_Ratio_Percent"] > 0)
    & (df["Delta_V"] > 0)
    & (df["Sensitivity"] > 0)
    & (df["Resin"] != "Unknown")
    & (df["Vendor"] != "Unknown")
    & (df["Solvent_Type"] != "Unknown")
].copy()

if not analysis_df.empty:
    low = analysis_df["Sensitivity"].quantile(0.01)
    high = analysis_df["Sensitivity"].quantile(0.99)
    analysis_df = analysis_df[
        (analysis_df["Sensitivity"] >= low) & (analysis_df["Sensitivity"] <= high)
    ].copy()

if analysis_df.empty:
    st.warning("⚠️ No valid dilution records found after validation.")
    st.stop()

# =========================================================
# [S07] SOP MATRIX BUILD
# Group: Resin + Vendor + Solvent Type + Viscosity Zone
# =========================================================
sop_matrix = (
    analysis_df.groupby(
        ["Resin", "Vendor", "Solvent_Type", "Viscosity_Zone", "Zone_Sort"],
        observed=False,
    )
    .agg(
        Typical_Target_V=("黏度(秒)_1", "median"),
        After_V_P10=("黏度(秒)_1", lambda x: safe_quantile(x, 0.10)),
        After_V_P90=("黏度(秒)_1", lambda x: safe_quantile(x, 0.90)),
        Ratio_Median=("Solvent_Ratio_Percent", "median"),
        Ratio_P90=("Solvent_Ratio_Percent", lambda x: safe_quantile(x, 0.90)),
        Ratio_P95=("Solvent_Ratio_Percent", lambda x: safe_quantile(x, 0.95)),
        Drop_Median=("Delta_V", "median"),
        Drop_P10=("Delta_V", lambda x: safe_quantile(x, 0.10)),
        Drop_P90=("Delta_V", lambda x: safe_quantile(x, 0.90)),
        Drop_Max=("Delta_V", "max"),
        Sensitivity_Median=("Sensitivity", "median"),
        Sensitivity_Std=("Sensitivity", "std"),
        Records=("塗料批號", "size"),
    )
    .reset_index()
)
sop_matrix["Factor_kg_per_100kg_per_1s"] = np.where(
    sop_matrix["Sensitivity_Median"] > 0,
    1 / sop_matrix["Sensitivity_Median"],
    np.nan,
)
sop_matrix["Stage_1_Coeff"] = sop_matrix["Ratio_Median"] * STAGE_1_PERCENT
sop_matrix["Stage_2_Coeff"] = sop_matrix["Ratio_Median"] * STAGE_2_PERCENT
sop_matrix["Fine_Adjust_Coeff"] = sop_matrix["Ratio_Median"] * STAGE_3_PERCENT
sop_matrix["Max_Total_Coeff"] = sop_matrix["Ratio_P90"]
sop_matrix["Data_Confidence"] = sop_matrix["Records"].apply(lambda x: get_confidence(x)[0])
sop_matrix["Confidence_Icon"] = sop_matrix["Records"].apply(lambda x: get_confidence(x)[1])
sop_matrix = sop_matrix[sop_matrix["Records"] >= MIN_RECORDS_FOR_REFERENCE].copy()

# =========================================================
# [S08] KPI AREA
# =========================================================
st.subheader("💡 Historical Mixing Data Overview")
a, b, c, d = st.columns(4)
a.metric("Total Records", f"{len(df):,}")
b.metric("Valid Adjustment Records", f"{len(analysis_df):,}")
c.metric("Total Order Paint", f"{df['塗料重量'].sum():,.2f} kg")
d.metric("Rejected / Invalid Records", f"{len(rejected_data):,}")
st.info(f"Calculation rule: Dilution Base Paint = 塗料重量 + {MIN_OPERATING_PAINT_KG:.0f} kg.")
st.markdown("---")

# =========================================================
# [S09] MAIN FILTERS
# Resin → Vendor → Solvent Type
# =========================================================
f1, f2, f3 = st.columns(3)
resins = sorted(analysis_df["Resin"].unique().tolist())
with f1:
    selected_resin = st.selectbox("Select Resin", resins)
vendors = sorted(analysis_df.loc[analysis_df["Resin"] == selected_resin, "Vendor"].unique().tolist())
with f2:
    selected_vendor = st.selectbox("Select Vendor", vendors)
solvents = sorted(
    analysis_df.loc[
        (analysis_df["Resin"] == selected_resin) & (analysis_df["Vendor"] == selected_vendor),
        "Solvent_Type",
    ].unique().tolist()
)
with f3:
    selected_solvent = st.selectbox("Select Solvent Type", solvents)

filtered_data = analysis_df[
    (analysis_df["Resin"] == selected_resin)
    & (analysis_df["Vendor"] == selected_vendor)
    & (analysis_df["Solvent_Type"] == selected_solvent)
].copy()
filtered_sop = sop_matrix[
    (sop_matrix["Resin"] == selected_resin)
    & (sop_matrix["Vendor"] == selected_vendor)
    & (sop_matrix["Solvent_Type"] == selected_solvent)
].copy()

# =========================================================
# [S10] TABS
# =========================================================
tab_analysis, tab_sop, tab_matrix, tab_worker_sop = st.tabs([
    "📊 Historical Analysis",
    "🧠 SOP Recommendation",
    "📚 Engineering Matrix",
    "📄 Worker SOP"
])

# =========================================================
# [S11] HISTORICAL ANALYSIS
# No boxplots: Scatter + Median/P10-P90 bar charts
# =========================================================
with tab_sop:
    st.markdown("### 📊 Historical Dilution Behavior")
    if filtered_data.empty:
        st.info("No valid records for the selected group.")
    else:
        col1, col2 = st.columns(2)

        # [S11.01] Scatter: ratio vs drop
        with col1:
            st.markdown("#### Solvent Ratio vs. Viscosity Reduction")
            fig = px.scatter(
                filtered_data,
                x="Solvent_Ratio_Percent",
                y="Delta_V",
                color="Viscosity_Zone",
                category_orders={"Viscosity_Zone": VISCOSITY_ZONE_ORDER},
                hover_data=["黏度(秒)", "黏度(秒)_1", "添加重量", "塗料重量", "Dilution_Base_Paint_kg", "溫度", "濕度"],
                labels={
                    "Solvent_Ratio_Percent": "Solvent Ratio (%)",
                    "Delta_V": "Viscosity Drop (s)",
                    "Viscosity_Zone": "Initial Viscosity Zone",
                },
            )
            st.plotly_chart(fig, use_container_width=True)

        # [S11.02] Bar: median drop with P10-P90
        with col2:
            st.markdown("#### Median Viscosity Drop by Initial Viscosity Zone")
            summary = zone_summary(filtered_data, "Delta_V")
            fig = px.bar(
                summary,
                x="Viscosity_Zone",
                y="Median",
                error_y="Err_Plus",
                error_y_minus="Err_Minus",
                text="Median",
                category_orders={"Viscosity_Zone": VISCOSITY_ZONE_ORDER},
                hover_data={"P10": ":.2f", "P90": ":.2f", "Records": True},
                labels={"Viscosity_Zone": "Initial Viscosity Zone", "Median": "Median Viscosity Drop (s)"},
            )
            fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

        col3, col4 = st.columns(2)

        # [S11.03] Scatter: ratio vs sensitivity
        with col3:
            st.markdown("#### Solvent Ratio vs. Dilution Efficiency")
            fig = px.scatter(
                filtered_data,
                x="Solvent_Ratio_Percent",
                y="Sensitivity",
                color="Viscosity_Zone",
                category_orders={"Viscosity_Zone": VISCOSITY_ZONE_ORDER},
                hover_data=["黏度(秒)", "黏度(秒)_1", "Delta_V"],
                labels={
                    "Solvent_Ratio_Percent": "Solvent Ratio (%)",
                    "Sensitivity": "Sensitivity (s / %)",
                    "Viscosity_Zone": "Initial Viscosity Zone",
                },
            )
            st.plotly_chart(fig, use_container_width=True)

        # [S11.04] Bar: median after viscosity with P10-P90
        with col4:
            st.markdown("#### Median After-Dilution Viscosity by Zone")
            summary = zone_summary(filtered_data, "黏度(秒)_1")
            fig = px.bar(
                summary,
                x="Viscosity_Zone",
                y="Median",
                error_y="Err_Plus",
                error_y_minus="Err_Minus",
                text="Median",
                category_orders={"Viscosity_Zone": VISCOSITY_ZONE_ORDER},
                hover_data={"P10": ":.2f", "P90": ":.2f", "Records": True},
                labels={"Viscosity_Zone": "Initial Viscosity Zone", "Median": "Median After-Dilution Viscosity (s)"},
            )
            fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

        st.caption("Bar charts show Median with P10–P90 ranges. No boxplots are used.")

# =========================================================
# [S12] SOP RECOMMENDATION
# =========================================================
with tab_sop:
    st.markdown("### 🧠 Solvent Recommendation")

    if filtered_data.empty or filtered_sop.empty:
        st.warning("⚠️ Insufficient historical SOP data for the selected group.")
    else:
        # [S12.01] User input
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            current_v = st.number_input("Current Viscosity (s)", value=90.0, step=1.0, format="%.2f")
        with c2:
            target_lsl = st.number_input(
                "Approved Viscosity Lower Limit (s)",
                value=float(filtered_data["黏度(秒)_1"].quantile(0.25)),
                step=1.0,
                format="%.2f",
            )
        with c3:
            target_usl = st.number_input(
                "Approved Viscosity Upper Limit (s)",
                value=float(filtered_data["黏度(秒)_1"].quantile(0.75)),
                step=1.0,
                format="%.2f",
            )
        with c4:
            order_paint_kg = st.number_input("Order Paint Weight (kg)", value=80.0, min_value=0.0, step=1.0, format="%.2f")

        # [S12.02] Base calculation
        dilution_base_kg = order_paint_kg + MIN_OPERATING_PAINT_KG
        x1, x2, x3 = st.columns(3)
        x1.metric("Order Paint Weight", f"{order_paint_kg:.2f} kg")
        x2.metric("Minimum Operating Paint", f"{MIN_OPERATING_PAINT_KG:.2f} kg")
        x3.metric("Dilution Calculation Total", f"{dilution_base_kg:.2f} kg")

        # [S12.03] Recommendation calculation
        if target_lsl >= target_usl:
            st.error("❌ Approved lower limit must be less than upper limit.")
        else:
            target_center = (target_lsl + target_usl) / 2
            required_drop = current_v - target_center

            if required_drop <= 0:
                st.success("✅ Current viscosity is already within or below target range.")
            else:
                current_zone = viscosity_zone(current_v)
                zone_data = filtered_data[
                    filtered_data["Viscosity_Zone"].astype(str) == current_zone
                ].copy()

                if len(zone_data) >= MIN_RECORDS_FOR_RECOMMENDATION:
                    reference = zone_data
                    match_type = "zone"
                else:
                    reference = filtered_data
                    match_type = "general"

                if len(reference) < MIN_RECORDS_FOR_RECOMMENDATION:
                    st.error("❌ At least 5 valid historical records are required.")
                else:
                    sensitivity = reference["Sensitivity"].median()
                    required_ratio = required_drop / sensitivity
                    total_solvent = dilution_base_kg * required_ratio / 100

                    # [S12.04] Result
                    st.subheader("Recommendation Result")
                    r1, r2, r3 = st.columns(3)
                    r1.metric("Recommended Total Solvent", f"{total_solvent:.2f} kg")
                    r2.metric("Required Viscosity Drop", f"{required_drop:.2f} s")
                    r3.metric("Calculated Solvent Ratio", f"{required_ratio:.2f}%")

                    st.write(f"**Main SOP Group:** {selected_resin} + {selected_vendor} + {selected_solvent}")
                    st.write(f"**Matched Viscosity Zone:** {current_zone}")
                    st.write(f"**Historical Sensitivity Used:** {sensitivity:.2f} s/%")
                    st.write(f"**Reference Records:** {len(reference)}")
                    st.write(f"**Confidence:** {get_confidence(len(reference))[0]}")

                    # [S12.05] Staged addition
                    st.markdown("#### Recommended Staged Addition")
                    p1, p2, p3 = st.columns(3)
                    p1.metric("Stage 1: Initial Addition", f"{total_solvent * STAGE_1_PERCENT:.2f} kg")
                    p2.metric("Stage 2: After Re-check", f"{total_solvent * STAGE_2_PERCENT:.2f} kg")
                    p3.metric("Stage 3: Fine Adjustment", f"{total_solvent * STAGE_3_PERCENT:.2f} kg")

                    # [S12.06] Historical warning boundaries
                    ratio_p90 = safe_quantile(reference["Solvent_Ratio_Percent"], 0.90)
                    ratio_p95 = safe_quantile(reference["Solvent_Ratio_Percent"], 0.95)
                    drop_p90 = safe_quantile(reference["Delta_V"], 0.90)
                    drop_max = safe_quantile(reference["Delta_V"], 1.00)

                    h1, h2, h3, h4 = st.columns(4)
                    h1.metric("Historical Ratio P90", f"{ratio_p90:.2f}%")
                    h2.metric("Historical Ratio P95", f"{ratio_p95:.2f}%")
                    h3.metric("Historical Drop P90", f"{drop_p90:.2f} s")
                    h4.metric("Historical Max Drop", f"{drop_max:.2f} s")

                    if required_ratio > ratio_p90:
                        st.warning("⚠️ Required solvent ratio exceeds historical P90. Use staged addition.")
                    if required_ratio > ratio_p95:
                        st.error("🚨 Required solvent ratio exceeds historical P95. QE confirmation is required.")
                    if required_drop > drop_p90:
                        st.warning("⚠️ Required viscosity reduction exceeds historical P90 range.")
                    if required_drop > drop_max:
                        st.error("🚨 Required viscosity reduction exceeds maximum historical drop.")

# =========================================================
# [S13] FULL SOP MATRIX EXPORT
# Export ALL groups, not only selected filter group
# =========================================================
with tab_matrix:
    st.markdown("### 📚 Full SOP Coefficient Matrix")
    st.caption("Export includes all Resin + Vendor + Solvent Type + Initial Viscosity Zone combinations.")

    if sop_matrix.empty:
        st.warning("⚠️ No SOP matrix records are available.")
    else:
        # [S13.01] Full export table
        export_df = sop_matrix.copy().rename(columns={
            "Solvent_Type": "Solvent Type",
            "Viscosity_Zone": "Initial Viscosity Range",
            "Typical_Target_V": "Typical Target V (s)",
            "After_V_P10": "Historical After V P10 (s)",
            "After_V_P90": "Historical After V P90 (s)",
            "Ratio_Median": "Historical Ratio Median (%)",
            "Ratio_P90": "Historical Ratio P90 (%)",
            "Ratio_P95": "Historical Ratio P95 (%)",
            "Drop_Median": "Typical Viscosity Drop (s)",
            "Drop_P10": "Viscosity Drop P10 (s)",
            "Drop_P90": "Viscosity Drop P90 (s)",
            "Drop_Max": "Max Historical Drop (s)",
            "Sensitivity_Median": "Median Sensitivity (s/%)",
            "Sensitivity_Std": "Sensitivity Std",
            "Factor_kg_per_100kg_per_1s": "Factor (kg/100kg/1s)",
            "Stage_1_Coeff": "Draft Stage 1 Coeff. (kg/100kg)",
            "Stage_2_Coeff": "Draft Stage 2 Coeff. (kg/100kg)",
            "Fine_Adjust_Coeff": "Draft Fine Adjust Coeff. (kg/100kg)",
            "Max_Total_Coeff": "Draft Max Total Coeff. (kg/100kg)",
        })

        display_cols = [
            "Resin", "Vendor", "Solvent Type", "Initial Viscosity Range",
            "Typical Target V (s)", "Historical After V P10 (s)", "Historical After V P90 (s)",
            "Historical Ratio Median (%)", "Historical Ratio P90 (%)", "Historical Ratio P95 (%)",
            "Typical Viscosity Drop (s)", "Viscosity Drop P10 (s)", "Viscosity Drop P90 (s)",
            "Max Historical Drop (s)", "Median Sensitivity (s/%)", "Sensitivity Std",
            "Factor (kg/100kg/1s)", "Draft Stage 1 Coeff. (kg/100kg)",
            "Draft Stage 2 Coeff. (kg/100kg)", "Draft Fine Adjust Coeff. (kg/100kg)",
            "Draft Max Total Coeff. (kg/100kg)", "Records", "Data_Confidence", "Confidence_Icon",
        ]
        numeric_cols = [
            c for c in display_cols
            if c not in ["Resin", "Vendor", "Solvent Type", "Initial Viscosity Range", "Records", "Data_Confidence", "Confidence_Icon"]
        ]

        export_df = export_df[display_cols + ["Zone_Sort"]].copy()
        export_df[numeric_cols] = export_df[numeric_cols].round(2)
        export_df = export_df.sort_values(["Resin", "Vendor", "Solvent Type", "Zone_Sort"]).drop(columns=["Zone_Sort"])

        st.dataframe(
            export_df,
            column_config={c: st.column_config.NumberColumn(format="%.2f") for c in numeric_cols},
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "📥 Download Full SOP Matrix as CSV",
            data=export_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="All_Resin_Vendor_Solvent_SOP_Matrix.csv",
            mime="text/csv",
        )
# =========================================================
# [S14] TAB 4 - WORKER SOP EXPORT
# =========================================================
with tab_worker_sop:
    st.markdown("### 📄 塗料稀釋作業標準書")

    worker_col1, worker_col2 = st.columns(2)

    with worker_col1:
        worker_zone = st.selectbox(
            "稀釋前黏度範圍",
            VISCOSITY_ZONE_ORDER
        )

    with worker_col2:
        worker_order_paint = st.number_input(
            "訂單塗料重量 (kg)",
            min_value=0.0,
            value=80.0,
            step=1.0,
            format="%.2f"
        )

    worker_sop_row = sop_matrix[
        (sop_matrix["Resin"] == selected_resin) &
        (sop_matrix["Vendor"] == selected_vendor) &
        (sop_matrix["Solvent_Type"] == selected_solvent) &
        (sop_matrix["Viscosity_Zone"].astype(str) == worker_zone)
    ].copy()

    if worker_sop_row.empty:
        st.warning("⚠️ 此條件尚無足夠歷史資料可建立 SOP。")

    else:
        selected_sop = worker_sop_row.iloc[0]

        calculation_total_paint = (
            worker_order_paint + MIN_OPERATING_PAINT_KG
        )

        stage_1_kg = (
            calculation_total_paint
            * selected_sop["Draft_Stage_1_Coeff_kg_per_100kg"]
            / 100
        )

        fine_adjust_kg = (
            calculation_total_paint
            * selected_sop["Draft_Fine_Adjust_Coeff_kg_per_100kg"]
            / 100
        )

        max_total_kg = (
            calculation_total_paint
            * selected_sop["Draft_Max_Total_Coeff_kg_per_100kg"]
            / 100
        )

        worker_sop_display = pd.DataFrame({
            "項目": [
                "樹脂種類",
                "塗料供應商",
                "指定稀釋劑",
                "稀釋前黏度範圍",
                "核准稀釋後黏度範圍",
                "訂單塗料重量",
                "設備最低運轉塗料量",
                "稀釋計算總塗料量",
                "第一次添加量",
                "每次微調量",
                "最大總添加量"
            ],
            "作業標準": [
                selected_resin,
                selected_vendor,
                selected_solvent,
                worker_zone,
                (
                    f"{selected_sop['Historical_Low_V_P10']:.2f}"
                    f"–{selected_sop['Historical_High_V_P90']:.2f} 秒"
                ),
                f"{worker_order_paint:.2f} kg",
                f"{MIN_OPERATING_PAINT_KG:.2f} kg",
                f"{calculation_total_paint:.2f} kg",
                f"{stage_1_kg:.2f} kg",
                f"{fine_adjust_kg:.2f} kg",
                f"{max_total_kg:.2f} kg"
            ]
        })

        st.dataframe(
            worker_sop_display,
            use_container_width=True,
            hide_index=True
        )

        st.warning(
            "注意：先添加第一次添加量，依核准攪拌條件完成混合後再量測黏度。"
            "若未達核准範圍，只可依每次微調量逐次添加；"
            "不得超過最大總添加量。"
        )

        worker_csv = worker_sop_display.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            label="📥 Download Worker SOP",
            data=worker_csv,
            file_name="Worker_Paint_Dilution_SOP.csv",
            mime="text/csv"
        )
