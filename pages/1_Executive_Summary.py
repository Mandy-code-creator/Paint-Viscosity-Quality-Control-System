import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

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
    "Historical dilution behavior, solvent dosing recommendation, "
    "engineering matrix, and worker work instruction."
)
st.divider()


# =========================================================
# CONSTANTS
# =========================================================
MIN_OPERATING_PAINT_KG = 120.0

MIN_REFERENCE_RECORDS = 3
MIN_RECOMMEND_RECORDS = 5
MIN_RELIABLE_RECORDS = 10

OUTLIER_FILTER_MIN_RECORDS = 30

STAGE_1_PERCENT = 0.60
STAGE_2_PERCENT = 0.25
FINE_ADJUST_PERCENT = 0.15

ZONE_ORDER = [
    "≤70 s",
    "71–90 s",
    "91–110 s",
    "111–130 s",
    ">130 s"
]


# =========================================================
# HELPER FUNCTIONS
# =========================================================
def clean_text(series, default="Unknown"):
    return (
        series.fillna(default)
        .astype(str)
        .str.strip()
        .replace("", default)
    )


def safe_quantile(series, quantile_value):
    values = pd.to_numeric(series, errors="coerce").dropna()

    if values.empty:
        return np.nan

    return values.quantile(quantile_value)


def get_confidence(record_count):
    if record_count >= MIN_RELIABLE_RECORDS:
        return "Reliable", "✅"

    if record_count >= MIN_RECOMMEND_RECORDS:
        return "Usable with Caution", "⚠️"

    if record_count >= MIN_REFERENCE_RECORDS:
        return "Limited Data", "🟡"

    return "Insufficient Data", "🔴"


def get_viscosity_zone(viscosity):
    if viscosity <= 70:
        return "≤70 s"

    if viscosity <= 90:
        return "71–90 s"

    if viscosity <= 110:
        return "91–110 s"

    if viscosity <= 130:
        return "111–130 s"

    return ">130 s"


def add_viscosity_zone(data):
    data = data.copy()

    data["Viscosity_Zone"] = pd.cut(
        data["黏度(秒)"],
        bins=[-np.inf, 70, 90, 110, 130, np.inf],
        labels=ZONE_ORDER,
        include_lowest=True
    )

    zone_map = {
        "≤70 s": 1,
        "71–90 s": 2,
        "91–110 s": 3,
        "111–130 s": 4,
        ">130 s": 5
    }

    data["Zone_Sort"] = (
        data["Viscosity_Zone"]
        .astype(str)
        .map(zone_map)
        .fillna(999)
    )

    return data


def filter_group_outliers(data):
    """
    Remove P1-P99 Sensitivity outliers only when a Resin+Vendor+Solvent group
    has at least 30 valid records.
    """
    data = data.copy()

    group_cols = ["Resin", "Vendor", "Solvent_Type"]

    def remove_outlier_in_group(group):
        if len(group) < OUTLIER_FILTER_MIN_RECORDS:
            return group

        low_limit = group["Sensitivity"].quantile(0.01)
        high_limit = group["Sensitivity"].quantile(0.99)

        return group[
            group["Sensitivity"].between(low_limit, high_limit)
        ]

    return (
        data.groupby(group_cols, group_keys=False, observed=True)
        .apply(remove_outlier_in_group)
        .copy()
    )


def make_zone_summary(data, metric):
    summary = (
        data.groupby(
            ["Viscosity_Zone", "Zone_Sort"],
            observed=True
        )
        .agg(
            Median=(metric, "median"),
            P10=(metric, lambda x: safe_quantile(x, 0.10)),
            P90=(metric, lambda x: safe_quantile(x, 0.90)),
            Records=(metric, "size")
        )
        .reset_index()
        .sort_values("Zone_Sort")
    )

    summary["Err_Plus"] = (
        summary["P90"] - summary["Median"]
    ).clip(lower=0)

    summary["Err_Minus"] = (
        summary["Median"] - summary["P10"]
    ).clip(lower=0)

    return summary


