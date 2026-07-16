import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Solvent Reduction Analytics",
    page_icon="🎨",
    layout="wide"
)

st.title("🎨 稀釋劑減量機會分析 (Solvent Reduction Opportunity)")

# Check if required session state exists
if "group_a_data" not in st.session_state or st.session_state["group_a_data"] is None:
    st.warning("⚠️ No data available. Please load the main dataset first. (尚未載入資料，請先返回首頁載入)")
    st.stop()

# Base DataFrame
df = st.session_state["group_a_data"].copy()

# Ensure expected columns exist (graceful fallback)
expected_cols = ["Date", "Vendor", "Resin", "Coating_Position", "Paint_Code", "Line", "Solvent_Type", 
                 "Batch_ID", "Paint_Weight", "Added_Weight", "Initial_Viscosity", "Final_Viscosity"]
for c in expected_cols:
    if c not in df.columns:
        df[c] = "N/A" if df.dtypes.get(c) == 'object' else 0

# ==========================================
# 2. GLOBAL FILTERS (Sidebar)
# ==========================================
st.sidebar.header("🔍 全局篩選條件 (Global Filters)")

filtered_df = df.copy()

def get_options(data, col):
    return sorted([str(x) for x in data[col].dropna().unique() if str(x).strip() != ""])

# A. Analysis Period
if "Date" in df.columns and pd.api.types.is_datetime64_any_dtype(df["Date"]):
    min_date = df["Date"].min()
    max_date = df["Date"].max()
    date_range = st.sidebar.date_input("資料期間 (Analysis Period)", [min_date, max_date])
    if len(date_range) == 2:
        filtered_df = filtered_df[(filtered_df["Date"].dt.date >= date_range[0]) & (filtered_df["Date"].dt.date <= date_range[1])]

# B. Vendor
vendor_opts = ["全部 (All)"] + get_options(filtered_df, "Vendor")
vendor = st.sidebar.selectbox("塗料供應商 (Vendor)", vendor_opts)
if vendor != "全部 (All)":
    filtered_df = filtered_df[filtered_df["Vendor"] == vendor]

# C. Resin Type
resin_opts = ["全部 (All)"] + get_options(filtered_df, "Resin")
resin = st.sidebar.selectbox("樹脂種類 (Resin Type)", resin_opts)
if resin != "全部 (All)":
    filtered_df = filtered_df[filtered_df["Resin"] == resin]

# D. Coating Position
pos_opts = ["全部 (All)"] + get_options(filtered_df, "Coating_Position")
position = st.sidebar.selectbox("塗層位置 (Coating Position)", pos_opts)
if position != "全部 (All)":
    filtered_df = filtered_df[filtered_df["Coating_Position"] == position]

# E. Production Line (Multiselect)
line_opts = get_options(filtered_df, "Line")
selected_lines = st.sidebar.multiselect("產線 (Production Line)", options=line_opts, default=line_opts)
if selected_lines:
    filtered_df = filtered_df[filtered_df["Line"].isin(selected_lines)]
else:
    st.sidebar.warning("請至少選擇一條產線 (Please select at least one line)")
    st.stop()

# F. Solvent Type
solvent_opts = ["全部 (All)"] + get_options(filtered_df, "Solvent_Type")
solvent = st.sidebar.selectbox("稀釋劑種類 (Solvent Type)", solvent_opts)
if solvent != "全部 (All)":
    filtered_df = filtered_df[filtered_df["Solvent_Type"] == solvent]

if filtered_df.empty:
    st.warning("⚠️ No data matches the selected global filters. (無符合篩選條件的資料)")
    st.stop()

# ==========================================
# 3. TABS STRUCTURE
# ==========================================
tab_ranking, tab_detail, tab_line_compare = st.tabs([
    "1️⃣ 減量優先順序 (Paint Code Ranking)",
    "2️⃣ 塗料編號詳細分析 (Paint Code Details)",
    "3️⃣ 產線黏度比較 (Production Line Comparison)"
])

# ------------------------------------------
# TAB 1: Paint Code Ranking
# ------------------------------------------
with tab_ranking:
    st.subheader("📊 塗料消耗排名 (Paint Code Consumption Ranking)")
    
    group_cols = ["Vendor", "Resin", "Coating_Position", "Paint_Code", "Solvent_Type"]
    valid_group_cols = [c for c in group_cols if c in filtered_df.columns]
    
    df_summary = filtered_df.groupby(valid_group_cols).agg(
        Records=("Paint_Code", "count"),
        Historical_Batches=("Batch_ID", "nunique"),
        Production_Lines=("Line", "nunique"),
        Total_Paint_kg=("Paint_Weight", "sum"),
        Total_Solvent_kg=("Added_Weight", "sum"),
        Median_Solvent_Added=("Added_Weight", "median"),
        Initial_Viscosity_Median=("Initial_Viscosity", "median"),
        Final_Viscosity_Median=("Final_Viscosity", "median")
    ).reset_index()
    
    df_summary["Weighted_Ratio_%"] = (df_summary["Total_Solvent_kg"] / df_summary["Total_Paint_kg"].replace(0, np.nan)) * 100
    df_summary = df_summary.sort_values(by="Total_Solvent_kg", ascending=False).reset_index(drop=True)
    
    # Format for display
    display_df = df_summary.copy()
    for col in ["Total_Paint_kg", "Total_Solvent_kg", "Median_Solvent_Added", "Initial_Viscosity_Median", "Final_Viscosity_Median", "Weighted_Ratio_%"]:
        if col in display_df.columns:
            display_df[col] = display_df[col].round(2)
            
    st.dataframe(
        display_df,
        use_container_width=True,
        column_config={
            "Records": "調整紀錄數 (Records)",
            "Historical_Batches": "歷史批數 (Batches)",
            "Production_Lines": "產線數 (Lines)",
            "Total_Paint_kg": "總塗料量 (Total Paint kg)",
            "Total_Solvent_kg": "總稀釋劑量 (Total Solvent kg)",
            "Median_Solvent_Added": "添加量中位數 (Median Added kg)",
            "Weighted_Ratio_%": "加權添加比例 (Weighted Ratio %)",
            "Initial_Viscosity_Median": "初始黏度中位數 (Initial Visc. Median)",
            "Final_Viscosity_Median": "最終黏度中位數 (Final Visc. Median)"
        }
    )

