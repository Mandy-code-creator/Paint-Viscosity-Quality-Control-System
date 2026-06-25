import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="Solvent Dosing Recommendation & SOP Control",
    page_icon="🧪",
    layout="wide"
)

st.title("🧪 Solvent Dosing Recommendation & SOP Control")
st.caption(
    "Historical dilution analysis, solvent dosing recommendation, "
    "risk limits, engineering matrix, and work instruction."
)
st.divider()

# =========================================================
# CONSTANTS
# =========================================================
MIN_OPERATING_PAINT_KG = 120.0
MIN_REF_RECORDS = 3
MIN_RECOMMEND_RECORDS = 5
RELIABLE_RECORDS = 10

STAGE_1_PERCENT = 0.60
STAGE_2_PERCENT = 0.25
FINE_ADJUST_PERCENT = 0.15

ZONE_ORDER = ["≤70 s", "71–90 s", "91–110 s", "111–130 s", ">130 s"]


# =========================================================
# HELPERS
# =========================================================
def clean_text(series, default="Unknown"):
    return (
        series.fillna(default)
        .astype(str)
        .str.strip()
        .replace("", default)
    )


def q(series, percentile):
    values = pd.to_numeric(series, errors="coerce").dropna()
    return values.quantile(percentile) if not values.empty else np.nan


def confidence(records):
    if records >= RELIABLE_RECORDS:
        return "Reliable", "✅"
    if records >= MIN_RECOMMEND_RECORDS:
        return "Usable with Caution", "⚠️"
    if records >= MIN_REF_RECORDS:
        return "Limited Data", "🟡"
    return "Insufficient Data", "🔴"


def get_zone(viscosity):
    if viscosity <= 70:
        return "≤70 s"
    if viscosity <= 90:
        return "71–90 s"
    if viscosity <= 110:
        return "91–110 s"
    if viscosity <= 130:
        return "111–130 s"
    return ">130 s"


def add_zone_columns(data):
    data = data.copy()

    data["Viscosity_Zone"] = pd.cut(
        data["黏度(秒)"],
        bins=[-np.inf, 70, 90, 110, 130, np.inf],
        labels=ZONE_ORDER,
        include_lowest=True
    )

    data["Zone_Sort"] = (
        data["Viscosity_Zone"]
        .astype(str)
        .map({zone: i for i, zone in enumerate(ZONE_ORDER, start=1)})
    )

    return data


def make_zone_summary(data, metric):
    result = (
        data.groupby(["Viscosity_Zone", "Zone_Sort"], observed=True)
        .agg(
            Median=(metric, "median"),
            P10=(metric, lambda x: q(x, 0.10)),
            P90=(metric, lambda x: q(x, 0.90)),
            Records=(metric, "size")
        )
        .reset_index()
        .sort_values("Zone_Sort")
    )

    result["Err_Plus"] = (result["P90"] - result["Median"]).clip(lower=0)
    result["Err_Minus"] = (result["Median"] - result["P10"]).clip(lower=0)

    return result


def build_sop_matrix(data):
    matrix = (
        data.groupby(
            ["Resin", "Vendor", "Solvent_Type", "Viscosity_Zone", "Zone_Sort"],
            observed=True
        )
        .agg(
            Typical_Target_V=("黏度(秒)_1", "median"),
            After_V_P10=("黏度(秒)_1", lambda x: q(x, 0.10)),
            After_V_P90=("黏度(秒)_1", lambda x: q(x, 0.90)),
            Ratio_Median=("Solvent_Ratio_Percent", "median"),
            Ratio_P90=("Solvent_Ratio_Percent", lambda x: q(x, 0.90)),
            Ratio_P95=("Solvent_Ratio_Percent", lambda x: q(x, 0.95)),
            Drop_Median=("Delta_V", "median"),
            Drop_P10=("Delta_V", lambda x: q(x, 0.10)),
            Drop_P90=("Delta_V", lambda x: q(x, 0.90)),
            Drop_Max=("Delta_V", "max"),
            Sensitivity_Median=("Sensitivity", "median"),
            Sensitivity_Std=("Sensitivity", "std"),
            Records=("塗料批號", "size")
        )
        .reset_index()
    )

    matrix = matrix[matrix["Records"] >= MIN_REF_RECORDS].copy()

    matrix["Factor_kg_per_100kg_per_1s"] = np.where(
        matrix["Sensitivity_Median"] > 0,
        1 / matrix["Sensitivity_Median"],
        np.nan
    )

    matrix["Stage_1_Coeff"] = matrix["Ratio_Median"] * STAGE_1_PERCENT
    matrix["Stage_2_Coeff"] = matrix["Ratio_Median"] * STAGE_2_PERCENT
    matrix["Fine_Adjust_Coeff"] = matrix["Ratio_Median"] * FINE_ADJUST_PERCENT
    matrix["Max_Total_Coeff"] = matrix["Ratio_P90"]

    matrix[["Data_Confidence", "Confidence_Icon"]] = matrix["Records"].apply(
        lambda x: pd.Series(confidence(x))
    )

    return matrix