def build_sop_matrix(data):
    matrix = (
        data.groupby(
            [
                "Resin",
                "Vendor",
                "Solvent_Type",
                "Viscosity_Zone",
                "Zone_Sort"
            ],
            observed=True
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
            Records=("Record_ID", "size")
        )
        .reset_index()
    )

    matrix = matrix[
        matrix["Records"] >= MIN_REFERENCE_RECORDS
    ].copy()

    matrix["Factor_kg_per_100kg_per_1s"] = np.where(
        matrix["Sensitivity_Median"] > 0,
        1 / matrix["Sensitivity_Median"],
        np.nan
    )

    matrix["Stage_1_Coeff"] = (
        matrix["Ratio_Median"] * STAGE_1_PERCENT
    )

    matrix["Stage_2_Coeff"] = (
        matrix["Ratio_Median"] * STAGE_2_PERCENT
    )

    matrix["Fine_Adjust_Coeff"] = (
        matrix["Ratio_Median"] * FINE_ADJUST_PERCENT
    )

    matrix["Max_Total_Coeff"] = matrix["Ratio_P90"]

    matrix[["Data_Confidence", "Confidence_Icon"]] = (
        matrix["Records"]
        .apply(lambda x: pd.Series(get_confidence(x)))
    )

    return matrix


def build_recommendation(
    historical_data,
    current_viscosity,
    approved_lsl,
    approved_usl,
    order_paint_kg
):
    if historical_data.empty:
        return None, "No valid historical data is available for this group."

    if approved_lsl >= approved_usl:
        return None, "Approved lower limit must be less than upper limit."

    target_center = (approved_lsl + approved_usl) / 2
    required_drop = current_viscosity - target_center

    dilution_base = order_paint_kg + MIN_OPERATING_PAINT_KG

    if required_drop <= 0:
        return {
            "already_in_target": True,
            "target_center": target_center,
            "required_drop": required_drop,
            "dilution_base": dilution_base
        }, None

    current_zone = get_viscosity_zone(current_viscosity)

    zone_reference = historical_data[
        historical_data["Viscosity_Zone"].astype(str) == current_zone
    ].copy()

    if len(zone_reference) >= MIN_RECOMMEND_RECORDS:
        reference_data = zone_reference
        match_type = f"Matched Zone: {current_zone}"

    else:
        reference_data = historical_data
        match_type = "General Resin + Vendor + Solvent Reference"

    if len(reference_data) < MIN_RECOMMEND_RECORDS:
        return None, (
            "At least 5 valid historical records are required "
            "before automatic recommendation can be used."
        )

    historical_sensitivity = reference_data["Sensitivity"].median()

    if pd.isna(historical_sensitivity) or historical_sensitivity <= 0:
        return None, "Historical sensitivity cannot be calculated."

    required_ratio = required_drop / historical_sensitivity
    recommended_solvent = dilution_base * required_ratio / 100

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

    max_drop = reference_data["Delta_V"].max()

    risk_status = "Normal"
    risk_message = "Within historical operating range."

    if required_ratio > ratio_p95 or required_drop > max_drop:
        risk_status = "Blocked"
        risk_message = (
            "Automatic recommendation is blocked. "
            "QE / Process Engineer confirmation is required."
        )

    elif required_ratio > ratio_p90 or required_drop > drop_p90:
        risk_status = "Warning"
        risk_message = (
            "Required adjustment exceeds historical P90. "
            "Use staged addition and re-check viscosity after each step."
        )

    max_total_solvent = dilution_base * ratio_p90 / 100

    result = {
        "already_in_target": False,
        "current_zone": current_zone,
        "match_type": match_type,
        "reference_records": len(reference_data),
        "confidence": get_confidence(len(reference_data))[0],
        "target_center": target_center,
        "required_drop": required_drop,
        "dilution_base": dilution_base,
        "historical_sensitivity": historical_sensitivity,
        "required_ratio": required_ratio,
        "recommended_solvent": recommended_solvent,
        "stage_1_kg": recommended_solvent * STAGE_1_PERCENT,
        "stage_2_kg": recommended_solvent * STAGE_2_PERCENT,
        "fine_adjust_kg": recommended_solvent * FINE_ADJUST_PERCENT,
        "ratio_p90": ratio_p90,
        "ratio_p95": ratio_p95,
        "drop_p90": drop_p90,
        "max_drop": max_drop,
        "max_total_solvent": max_total_solvent,
        "risk_status": risk_status,
        "risk_message": risk_message
    }

    return result, None