# ------------------------------------------
# SHARED SELECTOR FOR TAB 2 & 3
# ------------------------------------------
paint_code_options = sorted([str(x) for x in filtered_df["Paint_Code"].dropna().unique() if str(x).strip() != ""])

if not paint_code_options:
    st.warning("No paint codes available for detailed analysis.")
    st.stop()

# ------------------------------------------
# TAB 2: Paint Code Details
# ------------------------------------------
with tab_detail:
    st.subheader("🔍 塗料編號詳細分析 (Paint Code Details)")
    
    # Selector strictly driven by filtered_df
    selected_paint_code = st.selectbox(
        "選擇分析塗料編號 (Select Paint Code for Analysis):", 
        paint_code_options,
        key="detail_paint_selector"
    )
    
    selected_code_df = filtered_df[filtered_df["Paint_Code"] == selected_paint_code].copy()
    
    col1, col2, col3, col4 = st.columns(4)
    tot_paint = selected_code_df["Paint_Weight"].sum()
    tot_solvent = selected_code_df["Added_Weight"].sum()
    weighted_r = (tot_solvent / tot_paint * 100) if tot_paint > 0 else 0
    
    col1.metric("總紀錄數 (Total Records)", len(selected_code_df))
    col2.metric("總塗料量 (Total Paint kg)", f"{tot_paint:,.2f}")
    col3.metric("總稀釋劑量 (Total Solvent kg)", f"{tot_solvent:,.2f}")
    col4.metric("加權添加比例 (Weighted Ratio %)", f"{weighted_r:.2f}%")
    
    # Basic Scatter Plot
    st.markdown("#### 初始黏度 vs 加權添加比例 (Initial Viscosity vs Addition Ratio)")
    selected_code_df["Addition_Ratio_%"] = (selected_code_df["Added_Weight"] / selected_code_df["Paint_Weight"].replace(0, np.nan)) * 100
    if not selected_code_df.empty:
        fig = px.scatter(selected_code_df, x="Initial_Viscosity", y="Addition_Ratio_%", color="Line")
        fig.update_layout(margin=dict(l=0, r=0, t=30, b=0), height=350)
        st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------
# TAB 3: Production Line Comparison
# ------------------------------------------
with tab_line_compare:
    st.subheader(f"🏭 產線黏度比較 (Line Comparison for {selected_paint_code})")
    
    if len(selected_lines) <= 1:
        st.info("ℹ️ **Production Line Comparison is limited because only a single line was selected in the global filter.**")
    
    line_summary = selected_code_df.groupby("Line").agg(
        Records=("Paint_Code", "count"),
        Batches=("Batch_ID", "nunique"),
        Total_Paint_kg=("Paint_Weight", "sum"),
        Total_Solvent_kg=("Added_Weight", "sum"),
        Initial_Viscosity_Median=("Initial_Viscosity", "median"),
        Final_Viscosity_Median=("Final_Viscosity", "median")
    ).reset_index()
    
    line_summary["Weighted_Ratio_%"] = (line_summary["Total_Solvent_kg"] / line_summary["Total_Paint_kg"].replace(0, np.nan)) * 100
    
    for c in ["Total_Paint_kg", "Total_Solvent_kg", "Weighted_Ratio_%", "Initial_Viscosity_Median", "Final_Viscosity_Median"]:
        if c in line_summary.columns:
            line_summary[c] = line_summary[c].round(2)
            
    st.dataframe(
        line_summary,
        use_container_width=True,
        column_config={
            "Line": "產線 (Line)",
            "Records": "紀錄數 (Records)",
            "Batches": "批數 (Batches)",
            "Total_Paint_kg": "塗料量 (Paint kg)",
            "Total_Solvent_kg": "稀釋劑量 (Solvent kg)",
            "Weighted_Ratio_%": "加權添加比例 (Weighted Ratio %)",
            "Initial_Viscosity_Median": "初始黏度中位數 (Initial Visc. Median)",
            "Final_Viscosity_Median": "最終黏度中位數 (Final Visc. Median)"
        }
    )
