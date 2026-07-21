import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


@st.cache_data(show_spinner=False)
def dataframe_to_csv_bytes(dataframe: pd.DataFrame) -> bytes:
    """Convert a dataframe to UTF-8 BOM CSV once and reuse the result."""
    return dataframe.to_csv(index=False).encode("utf-8-sig")



# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="Seasonal Viscosity Comparison",
    page_icon="🌡️",
    layout="wide",
)

st.title("🌡️ 季節別黏度比較分析")
st.markdown(
    "依月份區分為冬季、春季、夏季及秋季，"
    "比較各期間稀釋劑添加前後黏度、降黏幅度及添加比例差異。"
)


# =========================================================
# 2. LOAD DATA FROM SESSION STATE
# =========================================================
if (
    not st.session_state.get("raw_data_loaded", False)
    or st.session_state.get("group_a_data") is None
):
    st.warning(
        "⚠️ 尚未載入資料，請先返回首頁上傳原始資料。"
        " (Please return to the Main App and upload the raw data first.)"
    )
    st.stop()

df = st.session_state["group_a_data"].copy()


# =========================================================
# 3. DATA PREPARATION
# =========================================================
required_text_cols = [
    "Vendor",
    "Resin",
    "Solvent_Type",
    "塗料批號",
    "線別",
    "塗裝位置",
]

for col in required_text_cols:
    if col not in df.columns:
        df[col] = "Unknown"

    df[col] = (
        df[col]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
    )

# Paint code
df["Paint_Code"] = (
    df.get("塗料編號", pd.Series("Unknown", index=df.index))
    .fillna("Unknown")
    .astype(str)
    .str.strip()
    .str.upper()
)

df["Solvent_Type"] = (
    df["Solvent_Type"]
    .astype(str)
    .str.strip()
    .str.upper()
)

# Replace invalid text
invalid_vals = {
    "",
    "NAN",
    "NONE",
    "NULL",
    "N/A",
    "NA",
    "-",
    "--",
}

df.replace(list(invalid_vals), "Unknown", inplace=True)

# Standard identifiers
df["Batch_ID"] = df["塗料批號"]

df["Bucket_Number"] = (
    df.get("塗料桶號", pd.Series("Unknown", index=df.index))
    .fillna("Unknown")
    .astype(str)
    .str.strip()
)

# Position mapping
position_map = {
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
    .map(position_map)
    .fillna(df["塗裝位置"])
)

# Numeric columns
numeric_cols = [
    "塗料重量",
    "添加重量",
    "黏度(秒)",
    "黏度(秒)_1",
    "溫度",
]

for col in numeric_cols:
    if col not in df.columns:
        df[col] = np.nan

    df[col] = pd.to_numeric(df[col], errors="coerce")


# =========================================================
# 4. CALCULATION LOGIC
# =========================================================
# 塗料重量為添加後累積重量，因此扣除添加重量取得原始塗料重量。
df["Base_Paint_kg"] = df["塗料重量"] - df["添加重量"]

df["Delta_V"] = df["黏度(秒)"] - df["黏度(秒)_1"]

df["Solvent_Ratio_Percent"] = np.where(
    df["Base_Paint_kg"] > 0,
    df["添加重量"] / df["Base_Paint_kg"] * 100,
    np.nan,
)

df["Viscosity_Sensitivity"] = np.where(
    df["Solvent_Ratio_Percent"] > 0,
    df["Delta_V"] / df["Solvent_Ratio_Percent"],
    np.nan,
)

# Strict valid data filter
df = df[
    (df["Base_Paint_kg"] > 0)
    & (df["添加重量"] > 0)
    & (df["黏度(秒)"] > 0)
    & (df["黏度(秒)_1"] > 0)
    & (df["Delta_V"] > 0)
].copy()

if df.empty:
    st.warning("⚠️ 資料清理後無有效黏度調整紀錄。")
    st.stop()


# =========================================================
# 5. DATE PARSING
# =========================================================
date_candidates = [
    "攪拌日期",
    "調整日期",
    "生產日期",
    "Date",
]

date_col = next((col for col in date_candidates if col in df.columns), None)

time_candidates = [
    "攪拌時間",
    "攪拌時間(迄)",
    "Time",
]

time_col = next((col for col in time_candidates if col in df.columns), None)

if date_col is None:
    st.error(
        "❌ 找不到日期欄位。"
        "請確認資料中包含攪拌日期、調整日期、生產日期或 Date。"
    )
    st.stop()

df["_Analysis_Date"] = pd.to_datetime(df[date_col], errors="coerce")
df = df[df["_Analysis_Date"].notna()].copy()

if df.empty:
    st.warning("⚠️ 日期格式無法解析，無法進行季節分析。")
    st.stop()


# =========================================================
# 6. SORTING AND DEDUPLICATION
# =========================================================
sort_cols = ["Batch_ID", "Bucket_Number", "_Analysis_Date"]

if time_col is not None and time_col in df.columns:
    sort_cols.append(time_col)

df = df.sort_values(
    by=sort_cols,
    ascending=True,
    na_position="last",
)

# PS30213X8：大桶每筆為獨立取用與調整，因此保留全部紀錄。
special_paint_codes = ["PS30213X8"]
is_special_paint = df["Paint_Code"].isin(special_paint_codes)

# 一般色號：同批號 + 同桶號為累積紀錄，只保留最後一筆。
df_standard = df[~is_special_paint].copy()
df_standard = df_standard.drop_duplicates(
    subset=["Batch_ID", "Bucket_Number"],
    keep="last",
)

# 特殊色號：保留全部有效紀錄。
df_special = df[is_special_paint].copy()

# Merge
df = pd.concat([df_standard, df_special], ignore_index=True)
df = df.sort_values(
    by=["Batch_ID", "Bucket_Number", "_Analysis_Date"],
    ascending=True,
    na_position="last",
).reset_index(drop=True)


# =========================================================
# 7. SEASON CLASSIFICATION
# =========================================================
def assign_season(month):
    if pd.isna(month):
        return np.nan

    month = int(month)

    if month in [12, 1, 2]:
        return "冬季 (12–02月)"
    if month in [3, 4, 5]:
        return "春季 (03–05月)"
    if month in [6, 7, 8]:
        return "夏季 (06–08月)"
    return "秋季 (09–11月)"


