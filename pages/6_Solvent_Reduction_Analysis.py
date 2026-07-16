
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="Solvent Reduction Analysis",
    page_icon="🎨",
    layout="wide"
)

st.title("🎨 Paint Viscosity Improvement & Solvent Reduction")

st.markdown(
    """
    This module identifies frequently used paint codes with high solvent
    consumption and compares viscosity performance across production lines.
    The results support supplier discussions regarding suitable delivery
    viscosity and solvent-reduction opportunities.
    """
)


# =========================================================
# 2. MATPLOTLIB SETTINGS
# =========================================================
plt.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei",
    "Arial Unicode MS",
    "Noto Sans CJK TC",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False


# =========================================================
# 3. LOAD DATA
# =========================================================
if not st.session_state.get("raw_data_loaded", False):
    st.warning("⚠️ Please return to the Main App page and upload the raw data first.")
    st.stop()

group_a = st.session_state.get("group_a_data")

if group_a is None or group_a.empty:
    st.warning("⚠️ No valid Group A data are available for analysis.")
    st.stop()

df = group_a.copy()


# =========================================================
# 4. REQUIRED COLUMNS
# =========================================================
text_defaults = [
    "Vendor",
    "Resin",
    "Solvent_Type",
    "塗料批號",
    "線別",
    "塗裝位置",
]

numeric_defaults = [
    "塗料重量",
    "添加重量",
    "黏度(秒)",
    "黏度(秒)_1",
    "Delta_V",
    "Solvent_Ratio_Percent",
    "Viscosity_Sensitivity",
]

for col in text_defaults:
    if col not in df.columns:
        df[col] = "Unknown"

for col in numeric_defaults:
    if col not in df.columns:
        df[col] = np.nan