def create_transition_data(data, max_records):
    """
    Convert each batch into Before and After rows for a connected line chart.
    """
    plot_data = data.copy()

    if len(plot_data) > max_records:
        plot_data = plot_data.tail(max_records).copy()

    before_data = plot_data[
        [
            "Record_ID",
            "Viscosity_Zone",
            "黏度(秒)",
            "黏度(秒)_1",
            "Delta_V",
            "Solvent_Ratio_Percent",
            "添加重量",
            "塗料重量"
        ]
    ].copy()

    before_data["Stage"] = "Before Solvent"
    before_data["Viscosity"] = before_data["黏度(秒)"]

    after_data = plot_data[
        [
            "Record_ID",
            "Viscosity_Zone",
            "黏度(秒)",
            "黏度(秒)_1",
            "Delta_V",
            "Solvent_Ratio_Percent",
            "添加重量",
            "塗料重量"
        ]
    ].copy()

    after_data["Stage"] = "After Solvent"
    after_data["Viscosity"] = after_data["黏度(秒)_1"]

    transition_data = pd.concat(
        [before_data, after_data],
        ignore_index=True
    )

    transition_data["Stage_Order"] = transition_data["Stage"].map({
        "Before Solvent": 1,
        "After Solvent": 2
    })

    transition_data = transition_data.sort_values(
        ["Record_ID", "Stage_Order"]
    )

    return transition_data


# =========================================================
# DATA VALIDATION
# =========================================================
if not st.session_state.get("raw_data_loaded", False):
    st.warning("⚠️ Please upload data on the main page first.")
    st.stop()

if "group_a_data" not in st.session_state:
    st.error("❌ Group A data is not available.")
    st.stop()

raw = st.session_state["group_a_data"].copy()
rejected_data = st.session_state.get("rejected_data", pd.DataFrame())

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
    column
    for column in required_columns
    if column not in raw.columns
]

if missing_columns:
    st.error(
        "❌ Missing required columns: "
        + ", ".join(missing_columns)
    )
    st.stop()


# =========================================================
# DATA PREPARATION
# =========================================================
df = raw.copy()

numeric_columns = [
    "添加重量",
    "塗料重量",
    "黏度(秒)",
    "黏度(秒)_1",
    "溫度",
    "濕度"
]

for column in numeric_columns:
    if column not in df.columns:
        df[column] = np.nan

    df[column] = pd.to_numeric(
        df[column],
        errors="coerce"
    )

if "塗料批號" not in df.columns:
    df["塗料批號"] = df.index.astype(str)

df["Resin"] = clean_text(df["Resin"])
df["Vendor"] = clean_text(df["Vendor"])
df["Solvent_Type"] = clean_text(df["稀釋劑"])

df["Record_ID"] = (
    df["塗料批號"].astype(str)
    + "_"
    + df.index.astype(str)
)

df["Dilution_Base_Paint_kg"] = (
    df["塗料重量"] + MIN_OPERATING_PAINT_KG
)

df["Solvent_Ratio_Percent"] = (
    df["添加重量"]
    / df["Dilution_Base_Paint_kg"].replace(0, np.nan)
    * 100
)

df["Delta_V"] = (
    df["黏度(秒)"] - df["黏度(秒)_1"]
)

df["Sensitivity"] = (
    df["Delta_V"]
    / df["Solvent_Ratio_Percent"].replace(0, np.nan)
)