def build_recommendation(
    filtered_data,
    current_v,
    target_lsl,
    target_usl,
    order_paint_kg
):
    if filtered_data.empty:
        return None, "No historical data is available for this group."

    if target_lsl >= target_usl:
        return None, "Approved lower limit must be less than upper limit."

    target_center = (target_lsl + target_usl) / 2
    required_drop = current_v - target_center
    dilution_base = order_paint_kg + MIN_OPERATING_PAINT_KG

    if required_drop <= 0:
        return {
            "already_in_target": True,
            "target_center": target_center,
            "required_drop": required_drop,
            "dilution_base": dilution_base
        }, None

    current_zone = get_zone(current_v)

    zone_data = filtered_data[
        filtered_data["Viscosity_Zone"].astype(str) == current_zone
    ].copy()

    if len(zone_data) >= MIN_RECOMMEND_RECORDS:
        reference = zone_data
        match_type = f"Matched Zone: {current_zone}"
    else:
        reference = filtered_data
        match_type = "General Historical Reference"

    if len(reference) < MIN_RECOMMEND_RECORDS:
        return None, "At least 5 valid historical records are required."

    sensitivity = reference["Sensitivity"].median()
    required_ratio = required_drop / sensitivity
    total_solvent = dilution_base * required_ratio / 100

    ratio_p90 = q(reference["Solvent_Ratio_Percent"], 0.90)
    ratio_p95 = q(reference["Solvent_Ratio_Percent"], 0.95)
    drop_p90 = q(reference["Delta_V"], 0.90)
    drop_max = reference["Delta_V"].max()

    result = {
        "already_in_target": False,
        "current_zone": current_zone,
        "match_type": match_type,
        "reference_records": len(reference),
        "confidence": confidence(len(reference))[0],
        "target_center": target_center,
        "required_drop": required_drop,
        "dilution_base": dilution_base,
        "sensitivity": sensitivity,
        "required_ratio": required_ratio,
        "total_solvent": total_solvent,
        "stage_1_kg": total_solvent * STAGE_1_PERCENT,
        "stage_2_kg": total_solvent * STAGE_2_PERCENT,
        "fine_adjust_kg": total_solvent * FINE_ADJUST_PERCENT,
        "ratio_p90": ratio_p90,
        "ratio_p95": ratio_p95,
        "drop_p90": drop_p90,
        "drop_max": drop_max,
        "max_total_kg": dilution_base * ratio_p90 / 100
    }

    return result, None


# =========================================================
# VALIDATE DATA
# =========================================================
if not st.session_state.get("raw_data_loaded", False):
    st.warning("⚠️ Please upload data on the main page first.")
    st.stop()

if "group_a_data" not in st.session_state:
    st.error("❌ Group A data is not available.")
    st.stop()

raw = st.session_state["group_a_data"].copy()
rejected_data = st.session_state.get("rejected_data", pd.DataFrame())

required_cols = [
    "Resin", "Vendor", "稀釋劑",
    "黏度(秒)", "黏度(秒)_1",
    "添加重量", "塗料重量"
]

missing_cols = [col for col in required_cols if col not in raw.columns]

