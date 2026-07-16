import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="Solvent Reduction Opportunity",
    page_icon="🎨",
    layout="wide"
)

st.title("🎨 塗料黏度改善與稀釋劑減量分析")

st.markdown(
    """
    本頁依塗料供應商、樹脂種類、塗料編號、線別及稀釋劑種類，
    分析高使用頻率及高稀釋劑用量之塗料，作為後續與供應商
    討論交貨黏度及降低稀釋劑使用量之參考。
    """
)


# =========================================================
# 2. MATPLOTLIB SETTINGS
# =========================================================
plt.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei",
    "Arial Unicode MS",
    "Noto Sans CJK TC",
    "DejaVu Sans"
]
plt.rcParams["axes.unicode_minus"] = False


# =========================================================
# 3. LOAD DATA
# =========================================================
if not st.session_state.get("raw_data_loaded", False):
    st.warning("⚠️ 請先回到首頁上傳原始資料。")
    st.stop()

group_a = st.session_state.get("group_a_data")

if group_a is None or group_a.empty:
    st.warning("⚠️ 目前沒有可供分析的 Group A 有效資料。")
    st.stop()

df = group_a.copy()


# =========================================================
# 4. REQUIRED COLUMNS
# =========================================================
required_columns = [
    "Vendor",
    "Resin",
    "Solvent_Type",
    "塗料重量",
    "添加重量",
    "黏度(秒)",
    "黏度(秒)_1",
    "Delta_V",
    "Solvent_Ratio_Percent",
    "Viscosity_Sensitivity",
    "塗料批號",
    "線別"
]

for col in required_columns:
    if col not in df.columns:
        if col in [
            "塗料重量",
            "添加重量",
            "黏度(秒)",
            "黏度(秒)_1",
            "Delta_V",
            "Solvent_Ratio_Percent",
            "Viscosity_Sensitivity"
        ]:
            df[col] = np.nan
        else:
            df[col] = "Unknown"


# Paint code
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
text_columns = [
    "Vendor",
    "Resin",
    "Paint_Code",
    "Solvent_Type",
    "線別",
    "塗料批號"
]

invalid_text_values = {
    "",
    "NAN",
    "NONE",
    "NULL",
    "N/A",
    "NA",
    "-",
    "--"
}

for col in text_columns:
    df[col] = (
        df[col]
        .fillna("")
        .astype(str)
        .str.strip()
    )

df["Paint_Code"] = df["Paint_Code"].str.upper()
df["Solvent_Type"] = df["Solvent_Type"].str.upper()

for col in ["Vendor", "Resin", "Paint_Code", "Solvent_Type", "線別"]:
    df.loc[
        df[col].str.upper().isin(invalid_text_values),
        col
    ] = "Unknown"

df["Batch_ID"] = df["塗料批號"].copy()


# =========================================================
# 6. NUMERIC CLEANING
# =========================================================
numeric_columns = [
    "塗料重量",
    "添加重量",
    "黏度(秒)",
    "黏度(秒)_1",
    "Delta_V",
    "Solvent_Ratio_Percent",
    "Viscosity_Sensitivity"
]

for col in numeric_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce")


# Recalculate to ensure consistency with the current app logic
df["Delta_V"] = df["黏度(秒)"] - df["黏度(秒)_1"]

df["Solvent_Ratio_Percent"] = np.where(
    df["塗料重量"] > 0,
    df["添加重量"] / df["塗料重量"] * 100,
    np.nan
)