season_order_map = {
    "冬季 (12–02月)": 1,
    "春季 (03–05月)": 2,
    "夏季 (06–08月)": 3,
    "秋季 (09–11月)": 4,
}

df["Month"] = df["_Analysis_Date"].dt.month
df["Season"] = df["Month"].apply(assign_season)
df["Season_Order"] = df["Season"].map(season_order_map)

# 12月歸入下一年度冬季，例如 2025/12 + 2026/01 + 2026/02 = 2026 冬季。
df["Season_Year"] = np.where(
    df["Month"] == 12,
    df["_Analysis_Date"].dt.year + 1,
    df["_Analysis_Date"].dt.year,
)

df["Season_Year"] = pd.Series(
    df["Season_Year"],
    index=df.index,
).astype("Int64")

df["Season_Period"] = (
    df["Season_Year"].astype(str)
    + " "
    + df["Season"].fillna("Unknown")
)


# =========================================================
# 8. GLOBAL FILTERS
# =========================================================
st.markdown("---")
st.subheader("🔍 分析篩選條件")

filter_df = df.copy()

filter_col1, filter_col2, filter_col3 = st.columns(3)
filter_col4, filter_col5, filter_col6 = st.columns(3)

# Vendor
vendor_options = ["All"] + sorted(
    [
        str(value)
        for value in filter_df["Vendor"].unique()
        if value != "Unknown"
    ]
)

selected_vendor = filter_col1.selectbox(
    "Vendor (供應商)",
    vendor_options,
)

if selected_vendor != "All":
    filter_df = filter_df[filter_df["Vendor"] == selected_vendor]

# Resin
resin_options = ["All"] + sorted(
    [
        str(value)
        for value in filter_df["Resin"].unique()
        if value != "Unknown"
    ]
)

selected_resin = filter_col2.selectbox(
    "Resin Type (樹脂種類)",
    resin_options,
)

if selected_resin != "All":
    filter_df = filter_df[filter_df["Resin"] == selected_resin]

# Position
position_options = ["All"] + sorted(
    [
        str(value)
        for value in filter_df["Position_UI"].unique()
        if value != "Unknown"
    ]
)

selected_position = filter_col3.selectbox(
    "Coating Position (塗裝位置)",
    position_options,
)

if selected_position != "All":
    filter_df = filter_df[
        filter_df["Position_UI"] == selected_position
    ]

# Solvent
solvent_options = ["All"] + sorted(
    [
        str(value)
        for value in filter_df["Solvent_Type"].unique()
        if value != "Unknown"
    ]
)

selected_solvent = filter_col4.selectbox(
    "Solvent Type (稀釋劑種類)",
    solvent_options,
)

if selected_solvent != "All":
    filter_df = filter_df[
        filter_df["Solvent_Type"] == selected_solvent
    ]

# Production line
line_options = sorted(
    [
        str(value)
        for value in filter_df["線別"].unique()
        if value != "Unknown"
    ]
)

selected_lines = filter_col5.multiselect(
    "Production Line (產線)",
    line_options,
    default=line_options,
)

if selected_lines:
    filter_df = filter_df[filter_df["線別"].isin(selected_lines)]
else:
    st.warning("⚠️ 請至少選擇一條產線。")
    st.stop()

# Analysis mode
analysis_mode = filter_col6.selectbox(
    "分析方式 (Analysis Mode)",
    [
        "合併各年度比較四季",
        "依季節年度比較",
    ],
)

if filter_df.empty:
    st.warning("⚠️ 無符合目前篩選條件的資料。")
    st.stop()


# =========================================================
# 9. ALL PAINT CODES — SEASONAL VISCOSITY OVERVIEW MATRIX
# =========================================================
st.markdown("---")
st.subheader("🧭 全色號季節黏度總覽")
st.markdown(
    "先以矩陣同時檢視多個色號於四季之添加前後黏度，"
    "再於下方選擇單一色號進行詳細分析。"
)

# Aggregate all paint codes by the four fixed seasonal periods.
overview_df = (
    filter_df.groupby(
        ["Paint_Code", "Season_Order", "Season"],
        dropna=False,
    )
    .agg(
        Historical_Records=("Paint_Code", "size"),
        Historical_Batches=("Batch_ID", "nunique"),
        Median_Before_Viscosity=("黏度(秒)", "median"),
        Median_After_Viscosity=("黏度(秒)_1", "median"),
        Median_Viscosity_Drop=("Delta_V", "median"),
        Median_Solvent_Ratio=("Solvent_Ratio_Percent", "median"),
        Median_Temperature=("溫度", "median"),
        Total_Solvent_kg=("添加重量", "sum"),
    )
    .reset_index()
)

paint_overview_rank = (
    filter_df.groupby("Paint_Code", dropna=False)
    .agg(
        Total_Records=("Paint_Code", "size"),
        Total_Solvent_kg=("添加重量", "sum"),
    )
    .reset_index()
)

view_col1, view_col2 = st.columns([1, 2])

with view_col1:
    overview_scope = st.selectbox(
        "顯示範圍",
        [
            "歷史紀錄數 Top 20",
            "稀釋劑用量 Top 20",
            "稀釋劑用量 Top 10",
            "全部色號",
            "自訂選擇",
        ],
        key="season_overview_scope",
    )

all_overview_codes = (
    paint_overview_rank["Paint_Code"]
    .dropna()
    .astype(str)
    .tolist()
)

if overview_scope == "歷史紀錄數 Top 20":
    default_overview_codes = (
        paint_overview_rank.sort_values(
            "Total_Records",
            ascending=False,
        )
        .head(20)["Paint_Code"]
        .astype(str)
        .tolist()
    )
elif overview_scope == "稀釋劑用量 Top 20":
    default_overview_codes = (
        paint_overview_rank.sort_values(
            "Total_Solvent_kg",
            ascending=False,
        )
        .head(20)["Paint_Code"]
        .astype(str)
        .tolist()
    )
elif overview_scope == "全部色號":
    default_overview_codes = all_overview_codes
else:
    default_overview_codes = all_overview_codes[:10]

# Synchronize the paint-code selector whenever the display scope changes.
# Streamlit keeps multiselect values in session_state, so changing only
# the `default` argument does not update an already-created widget.
previous_overview_scope = st.session_state.get(
    "_previous_season_overview_scope"
)

