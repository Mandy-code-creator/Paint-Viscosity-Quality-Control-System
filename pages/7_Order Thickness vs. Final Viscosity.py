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
# 8. COATING STRUCTURE ANALYSIS
# =========================================================
st.markdown("---")
st.subheader("3. Coating Structure Effect on Final Viscosity")

system_label = (
    f"{selected_resin} | {selected_position} | {selected_vendor} | "
    f"{selected_solvent} | {selected_paint_code}"
)

# Use the full Primer + Main Coat pair as the primary segmentation key.
structure_df = system_df[
    system_df["Coating_Structure"].notna()
    & ~system_df["Coating_Structure"].isin(["Unknown", "—"])
].copy()

if structure_df.empty:
    st.warning(
        "No valid coating-structure pairs are available for the selected system."
    )
    st.stop()

# Exact structure label used for analysis and recommendation.
structure_df["Structure_Key"] = structure_df["Coating_Structure"].astype(str)

# Helper to sort labels such as 5 µm + 20 µm numerically.
def structure_sort_key(label):
    try:
        left, right = str(label).replace("µm", "").split("+")
        return (float(left.strip()), float(right.strip()))
    except Exception:
        return (9999.0, 9999.0)

structure_order = sorted(
    structure_df["Structure_Key"].dropna().unique().tolist(),
    key=structure_sort_key,
)

# ---------------------------------------------------------
# 8.1 Structure summary
# ---------------------------------------------------------
structure_summary = (
    structure_df.groupby("Structure_Key", dropna=False)
    .agg(
        Records=("Paint_Code", "size"),
        Primer_Thickness=("Primer_Thickness", "median"),
        Main_Coat_Thickness=("Main_Coat_Thickness", "median"),
        Total_Coating_Thickness=("Total_Coating_Thickness", "median"),
        Incoming_P25=("黏度(秒)", lambda x: x.quantile(0.25)),
        Incoming_Median=("黏度(秒)", "median"),
        Incoming_P75=("黏度(秒)", lambda x: x.quantile(0.75)),
        Final_P25=("黏度(秒)_1", lambda x: x.quantile(0.25)),
        Final_Median=("黏度(秒)_1", "median"),
        Final_P75=("黏度(秒)_1", lambda x: x.quantile(0.75)),
        Median_Viscosity_Drop=("Delta_V", "median"),
        Median_Solvent_Ratio=("Solvent_Ratio_Percent", "median"),
    )
    .reset_index()
)

structure_summary["_sort"] = structure_summary["Structure_Key"].map(
    lambda x: structure_sort_key(x)
)
structure_summary = (
    structure_summary.sort_values("_sort")
    .drop(columns="_sort")
    .reset_index(drop=True)
)

usable_structures = structure_summary[
    structure_summary["Records"] >= MIN_GROUP_RECORDS
].copy()

structure_gap = np.nan
if len(usable_structures) >= 2:
    structure_gap = float(
        usable_structures["Final_Median"].max()
        - usable_structures["Final_Median"].min()
    )

s1, s2, s3, s4 = st.columns(4)
s1.metric("Records", f"{len(structure_df):,}")
s2.metric("Coating Structures", f"{structure_df['Structure_Key'].nunique():,}")
s3.metric("Usable Structures", f"{len(usable_structures):,}")
s4.metric(
    "Median Final Viscosity Gap",
    "N/A" if pd.isna(structure_gap) else f"{structure_gap:.1f} s",
)

st.info(
    f"**Selected system:** {system_label}  \n"
    "**Primary analysis unit:** exact coating structure = Primer thickness + Main coat thickness"
)

