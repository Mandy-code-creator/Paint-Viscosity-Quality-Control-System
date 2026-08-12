import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="Order Thickness vs Viscosity",
    page_icon="📏",
    layout="wide",
)

st.title("📏 Order Film Thickness vs. Viscosity Analysis")
st.markdown(
    "Evaluate whether different order film thickness requirements are associated "
    "with different final viscosity targets under the same Resin × Position × "
    "Vendor × Solvent × Paint Code condition."
)


# =========================================================
# 2. ENGINEERING SETTINGS
# =========================================================
# These thresholds DO NOT hide data from the filters.
# They are only used to grade the confidence of the automatic SOP decision.
MIN_TOTAL_RECORDS = 10
MIN_UNIQUE_THICKNESS = 3
MIN_GROUP_RECORDS = 3

PRACTICAL_FINAL_VISC_GAP = 5.0      # seconds
STRONG_CORRELATION = 0.50
MODERATE_CORRELATION = 0.30
PRACTICAL_SLOPE = 0.50              # seconds per µm
MODERATE_SLOPE = 0.30               # seconds per µm


# =========================================================
# 3. LOAD DATA
# =========================================================
if (
    not st.session_state.get("raw_data_loaded", False)
    or st.session_state.get("group_a_data") is None
):
    st.warning(
        "⚠️ No data loaded. Please return to the Main App and upload the "
        "Paint Viscosity Analytics file first."
    )
    st.stop()

df = st.session_state["group_a_data"].copy()

if df.empty:
    st.warning("⚠️ Group A data is empty.")
    st.stop()


# =========================================================
# 4. HELPER FUNCTIONS
# =========================================================
def normalize_text(series):
    return (
        series
        .astype("string")
        .str.strip()
    )


def clean_numeric(series):
    return pd.to_numeric(
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace(" ", "", regex=False)
        .replace(
            {
                "": np.nan,
                "nan": np.nan,
                "NaN": np.nan,
                "None": np.nan,
                "NONE": np.nan,
                "NULL": np.nan,
                "-": np.nan,
                "--": np.nan,
            }
        ),
        errors="coerce",
    )


def safe_sorted_unique(series):
    return sorted(
        series.dropna()
        .astype(str)
        .str.strip()
        .loc[lambda x: x.ne("")]
        .unique()
        .tolist()
    )