if missing_cols:
    st.error("❌ Missing required columns: " + ", ".join(missing_cols))
    st.stop()


# =========================================================
# DATA PREPARATION
# =========================================================
df = raw.copy()

for col in ["添加重量", "塗料重量", "黏度(秒)", "黏度(秒)_1", "溫度", "濕度"]:
    df[col] = pd.to_numeric(df.get(col), errors="coerce")

if "塗料批號" not in df.columns:
    df["塗料批號"] = df.index.astype(str)

df["Resin"] = clean_text(df["Resin"])
df["Vendor"] = clean_text(df["Vendor"])
df["Solvent_Type"] = clean_text(df["稀釋劑"])

df["Dilution_Base_Paint_kg"] = df["塗料重量"] + MIN_OPERATING_PAINT_KG
df["Solvent_Ratio_Percent"] = (
    df["添加重量"]
    / df["Dilution_Base_Paint_kg"].replace(0, np.nan)
    * 100
)

df["Delta_V"] = df["黏度(秒)"] - df["黏度(秒)_1"]
df["Sensitivity"] = (
    df["Delta_V"]
    / df["Solvent_Ratio_Percent"].replace(0, np.nan)
)

df = add_zone_columns(df)

analysis_df = df[
    (df["添加重量"] > 0)
    & (df["塗料重量"] > 0)
    & (df["Delta_V"] > 0)
    & (df["Sensitivity"] > 0)
    & (df["Resin"] != "Unknown")
    & (df["Vendor"] != "Unknown")
    & (df["Solvent_Type"] != "Unknown")
].copy()

if not analysis_df.empty:
    low_limit = analysis_df["Sensitivity"].quantile(0.01)
    high_limit = analysis_df["Sensitivity"].quantile(0.99)

    analysis_df = analysis_df[
        analysis_df["Sensitivity"].between(low_limit, high_limit)
    ].copy()

if analysis_df.empty:
    st.warning("⚠️ No valid dilution records found after validation.")
    st.stop()

sop_matrix = build_sop_matrix(analysis_df)


# =========================================================
# KPI
# =========================================================
st.subheader("💡 Historical Mixing Data Overview")

k1, k2, k3, k4 = st.columns(4)

k1.metric("Total Records", f"{len(df):,}")
k2.metric("Valid Adjustment Records", f"{len(analysis_df):,}")
k3.metric("Total Order Paint", f"{df['塗料重量'].sum():,.2f} kg")
k4.metric("Excluded Source Records", f"{len(rejected_data):,}")

st.info(
    f"Calculation Rule: Dilution Base Paint = Order Paint Weight + "
    f"{MIN_OPERATING_PAINT_KG:.0f} kg."
)

st.divider()


# =========================================================
# FILTERS
# =========================================================
f1, f2, f3 = st.columns(3)

with f1:
    selected_resin = st.selectbox(
        "Select Resin",
        sorted(analysis_df["Resin"].unique())
    )

vendor_options = sorted(
    analysis_df.loc[
        analysis_df["Resin"] == selected_resin,
        "Vendor"
    ].unique()
)

with f2:
    selected_vendor = st.selectbox("Select Vendor", vendor_options)

solvent_options = sorted(
    analysis_df.loc[
        (analysis_df["Resin"] == selected_resin)
        & (analysis_df["Vendor"] == selected_vendor),
        "Solvent_Type"
    ].unique()
)

with f3:
    selected_solvent = st.selectbox(
        "Select Solvent Type",
        solvent_options
    )

filtered_data = analysis_df[
    (analysis_df["Resin"] == selected_resin)
    & (analysis_df["Vendor"] == selected_vendor)
    & (analysis_df["Solvent_Type"] == selected_solvent)
].copy()


# =========================================================
# TABS
# =========================================================
tab_analysis, tab_sop, tab_matrix, tab_worker = st.tabs([
    "📊 Historical Analysis",
    "🧠 SOP Recommendation",
    "📚 Engineering Matrix",
    "📄 稀釋作業指導書"
])


