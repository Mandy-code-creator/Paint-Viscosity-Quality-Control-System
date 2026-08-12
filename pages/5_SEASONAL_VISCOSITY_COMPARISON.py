import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="Seasonal Viscosity Comparison",
    page_icon="🌡️",
    layout="wide",
)

st.title("🌡️ 季節別黏度比較分析")
st.caption(
    "依色號與膜厚條件比較四季之添加前／後黏度、稀釋劑添加比例及溫度。"
)


# =========================================================
# 2. LOAD DATA
# =========================================================
if (
    not st.session_state.get("raw_data_loaded", False)
    or st.session_state.get("group_a_data") is None
):
    st.warning(
        "⚠️ 尚未載入資料，請先返回首頁上傳原始資料。"
    )
    st.stop()

df = st.session_state["group_a_data"].copy()


# =========================================================
# 3. HELPERS
# =========================================================
@st.cache_data(show_spinner=False)
def dataframe_to_csv_bytes(dataframe: pd.DataFrame) -> bytes:
    return dataframe.to_csv(index=False).encode("utf-8-sig")


def safe_unique(series):
    return sorted(
        [
            str(value).strip()
            for value in series.dropna().unique().tolist()
            if str(value).strip()
            not in {
                "",
                "Unknown",
                "UNKNOWN",
                "nan",
                "NaN",
                "None",
                "<NA>",
            }
        ]
    )


def fmt_thickness(value):
    if pd.isna(value):
        return "—"

    value = float(value)

    if value.is_integer():
        return str(int(value))

    return f"{value:.1f}".rstrip("0").rstrip(".")


def build_structure_label(row):
    primer = row["Primer_Thickness"]
    main = row["Main_Coat_Thickness"]

    if pd.isna(primer) and pd.isna(main):
        return "Unknown"

    return (
        f"{fmt_thickness(primer)} µm + "
        f"{fmt_thickness(main)} µm"
    )


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


SEASON_ORDER = {
    "冬季 (12–02月)": 1,
    "春季 (03–05月)": 2,
    "夏季 (06–08月)": 3,
    "秋季 (09–11月)": 4,
}


# =========================================================
# 4. DATA PREPARATION
# =========================================================
text_cols = [
    "Vendor",
    "Resin",
    "Solvent_Type",
    "塗料批號",
    "線別",
    "塗裝位置",
]

for col in text_cols:
    if col not in df.columns:
        df[col] = "Unknown"

    df[col] = (
        df[col]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
    )