df["Viscosity_Sensitivity"] = np.where(
    df["Solvent_Ratio_Percent"] > 0,
    df["Delta_V"] / df["Solvent_Ratio_Percent"],
    np.nan
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
    st.warning("⚠️ 清理後沒有可供分析的有效資料。")
    st.stop()


# =========================================================
# 7. HELPER FUNCTIONS
# =========================================================
def clean_options(series):
    """Return sorted non-empty filter options."""
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
    """Count distinct valid paint batch IDs."""
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
    """Return a formatted P10-P90 range."""
    valid = pd.to_numeric(series, errors="coerce").dropna()

    if valid.empty:
        return "-"

    p_low = valid.quantile(low)
    p_high = valid.quantile(high)

    if np.isclose(p_low, p_high):
        return f"{p_low:.1f}"

    return f"{p_low:.1f} – {p_high:.1f}"


def apply_filter(data, column, selected_value):
    """Apply one All/selected filter."""
    if selected_value == "全部":
        return data.copy()

    return data[
        data[column].astype(str) == str(selected_value)
    ].copy()


def safe_metric(value, decimals=1, suffix=""):
    """Format KPI values safely."""
    if value is None or pd.isna(value):
        return "-"

    return f"{value:,.{decimals}f}{suffix}"


def build_summary(source_df):
    """
    Build summary by:
    Vendor + Resin + Paint Code + Solvent Type

    Production line is not included in the main ranking group,
    so each paint code remains one overall improvement target.
    """
    if source_df.empty:
        return pd.DataFrame()

    summary = source_df.groupby(
        [
            "Vendor",
            "Resin",
            "Paint_Code",
            "Solvent_Type"
        ],
        observed=False,
        dropna=False
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
        Median_Efficiency=("Viscosity_Sensitivity", "median")
    ).reset_index()

    summary["Weighted_Ratio_Percent"] = np.where(
        summary["Total_Paint_kg"] > 0,
        summary["Total_Solvent_kg"]
        / summary["Total_Paint_kg"]
        * 100,
        np.nan
    )

    summary["Solvent_Per_Batch_kg"] = np.where(
        summary["Historical_Batches"] > 0,
        summary["Total_Solvent_kg"]
        / summary["Historical_Batches"],
        np.nan
    )

    # Percentile-based opportunity score
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

    # Total solvent usage carries the highest weight
    summary["Opportunity_Score"] = (
        summary["Batch_Score"] * 0.35
        + summary["Solvent_Score"] * 0.45
        + summary["Ratio_Score"] * 0.20
    ) * 100

    summary["Priority_Level"] = pd.cut(
        summary["Opportunity_Score"],
        bins=[-np.inf, 40, 70, np.inf],
        labels=["一般", "中度優先", "高度優先"]
    ).astype(str)

    summary = summary.sort_values(
        by=[
            "Opportunity_Score",
            "Total_Solvent_kg",
            "Historical_Batches"
        ],
        ascending=[False, False, False]
    ).reset_index(drop=True)

    summary["Priority_Rank"] = np.arange(
        1,
        len(summary) + 1
    )

    return summary


def prepare_summary_display(summary_df):
    """Prepare the summary table displayed in the UI."""
    if summary_df.empty:
        return pd.DataFrame()

    display_df = summary_df[
        [
            "Priority_Rank",
            "Priority_Level",
            "Vendor",
            "Resin",
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
            "Opportunity_Score"
        ]
    ].copy()

    display_df.columns = [
        "優先順序",
        "改善優先等級",
        "塗料供應商",
        "樹脂種類",
        "塗料編號",
        "稀釋劑種類",
        "調整紀錄數",
        "歷史批數",
        "使用線別數",
        "總塗料使用量 (kg)",
        "總稀釋劑使用量 (kg)",
        "加權添加比例 (%)",
        "平均每批添加量 (kg)",
        "初始黏度中位數 (s)",
        "最終黏度中位數 (s)",
        "減量機會分數"
    ]

    numeric_round_columns = [
        "總塗料使用量 (kg)",
        "總稀釋劑使用量 (kg)",
        "加權添加比例 (%)",
        "平均每批添加量 (kg)",
        "初始黏度中位數 (s)",
        "最終黏度中位數 (s)",
        "減量機會分數"
    ]

    for col in numeric_round_columns:
        display_df[col] = display_df[col].round(2)

    return display_df


def select_all_filter(label, source_df, column, key):
    """Create an All + options selectbox."""
    options = ["全部"] + clean_options(source_df[column])

    return st.selectbox(
        label,
        options=options,
        key=key
    )


# =========================================================
# 8. MAIN SUB-TABS
# =========================================================
tab_priority, tab_detail, tab_line = st.tabs([
    "① 減量優先順序",
    "② 塗料編號詳細分析",
    "③ 產線黏度比較"
])


# =========================================================
# TAB 1: SOLVENT REDUCTION PRIORITY
# =========================================================
with tab_priority:
    st.subheader("① 稀釋劑減量優先順序")

    st.caption(
        "以歷史批數、總稀釋劑使用量及加權添加比例，"
        "找出最適合優先與供應商討論交貨黏度之塗料編號。"
    )

    st.markdown("#### 🔍 分析條件")

    f1, f2, f3, f4 = st.columns(4)

    with f1:
        priority_vendor = select_all_filter(
            "塗料供應商",
            df,
            "Vendor",
            "priority_vendor"
        )

    priority_df = apply_filter(
        df,
        "Vendor",
        priority_vendor
    )

    with f2:
        priority_resin = select_all_filter(
            "樹脂種類",
            priority_df,
            "Resin",
            "priority_resin"
        )

    priority_df = apply_filter(
        priority_df,
        "Resin",
        priority_resin
    )

    with f3:
        priority_line = select_all_filter(
            "線別",
            priority_df,
            "線別",
            "priority_line"
        )

    priority_df = apply_filter(
        priority_df,
        "線別",
        priority_line
    )

    with f4:
        priority_solvent = select_all_filter(
            "稀釋劑種類",
            priority_df,
            "Solvent_Type",
            "priority_solvent"
        )

    priority_df = apply_filter(
        priority_df,
        "Solvent_Type",
        priority_solvent
    )

    if priority_df.empty:
        st.warning("⚠️ 目前篩選條件沒有可供分析的資料。")
    else:
        priority_summary = build_summary(priority_df)

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
            "塗料編號數",
            f"{total_paint_codes:,}"
        )

        k2.metric(
            "歷史批數",
            f"{int(total_batches):,}"
        )

        k3.metric(
            "總塗料使用量",
            safe_metric(total_paint, 0, " kg")
        )

        k4.metric(
            "總稀釋劑使用量",
            safe_metric(total_solvent, 0, " kg")
        )

        k5.metric(
            "整體加權添加比例",
            safe_metric(overall_weighted_ratio, 2, "%")
        )

        st.markdown("---")

        # -----------------------------------------------------
        # Priority selection
        # -----------------------------------------------------
        top_n = st.slider(
            "顯示前幾名塗料編號",
            min_value=5,
            max_value=min(30, max(5, len(priority_summary))),
            value=min(15, max(5, len(priority_summary))),
            step=1,
            key="priority_top_n"
        )

        top_n = min(top_n, len(priority_summary))

        ranking_mode = st.radio(
            "排名方式",
            options=[
                "綜合減量機會",
                "使用頻率最高",
                "稀釋劑總用量最高",
                "加權添加比例最高"
            ],
            horizontal=True,
            key="priority_ranking_mode"
        )

        if ranking_mode == "使用頻率最高":
            ranked_df = priority_summary.sort_values(
                by=[
                    "Historical_Batches",
                    "Adjustment_Records",
                    "Total_Solvent_kg"
                ],
                ascending=[False, False, False]
            ).copy()

        elif ranking_mode == "稀釋劑總用量最高":
            ranked_df = priority_summary.sort_values(
                by=[
                    "Total_Solvent_kg",
                    "Historical_Batches",
                    "Weighted_Ratio_Percent"
                ],
                ascending=[False, False, False]
            ).copy()

        elif ranking_mode == "加權添加比例最高":
            ranked_df = priority_summary.sort_values(
                by=[
                    "Weighted_Ratio_Percent",
                    "Historical_Batches",
                    "Total_Solvent_kg"
                ],
                ascending=[False, False, False]
            ).copy()

        else:
            ranked_df = priority_summary.sort_values(
                by=[
                    "Opportunity_Score",
                    "Total_Solvent_kg",
                    "Historical_Batches"
                ],
                ascending=[False, False, False]
            ).copy()

        ranked_df = ranked_df.reset_index(drop=True)
        ranked_df["Priority_Rank"] = np.arange(
            1,
            len(ranked_df) + 1
        )

        top_ranked = ranked_df.head(top_n).copy()

        # -----------------------------------------------------
        # Charts
        # -----------------------------------------------------
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.markdown("#### 稀釋劑總用量最高塗料編號")

            solvent_chart_df = (
                priority_summary
                .sort_values(
                    "Total_Solvent_kg",
                    ascending=False
                )
                .head(top_n)
                .sort_values(
                    "Total_Solvent_kg",
                    ascending=True
                )
            )

            fig1, ax1 = plt.subplots(
                figsize=(9, max(5, top_n * 0.42)),
                dpi=150
            )

            labels = (
                solvent_chart_df["Paint_Code"]
                + " | "
                + solvent_chart_df["Vendor"]
            )

            ax1.barh(
                labels,
                solvent_chart_df["Total_Solvent_kg"]
            )

            for index, value in enumerate(
                solvent_chart_df["Total_Solvent_kg"]
            ):
                ax1.text(
                    value,
                    index,
                    f" {value:,.0f} kg",
                    va="center",
                    fontsize=8
                )

            ax1.set_xlabel("總稀釋劑使用量 (kg)")
            ax1.set_ylabel("塗料編號")
            ax1.grid(
                axis="x",
                linestyle="--",
                linewidth=0.6,
                alpha=0.4
            )

            for spine in ax1.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(1.0)

            fig1.tight_layout()

            st.pyplot(
                fig1,
                use_container_width=True
            )

            plt.close(fig1)

        with chart_col2:
            st.markdown("#### 使用頻率與稀釋劑總用量")

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
                    80
                )

            fig2, ax2 = plt.subplots(
                figsize=(9, 6),
                dpi=150
            )

            ax2.scatter(
                scatter_df["Historical_Batches"],
                scatter_df["Total_Solvent_kg"],
                s=marker_sizes,
                alpha=0.65
            )

            label_df = (
                scatter_df
                .sort_values(
                    "Opportunity_Score",
                    ascending=False
                )
                .head(min(10, len(scatter_df)))
            )

            for _, row in label_df.iterrows():
                ax2.annotate(
                    row["Paint_Code"],
                    (
                        row["Historical_Batches"],
                        row["Total_Solvent_kg"]
                    ),
                    xytext=(5, 5),
                    textcoords="offset points",
                    fontsize=8
                )

            ax2.set_xlabel("歷史批數")
            ax2.set_ylabel("總稀釋劑使用量 (kg)")
            ax2.grid(
                True,
                linestyle="--",
                linewidth=0.6,
                alpha=0.4
            )

            ax2.text(
                0.02,
                0.98,
                "圓點大小：加權添加比例",
                transform=ax2.transAxes,
                va="top",
                fontsize=9
            )

            for spine in ax2.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(1.0)

            fig2.tight_layout()

            st.pyplot(
                fig2,
                use_container_width=True
            )

            plt.close(fig2)

        # -----------------------------------------------------
        # Ranking table
        # -----------------------------------------------------
        st.markdown(f"#### 📋 {ranking_mode}")

        priority_display = prepare_summary_display(
            top_ranked
        )

        st.dataframe(
            priority_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "優先順序": st.column_config.NumberColumn(
                    width="small",
                    format="%d"
                ),
                "改善優先等級": st.column_config.TextColumn(
                    width="small"
                ),
                "塗料編號": st.column_config.TextColumn(
                    width="medium"
                ),
                "總塗料使用量 (kg)": st.column_config.NumberColumn(
                    format="%.0f"
                ),
                "總稀釋劑使用量 (kg)": st.column_config.NumberColumn(
                    format="%.0f"
                ),
                "加權添加比例 (%)": st.column_config.NumberColumn(
                    format="%.2f"
                ),
                "平均每批添加量 (kg)": st.column_config.NumberColumn(
                    format="%.2f"
                ),
                "減量機會分數": st.column_config.NumberColumn(
                    format="%.1f"
                )
            }
        )

        # -----------------------------------------------------
        # Automatic conclusion
        # -----------------------------------------------------
        if not priority_summary.empty:
            top_opportunity = priority_summary.iloc[0]

            st.markdown("#### 📝 優先改善建議")

            st.info(
                f"塗料編號 **{top_opportunity['Paint_Code']}** "
                f"（供應商：**{top_opportunity['Vendor']}**；"
                f"樹脂：**{top_opportunity['Resin']}**）"
                f"歷史共有 **{int(top_opportunity['Historical_Batches'])} 批**，"
                f"總稀釋劑使用量為 "
                f"**{top_opportunity['Total_Solvent_kg']:,.0f} kg**，"
                f"加權添加比例為 "
                f"**{top_opportunity['Weighted_Ratio_Percent']:.2f}%**。"
                f"建議列為供應商交貨黏度改善之優先確認對象。"
            )

        # -----------------------------------------------------
        # Full data export
        # -----------------------------------------------------
        full_priority_display = prepare_summary_display(
            priority_summary
        )

        csv_data = full_priority_display.to_csv(
            index=False,
            encoding="utf-8-sig"
        ).encode("utf-8-sig")

        st.download_button(
            label="📥 下載完整優先順序表 CSV",
            data=csv_data,
            file_name="Solvent_Reduction_Priority.csv",
            mime="text/csv",
            key="download_priority_csv"
        )