def build_position_detail(data):
    """
    Keep the existing broad Position_UI logic for compatibility,
    but create Position_Detail specifically for thickness analysis.

    TF -> Top Finish  -> TOPFILM_THICK
    TP -> Top Primer  -> TTMFILM_THICK
    BF -> Back Finish -> BACKFILM_THICK
    BP -> Back Primer -> BTMFILM_THICK
    """
    work = data.copy()

    if "塗裝位置" not in work.columns:
        work["塗裝位置"] = pd.NA

    raw_pos = (
        work["塗裝位置"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    invalid_positions = {
        "",
        "0",
        "0.0",
        "NAN",
        "NONE",
        "NULL",
        "N/A",
        "NA",
        "-",
        "--",
        "<NA>",
        "UNKNOWN",
    }

    raw_pos = raw_pos.mask(raw_pos.isin(invalid_positions), pd.NA)
    work["_Position_Raw"] = raw_pos

    detail_map = {
        "TF": "Top Finish",
        "正面漆": "Top Finish",
        "TP": "Top Primer",
        "正底漆": "Top Primer",
        "BF": "Back Finish",
        "背面漆": "Back Finish",
        "BP": "Back Primer",
        "背底漆": "Back Primer",
    }

    broad_map = {
        "TF": "Top Finish",
        "正面漆": "Top Finish",
        "TP": "Primer",
        "正底漆": "Primer",
        "BF": "Back Finish",
        "背面漆": "Back Finish",
        "BP": "Primer",
        "背底漆": "Primer",
    }

    work["Position_Detail"] = raw_pos.map(detail_map)
    work["Position_UI_Thickness"] = raw_pos.map(broad_map)

    return work


def assign_order_thickness(data):
    """
    Select the correct active-layer thickness according to Position_Detail,
    and also build the full coating structure:

    Top side:
        TTMFILM_THICK + TOPFILM_THICK
        Primer + Top Finish

    Back side:
        BTMFILM_THICK + BACKFILM_THICK
        Primer + Back Finish
    """
    work = data.copy()

    thickness_columns = [
        "TOPFILM_THICK",
        "TTMFILM_THICK",
        "BACKFILM_THICK",
        "BTMFILM_THICK",
    ]

    for col in thickness_columns:
        if col not in work.columns:
            work[col] = np.nan
        work[col] = clean_numeric(work[col])

    # Thickness of the specific coating layer currently being analyzed.
    work["Order_Film_Thickness"] = np.select(
        [
            work["Position_Detail"] == "Top Finish",
            work["Position_Detail"] == "Top Primer",
            work["Position_Detail"] == "Back Finish",
            work["Position_Detail"] == "Back Primer",
        ],
        [
            work["TOPFILM_THICK"],
            work["TTMFILM_THICK"],
            work["BACKFILM_THICK"],
            work["BTMFILM_THICK"],
        ],
        default=np.nan,
    )

    work["Thickness_Source_Column"] = np.select(
        [
            work["Position_Detail"] == "Top Finish",
            work["Position_Detail"] == "Top Primer",
            work["Position_Detail"] == "Back Finish",
            work["Position_Detail"] == "Back Primer",
        ],
        [
            "TOPFILM_THICK",
            "TTMFILM_THICK",
            "BACKFILM_THICK",
            "BTMFILM_THICK",
        ],
        default="Unknown",
    )

    # Full side structure: primer + main coating.
    is_top_side = work["Position_Detail"].isin(
        ["Top Finish", "Top Primer"]
    )
    is_back_side = work["Position_Detail"].isin(
        ["Back Finish", "Back Primer"]
    )

    work["Primer_Thickness"] = np.select(
        [is_top_side, is_back_side],
        [work["TTMFILM_THICK"], work["BTMFILM_THICK"]],
        default=np.nan,
    )

    work["Main_Coat_Thickness"] = np.select(
        [is_top_side, is_back_side],
        [work["TOPFILM_THICK"], work["BACKFILM_THICK"]],
        default=np.nan,
    )

    work["Total_Coating_Thickness"] = (
        pd.to_numeric(work["Primer_Thickness"], errors="coerce")
        + pd.to_numeric(work["Main_Coat_Thickness"], errors="coerce")
    )

    def format_um(value):
        if pd.isna(value):
            return "—"
        value = float(value)
        if value.is_integer():
            return f"{int(value)}"
        return f"{value:.1f}".rstrip("0").rstrip(".")

    def build_structure_label(row):
        primer = row["Primer_Thickness"]
        main = row["Main_Coat_Thickness"]

        if pd.isna(primer) and pd.isna(main):
            return "Unknown"

        return (
            f"{format_um(primer)} µm + "
            f"{format_um(main)} µm"
        )

    work["Coating_Structure"] = work.apply(
        build_structure_label,
        axis=1,
    )

    work["Coating_Structure_Detail"] = np.select(
        [is_top_side, is_back_side],
        [
            work["Coating_Structure"]
            + " (Primer + Top Finish)",
            work["Coating_Structure"]
            + " (Primer + Back Finish)",
        ],
        default=work["Coating_Structure"],
    )

    return work


def adaptive_thickness_group(series):
    """
    Use actual thickness values when the number of distinct values is small.
    If there are many values, split by data distribution (terciles) instead
    of using arbitrary fixed ranges.
    """
    s = pd.to_numeric(series, errors="coerce")
    valid = s.dropna()

    if valid.empty:
        return pd.Series(pd.NA, index=series.index, dtype="string")

    unique_values = np.sort(valid.unique())

    if len(unique_values) <= 6:
        result = s.map(
            lambda x: f"{x:g} µm" if pd.notna(x) else pd.NA
        )
        return result.astype("string")

    try:
        grouped = pd.qcut(
            s,
            q=[0.0, 1/3, 2/3, 1.0],
            duplicates="drop",
        )

        def format_interval(interval):
            if pd.isna(interval):
                return pd.NA
            left = float(interval.left)
            right = float(interval.right)
            return f"{left:g}–{right:g} µm"

        return grouped.map(format_interval).astype("string")

    except Exception:
        rounded = s.round(0)
        return rounded.map(
            lambda x: f"{x:g} µm" if pd.notna(x) else pd.NA
        ).astype("string")


def calculate_relationship_metrics(source_df):
    result = {
        "records": 0,
        "unique_thickness": 0,
        "pearson_r": np.nan,
        "spearman_r": np.nan,
        "slope": np.nan,
        "intercept": np.nan,
        "final_visc_gap": np.nan,
        "min_group_records": 0,
        "usable_groups": 0,
    }

    work = source_df[
        ["Order_Film_Thickness", "黏度(秒)_1"]
    ].dropna().copy()

    result["records"] = len(work)
    result["unique_thickness"] = work["Order_Film_Thickness"].nunique()

    if len(work) < 2 or result["unique_thickness"] < 2:
        return result

    x = pd.to_numeric(work["Order_Film_Thickness"], errors="coerce")
    y = pd.to_numeric(work["黏度(秒)_1"], errors="coerce")

    valid = x.notna() & y.notna() & np.isfinite(x) & np.isfinite(y)
    x = x[valid]
    y = y[valid]

    if len(x) < 2 or x.nunique() < 2:
        return result

    result["pearson_r"] = x.corr(y, method="pearson")
    result["spearman_r"] = x.rank().corr(y.rank(), method="pearson")

    try:
        slope, intercept = np.polyfit(x.to_numpy(), y.to_numpy(), 1)
        result["slope"] = float(slope)
        result["intercept"] = float(intercept)
    except Exception:
        pass

    grouped = (
        source_df.dropna(subset=["Thickness_Group", "黏度(秒)_1"])
        .groupby("Thickness_Group", dropna=False)
        .agg(
            Records=("黏度(秒)_1", "size"),
            Median_Final=("黏度(秒)_1", "median"),
        )
        .reset_index()
    )

    usable = grouped[grouped["Records"] >= MIN_GROUP_RECORDS].copy()
    result["usable_groups"] = len(usable)

    if not usable.empty:
        result["min_group_records"] = int(usable["Records"].min())

    if len(usable) >= 2:
        result["final_visc_gap"] = (
            usable["Median_Final"].max()
            - usable["Median_Final"].min()
        )

    return result


def classify_sop_decision(metrics):
    """
    Conservative engineering classification.
    This is an association screen, not proof of causality.
    """
    n = metrics["records"]
    unique_t = metrics["unique_thickness"]
    usable_groups = metrics["usable_groups"]

    if (
        n < MIN_TOTAL_RECORDS
        or unique_t < MIN_UNIQUE_THICKNESS
        or usable_groups < 2
    ):
        return {
            "level": "Insufficient Evidence",
            "icon": "⚪",
            "message": (
                "Thickness data are not sufficient to decide whether the SOP "
                "should be segmented by thickness."
            ),
            "recommendation": (
                "Keep the current SOP for now and continue collecting matched "
                "order-thickness records."
            ),
        }

    r = metrics["spearman_r"]
    slope = metrics["slope"]
    gap = metrics["final_visc_gap"]

    abs_r = abs(r) if pd.notna(r) else 0.0
    abs_slope = abs(slope) if pd.notna(slope) else 0.0
    gap_value = abs(gap) if pd.notna(gap) else 0.0

    strong = (
        abs_r >= STRONG_CORRELATION
        and abs_slope >= PRACTICAL_SLOPE
        and gap_value >= PRACTICAL_FINAL_VISC_GAP
    )

    moderate = (
        (
            abs_r >= MODERATE_CORRELATION
            and gap_value >= 4.0
        )
        or (
            abs_slope >= MODERATE_SLOPE
            and gap_value >= 4.0
        )
    )

    if strong:
        direction = (
            "higher thickness tends to require higher final viscosity"
            if slope > 0
            else "higher thickness tends to be associated with lower final viscosity"
        )
        return {
            "level": "Thickness Effect Detected",
            "icon": "🟠",
            "message": (
                f"A clear thickness–final-viscosity association is visible; "
                f"{direction}."
            ),
            "recommendation": (
                "Consider a thickness-based SOP pilot for this exact paint system. "
                "Validate the proposed ranges on line before changing the official SOP."
            ),
        }

    if moderate:
        return {
            "level": "Possible Thickness Effect",
            "icon": "🟡",
            "message": (
                "Some thickness-related shift is visible, but the evidence is "
                "not yet strong enough for automatic SOP segmentation."
            ),
            "recommendation": (
                "Keep the current SOP and run a focused pilot by thickness group "
                "before creating separate shop-floor limits."
            ),
        }

    return {
        "level": "No Meaningful Thickness Segmentation Needed",
        "icon": "🟢",
        "message": (
            "Final viscosity does not show a sufficiently large and consistent "
            "difference across thickness levels in the current historical data."
        ),
        "recommendation": (
            "Keep one SOP for this system. Thickness can remain a monitoring "
            "variable instead of a segmentation variable."
        ),
    }


def safe_metric(value, fmt, fallback="N/A"):
    if pd.isna(value):
        return fallback
    return fmt.format(value)


# =========================================================
# 5. DATA PREPARATION
# =========================================================
required_core = [
    "Resin",
    "Vendor",
    "Solvent_Type",
    "塗料編號",
    "黏度(秒)",
    "黏度(秒)_1",
    "塗裝位置",
]

missing_core = [c for c in required_core if c not in df.columns]

if missing_core:
    st.error(
        "❌ Missing required columns: "
        + ", ".join(missing_core)
    )
    st.stop()

for col in ["Resin", "Vendor", "Solvent_Type", "塗料編號"]:
    df[col] = normalize_text(df[col])

df["Paint_Code"] = (
    df["塗料編號"]
    .fillna("")
    .astype(str)
    .str.strip()
    .str.upper()
)

df["黏度(秒)"] = clean_numeric(df["黏度(秒)"])
df["黏度(秒)_1"] = clean_numeric(df["黏度(秒)_1"])

df = build_position_detail(df)
df = assign_order_thickness(df)

# Keep all valid viscosity records. Thickness availability is evaluated separately.
df = df[
    df["Position_Detail"].notna()
    & df["Paint_Code"].ne("")
    & df["黏度(秒)"].notna()
    & df["黏度(秒)_1"].notna()
    & (df["黏度(秒)"] > 0)
    & (df["黏度(秒)_1"] > 0)
].copy()

if df.empty:
    st.warning("⚠️ No valid records are available after data preparation.")
    st.stop()

df["Delta_V"] = df["黏度(秒)"] - df["黏度(秒)_1"]

if "添加重量" in df.columns:
    df["添加重量"] = clean_numeric(df["添加重量"])

if "塗料重量" in df.columns:
    df["塗料重量"] = clean_numeric(df["塗料重量"])

if "Solvent_Ratio_Percent" not in df.columns:
    if "添加重量" in df.columns and "塗料重量" in df.columns:
        base_paint = df["塗料重量"] - df["添加重量"]
        df["Solvent_Ratio_Percent"] = np.where(
            base_paint > 0,
            df["添加重量"] / base_paint * 100,
            np.nan,
        )
    else:
        df["Solvent_Ratio_Percent"] = np.nan
else:
    df["Solvent_Ratio_Percent"] = clean_numeric(
        df["Solvent_Ratio_Percent"]
    )

# Thickness Match Coverage
if "Thickness_Match_Status" in df.columns:
    df["Thickness_Match_Status"] = normalize_text(
        df["Thickness_Match_Status"]
    )
else:
    df["Thickness_Match_Status"] = pd.NA


# =========================================================
# 6. DATA COVERAGE
# =========================================================
st.markdown("---")
st.subheader("1. Order Thickness Data Coverage")

total_records = len(df)
matched_thickness_records = int(df["Order_Film_Thickness"].notna().sum())
coverage_pct = (
    matched_thickness_records / total_records * 100
    if total_records > 0
    else 0.0
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Valid Viscosity Records", f"{total_records:,}")
c2.metric("Records with Order Thickness", f"{matched_thickness_records:,}")
c3.metric("Thickness Coverage", f"{coverage_pct:.1f}%")
c4.metric(
    "Paint Codes with Thickness",
    f"{df.loc[df['Order_Film_Thickness'].notna(), 'Paint_Code'].nunique():,}",
)

coverage_by_position = (
    df.groupby("Position_Detail", dropna=False)
    .agg(
        Total_Records=("Paint_Code", "size"),
        Thickness_Records=(
            "Order_Film_Thickness",
            lambda x: x.notna().sum(),
        ),
    )
    .reset_index()
)

coverage_by_position["Coverage_%"] = np.where(
    coverage_by_position["Total_Records"] > 0,
    coverage_by_position["Thickness_Records"]
    / coverage_by_position["Total_Records"]
    * 100,
    np.nan,
)

with st.expander("View thickness coverage by coating position"):
    st.dataframe(
        coverage_by_position,
        column_config={
            "Position_Detail": "Position",
            "Total_Records": st.column_config.NumberColumn(
                "Viscosity Records", format="%d"
            ),
            "Thickness_Records": st.column_config.NumberColumn(
                "Records with Thickness", format="%d"
            ),
            "Coverage_%": st.column_config.NumberColumn(
                "Coverage (%)", format="%.1f"
            ),
        },
        hide_index=True,
        use_container_width=True,
    )


# =========================================================
# 7. LINKED FILTERS
#    Main analysis object = Paint Code
#    Filter order: Vendor → Paint Code → Position → Resin → Solvent
# =========================================================
st.markdown("---")
st.subheader("2. System Selection")

filter_source = df[df["Order_Film_Thickness"].notna()].copy()

if filter_source.empty:
    st.warning(
        "⚠️ No matched order-thickness data are available. "
        "Please check the four thickness columns in the new source file."
    )
    st.stop()

f1, f2, f3, f4, f5 = st.columns(5)

# ---------------------------------------------------------
# 1. Vendor
# ---------------------------------------------------------
with f1:
    vendor_options = safe_sorted_unique(
        filter_source["Vendor"]
    )

    selected_vendor = st.selectbox(
        "Select Vendor:",
        vendor_options,
    )

vendor_df = filter_source[
    filter_source["Vendor"] == selected_vendor
].copy()

# ---------------------------------------------------------
# 2. Paint Code — main analysis object
# ---------------------------------------------------------
with f2:
    paint_code_options = safe_sorted_unique(
        vendor_df["Paint_Code"]
    )

    selected_paint_code = st.selectbox(
        "Select Paint Code:",
        paint_code_options,
    )

paint_df = vendor_df[
    vendor_df["Paint_Code"] == selected_paint_code
].copy()

# ---------------------------------------------------------
# 3. Position
# ---------------------------------------------------------
with f3:
    position_options = safe_sorted_unique(
        paint_df["Position_Detail"]
    )

    selected_position = st.selectbox(
        "Select Position:",
        position_options,
    )

position_df = paint_df[
    paint_df["Position_Detail"] == selected_position
].copy()

# ---------------------------------------------------------
# 4. Resin
# ---------------------------------------------------------
with f4:
    resin_options = safe_sorted_unique(
        position_df["Resin"]
    )

    selected_resin = st.selectbox(
        "Select Resin:",
        resin_options,
    )

resin_df = position_df[
    position_df["Resin"] == selected_resin
].copy()

# ---------------------------------------------------------
# 5. Solvent
# ---------------------------------------------------------
with f5:
    solvent_options = safe_sorted_unique(
        resin_df["Solvent_Type"]
    )

    selected_solvent = st.selectbox(
        "Select Solvent:",
        solvent_options,
    )

# Final selected paint-code system
system_df = resin_df[
    resin_df["Solvent_Type"] == selected_solvent
].copy()

if system_df.empty:
    st.warning("No data available for the selected paint-code system.")
    st.stop()

system_df["Thickness_Group"] = adaptive_thickness_group(
    system_df["Order_Film_Thickness"]
)


# =========================================================
# 8. SYSTEM SUMMARY
# =========================================================
st.markdown("---")
st.subheader("3. Thickness Effect on Final Viscosity")

source_column = (
    system_df["Thickness_Source_Column"]
    .dropna()
    .astype(str)
    .mode()
)

source_column_text = (
    source_column.iloc[0]
    if not source_column.empty
    else "Unknown"
)

system_label = (
    f"{selected_resin} | {selected_position} | {selected_vendor} | "
    f"{selected_solvent} | {selected_paint_code}"
)

structure_values = (
    system_df["Coating_Structure_Detail"]
    .dropna()
    .astype(str)
    .loc[lambda s: ~s.isin(["Unknown", "—"])]
    .unique()
    .tolist()
)

if len(structure_values) == 1:
    structure_text = structure_values[0]
elif len(structure_values) <= 4:
    structure_text = " / ".join(structure_values)
else:
    structure_text = (
        "Multiple structures: "
        + " / ".join(structure_values[:4])
        + f" / ... ({len(structure_values)} total)"
    )

st.info(
    f"**Selected system:** {system_label}  \n"
    f"**Coating structure:** {structure_text}  \n"
    f"**Active thickness source:** `{source_column_text}`"
)

metrics = calculate_relationship_metrics(system_df)
decision = classify_sop_decision(metrics)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Records", f"{metrics['records']:,}")
m2.metric(
    "Unique Thickness Values",
    f"{metrics['unique_thickness']:,}",
)
m3.metric(
    "Spearman Correlation",
    safe_metric(metrics["spearman_r"], "{:.2f}"),
)
m4.metric(
    "Slope",
    safe_metric(metrics["slope"], "{:.2f} s/µm"),
)
m5.metric(
    "Median Final Viscosity Gap",
    safe_metric(metrics["final_visc_gap"], "{:.1f} s"),
)

# ---------------------------------------------------------
# Scatter + trend
# ---------------------------------------------------------
fig_scatter = px.scatter(
    system_df,
    x="Order_Film_Thickness",
    y="黏度(秒)_1",
    hover_data={
        "Paint_Code": True,
        "Coating_Structure_Detail": True,
        "Primer_Thickness": ":.1f",
        "Main_Coat_Thickness": ":.1f",
        "Total_Coating_Thickness": ":.1f",
        "黏度(秒)": ":.1f",
        "黏度(秒)_1": ":.1f",
        "Delta_V": ":.1f",
        "Solvent_Ratio_Percent": ":.2f",
        "Order_Film_Thickness": ":.2f",
    },
    labels={
        "Order_Film_Thickness": "Order Film Thickness (µm)",
        "黏度(秒)_1": "Final Viscosity (s)",
    },
)

fig_scatter.update_traces(
    marker=dict(
        size=9,
        opacity=0.75,
        line=dict(width=0.8, color="white"),
    )
)

# Linear trend line
trend_df = system_df[
    ["Order_Film_Thickness", "黏度(秒)_1"]
].dropna().copy()

if (
    len(trend_df) >= 2
    and trend_df["Order_Film_Thickness"].nunique() >= 2
):
    x = trend_df["Order_Film_Thickness"].astype(float)
    y = trend_df["黏度(秒)_1"].astype(float)

    slope, intercept = np.polyfit(x, y, 1)

    x_line = np.linspace(
        x.min(),
        x.max(),
        100,
    )
    y_line = slope * x_line + intercept

    fig_scatter.add_trace(
        go.Scatter(
            x=x_line,
            y=y_line,
            mode="lines",
            name="Linear Trend",
            line=dict(width=3),
            hovertemplate=(
                "Trend Final Viscosity: %{y:.1f} s"
                "<extra></extra>"
            ),
        )
    )

fig_scatter.update_layout(
    title=dict(
        text=(
            "<b>Order Film Thickness vs. Final Viscosity</b>"
            f"<br><sup>{system_label}</sup>"
            f"<br><sup>Coating Structure: {structure_text}</sup>"
        ),
        x=0.5,
        xanchor="center",
    ),
    height=560,
    margin=dict(l=70, r=50, t=145, b=70),
    template="plotly_white",
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.01,
        xanchor="center",
        x=0.5,
    ),
)

fig_scatter.update_xaxes(
    showgrid=True,
    gridcolor="#E5E7EB",
    showline=True,
    linecolor="#374151",
    mirror=True,
)

fig_scatter.update_yaxes(
    showgrid=True,
    gridcolor="#E5E7EB",
    showline=True,
    linecolor="#374151",
    mirror=True,
)

st.plotly_chart(
    fig_scatter,
    use_container_width=True,
)

st.caption(
    "The trend line is descriptive only. A relationship in historical data "
    "does not by itself prove that thickness causes the viscosity change."
)


# =========================================================
# 9. THICKNESS GROUP COMPARISON
# =========================================================
st.markdown("---")
st.subheader("4. Thickness Group Comparison")

summary_df = (
    system_df.dropna(
        subset=["Thickness_Group", "Order_Film_Thickness"]
    )
    .groupby(
        "Thickness_Group",
        dropna=False,
        observed=False,
    )
    .agg(
        Records=("Paint_Code", "size"),
        Coating_Structure=(
            "Coating_Structure_Detail",
            lambda x: " / ".join(
                pd.Series(x)
                .dropna()
                .astype(str)
                .drop_duplicates()
                .tolist()
            ),
        ),
        Primer_Thickness=("Primer_Thickness", "median"),
        Main_Coat_Thickness=("Main_Coat_Thickness", "median"),
        Total_Coating_Thickness=("Total_Coating_Thickness", "median"),
        Thickness_Min=("Order_Film_Thickness", "min"),
        Thickness_Median=("Order_Film_Thickness", "median"),
        Thickness_Max=("Order_Film_Thickness", "max"),
        Median_Before_Viscosity=("黏度(秒)", "median"),
        Median_Final_Viscosity=("黏度(秒)_1", "median"),
        Final_Viscosity_P25=("黏度(秒)_1", lambda x: x.quantile(0.25)),
        Final_Viscosity_P75=("黏度(秒)_1", lambda x: x.quantile(0.75)),
        Median_Viscosity_Drop=("Delta_V", "median"),
        Median_Solvent_Ratio=(
            "Solvent_Ratio_Percent",
            "median",
        ),
    )
    .reset_index()
)

summary_df = summary_df.sort_values(
    "Thickness_Median"
).reset_index(drop=True)

st.dataframe(
    summary_df,
    column_config={
        "Thickness_Group": "Thickness Group",
        "Coating_Structure": st.column_config.TextColumn(
            "Coating Structure",
            width="large",
        ),
        "Primer_Thickness": st.column_config.NumberColumn(
            "Primer (µm)", format="%.1f"
        ),
        "Main_Coat_Thickness": st.column_config.NumberColumn(
            "Main Coat (µm)", format="%.1f"
        ),
        "Total_Coating_Thickness": st.column_config.NumberColumn(
            "Total (µm)", format="%.1f"
        ),
        "Records": st.column_config.NumberColumn(
            "Records", format="%d"
        ),
        "Thickness_Min": st.column_config.NumberColumn(
            "Min Thickness (µm)", format="%.1f"
        ),
        "Thickness_Median": st.column_config.NumberColumn(
            "Median Thickness (µm)", format="%.1f"
        ),
        "Thickness_Max": st.column_config.NumberColumn(
            "Max Thickness (µm)", format="%.1f"
        ),
        "Median_Before_Viscosity": st.column_config.NumberColumn(
            "Median Before (s)", format="%.1f"
        ),
        "Median_Final_Viscosity": st.column_config.NumberColumn(
            "Median Final (s)", format="%.1f"
        ),
        "Final_Viscosity_P25": st.column_config.NumberColumn(
            "Final P25 (s)", format="%.1f"
        ),
        "Final_Viscosity_P75": st.column_config.NumberColumn(
            "Final P75 (s)", format="%.1f"
        ),
        "Median_Viscosity_Drop": st.column_config.NumberColumn(
            "Median ΔV (s)", format="%.1f"
        ),
        "Median_Solvent_Ratio": st.column_config.NumberColumn(
            "Median Solvent Ratio (%)", format="%.2f"
        ),
    },
    hide_index=True,
    use_container_width=True,
)

group_order = summary_df["Thickness_Group"].astype(str).tolist()

fig_box = px.box(
    system_df,
    x="Thickness_Group",
    y="黏度(秒)_1",
    points="all",
    category_orders={
        "Thickness_Group": group_order,
    },
    labels={
        "Thickness_Group": "Order Thickness Group",
        "黏度(秒)_1": "Final Viscosity (s)",
    },
)

fig_box.update_layout(
    title=dict(
        text=(
            "<b>Final Viscosity Distribution by Order Thickness</b>"
            f"<br><sup>{selected_paint_code} | Coating Structure: "
            f"{structure_text}</sup>"
        ),
        x=0.5,
        xanchor="center",
    ),
    height=520,
    margin=dict(l=70, r=50, t=105, b=90),
    template="plotly_white",
    showlegend=False,
)

fig_box.update_xaxes(
    showline=True,
    linecolor="#374151",
    mirror=True,
)

fig_box.update_yaxes(
    showgrid=True,
    gridcolor="#E5E7EB",
    showline=True,
    linecolor="#374151",
    mirror=True,
)

st.plotly_chart(
    fig_box,
    use_container_width=True,
)


# =========================================================
# 10. AUTOMATIC SOP SEGMENTATION DECISION
# =========================================================
st.markdown("---")
st.subheader("5. SOP Segmentation Decision")

if decision["level"] == "Thickness Effect Detected":
    st.warning(
        f"{decision['icon']} **{decision['level']}**  \n"
        f"{decision['message']}"
    )
elif decision["level"] == "Possible Thickness Effect":
    st.info(
        f"{decision['icon']} **{decision['level']}**  \n"
        f"{decision['message']}"
    )
elif decision["level"] == "No Meaningful Thickness Segmentation Needed":
    st.success(
        f"{decision['icon']} **{decision['level']}**  \n"
        f"{decision['message']}"
    )
else:
    st.info(
        f"{decision['icon']} **{decision['level']}**  \n"
        f"{decision['message']}"
    )

st.markdown(
    f"**Recommended action:** {decision['recommendation']}"
)

direction_text = "Not determined"

if pd.notna(metrics["slope"]):
    if metrics["slope"] > 0:
        direction_text = (
            "Thickness ↑ → Final viscosity tends to ↑"
        )
    elif metrics["slope"] < 0:
        direction_text = (
            "Thickness ↑ → Final viscosity tends to ↓"
        )
    else:
        direction_text = "No directional trend"

decision_table = pd.DataFrame(
    [
        {
            "System": system_label,
            "Coating Structure": structure_text,
            "Records": metrics["records"],
            "Unique Thickness": metrics["unique_thickness"],
            "Pearson r": metrics["pearson_r"],
            "Spearman r": metrics["spearman_r"],
            "Slope (s/µm)": metrics["slope"],
            "Median Final Viscosity Gap (s)": metrics["final_visc_gap"],
            "Direction": direction_text,
            "Decision": decision["level"],
        }
    ]
)

st.dataframe(
    decision_table,
    column_config={
        "Records": st.column_config.NumberColumn(
            "Records", format="%d"
        ),
        "Unique Thickness": st.column_config.NumberColumn(
            "Unique Thickness", format="%d"
        ),
        "Pearson r": st.column_config.NumberColumn(
            "Pearson r", format="%.2f"
        ),
        "Spearman r": st.column_config.NumberColumn(
            "Spearman r", format="%.2f"
        ),
        "Slope (s/µm)": st.column_config.NumberColumn(
            "Slope (s/µm)", format="%.2f"
        ),
        "Median Final Viscosity Gap (s)": st.column_config.NumberColumn(
            "Final Viscosity Gap (s)", format="%.1f"
        ),
    },
    hide_index=True,
    use_container_width=True,
)


# =========================================================
# 11. ALL PAINT CODES SCREENING
# =========================================================
st.markdown("---")
st.subheader("6. All Paint Codes — Thickness Effect Screening")

st.caption(
    "This table screens all paint codes under the selected "
    "Vendor × Position × Resin × Solvent condition. "
    "Paint Code remains the main analysis object, and this screening helps "
    "identify which codes deserve a thickness-based SOP pilot."
)

# Compare all paint codes under the same Vendor × Position × Resin × Solvent condition.
screen_source = filter_source[
    (filter_source["Vendor"] == selected_vendor)
    & (filter_source["Position_Detail"] == selected_position)
    & (filter_source["Resin"] == selected_resin)
    & (filter_source["Solvent_Type"] == selected_solvent)
].copy()

screen_rows = []

for paint_code, code_df in screen_source.groupby(
    "Paint_Code",
    dropna=False,
):
    code_df = code_df.copy()
    code_df["Thickness_Group"] = adaptive_thickness_group(
        code_df["Order_Film_Thickness"]
    )

    m = calculate_relationship_metrics(code_df)
    d = classify_sop_decision(m)

    screen_rows.append(
        {
            "Paint_Code": str(paint_code),
            "Records": m["records"],
            "Unique_Thickness": m["unique_thickness"],
            "Spearman_r": m["spearman_r"],
            "Slope_s_per_um": m["slope"],
            "Final_Viscosity_Gap_s": m["final_visc_gap"],
            "Decision": d["level"],
        }
    )

screen_df = pd.DataFrame(screen_rows)

if screen_df.empty:
    st.info("No paint-code screening results are available.")
else:
    priority_map = {
        "Thickness Effect Detected": 1,
        "Possible Thickness Effect": 2,
        "No Meaningful Thickness Segmentation Needed": 3,
        "Insufficient Evidence": 4,
    }

    screen_df["_Priority"] = (
        screen_df["Decision"]
        .map(priority_map)
        .fillna(99)
    )

    screen_df = (
        screen_df.sort_values(
            [
                "_Priority",
                "Final_Viscosity_Gap_s",
                "Records",
            ],
            ascending=[True, False, False],
            na_position="last",
        )
        .drop(columns="_Priority")
        .reset_index(drop=True)
    )

    st.dataframe(
        screen_df,
        column_config={
            "Paint_Code": "Paint Code",
            "Records": st.column_config.NumberColumn(
                "Records", format="%d"
            ),
            "Unique_Thickness": st.column_config.NumberColumn(
                "Unique Thickness", format="%d"
            ),
            "Spearman_r": st.column_config.NumberColumn(
                "Spearman r", format="%.2f"
            ),
            "Slope_s_per_um": st.column_config.NumberColumn(
                "Slope (s/µm)", format="%.2f"
            ),
            "Final_Viscosity_Gap_s": st.column_config.NumberColumn(
                "Final Viscosity Gap (s)", format="%.1f"
            ),
            "Decision": "SOP Decision",
        },
        hide_index=True,
        use_container_width=True,
    )



# =========================================================
# 12. READY-TO-LINE INCOMING VISCOSITY RECOMMENDATION
# =========================================================
st.markdown("---")
st.subheader("7. Ready-to-Line Incoming Viscosity Recommendation")

st.markdown(
    "Estimate an incoming viscosity range that may allow the selected paint "
    "to go directly to line without on-site solvent addition. "
    "The recommendation is based on the historical final-viscosity distribution "
    "for the same Paint Code and Coating Structure."
)

# ---------------------------------------------------------
# 12.1 Clean historical reference records
# ---------------------------------------------------------
ready_df = system_df.copy()

# Keep only positive and valid final viscosity values.
ready_df = ready_df[
    ready_df["黏度(秒)_1"].notna()
    & (ready_df["黏度(秒)_1"] > 0)
].copy()

# Exclude clearly abnormal solvent-ratio records from the recommendation reference.
# This does NOT remove them from the earlier analysis; it only protects the
# ready-to-line recommendation from extreme dilution events.
ratio_reference = pd.to_numeric(
    ready_df["Solvent_Ratio_Percent"],
    errors="coerce",
)

if ratio_reference.notna().sum() >= 5:
    ratio_p10 = float(ratio_reference.quantile(0.10))
    ratio_p90 = float(ratio_reference.quantile(0.90))

    ready_reference_df = ready_df[
        ready_df["Solvent_Ratio_Percent"].between(
            ratio_p10,
            ratio_p90,
            inclusive="both",
        )
    ].copy()
else:
    ratio_p10 = np.nan
    ratio_p90 = np.nan
    ready_reference_df = ready_df.copy()

# If trimming leaves too few records, fall back to all valid records.
if len(ready_reference_df) < 5:
    ready_reference_df = ready_df.copy()

# ---------------------------------------------------------
# 12.2 Recommendation statistics
# ---------------------------------------------------------
ready_records = len(ready_reference_df)

if ready_records == 0:
    st.info(
        "No valid historical final-viscosity records are available for "
        "a ready-to-line recommendation."
    )
else:
    current_incoming_p25 = float(
        ready_reference_df["黏度(秒)"].quantile(0.25)
    )
    current_incoming_median = float(
        ready_reference_df["黏度(秒)"].median()
    )
    current_incoming_p75 = float(
        ready_reference_df["黏度(秒)"].quantile(0.75)
    )

    recommended_lower = float(
        ready_reference_df["黏度(秒)_1"].quantile(0.25)
    )
    recommended_target = float(
        ready_reference_df["黏度(秒)_1"].median()
    )
    recommended_upper = float(
        ready_reference_df["黏度(秒)_1"].quantile(0.75)
    )

    final_iqr = recommended_upper - recommended_lower

    median_solvent_ratio = float(
        ready_reference_df["Solvent_Ratio_Percent"].median()
    ) if ready_reference_df["Solvent_Ratio_Percent"].notna().any() else np.nan

    median_solvent_kg = float(
        ready_reference_df["添加重量"].median()
    ) if "添加重量" in ready_reference_df.columns and ready_reference_df["添加重量"].notna().any() else np.nan

    total_solvent_kg = float(
        ready_reference_df["添加重量"].sum()
    ) if "添加重量" in ready_reference_df.columns and ready_reference_df["添加重量"].notna().any() else np.nan

    # -----------------------------------------------------
    # 12.3 Pilot readiness classification
    # -----------------------------------------------------
    if ready_records < 8:
        ready_status = "Insufficient Data"
        ready_icon = "⚪"
        ready_message = (
            "Historical reference is limited. Keep the current incoming viscosity "
            "and collect more matched records before a no-solvent pilot."
        )
    elif final_iqr <= 4:
        ready_status = "Ready for No-Solvent Pilot"
        ready_icon = "🟢"
        ready_message = (
            "Historical final viscosity is tightly concentrated. "
            "A supplier trial at the recommended incoming target is suitable "
            "for line validation."
        )
    elif final_iqr <= 8:
        ready_status = "Pilot with Monitoring"
        ready_icon = "🟡"
        ready_message = (
            "Historical final viscosity is moderately dispersed. "
            "A controlled pilot is possible, but viscosity and coating quality "
            "should be checked closely."
        )
    else:
        ready_status = "Not Ready for Direct Specification"
        ready_icon = "🟠"
        ready_message = (
            "Historical final viscosity is too dispersed for a narrow incoming "
            "specification. Further stratification or process review is recommended."
        )

    # -----------------------------------------------------
    # 12.4 KPI cards
    # -----------------------------------------------------
    r1, r2, r3, r4 = st.columns(4)

    r1.metric(
        "Current Incoming Median",
        f"{current_incoming_median:.1f} s",
    )

    r2.metric(
        "Recommended Lower",
        f"{recommended_lower:.1f} s",
    )

    r3.metric(
        "Recommended Target",
        f"{recommended_target:.1f} s",
    )

    r4.metric(
        "Recommended Upper",
        f"{recommended_upper:.1f} s",
    )

    # -----------------------------------------------------
    # 12.5 Recommendation table
    # -----------------------------------------------------
    ready_report = pd.DataFrame(
        [
            {
                "Vendor": selected_vendor,
                "Paint Code": selected_paint_code,
                "Position": selected_position,
                "Resin": selected_resin,
                "Solvent": selected_solvent,
                "Coating Structure": structure_text,
                "Reference Records": ready_records,
                "Current Incoming P25 (s)": current_incoming_p25,
                "Current Incoming Median (s)": current_incoming_median,
                "Current Incoming P75 (s)": current_incoming_p75,
                "Recommended Lower (s)": recommended_lower,
                "Recommended Target (s)": recommended_target,
                "Recommended Upper (s)": recommended_upper,
                "Final Viscosity IQR (s)": final_iqr,
                "Historical Median Solvent Ratio (%)": median_solvent_ratio,
                "Historical Median Solvent Added (kg)": median_solvent_kg,
                "Historical Solvent Total (kg)": total_solvent_kg,
                "Pilot Readiness": ready_status,
            }
        ]
    )

    st.dataframe(
        ready_report,
        column_config={
            "Reference Records": st.column_config.NumberColumn(
                "Reference Records", format="%d"
            ),
            "Current Incoming P25 (s)": st.column_config.NumberColumn(
                "Current Incoming P25 (s)", format="%.1f"
            ),
            "Current Incoming Median (s)": st.column_config.NumberColumn(
                "Current Incoming Median (s)", format="%.1f"
            ),
            "Current Incoming P75 (s)": st.column_config.NumberColumn(
                "Current Incoming P75 (s)", format="%.1f"
            ),
            "Recommended Lower (s)": st.column_config.NumberColumn(
                "Recommended Lower (s)", format="%.1f"
            ),
            "Recommended Target (s)": st.column_config.NumberColumn(
                "Recommended Target (s)", format="%.1f"
            ),
            "Recommended Upper (s)": st.column_config.NumberColumn(
                "Recommended Upper (s)", format="%.1f"
            ),
            "Final Viscosity IQR (s)": st.column_config.NumberColumn(
                "Final Viscosity IQR (s)", format="%.1f"
            ),
            "Historical Median Solvent Ratio (%)": st.column_config.NumberColumn(
                "Historical Median Solvent Ratio (%)", format="%.2f"
            ),
            "Historical Median Solvent Added (kg)": st.column_config.NumberColumn(
                "Historical Median Solvent Added (kg)", format="%.2f"
            ),
            "Historical Solvent Total (kg)": st.column_config.NumberColumn(
                "Historical Solvent Total (kg)", format="%.1f"
            ),
        },
        hide_index=True,
        use_container_width=True,
    )

    # -----------------------------------------------------
    # 12.6 Current vs recommended range chart
    # -----------------------------------------------------
    fig_ready = go.Figure()

    fig_ready.add_trace(
        go.Scatter(
            x=[
                current_incoming_p25,
                current_incoming_p75,
            ],
            y=[
                "Current Incoming",
                "Current Incoming",
            ],
            mode="lines",
            line=dict(width=18),
            name="Current Incoming P25–P75",
            hovertemplate=(
                "Current incoming range: "
                f"{current_incoming_p25:.1f}–{current_incoming_p75:.1f} s"
                "<extra></extra>"
            ),
        )
    )

    fig_ready.add_trace(
        go.Scatter(
            x=[current_incoming_median],
            y=["Current Incoming"],
            mode="markers+text",
            marker=dict(
                size=16,
                symbol="diamond",
            ),
            text=[f"{current_incoming_median:.1f} s"],
            textposition="top center",
            name="Current Incoming Median",
            hovertemplate=(
                "Current incoming median: "
                f"{current_incoming_median:.1f} s"
                "<extra></extra>"
            ),
        )
    )

    fig_ready.add_trace(
        go.Scatter(
            x=[
                recommended_lower,
                recommended_upper,
            ],
            y=[
                "Recommended Incoming",
                "Recommended Incoming",
            ],
            mode="lines",
            line=dict(width=18),
            name="Recommended P25–P75",
            hovertemplate=(
                "Recommended incoming range: "
                f"{recommended_lower:.1f}–{recommended_upper:.1f} s"
                "<extra></extra>"
            ),
        )
    )

    fig_ready.add_trace(
        go.Scatter(
            x=[recommended_target],
            y=["Recommended Incoming"],
            mode="markers+text",
            marker=dict(
                size=17,
                symbol="diamond",
            ),
            text=[f"Target {recommended_target:.1f} s"],
            textposition="bottom center",
            name="Recommended Target",
            hovertemplate=(
                "Recommended target: "
                f"{recommended_target:.1f} s"
                "<extra></extra>"
            ),
        )
    )

    x_min = min(
        current_incoming_p25,
        recommended_lower,
    )
    x_max = max(
        current_incoming_p75,
        recommended_upper,
    )
    x_pad = max((x_max - x_min) * 0.15, 5.0)

    fig_ready.update_layout(
        title=dict(
            text=(
                "<b>Current Incoming vs. Ready-to-Line Recommendation</b>"
                f"<br><sup>{selected_paint_code} | "
                f"Coating Structure: {structure_text}</sup>"
            ),
            x=0.5,
            xanchor="center",
        ),
        height=520,
        margin=dict(
            l=170,
            r=50,
            t=125,
            b=75,
        ),
        template="plotly_white",
        xaxis=dict(
            title="Viscosity (s)",
            range=[x_min - x_pad, x_max + x_pad],
            showgrid=True,
            gridcolor="#E5E7EB",
            showline=True,
            linecolor="#374151",
            mirror=True,
        ),
        yaxis=dict(
            title="",
            categoryorder="array",
            categoryarray=[
                "Recommended Incoming",
                "Current Incoming",
            ],
            showgrid=True,
            gridcolor="#E5E7EB",
            showline=True,
            linecolor="#374151",
            mirror=True,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
        ),
    )

    st.plotly_chart(
        fig_ready,
        use_container_width=True,
    )

    # -----------------------------------------------------
    # 12.7 Decision message
    # -----------------------------------------------------
    if ready_status == "Ready for No-Solvent Pilot":
        st.success(
            f"{ready_icon} **{ready_status}**  \n{ready_message}"
        )
    elif ready_status == "Pilot with Monitoring":
        st.warning(
            f"{ready_icon} **{ready_status}**  \n{ready_message}"
        )
    elif ready_status == "Not Ready for Direct Specification":
        st.warning(
            f"{ready_icon} **{ready_status}**  \n{ready_message}"
        )
    else:
        st.info(
            f"{ready_icon} **{ready_status}**  \n{ready_message}"
        )

    st.caption(
        "The recommended range is a supplier trial reference based on historical "
        "post-dilution viscosity. It should not be treated as a final purchasing "
        "specification until line validation confirms coating thickness, gloss, "
        "surface quality, and finished-product quality."
    )

# =========================================================
# 13. EXPORT
# =========================================================
st.markdown("---")
st.subheader("8. Export")

export_summary = summary_df.copy()
export_decision = decision_table.copy()

csv_summary = export_summary.to_csv(
    index=False
).encode("utf-8-sig")

csv_screen = screen_df.to_csv(
    index=False
).encode("utf-8-sig")

e1, e2 = st.columns(2)

with e1:
    st.download_button(
        "Download Selected Paint Code Thickness Summary",
        data=csv_summary,
        file_name=(
            f"Thickness_Viscosity_{selected_paint_code}.csv"
        ),
        mime="text/csv",
    )

with e2:
    st.download_button(
        "Download All Paint Codes Screening",
        data=csv_screen,
        file_name="Thickness_SOP_Screening_All_Paint_Codes.csv",
        mime="text/csv",
    )


# =========================================================
# 14. METHOD NOTE
# =========================================================
with st.expander("Method & Interpretation"):
    st.markdown(
        """
**Purpose**

This page answers three questions:

1. Under the same paint system, does final viscosity differ when order film thickness changes?
2. Does higher thickness tend to correspond to higher or lower final viscosity?
3. Is the difference large and consistent enough to justify a thickness-based SOP?

**Thickness mapping**

- TF / 正面漆 → active thickness = `TOPFILM_THICK`
- TP / 正底漆 → active thickness = `TTMFILM_THICK`
- BF / 背面漆 → active thickness = `BACKFILM_THICK`
- BP / 背底漆 → active thickness = `BTMFILM_THICK`

**Full coating structure shown in titles and tables**

- Top side = `TTMFILM_THICK + TOPFILM_THICK`
  = Primer + Top Finish
- Back side = `BTMFILM_THICK + BACKFILM_THICK`
  = Primer + Back Finish

Example: `5 µm + 20 µm (Primer + Top Finish)`.

**Important**

The automatic decision is a screening tool. Historical association does not prove causality.
A thickness-based SOP should be introduced only after a controlled line trial confirms that
the proposed viscosity ranges remain safe for coating quality, gloss, film thickness, and final product quality.
"""
    )