df["Paint_Code"] = (
    df.get(
        "塗料編號",
        pd.Series("Unknown", index=df.index),
    )
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

df["Batch_ID"] = (
    df["塗料批號"]
    .fillna("Unknown")
    .astype(str)
    .str.strip()
)

df["Bucket_Number"] = (
    df.get(
        "塗料桶號",
        pd.Series("Unknown", index=df.index),
    )
    .fillna("Unknown")
    .astype(str)
    .str.strip()
)


# ---------------------------------------------------------
# 4.1 COATING POSITION
# ---------------------------------------------------------
position_map = {
    "TP": "Primer",
    "正底漆": "Primer",
    "BP": "Primer",
    "背底漆": "Primer",
    "TF": "Top Finish",
    "正面漆": "Top Finish",
    "BF": "Back Finish",
    "背面漆": "Back Finish",
    "PRIMER": "Primer",
    "TOP FINISH": "Top Finish",
    "BACK FINISH": "Back Finish",
}

position_key = (
    df["塗裝位置"]
    .fillna("")
    .astype(str)
    .str.strip()
    .str.upper()
)

invalid_position_values = {
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

position_key = position_key.mask(
    position_key.isin(invalid_position_values),
    "",
)

df["_Position_Raw"] = position_key

df["Position_UI"] = (
    position_key
    .map(position_map)
    .fillna("Unknown")
)


# ---------------------------------------------------------
# 4.2 SPECIAL EXCEPTION — PS30213Z2
# ---------------------------------------------------------
# PS30213Z2 is operationally a primer-group paint.
# Some multi-pass records may be marked as TF / Top Finish,
# but it must never appear when Top Finish is selected.
special_primer_paint_codes = {
    "PS30213Z2",
}

df.loc[
    df["Paint_Code"].isin(special_primer_paint_codes),
    "Position_UI",
] = "Primer"


# ---------------------------------------------------------
# 4.3 ORDER FILM THICKNESS
# ---------------------------------------------------------
thickness_cols = [
    "TOPFILM_THICK",
    "TTMFILM_THICK",
    "BACKFILM_THICK",
    "BTMFILM_THICK",
]

for col in thickness_cols:
    if col not in df.columns:
        df[col] = np.nan

    df[col] = pd.to_numeric(
        df[col],
        errors="coerce",
    )


# Determine coating side from raw source position.
is_top_side = df["_Position_Raw"].isin(
    [
        "TF",
        "TP",
        "正面漆",
        "正底漆",
        "TOP FINISH",
    ]
)

is_back_side = df["_Position_Raw"].isin(
    [
        "BF",
        "BP",
        "背面漆",
        "背底漆",
        "BACK FINISH",
    ]
)


df["Primer_Thickness"] = np.select(
    [
        is_top_side,
        is_back_side,
    ],
    [
        df["TTMFILM_THICK"],
        df["BTMFILM_THICK"],
    ],
    default=np.nan,
)

df["Main_Coat_Thickness"] = np.select(
    [
        is_top_side,
        is_back_side,
    ],
    [
        df["TOPFILM_THICK"],
        df["BACKFILM_THICK"],
    ],
    default=np.nan,
)

df["Total_Coating_Thickness"] = (
    df["Primer_Thickness"]
    + df["Main_Coat_Thickness"]
)

df["Coating_Structure"] = df.apply(
    build_structure_label,
    axis=1,
)


# ---------------------------------------------------------
# 4.4 NUMERIC FIELDS
# ---------------------------------------------------------
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

    df[col] = pd.to_numeric(
        df[col],
        errors="coerce",
    )


# ---------------------------------------------------------
# 4.5 CORE CALCULATIONS
# ---------------------------------------------------------
df["Base_Paint_kg"] = (
    df["塗料重量"]
    - df["添加重量"]
)

df["Delta_V"] = (
    df["黏度(秒)"]
    - df["黏度(秒)_1"]
)

df["Solvent_Ratio_Percent"] = np.where(
    df["Base_Paint_kg"] > 0,
    df["添加重量"]
    / df["Base_Paint_kg"]
    * 100,
    np.nan,
)

df["Viscosity_Sensitivity"] = np.where(
    df["Solvent_Ratio_Percent"] > 0,
    df["Delta_V"]
    / df["Solvent_Ratio_Percent"],
    np.nan,
)


# Group A strict valid records.
df = df[
    (df["Base_Paint_kg"] > 0)
    & (df["添加重量"] > 0)
    & (df["黏度(秒)"] > 0)
    & (df["黏度(秒)_1"] > 0)
    & (df["Delta_V"] > 0)
    & (df["Position_UI"].isin(
        [
            "Primer",
            "Top Finish",
            "Back Finish",
        ]
    ))
].copy()

if df.empty:
    st.warning(
        "⚠️ 資料清理後無有效黏度調整紀錄。"
    )
    st.stop()


# =========================================================
# 5. DATE / RECORD LOGIC
# =========================================================
date_candidates = [
    "攪拌日期",
    "調整日期",
    "生產日期",
    "Date",
]

date_col = next(
    (
        col
        for col in date_candidates
        if col in df.columns
    ),
    None,
)

if date_col is None:
    st.error(
        "❌ 找不到日期欄位。"
    )
    st.stop()

df["_Analysis_Date"] = pd.to_datetime(
    df[date_col],
    errors="coerce",
)

df = df[
    df["_Analysis_Date"].notna()
].copy()

if df.empty:
    st.warning(
        "⚠️ 日期格式無法解析。"
    )
    st.stop()


time_candidates = [
    "攪拌時間(迄)",
    "攪拌時間",
    "Time",
]

time_col = next(
    (
        col
        for col in time_candidates
        if col in df.columns
    ),
    None,
)

sort_cols = [
    "Batch_ID",
    "Bucket_Number",
    "_Analysis_Date",
]

if time_col is not None:
    sort_cols.append(time_col)

df = df.sort_values(
    sort_cols,
    ascending=True,
    na_position="last",
)


# PS30213X8: every row is an independent use/adjustment event.
special_record_codes = {
    "PS30213X8",
}

is_special_record = df[
    "Paint_Code"
].isin(
    special_record_codes
)

df_standard = (
    df.loc[~is_special_record]
    .drop_duplicates(
        subset=[
            "Batch_ID",
            "Bucket_Number",
        ],
        keep="last",
    )
    .copy()
)

df_special = (
    df.loc[is_special_record]
    .copy()
)

df = pd.concat(
    [
        df_standard,
        df_special,
    ],
    ignore_index=True,
)

df = df.sort_values(
    [
        "_Analysis_Date",
        "Batch_ID",
        "Bucket_Number",
    ],
    ascending=True,
    na_position="last",
).reset_index(drop=True)


# =========================================================
# 6. SEASON CLASSIFICATION
# =========================================================
df["Month"] = (
    df["_Analysis_Date"]
    .dt.month
)

df["Season"] = (
    df["Month"]
    .apply(assign_season)
)

df["Season_Order"] = (
    df["Season"]
    .map(SEASON_ORDER)
)

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
# 7. LINKED FILTERS
#    Vendor → Paint Code → Position → Thickness
#    → Resin → Solvent → Line
# =========================================================
st.markdown("---")
st.subheader("🔍 分析篩選條件")

filter_source = df.copy()

row1_col1, row1_col2, row1_col3, row1_col4 = st.columns(4)
row2_col1, row2_col2, row2_col3, row2_col4 = st.columns(4)


# Vendor
vendor_options = safe_unique(
    filter_source["Vendor"]
)

if not vendor_options:
    st.warning("⚠️ 無供應商資料。")
    st.stop()

selected_vendor = row1_col1.selectbox(
    "Vendor (供應商)",
    vendor_options,
)

vendor_df = filter_source[
    filter_source["Vendor"] == selected_vendor
].copy()


# Paint Code
paint_code_options = safe_unique(
    vendor_df["Paint_Code"]
)

if not paint_code_options:
    st.warning(
        "⚠️ 此供應商無有效色號。"
    )
    st.stop()

selected_paint_code = row1_col2.selectbox(
    "Paint Code (色號)",
    paint_code_options,
)

paint_df = vendor_df[
    vendor_df["Paint_Code"] == selected_paint_code
].copy()


# Position
valid_position_order = [
    "Primer",
    "Top Finish",
    "Back Finish",
]

position_available = set(
    paint_df["Position_UI"]
    .dropna()
    .astype(str)
    .tolist()
)

position_options = [
    value
    for value in valid_position_order
    if value in position_available
]

if not position_options:
    st.warning(
        "⚠️ 此色號無有效塗裝位置。"
    )
    st.stop()

selected_position = row1_col3.selectbox(
    "Coating Position (塗裝位置)",
    position_options,
)

position_df = paint_df[
    paint_df["Position_UI"] == selected_position
].copy()


# Coating Structure
structure_options = safe_unique(
    position_df["Coating_Structure"]
)

structure_options = [
    value
    for value in structure_options
    if value != "Unknown"
]

if not structure_options:
    structure_options = ["All"]

selected_structure = row1_col4.selectbox(
    "Coating Structure (膜厚組合)",
    ["All"] + structure_options
    if structure_options != ["All"]
    else ["All"],
    help=(
        "Top side = Primer + Top Finish；"
        "Back side = Primer + Back Finish。"
        "例如：5 µm + 20 µm。"
    ),
)

if selected_structure != "All":
    structure_df = position_df[
        position_df["Coating_Structure"]
        == selected_structure
    ].copy()
else:
    structure_df = position_df.copy()


# Resin
resin_options = safe_unique(
    structure_df["Resin"]
)

if not resin_options:
    resin_options = ["All"]

selected_resin = row2_col1.selectbox(
    "Resin Type (樹脂種類)",
    ["All"] + resin_options
    if resin_options != ["All"]
    else ["All"],
)

if selected_resin != "All":
    resin_df = structure_df[
        structure_df["Resin"] == selected_resin
    ].copy()
else:
    resin_df = structure_df.copy()


# Solvent
solvent_options = safe_unique(
    resin_df["Solvent_Type"]
)

if not solvent_options:
    solvent_options = ["All"]

selected_solvent = row2_col2.selectbox(
    "Solvent Type (稀釋劑種類)",
    ["All"] + solvent_options
    if solvent_options != ["All"]
    else ["All"],
)

if selected_solvent != "All":
    solvent_df = resin_df[
        resin_df["Solvent_Type"]
        == selected_solvent
    ].copy()
else:
    solvent_df = resin_df.copy()


# Production Line
line_options = safe_unique(
    solvent_df["線別"]
)

selected_lines = row2_col3.multiselect(
    "Production Line (產線)",
    line_options,
    default=line_options,
)

if not selected_lines:
    st.warning(
        "⚠️ 請至少選擇一條產線。"
    )
    st.stop()

analysis_df = solvent_df[
    solvent_df["線別"].isin(
        selected_lines
    )
].copy()


# Analysis mode
analysis_mode = row2_col4.selectbox(
    "Analysis Mode (分析方式)",
    [
        "合併各年度比較四季",
        "依季節年度比較",
    ],
)

if analysis_df.empty:
    st.warning(
        "⚠️ 無符合目前篩選條件的資料。"
    )
    st.stop()


# =========================================================
# 8. FILTER / DATA SUMMARY
# =========================================================
min_date = (
    analysis_df["_Analysis_Date"]
    .min()
    .strftime("%Y-%m-%d")
)

max_date = (
    analysis_df["_Analysis_Date"]
    .max()
    .strftime("%Y-%m-%d")
)

unique_structures = safe_unique(
    analysis_df["Coating_Structure"]
)

if selected_structure == "All":
    if len(unique_structures) == 1:
        structure_display = unique_structures[0]
    elif len(unique_structures) <= 4:
        structure_display = " / ".join(
            unique_structures
        )
    else:
        structure_display = (
            f"{len(unique_structures)} structures"
        )
else:
    structure_display = selected_structure

filter_details = (
    f"Vendor: {selected_vendor} | "
    f"Paint Code: {selected_paint_code} | "
    f"Position: {selected_position} | "
    f"Thickness: {structure_display} | "
    f"Resin: {selected_resin} | "
    f"Solvent: {selected_solvent}"
)

st.info(
    f"📅 **資料期間：** {min_date} ➔ {max_date}"
    f" ｜ 📊 **有效紀錄：** {len(analysis_df):,} 筆"
    f" ｜ 🎨 **色號：** {selected_paint_code}"
    f" ｜ 📏 **膜厚：** {structure_display}"
)


# =========================================================
# 9. SEASONAL AGGREGATION
# =========================================================
if analysis_mode == "合併各年度比較四季":
    group_cols = [
        "Season_Order",
        "Season",
    ]
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
    analysis_df
    .groupby(
        group_cols,
        dropna=False,
    )
    .agg(
        Historical_Records=(
            "Paint_Code",
            "size",
        ),
        Historical_Batches=(
            "Batch_ID",
            "nunique",
        ),
        Median_Before_Viscosity=(
            "黏度(秒)",
            "median",
        ),
        Before_P25=(
            "黏度(秒)",
            lambda x: x.quantile(0.25),
        ),
        Before_P75=(
            "黏度(秒)",
            lambda x: x.quantile(0.75),
        ),
        Median_After_Viscosity=(
            "黏度(秒)_1",
            "median",
        ),
        After_P25=(
            "黏度(秒)_1",
            lambda x: x.quantile(0.25),
        ),
        After_P75=(
            "黏度(秒)_1",
            lambda x: x.quantile(0.75),
        ),
        Median_Viscosity_Drop=(
            "Delta_V",
            "median",
        ),
        Median_Solvent_Ratio=(
            "Solvent_Ratio_Percent",
            "median",
        ),
        Median_Temperature=(
            "溫度",
            "median",
        ),
        Total_Solvent_kg=(
            "添加重量",
            "sum",
        ),
    )
    .reset_index()
)

if analysis_mode == "合併各年度比較四季":
    season_summary = (
        season_summary
        .sort_values(
            ["Season_Order"]
        )
        .reset_index(drop=True)
    )
else:
    season_summary = (
        season_summary
        .sort_values(
            [
                "Season_Year",
                "Season_Order",
            ]
        )
        .reset_index(drop=True)
    )

if season_summary.empty:
    st.warning(
        "⚠️ 此條件無足夠季節資料。"
    )
    st.stop()


# =========================================================
# 10. COMPACT SEASONAL OVERVIEW
# =========================================================
st.markdown("---")
st.subheader("1. Seasonal Overview")
st.caption(filter_details)

period_values = (
    season_summary[period_col]
    .astype(str)
    .tolist()
)

cell_text = []

for _, row in season_summary.iterrows():
    temp_text = (
        f"{row['Median_Temperature']:.1f} °C"
        if pd.notna(
            row["Median_Temperature"]
        )
        else "—"
    )

    cell_text.append(
        (
            f"<b>{row['Median_Before_Viscosity']:.0f}"
            f" → {row['Median_After_Viscosity']:.0f} s</b>"
            f"<br>{row['Median_Solvent_Ratio']:.1f}%"
            f"<br>{temp_text}"
        )
    )

z_values = np.array(
    [
        season_summary[
            "Median_Viscosity_Drop"
        ].tolist()
    ],
    dtype=float,
)

customdata = np.array(
    [
        [
            [
                row["Median_Before_Viscosity"],
                row["Median_After_Viscosity"],
                row["Median_Viscosity_Drop"],
                row["Median_Solvent_Ratio"],
                row["Median_Temperature"],
                row["Historical_Records"],
                row["Historical_Batches"],
            ]
            for _, row in season_summary.iterrows()
        ]
    ],
    dtype=object,
)

fig_overview = go.Figure(
    data=go.Heatmap(
        z=z_values,
        x=period_values,
        y=[selected_paint_code],
        text=[cell_text],
        texttemplate="%{text}",
        textfont=dict(
            size=13,
            color="#111827",
        ),
        customdata=customdata,
        colorscale=[
            [0.00, "#EFF6FF"],
            [0.35, "#BFDBFE"],
            [0.70, "#60A5FA"],
            [1.00, "#1D4ED8"],
        ],
        colorbar=dict(
            title="ΔV<br>(s)",
            thickness=13,
            len=0.70,
        ),
        xgap=3,
        ygap=3,
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Before: %{customdata[0]:.1f} s<br>"
            "After: %{customdata[1]:.1f} s<br>"
            "Drop: %{customdata[2]:.1f} s<br>"
            "Solvent Ratio: %{customdata[3]:.2f}%<br>"
            "Temperature: %{customdata[4]:.1f} °C<br>"
            "Records: %{customdata[5]:,.0f}<br>"
            "Batches: %{customdata[6]:,.0f}"
            "<extra></extra>"
        ),
    )
)