df = add_viscosity_zone(df)


# =========================================================
# VALID DATA FILTER
# =========================================================
analysis_df = df[
    (df["添加重量"] > 0)
    & (df["塗料重量"] > 0)
    & (df["黏度(秒)"] > 0)
    & (df["黏度(秒)_1"] > 0)
    & (df["Delta_V"] > 0)
    & (df["Sensitivity"] > 0)
    & (df["Resin"] != "Unknown")
    & (df["Vendor"] != "Unknown")
    & (df["Solvent_Type"] != "Unknown")
].copy()

if analysis_df.empty:
    st.warning("⚠️ No valid dilution records found after validation.")
    st.stop()

analysis_df = filter_group_outliers(analysis_df)

if analysis_df.empty:
    st.warning("⚠️ No valid records remain after outlier handling.")
    st.stop()

sop_matrix = build_sop_matrix(analysis_df)


# =========================================================
# KPI AREA
# =========================================================
st.subheader("💡 Historical Mixing Data Overview")

kpi_1, kpi_2, kpi_3, kpi_4 = st.columns(4)

kpi_1.metric(
    "Total Source Records",
    f"{len(df):,}"
)

kpi_2.metric(
    "Valid Adjustment Records",
    f"{len(analysis_df):,}"
)

kpi_3.metric(
    "Total Order Paint",
    f"{df['塗料重量'].sum():,.2f} kg"
)

kpi_4.metric(
    "Invalid / Excluded Records",
    f"{len(df) - len(analysis_df):,}"
)

st.info(
    f"Calculation rule: Dilution Base = Order Paint Weight + "
    f"{MIN_OPERATING_PAINT_KG:.0f} kg. "
    f"Outlier filtering uses P1–P99 only within Resin + Vendor + Solvent groups "
    f"with at least {OUTLIER_FILTER_MIN_RECORDS} records."
)

st.divider()


# =========================================================
# FILTERS
# =========================================================
filter_1, filter_2, filter_3 = st.columns(3)

with filter_1:
    selected_resin = st.selectbox(
        "Select Resin",
        sorted(analysis_df["Resin"].dropna().unique().tolist())
    )

vendor_options = sorted(
    analysis_df.loc[
        analysis_df["Resin"] == selected_resin,
        "Vendor"
    ].dropna().unique().tolist()
)

with filter_2:
    selected_vendor = st.selectbox(
        "Select Vendor",
        vendor_options
    )

solvent_options = sorted(
    analysis_df.loc[
        (analysis_df["Resin"] == selected_resin)
        & (analysis_df["Vendor"] == selected_vendor),
        "Solvent_Type"
    ].dropna().unique().tolist()
)

with filter_3:
    selected_solvent = st.selectbox(
        "Select Solvent Type",
        solvent_options
    )

filtered_data = analysis_df[
    (analysis_df["Resin"] == selected_resin)
    & (analysis_df["Vendor"] == selected_vendor)
    & (analysis_df["Solvent_Type"] == selected_solvent)
].copy()

if filtered_data.empty:
    st.warning("⚠️ No valid historical data exists for this selection.")
    st.stop()


# =========================================================
# RESET SESSION STATE WHEN FILTER CHANGES
# =========================================================
current_filter_key = (
    f"{selected_resin}|{selected_vendor}|{selected_solvent}"
)

default_lsl = float(
    filtered_data["黏度(秒)_1"].quantile(0.25)
)

default_usl = float(
    filtered_data["黏度(秒)_1"].quantile(0.75)
)

if pd.isna(default_lsl):
    default_lsl = 0.0

if pd.isna(default_usl):
    default_usl = default_lsl + 1.0

if default_lsl >= default_usl:
    default_usl = default_lsl + 1.0

if st.session_state.get("last_filter_key") != current_filter_key:
    st.session_state.current_viscosity = float(
        max(filtered_data["黏度(秒)"].median(), default_usl + 1)
    )

    st.session_state.approved_lsl = default_lsl
    st.session_state.approved_usl = default_usl
    st.session_state.order_paint_kg = 80.0
    st.session_state.last_filter_key = current_filter_key