scope_changed = previous_overview_scope != overview_scope

if scope_changed:
    st.session_state["season_overview_codes"] = (
        default_overview_codes.copy()
    )
    st.session_state["_previous_season_overview_scope"] = (
        overview_scope
    )
else:
    # Remove selections that are no longer available after upper filters change.
    current_overview_codes = st.session_state.get(
        "season_overview_codes",
        default_overview_codes,
    )
    valid_current_codes = [
        code
        for code in current_overview_codes
        if code in all_overview_codes
    ]

    if overview_scope != "自訂選擇":
        # Top 20 / All modes always follow the calculated ranking exactly.
        valid_current_codes = default_overview_codes.copy()
    elif not valid_current_codes:
        valid_current_codes = default_overview_codes.copy()

    st.session_state["season_overview_codes"] = valid_current_codes

with view_col2:
    selected_overview_codes = st.multiselect(
        "選擇要同時比較的色號",
        options=all_overview_codes,
        key="season_overview_codes",
        disabled=(overview_scope != "自訂選擇"),
        help=(
            "Top 20／全部色號模式會自動同步；"
            "選擇「自訂選擇」後可自行增減色號。"
        ),
    )

if selected_overview_codes:
    matrix_source = overview_df[
        overview_df["Paint_Code"].isin(selected_overview_codes)
    ].copy()

    # Keep the displayed code order aligned with the selected ranking/order.
    code_order = [
        code
        for code in default_overview_codes
        if code in selected_overview_codes
    ]
    code_order += [
        code
        for code in selected_overview_codes
        if code not in code_order
    ]

    season_labels = [
        "冬季 (12–02月)",
        "春季 (03–05月)",
        "夏季 (06–08月)",
        "秋季 (09–11月)",
    ]

    before_pivot = matrix_source.pivot_table(
        index="Paint_Code",
        columns="Season",
        values="Median_Before_Viscosity",
        aggfunc="first",
    ).reindex(index=code_order, columns=season_labels)

    after_pivot = matrix_source.pivot_table(
        index="Paint_Code",
        columns="Season",
        values="Median_After_Viscosity",
        aggfunc="first",
    ).reindex(index=code_order, columns=season_labels)

    drop_pivot = matrix_source.pivot_table(
        index="Paint_Code",
        columns="Season",
        values="Median_Viscosity_Drop",
        aggfunc="first",
    ).reindex(index=code_order, columns=season_labels)

    ratio_pivot = matrix_source.pivot_table(
        index="Paint_Code",
        columns="Season",
        values="Median_Solvent_Ratio",
        aggfunc="first",
    ).reindex(index=code_order, columns=season_labels)

    temp_pivot = matrix_source.pivot_table(
        index="Paint_Code",
        columns="Season",
        values="Median_Temperature",
        aggfunc="first",
    ).reindex(index=code_order, columns=season_labels)

    records_pivot = matrix_source.pivot_table(
        index="Paint_Code",
        columns="Season",
        values="Historical_Records",
        aggfunc="first",
    ).reindex(index=code_order, columns=season_labels)

    batches_pivot = matrix_source.pivot_table(
        index="Paint_Code",
        columns="Season",
        values="Historical_Batches",
        aggfunc="first",
    ).reindex(index=code_order, columns=season_labels)

    cell_text = []
    customdata = []

    for code in code_order:
        text_row = []
        custom_row = []

        for season_name in season_labels:
            before_value = before_pivot.loc[code, season_name]
            after_value = after_pivot.loc[code, season_name]
            drop_value = drop_pivot.loc[code, season_name]
            ratio_value = ratio_pivot.loc[code, season_name]
            temp_value = temp_pivot.loc[code, season_name]
            records_value = records_pivot.loc[code, season_name]
            batches_value = batches_pivot.loc[code, season_name]

            if pd.notna(before_value) and pd.notna(after_value):
                ratio_text = (
                    f"{ratio_value:.1f}%"
                    if pd.notna(ratio_value)
                    else "—"
                )
                text_row.append(
                    f"<b>{before_value:.0f} → {after_value:.0f}</b>"
                    f"<br>{ratio_text}"
                )
            else:
                text_row.append("—")

            custom_row.append(
                [
                    before_value,
                    after_value,
                    drop_value,
                    ratio_value,
                    temp_value,
                    records_value,
                    batches_value,
                ]
            )

        cell_text.append(text_row)
        customdata.append(custom_row)

    z_values = drop_pivot.to_numpy(dtype=float)

    fig_overview = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=season_labels,
            y=code_order,
            text=cell_text,
            texttemplate="%{text}",
            textfont=dict(size=12, color="#111827"),
            customdata=np.array(customdata, dtype=object),
            colorscale=[
                [0.00, "#EFF6FF"],
                [0.35, "#BFDBFE"],
                [0.70, "#60A5FA"],
                [1.00, "#1D4ED8"],
            ],
            colorbar=dict(
                title="降黏幅度<br>(秒)",
                thickness=14,
                len=0.80,
                outlinecolor="#64748B",
                outlinewidth=1,
            ),
            xgap=2,
            ygap=2,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "%{x}<br>"
                "添加前黏度中位數：%{customdata[0]:.1f} s<br>"
                "添加後黏度中位數：%{customdata[1]:.1f} s<br>"
                "降黏幅度中位數：%{customdata[2]:.1f} s<br>"
                "添加比例中位數：%{customdata[3]:.2f}%<br>"
                "溫度中位數：%{customdata[4]:.1f} °C<br>"
                "歷史紀錄數：%{customdata[5]:,.0f}<br>"
                "歷史批數：%{customdata[6]:,.0f}"
                "<extra></extra>"
            ),
            hoverongaps=False,
        )
    )

    fig_overview.update_xaxes(
        title="季節期間",
        side="top",
        showline=True,
        linecolor="#475569",
        linewidth=1.5,
        mirror=True,
        ticks="outside",
        ticklen=6,
        tickfont=dict(size=12),
    )

    fig_overview.update_yaxes(
        title="色號",
        autorange="reversed",
        showline=True,
        linecolor="#475569",
        linewidth=1.5,
        mirror=True,
        ticks="outside",
        ticklen=5,
        tickfont=dict(size=11),
    )

    fig_overview.update_layout(
        title=(
            "<b>全色號季節添加前後黏度矩陣</b>"
            "<br><sup>第一行＝添加前 → 添加後；第二行＝稀釋劑添加比例；底色＝降黏幅度</sup>"
        ),
        height=max(520, len(code_order) * 42 + 180),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=130, r=80, t=145, b=65),
        font=dict(
            family="Arial, Microsoft JhengHei, sans-serif",
            size=12,
            color="#334155",
        ),
    )

    st.plotly_chart(fig_overview, use_container_width=True)

    st.caption(
        "每一格第一行顯示添加前 → 添加後黏度中位數，第二行顯示"
        "稀釋劑添加比例中位數；底色越深代表典型降黏幅度越大。"
        "將游標移至儲存格可查看溫度、紀錄數及批數。"
    )

    # =====================================================
    # OPTIMIZED WIDE TABLE — ONE PAINT CODE PER ROW
    # =====================================================
    st.markdown("---")
    st.subheader("📋 全色號季節比較總表")
    st.caption(
        "每個色號僅顯示一列；各季節欄位以「添加前 → 添加後」呈現，"
        "並搭配添加比例，以利快速橫向比較。"
    )

    season_short_map = {
        "冬季 (12–02月)": "冬季",
        "春季 (03–05月)": "春季",
        "夏季 (06–08月)": "夏季",
        "秋季 (09–11月)": "秋季",
    }
    season_short_order = ["冬季", "春季", "夏季", "秋季"]

    wide_source = matrix_source.copy()
    wide_source["Season_Short"] = wide_source["Season"].map(
        season_short_map
    )
    wide_source["Before_After"] = wide_source.apply(
        lambda row: (
            f"{row['Median_Before_Viscosity']:.0f} → "
            f"{row['Median_After_Viscosity']:.0f}"
        )
        if pd.notna(row["Median_Before_Viscosity"])
        and pd.notna(row["Median_After_Viscosity"])
        else "—",
        axis=1,
    )

    before_after_wide = wide_source.pivot_table(
        index="Paint_Code",
        columns="Season_Short",
        values="Before_After",
        aggfunc="first",
    ).reindex(index=code_order, columns=season_short_order)

    ratio_wide = wide_source.pivot_table(
        index="Paint_Code",
        columns="Season_Short",
        values="Median_Solvent_Ratio",
        aggfunc="first",
    ).reindex(index=code_order, columns=season_short_order)

    before_wide = wide_source.pivot_table(
        index="Paint_Code",
        columns="Season_Short",
        values="Median_Before_Viscosity",
        aggfunc="first",
    ).reindex(index=code_order, columns=season_short_order)

    after_wide = wide_source.pivot_table(
        index="Paint_Code",
        columns="Season_Short",
        values="Median_After_Viscosity",
        aggfunc="first",
    ).reindex(index=code_order, columns=season_short_order)

    code_totals = (
        filter_df[
            filter_df["Paint_Code"].isin(selected_overview_codes)
        ]
        .groupby("Paint_Code", dropna=False)
        .agg(
            Total_Records=("Paint_Code", "size"),
            Total_Batches=("Batch_ID", "nunique"),
            Total_Solvent_kg=("添加重量", "sum"),
        )
        .reindex(code_order)
    )

    wide_display = pd.DataFrame(index=code_order)
    wide_display.index.name = "色號"
    wide_display["歷史紀錄數"] = code_totals["Total_Records"]
    wide_display["歷史批數"] = code_totals["Total_Batches"]

    for season_name in season_short_order:
        wide_display[f"{season_name} 前→後"] = before_after_wide[
            season_name
        ].fillna("—")
        wide_display[f"{season_name} 添加比"] = ratio_wide[
            season_name
        ]

    # Seasonal difference uses the spread of median before-viscosity.
    wide_display["添加前季節差異"] = (
        before_wide.max(axis=1, skipna=True)
        - before_wide.min(axis=1, skipna=True)
    )
    wide_display["添加後季節差異"] = (
        after_wide.max(axis=1, skipna=True)
        - after_wide.min(axis=1, skipna=True)
    )
    wide_display["稀釋劑總用量"] = code_totals["Total_Solvent_kg"]

    available_season_count = before_wide.notna().sum(axis=1)

    def classify_season_difference(row):
        code = row.name
        season_count = int(available_season_count.get(code, 0))
        before_gap = row["添加前季節差異"]
        after_gap = row["添加後季節差異"]

        if season_count < 2 or pd.isna(before_gap):
            return "資料不足"
        if before_gap <= 5 and (pd.isna(after_gap) or after_gap <= 5):
            return "穩定"
        if before_gap <= 10 and (pd.isna(after_gap) or after_gap <= 8):
            return "輕微差異"
        return "季節差異明顯"

    wide_display["判定"] = wide_display.apply(
        classify_season_difference,
        axis=1,
    )
    wide_display = wide_display.reset_index()

    table_filter_col1, table_filter_col2, table_filter_col3 = st.columns(
        [1.1, 1.1, 1.4]
    )

    with table_filter_col1:
        table_result_filter = st.selectbox(
            "判定篩選",
            [
                "全部",
                "季節差異明顯",
                "輕微差異",
                "穩定",
                "資料不足",
            ],
            key="season_wide_result_filter",
        )

    with table_filter_col2:
        table_sort_mode = st.selectbox(
            "排序方式",
            [
                "依目前選擇順序",
                "添加前季節差異由大到小",
                "添加後季節差異由大到小",
                "歷史紀錄數由多到少",
                "稀釋劑用量由高到低",
            ],
            key="season_wide_sort_mode",
        )

    with table_filter_col3:
        table_search_text = st.text_input(
            "搜尋色號",
            placeholder="輸入部分色號，例如 13X8",
            key="season_wide_search",
        )

    wide_filtered = wide_display.copy()

    if table_result_filter != "全部":
        wide_filtered = wide_filtered[
            wide_filtered["判定"] == table_result_filter
        ]

    if table_search_text.strip():
        wide_filtered = wide_filtered[
            wide_filtered["色號"].astype(str).str.contains(
                table_search_text.strip(),
                case=False,
                na=False,
            )
        ]

    if table_sort_mode == "添加前季節差異由大到小":
        wide_filtered = wide_filtered.sort_values(
            "添加前季節差異",
            ascending=False,
            na_position="last",
        )
    elif table_sort_mode == "添加後季節差異由大到小":
        wide_filtered = wide_filtered.sort_values(
            "添加後季節差異",
            ascending=False,
            na_position="last",
        )
    elif table_sort_mode == "歷史紀錄數由多到少":
        wide_filtered = wide_filtered.sort_values(
            "歷史紀錄數",
            ascending=False,
            na_position="last",
        )
    elif table_sort_mode == "稀釋劑用量由高到低":
        wide_filtered = wide_filtered.sort_values(
            "稀釋劑總用量",
            ascending=False,
            na_position="last",
        )
    else:
        wide_filtered["_Order"] = pd.Categorical(
            wide_filtered["色號"],
            categories=code_order,
            ordered=True,
        )
        wide_filtered = wide_filtered.sort_values("_Order").drop(
            columns="_Order"
        )

    st.info(
        f"目前顯示 **{len(wide_filtered):,}** 個色號。"
        "『添加前季節差異』與『添加後季節差異』皆為四季中位數最大值減最小值。"
    )

    wide_column_config = {
        "色號": st.column_config.TextColumn("色號", width="medium"),
        "歷史紀錄數": st.column_config.NumberColumn(
            "歷史紀錄數", format="%d", width="small"
        ),
        "歷史批數": st.column_config.NumberColumn(
            "歷史批數", format="%d", width="small"
        ),
        "冬季 前→後": st.column_config.TextColumn(
            "冬季 前→後 (s)", width="small"
        ),
        "冬季 添加比": st.column_config.NumberColumn(
            "冬季 添加比 (%)", format="%.1f", width="small"
        ),
        "春季 前→後": st.column_config.TextColumn(
            "春季 前→後 (s)", width="small"
        ),
        "春季 添加比": st.column_config.NumberColumn(
            "春季 添加比 (%)", format="%.1f", width="small"
        ),
        "夏季 前→後": st.column_config.TextColumn(
            "夏季 前→後 (s)", width="small"
        ),
        "夏季 添加比": st.column_config.NumberColumn(
            "夏季 添加比 (%)", format="%.1f", width="small"
        ),
        "秋季 前→後": st.column_config.TextColumn(
            "秋季 前→後 (s)", width="small"
        ),
        "秋季 添加比": st.column_config.NumberColumn(
            "秋季 添加比 (%)", format="%.1f", width="small"
        ),
        "添加前季節差異": st.column_config.NumberColumn(
            "添加前季節差異 (s)", format="%.1f", width="small"
        ),
        "添加後季節差異": st.column_config.NumberColumn(
            "添加後季節差異 (s)", format="%.1f", width="small"
        ),
        "稀釋劑總用量": st.column_config.NumberColumn(
            "稀釋劑總用量 (kg)", format="%.1f", width="small"
        ),
        "判定": st.column_config.TextColumn("判定", width="small"),
    }

    st.dataframe(
        wide_filtered,
        column_config=wide_column_config,
        use_container_width=True,
        hide_index=True,
        height=min(760, max(240, len(wide_filtered) * 35 + 38)),
    )

    wide_csv = dataframe_to_csv_bytes(wide_filtered)
    st.download_button(
        label="下載全色號季節橫向比較表 CSV",
        data=wide_csv,
        file_name="Seasonal_Viscosity_All_Paint_Codes_Wide.csv",
        mime="text/csv",
        key="download_wide_overview_csv",
        on_click="ignore",
    )