fig_overview.update_layout(
    title=None,
    height=315,
    margin=dict(
        l=130,
        r=80,
        t=55,
        b=65,
    ),
    paper_bgcolor="white",
    plot_bgcolor="white",
    font=dict(
        family=(
            "Arial, Microsoft JhengHei, "
            "sans-serif"
        ),
        color="#334155",
    ),
)

fig_overview.update_xaxes(
    title=None,
    side="top",
    showline=True,
    linecolor="#475569",
    mirror=True,
    ticks="outside",
    ticklen=6,
    tickfont=dict(size=12),
)

fig_overview.update_yaxes(
    title="Paint Code",
    showline=True,
    linecolor="#475569",
    mirror=True,
)

st.plotly_chart(
    fig_overview,
    use_container_width=True,
)

st.caption(
    "每格依序顯示：添加前 → 添加後黏度、稀釋劑添加比例、溫度；底色代表典型降黏幅度。"
)


# =========================================================
# 11. KPI SUMMARY
# =========================================================
st.markdown("---")
st.subheader("2. Seasonal Summary")

highest_before_row = season_summary.loc[
    season_summary[
        "Median_Before_Viscosity"
    ].idxmax()
]

lowest_before_row = season_summary.loc[
    season_summary[
        "Median_Before_Viscosity"
    ].idxmin()
]