# =========================================================
# TAB 2: PAINT CODE DETAIL
# =========================================================
with tab_detail:
    st.subheader("② 塗料編號詳細分析")

    st.caption(
        "選擇單一塗料編號，確認其使用線別、稀釋劑種類、"
        "歷史添加量及調整前後黏度。"
    )

    st.markdown("#### 🔍 塗料編號選擇")

    d1, d2, d3, d4 = st.columns(4)

    with d1:
        detail_vendor_options = clean_options(df["Vendor"])

        detail_vendor = st.selectbox(
            "塗料供應商",
            options=detail_vendor_options,
            key="detail_vendor"
        )

    detail_filter_df = df[
        df["Vendor"] == detail_vendor
    ].copy()

    with d2:
        detail_resin_options = clean_options(
            detail_filter_df["Resin"]
        )

        detail_resin = st.selectbox(
            "樹脂種類",
            options=detail_resin_options,
            key="detail_resin"
        )

    detail_filter_df = detail_filter_df[
        detail_filter_df["Resin"] == detail_resin
    ].copy()

    with d3:
        detail_paint_options = clean_options(
            detail_filter_df["Paint_Code"]
        )

        detail_paint_code = st.selectbox(
            "塗料編號",
            options=detail_paint_options,
            key="detail_paint_code"
        )

    detail_filter_df = detail_filter_df[
        detail_filter_df["Paint_Code"]
        == detail_paint_code
    ].copy()

    with d4:
        detail_solvent_options = clean_options(
            detail_filter_df["Solvent_Type"]
        )

        detail_solvent = st.selectbox(
            "稀釋劑種類",
            options=detail_solvent_options,
            key="detail_solvent"
        )

    detail_df = detail_filter_df[
        detail_filter_df["Solvent_Type"]
        == detail_solvent
    ].copy()

    if detail_df.empty:
        st.warning("⚠️ 目前選擇條件沒有有效資料。")
    else:
        detail_records = len(detail_df)
        detail_batches = distinct_batch_count(
            detail_df["Batch_ID"]
        )

        detail_lines = detail_df.loc[
            detail_df["線別"] != "Unknown",
            "線別"
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
            "調整紀錄數",
            f"{detail_records:,}"
        )

        kpi_row1[1].metric(
            "歷史批數",
            f"{detail_batches:,}"
        )

        kpi_row1[2].metric(
            "使用線別數",
            f"{detail_lines:,}"
        )

        kpi_row1[3].metric(
            "總稀釋劑使用量",
            safe_metric(
                detail_total_solvent,
                0,
                " kg"
            )
        )

        kpi_row1[4].metric(
            "加權添加比例",
            safe_metric(
                detail_weighted_ratio,
                2,
                "%"
            )
        )

        kpi_row2 = st.columns(5)

        kpi_row2[0].metric(
            "參考塗料重量",
            safe_metric(
                median_paint,
                1,
                " kg"
            )
        )

        kpi_row2[1].metric(
            "參考添加量",
            safe_metric(
                median_solvent,
                1,
                " kg"
            )
        )

        kpi_row2[2].metric(
            "初始黏度中位數",
            safe_metric(
                median_before,
                1,
                " s"
            )
        )

        kpi_row2[3].metric(
            "最終黏度中位數",
            safe_metric(
                median_after,
                1,
                " s"
            )
        )

        kpi_row2[4].metric(
            "稀釋效率中位數",
            safe_metric(
                median_efficiency,
                2,
                " s/%"
            )
        )

        st.markdown("---")

        # -----------------------------------------------------
        # Historical reference box
        # -----------------------------------------------------
        st.markdown("#### 📌 歷史黏度與添加量參考")

        reference_col1, reference_col2, reference_col3 = st.columns(3)

        reference_col1.info(
            f"**歷史調整後黏度 P10–P90**\n\n"
            f"{after_viscosity_range} s"
        )

        reference_col2.info(
            f"**歷史添加比例 P10–P90**\n\n"
            f"{ratio_range}%"
        )

        reference_col3.info(
            f"**歷史降黏幅度中位數**\n\n"
            f"{median_delta:.1f} s"
        )

        st.caption(
            "上述調整後黏度為歷史生產參考，正式設定供應商交貨黏度前，"
            "仍需確認量測溫度、量測方法、塗裝位置及產品規格。"
        )

        # -----------------------------------------------------
        # Detailed charts
        # -----------------------------------------------------
        detail_chart_col1, detail_chart_col2 = st.columns(2)

        with detail_chart_col1:
            st.markdown("#### 初始黏度與稀釋劑添加比例")

            fig3, ax3 = plt.subplots(
                figsize=(8.5, 5.5),
                dpi=150
            )

            line_values = clean_options(
                detail_df["線別"]
            )

            if not line_values:
                ax3.scatter(
                    detail_df["黏度(秒)"],
                    detail_df["Solvent_Ratio_Percent"],
                    alpha=0.7
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
                        alpha=0.7
                    )

                ax3.legend(
                    title="線別",
                    fontsize=8,
                    title_fontsize=9
                )

            ax3.set_xlabel("調整前黏度 (s)")
            ax3.set_ylabel("稀釋劑添加比例 (%)")
            ax3.grid(
                True,
                linestyle="--",
                linewidth=0.6,
                alpha=0.4
            )

            for spine in ax3.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(1.0)

            fig3.tight_layout()

            st.pyplot(
                fig3,
                use_container_width=True
            )

            plt.close(fig3)

        with detail_chart_col2:
            st.markdown("#### 各線別稀釋劑使用量")

            line_usage = detail_df.groupby(
                "線別",
                observed=False
            ).agg(
                Total_Solvent_kg=("添加重量", "sum"),
                Total_Paint_kg=("塗料重量", "sum"),
                Records=("Paint_Code", "size")
            ).reset_index()

            line_usage["Weighted_Ratio_Percent"] = np.where(
                line_usage["Total_Paint_kg"] > 0,
                line_usage["Total_Solvent_kg"]
                / line_usage["Total_Paint_kg"]
                * 100,
                np.nan
            )

            line_usage = line_usage.sort_values(
                "Total_Solvent_kg",
                ascending=True
            )

            fig4, ax4 = plt.subplots(
                figsize=(8.5, 5.5),
                dpi=150
            )

            ax4.barh(
                line_usage["線別"],
                line_usage["Total_Solvent_kg"]
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
                    fontsize=8
                )

            ax4.set_xlabel("總稀釋劑使用量 (kg)")
            ax4.set_ylabel("線別")
            ax4.grid(
                axis="x",
                linestyle="--",
                linewidth=0.6,
                alpha=0.4
            )

            for spine in ax4.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(1.0)

            fig4.tight_layout()

            st.pyplot(
                fig4,
                use_container_width=True
            )

            plt.close(fig4)

        # -----------------------------------------------------
        # Savings simulation
        # -----------------------------------------------------
        st.markdown("#### 💰 稀釋劑減量模擬")

        simulation_col1, simulation_col2 = st.columns(2)

        with simulation_col1:
            reduction_rate = st.select_slider(
                "預估減量比例",
                options=[5, 10, 15, 20, 25, 30],
                value=10,
                format_func=lambda x: f"{x}%",
                key="detail_reduction_rate"
            )

        with simulation_col2:
            solvent_unit_price = st.number_input(
                "稀釋劑單價（每 kg，可選填）",
                min_value=0.0,
                value=0.0,
                step=1.0,
                key="detail_solvent_price"
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
            "歷史總稀釋劑使用量",
            safe_metric(
                detail_total_solvent,
                0,
                " kg"
            )
        )

        sim2.metric(
            f"預估減少量（{reduction_rate}%）",
            safe_metric(
                estimated_reduction_kg,
                0,
                " kg"
            )
        )

        sim3.metric(
            "預估節省金額",
            (
                safe_metric(
                    estimated_saving,
                    0
                )
                if solvent_unit_price > 0
                else "請輸入單價"
            )
        )

        # -----------------------------------------------------
        # Detailed records
        # -----------------------------------------------------
        with st.expander("查看塗料編號歷史明細"):
            detail_columns = [
                "Vendor",
                "Resin",
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
                "Viscosity_Sensitivity"
            ]

            detail_display = detail_df[
                detail_columns
            ].copy()

            detail_display.columns = [
                "塗料供應商",
                "樹脂種類",
                "塗料編號",
                "線別",
                "稀釋劑種類",
                "塗料批號",
                "塗料重量 (kg)",
                "添加重量 (kg)",
                "添加比例 (%)",
                "調整前黏度 (s)",
                "調整後黏度 (s)",
                "降黏幅度 (s)",
                "稀釋效率 (s/%)"
            ]

            numeric_cols_detail = [
                "塗料重量 (kg)",
                "添加重量 (kg)",
                "添加比例 (%)",
                "調整前黏度 (s)",
                "調整後黏度 (s)",
                "降黏幅度 (s)",
                "稀釋效率 (s/%)"
            ]

            for col in numeric_cols_detail:
                detail_display[col] = (
                    pd.to_numeric(
                        detail_display[col],
                        errors="coerce"
                    ).round(2)
                )

            st.dataframe(
                detail_display,
                use_container_width=True,
                hide_index=True
            )