st.dataframe(
    structure_summary,
    column_config={
        "Structure_Key": "Coating Structure",
        "Records": st.column_config.NumberColumn("Records", format="%d"),
        "Primer_Thickness": st.column_config.NumberColumn("Primer (µm)", format="%.1f"),
        "Main_Coat_Thickness": st.column_config.NumberColumn("Main Coat (µm)", format="%.1f"),
        "Total_Coating_Thickness": st.column_config.NumberColumn("Total (µm)", format="%.1f"),
        "Incoming_P25": st.column_config.NumberColumn("Incoming P25 (s)", format="%.1f"),
        "Incoming_Median": st.column_config.NumberColumn("Incoming Median (s)", format="%.1f"),
        "Incoming_P75": st.column_config.NumberColumn("Incoming P75 (s)", format="%.1f"),
        "Final_P25": st.column_config.NumberColumn("Final P25 (s)", format="%.1f"),
        "Final_Median": st.column_config.NumberColumn("Final Median (s)", format="%.1f"),
        "Final_P75": st.column_config.NumberColumn("Final P75 (s)", format="%.1f"),
        "Median_Viscosity_Drop": st.column_config.NumberColumn("Median ΔV (s)", format="%.1f"),
        "Median_Solvent_Ratio": st.column_config.NumberColumn("Median Solvent Ratio (%)", format="%.2f"),
    },
    hide_index=True,
    use_container_width=True,
)

# ---------------------------------------------------------
# 8.2 Final viscosity distribution by exact structure
# ---------------------------------------------------------
fig_structure_box = px.box(
    structure_df,
    x="Structure_Key",
    y="黏度(秒)_1",
    points="all",
    category_orders={"Structure_Key": structure_order},
    labels={
        "Structure_Key": "Coating Structure (Primer + Main Coat)",
        "黏度(秒)_1": "Final Viscosity (s)",
    },
    hover_data={
        "Paint_Code": True,
        "Primer_Thickness": ":.1f",
        "Main_Coat_Thickness": ":.1f",
        "Total_Coating_Thickness": ":.1f",
        "黏度(秒)": ":.1f",
        "黏度(秒)_1": ":.1f",
        "Delta_V": ":.1f",
        "Solvent_Ratio_Percent": ":.2f",
    },
)

fig_structure_box.update_layout(
    title=dict(
        text=(
            "<b>Final Viscosity Distribution by Coating Structure</b>"
            f"<br><sup>{system_label}</sup>"
        ),
        x=0.5,
        xanchor="center",
    ),
    height=560,
    margin=dict(l=70, r=50, t=105, b=100),
    template="plotly_white",
    showlegend=False,
)
fig_structure_box.update_xaxes(
    showline=True,
    linecolor="#374151",
    mirror=True,
    tickangle=-20,
)
fig_structure_box.update_yaxes(
    showgrid=True,
    gridcolor="#E5E7EB",
    showline=True,
    linecolor="#374151",
    mirror=True,
)
st.plotly_chart(fig_structure_box, use_container_width=True)


# =========================================================
# 9. STRUCTURE SEGMENTATION DECISION
# =========================================================
st.markdown("---")
st.subheader("4. Should the SOP Be Split by Coating Structure?")

if len(structure_df) < MIN_TOTAL_RECORDS or len(usable_structures) < 2:
    structure_decision = "Insufficient Evidence"
    structure_icon = "⚪"
    structure_message = (
        "There are not enough records across at least two coating structures to "
        "support a structure-specific SOP decision."
    )
    structure_action = (
        "Keep the current SOP temporarily and continue collecting matched "
        "Primer + Main Coat thickness records."
    )
elif structure_gap >= PRACTICAL_FINAL_VISC_GAP:
    structure_decision = "Structure Effect Detected"
    structure_icon = "🟠"
    structure_message = (
        f"The median final-viscosity difference across usable coating structures is "
        f"{structure_gap:.1f} s, which is large enough to justify separate analysis."
    )
    structure_action = (
        "Use structure-specific incoming-viscosity pilot ranges. Validate each range "
        "on line before converting it into an official purchasing or production specification."
    )
elif structure_gap >= 3.0:
    structure_decision = "Possible Structure Effect"
    structure_icon = "🟡"
    structure_message = (
        f"The median final-viscosity difference is {structure_gap:.1f} s. "
        "A structure-related shift is visible but is not yet large enough for an automatic SOP split."
    )
    structure_action = (
        "Run a focused pilot by coating structure and confirm film thickness, gloss, "
        "surface quality, and finished-product quality before splitting the SOP."
    )