# =========================================================
# TABS
# =========================================================
tab_analysis, tab_recommendation, tab_matrix, tab_worker = st.tabs([
    "📊 Historical Analysis",
    "🧠 SOP Recommendation",
    "📚 Engineering Matrix",
    "📄 塗料稀釋作業指導書"
])


# =========================================================
# TAB 1 — HISTORICAL ANALYSIS
# =========================================================
with tab_analysis:
    st.subheader("📊 Historical Before → After Dilution Analysis")

    record_count = len(filtered_data)

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)

    metric_1.metric(
        "Selected Historical Records",
        f"{record_count:,}"
    )

    metric_2.metric(
        "Median Before Viscosity",
        f"{filtered_data['黏度(秒)'].median():.2f} s"
    )

    metric_3.metric(
        "Median After Viscosity",
        f"{filtered_data['黏度(秒)_1'].median():.2f} s"
    )

    metric_4.metric(
        "Median Viscosity Drop",
        f"{filtered_data['Delta_V'].median():.2f} s"
    )

    st.markdown("### 1. Individual Batch Transition: Before → After")

    max_display_records = min(len(filtered_data), 200)

    display_records = st.slider(
        "Number of records displayed",
        min_value=10 if max_display_records >= 10 else 1,
        max_value=max_display_records,
        value=min(80, max_display_records),
        step=10 if max_display_records >= 10 else 1
    )

    transition_data = create_transition_data(
        filtered_data,
        display_records
    )

    fig_transition = px.line(
        transition_data,
        x="Stage",
        y="Viscosity",
        line_group="Record_ID",
        color="Viscosity_Zone",
        markers=True,
        category_orders={
            "Stage": [
                "Before Solvent",
                "After Solvent"
            ],
            "Viscosity_Zone": ZONE_ORDER
        },
        hover_data={
            "Record_ID": True,
            "黏度(秒)": ":.2f",
            "黏度(秒)_1": ":.2f",
            "Delta_V": ":.2f",
            "Solvent_Ratio_Percent": ":.2f",
            "添加重量": ":.2f",
            "塗料重量": ":.2f"
        },
        labels={
            "Stage": "Mixing Stage",
            "Viscosity": "Viscosity (s)",
            "Viscosity_Zone": "Initial Viscosity Zone"
        }
    )

    fig_transition.update_layout(
        height=560,
        legend_title_text="Initial Viscosity Zone"
    )

    st.plotly_chart(
        fig_transition,
        use_container_width=True
    )

    st.caption(
        "Each line represents one historical mixing record. "
        "The left point is viscosity before solvent addition; "
        "the right point is viscosity after solvent addition."
    )

    st.markdown("### 2. Initial Viscosity vs. After-Dilution Viscosity")

    fig_scatter = px.scatter(
        filtered_data,
        x="黏度(秒)",
        y="黏度(秒)_1",
        color="Viscosity_Zone",
        size="添加重量",
        hover_data=[
            "Record_ID",
            "Delta_V",
            "Solvent_Ratio_Percent",
            "Sensitivity",
            "添加重量",
            "塗料重量",
            "溫度",
            "濕度"
        ],
        category_orders={
            "Viscosity_Zone": ZONE_ORDER
        },
        labels={
            "黏度(秒)": "Initial Viscosity (s)",
            "黏度(秒)_1": "After-Dilution Viscosity (s)",
            "Viscosity_Zone": "Initial Viscosity Zone",
            "添加重量": "Added Solvent (kg)"
        }
    )

    max_axis = max(
        filtered_data["黏度(秒)"].max(),
        filtered_data["黏度(秒)_1"].max()
    ) * 1.05

    fig_scatter.add_trace(
        go.Scatter(
            x=[0, max_axis],
            y=[0, max_axis],
            mode="lines",
            name="No Change Line",
            line=dict(dash="dash")
        )
    )

    fig_scatter.update_layout(
        height=560,
        xaxis=dict(range=[0, max_axis]),
        yaxis=dict(range=[0, max_axis])
    )

    st.plotly_chart(
        fig_scatter,
        use_container_width=True
    )

    st.caption(
        "Points below the diagonal line indicate viscosity reduction after solvent addition. "
        "The farther below the line, the larger the viscosity reduction."
    )

    chart_left, chart_right = st.columns(2)

    with chart_left:
        st.markdown("### 3. Median Viscosity Drop by Initial Zone")

        drop_summary = make_zone_summary(
            filtered_data,
            "Delta_V"
        )

        fig_drop = px.bar(
            drop_summary,
            x="Viscosity_Zone",
            y="Median",
            error_y="Err_Plus",
            error_y_minus="Err_Minus",
            text="Median",
            category_orders={
                "Viscosity_Zone": ZONE_ORDER
            },
            hover_data={
                "P10": ":.2f",
                "P90": ":.2f",
                "Records": True
            },
            labels={
                "Viscosity_Zone": "Initial Viscosity Zone",
                "Median": "Median Viscosity Drop (s)"
            }
        )

        fig_drop.update_traces(
            texttemplate="%{text:.2f}",
            textposition="outside"
        )

        fig_drop.update_layout(height=450)

        st.plotly_chart(
            fig_drop,
            use_container_width=True
        )

    with chart_right:
        st.markdown("### 4. Median After-Dilution Viscosity by Zone")

        after_summary = make_zone_summary(
            filtered_data,
            "黏度(秒)_1"
        )

        fig_after = px.bar(
            after_summary,
            x="Viscosity_Zone",
            y="Median",
            error_y="Err_Plus",
            error_y_minus="Err_Minus",
            text="Median",
            category_orders={
                "Viscosity_Zone": ZONE_ORDER
            },
            hover_data={
                "P10": ":.2f",
                "P90": ":.2f",
                "Records": True
            },
            labels={
                "Viscosity_Zone": "Initial Viscosity Zone",
                "Median": "Median After-Dilution Viscosity (s)"
            }
        )

        fig_after.update_traces(
            texttemplate="%{text:.2f}",
            textposition="outside"
        )

        fig_after.update_layout(height=450)

        st.plotly_chart(
            fig_after,
            use_container_width=True
        )

    st.markdown("### 5. Solvent Ratio vs. Actual Viscosity Drop")

    fig_ratio_drop = px.scatter(
        filtered_data,
        x="Solvent_Ratio_Percent",
        y="Delta_V",
        color="Viscosity_Zone",
        size="添加重量",
        hover_data=[
            "Record_ID",
            "黏度(秒)",
            "黏度(秒)_1",
            "Sensitivity",
            "添加重量",
            "塗料重量"
        ],
        category_orders={
            "Viscosity_Zone": ZONE_ORDER
        },
        labels={
            "Solvent_Ratio_Percent": "Solvent Ratio (%)",
            "Delta_V": "Actual Viscosity Drop (s)",
            "Viscosity_Zone": "Initial Viscosity Zone",
            "添加重量": "Added Solvent (kg)"
        }
    )

    fig_ratio_drop.update_layout(height=520)

    st.plotly_chart(
        fig_ratio_drop,
        use_container_width=True
    )