highest_ratio_row = season_summary.loc[
    season_summary[
        "Median_Solvent_Ratio"
    ].idxmax()
]

largest_drop_row = season_summary.loc[
    season_summary[
        "Median_Viscosity_Drop"
    ].idxmax()
]

k1, k2, k3, k4 = st.columns(4)

k1.metric(
    "Highest Incoming Viscosity",
    str(
        highest_before_row[
            period_col
        ]
    ),
    (
        f"{highest_before_row['Median_Before_Viscosity']:.1f} s"
    ),
)

k2.metric(
    "Lowest Incoming Viscosity",
    str(
        lowest_before_row[
            period_col
        ]
    ),
    (
        f"{lowest_before_row['Median_Before_Viscosity']:.1f} s"
    ),
)

k3.metric(
    "Highest Solvent Ratio",
    str(
        highest_ratio_row[
            period_col
        ]
    ),
    (
        f"{highest_ratio_row['Median_Solvent_Ratio']:.1f}%"
    ),
)

k4.metric(
    "Largest Viscosity Drop",
    str(
        largest_drop_row[
            period_col
        ]
    ),
    (
        f"{largest_drop_row['Median_Viscosity_Drop']:.1f} s"
    ),
)


# =========================================================
# 12. CHART 1 — BEFORE VS AFTER
# =========================================================
st.markdown("---")
st.subheader("3. Before vs. After Viscosity by Season")

