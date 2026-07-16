import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Solvent Reduction Opportunity",
    page_icon="🎨",
    layout="wide"
)

st.title("🎨 稀釋劑減量機會分析 (Solvent Reduction Opportunity Analysis)")

# Check if required session state exists
if "group_a_data" not in st.session_state:
    st.warning("⚠️ No data available. Please load the main dataset first. (尚未載入資料，請先返回首頁載入)")
    st.stop()

# Load raw data
df_raw = st.session_state["group_a_data"].copy()

# Ensure required columns exist, fill missing with defaults to avoid errors
required_cols = ["Vendor", "Resin", "Paint_Code", "Line", "Solvent_Type", 
                 "Batch_ID", "Paint_Weight", "Added_Weight", "Initial_Viscosity", "Final_Viscosity"]
for col in required_cols:
    if col not in df_raw.columns:
        df_raw[col] = "N/A" if df_raw.dtypes.get(col) == 'object' else 0

# ==========================================
# 2. GLOBAL FILTERS (Sidebar) - Sequential
# ==========================================
st.sidebar.header("🔍 篩選條件 (Filters)")

def get_options(df_current, col):
    if col in df_current.columns:
        opts = sorted([str(x) for x in df_current[col].dropna().unique() if str(x).strip() != ""])
        return ["全部 (All)"] + opts
    return ["全部 (All)"]

# Sequential Filtering
df_filtered = df_raw.copy()

vendor = st.sidebar.selectbox("塗料供應商 (Vendor)", get_options(df_filtered, "Vendor"))
if vendor != "全部 (All)":
    df_filtered = df_filtered[df_filtered["Vendor"] == vendor]

resin_type = st.sidebar.selectbox("樹脂種類 (Resin Type)", get_options(df_filtered, "Resin"))
if resin_type != "全部 (All)":
    df_filtered = df_filtered[df_filtered["Resin"] == resin_type]

paint_code = st.sidebar.selectbox("塗料編號 (Paint Code)", get_options(df_filtered, "Paint_Code"))
if paint_code != "全部 (All)":
    df_filtered = df_filtered[df_filtered["Paint_Code"] == paint_code]

line = st.sidebar.selectbox("產線 (Line)", get_options(df_filtered, "Line"))
if line != "全部 (All)":
    df_filtered = df_filtered[df_filtered["Line"] == line]

solvent_type = st.sidebar.selectbox("稀釋劑種類 (Solvent Type)", get_options(df_filtered, "Solvent_Type"))
if solvent_type != "全部 (All)":
    df_filtered = df_filtered[df_filtered["Solvent_Type"] == solvent_type]


if df_filtered.empty:
    st.warning("⚠️ No data matches the selected filters. (無符合篩選條件的資料)")
    st.stop()

# ==========================================
# 3. TABS LAYOUT
# ==========================================
tab_priority, tab_detail, tab_line_compare = st.tabs([
    "① 減量優先順序 (Priority Ranking)",
    "② 塗料編號詳細分析 (Detail Analysis)",
    "③ 產線黏度比較 (Line Comparison)"
])

# ==========================================
# DATA AGGREGATION FOR RANKING
# ==========================================
group_cols = ["Vendor", "Resin", "Paint_Code", "Solvent_Type"]
available_group_cols = [c for c in group_cols if c in df_filtered.columns]

df_grouped = df_filtered.groupby(available_group_cols).agg(
    Adjustment_Records=("Paint_Code", "count"),
    Historical_Batches=("Batch_ID", "nunique"),
    Total_Paint_kg=("Paint_Weight", "sum"),
    Total_Solvent_kg=("Added_Weight", "sum"),
    Initial_Viscosity_Median=("Initial_Viscosity", "median"),
    Final_Viscosity_Median=("Final_Viscosity", "median")
).reset_index()

df_grouped["Weighted_Ratio_%"] = (df_grouped["Total_Solvent_kg"] / df_grouped["Total_Paint_kg"].replace(0, np.nan)) * 100
df_grouped["Avg_Solvent_Per_Batch_kg"] = df_grouped["Total_Solvent_kg"] / df_grouped["Historical_Batches"].replace(0, np.nan)

df_priority = df_grouped.sort_values(by="Total_Solvent_kg", ascending=False).reset_index(drop=True)