# =========================================================
# TAB 1 — HISTORICAL ANALYSIS
# =========================================================
with tab_analysis:
    st.subheader("📊 Historical Dilution Behavior")

    if filtered_data.empty:
        st.info("No valid historical records for this group.")

    else:
        c1, c2 = st.columns(2)

        with c1:
            fig = px.scatter(
                filtered_data,
                x="Solvent_Ratio_Percent",
                y="Delta_V",
                color="Viscosity_Zone",
                category_orders={"Viscosity_Zone": ZONE_ORDER},
                hover_data=[
                    "黏度(秒)",
                    "黏度(秒)_1",
                    "添加重量",
                    "塗料重量",
                    "溫度",
                    "濕度"
                ],
                labels={
                    "Solvent_Ratio_Percent": "Solvent Ratio (%)",
                    "Delta_V": "Viscosity Drop (s)",
                    "Viscosity_Zone": "Initial Viscosity Zone"
                },
                title="Solvent Ratio vs. Viscosity Reduction"
            )
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            summary = make_zone_summary(filtered_data, "Delta_V")

            fig = px.bar(
                summary,
                x="Viscosity_Zone",
                y="Median",
                error_y="Err_Plus",
                error_y_minus="Err_Minus",
                text="Median",
                category_orders={"Viscosity_Zone": ZONE_ORDER},
                labels={
                    "Viscosity_Zone": "Initial Viscosity Zone",
                    "Median": "Median Viscosity Drop (s)"
                },
                title="Median Viscosity Drop by Zone"
            )

            fig.update_traces(
                texttemplate="%{text:.1f}",
                textposition="outside"
            )

            st.plotly_chart(fig, use_container_width=True)

        c3, c4 = st.columns(2)

        with c3:
            fig = px.scatter(
                filtered_data,
                x="Solvent_Ratio_Percent",
                y="Sensitivity",
                color="Viscosity_Zone",
                category_orders={"Viscosity_Zone": ZONE_ORDER},
                hover_data=["黏度(秒)", "黏度(秒)_1", "Delta_V"],
                labels={
                    "Solvent_Ratio_Percent": "Solvent Ratio (%)",
                    "Sensitivity": "Dilution Sensitivity (s / %)",
                    "Viscosity_Zone": "Initial Viscosity Zone"
                },
                title="Solvent Ratio vs. Dilution Efficiency"
            )
            st.plotly_chart(fig, use_container_width=True)

        with c4:
            summary = make_zone_summary(filtered_data, "黏度(秒)_1")

            fig = px.bar(
                summary,
                x="Viscosity_Zone",
                y="Median",
                error_y="Err_Plus",
                error_y_minus="Err_Minus",
                text="Median",
                category_orders={"Viscosity_Zone": ZONE_ORDER},
                labels={
                    "Viscosity_Zone": "Initial Viscosity Zone",
                    "Median": "Median After-Dilution Viscosity (s)"
                },
                title="After-Dilution Viscosity by Zone"
            )

            fig.update_traces(
                texttemplate="%{text:.1f}",
                textposition="outside"
            )

            st.plotly_chart(fig, use_container_width=True)


# =========================================================
# SHARED INPUTS FOR SOP + WORKER INSTRUCTION
# =========================================================
default_lsl = float(filtered_data["黏度(秒)_1"].quantile(0.25))
default_usl = float(filtered_data["黏度(秒)_1"].quantile(0.75))

if "current_v" not in st.session_state:
    st.session_state.current_v = 90.0

if "target_lsl" not in st.session_state:
    st.session_state.target_lsl = default_lsl

if "target_usl" not in st.session_state:
    st.session_state.target_usl = default_usl

if "order_paint_kg" not in st.session_state:
    st.session_state.order_paint_kg = 80.0