else:
    st.info("請至少選擇一個色號以產生季節黏度總覽矩陣。")


# =========================================================
# 10. PAINT CODE FILTER — DETAILED SINGLE-CODE ANALYSIS
# =========================================================
st.markdown("---")
st.subheader("🔎 單一色號詳細分析")
paint_code_count_df = (
    filter_df.groupby("Paint_Code")
    .size()
    .reset_index(name="Records")
    .sort_values("Records", ascending=False)
)

paint_code_options = paint_code_count_df["Paint_Code"].tolist()

if not paint_code_options:
    st.warning("⚠️ 無可分析色號。")
    st.stop()

selected_paint_code = st.selectbox(
    "選擇分析色號 (Select Paint Code)",
    paint_code_options,
)

analysis_df = filter_df[
    filter_df["Paint_Code"] == selected_paint_code
].copy()

if analysis_df.empty:
    st.warning("⚠️ 此色號無有效資料。")
    st.stop()


# =========================================================
# 11. FILTER INFORMATION
# =========================================================
min_date = analysis_df["_Analysis_Date"].min().strftime("%Y-%m-%d")
max_date = analysis_df["_Analysis_Date"].max().strftime("%Y-%m-%d")

filter_details = (
    f"Vendor: {selected_vendor} | "
    f"Resin: {selected_resin} | "
    f"Position: {selected_position} | "
    f"Solvent: {selected_solvent} | "
    f"Paint Code: {selected_paint_code}"
)