else:
    structure_decision = "One Common SOP May Be Sufficient"
    structure_icon = "🟢"
    structure_message = (
        f"The median final-viscosity difference across usable structures is only "
        f"{structure_gap:.1f} s."
    )
    structure_action = (
        "Keep one common SOP for now. Continue monitoring coating structure as a process variable."
    )

if structure_decision == "Structure Effect Detected":
    st.warning(f"{structure_icon} **{structure_decision}**  \n{structure_message}")
elif structure_decision == "Possible Structure Effect":
    st.info(f"{structure_icon} **{structure_decision}**  \n{structure_message}")
elif structure_decision == "One Common SOP May Be Sufficient":
    st.success(f"{structure_icon} **{structure_decision}**  \n{structure_message}")
else:
    st.info(f"{structure_icon} **{structure_decision}**  \n{structure_message}")

st.markdown(f"**Recommended action:** {structure_action}")


# =========================================================
# 10. STRUCTURE-SPECIFIC READY-TO-LINE RECOMMENDATIONS
# =========================================================
st.markdown("---")
st.subheader("5. Ready-to-Line Incoming Viscosity by Coating Structure")

st.markdown(
    "Each Primer + Main Coat thickness pair is evaluated separately. The proposed "
    "incoming range is based on the historical final-viscosity distribution of that "
    "exact coating structure, rather than mixing all thickness combinations together."
)

recommendation_rows = []
recommendation_reference = {}

for structure in structure_order:
    g = structure_df[structure_df["Structure_Key"] == structure].copy()
    g = g[g["黏度(秒)_1"].notna() & (g["黏度(秒)_1"] > 0)].copy()

    if g.empty:
        continue

    # Trim only extreme solvent-ratio records for the ready-to-line reference.
    ratio_ref = pd.to_numeric(g["Solvent_Ratio_Percent"], errors="coerce")
    if ratio_ref.notna().sum() >= 5:
        p10 = float(ratio_ref.quantile(0.10))
        p90 = float(ratio_ref.quantile(0.90))
        ref = g[g["Solvent_Ratio_Percent"].between(p10, p90, inclusive="both")].copy()
    else:
        p10 = np.nan
        p90 = np.nan
        ref = g.copy()

    if len(ref) < 5:
        ref = g.copy()

    n = len(ref)
    if n == 0:
        continue

    current_p25 = float(ref["黏度(秒)"].quantile(0.25))
    current_med = float(ref["黏度(秒)"].median())
    current_p75 = float(ref["黏度(秒)"].quantile(0.75))

    lower = float(ref["黏度(秒)_1"].quantile(0.25))
    target = float(ref["黏度(秒)_1"].median())
    upper = float(ref["黏度(秒)_1"].quantile(0.75))
    iqr = upper - lower

    if n < 8:
        status = "Insufficient Data"
    elif iqr <= 4:
        status = "Ready for No-Solvent Pilot"
    elif iqr <= 8:
        status = "Pilot with Monitoring"
    else:
        status = "Not Ready for Direct Specification"

    primer = float(ref["Primer_Thickness"].median()) if ref["Primer_Thickness"].notna().any() else np.nan
    main = float(ref["Main_Coat_Thickness"].median()) if ref["Main_Coat_Thickness"].notna().any() else np.nan
    total = float(ref["Total_Coating_Thickness"].median()) if ref["Total_Coating_Thickness"].notna().any() else np.nan
    med_ratio = float(ref["Solvent_Ratio_Percent"].median()) if ref["Solvent_Ratio_Percent"].notna().any() else np.nan
    med_solvent_kg = float(ref["添加重量"].median()) if "添加重量" in ref.columns and ref["添加重量"].notna().any() else np.nan
    total_solvent_kg = float(ref["添加重量"].sum()) if "添加重量" in ref.columns and ref["添加重量"].notna().any() else np.nan

    recommendation_rows.append(
        {
            "Coating Structure": structure,
            "Primer (µm)": primer,
            "Main Coat (µm)": main,
            "Total (µm)": total,
            "Reference Records": n,
            "Current Incoming P25 (s)": current_p25,
            "Current Incoming Median (s)": current_med,
            "Current Incoming P75 (s)": current_p75,
            "Recommended Lower (s)": lower,
            "Recommended Target (s)": target,
            "Recommended Upper (s)": upper,
            "Final Viscosity IQR (s)": iqr,
            "Historical Median Solvent Ratio (%)": med_ratio,
            "Historical Median Solvent Added (kg)": med_solvent_kg,
            "Historical Solvent Total (kg)": total_solvent_kg,
            "Pilot Readiness": status,
        }
    )
    recommendation_reference[structure] = ref