if "Paint_Code" not in df.columns:
    if "塗料編號" in df.columns:
        df["Paint_Code"] = (
            df["塗料編號"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
        )
    else:
        df["Paint_Code"] = "Unknown"


# =========================================================
# 5. NORMALIZE TEXT FIELDS
# =========================================================
invalid_text_values = {
    "",
    "NAN",
    "NONE",
    "NULL",
    "N/A",
    "NA",
    "-",
    "--",
}

text_columns = [
    "Vendor",
    "Resin",
    "Paint_Code",
    "Solvent_Type",
    "線別",
    "塗料批號",
    "塗裝位置",
]

for col in text_columns:
    df[col] = (
        df[col]
        .fillna("")
        .astype(str)
        .str.strip()
    )

df["Paint_Code"] = df["Paint_Code"].str.upper()
df["Solvent_Type"] = df["Solvent_Type"].str.upper()

for col in [
    "Vendor",
    "Resin",
    "Paint_Code",
    "Solvent_Type",
    "線別",
    "塗裝位置",
]:
    df.loc[
        df[col].str.upper().isin(invalid_text_values),
        col
    ] = "Unknown"

df["Batch_ID"] = df["塗料批號"].copy()


# =========================================================
# 6. COATING POSITION MAPPING
# =========================================================
position_mapping = {
    "TP": "Primer",
    "正底漆": "Primer",
    "BP": "Primer",
    "背底漆": "Primer",
    "TF": "Top Finish",
    "正面漆": "Top Finish",
    "BF": "Back Finish",
    "背面漆": "Back Finish",
}

df["Position_UI"] = (
    df["塗裝位置"]
    .map(position_mapping)
    .fillna(df["塗裝位置"])
)

df.loc[
    df["Position_UI"].astype(str).str.upper().isin(invalid_text_values),
    "Position_UI"
] = "Unknown"


# =========================================================
# 7. NUMERIC CLEANING & CORE CALCULATIONS
# =========================================================
for col in numeric_defaults:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df["Delta_V"] = df["黏度(秒)"] - df["黏度(秒)_1"]

df["Solvent_Ratio_Percent"] = np.where(
    df["塗料重量"] > 0,
    df["添加重量"] / df["塗料重量"] * 100,
    np.nan,
)

df["Viscosity_Sensitivity"] = np.where(
    df["Solvent_Ratio_Percent"] > 0,
    df["Delta_V"] / df["Solvent_Ratio_Percent"],
    np.nan,
)

df = df.replace([np.inf, -np.inf], np.nan)

df = df[
    (df["塗料重量"] > 0)
    & (df["添加重量"] > 0)
    & (df["黏度(秒)"] > 0)
    & (df["黏度(秒)_1"] > 0)
    & (df["Delta_V"] > 0)
    & (df["Solvent_Ratio_Percent"] > 0)
].copy()

if df.empty:
    st.warning("⚠️ No valid dilution records remain after data cleaning.")
    st.stop()


# =========================================================
# 8. HELPER FUNCTIONS
# =========================================================
def clean_options(series):
    values = (
        series
        .dropna()
        .astype(str)
        .str.strip()
    )

    values = values[
        ~values.str.upper().isin(invalid_text_values)
    ]

    return sorted(values.unique().tolist())


def distinct_batch_count(series):
    values = (
        series
        .dropna()
        .astype(str)
        .str.strip()
    )

    values = values[
        ~values.str.upper().isin(invalid_text_values)
    ]

    return values.nunique()


def percentile_range(series, low=0.10, high=0.90):
    valid = pd.to_numeric(series, errors="coerce").dropna()

    if valid.empty:
        return "-"

    p_low = valid.quantile(low)
    p_high = valid.quantile(high)

    if np.isclose(p_low, p_high):
        return f"{p_low:.1f}"

    return f"{p_low:.1f} – {p_high:.1f}"


def safe_metric(value, decimals=1, suffix=""):
    if value is None or pd.isna(value):
        return "-"

    return f"{value:,.{decimals}f}{suffix}"


def apply_filter(data, column, selected_value):
    if selected_value == "All":
        return data.copy()

    return data[
        data[column].astype(str) == str(selected_value)
    ].copy()


def select_all_filter(label, source_df, column, key):
    options = ["All"] + clean_options(source_df[column])

    return st.selectbox(
        label,
        options=options,
        key=key,
    )


def build_priority_summary(source_df):
    if source_df.empty:
        return pd.DataFrame()

    group_columns = [
        "Vendor",
        "Resin",
        "Position_UI",
        "Paint_Code",
        "Solvent_Type",
    ]

    summary = source_df.groupby(
        group_columns,
        observed=False,
        dropna=False,
    ).agg(
        Adjustment_Records=("Paint_Code", "size"),
        Historical_Batches=("Batch_ID", distinct_batch_count),
        Production_Lines=("線別", lambda x: x[x != "Unknown"].nunique()),
        Total_Paint_kg=("塗料重量", "sum"),
        Total_Solvent_kg=("添加重量", "sum"),
        Median_Paint_kg=("塗料重量", "median"),
        Median_Solvent_kg=("添加重量", "median"),
        Median_Ratio_Percent=("Solvent_Ratio_Percent", "median"),
        Median_Viscosity_Before=("黏度(秒)", "median"),
        Median_Viscosity_After=("黏度(秒)_1", "median"),
        Median_Delta_V=("Delta_V", "median"),
        Median_Efficiency=("Viscosity_Sensitivity", "median"),
    ).reset_index()

    summary["Weighted_Ratio_Percent"] = np.where(
        summary["Total_Paint_kg"] > 0,
        summary["Total_Solvent_kg"]
        / summary["Total_Paint_kg"]
        * 100,
        np.nan,
    )

    summary["Solvent_Per_Batch_kg"] = np.where(
        summary["Historical_Batches"] > 0,
        summary["Total_Solvent_kg"]
        / summary["Historical_Batches"],
        np.nan,
    )

    summary["Batch_Score"] = (
        summary["Historical_Batches"]
        .rank(method="average", pct=True)
    )

    summary["Solvent_Score"] = (
        summary["Total_Solvent_kg"]
        .rank(method="average", pct=True)
    )

    summary["Ratio_Score"] = (
        summary["Weighted_Ratio_Percent"]
        .rank(method="average", pct=True)
    )

    summary["Opportunity_Score"] = (
        summary["Batch_Score"] * 0.35
        + summary["Solvent_Score"] * 0.45
        + summary["Ratio_Score"] * 0.20
    ) * 100

    summary["Priority_Level"] = pd.cut(
        summary["Opportunity_Score"],
        bins=[-np.inf, 40, 70, np.inf],
        labels=["Normal", "Medium Priority", "High Priority"],
    ).astype(str)

    summary = summary.sort_values(
        by=[
            "Opportunity_Score",
            "Total_Solvent_kg",
            "Historical_Batches",
        ],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    summary["Priority_Rank"] = np.arange(
        1,
        len(summary) + 1,
    )

    return summary


def prepare_priority_display(summary_df):
    if summary_df.empty:
        return pd.DataFrame()

    display_df = summary_df[
        [
            "Priority_Rank",
            "Priority_Level",
            "Vendor",
            "Resin",
            "Position_UI",
            "Paint_Code",
            "Solvent_Type",
            "Adjustment_Records",
            "Historical_Batches",
            "Production_Lines",
            "Total_Paint_kg",
            "Total_Solvent_kg",
            "Weighted_Ratio_Percent",
            "Solvent_Per_Batch_kg",
            "Median_Viscosity_Before",
            "Median_Viscosity_After",
            "Opportunity_Score",
        ]
    ].copy()

    display_df.columns = [
        "Rank",
        "Priority Level",
        "Vendor",
        "Resin Type",
        "Coating Position",
        "Paint Code",
        "Solvent Type",
        "Adjustment Records",
        "Historical Batches",
        "Production Lines",
        "Total Paint (kg)",
        "Total Solvent (kg)",
        "Weighted Ratio (%)",
        "Average Solvent per Batch (kg)",
        "Median Before Viscosity (s)",
        "Median After Viscosity (s)",
        "Opportunity Score",
    ]

    numeric_columns = [
        "Total Paint (kg)",
        "Total Solvent (kg)",
        "Weighted Ratio (%)",
        "Average Solvent per Batch (kg)",
        "Median Before Viscosity (s)",
        "Median After Viscosity (s)",
        "Opportunity Score",
    ]

    for col in numeric_columns:
        display_df[col] = pd.to_numeric(
            display_df[col],
            errors="coerce",
        ).round(2)

    return display_df


def build_line_comparison_candidates(
    source_df,
    min_records_per_line=3,
):
    line_group_columns = [
        "Vendor",
        "Resin",
        "Position_UI",
        "Paint_Code",
        "Solvent_Type",
        "線別",
    ]

    line_level = source_df.groupby(
        line_group_columns,
        observed=False,
        dropna=False,
    ).agg(
        Records=("Paint_Code", "size"),
        Batches=("Batch_ID", distinct_batch_count),
        Total_Paint_kg=("塗料重量", "sum"),
        Total_Solvent_kg=("添加重量", "sum"),
        Median_Paint_kg=("塗料重量", "median"),
        Median_Solvent_kg=("添加重量", "median"),
        Median_Before=("黏度(秒)", "median"),
        Median_After=("黏度(秒)_1", "median"),
        Median_Delta=("Delta_V", "median"),
        Median_Efficiency=("Viscosity_Sensitivity", "median"),
    ).reset_index()

    line_level = line_level[
        (line_level["線別"] != "Unknown")
        & (line_level["Records"] >= min_records_per_line)
    ].copy()

    if line_level.empty:
        return pd.DataFrame(), pd.DataFrame()

    line_level["Weighted_Ratio"] = np.where(
        line_level["Total_Paint_kg"] > 0,
        line_level["Total_Solvent_kg"]
        / line_level["Total_Paint_kg"]
        * 100,
        np.nan,
    )

    group_columns = [
        "Vendor",
        "Resin",
        "Position_UI",
        "Paint_Code",
        "Solvent_Type",
    ]

    candidates = line_level.groupby(
        group_columns,
        observed=False,
        dropna=False,
    ).agg(
        Production_Lines=("線別", "nunique"),
        Total_Records=("Records", "sum"),
        Total_Batches=("Batches", "sum"),
        Total_Solvent_kg=("Total_Solvent_kg", "sum"),
        Min_Weighted_Ratio=("Weighted_Ratio", "min"),
        Max_Weighted_Ratio=("Weighted_Ratio", "max"),
        Min_Before=("Median_Before", "min"),
        Max_Before=("Median_Before", "max"),
        Min_After=("Median_After", "min"),
        Max_After=("Median_After", "max"),
    ).reset_index()

    candidates = candidates[
        candidates["Production_Lines"] >= 2
    ].copy()

    if candidates.empty:
        return pd.DataFrame(), line_level

    candidates["Ratio_Difference"] = (
        candidates["Max_Weighted_Ratio"]
        - candidates["Min_Weighted_Ratio"]
    )

    candidates["Before_Viscosity_Difference"] = (
        candidates["Max_Before"]
        - candidates["Min_Before"]
    )

    candidates["After_Viscosity_Difference"] = (
        candidates["Max_After"]
        - candidates["Min_After"]
    )

    candidates["Comparison_Score"] = (
        candidates["Total_Records"].rank(pct=True) * 25
        + candidates["Total_Solvent_kg"].rank(pct=True) * 35
        + candidates["Ratio_Difference"].rank(pct=True) * 25
        + candidates["Before_Viscosity_Difference"].rank(pct=True) * 15
    )

    candidates = candidates.sort_values(
        by=[
            "Comparison_Score",
            "Total_Solvent_kg",
            "Total_Records",
        ],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    candidates["Condition_Label"] = (
        candidates["Vendor"].astype(str)
        + " | "
        + candidates["Resin"].astype(str)
        + " | "
        + candidates["Position_UI"].astype(str)
        + " | "
        + candidates["Paint_Code"].astype(str)
        + " | "
        + candidates["Solvent_Type"].astype(str)
        + " | "
        + candidates["Production_Lines"].astype(int).astype(str)
        + " Lines"
    )

    return candidates, line_level


# =========================================================
# 9. MAIN SUB-TABS
# =========================================================
tab_priority, tab_detail, tab_line = st.tabs([
    "1. Reduction Priority",
    "2. Paint Code Details",
    "3. Production Line Comparison",
])


# =========================================================
# TAB 1: REDUCTION PRIORITY
# =========================================================
with tab_priority:
    st.subheader("1. Solvent Reduction Priority")

    st.caption(
        "Rank paint codes using historical batch count, total solvent usage, "
        "and weighted solvent ratio."
    )

    st.markdown("#### Analysis Filters")

    f1, f2, f3, f4, f5 = st.columns(5)

    with f1:
        selected_vendor = select_all_filter(
            "Vendor",
            df,
            "Vendor",
            "priority_vendor",
        )

    priority_df = apply_filter(
        df,
        "Vendor",
        selected_vendor,
    )

    with f2:
        selected_resin = select_all_filter(
            "Resin Type",
            priority_df,
            "Resin",
            "priority_resin",
        )

    priority_df = apply_filter(
        priority_df,
        "Resin",
        selected_resin,
    )

    with f3:
        selected_position = select_all_filter(
            "Coating Position",
            priority_df,
            "Position_UI",
            "priority_position",
        )

    priority_df = apply_filter(
        priority_df,
        "Position_UI",
        selected_position,
    )

    with f4:
        selected_solvent = select_all_filter(
            "Solvent Type",
            priority_df,
            "Solvent_Type",
            "priority_solvent",
        )

    priority_df = apply_filter(
        priority_df,
        "Solvent_Type",
        selected_solvent,
    )

    with f5:
        selected_line = select_all_filter(
            "Production Line",
            priority_df,
            "線別",
            "priority_line",
        )

    priority_df = apply_filter(
        priority_df,
        "線別",
        selected_line,
    )

    if priority_df.empty:
        st.warning("⚠️ No records match the selected filters.")
    else:
        priority_summary = build_priority_summary(priority_df)

        total_paint_codes = priority_summary["Paint_Code"].nunique()
        total_batches = priority_summary["Historical_Batches"].sum()
        total_paint = priority_summary["Total_Paint_kg"].sum()
        total_solvent = priority_summary["Total_Solvent_kg"].sum()

        overall_weighted_ratio = (
            total_solvent / total_paint * 100
            if total_paint > 0
            else np.nan
        )

        k1, k2, k3, k4, k5 = st.columns(5)

        k1.metric(
            "Paint Codes",
            f"{total_paint_codes:,}",
        )

        k2.metric(
            "Historical Batches",
            f"{int(total_batches):,}",
        )

        k3.metric(
            "Total Paint",
            safe_metric(total_paint, 0, " kg"),
        )

        k4.metric(
            "Total Solvent",
            safe_metric(total_solvent, 0, " kg"),
        )

        k5.metric(
            "Overall Weighted Ratio",
            safe_metric(overall_weighted_ratio, 2, "%"),
        )

        st.markdown("---")

        top_n_limit = max(
            1,
            min(30, len(priority_summary)),
        )

        top_n_default = min(
            15,
            top_n_limit,
        )

        top_n = st.slider(
            "Number of paint codes to display",
            min_value=1,
            max_value=top_n_limit,
            value=top_n_default,
            step=1,
            key="priority_top_n",
        )

        ranking_mode = st.radio(
            "Ranking Method",
            options=[
                "Overall Opportunity",
                "Highest Usage Frequency",
                "Highest Total Solvent",
                "Highest Weighted Ratio",
            ],
            horizontal=True,
            key="priority_ranking_mode",
        )

        if ranking_mode == "Highest Usage Frequency":
            ranked_df = priority_summary.sort_values(
                by=[
                    "Historical_Batches",
                    "Adjustment_Records",
                    "Total_Solvent_kg",
                ],
                ascending=[False, False, False],
            ).copy()

        elif ranking_mode == "Highest Total Solvent":
            ranked_df = priority_summary.sort_values(
                by=[
                    "Total_Solvent_kg",
                    "Historical_Batches",
                    "Weighted_Ratio_Percent",
                ],
                ascending=[False, False, False],
            ).copy()

        elif ranking_mode == "Highest Weighted Ratio":
            ranked_df = priority_summary.sort_values(
                by=[
                    "Weighted_Ratio_Percent",
                    "Historical_Batches",
                    "Total_Solvent_kg",
                ],
                ascending=[False, False, False],
            ).copy()

        else:
            ranked_df = priority_summary.sort_values(
                by=[
                    "Opportunity_Score",
                    "Total_Solvent_kg",
                    "Historical_Batches",
                ],
                ascending=[False, False, False],
            ).copy()

        ranked_df = ranked_df.reset_index(drop=True)
        ranked_df["Priority_Rank"] = np.arange(
            1,
            len(ranked_df) + 1,
        )

        top_ranked = ranked_df.head(top_n).copy()

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.markdown("#### Paint Codes with Highest Total Solvent")

            solvent_chart_df = (
                priority_summary
                .sort_values(
                    "Total_Solvent_kg",
                    ascending=False,
                )
                .head(top_n)
                .sort_values(
                    "Total_Solvent_kg",
                    ascending=True,
                )
            )

            fig1, ax1 = plt.subplots(
                figsize=(9, max(5, top_n * 0.42)),
                dpi=150,
            )

            labels = (
                solvent_chart_df["Paint_Code"]
                + " | "
                + solvent_chart_df["Vendor"]
            )

            ax1.barh(
                labels,
                solvent_chart_df["Total_Solvent_kg"],
            )

            for index, value in enumerate(
                solvent_chart_df["Total_Solvent_kg"]
            ):
                ax1.text(
                    value,
                    index,
                    f" {value:,.0f} kg",
                    va="center",
                    fontsize=8,
                )

            ax1.set_xlabel("Total Solvent Usage (kg)")
            ax1.set_ylabel("Paint Code")
            ax1.grid(
                axis="x",
                linestyle="--",
                linewidth=0.6,
                alpha=0.4,
            )

            for spine in ax1.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(1.0)

            fig1.tight_layout()
            st.pyplot(fig1, use_container_width=True)
            plt.close(fig1)

        with chart_col2:
            st.markdown("#### Usage Frequency vs Total Solvent")

            scatter_df = priority_summary.copy()

            size_values = (
                scatter_df["Weighted_Ratio_Percent"]
                .fillna(0)
                .clip(lower=0)
            )

            if size_values.max() > 0:
                marker_sizes = (
                    size_values / size_values.max() * 500
                ) + 50
            else:
                marker_sizes = np.full(
                    len(scatter_df),
                    80,
                )

            fig2, ax2 = plt.subplots(
                figsize=(9, 6),
                dpi=150,
            )

            ax2.scatter(
                scatter_df["Historical_Batches"],
                scatter_df["Total_Solvent_kg"],
                s=marker_sizes,
                alpha=0.65,
            )

            label_df = (
                scatter_df
                .sort_values(
                    "Opportunity_Score",
                    ascending=False,
                )
                .head(min(10, len(scatter_df)))
            )

            for _, row in label_df.iterrows():
                ax2.annotate(
                    row["Paint_Code"],
                    (
                        row["Historical_Batches"],
                        row["Total_Solvent_kg"],
                    ),
                    xytext=(5, 5),
                    textcoords="offset points",
                    fontsize=8,
                )

            ax2.set_xlabel("Historical Batches")
            ax2.set_ylabel("Total Solvent Usage (kg)")
            ax2.grid(
                True,
                linestyle="--",
                linewidth=0.6,
                alpha=0.4,
            )

            ax2.text(
                0.02,
                0.98,
                "Bubble size: Weighted solvent ratio",
                transform=ax2.transAxes,
                va="top",
                fontsize=9,
            )

            for spine in ax2.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(1.0)

            fig2.tight_layout()
            st.pyplot(fig2, use_container_width=True)
            plt.close(fig2)

        st.markdown(f"#### Ranking Table — {ranking_mode}")

        priority_display = prepare_priority_display(
            top_ranked
        )

        st.dataframe(
            priority_display,
            use_container_width=True,
            hide_index=True,
        )

        if not priority_summary.empty:
            top_opportunity = priority_summary.iloc[0]

            st.markdown("#### Improvement Recommendation")

            st.info(
                f"Paint code **{top_opportunity['Paint_Code']}** "
                f"(Vendor: **{top_opportunity['Vendor']}**; "
                f"Resin: **{top_opportunity['Resin']}**; "
                f"Position: **{top_opportunity['Position_UI']}**) "
                f"has **{int(top_opportunity['Historical_Batches'])} historical batches**, "
                f"**{top_opportunity['Total_Solvent_kg']:,.0f} kg** total solvent usage, "
                f"and a weighted solvent ratio of "
                f"**{top_opportunity['Weighted_Ratio_Percent']:.2f}%**. "
                f"It should be reviewed first with the supplier for delivery-viscosity improvement."
            )

        full_priority_display = prepare_priority_display(
            priority_summary
        )

        csv_data = full_priority_display.to_csv(
            index=False,
            encoding="utf-8-sig",
        ).encode("utf-8-sig")

        st.download_button(
            label="📥 Download Full Priority Table",
            data=csv_data,
            file_name="Solvent_Reduction_Priority.csv",
            mime="text/csv",
            key="download_priority_csv",
        )


# =========================================================
# TAB 2: PAINT CODE DETAILS
# =========================================================
with tab_detail:
    st.subheader("2. Paint Code Details")

    st.caption(
        "Select a paint code to review its coating position, production lines, "
        "solvent type, historical addition amount, and viscosity performance."
    )

    st.markdown("#### Paint Code Selection")

    d1, d2, d3, d4, d5 = st.columns(5)

    with d1:
        detail_vendor = st.selectbox(
            "Vendor",
            options=clean_options(df["Vendor"]),
            key="detail_vendor",
        )

    detail_filter_df = df[
        df["Vendor"] == detail_vendor
    ].copy()

    with d2:
        detail_resin = st.selectbox(
            "Resin Type",
            options=clean_options(
                detail_filter_df["Resin"]
            ),
            key="detail_resin",
        )

    detail_filter_df = detail_filter_df[
        detail_filter_df["Resin"] == detail_resin
    ].copy()

    with d3:
        detail_position = st.selectbox(
            "Coating Position",
            options=clean_options(
                detail_filter_df["Position_UI"]
            ),
            key="detail_position",
        )

    detail_filter_df = detail_filter_df[
        detail_filter_df["Position_UI"]
        == detail_position
    ].copy()

    with d4:
        detail_solvent = st.selectbox(
            "Solvent Type",
            options=clean_options(
                detail_filter_df["Solvent_Type"]
            ),
            key="detail_solvent",
        )

    detail_filter_df = detail_filter_df[
        detail_filter_df["Solvent_Type"]
        == detail_solvent
    ].copy()

    with d5:
        detail_paint_code = st.selectbox(
            "Paint Code",
            options=clean_options(
                detail_filter_df["Paint_Code"]
            ),
            key="detail_paint_code",
        )

    detail_df = detail_filter_df[
        detail_filter_df["Paint_Code"]
        == detail_paint_code
    ].copy()

    if detail_df.empty:
        st.warning("⚠️ No records match the selected paint-code condition.")
    else:
        detail_records = len(detail_df)
        detail_batches = distinct_batch_count(
            detail_df["Batch_ID"]
        )

        detail_lines = detail_df.loc[
            detail_df["線別"] != "Unknown",
            "線別",
        ].nunique()

        detail_total_paint = detail_df["塗料重量"].sum()
        detail_total_solvent = detail_df["添加重量"].sum()

        detail_weighted_ratio = (
            detail_total_solvent
            / detail_total_paint
            * 100
            if detail_total_paint > 0
            else np.nan
        )

        median_before = detail_df["黏度(秒)"].median()
        median_after = detail_df["黏度(秒)_1"].median()
        median_delta = detail_df["Delta_V"].median()
        median_efficiency = (
            detail_df["Viscosity_Sensitivity"].median()
        )

        median_solvent = detail_df["添加重量"].median()
        median_paint = detail_df["塗料重量"].median()

        after_viscosity_range = percentile_range(
            detail_df["黏度(秒)_1"]
        )

        ratio_range = percentile_range(
            detail_df["Solvent_Ratio_Percent"]
        )

        kpi_row1 = st.columns(5)

        kpi_row1[0].metric(
            "Adjustment Records",
            f"{detail_records:,}",
        )

        kpi_row1[1].metric(
            "Historical Batches",
            f"{detail_batches:,}",
        )

        kpi_row1[2].metric(
            "Production Lines",
            f"{detail_lines:,}",
        )

        kpi_row1[3].metric(
            "Total Solvent",
            safe_metric(
                detail_total_solvent,
                0,
                " kg",
            ),
        )

        kpi_row1[4].metric(
            "Weighted Ratio",
            safe_metric(
                detail_weighted_ratio,
                2,
                "%",
            ),
        )

        kpi_row2 = st.columns(5)

        kpi_row2[0].metric(
            "Reference Paint Weight",
            safe_metric(
                median_paint,
                1,
                " kg",
            ),
        )

        kpi_row2[1].metric(
            "Reference Solvent Addition",
            safe_metric(
                median_solvent,
                1,
                " kg",
            ),
        )

        kpi_row2[2].metric(
            "Median Before Viscosity",
            safe_metric(
                median_before,
                1,
                " s",
            ),
        )

        kpi_row2[3].metric(
            "Median After Viscosity",
            safe_metric(
                median_after,
                1,
                " s",
            ),
        )

        kpi_row2[4].metric(
            "Median Dilution Efficiency",
            safe_metric(
                median_efficiency,
                2,
                " s/%",
            ),
        )

        st.markdown("---")

        st.markdown("#### Historical Reference")

        reference_col1, reference_col2, reference_col3 = st.columns(3)

        reference_col1.info(
            f"**After-viscosity P10–P90**\n\n"
            f"{after_viscosity_range} s"
        )

        reference_col2.info(
            f"**Solvent-ratio P10–P90**\n\n"
            f"{ratio_range}%"
        )

        reference_col3.info(
            f"**Median viscosity drop**\n\n"
            f"{median_delta:.1f} s"
        )

        st.caption(
            "The historical after-viscosity range is a production reference only. "
            "Before setting a supplier delivery-viscosity specification, confirm "
            "measurement temperature, method, coating position, and product requirements."
        )

        detail_chart_col1, detail_chart_col2 = st.columns(2)

        with detail_chart_col1:
            st.markdown("#### Before Viscosity vs Solvent Ratio")

            fig3, ax3 = plt.subplots(
                figsize=(8.5, 5.5),
                dpi=150,
            )

            line_values = clean_options(
                detail_df["線別"]
            )

            if not line_values:
                ax3.scatter(
                    detail_df["黏度(秒)"],
                    detail_df["Solvent_Ratio_Percent"],
                    alpha=0.7,
                )
            else:
                for line in line_values:
                    line_data = detail_df[
                        detail_df["線別"] == line
                    ]

                    ax3.scatter(
                        line_data["黏度(秒)"],
                        line_data["Solvent_Ratio_Percent"],
                        label=line,
                        alpha=0.7,
                    )

                ax3.legend(
                    title="Production Line",
                    fontsize=8,
                    title_fontsize=9,
                )

            ax3.set_xlabel("Before Viscosity (s)")
            ax3.set_ylabel("Solvent Ratio (%)")
            ax3.grid(
                True,
                linestyle="--",
                linewidth=0.6,
                alpha=0.4,
            )

            for spine in ax3.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(1.0)

            fig3.tight_layout()
            st.pyplot(fig3, use_container_width=True)
            plt.close(fig3)

        with detail_chart_col2:
            st.markdown("#### Solvent Usage by Production Line")

            line_usage = detail_df.groupby(
                "線別",
                observed=False,
            ).agg(
                Total_Solvent_kg=("添加重量", "sum"),
                Total_Paint_kg=("塗料重量", "sum"),
                Records=("Paint_Code", "size"),
            ).reset_index()

            line_usage["Weighted_Ratio_Percent"] = np.where(
                line_usage["Total_Paint_kg"] > 0,
                line_usage["Total_Solvent_kg"]
                / line_usage["Total_Paint_kg"]
                * 100,
                np.nan,
            )

            line_usage = line_usage.sort_values(
                "Total_Solvent_kg",
                ascending=True,
            )

            fig4, ax4 = plt.subplots(
                figsize=(8.5, 5.5),
                dpi=150,
            )

            ax4.barh(
                line_usage["線別"],
                line_usage["Total_Solvent_kg"],
            )

            for index, row in line_usage.reset_index(
                drop=True
            ).iterrows():
                ax4.text(
                    row["Total_Solvent_kg"],
                    index,
                    (
                        f" {row['Total_Solvent_kg']:,.0f} kg"
                        f" | {row['Weighted_Ratio_Percent']:.1f}%"
                    ),
                    va="center",
                    fontsize=8,
                )

            ax4.set_xlabel("Total Solvent Usage (kg)")
            ax4.set_ylabel("Production Line")
            ax4.grid(
                axis="x",
                linestyle="--",
                linewidth=0.6,
                alpha=0.4,
            )

            for spine in ax4.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(1.0)

            fig4.tight_layout()
            st.pyplot(fig4, use_container_width=True)
            plt.close(fig4)

        st.markdown("#### Solvent Reduction Simulation")

        simulation_col1, simulation_col2 = st.columns(2)

        with simulation_col1:
            reduction_rate = st.select_slider(
                "Expected Reduction Rate",
                options=[5, 10, 15, 20, 25, 30],
                value=10,
                format_func=lambda x: f"{x}%",
                key="detail_reduction_rate",
            )

        with simulation_col2:
            solvent_unit_price = st.number_input(
                "Solvent Unit Price per kg (optional)",
                min_value=0.0,
                value=0.0,
                step=1.0,
                key="detail_solvent_price",
            )

        estimated_reduction_kg = (
            detail_total_solvent
            * reduction_rate
            / 100
        )

        estimated_saving = (
            estimated_reduction_kg
            * solvent_unit_price
        )

        sim1, sim2, sim3 = st.columns(3)

        sim1.metric(
            "Historical Total Solvent",
            safe_metric(
                detail_total_solvent,
                0,
                " kg",
            ),
        )

        sim2.metric(
            f"Estimated Reduction ({reduction_rate}%)",
            safe_metric(
                estimated_reduction_kg,
                0,
                " kg",
            ),
        )

        sim3.metric(
            "Estimated Cost Saving",
            (
                safe_metric(
                    estimated_saving,
                    0,
                )
                if solvent_unit_price > 0
                else "Enter unit price"
            ),
        )

        with st.expander("View Historical Detail Records"):
            detail_columns = [
                "Vendor",
                "Resin",
                "Position_UI",
                "Paint_Code",
                "線別",
                "Solvent_Type",
                "塗料批號",
                "塗料重量",
                "添加重量",
                "Solvent_Ratio_Percent",
                "黏度(秒)",
                "黏度(秒)_1",
                "Delta_V",
                "Viscosity_Sensitivity",
            ]

            detail_display = detail_df[
                detail_columns
            ].copy()

            detail_display.columns = [
                "Vendor",
                "Resin Type",
                "Coating Position",
                "Paint Code",
                "Production Line",
                "Solvent Type",
                "Paint Batch",
                "Paint Weight (kg)",
                "Solvent Added (kg)",
                "Solvent Ratio (%)",
                "Before Viscosity (s)",
                "After Viscosity (s)",
                "Viscosity Drop (s)",
                "Dilution Efficiency (s/%)",
            ]

            numeric_cols_detail = [
                "Paint Weight (kg)",
                "Solvent Added (kg)",
                "Solvent Ratio (%)",
                "Before Viscosity (s)",
                "After Viscosity (s)",
                "Viscosity Drop (s)",
                "Dilution Efficiency (s/%)",
            ]

            for col in numeric_cols_detail:
                detail_display[col] = (
                    pd.to_numeric(
                        detail_display[col],
                        errors="coerce",
                    ).round(2)
                )

            st.dataframe(
                detail_display,
                use_container_width=True,
                hide_index=True,
            )


# =========================================================
# TAB 3: PRODUCTION LINE COMPARISON
# =========================================================
with tab_line:
    st.subheader("3. Production Line Comparison")

    st.caption(
        "The system automatically identifies paint-code conditions used on "
        "at least two production lines, ranks them, and allows one-click comparison."
    )

    st.markdown("#### Automatic Screening Filters")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        compare_vendor = select_all_filter(
            "Vendor",
            df,
            "Vendor",
            "compare_vendor",
        )

    compare_df = apply_filter(
        df,
        "Vendor",
        compare_vendor,
    )

    with c2:
        compare_resin = select_all_filter(
            "Resin Type",
            compare_df,
            "Resin",
            "compare_resin",
        )

    compare_df = apply_filter(
        compare_df,
        "Resin",
        compare_resin,
    )

    with c3:
        compare_position = select_all_filter(
            "Coating Position",
            compare_df,
            "Position_UI",
            "compare_position",
        )

    compare_df = apply_filter(
        compare_df,
        "Position_UI",
        compare_position,
    )

    with c4:
        minimum_records = st.number_input(
            "Minimum Records per Line",
            min_value=1,
            max_value=30,
            value=3,
            step=1,
            key="compare_minimum_records",
        )

    candidates, line_level = build_line_comparison_candidates(
        compare_df,
        min_records_per_line=minimum_records,
    )

    if candidates.empty:
        st.warning(
            "⚠️ No comparable paint-code condition was found. "
            "Try selecting All filters or reducing the minimum records per line."
        )
    else:
        screening_display = candidates[
            [
                "Vendor",
                "Resin",
                "Position_UI",
                "Paint_Code",
                "Solvent_Type",
                "Production_Lines",
                "Total_Records",
                "Total_Batches",
                "Total_Solvent_kg",
                "Ratio_Difference",
                "Before_Viscosity_Difference",
                "After_Viscosity_Difference",
                "Comparison_Score",
            ]
        ].copy()

        screening_display.columns = [
            "Vendor",
            "Resin Type",
            "Coating Position",
            "Paint Code",
            "Solvent Type",
            "Production Lines",
            "Total Records",
            "Total Batches",
            "Total Solvent (kg)",
            "Max Ratio Difference (%-pt)",
            "Max Before-Viscosity Difference (s)",
            "Max After-Viscosity Difference (s)",
            "Comparison Score",
        ]

        numeric_screening_cols = [
            "Total Solvent (kg)",
            "Max Ratio Difference (%-pt)",
            "Max Before-Viscosity Difference (s)",
            "Max After-Viscosity Difference (s)",
            "Comparison Score",
        ]

        for col in numeric_screening_cols:
            screening_display[col] = pd.to_numeric(
                screening_display[col],
                errors="coerce",
            ).round(2)

        st.markdown("#### Automatically Ranked Comparison Opportunities")

        st.dataframe(
            screening_display.head(30),
            use_container_width=True,
            hide_index=True,
        )

        selected_condition = st.selectbox(
            "Select Comparison Condition",
            options=candidates["Condition_Label"].tolist(),
            key="auto_line_condition",
        )

        selected_row = candidates[
            candidates["Condition_Label"]
            == selected_condition
        ].iloc[0]

        condition_mask = (
            (line_level["Vendor"] == selected_row["Vendor"])
            & (line_level["Resin"] == selected_row["Resin"])
            & (
                line_level["Position_UI"]
                == selected_row["Position_UI"]
            )
            & (
                line_level["Paint_Code"]
                == selected_row["Paint_Code"]
            )
            & (
                line_level["Solvent_Type"]
                == selected_row["Solvent_Type"]
            )
        )

        selected_line_summary = line_level[
            condition_mask
        ].copy()

        selected_line_summary = selected_line_summary.sort_values(
            "線別"
        ).reset_index(drop=True)

        number_of_lines = selected_line_summary[
            "線別"
        ].nunique()

        k1, k2, k3, k4 = st.columns(4)

        k1.metric(
            "Production Lines",
            f"{number_of_lines:,}",
        )

        k2.metric(
            "Total Records",
            f"{int(selected_line_summary['Records'].sum()):,}",
        )

        k3.metric(
            "Total Solvent",
            safe_metric(
                selected_line_summary[
                    "Total_Solvent_kg"
                ].sum(),
                0,
                " kg",
            ),
        )

        overall_line_ratio = (
            selected_line_summary[
                "Total_Solvent_kg"
            ].sum()
            / selected_line_summary[
                "Total_Paint_kg"
            ].sum()
            * 100
            if selected_line_summary[
                "Total_Paint_kg"
            ].sum() > 0
            else np.nan
        )

        k4.metric(
            "Overall Weighted Ratio",
            safe_metric(
                overall_line_ratio,
                2,
                "%",
            ),
        )

        st.markdown("---")

        chart1, chart2 = st.columns(2)

        with chart1:
            st.markdown("#### Before vs After Viscosity by Line")

            fig5, ax5 = plt.subplots(
                figsize=(8.5, 5.8),
                dpi=150,
            )

            x_positions = np.arange(
                len(selected_line_summary)
            )

            before_values = (
                selected_line_summary["Median_Before"]
                .to_numpy()
            )

            after_values = (
                selected_line_summary["Median_After"]
                .to_numpy()
            )

            for index in range(
                len(selected_line_summary)
            ):
                ax5.plot(
                    [index, index],
                    [
                        after_values[index],
                        before_values[index],
                    ],
                    linewidth=2,
                    alpha=0.65,
                )

            ax5.scatter(
                x_positions,
                before_values,
                marker="o",
                s=80,
                label="Before Viscosity",
            )

            ax5.scatter(
                x_positions,
                after_values,
                marker="s",
                s=80,
                label="After Viscosity",
            )

            for index, value in enumerate(before_values):
                ax5.annotate(
                    f"{value:.1f}",
                    (index, value),
                    xytext=(0, 8),
                    textcoords="offset points",
                    ha="center",
                    fontsize=8,
                )

            for index, value in enumerate(after_values):
                ax5.annotate(
                    f"{value:.1f}",
                    (index, value),
                    xytext=(0, -14),
                    textcoords="offset points",
                    ha="center",
                    fontsize=8,
                )

            ax5.set_xticks(x_positions)
            ax5.set_xticklabels(
                selected_line_summary["線別"],
            )

            ax5.set_xlabel("Production Line")
            ax5.set_ylabel("Median Viscosity (s)")
            ax5.legend()
            ax5.grid(
                axis="y",
                linestyle="--",
                linewidth=0.6,
                alpha=0.4,
            )

            for spine in ax5.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(1.0)

            fig5.tight_layout()
            st.pyplot(fig5, use_container_width=True)
            plt.close(fig5)

        with chart2:
            st.markdown("#### Weighted Solvent Ratio by Line")

            ratio_chart_df = selected_line_summary.sort_values(
                "Weighted_Ratio",
                ascending=True,
            )

            fig6, ax6 = plt.subplots(
                figsize=(8.5, 5.8),
                dpi=150,
            )

            ax6.barh(
                ratio_chart_df["線別"],
                ratio_chart_df["Weighted_Ratio"],
            )

            for index, row in ratio_chart_df.reset_index(
                drop=True
            ).iterrows():
                ax6.text(
                    row["Weighted_Ratio"],
                    index,
                    (
                        f" {row['Weighted_Ratio']:.2f}%"
                        f" | {row['Total_Solvent_kg']:,.0f} kg"
                    ),
                    va="center",
                    fontsize=8,
                )

            ax6.set_xlabel("Weighted Solvent Ratio (%)")
            ax6.set_ylabel("Production Line")
            ax6.grid(
                axis="x",
                linestyle="--",
                linewidth=0.6,
                alpha=0.4,
            )

            for spine in ax6.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(1.0)

            fig6.tight_layout()
            st.pyplot(fig6, use_container_width=True)
            plt.close(fig6)

        st.markdown("#### Production Line Comparison Table")

        comparison_display = selected_line_summary[
            [
                "線別",
                "Records",
                "Batches",
                "Total_Paint_kg",
                "Total_Solvent_kg",
                "Median_Paint_kg",
                "Median_Solvent_kg",
                "Weighted_Ratio",
                "Median_Before",
                "Median_After",
                "Median_Delta",
                "Median_Efficiency",
            ]
        ].copy()

        comparison_display.columns = [
            "Production Line",
            "Records",
            "Batches",
            "Total Paint (kg)",
            "Total Solvent (kg)",
            "Reference Paint Weight (kg)",
            "Reference Solvent Addition (kg)",
            "Weighted Ratio (%)",
            "Median Before Viscosity (s)",
            "Median After Viscosity (s)",
            "Median Viscosity Drop (s)",
            "Median Dilution Efficiency (s/%)",
        ]

        numeric_compare_cols = [
            "Total Paint (kg)",
            "Total Solvent (kg)",
            "Reference Paint Weight (kg)",
            "Reference Solvent Addition (kg)",
            "Weighted Ratio (%)",
            "Median Before Viscosity (s)",
            "Median After Viscosity (s)",
            "Median Viscosity Drop (s)",
            "Median Dilution Efficiency (s/%)",
        ]

        for col in numeric_compare_cols:
            comparison_display[col] = pd.to_numeric(
                comparison_display[col],
                errors="coerce",
            ).round(2)

        st.dataframe(
            comparison_display,
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### Automatic Interpretation")

        highest_ratio_row = selected_line_summary.loc[
            selected_line_summary[
                "Weighted_Ratio"
            ].idxmax()
        ]

        lowest_ratio_row = selected_line_summary.loc[
            selected_line_summary[
                "Weighted_Ratio"
            ].idxmin()
        ]

        ratio_difference = (
            highest_ratio_row["Weighted_Ratio"]
            - lowest_ratio_row["Weighted_Ratio"]
        )

        before_difference = (
            selected_line_summary["Median_Before"].max()
            - selected_line_summary["Median_Before"].min()
        )

        after_difference = (
            selected_line_summary["Median_After"].max()
            - selected_line_summary["Median_After"].min()
        )

        st.write(
            f"The highest weighted solvent ratio is on "
            f"**{highest_ratio_row['線別']}** "
            f"({highest_ratio_row['Weighted_Ratio']:.2f}%), "
            f"while the lowest is on "
            f"**{lowest_ratio_row['線別']}** "
            f"({lowest_ratio_row['Weighted_Ratio']:.2f}%). "
            f"The difference is **{ratio_difference:.2f} percentage points**."
        )

        st.write(
            f"The maximum difference in median before viscosity is "
            f"**{before_difference:.1f} s**, and the maximum difference "
            f"in median after viscosity is **{after_difference:.1f} s**."
        )

        all_lines_high_ratio = (
            selected_line_summary["Weighted_Ratio"].min()
            >= 10
        )

        if ratio_difference <= 2 and all_lines_high_ratio:
            st.success(
                "All production lines show consistently high solvent addition "
                "with only a small line-to-line difference. Supplier delivery "
                "viscosity should be reviewed as the first improvement target."
            )

        elif ratio_difference <= 2:
            st.info(
                "Solvent addition is similar across production lines. "
                "The difference between lines is limited."
            )

        elif before_difference >= 10:
            st.info(
                "Incoming viscosity differs clearly between production lines. "
                "The solvent-usage difference may be related to incoming viscosity "
                "or measurement conditions. Supplier conclusions should not be made yet."
            )

        else:
            st.warning(
                "The production lines show a noticeable solvent-ratio difference "
                "despite similar incoming viscosity. Review line operating conditions, "
                "measurement methods, and line-specific viscosity requirements first."
            )