# ------------------------------------------
# TAB 1: Priority Ranking
# ------------------------------------------
with tab_priority:
    st.subheader("📊 減量優先順序評估 (Priority Assessment for Solvent Reduction)")
    
    col1, col2 = st.columns([6, 4])
    
    with col1:
        st.markdown("#### 稀釋劑消耗 Top 10 (Top 10 Solvent Consumption Pareto)")
        df_top10 = df_priority.head(10).copy()
        
        if not df_top10.empty and "Paint_Code" in df_top10.columns:
            df_top10["Cumulative_Solvent"] = df_top10["Total_Solvent_kg"].cumsum()
            total_solvent_all = df_priority["Total_Solvent_kg"].sum()
            df_top10["Cumulative_Pct"] = (df_top10["Cumulative_Solvent"] / total_solvent_all) * 100

            fig_pareto = go.Figure()
            fig_pareto.add_trace(go.Bar(
                x=df_top10["Paint_Code"],
                y=df_top10["Total_Solvent_kg"],
                name="總稀釋劑量 (Solvent Used)",
                marker_color="lightslategray",
                yaxis="y1"
            ))
            fig_pareto.add_trace(go.Scatter(
                x=df_top10["Paint_Code"],
                y=df_top10["Cumulative_Pct"],
                name="累積比例 (Cumulative %)",
                mode="lines+markers",
                line=dict(color="DeepSkyBlue", width=3),
                marker=dict(size=8),
                yaxis="y2"
            ))
            fig_pareto.update_layout(
                xaxis=dict(title="塗料編號 (Paint Code)"),
                yaxis=dict(title="稀釋劑重量 (Solvent kg)", side="left", showgrid=False),
                yaxis2=dict(title="累積比例 (Cumulative %)", side="right", overlaying="y", range=[0, 105], showgrid=False),
                legend=dict(x=0.01, y=1.05, orientation="h"),
                margin=dict(l=0, r=0, t=40, b=0),
                height=400
            )
            st.plotly_chart(fig_pareto, use_container_width=True)
        
    with col2:
        st.markdown("#### 自動評估建議 (Automated Recommendations)")
        
        if not df_priority.empty:
            med_freq = df_priority["Historical_Batches"].median()
            med_solvent = df_priority["Total_Solvent_kg"].median()
            
            top_candidate = df_priority.iloc[0]
            
            if top_candidate["Historical_Batches"] >= med_freq and top_candidate["Total_Solvent_kg"] >= med_solvent:
                st.error(f"🚨 **優先改善 (Top Priority): {top_candidate.get('Paint_Code', 'N/A')}**\n\n"
                         "High usage frequency and high solvent consumption. Recommended to prioritize supplier negotiations for delivery viscosity.")
            elif top_candidate["Historical_Batches"] >= med_freq and top_candidate["Total_Solvent_kg"] < med_solvent:
                st.success(f"✅ **持續監控 (Monitor): {top_candidate.get('Paint_Code', 'N/A')}**\n\n"
                           "High usage but stable solvent ratio. Maintain current process.")
            elif top_candidate["Historical_Batches"] < med_freq and top_candidate["Total_Solvent_kg"] >= med_solvent:
                st.warning(f"⚠️ **異常檢查 (Anomaly Check): {top_candidate.get('Paint_Code', 'N/A')}**\n\n"
                           "Low frequency but unusually high solvent consumption. Check specific batches or operational conditions.")
            else:
                st.info(f"ℹ️ **低優先級 (Low Priority): {top_candidate.get('Paint_Code', 'N/A')}**\n\n"
                        "Low impact on overall cost.")

    st.markdown("#### 綜合排名表 (Comprehensive Ranking Table)")
    df_display = df_priority.copy()
    numeric_cols = ["Total_Paint_kg", "Total_Solvent_kg", "Weighted_Ratio_%", "Avg_Solvent_Per_Batch_kg", "Initial_Viscosity_Median", "Final_Viscosity_Median"]
    for c in numeric_cols:
        if c in df_display.columns:
            df_display[c] = df_display[c].round(2)
            
    st.dataframe(df_display, use_container_width=True)