fig_before_after = go.Figure()

for _, row in season_summary.iterrows():
    period_name = str(
        row[period_col]
    )

    fig_before_after.add_trace(
        go.Scatter(
            x=[
                row[
                    "Median_After_Viscosity"
                ],
                row[
                    "Median_Before_Viscosity"
                ],
            ],
            y=[
                period_name,
                period_name,
            ],
            mode="lines",
            line=dict(
                color="#94A3B8",
                width=5,
            ),
            hoverinfo="skip",
            showlegend=False,
        )
    )


fig_before_after.add_trace(
    go.Scatter(
        x=season_summary[
            "Median_Before_Viscosity"
        ],
        y=season_summary[
            period_col
        ].astype(str),
        mode="markers+text",
        name="Before Viscosity",
        marker=dict(
            size=17,
            color="#D97706",
            line=dict(
                color="white",
                width=1.5,
            ),
        ),
        text=season_summary[
            "Median_Before_Viscosity"
        ].map(
            lambda value: f"{value:.1f}"
        ),
        textposition="top center",
        customdata=np.column_stack(
            [
                season_summary[
                    "Before_P25"
                ],
                season_summary[
                    "Before_P75"
                ],
                season_summary[
                    "Historical_Records"
                ],
                season_summary[
                    "Historical_Batches"
                ],
            ]
        ),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Before Median: %{x:.1f} s<br>"
            "P25–P75: %{customdata[0]:.1f}"
            "–%{customdata[1]:.1f} s<br>"
            "Records: %{customdata[2]:,.0f}<br>"
            "Batches: %{customdata[3]:,.0f}"
            "<extra></extra>"
        ),
    )
)


fig_before_after.add_trace(
    go.Scatter(
        x=season_summary[
            "Median_After_Viscosity"
        ],
        y=season_summary[
            period_col
        ].astype(str),
        mode="markers+text",
        name="After Viscosity",
        marker=dict(
            size=17,
            color="#2563EB",
            line=dict(
                color="white",
                width=1.5,
            ),
        ),
        text=season_summary[
            "Median_After_Viscosity"
        ].map(
            lambda value: f"{value:.1f}"
        ),
        textposition="bottom center",
        customdata=np.column_stack(
            [
                season_summary[
                    "After_P25"
                ],
                season_summary[
                    "After_P75"
                ],
                season_summary[
                    "Median_Viscosity_Drop"
                ],
            ]
        ),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "After Median: %{x:.1f} s<br>"
            "P25–P75: %{customdata[0]:.1f}"
            "–%{customdata[1]:.1f} s<br>"
            "Median Drop: %{customdata[2]:.1f} s"
            "<extra></extra>"
        ),
    )
)


fig_before_after.update_layout(
    title=dict(
        text=(
            f"<b>{selected_paint_code} — "
            "Seasonal Before vs. After Viscosity</b>"
            f"<br><sup>{filter_details}</sup>"
        ),
        x=0.5,
        xanchor="center",
    ),
    height=max(
        520,
        len(season_summary) * 72,
    ),
    margin=dict(
        l=160,
        r=60,
        t=125,
        b=75,
    ),
    template="plotly_white",
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.03,
        xanchor="center",
        x=0.5,
    ),
    xaxis=dict(
        title="Viscosity (s)",
        showgrid=True,
        gridcolor="#E5E7EB",
        showline=True,
        linecolor="#475569",
        mirror=True,
    ),
    yaxis=dict(
        title="Season",
        categoryorder="array",
        categoryarray=period_values,
        showgrid=True,
        gridcolor="#E5E7EB",
        showline=True,
        linecolor="#475569",
        mirror=True,
    ),
)

st.plotly_chart(
    fig_before_after,
    use_container_width=True,
)