# =========================================================
# TAB 3: PRODUCTION LINE COMPARISON
# =========================================================
with tab_line:
    st.subheader("③ 產線黏度比較")

    st.caption(
        "固定同一供應商、樹脂、塗料編號及稀釋劑後，"
        "比較不同線別之初始黏度、最終黏度及稀釋劑使用量。"
    )

    st.markdown("#### 🔍 比較條件")

    l1, l2, l3, l4 = st.columns(4)

    with l1:
        line_vendor_options = clean_options(
            df["Vendor"]
        )

        line_vendor = st.selectbox(
            "塗料供應商",
            options=line_vendor_options,
            key="line_vendor"
        )

    line_filter_df = df[
        df["Vendor"] == line_vendor
    ].copy()

    with l2:
        line_resin_options = clean_options(
            line_filter_df["Resin"]
        )

        line_resin = st.selectbox(
            "樹脂種類",
            options=line_resin_options,
            key="line_resin"
        )

    line_filter_df = line_filter_df[
        line_filter_df["Resin"] == line_resin
    ].copy()

    with l3:
        line_paint_options = clean_options(
            line_filter_df["Paint_Code"]
        )

        line_paint_code = st.selectbox(
            "塗料編號",
            options=line_paint_options,
            key="line_paint_code"
        )

    line_filter_df = line_filter_df[
        line_filter_df["Paint_Code"]
        == line_paint_code
    ].copy()

    with l4:
        line_solvent_options = clean_options(
            line_filter_df["Solvent_Type"]
        )

        line_solvent = st.selectbox(
            "稀釋劑種類",
            options=line_solvent_options,
            key="line_solvent"
        )

    line_compare_df = line_filter_df[
        line_filter_df["Solvent_Type"]
        == line_solvent
    ].copy()

    line_compare_df = line_compare_df[
        line_compare_df["線別"] != "Unknown"
    ].copy()

    if line_compare_df.empty:
        st.warning("⚠️ 目前條件沒有可供比較的線別資料。")
    else:
        line_summary = line_compare_df.groupby(
            "線別",
            observed=False
        ).agg(
            Adjustment_Records=("Paint_Code", "size"),
            Historical_Batches=("Batch_ID", distinct_batch_count),
            Total_Paint_kg=("塗料重量", "sum"),
            Total_Solvent_kg=("添加重量", "sum"),
            Median_Paint_kg=("塗料重量", "median"),
            Median_Solvent_kg=("添加重量", "median"),
            Median_Viscosity_Before=("黏度(秒)", "median"),
            Median_Viscosity_After=("黏度(秒)_1", "median"),
            Median_Delta_V=("Delta_V", "median"),
            Median_Ratio_Percent=(
                "Solvent_Ratio_Percent",
                "median"
            ),
            Median_Efficiency=(
                "Viscosity_Sensitivity",
                "median"
            )
        ).reset_index()

        line_summary["Weighted_Ratio_Percent"] = np.where(
            line_summary["Total_Paint_kg"] > 0,
            line_summary["Total_Solvent_kg"]
            / line_summary["Total_Paint_kg"]
            * 100,
            np.nan
        )

        line_summary = line_summary.sort_values(
            "線別"
        ).reset_index(drop=True)

        number_of_lines = line_summary["線別"].nunique()

        if number_of_lines < 2:
            st.warning(
                "⚠️ 此塗料編號目前僅有一條線別資料，"
                "無法進行不同線別比較。"
            )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "比較線別數",
            f"{number_of_lines:,}"
        )

        c2.metric(
            "總調整紀錄數",
            f"{int(line_summary['Adjustment_Records'].sum()):,}"
        )

        c3.metric(
            "總稀釋劑使用量",
            safe_metric(
                line_summary["Total_Solvent_kg"].sum(),
                0,
                " kg"
            )
        )

        overall_line_ratio = (
            line_summary["Total_Solvent_kg"].sum()
            / line_summary["Total_Paint_kg"].sum()
            * 100
            if line_summary["Total_Paint_kg"].sum() > 0
            else np.nan
        )

        c4.metric(
            "整體加權添加比例",
            safe_metric(
                overall_line_ratio,
                2,
                "%"
            )
        )

        st.markdown("---")

        line_chart_col1, line_chart_col2 = st.columns(2)

        # -----------------------------------------------------
        # Before/after viscosity chart
        # -----------------------------------------------------
        with line_chart_col1:
            st.markdown("#### 各線別調整前後黏度")

            fig5, ax5 = plt.subplots(
                figsize=(8.5, 5.8),
                dpi=150
            )

            x_positions = np.arange(
                len(line_summary)
            )

            before_values = (
                line_summary["Median_Viscosity_Before"]
                .to_numpy()
            )

            after_values = (
                line_summary["Median_Viscosity_After"]
                .to_numpy()
            )

            for index, line_name in enumerate(
                line_summary["線別"]
            ):
                ax5.plot(
                    [index, index],
                    [
                        after_values[index],
                        before_values[index]
                    ],
                    linewidth=2,
                    alpha=0.65
                )

            ax5.scatter(
                x_positions,
                before_values,
                marker="o",
                s=80,
                label="調整前黏度"
            )

            ax5.scatter(
                x_positions,
                after_values,
                marker="s",
                s=80,
                label="調整後黏度"
            )

            for index, value in enumerate(before_values):
                ax5.annotate(
                    f"{value:.1f}",
                    (
                        index,
                        value
                    ),
                    xytext=(0, 8),
                    textcoords="offset points",
                    ha="center",
                    fontsize=8
                )

            for index, value in enumerate(after_values):
                ax5.annotate(
                    f"{value:.1f}",
                    (
                        index,
                        value
                    ),
                    xytext=(0, -14),
                    textcoords="offset points",
                    ha="center",
                    fontsize=8
                )

            ax5.set_xticks(x_positions)
            ax5.set_xticklabels(
                line_summary["線別"],
                rotation=0
            )

            ax5.set_xlabel("線別")
            ax5.set_ylabel("黏度中位數 (s)")
            ax5.legend()
            ax5.grid(
                axis="y",
                linestyle="--",
                linewidth=0.6,
                alpha=0.4
            )

            for spine in ax5.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(1.0)

            fig5.tight_layout()

            st.pyplot(
                fig5,
                use_container_width=True
            )

            plt.close(fig5)

        # -----------------------------------------------------
        # Weighted solvent ratio chart
        # -----------------------------------------------------
        with line_chart_col2:
            st.markdown("#### 各線別加權添加比例")

            ratio_chart_df = line_summary.sort_values(
                "Weighted_Ratio_Percent",
                ascending=True
            )

            fig6, ax6 = plt.subplots(
                figsize=(8.5, 5.8),
                dpi=150
            )

            ax6.barh(
                ratio_chart_df["線別"],
                ratio_chart_df["Weighted_Ratio_Percent"]
            )

            for index, row in ratio_chart_df.reset_index(
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
                    fontsize=8
                )

            ax6.set_xlabel("加權添加比例 (%)")
            ax6.set_ylabel("線別")
            ax6.grid(
                axis="x",
                linestyle="--",
                linewidth=0.6,
                alpha=0.4
            )

            for spine in ax6.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(1.0)

            fig6.tight_layout()

            st.pyplot(
                fig6,
                use_container_width=True
            )

            plt.close(fig6)

        # -----------------------------------------------------
        # Comparison table
        # -----------------------------------------------------
        st.markdown("#### 📋 線別比較表")

        line_display = line_summary[
            [
                "線別",
                "Adjustment_Records",
                "Historical_Batches",
                "Total_Paint_kg",
                "Total_Solvent_kg",
                "Median_Paint_kg",
                "Median_Solvent_kg",
                "Weighted_Ratio_Percent",
                "Median_Viscosity_Before",
                "Median_Viscosity_After",
                "Median_Delta_V",
                "Median_Efficiency"
            ]
        ].copy()

        line_display.columns = [
            "線別",
            "調整紀錄數",
            "歷史批數",
            "總塗料使用量 (kg)",
            "總稀釋劑使用量 (kg)",
            "參考塗料重量 (kg)",
            "參考添加量 (kg)",
            "加權添加比例 (%)",
            "初始黏度中位數 (s)",
            "最終黏度中位數 (s)",
            "降黏幅度中位數 (s)",
            "稀釋效率中位數 (s/%)"
        ]

        numeric_line_cols = [
            "總塗料使用量 (kg)",
            "總稀釋劑使用量 (kg)",
            "參考塗料重量 (kg)",
            "參考添加量 (kg)",
            "加權添加比例 (%)",
            "初始黏度中位數 (s)",
            "最終黏度中位數 (s)",
            "降黏幅度中位數 (s)",
            "稀釋效率中位數 (s/%)"
        ]

        for col in numeric_line_cols:
            line_display[col] = line_display[col].round(2)

        st.dataframe(
            line_display,
            use_container_width=True,
            hide_index=True
        )

        # -----------------------------------------------------
        # Automatic interpretation
        # -----------------------------------------------------
        st.markdown("#### 📝 產線差異判讀")

        if number_of_lines >= 2:
            highest_ratio_row = line_summary.loc[
                line_summary[
                    "Weighted_Ratio_Percent"
                ].idxmax()
            ]

            lowest_ratio_row = line_summary.loc[
                line_summary[
                    "Weighted_Ratio_Percent"
                ].idxmin()
            ]

            ratio_difference = (
                highest_ratio_row["Weighted_Ratio_Percent"]
                - lowest_ratio_row["Weighted_Ratio_Percent"]
            )

            before_difference = (
                line_summary[
                    "Median_Viscosity_Before"
                ].max()
                - line_summary[
                    "Median_Viscosity_Before"
                ].min()
            )

            after_difference = (
                line_summary[
                    "Median_Viscosity_After"
                ].max()
                - line_summary[
                    "Median_Viscosity_After"
                ].min()
            )

            st.write(
                f"加權添加比例最高為 **{highest_ratio_row['線別']}** "
                f"（{highest_ratio_row['Weighted_Ratio_Percent']:.2f}%），"
                f"最低為 **{lowest_ratio_row['線別']}** "
                f"（{lowest_ratio_row['Weighted_Ratio_Percent']:.2f}%），"
                f"差異為 **{ratio_difference:.2f} 個百分點**。"
            )

            st.write(
                f"各線別初始黏度中位數最大差異為 "
                f"**{before_difference:.1f} s**；"
                f"最終黏度中位數最大差異為 "
                f"**{after_difference:.1f} s**。"
            )

            if ratio_difference <= 2:
                st.success(
                    "各線別稀釋劑添加比例差異較小。"
                    "若各線別皆持續需要添加較多稀釋劑，"
                    "可優先與供應商確認交貨黏度。"
                )

            elif before_difference >= 10:
                st.info(
                    "不同線別之初始黏度存在明顯差異，"
                    "目前稀釋劑使用差異可能與投入黏度不同有關，"
                    "建議先確認各線別進料及量測條件。"
                )

            else:
                st.warning(
                    "在初始黏度相近的情況下，"
                    "不同線別之稀釋劑添加比例仍有較明顯差異，"
                    "建議確認線別操作條件、量測方法及使用需求。"
                )

        else:
            st.info(
                "目前僅有一條線別資料，結果可作為單一線別歷史參考，"
                "暫無法判定不同線別間之差異。"
            )