st.info(
    f"📅 **資料期間：** {min_date} ➔ {max_date}"
    f" ｜ 📊 **有效紀錄數：** {len(analysis_df):,} 筆"
    f" ｜ 🎨 **色號：** {selected_paint_code}"
)


# =========================================================
# 12. SEASONAL AGGREGATION
# =========================================================
if analysis_mode == "合併各年度比較四季":
    group_cols = ["Season_Order", "Season"]
    period_col = "Season"
else:
    group_cols = [
        "Season_Year",
        "Season_Order",
        "Season",
        "Season_Period",
    ]
    period_col = "Season_Period"

season_summary = (
    analysis_df.groupby(group_cols, dropna=False)
    .agg(
        Historical_Records=("Paint_Code", "size"),
        Historical_Batches=("Batch_ID", "nunique"),
        Median_Before_Viscosity=("黏度(秒)", "median"),
        Mean_Before_Viscosity=("黏度(秒)", "mean"),
        Before_P25=("黏度(秒)", lambda x: x.quantile(0.25)),
        Before_P75=("黏度(秒)", lambda x: x.quantile(0.75)),
        Median_After_Viscosity=("黏度(秒)_1", "median"),
        Mean_After_Viscosity=("黏度(秒)_1", "mean"),
        After_P25=("黏度(秒)_1", lambda x: x.quantile(0.25)),
        After_P75=("黏度(秒)_1", lambda x: x.quantile(0.75)),
        Median_Viscosity_Drop=("Delta_V", "median"),
        Median_Solvent_Ratio=("Solvent_Ratio_Percent", "median"),
        Total_Solvent_kg=("添加重量", "sum"),
        Median_Temperature=("溫度", "median"),
    )
    .reset_index()
)