# =========================================================
# 13. CHART 2 — SEASONAL VISCOSITY + SOLVENT RATIO + TEMPERATURE
#     Preferred line-chart style:
#     Before viscosity + After viscosity + Solvent ratio + Temperature
# =========================================================
st.markdown("---")
st.subheader("4. Seasonal Viscosity, Solvent Ratio and Temperature")

fig_condition = go.Figure()

period_series = season_summary[
    period_col
].astype(str)

# ---------------------------------------------------------
# Before viscosity
# ---------------------------------------------------------
fig_condition.add_trace(
    go.Scatter(
        x=period_series,
        y=season_summary[
            "Median_Before_Viscosity"
        ],
        mode="lines+markers+text",
        name="Before Viscosity (s)",
        line=dict(
            color="#D97706",
            width=3,
        ),
        marker=dict(
            size=9,
            color="#D97706",
        ),
        text=season_summary[
            "Median_Before_Viscosity"
        ].map(
            lambda value: f"{value:.1f}"
        ),
        textposition="top center",
        textfont=dict(
            size=11,
            color="#92400E",
        ),
        yaxis="y1",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Before Viscosity: %{y:.1f} s"
            "<extra></extra>"
        ),
    )
)

# ---------------------------------------------------------
# After viscosity
# ---------------------------------------------------------
fig_condition.add_trace(
    go.Scatter(
        x=period_series,
        y=season_summary[
            "Median_After_Viscosity"
        ],
        mode="lines+markers+text",
        name="After Viscosity (s)",
        line=dict(
            color="#2563EB",
            width=3,
        ),
        marker=dict(
            size=9,
            color="#2563EB",
        ),
        text=season_summary[
            "Median_After_Viscosity"
        ].map(
            lambda value: f"{value:.1f}"
        ),
        textposition="bottom center",
        textfont=dict(
            size=11,
            color="#1D4ED8",
        ),
        yaxis="y1",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{x}</b><br>"
            "After Viscosity: %{y:.1f} s"
            "<extra></extra>"
        ),
    )
)

# ---------------------------------------------------------
# Solvent ratio
# ---------------------------------------------------------
fig_condition.add_trace(
    go.Scatter(
        x=period_series,
        y=season_summary[
            "Median_Solvent_Ratio"
        ],
        mode="lines+markers",
        name="Solvent Ratio (%)",
        line=dict(
            color="#059669",
            width=3,
            dash="dot",
        ),
        marker=dict(
            size=10,
            color="#059669",
            symbol="diamond",
        ),
        yaxis="y2",
        customdata=np.column_stack(
            [
                season_summary[
                    "Total_Solvent_kg"
                ],
                season_summary[
                    "Historical_Records"
                ],
            ]
        ),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Solvent Ratio: %{y:.2f}%<br>"
            "Total Solvent: %{customdata[0]:.1f} kg<br>"
            "Records: %{customdata[1]:,.0f}"
            "<extra></extra>"
        ),
    )
)

# Solvent ratio labels
for i, row in season_summary.iterrows():
    fig_condition.add_annotation(
        x=str(row[period_col]),
        y=row[
            "Median_Solvent_Ratio"
        ],
        xref="x",
        yref="y2",
        text=(
            f"{row['Median_Solvent_Ratio']:.1f}%"
        ),
        showarrow=False,
        xshift=12 if i % 2 == 0 else -12,
        yshift=13,
        font=dict(
            size=10,
            color="#047857",
        ),
        bgcolor="rgba(255,255,255,0.90)",
        bordercolor="rgba(5,150,105,0.25)",
        borderwidth=1,
        borderpad=2,
    )

# ---------------------------------------------------------
# Temperature
# Use a third Y-axis on the right so the temperature line
# remains readable and does not compress the solvent-ratio line.
# ---------------------------------------------------------
if season_summary[
    "Median_Temperature"
].notna().any():
    fig_condition.add_trace(
        go.Scatter(
            x=period_series,
            y=season_summary[
                "Median_Temperature"
            ],
            mode="lines+markers+text",
            name="Temperature (°C)",
            line=dict(
                color="#7E22CE",
                width=3,
                dash="dash",
            ),
            marker=dict(
                size=9,
                color="#7E22CE",
                symbol="circle",
            ),
            text=season_summary[
                "Median_Temperature"
            ].map(
                lambda value: (
                    f"{value:.1f}°"
                    if pd.notna(value)
                    else ""
                )
            ),
            textposition="top center",
            textfont=dict(
                size=10,
                color="#6B21A8",
            ),
            yaxis="y3",
            cliponaxis=False,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Temperature: %{y:.1f} °C"
                "<extra></extra>"
            ),
        )
    )


# ---------------------------------------------------------
# Axis ranges
# ---------------------------------------------------------
ratio_values = pd.to_numeric(
    season_summary[
        "Median_Solvent_Ratio"
    ],
    errors="coerce",
).dropna()

if not ratio_values.empty:
    ratio_min = float(
        ratio_values.min()
    )
    ratio_max = float(
        ratio_values.max()
    )
    ratio_pad = max(
        0.8,
        (ratio_max - ratio_min) * 0.20,
    )
    ratio_range = [
        max(0, ratio_min - ratio_pad),
        ratio_max + ratio_pad,
    ]
else:
    ratio_range = None