# ------------------------------------------
# TAB 2: Detail Analysis
# ------------------------------------------
with tab_detail:
    st.subheader("🔍 塗料編號詳細分析 (Paint Code Deep-Dive)")
    
    # Needs a specific paint code to analyze deeply
    available_paints = df_priority["Paint_Code"].dropna().unique().tolist() if "Paint_Code" in df_priority.columns else []
    
    if not available_paints:
        st.info("No Paint Code data available for detail analysis.")
    else:
        selected_paint = st.selectbox("選擇分析塗料編號 (Select Paint Code for Deep-Dive)", available_paints)
        df_detail = df_filtered[df_filtered["Paint_Code"] == selected_paint].copy()
        
        hist_batches = df_detail["Batch_ID"].nunique()
        tot_paint = df_detail["Paint_Weight"].sum()
        tot_solvent = df_detail["Added_Weight"].sum()
        w_ratio = (tot_solvent / tot_paint * 100) if tot_paint > 0 else 0
        
        col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
        col_kpi1.metric("歷史批數 (Historical Batches)", f"{hist_batches}")
        col_kpi2.metric("總塗料使用量 (Total Paint kg)", f"{tot_paint:,.2f}")
        col_kpi3.metric("總稀釋劑量 (Total Solvent kg)", f"{tot_solvent:,.2f}")
        col_kpi4.metric("加權添加比例 (Weighted Ratio %)", f"{w_ratio:.2f}%")
        
        st.markdown("---")
        col_chart1, col_chart2 = st.columns([6, 4])
        
        with col_chart1:
            st.markdown("#### 初始黏度與稀釋劑添加比例 (Initial Viscosity vs Addition Ratio)")
            if not df_detail.empty and "Initial_Viscosity" in df_detail.columns and "Added_Weight" in df_detail.columns:
                df_detail["Addition_Ratio_%"] = (df_detail["Added_Weight"] / df_detail["Paint_Weight"].replace(0, np.nan)) * 100
                
                fig_scatter = px.scatter(
                    df_detail, 
                    x="Initial_Viscosity", 
                    y="Addition_Ratio_%",
                    hover_data=["Batch_ID", "Line"],
                    color_discrete_sequence=["lightslategray"]
                )
                
                # Add Target Reference Lines
                median_visc = df_detail["Final_Viscosity"].median()
                if pd.notna(median_visc):
                    fig_scatter.add_vline(x=median_visc, line_width=2, line_dash="dash", line_color="DeepSkyBlue", 
                                          annotation_text="Target Median Viscosity", annotation_position="top right")
                    
                fig_scatter.update_layout(margin=dict(l=0, r=0, t=30, b=0), height=350)
                st.plotly_chart(fig_scatter, use_container_width=True)
                
        with col_chart2:
            st.markdown("#### 預估潛在節省 (Estimated Potential Savings)")
            reduction_target = st.slider("預估減量比例 (Target Reduction %)", min_value=5, max_value=50, value=15, step=5)
            
            saved_kg = tot_solvent * (reduction_target / 100.0)
            
            st.info(f"**Target:** Reduce solvent usage by {reduction_target}%")
            st.success(f"**預估可減少稀釋劑量 (Estimated Reduction):** {saved_kg:,.2f} kg")
            
            # Show P10 to P90 range as supplier suggestion
            if "Final_Viscosity" in df_detail.columns:
                p10 = df_detail["Final_Viscosity"].quantile(0.10)
                p90 = df_detail["Final_Viscosity"].quantile(0.90)
                st.markdown("##### 建議供應商交貨黏度參考範圍 (Suggested Delivery Viscosity Range)")
                st.write(f"Based on historical stable production: **{p10:.1f} - {p90:.1f} s**")

# ------------------------------------------
# TAB 3: Line Comparison
# ------------------------------------------
with tab_line_compare:
    st.subheader("🏭 產線黏度比較 (Cross-Line Viscosity Comparison)")
    
    if available_paints:
        selected_paint_line = st.selectbox("選擇塗料編號 (Select Paint Code for Line Comparison)", available_paints, key="line_comp_select")
        df_line_raw = df_filtered[df_filtered["Paint_Code"] == selected_paint_line]
        
        if not df_line_raw.empty and "Line" in df_line_raw.columns:
            df_line_grouped = df_line_raw.groupby("Line").agg(
                Batches=("Batch_ID", "nunique"),
                Initial_Viscosity_Median=("Initial_Viscosity", "median"),
                Final_Viscosity_Median=("Final_Viscosity", "median"),
                Total_Paint_kg=("Paint_Weight", "sum"),
                Total_Solvent_kg=("Added_Weight", "sum")
            ).reset_index()
            
            df_line_grouped["Weighted_Ratio_%"] = (df_line_grouped["Total_Solvent_kg"] / df_line_grouped["Total_Paint_kg"].replace(0, np.nan)) * 100
            
            # Formatting
            for c in ["Total_Paint_kg", "Total_Solvent_kg", "Weighted_Ratio_%", "Initial_Viscosity_Median", "Final_Viscosity_Median"]:
                df_line_grouped[c] = df_line_grouped[c].round(2)
                
            st.dataframe(
                df_line_grouped,
                use_container_width=True,
                column_config={
                    "Line": "產線 (Line)",
                    "Batches": "批數 (Batches)",
                    "Initial_Viscosity_Median": "初始黏度中位數 (Initial Visc. Median)",
                    "Final_Viscosity_Median": "最終黏度中位數 (Final Visc. Median)",
                    "Total_Paint_kg": "總塗料量 (Total Paint kg)",
                    "Total_Solvent_kg": "總稀釋劑量 (Total Solvent kg)",
                    "Weighted_Ratio_%": "加權添加比例 (Weighted Ratio %)"
                }
            )
            
            # Auto Line Conclusion
            if len(df_line_grouped) > 1:
                max_ratio = df_line_grouped["Weighted_Ratio_%"].max()
                min_ratio = df_line_grouped["Weighted_Ratio_%"].min()
                
                if (max_ratio - min_ratio) > 5.0: # Arbitrary threshold for variance
                    st.warning("⚠️ **結論 (Conclusion):** Significant variance across lines. Check operational conditions on high-consumption lines before adjusting supplier targets.")
                else:
                    st.success("✅ **結論 (Conclusion):** Consistent high/low addition ratio across all lines. Strong evidence to adjust supplier delivery viscosity.")
        else:
            st.info("No Line data available for this paint code.")