recommendation_df = pd.DataFrame(recommendation_rows)

if recommendation_df.empty:
    st.info("No valid structure-specific recommendation can be calculated.")
else:
    recommendation_df["_sort"] = recommendation_df["Coating Structure"].map(structure_sort_key)
    recommendation_df = (
        recommendation_df.sort_values("_sort")
        .drop(columns="_sort")
        .reset_index(drop=True)
    )

    st.dataframe(
        recommendation_df,
        column_config={
            "Coating Structure": st.column_config.TextColumn("Coating Structure", width="medium"),
            "Primer (µm)": st.column_config.NumberColumn("Primer (µm)", format="%.1f"),
            "Main Coat (µm)": st.column_config.NumberColumn("Main Coat (µm)", format="%.1f"),
            "Total (µm)": st.column_config.NumberColumn("Total (µm)", format="%.1f"),
            "Reference Records": st.column_config.NumberColumn("Reference Records", format="%d"),
            "Current Incoming P25 (s)": st.column_config.NumberColumn("Current P25 (s)", format="%.1f"),
            "Current Incoming Median (s)": st.column_config.NumberColumn("Current Median (s)", format="%.1f"),
            "Current Incoming P75 (s)": st.column_config.NumberColumn("Current P75 (s)", format="%.1f"),
            "Recommended Lower (s)": st.column_config.NumberColumn("Proposed Lower (s)", format="%.1f"),
            "Recommended Target (s)": st.column_config.NumberColumn("Proposed Target (s)", format="%.1f"),
            "Recommended Upper (s)": st.column_config.NumberColumn("Proposed Upper (s)", format="%.1f"),
            "Final Viscosity IQR (s)": st.column_config.NumberColumn("Final IQR (s)", format="%.1f"),
            "Historical Median Solvent Ratio (%)": st.column_config.NumberColumn("Median Solvent Ratio (%)", format="%.2f"),
            "Historical Median Solvent Added (kg)": st.column_config.NumberColumn("Median Solvent Added (kg)", format="%.2f"),
            "Historical Solvent Total (kg)": st.column_config.NumberColumn("Solvent Total (kg)", format="%.1f"),
            "Pilot Readiness": "Pilot Readiness",
        },
        hide_index=True,
        use_container_width=True,
    )

    # -----------------------------------------------------
    # 10.1 Inspect one exact structure
    # -----------------------------------------------------
    st.markdown("#### Inspect One Coating Structure")

    default_structure = recommendation_df.sort_values(
        "Reference Records", ascending=False
    ).iloc[0]["Coating Structure"]

    structure_options = recommendation_df["Coating Structure"].tolist()
    default_idx = structure_options.index(default_structure)

    selected_structure = st.selectbox(
        "Select Coating Structure:",
        structure_options,
        index=default_idx,
    )

    selected_row = recommendation_df[
        recommendation_df["Coating Structure"] == selected_structure
    ].iloc[0]

    rr1, rr2, rr3, rr4 = st.columns(4)
    rr1.metric("Reference Records", f"{int(selected_row['Reference Records']):,}")
    rr2.metric("Proposed Lower", f"{selected_row['Recommended Lower (s)']:.1f} s")
    rr3.metric("Proposed Target", f"{selected_row['Recommended Target (s)']:.1f} s")
    rr4.metric("Proposed Upper", f"{selected_row['Recommended Upper (s)']:.1f} s")

    # Current incoming vs proposed range for selected structure.
    current_p25 = selected_row["Current Incoming P25 (s)"]
    current_med = selected_row["Current Incoming Median (s)"]
    current_p75 = selected_row["Current Incoming P75 (s)"]
    lower = selected_row["Recommended Lower (s)"]
    target = selected_row["Recommended Target (s)"]
    upper = selected_row["Recommended Upper (s)"]

    fig_ready = go.Figure()
    fig_ready.add_trace(
        go.Scatter(
            x=[current_p25, current_p75],
            y=["Current Incoming", "Current Incoming"],
            mode="lines",
            line=dict(width=18),
            name="Current Incoming P25–P75",
            hovertemplate=(
                f"Current incoming range: {current_p25:.1f}–{current_p75:.1f} s"
                "<extra></extra>"
            ),
        )
    )
    fig_ready.add_trace(
        go.Scatter(
            x=[current_med],
            y=["Current Incoming"],
            mode="markers+text",
            marker=dict(size=16, symbol="diamond"),
            text=[f"{current_med:.1f} s"],
            textposition="top center",
            name="Current Incoming Median",
            hovertemplate=(
                f"Current incoming median: {current_med:.1f} s<extra></extra>"
            ),
        )
    )
    fig_ready.add_trace(
        go.Scatter(
            x=[lower, upper],
            y=["Proposed Incoming", "Proposed Incoming"],
            mode="lines",
            line=dict(width=18),
            name="Proposed P25–P75",
            hovertemplate=(
                f"Proposed range: {lower:.1f}–{upper:.1f} s<extra></extra>"
            ),
        )
    )
    fig_ready.add_trace(
        go.Scatter(
            x=[target],
            y=["Proposed Incoming"],
            mode="markers+text",
            marker=dict(size=17, symbol="diamond"),
            text=[f"Target {target:.1f} s"],
            textposition="bottom center",
            name="Proposed Target",
            hovertemplate=f"Proposed target: {target:.1f} s<extra></extra>",
        )
    )

    x_min = min(current_p25, lower)
    x_max = max(current_p75, upper)
    x_pad = max((x_max - x_min) * 0.15, 5.0)

    fig_ready.update_layout(
        title=dict(
            text=(
                "<b>Current Incoming vs. Structure-Specific Recommendation</b>"
                f"<br><sup>{selected_paint_code} | {selected_structure}</sup>"
            ),
            x=0.5,
            xanchor="center",
        ),
        height=520,
        margin=dict(l=170, r=50, t=115, b=75),
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
            categoryarray=["Proposed Incoming", "Current Incoming"],
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
    st.plotly_chart(fig_ready, use_container_width=True)

    selected_status = selected_row["Pilot Readiness"]
    if selected_status == "Ready for No-Solvent Pilot":
        st.success(
            "🟢 **Ready for No-Solvent Pilot**  \n"
            "The historical final viscosity for this exact coating structure is tightly concentrated."
        )
    elif selected_status == "Pilot with Monitoring":
        st.warning(
            "🟡 **Pilot with Monitoring**  \n"
            "A controlled supplier trial is possible, but line quality should be monitored closely."
        )
    elif selected_status == "Not Ready for Direct Specification":
        st.warning(
            "🟠 **Not Ready for Direct Specification**  \n"
            "The final-viscosity distribution is still too dispersed for a narrow incoming specification."
        )
    else:
        st.info(
            "⚪ **Insufficient Data**  \n"
            "Collect more records for this exact coating structure before setting a no-solvent target."
        )

    st.caption(
        "The proposed range is a supplier trial reference derived from historical "
        "post-dilution viscosity for the exact coating structure. It is not a final "
        "purchasing specification until line validation confirms coating thickness, "
        "gloss, surface quality, and finished-product quality."
    )


# =========================================================
# 11. ACTIVE-LAYER THICKNESS TREND — SECONDARY VIEW
# =========================================================
st.markdown("---")
st.subheader("6. Active-Layer Thickness Trend — Secondary View")

st.caption(
    "This view is retained only as a secondary engineering screen. The main SOP "
    "segmentation above uses the full Primer + Main Coat structure."
)

system_df["Thickness_Group"] = adaptive_thickness_group(
    system_df["Order_Film_Thickness"]
)
metrics = calculate_relationship_metrics(system_df)
decision = classify_sop_decision(metrics)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Records", f"{metrics['records']:,}")
m2.metric("Unique Active Thickness", f"{metrics['unique_thickness']:,}")
m3.metric("Spearman Correlation", safe_metric(metrics["spearman_r"], "{:.2f}"))
m4.metric("Slope", safe_metric(metrics["slope"], "{:.2f} s/µm"))
m5.metric("Median Final Gap", safe_metric(metrics["final_visc_gap"], "{:.1f} s"))

fig_scatter = px.scatter(
    system_df,
    x="Order_Film_Thickness",
    y="黏度(秒)_1",
    color="Coating_Structure",
    hover_data={
        "Paint_Code": True,
        "Coating_Structure_Detail": True,
        "Primer_Thickness": ":.1f",
        "Main_Coat_Thickness": ":.1f",
        "黏度(秒)": ":.1f",
        "黏度(秒)_1": ":.1f",
        "Solvent_Ratio_Percent": ":.2f",
    },
    labels={
        "Order_Film_Thickness": "Active Layer Thickness (µm)",
        "黏度(秒)_1": "Final Viscosity (s)",
        "Coating_Structure": "Coating Structure",
    },
)
fig_scatter.update_traces(marker=dict(size=9, opacity=0.75, line=dict(width=0.8, color="white")))
fig_scatter.update_layout(
    title=dict(
        text=(
            "<b>Active-Layer Thickness vs. Final Viscosity</b>"
            f"<br><sup>{system_label}</sup>"
        ),
        x=0.5,
        xanchor="center",
    ),
    height=560,
    margin=dict(l=70, r=50, t=110, b=70),
    template="plotly_white",
    legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="center", x=0.5),
)
fig_scatter.update_xaxes(showgrid=True, gridcolor="#E5E7EB", showline=True, linecolor="#374151", mirror=True)
fig_scatter.update_yaxes(showgrid=True, gridcolor="#E5E7EB", showline=True, linecolor="#374151", mirror=True)
st.plotly_chart(fig_scatter, use_container_width=True)