temp_values = pd.to_numeric(
    season_summary[
        "Median_Temperature"
    ],
    errors="coerce",
).dropna()

if not temp_values.empty:
    temp_min = float(
        temp_values.min()
    )
    temp_max = float(
        temp_values.max()
    )
    temp_pad = max(
        1.0,
        (temp_max - temp_min) * 0.18,
    )
    temp_range = [
        temp_min - temp_pad,
        temp_max + temp_pad,
    ]
else:
    temp_range = None


# ---------------------------------------------------------
# Layout
# ---------------------------------------------------------
fig_condition.update_layout(
    title=dict(
        text=(
            f"<b>{selected_paint_code} — "
            "Seasonal Viscosity, Solvent Ratio & Temperature</b>"
            f"<br><sup>Thickness: "
            f"{structure_display}</sup>"
        ),
        x=0.5,
        xanchor="center",
    ),
    height=590,
    template="plotly_white",
    margin=dict(
        l=80,
        r=150,
        t=145,
        b=80,
    ),
    xaxis=dict(
        title="Season",
        categoryorder="array",
        categoryarray=period_values,
        showgrid=False,
        showline=True,
        linecolor="#4B5563",
        linewidth=1.4,
        mirror=True,
        ticks="outside",
    ),
    yaxis=dict(
        title="Viscosity (s)",
        side="left",
        showgrid=True,
        gridcolor="#D6DCE5",
        gridwidth=1,
        showline=True,
        linecolor="#4B5563",
        linewidth=1.4,
        zeroline=False,
    ),
    yaxis2=dict(
        title="Solvent Ratio (%)",
        overlaying="y",
        side="right",
        range=ratio_range,
        showgrid=False,
        showline=True,
        linecolor="#059669",
        linewidth=1.4,
        tickfont=dict(
            color="#047857"
        ),
        title_font=dict(
            color="#047857"
        ),
        zeroline=False,
    ),
    yaxis3=dict(
        title="Temperature (°C)",
        overlaying="y",
        side="right",
        anchor="free",
        position=1.0,
        range=temp_range,
        showgrid=False,
        showline=False,
        tickfont=dict(
            color="#7E22CE"
        ),
        title_font=dict(
            color="#7E22CE"
        ),
        ticksuffix="°",
        zeroline=False,
    ),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.07,
        xanchor="center",
        x=0.5,
        bgcolor="rgba(255,255,255,0.94)",
        bordercolor="#D1D5DB",
        borderwidth=1,
    ),
    font=dict(
        family=(
            "Arial, Microsoft JhengHei, "
            "sans-serif"
        ),
        size=12,
        color="#374151",
    ),
)

# Shift the temperature axis title farther right so it does not overlap
# with the solvent-ratio axis.
fig_condition.update_layout(
    yaxis3=dict(
        title=dict(
            text="Temperature (°C)",
            font=dict(
                color="#7E22CE"
            ),
            standoff=48,
        ),
        overlaying="y",
        side="right",
        anchor="free",
        position=1.0,
        range=temp_range,
        showgrid=False,
        showline=False,
        tickfont=dict(
            color="#7E22CE"
        ),
        ticksuffix="°",
        zeroline=False,
    )
)

st.plotly_chart(
    fig_condition,
    use_container_width=True,
)

st.caption(
    "橘線＝添加前黏度；藍線＝添加後黏度；"
    "綠色虛線＝稀釋劑添加比例；紫色虛線＝溫度。"
)


# =========================================================
# 14. SINGLE SUMMARY TABLE
# =========================================================
st.markdown("---")
st.subheader("5. Seasonal Summary Table")

season_display = season_summary[
    [
        period_col,
        "Historical_Records",
        "Historical_Batches",
        "Median_Before_Viscosity",
        "Median_After_Viscosity",
        "Median_Viscosity_Drop",
        "Median_Solvent_Ratio",
        "Median_Temperature",
        "Total_Solvent_kg",
    ]
].copy()

season_display.insert(
    1,
    "膜厚組合",
    structure_display,
)

season_display = season_display.rename(
    columns={
        period_col: "季節期間",
        "Historical_Records": "歷史紀錄數",
        "Historical_Batches": "歷史批數",
        "Median_Before_Viscosity": "添加前黏度中位數",
        "Median_After_Viscosity": "添加後黏度中位數",
        "Median_Viscosity_Drop": "降黏幅度中位數",
        "Median_Solvent_Ratio": "添加比例中位數",
        "Median_Temperature": "溫度中位數",
        "Total_Solvent_kg": "稀釋劑總用量",
    }
)

round_cols = [
    "添加前黏度中位數",
    "添加後黏度中位數",
    "降黏幅度中位數",
    "添加比例中位數",
    "溫度中位數",
    "稀釋劑總用量",
]

season_display[
    round_cols
] = season_display[
    round_cols
].round(1)