# =========================================================
# TAB 2 — SOP RECOMMENDATION
# =========================================================
with tab_sop:
    st.subheader("🧠 Solvent Recommendation")

    i1, i2, i3, i4 = st.columns(4)

    with i1:
        current_v = st.number_input(
            "Current Viscosity (s)",
            min_value=0.0,
            step=1.0,
            key="current_v"
        )

    with i2:
        target_lsl = st.number_input(
            "Approved Lower Limit (s)",
            min_value=0.0,
            step=1.0,
            key="target_lsl"
        )

    with i3:
        target_usl = st.number_input(
            "Approved Upper Limit (s)",
            min_value=0.0,
            step=1.0,
            key="target_usl"
        )

    with i4:
        order_paint_kg = st.number_input(
            "Order Paint Weight (kg)",
            min_value=0.0,
            step=1.0,
            key="order_paint_kg"
        )

    recommendation, error_message = build_recommendation(
        filtered_data=filtered_data,
        current_v=current_v,
        target_lsl=target_lsl,
        target_usl=target_usl,
        order_paint_kg=order_paint_kg
    )

    if error_message:
        st.error(f"❌ {error_message}")

    elif recommendation["already_in_target"]:
        st.success("✅ Current viscosity is already within or below the target range.")

    else:
        r1, r2, r3, r4 = st.columns(4)

        r1.metric(
            "Recommended Total Solvent",
            f"{recommendation['total_solvent']:.2f} kg"
        )

        r2.metric(
            "Required Viscosity Drop",
            f"{recommendation['required_drop']:.2f} s"
        )

        r3.metric(
            "Calculated Solvent Ratio",
            f"{recommendation['required_ratio']:.2f}%"
        )

        r4.metric(
            "Historical Sensitivity",
            f"{recommendation['sensitivity']:.2f} s/%"
        )

        st.caption(
            f"{recommendation['match_type']} | "
            f"Reference Records: {recommendation['reference_records']} | "
            f"Confidence: {recommendation['confidence']}"
        )

        st.markdown("#### Recommended Staged Addition")

        s1, s2, s3 = st.columns(3)

        s1.metric(
            "Stage 1: Initial Addition",
            f"{recommendation['stage_1_kg']:.2f} kg"
        )

        s2.metric(
            "Stage 2: Re-check Addition",
            f"{recommendation['stage_2_kg']:.2f} kg"
        )

        s3.metric(
            "Stage 3: Fine Adjustment",
            f"{recommendation['fine_adjust_kg']:.2f} kg"
        )

        st.markdown("#### Historical Risk Boundaries")

        b1, b2, b3, b4 = st.columns(4)

        b1.metric("Historical Ratio P90", f"{recommendation['ratio_p90']:.2f}%")
        b2.metric("Historical Ratio P95", f"{recommendation['ratio_p95']:.2f}%")
        b3.metric("Historical Drop P90", f"{recommendation['drop_p90']:.2f} s")
        b4.metric("Historical Maximum Drop", f"{recommendation['drop_max']:.2f} s")

        if recommendation["required_ratio"] > recommendation["ratio_p95"]:
            st.error("🚨 Required ratio exceeds Historical P95. QE confirmation is required.")

        elif recommendation["required_ratio"] > recommendation["ratio_p90"]:
            st.warning("⚠️ Required ratio exceeds Historical P90. Use staged addition carefully.")

        if recommendation["required_drop"] > recommendation["drop_max"]:
            st.error("🚨 Required viscosity reduction exceeds the historical maximum.")