# =========================================================
# 12. ALL PAINT CODES — STRUCTURE EFFECT SCREENING
# =========================================================
st.markdown("---")
st.subheader("7. All Paint Codes — Coating Structure Screening")

st.caption(
    "This table checks each paint code under the selected Vendor × Position × Resin × Solvent "
    "condition and identifies whether exact coating structures show practically different final viscosity."
)

screen_source = filter_source[
    (filter_source["Vendor"] == selected_vendor)
    & (filter_source["Position_Detail"] == selected_position)
    & (filter_source["Resin"] == selected_resin)
    & (filter_source["Solvent_Type"] == selected_solvent)
].copy()

screen_rows = []
for paint_code, code_df in screen_source.groupby("Paint_Code", dropna=False):
    code_df = code_df[
        code_df["Coating_Structure"].notna()
        & ~code_df["Coating_Structure"].isin(["Unknown", "—"])
    ].copy()

    if code_df.empty:
        continue

    temp = (
        code_df.groupby("Coating_Structure")
        .agg(
            Records=("Paint_Code", "size"),
            Final_Median=("黏度(秒)_1", "median"),
        )
        .reset_index()
    )
    usable = temp[temp["Records"] >= MIN_GROUP_RECORDS]

    gap = np.nan
    if len(usable) >= 2:
        gap = float(usable["Final_Median"].max() - usable["Final_Median"].min())

    if len(code_df) < MIN_TOTAL_RECORDS or len(usable) < 2:
        d = "Insufficient Evidence"
    elif gap >= PRACTICAL_FINAL_VISC_GAP:
        d = "Structure Effect Detected"
    elif gap >= 3.0:
        d = "Possible Structure Effect"
    else:
        d = "One Common SOP May Be Sufficient"

    screen_rows.append(
        {
            "Paint Code": str(paint_code),
            "Records": len(code_df),
            "Coating Structures": code_df["Coating_Structure"].nunique(),
            "Usable Structures": len(usable),
            "Median Final Viscosity Gap (s)": gap,
            "Decision": d,
        }
    )