# =========================================================
# TAB 2 — SOP RECOMMENDATION
# =========================================================
with tab_recommendation:
    st.subheader("🧠 Solvent Dosing Recommendation")

    st.caption(
        "Approved viscosity range should come from approved SOP, Lab standard, "
        "or Engineering control limit. Historical values are reference only."
    )

    input_1, input_2, input_3, input_4 = st.columns(4)

    with input_1:
        current_viscosity = st.number_input(
            "Current Viscosity (s)",
            min_value=0.0,
            step=1.0,
            key="current_viscosity"
        )

    with input_2:
        approved_lsl = st.number_input(
            "Approved Lower Limit (s)",
            min_value=0.0,
            step=1.0,
            key="approved_lsl"
        )

    with input_3:
        approved_usl = st.number_input(
            "Approved Upper Limit (s)",
            min_value=0.0,
            step=1.0,
            key="approved_usl"
        )

    with input_4:
        order_paint_kg = st.number_input(
            "Order Paint Weight (kg)",
            min_value=0.0,
            step=1.0,
            key="order_paint_kg"
        )

    recommendation, error_message = build_recommendation(
        historical_data=filtered_data,
        current_viscosity=current_viscosity,
        approved_lsl=approved_lsl,
        approved_usl=approved_usl,
        order_paint_kg=order_paint_kg
    )

    if error_message:
        st.warning(f"⚠️ {error_message}")

    elif recommendation["already_in_target"]:
        st.success(
            "✅ Current viscosity is already within or below the approved target range. "
            "No solvent addition is required."
        )

        st.metric(
            "Dilution Calculation Base",
            f"{recommendation['dilution_base']:.2f} kg"
        )

    else:
        result_1, result_2, result_3, result_4 = st.columns(4)

        result_1.metric(
            "Recommended Total Solvent",
            f"{recommendation['recommended_solvent']:.2f} kg"
        )

        result_2.metric(
            "Required Viscosity Drop",
            f"{recommendation['required_drop']:.2f} s"
        )

        result_3.metric(
            "Calculated Solvent Ratio",
            f"{recommendation['required_ratio']:.2f}%"
        )

        result_4.metric(
            "Historical Sensitivity",
            f"{recommendation['historical_sensitivity']:.2f} s / %"
        )

        st.info(
            f"Reference: {recommendation['match_type']} | "
            f"Records: {recommendation['reference_records']} | "
            f"Confidence: {recommendation['confidence']}"
        )

        st.markdown("### Recommended Staged Addition")

        stage_1, stage_2, stage_3, stage_4 = st.columns(4)

        stage_1.metric(
            "Stage 1: Initial Addition",
            f"{recommendation['stage_1_kg']:.2f} kg"
        )

        stage_2.metric(
            "Stage 2: Re-check Addition",
            f"{recommendation['stage_2_kg']:.2f} kg"
        )

        stage_3.metric(
            "Fine Adjustment",
            f"{recommendation['fine_adjust_kg']:.2f} kg"
        )

        stage_4.metric(
            "Maximum Total Solvent",
            f"{recommendation['max_total_solvent']:.2f} kg"
        )

        st.markdown("### Historical Risk Boundaries")

        risk_1, risk_2, risk_3, risk_4 = st.columns(4)

        risk_1.metric(
            "Historical Ratio P90",
            f"{recommendation['ratio_p90']:.2f}%"
        )

        risk_2.metric(
            "Historical Ratio P95",
            f"{recommendation['ratio_p95']:.2f}%"
        )

        risk_3.metric(
            "Historical Drop P90",
            f"{recommendation['drop_p90']:.2f} s"
        )

        risk_4.metric(
            "Historical Maximum Drop",
            f"{recommendation['max_drop']:.2f} s"
        )

        if recommendation["risk_status"] == "Blocked":
            st.error(f"🚨 {recommendation['risk_message']}")

        elif recommendation["risk_status"] == "Warning":
            st.warning(f"⚠️ {recommendation['risk_message']}")

        else:
            st.success(f"✅ {recommendation['risk_message']}")