st.dataframe(
    season_display,
    column_config={
        "季節期間": st.column_config.TextColumn(
            "季節期間",
            width="medium",
        ),
        "膜厚組合": st.column_config.TextColumn(
            "膜厚組合",
            width="medium",
        ),
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
        "溫度中位數": st.column_config.NumberColumn(
            "溫度中位數 (°C)",
            format="%.1f",
        ),
        "稀釋劑總用量": st.column_config.NumberColumn(
            "稀釋劑總用量 (kg)",
            format="%.1f",
        ),
    },
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# 15. SHORT AUTOMATIC CONCLUSION
# =========================================================
st.markdown("---")
st.subheader("6. Automatic Conclusion")

before_range = (
    season_summary[
        "Median_Before_Viscosity"
    ].max()
    - season_summary[
        "Median_Before_Viscosity"
    ].min()
)

after_range = (
    season_summary[
        "Median_After_Viscosity"
    ].max()
    - season_summary[
        "Median_After_Viscosity"
    ].min()
)

ratio_range = (
    season_summary[
        "Median_Solvent_Ratio"
    ].max()
    - season_summary[
        "Median_Solvent_Ratio"
    ].min()
)

available_seasons = int(
    season_summary[
        "Season"
    ].nunique()
)

if available_seasons < 2:
    st.info(
        "⚪ 可比較季節少於 2 個，目前資料不足以判定季節差異。"
    )
else:
    if before_range <= 5:
        before_text = (
            "添加前黏度季節差異小"
        )
    elif before_range <= 10:
        before_text = (
            "添加前黏度有輕微季節差異"
        )
    else:
        before_text = (
            "添加前黏度季節差異明顯"
        )

    if after_range <= 5:
        after_text = (
            "現場調整後黏度大致一致"
        )
    else:
        after_text = (
            "調整後黏度仍有季節差異"
        )

    st.markdown(
        f"- **{before_text}**：最大差異約 **{before_range:.1f} s**。  \n"
        f"- **{after_text}**：最大差異約 **{after_range:.1f} s**。  \n"
        f"- 稀釋劑添加比例季節差異約 **{ratio_range:.1f} 個百分點**。"
    )


# =========================================================
# 16. EXPORT
# =========================================================
st.markdown("---")
st.subheader("📥 Export")

csv_data = dataframe_to_csv_bytes(
    season_display
)

st.download_button(
    label="下載季節比較表 CSV",
    data=csv_data,
    file_name=(
        f"Seasonal_Viscosity_"
        f"{selected_paint_code}.csv"
    ),
    mime="text/csv",
    on_click="ignore",
)


if st.button(
    "產生互動式 HTML 報告",
    type="primary",
):
    try:
        overview_html = (
            fig_overview.to_html(
                full_html=False,
                include_plotlyjs="cdn",
                default_width="100%",
                default_height="360px",
            )
        )

        chart1_html = (
            fig_before_after.to_html(
                full_html=False,
                include_plotlyjs=False,
                default_width="100%",
                default_height="600px",
            )
        )

        chart2_html = (
            fig_condition.to_html(
                full_html=False,
                include_plotlyjs=False,
                default_width="100%",
                default_height="560px",
            )
        )

        table_html = (
            season_display.to_html(
                index=False,
                border=0,
                classes="summary-table",
            )
        )

        html_content = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>Seasonal Viscosity Comparison</title>
            <style>
                body {{
                    font-family: Arial, "Microsoft JhengHei", sans-serif;
                    margin: 32px;
                    color: #1F2937;
                    background: #F8FAFC;
                }}

                h1 {{
                    color: #1F4E78;
                }}

                h2 {{
                    margin-top: 34px;
                    border-bottom: 2px solid #CBD5E1;
                    padding-bottom: 7px;
                }}

                .info {{
                    background: white;
                    border-left: 5px solid #2563EB;
                    padding: 16px;
                    margin-bottom: 24px;
                }}

                .box {{
                    background: white;
                    border: 1px solid #CBD5E1;
                    padding: 14px;
                    margin-bottom: 25px;
                }}

                .summary-table {{
                    border-collapse: collapse;
                    width: 100%;
                    background: white;
                    font-size: 13px;
                }}

                .summary-table th {{
                    background: #1F4E78;
                    color: white;
                    padding: 8px;
                    border: 1px solid #CBD5E1;
                }}

                .summary-table td {{
                    padding: 8px;
                    text-align: center;
                    border: 1px solid #CBD5E1;
                }}
            </style>
        </head>

        <body>
            <h1>季節別黏度比較分析</h1>

            <div class="info">
                <p><b>Paint Code：</b>{selected_paint_code}</p>
                <p><b>Coating Position：</b>{selected_position}</p>
                <p><b>Coating Structure：</b>{structure_display}</p>
                <p><b>Data Period：</b>{min_date} ～ {max_date}</p>
                <p><b>Filters：</b>{filter_details}</p>
            </div>

            <h2>Seasonal Overview</h2>
            <div class="box">{overview_html}</div>

            <h2>Before vs. After Viscosity</h2>
            <div class="box">{chart1_html}</div>

            <h2>Seasonal Viscosity, Solvent Ratio and Temperature</h2>
            <div class="box">{chart2_html}</div>

            <h2>Seasonal Summary Table</h2>
            <div class="box">{table_html}</div>
        </body>
        </html>
        """

        html_buffer = (
            html_content.encode(
                "utf-8"
            )
        )

        st.success(
            "✅ HTML 報告已產生。"
        )

        st.download_button(
            label="下載 HTML 報告",
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
        st.error(
            f"❌ 產生報告時發生錯誤：{error}"
        )