if analysis_mode == "合併各年度比較四季":
    season_summary = season_summary.sort_values(by=["Season_Order"])
else:
    season_summary = season_summary.sort_values(
        by=["Season_Year", "Season_Order"]
    )

if season_summary.empty:
    st.warning("⚠️ 此色號無足夠季節資料。")
    st.stop()

season_summary = season_summary.reset_index(drop=True)


# =========================================================
# 13. KPI SUMMARY
# =========================================================
st.markdown("---")
st.subheader("📌 季節比較摘要")

highest_before_row = season_summary.loc[
    season_summary["Median_Before_Viscosity"].idxmax()
]

lowest_before_row = season_summary.loc[
    season_summary["Median_Before_Viscosity"].idxmin()
]

largest_drop_row = season_summary.loc[
    season_summary["Median_Viscosity_Drop"].idxmax()
]

highest_ratio_row = season_summary.loc[
    season_summary["Median_Solvent_Ratio"].idxmax()
]

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

kpi1.metric(
    "最高添加前黏度期間",
    str(highest_before_row[period_col]),
    f"{highest_before_row['Median_Before_Viscosity']:.1f} s",
)

kpi2.metric(
    "最低添加前黏度期間",
    str(lowest_before_row[period_col]),
    f"{lowest_before_row['Median_Before_Viscosity']:.1f} s",
)

kpi3.metric(
    "最大降黏期間",
    str(largest_drop_row[period_col]),
    f"{largest_drop_row['Median_Viscosity_Drop']:.1f} s",
)

kpi4.metric(
    "最高添加比例期間",
    str(highest_ratio_row[period_col]),
    f"{highest_ratio_row['Median_Solvent_Ratio']:.1f}%",
)


# =========================================================
# 14. CHART 1 — BEFORE VS AFTER DUMBBELL
# =========================================================
st.markdown("---")
st.subheader("圖1　各季節添加前後黏度比較")

fig_before_after = go.Figure()
period_values = season_summary[period_col].astype(str).tolist()

# Connection lines
for _, row in season_summary.iterrows():
    period_name = str(row[period_col])

    fig_before_after.add_trace(
        go.Scatter(
            x=[
                row["Median_After_Viscosity"],
                row["Median_Before_Viscosity"],
            ],
            y=[period_name, period_name],
            mode="lines",
            line=dict(color="#94A3B8", width=5),
            hoverinfo="skip",
            showlegend=False,
        )
    )

# Before viscosity
fig_before_after.add_trace(
    go.Scatter(
        x=season_summary["Median_Before_Viscosity"],
        y=season_summary[period_col].astype(str),
        mode="markers+text",
        name="添加前黏度",
        marker=dict(
            size=17,
            color="#D97706",
            line=dict(color="white", width=1.5),
        ),
        text=season_summary["Median_Before_Viscosity"].map(
            lambda value: f"{value:.1f}"
        ),
        textposition="top center",
        customdata=np.column_stack(
            [
                season_summary["Historical_Records"],
                season_summary["Historical_Batches"],
                season_summary["Median_Solvent_Ratio"],
                season_summary["Median_Temperature"],
                season_summary["Before_P25"],
                season_summary["Before_P75"],
            ]
        ),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "添加前黏度中位數：%{x:.1f} s<br>"
            "添加前黏度 P25–P75："
            "%{customdata[4]:.1f}–%{customdata[5]:.1f} s<br>"
            "歷史紀錄數：%{customdata[0]:,.0f}<br>"
            "歷史批數：%{customdata[1]:,.0f}<br>"
            "添加比例中位數：%{customdata[2]:.2f}%<br>"
            "溫度中位數：%{customdata[3]:.1f} °C"
            "<extra></extra>"
        ),
    )
)

# After viscosity
fig_before_after.add_trace(
    go.Scatter(
        x=season_summary["Median_After_Viscosity"],
        y=season_summary[period_col].astype(str),
        mode="markers+text",
        name="添加後黏度",
        marker=dict(
            size=17,
            color="#2563EB",
            line=dict(color="white", width=1.5),
        ),
        text=season_summary["Median_After_Viscosity"].map(
            lambda value: f"{value:.1f}"
        ),
        textposition="bottom center",
        customdata=np.column_stack(
            [
                season_summary["Median_Viscosity_Drop"],
                season_summary["Historical_Records"],
                season_summary["Historical_Batches"],
                season_summary["Median_Solvent_Ratio"],
                season_summary["After_P25"],
                season_summary["After_P75"],
            ]
        ),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "添加後黏度中位數：%{x:.1f} s<br>"
            "添加後黏度 P25–P75："
            "%{customdata[4]:.1f}–%{customdata[5]:.1f} s<br>"
            "降黏幅度中位數：%{customdata[0]:.1f} s<br>"
            "歷史紀錄數：%{customdata[1]:,.0f}<br>"
            "歷史批數：%{customdata[2]:,.0f}<br>"
            "添加比例中位數：%{customdata[3]:.2f}%"
            "<extra></extra>"
        ),
    )
)

fig_before_after.update_xaxes(
    title="黏度 (秒)",
    showgrid=True,
    gridcolor="#D6DCE5",
    gridwidth=1,
    showline=True,
    linecolor="#4B5563",
    linewidth=1.5,
    mirror=True,
    ticks="outside",
    ticklen=6,
    tickwidth=1.2,
    tickcolor="#4B5563",
    zeroline=False,
)

fig_before_after.update_yaxes(
    title="季節期間",
    categoryorder="array",
    categoryarray=period_values,
    showgrid=True,
    gridcolor="#E5E7EB",
    gridwidth=1,
    showline=True,
    linecolor="#4B5563",
    linewidth=1.5,
    mirror=True,
    ticks="outside",
    ticklen=6,
)

fig_before_after.update_layout(
    title=(
        f"<b>{selected_paint_code} 各季節添加前後黏度比較</b>"
        f"<br><sup>{filter_details}</sup>"
    ),
    height=max(540, len(season_summary) * 78),
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(l=145, r=55, t=130, b=85),
    font=dict(
        family="Arial, Microsoft JhengHei, sans-serif",
        size=12,
        color="#374151",
    ),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.06,
        xanchor="right",
        x=1,
        bgcolor="rgba(255,255,255,0.92)",
        bordercolor="#CBD5E1",
        borderwidth=1,
    ),
)