# =========================================================
# TAB 3 — ENGINEERING MATRIX
# =========================================================
with tab_matrix:
    st.subheader("📚 Engineering SOP Coefficient Matrix")

    matrix_display = sop_matrix.copy()

    matrix_display = matrix_display.rename(columns={
        "Solvent_Type": "Solvent Type",
        "Viscosity_Zone": "Initial Viscosity Range",
        "Typical_Target_V": "Typical After Viscosity (s)",
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

    matrix_display = matrix_display.sort_values(
        [
            "Resin",
            "Vendor",
            "Solvent Type",
            "Zone_Sort"
        ]
    ).drop(columns=["Zone_Sort"])

    numeric_matrix_cols = matrix_display.select_dtypes(
        include=np.number
    ).columns.tolist()

    matrix_display[numeric_matrix_cols] = (
        matrix_display[numeric_matrix_cols]
        .round(2)
    )

    st.dataframe(
        matrix_display,
        use_container_width=True,
        hide_index=True
    )

    st.download_button(
        label="📥 Download Engineering Matrix",
        data=matrix_display.to_csv(
            index=False
        ).encode("utf-8-sig"),
        file_name="Solvent_Engineering_Matrix.csv",
        mime="text/csv"
    )


# =========================================================
# TAB 4 — WORKER INSTRUCTION
# =========================================================
with tab_worker:
    st.subheader("📄 塗料稀釋作業指導書")

    recommendation, error_message = build_recommendation(
        historical_data=filtered_data,
        current_viscosity=st.session_state.current_viscosity,
        approved_lsl=st.session_state.approved_lsl,
        approved_usl=st.session_state.approved_usl,
        order_paint_kg=st.session_state.order_paint_kg
    )

    if error_message:
        st.warning(f"⚠️ {error_message}")

    elif recommendation["already_in_target"]:
        st.success(
            "✅ 目前黏度已在核准範圍內，不需添加稀釋劑。"
        )

    else:
        worker_instruction = pd.DataFrame({
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
                "最大允許添加量",
                "歷史資料可信度"
            ],
            "作業標準": [
                selected_resin,
                selected_vendor,
                selected_solvent,
                f"{st.session_state.current_viscosity:.2f} 秒",
                (
                    f"{st.session_state.approved_lsl:.2f} "
                    f"– {st.session_state.approved_usl:.2f} 秒"
                ),
                f"{st.session_state.order_paint_kg:.2f} kg",
                f"{MIN_OPERATING_PAINT_KG:.2f} kg",
                f"{recommendation['dilution_base']:.2f} kg",
                f"{recommendation['recommended_solvent']:.2f} kg",
                f"{recommendation['stage_1_kg']:.2f} kg",
                f"{recommendation['stage_2_kg']:.2f} kg",
                f"{recommendation['fine_adjust_kg']:.2f} kg",
                f"{recommendation['max_total_solvent']:.2f} kg",
                recommendation["confidence"]
            ]
        })

        st.dataframe(
            worker_instruction,
            use_container_width=True,
            hide_index=True
        )

        st.markdown("### 作業步驟")

        st.info(
            f"""
1. 先加入第一次添加量：**{recommendation['stage_1_kg']:.2f} kg**。  
2. 依標準攪拌條件完成混合後，重新量測黏度。  
3. 若黏度仍高於核准上限，再加入第二次添加量：**{recommendation['stage_2_kg']:.2f} kg**。  
4. 若仍需調整，只可依每次微調量：**{recommendation['fine_adjust_kg']:.2f} kg** 逐次添加。  
5. 每次微調後都必須重新攪拌及量測黏度。  
6. 總添加量不得超過：**{recommendation['max_total_solvent']:.2f} kg**。  
7. 若仍無法進入核准範圍，請通知 QE / 製程工程師確認。  
            """
        )

        if recommendation["risk_status"] == "Blocked":
            st.error(
                "🚨 此批次需求已超出歷史安全範圍，"
                "不可依本作業指導書直接執行，需 QE / 製程工程師確認。"
            )

        elif recommendation["risk_status"] == "Warning":
            st.warning(
                "⚠️ 此批次接近或超過歷史 P90 操作範圍，"
                "必須嚴格依分段添加方式操作。"
            )

        st.download_button(
            label="📥 Download Worker Work Instruction",
            data=worker_instruction.to_csv(
                index=False
            ).encode("utf-8-sig"),
            file_name="Paint_Dilution_Work_Instruction.csv",
            mime="text/csv"
        )
