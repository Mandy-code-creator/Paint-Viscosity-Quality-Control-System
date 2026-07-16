
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
    layout="wide",
)

st.title("🎨 Paint Viscosity Improvement & Solvent Reduction")

st.markdown(
    """
    This module identifies paint codes that are frequently used and consume
    large amounts of solvent. All analyses below follow one common filter set.
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
# 3. LOAD GROUP A DATA
# =========================================================
if not st.session_state.get("raw_data_loaded", False):
    st.warning(
        "⚠️ Please return to the Main App page and upload the raw data first."
    )
    st.stop()

group_a = st.session_state.get("group_a_data")

if group_a is None or group_a.empty:
    st.warning("⚠️ No valid Group A data are available for analysis.")
    st.stop()

df = group_a.copy()


# =========================================================
# 4. REQUIRED COLUMNS
# =========================================================
text_columns = [
    "Vendor",
    "Resin",
    "Solvent_Type",
    "塗料批號",
    "線別",
    "塗裝位置",
]

numeric_columns = [
    "塗料重量",
    "添加重量",
    "黏度(秒)",
    "黏度(秒)_1",
]

for col in text_columns:
    if col not in df.columns:
        df[col] = "Unknown"

for col in numeric_columns:
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
# 5. NORMALIZE TEXT
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

for col in [
    "Vendor",
    "Resin",
    "Paint_Code",
    "Solvent_Type",
    "塗料批號",
    "線別",
    "塗裝位置",
]:
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
        col,
    ] = "Unknown"

df["Batch_ID"] = df["塗料批號"].copy()


# =========================================================
# 6. COATING POSITION
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
    "Position_UI",
] = "Unknown"


# =========================================================
# 7. NUMERIC CLEANING & CALCULATIONS
# =========================================================
for col in numeric_columns:
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
# 8. DATE COLUMN DETECTION
# =========================================================
DATE_CANDIDATES = [
    "攪拌日期",
    "調整日期",
    "生產日期",
    "日期",
    "Date",
    "date",
    "DATE",
]

date_column = next(
    (col for col in DATE_CANDIDATES if col in df.columns),
    None,
)

if date_column is not None:
    df["_Analysis_Date"] = pd.to_datetime(
        df[date_column],
        errors="coerce",
    )
else:
    df["_Analysis_Date"] = pd.NaT


# =========================================================
# 9. HELPER FUNCTIONS
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


def valid_batch_count(series):
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


def safe_metric(value, decimals=1, suffix=""):
    if value is None or pd.isna(value):
        return "-"

    return f"{value:,.{decimals}f}{suffix}"


def format_range(series, low=0.10, high=0.90):
    valid = pd.to_numeric(series, errors="coerce").dropna()

    if valid.empty:
        return "-"

    lower = valid.quantile(low)
    upper = valid.quantile(high)

    if np.isclose(lower, upper):
        return f"{lower:.1f}"

    return f"{lower:.1f} – {upper:.1f}"


def select_all(label, source_df, column, key):
    options = ["All"] + clean_options(source_df[column])

    current_value = st.session_state.get(key, "All")

    if current_value not in options:
        st.session_state[key] = "All"

    return st.selectbox(
        label,
        options=options,
        key=key,
    )


def apply_single_filter(source_df, column, value):
    if value == "All":
        return source_df.copy()

    return source_df[
        source_df[column].astype(str) == str(value)
    ].copy()


def build_paint_code_summary(source_df):
    if source_df.empty:
        return pd.DataFrame()

    group_cols = [
        "Vendor",
        "Resin",
        "Position_UI",
        "Paint_Code",
        "Solvent_Type",
    ]

    summary = source_df.groupby(
        group_cols,
        observed=False,
        dropna=False,
    ).agg(
        Adjustment_Records=("Paint_Code", "size"),
        Historical_Batches=("Batch_ID", valid_batch_count),
        Production_Lines=("線別", lambda x: x[x != "Unknown"].nunique()),
        Total_Paint_kg=("塗料重量", "sum"),
        Total_Solvent_kg=("添加重量", "sum"),
        Median_Paint_kg=("塗料重量", "median"),
        Median_Solvent_kg=("添加重量", "median"),
        Median_Ratio_Percent=("Solvent_Ratio_Percent", "median"),
        Median_Before_Viscosity=("黏度(秒)", "median"),
        Median_After_Viscosity=("黏度(秒)_1", "median"),
        Median_Viscosity_Drop=("Delta_V", "median"),
        Median_Dilution_Efficiency=("Viscosity_Sensitivity", "median"),
    ).reset_index()

    summary["Weighted_Ratio_Percent"] = np.where(
        summary["Total_Paint_kg"] > 0,
        summary["Total_Solvent_kg"]
        / summary["Total_Paint_kg"]
        * 100,
        np.nan,
    )

    return summary


def build_line_summary(source_df):
    if source_df.empty:
        return pd.DataFrame()

    line_summary = source_df.groupby(
        "線別",
        observed=False,
        dropna=False,
    ).agg(
        Adjustment_Records=("Paint_Code", "size"),
        Historical_Batches=("Batch_ID", valid_batch_count),
        Total_Paint_kg=("塗料重量", "sum"),
        Total_Solvent_kg=("添加重量", "sum"),
        Median_Paint_kg=("塗料重量", "median"),
        Median_Solvent_kg=("添加重量", "median"),
        Median_Before_Viscosity=("黏度(秒)", "median"),
        Median_After_Viscosity=("黏度(秒)_1", "median"),
        Median_Viscosity_Drop=("Delta_V", "median"),
        Median_Dilution_Efficiency=("Viscosity_Sensitivity", "median"),
    ).reset_index()

    line_summary["Weighted_Ratio_Percent"] = np.where(
        line_summary["Total_Paint_kg"] > 0,
        line_summary["Total_Solvent_kg"]
        / line_summary["Total_Paint_kg"]
        * 100,
        np.nan,
    )

    return line_summary.sort_values("線別").reset_index(drop=True)


def analysis_period_text(source_df):
    valid_dates = source_df["_Analysis_Date"].dropna()

    if valid_dates.empty:
        return "All available data"

    min_date = valid_dates.min().strftime("%Y/%m/%d")
    max_date = valid_dates.max().strftime("%Y/%m/%d")

    return f"{min_date} – {max_date}"


# =========================================================
# 10. GLOBAL FILTERS — APPLIED ONCE
# =========================================================
st.markdown("---")
st.subheader("Global Analysis Filters")

filter_df = df.copy()

# -------------------------
# Date filter
# -------------------------
if filter_df["_Analysis_Date"].notna().any():
    min_date = filter_df["_Analysis_Date"].min().date()
    max_date = filter_df["_Analysis_Date"].max().date()

    selected_dates = st.date_input(
        "Analysis Period",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key="global_analysis_period",
    )

    if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
        start_date, end_date = selected_dates

        filter_df = filter_df[
            filter_df["_Analysis_Date"].dt.date.between(
                start_date,
                end_date,
                inclusive="both",
            )
        ].copy()
else:
    st.info(
        "No recognized date column was found. "
        "All available records will be analyzed."
    )

# -------------------------
# Cascading common filters
# -------------------------
g1, g2, g3 = st.columns(3)

with g1:
    selected_vendor = select_all(
        "Vendor",
        filter_df,
        "Vendor",
        "global_vendor",
    )

filter_df = apply_single_filter(
    filter_df,
    "Vendor",
    selected_vendor,
)

with g2:
    selected_resin = select_all(
        "Resin Type",
        filter_df,
        "Resin",
        "global_resin",
    )

filter_df = apply_single_filter(
    filter_df,
    "Resin",
    selected_resin,
)

with g3:
    selected_position = select_all(
        "Coating Position",
        filter_df,
        "Position_UI",
        "global_position",
    )

filter_df = apply_single_filter(
    filter_df,
    "Position_UI",
    selected_position,
)

g4, g5 = st.columns(2)

with g4:
    selected_solvent = select_all(
        "Solvent Type",
        filter_df,
        "Solvent_Type",
        "global_solvent",
    )

filter_df = apply_single_filter(
    filter_df,
    "Solvent_Type",
    selected_solvent,
)

with g5:
    line_options = clean_options(filter_df["線別"])

    previous_lines = st.session_state.get(
        "global_lines",
        line_options,
    )

    valid_previous_lines = [
        line for line in previous_lines
        if line in line_options
    ]

    if not valid_previous_lines:
        valid_previous_lines = line_options

    selected_lines = st.multiselect(
        "Production Line",
        options=line_options,
        default=valid_previous_lines,
        key="global_lines",
    )

if selected_lines:
    filter_df = filter_df[
        filter_df["線別"].isin(selected_lines)
    ].copy()
else:
    filter_df = filter_df.iloc[0:0].copy()

if filter_df.empty:
    st.warning("⚠️ No records match the global analysis filters.")
    st.stop()


# =========================================================
# 11. FILTER SUMMARY
# =========================================================
period_label = analysis_period_text(filter_df)

summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)

summary_col1.metric(
    "Analysis Period",
    period_label,
)

summary_col2.metric(
    "Records Included",
    f"{len(filter_df):,}",
)

summary_col3.metric(
    "Paint Codes Included",
    f"{filter_df['Paint_Code'].nunique():,}",
)

summary_col4.metric(
    "Production Lines Included",
    f"{filter_df['線別'].nunique():,}",
)

st.caption(
    "All tabs below use this same filtered dataset. "
    "No additional Vendor, Resin, Position, Solvent, Line, or Date filters are applied later."
)


# =========================================================
# 12. MAIN TABS
# =========================================================
tab_ranking, tab_detail, tab_line = st.tabs([
    "1. Paint Code Ranking",
    "2. Paint Code Details",
    "3. Production Line Comparison",
])


# =========================================================
# TAB 1 — PAINT CODE RANKING
# =========================================================
with tab_ranking:
    st.subheader("1. Paint Code Solvent Consumption Ranking")

    st.caption(
        f"Analysis Period: {period_label} | "
        f"Records Included: {len(filter_df):,}"
    )

    summary_df = build_paint_code_summary(filter_df)

    if summary_df.empty:
        st.warning("⚠️ No paint-code summary can be generated.")
    else:
        total_paint = summary_df["Total_Paint_kg"].sum()
        total_solvent = summary_df["Total_Solvent_kg"].sum()

        overall_weighted_ratio = (
            total_solvent / total_paint * 100
            if total_paint > 0
            else np.nan
        )

        k1, k2, k3, k4 = st.columns(4)

        k1.metric(
            "Paint Codes",
            f"{summary_df['Paint_Code'].nunique():,}",
        )

        k2.metric(
            "Historical Batches",
            f"{int(summary_df['Historical_Batches'].sum()):,}",
        )

        k3.metric(
            "Total Solvent Usage",
            safe_metric(total_solvent, 0, " kg"),
        )

        k4.metric(
            "Overall Weighted Ratio",
            safe_metric(overall_weighted_ratio, 2, "%"),
        )

        ranking_mode = st.radio(
            "Ranking Method",
            options=[
                "Highest Total Solvent Usage",
                "Most Frequently Used",
                "Highest Weighted Solvent Ratio",
            ],
            horizontal=True,
            key="ranking_mode",
        )

        if ranking_mode == "Most Frequently Used":
            ranked_df = summary_df.sort_values(
                by=[
                    "Historical_Batches",
                    "Adjustment_Records",
                    "Total_Solvent_kg",
                ],
                ascending=[False, False, False],
            ).copy()

        elif ranking_mode == "Highest Weighted Solvent Ratio":
            ranked_df = summary_df.sort_values(
                by=[
                    "Weighted_Ratio_Percent",
                    "Historical_Batches",
                    "Total_Solvent_kg",
                ],
                ascending=[False, False, False],
            ).copy()

        else:
            ranked_df = summary_df.sort_values(
                by=[
                    "Total_Solvent_kg",
                    "Historical_Batches",
                    "Weighted_Ratio_Percent",
                ],
                ascending=[False, False, False],
            ).copy()

        ranked_df = ranked_df.reset_index(drop=True)
        ranked_df.insert(
            0,
            "Rank",
            np.arange(1, len(ranked_df) + 1),
        )

        max_top_n = max(1, min(30, len(ranked_df)))

        top_n = st.slider(
            "Number of paint codes to display",
            min_value=1,
            max_value=max_top_n,
            value=min(15, max_top_n),
            step=1,
            key="ranking_top_n",
        )

        top_df = ranked_df.head(top_n).copy()

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            chart_df = top_df.sort_values(
                "Total_Solvent_kg",
                ascending=True,
            )

            fig1, ax1 = plt.subplots(
                figsize=(9, max(5, len(chart_df) * 0.42)),
                dpi=150,
            )

            labels = (
                chart_df["Paint_Code"]
                + " | "
                + chart_df["Vendor"]
            )

            ax1.barh(
                labels,
                chart_df["Total_Solvent_kg"],
            )

            for index, value in enumerate(
                chart_df["Total_Solvent_kg"]
            ):
                ax1.text(
                    value,
                    index,
                    f" {value:,.0f} kg",
                    va="center",
                    fontsize=8,
                )

            ax1.set_title(
                "Total Solvent Usage by Paint Code",
                loc="left",
                fontweight="bold",
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
            fig2, ax2 = plt.subplots(
                figsize=(9, 6),
                dpi=150,
            )

            size_values = (
                summary_df["Weighted_Ratio_Percent"]
                .fillna(0)
                .clip(lower=0)
            )

            if size_values.max() > 0:
                marker_sizes = (
                    size_values / size_values.max() * 500
                ) + 50
            else:
                marker_sizes = np.full(
                    len(summary_df),
                    80,
                )

            ax2.scatter(
                summary_df["Historical_Batches"],
                summary_df["Total_Solvent_kg"],
                s=marker_sizes,
                alpha=0.65,
            )

            label_df = (
                summary_df
                .sort_values(
                    "Total_Solvent_kg",
                    ascending=False,
                )
                .head(min(10, len(summary_df)))
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

            ax2.set_title(
                "Usage Frequency vs Total Solvent",
                loc="left",
                fontweight="bold",
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

        display_df = top_df[
            [
                "Rank",
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
                "Median_Solvent_kg",
                "Weighted_Ratio_Percent",
                "Median_Before_Viscosity",
                "Median_After_Viscosity",
            ]
        ].copy()

        display_df.columns = [
            "Rank",
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
            "Median Solvent Added (kg)",
            "Weighted Solvent Ratio (%)",
            "Median Before Viscosity (s)",
            "Median After Viscosity (s)",
        ]

        numeric_display_cols = [
            "Total Paint (kg)",
            "Total Solvent (kg)",
            "Median Solvent Added (kg)",
            "Weighted Solvent Ratio (%)",
            "Median Before Viscosity (s)",
            "Median After Viscosity (s)",
        ]

        for col in numeric_display_cols:
            display_df[col] = pd.to_numeric(
                display_df[col],
                errors="coerce",
            ).round(2)

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
        )

        csv_data = ranked_df.to_csv(
            index=False,
            encoding="utf-8-sig",
        ).encode("utf-8-sig")

        st.download_button(
            label="📥 Download Full Paint Code Ranking",
            data=csv_data,
            file_name="Paint_Code_Solvent_Ranking.csv",
            mime="text/csv",
            key="download_ranking_csv",
        )


# =========================================================
# TAB 2 — PAINT CODE DETAILS
# =========================================================
with tab_detail:
    st.subheader("2. Paint Code Details")

    st.caption(
        f"Analysis Period: {period_label} | "
        f"Records Included: {len(filter_df):,}"
    )

    paint_code_options = clean_options(
        filter_df["Paint_Code"]
    )

    selected_paint_code = st.selectbox(
        "Select Paint Code",
        options=paint_code_options,
        key="detail_paint_code",
    )

    detail_df = filter_df[
        filter_df["Paint_Code"] == selected_paint_code
    ].copy()

    if detail_df.empty:
        st.warning("⚠️ No records are available for this paint code.")
    else:
        detail_records = len(detail_df)
        detail_batches = valid_batch_count(
            detail_df["Batch_ID"]
        )
        detail_lines = detail_df["線別"].nunique()
        total_paint = detail_df["塗料重量"].sum()
        total_solvent = detail_df["添加重量"].sum()

        weighted_ratio = (
            total_solvent / total_paint * 100
            if total_paint > 0
            else np.nan
        )

        median_paint = detail_df["塗料重量"].median()
        median_solvent = detail_df["添加重量"].median()
        median_before = detail_df["黏度(秒)"].median()
        median_after = detail_df["黏度(秒)_1"].median()
        median_drop = detail_df["Delta_V"].median()
        median_efficiency = detail_df[
            "Viscosity_Sensitivity"
        ].median()

        kpi1 = st.columns(5)

        kpi1[0].metric(
            "Adjustment Records",
            f"{detail_records:,}",
        )
        kpi1[1].metric(
            "Historical Batches",
            f"{detail_batches:,}",
        )
        kpi1[2].metric(
            "Production Lines",
            f"{detail_lines:,}",
        )
        kpi1[3].metric(
            "Total Solvent Usage",
            safe_metric(total_solvent, 0, " kg"),
        )
        kpi1[4].metric(
            "Weighted Solvent Ratio",
            safe_metric(weighted_ratio, 2, "%"),
        )

        kpi2 = st.columns(5)

        kpi2[0].metric(
            "Reference Paint Weight",
            safe_metric(median_paint, 1, " kg"),
        )
        kpi2[1].metric(
            "Median Solvent Added",
            safe_metric(median_solvent, 1, " kg"),
        )
        kpi2[2].metric(
            "Median Before Viscosity",
            safe_metric(median_before, 1, " s"),
        )
        kpi2[3].metric(
            "Median After Viscosity",
            safe_metric(median_after, 1, " s"),
        )
        kpi2[4].metric(
            "Median Dilution Efficiency",
            safe_metric(median_efficiency, 2, " s/%"),
        )

        st.markdown("#### Historical Reference")

        ref1, ref2, ref3 = st.columns(3)

        ref1.info(
            f"**After-viscosity P10–P90**\n\n"
            f"{format_range(detail_df['黏度(秒)_1'])} s"
        )

        ref2.info(
            f"**Solvent-ratio P10–P90**\n\n"
            f"{format_range(detail_df['Solvent_Ratio_Percent'])}%"
        )

        ref3.info(
            f"**Median viscosity drop**\n\n"
            f"{median_drop:.1f} s"
        )

        detail_chart1, detail_chart2 = st.columns(2)

        with detail_chart1:
            fig3, ax3 = plt.subplots(
                figsize=(8.5, 5.5),
                dpi=150,
            )

            for line in clean_options(detail_df["線別"]):
                line_df = detail_df[
                    detail_df["線別"] == line
                ]

                ax3.scatter(
                    line_df["黏度(秒)"],
                    line_df["Solvent_Ratio_Percent"],
                    label=line,
                    alpha=0.7,
                )

            ax3.set_title(
                "Before Viscosity vs Solvent Ratio",
                loc="left",
                fontweight="bold",
            )
            ax3.set_xlabel("Before Viscosity (s)")
            ax3.set_ylabel("Solvent Ratio (%)")
            ax3.grid(
                True,
                linestyle="--",
                linewidth=0.6,
                alpha=0.4,
            )

            if detail_lines > 1:
                ax3.legend(
                    title="Production Line",
                    fontsize=8,
                    title_fontsize=9,
                )

            for spine in ax3.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(1.0)

            fig3.tight_layout()
            st.pyplot(fig3, use_container_width=True)
            plt.close(fig3)

        with detail_chart2:
            line_usage = build_line_summary(detail_df)

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
                        f" | {row['Weighted_Ratio_Percent']:.2f}%"
                    ),
                    va="center",
                    fontsize=8,
                )

            ax4.set_title(
                "Solvent Usage by Production Line",
                loc="left",
                fontweight="bold",
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

        with st.expander("View Historical Detail Records"):
            detail_display = detail_df[
                [
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

            st.dataframe(
                detail_display,
                use_container_width=True,
                hide_index=True,
            )


# =========================================================
# TAB 3 — PRODUCTION LINE COMPARISON
# =========================================================
with tab_line:
    st.subheader("3. Production Line Comparison")

    st.caption(
        f"Analysis Period: {period_label} | "
        f"Records Included: {len(filter_df):,}"
    )

    line_paint_code = st.selectbox(
        "Select Paint Code for Line Comparison",
        options=clean_options(filter_df["Paint_Code"]),
        key="line_paint_code",
    )

    comparison_df = filter_df[
        filter_df["Paint_Code"] == line_paint_code
    ].copy()

    line_summary = build_line_summary(comparison_df)

    if line_summary.empty:
        st.warning("⚠️ No production-line data are available.")
    elif line_summary["線別"].nunique() < 2:
        st.warning(
            "⚠️ Only one production line remains after the global filters. "
            "Select at least two production lines in the global filter to compare them."
        )

        single_line_display = line_summary.copy()
        st.dataframe(
            single_line_display,
            use_container_width=True,
            hide_index=True,
        )
    else:
        number_of_lines = line_summary["線別"].nunique()
        total_solvent = line_summary["Total_Solvent_kg"].sum()
        total_paint = line_summary["Total_Paint_kg"].sum()

        overall_weighted_ratio = (
            total_solvent / total_paint * 100
            if total_paint > 0
            else np.nan
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Production Lines",
            f"{number_of_lines:,}",
        )
        c2.metric(
            "Total Records",
            f"{int(line_summary['Adjustment_Records'].sum()):,}",
        )
        c3.metric(
            "Total Solvent Usage",
            safe_metric(total_solvent, 0, " kg"),
        )
        c4.metric(
            "Overall Weighted Ratio",
            safe_metric(overall_weighted_ratio, 2, "%"),
        )

        chart1, chart2 = st.columns(2)

        with chart1:
            fig5, ax5 = plt.subplots(
                figsize=(8.5, 5.8),
                dpi=150,
            )

            x_values = np.arange(len(line_summary))

            before_values = line_summary[
                "Median_Before_Viscosity"
            ].to_numpy()

            after_values = line_summary[
                "Median_After_Viscosity"
            ].to_numpy()

            for index in range(len(line_summary)):
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
                x_values,
                before_values,
                s=80,
                marker="o",
                label="Before Viscosity",
            )

            ax5.scatter(
                x_values,
                after_values,
                s=80,
                marker="s",
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

            ax5.set_xticks(x_values)
            ax5.set_xticklabels(line_summary["線別"])
            ax5.set_title(
                "Before vs After Viscosity by Line",
                loc="left",
                fontweight="bold",
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
            ratio_df = line_summary.sort_values(
                "Weighted_Ratio_Percent",
                ascending=True,
            )

            fig6, ax6 = plt.subplots(
                figsize=(8.5, 5.8),
                dpi=150,
            )

            ax6.barh(
                ratio_df["線別"],
                ratio_df["Weighted_Ratio_Percent"],
            )

            for index, row in ratio_df.reset_index(
                drop=True
            ).iterrows():
                ax6.text(
                    row["Weighted_Ratio_Percent"],
                    index,
                    (
                        f" {row['Weighted_Ratio_Percent']:.2f}%"
                        f" | {row['Total_Solvent_kg']:,.0f} kg"
                    ),
                    va="center",
                    fontsize=8,
                )

            ax6.set_title(
                "Weighted Solvent Ratio by Line",
                loc="left",
                fontweight="bold",
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

        comparison_display = line_summary[
            [
                "線別",
                "Adjustment_Records",
                "Historical_Batches",
                "Total_Paint_kg",
                "Total_Solvent_kg",
                "Median_Paint_kg",
                "Median_Solvent_kg",
                "Weighted_Ratio_Percent",
                "Median_Before_Viscosity",
                "Median_After_Viscosity",
                "Median_Viscosity_Drop",
                "Median_Dilution_Efficiency",
            ]
        ].copy()

        comparison_display.columns = [
            "Production Line",
            "Adjustment Records",
            "Historical Batches",
            "Total Paint (kg)",
            "Total Solvent (kg)",
            "Reference Paint Weight (kg)",
            "Median Solvent Added (kg)",
            "Weighted Solvent Ratio (%)",
            "Median Before Viscosity (s)",
            "Median After Viscosity (s)",
            "Median Viscosity Drop (s)",
            "Median Dilution Efficiency (s/%)",
        ]

        for col in comparison_display.columns[3:]:
            comparison_display[col] = pd.to_numeric(
                comparison_display[col],
                errors="coerce",
            ).round(2)

        st.dataframe(
            comparison_display,
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### Comparison Interpretation")

        max_ratio_row = line_summary.loc[
            line_summary["Weighted_Ratio_Percent"].idxmax()
        ]

        min_ratio_row = line_summary.loc[
            line_summary["Weighted_Ratio_Percent"].idxmin()
        ]

        ratio_difference = (
            max_ratio_row["Weighted_Ratio_Percent"]
            - min_ratio_row["Weighted_Ratio_Percent"]
        )

        before_difference = (
            line_summary["Median_Before_Viscosity"].max()
            - line_summary["Median_Before_Viscosity"].min()
        )

        st.write(
            f"The highest weighted solvent ratio is on "
            f"**{max_ratio_row['線別']}** "
            f"({max_ratio_row['Weighted_Ratio_Percent']:.2f}%), "
            f"while the lowest is on "
            f"**{min_ratio_row['線別']}** "
            f"({min_ratio_row['Weighted_Ratio_Percent']:.2f}%). "
            f"The difference is **{ratio_difference:.2f} percentage points**."
        )

        if ratio_difference <= 2:
            st.info(
                "The production lines show similar solvent-addition ratios. "
                "If all lines consistently require high solvent addition, "
                "supplier delivery viscosity should be reviewed."
            )
        elif before_difference >= 10:
            st.info(
                "The production lines have clearly different incoming viscosity. "
                "The solvent difference may be caused by incoming viscosity or "
                "measurement conditions rather than line performance alone."
            )
        else:
            st.warning(
                "The production lines show a noticeable solvent-ratio difference "
                "despite relatively similar incoming viscosity. Review line operating "
                "conditions and line-specific viscosity requirements."
            )