st.plotly_chart(fig_before_after, use_container_width=True)

st.caption(
    "橘色點為添加前黏度中位數，藍色點為添加後黏度中位數；"
    "兩點距離代表該期間典型降黏幅度。"
)


# =========================================================
# 15. CHART 2 — SEASONAL TREND
#     Label overlap fixed with separate annotations.
# =========================================================
st.markdown("---")
st.subheader("圖2　各季節黏度與添加比例趨勢")

fig_trend = go.Figure()
period_series = season_summary[period_col].astype(str)

# 添加前黏度：保留文字，但統一往上。
fig_trend.add_trace(
    go.Scatter(
        x=period_series,
        y=season_summary["Median_Before_Viscosity"],
        mode="lines+markers+text",
        name="添加前黏度",
        line=dict(color="#D97706", width=3),
        marker=dict(size=10),
        text=season_summary["Median_Before_Viscosity"].map(
            lambda value: f"{value:.1f}"
        ),
        textposition="top center",
        textfont=dict(size=11, color="#92400E"),
        cliponaxis=False,
        yaxis="y1",
    )
)

# 添加後黏度：文字往下。
fig_trend.add_trace(
    go.Scatter(
        x=period_series,
        y=season_summary["Median_After_Viscosity"],
        mode="lines+markers+text",
        name="添加後黏度",
        line=dict(color="#2563EB", width=3),
        marker=dict(size=10),
        text=season_summary["Median_After_Viscosity"].map(
            lambda value: f"{value:.1f}"
        ),
        textposition="bottom center",
        textfont=dict(size=11, color="#1D4ED8"),
        cliponaxis=False,
        yaxis="y1",
    )
)

# 添加比例：不直接顯示 trace 文字，改用 annotation 避免與黏度標籤重疊。
fig_trend.add_trace(
    go.Scatter(
        x=period_series,
        y=season_summary["Median_Solvent_Ratio"],
        mode="lines+markers",
        name="添加比例",
        line=dict(color="#059669", width=3, dash="dot"),
        marker=dict(size=10, symbol="diamond"),
        yaxis="y2",
        customdata=np.column_stack(
            [
                season_summary["Historical_Records"],
                season_summary["Median_Temperature"],
            ]
        ),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "添加比例中位數：%{y:.1f}%<br>"
            "歷史紀錄數：%{customdata[0]:,.0f}<br>"
            "溫度中位數：%{customdata[1]:.1f} °C"
            "<extra></extra>"
        ),
    )
)

# 添加比例標籤：第一個點向右移，其餘點往上，避免與添加前黏度重疊。
for i, row in season_summary.iterrows():
    xshift = 24 if i == 0 else 0
    yshift = 14

    fig_trend.add_annotation(
        x=str(row[period_col]),
        y=row["Median_Solvent_Ratio"],
        xref="x",
        yref="y2",
        text=f"{row['Median_Solvent_Ratio']:.1f}%",
        showarrow=False,
        xshift=xshift,
        yshift=yshift,
        font=dict(size=11, color="#047857"),
        bgcolor="rgba(255,255,255,0.90)",
        bordercolor="rgba(4,120,87,0.25)",
        borderwidth=1,
        borderpad=2,
    )

fig_trend.update_layout(
    title=(
        f"<b>{selected_paint_code} 各季節黏度與添加比例趨勢</b>"
    ),
    height=590,
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(l=75, r=105, t=145, b=85),
    xaxis=dict(
        title="季節期間",
        categoryorder="array",
        categoryarray=period_values,
        showgrid=False,
        showline=True,
        linecolor="#4B5563",
        linewidth=1.5,
        mirror=True,
        ticks="outside",
    ),
    yaxis=dict(
        title="黏度 (秒)",
        side="left",
        showgrid=True,
        gridcolor="#D6DCE5",
        gridwidth=1,
        showline=True,
        linecolor="#4B5563",
        linewidth=1.5,
        mirror=True,
        zeroline=False,
    ),
    yaxis2=dict(
        title="添加比例 (%)",
        overlaying="y",
        side="right",
        showgrid=False,
        showline=True,
        linecolor="#4B5563",
        linewidth=1.5,
        zeroline=False,
    ),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.07,
        xanchor="right",
        x=1,
        bgcolor="rgba(255,255,255,0.92)",
        bordercolor="#CBD5E1",
        borderwidth=1,
    ),
    font=dict(
        family="Arial, Microsoft JhengHei, sans-serif",
        size=12,
        color="#374151",
    ),
)

st.plotly_chart(fig_trend, use_container_width=True)


# =========================================================
# 16. SUMMARY TABLE
# =========================================================
st.markdown("---")
st.subheader("📋 季節比較明細")

season_display = season_summary[
    [
        period_col,
        "Historical_Records",
        "Historical_Batches",
        "Median_Before_Viscosity",
        "Median_After_Viscosity",
        "Median_Viscosity_Drop",
        "Median_Solvent_Ratio",
        "Total_Solvent_kg",
        "Median_Temperature",
    ]
].copy()

season_display = season_display.rename(
    columns={
        period_col: "季節期間",
        "Historical_Records": "歷史紀錄數",
        "Historical_Batches": "歷史批數",
        "Median_Before_Viscosity": "添加前黏度中位數",
        "Median_After_Viscosity": "添加後黏度中位數",
        "Median_Viscosity_Drop": "降黏幅度中位數",
        "Median_Solvent_Ratio": "添加比例中位數",
        "Total_Solvent_kg": "稀釋劑總用量",
        "Median_Temperature": "溫度中位數",
    }
)

round_cols = [
    "添加前黏度中位數",
    "添加後黏度中位數",
    "降黏幅度中位數",
    "添加比例中位數",
    "稀釋劑總用量",
    "溫度中位數",
]

season_display[round_cols] = season_display[round_cols].round(1)