screen_df = pd.DataFrame(screen_rows)

if screen_df.empty:
    st.info("No paint-code structure-screening results are available.")
else:
    priority_map = {
        "Structure Effect Detected": 1,
        "Possible Structure Effect": 2,
        "One Common SOP May Be Sufficient": 3,
        "Insufficient Evidence": 4,
    }
    screen_df["_Priority"] = screen_df["Decision"].map(priority_map).fillna(99)
    screen_df = (
        screen_df.sort_values(
            ["_Priority", "Median Final Viscosity Gap (s)", "Records"],
            ascending=[True, False, False],
            na_position="last",
        )
        .drop(columns="_Priority")
        .reset_index(drop=True)
    )

    st.dataframe(
        screen_df,
        column_config={
            "Paint Code": "Paint Code",
            "Records": st.column_config.NumberColumn("Records", format="%d"),
            "Coating Structures": st.column_config.NumberColumn("Structures", format="%d"),
            "Usable Structures": st.column_config.NumberColumn("Usable Structures", format="%d"),
            "Median Final Viscosity Gap (s)": st.column_config.NumberColumn("Final Viscosity Gap (s)", format="%.1f"),
            "Decision": "SOP Decision",
        },
        hide_index=True,
        use_container_width=True,
    )


# =========================================================
# 13. EXPORT
# =========================================================
st.markdown("---")
st.subheader("8. Export")