# =========================================================
# TAB 3 — ENGINEERING MATRIX
# =========================================================
with tab_matrix:
    st.subheader("📚 Full SOP Coefficient Matrix")

    display_matrix = sop_matrix.copy()

    display_matrix = display_matrix.rename(columns={
        "Solvent_Type": "Solvent Type",
        "Viscosity_Zone": "Initial Viscosity Range",
        "Typical_Target_V": "Typical Target V (s)",
        "After_V_P10": "After V P10 (s)",
        "After_V_P90": "After V P90 (s)",
        "Ratio_Median": "Ratio Median (%)",
        "Ratio_P90": "Ratio P90 (%)",
        "Ratio_P95": "Ratio P95 (%)",
        "Drop_Median": "Typical Drop (s)",
        "Drop_P10": "Drop P10 (s)",
        "Drop_P90": "Drop P90 (s)",
        "Drop_Max": "Max Historical Drop (s)",
        "Sensitivity_Median": "Sensitivity Median (s/%)",
        "Sensitivity_Std": "Sensitivity Std",
        "Factor_kg_per_100kg_per_1s": "Factor (kg/100kg/1s)",
        "Stage_1_Coeff": "Stage 1 Coeff. (kg/100kg)",
        "Stage_2_Coeff": "Stage 2 Coeff. (kg/100kg)",
        "Fine_Adjust_Coeff": "Fine Adjust Coeff. (kg/100kg)",
        "Max_Total_Coeff": "Max Total Coeff. (kg/100kg)"
    })

    display_matrix = display_matrix.sort_values(
        ["Resin", "Vendor", "Solvent Type", "Zone_Sort"]
    ).drop(columns=["Zone_Sort"])

    numeric_cols = display_matrix.select_dtypes(
        include=np.number
    ).columns.tolist()

    display_matrix[numeric_cols] = display_matrix[numeric_cols].round(2)

    st.dataframe(
        display_matrix,
        use_container_width=True,
        hide_index=True
    )

    st.download_button(
        "📥 Download Engineering Matrix",
        data=display_matrix.to_csv(index=False).encode("utf-8-sig"),
        file_name="Solvent_Engineering_Matrix.csv",
        mime="text/csv"
    )


# =========================================================
# TAB 4 — WORK INSTRUCTION
# =========================================================
with tab_worker:
    st.subheader("📄 塗料稀釋作業指導書")

    recommendation, error_message = build_recommendation(
        filtered_data=filtered_data,
        current_v=st.session_state.current_v,
        target_lsl=st.session_state.target_lsl,
        target_usl=st.session_state.target_usl,
        order_paint_kg=st.session_state.order_paint_kg
    )

    if error_message:
        st.warning(f"⚠️ {error_message}")

    elif recommendation["already_in_target"]:
        st.success("✅ 目前黏度已在核准範圍內，不需添加稀釋劑。")

    else:
        work_instruction = pd.DataFrame({
            "項目": [
                "樹脂種類",
                "塗料供應商",
                "指定稀釋劑",
                "目前黏度",
                "核准黏度範圍",
                "訂單塗料重量",
                "設備最低運轉塗料量",
                "稀釋計算總塗料量",
                "建議總添加量",
                "第一次添加量",
                "第二次添加量",
                "每次微調量",
                "最大允許添加量"
            ],
            "作業標準": [
                selected_resin,
                selected_vendor,
                selected_solvent,
                f"{st.session_state.current_v:.2f} 秒",
                f"{st.session_state.target_lsl:.2f} – {st.session_state.target_usl:.2f} 秒",
                f"{st.session_state.order_paint_kg:.2f} kg",
                f"{MIN_OPERATING_PAINT_KG:.2f} kg",
                f"{recommendation['dilution_base']:.2f} kg",
                f"{recommendation['total_solvent']:.2f} kg",
                f"{recommendation['stage_1_kg']:.2f} kg",
                f"{recommendation['stage_2_kg']:.2f} kg",
                f"{recommendation['fine_adjust_kg']:.2f} kg",
                f"{recommendation['max_total_kg']:.2f} kg"
            ]
        })

        st.dataframe(
            work_instruction,
            use_container_width=True,
            hide_index=True
        )

        st.markdown("#### 作業步驟")

        st.info(
            f"""
1. 先加入第一次添加量：**{recommendation['stage_1_kg']:.2f} kg**。  
2. 完成攪拌後，重新量測黏度。  
3. 若黏度仍高於核准範圍，再加入第二次添加量：**{recommendation['stage_2_kg']:.2f} kg**。  
4. 最後僅可依每次微調量：**{recommendation['fine_adjust_kg']:.2f} kg** 逐次添加。  
5. 總添加量不得超過：**{recommendation['max_total_kg']:.2f} kg**。  
6. 若仍無法進入核准黏度範圍，請通知 QE / 製程工程師確認。  
            """
        )

        st.download_button(
            "📥 Download Work Instruction",
            data=work_instruction.to_csv(index=False).encode("utf-8-sig"),
            file_name="Paint_Dilution_Work_Instruction.csv",
            mime="text/csv"
        )