st.dataframe(
    season_display,
    column_config={
        "季節期間": "季節期間",
        "歷史紀錄數": st.column_config.NumberColumn(
            "歷史紀錄數",
            format="%d",
        ),
        "歷史批數": st.column_config.NumberColumn(
            "歷史批數",
            format="%d",
        ),
        "添加前黏度中位數": st.column_config.NumberColumn(
            "添加前黏度中位數 (s)",
            format="%.1f",
        ),
        "添加後黏度中位數": st.column_config.NumberColumn(
            "添加後黏度中位數 (s)",
            format="%.1f",
        ),
        "降黏幅度中位數": st.column_config.NumberColumn(
            "降黏幅度中位數 (s)",
            format="%.1f",
        ),
        "添加比例中位數": st.column_config.NumberColumn(
            "添加比例中位數 (%)",
            format="%.1f",
        ),
        "稀釋劑總用量": st.column_config.NumberColumn(
            "稀釋劑總用量 (kg)",
            format="%.1f",
        ),
        "溫度中位數": st.column_config.NumberColumn(
            "溫度中位數 (°C)",
            format="%.1f",
        ),
    },
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# 17. AUTOMATIC COMMENTARY
# =========================================================
st.markdown("---")
st.subheader("📝 自動分析摘要")

before_range = (
    season_summary["Median_Before_Viscosity"].max()
    - season_summary["Median_Before_Viscosity"].min()
)

after_range = (
    season_summary["Median_After_Viscosity"].max()
    - season_summary["Median_After_Viscosity"].min()
)

ratio_range = (
    season_summary["Median_Solvent_Ratio"].max()
    - season_summary["Median_Solvent_Ratio"].min()
)

st.markdown(
    f"""
- **添加前黏度最高期間：**
  {highest_before_row[period_col]}，中位數為 **{highest_before_row['Median_Before_Viscosity']:.1f} 秒**。

- **添加前黏度最低期間：**
  {lowest_before_row[period_col]}，中位數為 **{lowest_before_row['Median_Before_Viscosity']:.1f} 秒**。

- 各期間添加前黏度最大差異為 **{before_range:.1f} 秒**。

- 各期間添加後黏度最大差異為 **{after_range:.1f} 秒**。

- 各期間添加比例中位數最大差異為 **{ratio_range:.1f} 個百分點**。
"""
)

if before_range >= 10:
    st.info(
        "添加前黏度於不同季節間有較明顯差異，"
        "建議後續確認溫度、儲存條件及塗料批次是否為主要影響因素。"
    )
else:
    st.success(
        "添加前黏度於各季節間差異不大，整體季節變動相對有限。"
    )

if after_range <= 5:
    st.success(
        "添加後黏度各季節差異較小，顯示現場調整後結果大致一致。"
    )
else:
    st.warning(
        "添加後黏度於不同季節仍有差異，"
        "建議確認各季節目標黏度及稀釋劑添加方式是否一致。"
    )


# =========================================================
# 18. EXPORT CSV
# =========================================================
st.markdown("---")
st.subheader("📥 資料匯出")

csv_data = dataframe_to_csv_bytes(season_display)

st.download_button(
    label="下載季節黏度比較表 CSV",
    data=csv_data,
    file_name=f"Seasonal_Viscosity_{selected_paint_code}.csv",
    mime="text/csv",
    on_click="ignore",
)


# =========================================================
# 19. EXPORT INTERACTIVE HTML REPORT
# =========================================================
if st.button("產生互動式季節分析報告 HTML", type="primary"):
    try:
        chart1_html = fig_before_after.to_html(
            full_html=False,
            include_plotlyjs="cdn",
            default_width="100%",
            default_height="600px",
        )

        chart2_html = fig_trend.to_html(
            full_html=False,
            include_plotlyjs=False,
            default_width="100%",
            default_height="600px",
        )

        table_html = season_display.to_html(
            index=False,
            border=0,
            classes="summary-table",
            justify="center",
        )

        html_content = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>季節別黏度比較分析</title>

            <style>
                body {{
                    font-family: Arial, "Microsoft JhengHei", sans-serif;
                    margin: 35px;
                    background-color: #F3F4F6;
                    color: #1F2937;
                }}

                h1 {{
                    text-align: center;
                    color: #1F4E78;
                }}

                h2 {{
                    margin-top: 40px;
                    border-bottom: 2px solid #CBD5E1;
                    padding-bottom: 8px;
                }}

                .info-box {{
                    background-color: white;
                    border-left: 5px solid #2563EB;
                    padding: 18px;
                    margin-bottom: 25px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.08);
                }}

                .chart-box {{
                    background-color: white;
                    border: 1px solid #CBD5E1;
                    padding: 15px;
                    margin-bottom: 30px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.08);
                }}

                .table-box {{
                    background-color: white;
                    padding: 18px;
                    border: 1px solid #CBD5E1;
                }}

                .summary-table {{
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 13px;
                }}

                .summary-table th {{
                    background-color: #1F4E78;
                    color: white;
                    border: 1px solid #CBD5E1;
                    padding: 9px;
                }}

                .summary-table td {{
                    border: 1px solid #CBD5E1;
                    padding: 8px;
                    text-align: center;
                }}

                .summary-table tr:nth-child(even) {{
                    background-color: #F8FAFC;
                }}
            </style>
        </head>

        <body>
            <h1>季節別黏度比較分析</h1>

            <div class="info-box">
                <p><strong>分析色號：</strong>{selected_paint_code}</p>
                <p><strong>資料期間：</strong>{min_date} ～ {max_date}</p>
                <p><strong>篩選條件：</strong>{filter_details}</p>
                <p><strong>分析方式：</strong>{analysis_mode}</p>
            </div>

            <h2>圖1 各季節添加前後黏度比較</h2>
            <div class="chart-box">{chart1_html}</div>

            <h2>圖2 各季節黏度與添加比例趨勢</h2>
            <div class="chart-box">{chart2_html}</div>

            <h2>季節比較明細</h2>
            <div class="table-box">{table_html}</div>
        </body>
        </html>
        """

        html_buffer = html_content.encode("utf-8")

        st.success("✅ 季節分析報告已產生。")

        st.download_button(
            label="下載季節分析報告 HTML",
            data=html_buffer,
            file_name=(
                f"Seasonal_Viscosity_Report_"
                f"{selected_paint_code}_"
                f"{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}"
                f".html"
            ),
            mime="text/html",
            on_click="ignore",
        )

    except Exception as error:
        st.error(f"❌ 產生報告時發生錯誤：{error}")