csv_structure_summary = structure_summary.to_csv(index=False).encode("utf-8-sig")
csv_recommendation = recommendation_df.to_csv(index=False).encode("utf-8-sig") if not recommendation_df.empty else b""
csv_screen = screen_df.to_csv(index=False).encode("utf-8-sig") if not screen_df.empty else b""

e1, e2, e3 = st.columns(3)

with e1:
    st.download_button(
        "Download Structure Summary",
        data=csv_structure_summary,
        file_name=f"Coating_Structure_Summary_{selected_paint_code}.csv",
        mime="text/csv",
    )

with e2:
    st.download_button(
        "Download Structure Recommendations",
        data=csv_recommendation,
        file_name=f"Structure_Viscosity_Recommendations_{selected_paint_code}.csv",
        mime="text/csv",
        disabled=recommendation_df.empty,
    )

with e3:
    st.download_button(
        "Download All Paint Codes Screening",
        data=csv_screen,
        file_name="Coating_Structure_SOP_Screening_All_Paint_Codes.csv",
        mime="text/csv",
        disabled=screen_df.empty,
    )


# =========================================================
# 14. METHOD NOTE
# =========================================================
with st.expander("Method & Interpretation"):
    st.markdown(
        """
**Purpose**

This page answers four questions:

1. Under the same paint system, do different **Primer + Main Coat thickness pairs** have different final-viscosity distributions?
2. Is the difference large enough to justify separate SOP or supplier pilot ranges?
3. What incoming-viscosity range should be tested for each exact coating structure?
4. Does active-layer thickness still show a broader directional relationship with final viscosity?

**Primary segmentation unit**

- Top side = `TTMFILM_THICK + TOPFILM_THICK` = Primer + Top Finish
- Back side = `BTMFILM_THICK + BACKFILM_THICK` = Primer + Back Finish

Example: `5 µm + 20 µm` and `10 µm + 20 µm` are treated as **different coating structures**, even though both have a 20 µm main coat.

**Structure-specific recommendation**

For each exact coating structure:

- Proposed Lower = historical final-viscosity P25
- Proposed Target = historical final-viscosity Median
- Proposed Upper = historical final-viscosity P75

Extreme solvent-ratio records are trimmed at P10–P90 when enough data are available; if trimming leaves too few records, all valid records are used.

**Evidence rules**

- A structure needs at least `MIN_GROUP_RECORDS` records to enter the structure-gap comparison.
- If the median final-viscosity gap across usable structures is at least 5 s, the app flags a practical structure effect.
- A 3–5 s gap is treated as a possible structure effect requiring a focused pilot.
- These thresholds are engineering screening rules, not proof of causality.

**Important**

The proposed range is a supplier trial reference only. Before changing an official incoming specification, validate that the proposed viscosity can run directly on line and still meet film thickness, gloss, surface quality, and finished-product quality requirements.
"""
    )
