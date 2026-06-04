import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. SETUP & DATA RETRIEVAL ---
if 'raw_data_loaded' not in st.session_state or not st.session_state['raw_data_loaded']:
    st.warning("⚠️ Please upload data on the main page (App) first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()
rejected_data = st.session_state['rejected_data'].copy()

# Global calculations for Sensitivity
group_a['Solvent_Ratio_Percent'] = (group_a['添加重量'] / group_a['塗料重量']) * 100
group_a['Sensitivity'] = group_a['Delta_V'] / (group_a['Solvent_Ratio_Percent'].replace(0, 1))

st.title("📊 Executive Summary")
st.markdown("---")

# --- 2. KPI METRICS ---
st.subheader("💡 Key Performance Indicators")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="Total Valid Batches", value=f"{len(group_a):,} batches")
with col2:
    st.metric(label="Total Paint Used", value=f"{group_a['塗料重量'].sum():,.1f} kg")
with col3:
    st.metric(label="Avg Solvent Ratio", value=f"{(group_a['Solvent_Ratio_Percent'].mean()):.2f} %")
with col4:
    st.metric(label="Data Errors (Rejected)", value=f"{len(rejected_data)} rows")

st.markdown("---")

# --- 3. OPTIMIZED SENSITIVITY HEATMAP ---
st.subheader("🌡️ Solvent Usage Efficiency Heatmap")

# 1. Định nghĩa các "thùng" (bins) để chia ma trận
# Trục X: Tỷ lệ dung môi (Solvent Ratio %)
# Trục Y: Độ nhớt ban đầu (Initial Viscosity - 黏度(秒))
group_a['Solvent_Bin'] = pd.cut(group_a['Solvent_Ratio_Percent'], bins=10)
group_a['Initial_V_Bin'] = pd.cut(group_a['黏度(秒)'], bins=10)

# 2. Tạo Pivot Table cho Heatmap (Giá trị là Sensitivity - Hiệu quả giảm nhớt)
heatmap_data = group_a.groupby(['Initial_V_Bin', 'Solvent_Bin'])['Sensitivity'].mean().reset_index()
pivot_table = heatmap_data.pivot(index='Initial_V_Bin', columns='Solvent_Bin', values='Sensitivity')

# 3. Vẽ Heatmap
fig_heatmap = px.imshow(
    pivot_table,
    text_auto=".1f",
    aspect="auto",
    color_continuous_scale='RdYlGn', # Màu sắc phản ánh độ hiệu quả
    labels=dict(x="Solvent Ratio (%)", y="Initial Viscosity (s)", color="Sensitivity"),
    title="Optimal Solvent Usage: Efficiency based on Initial Viscosity"
)

fig_heatmap.update_layout(
    xaxis_title="Solvent Ratio (%)",
    yaxis_title="Initial Viscosity (s)"
)

st.plotly_chart(fig_heatmap, use_container_width=True)

st.caption("""
**Heatmap Insights:**
* **X-Axis:** Percentage of solvent added relative to paint weight.
* **Y-Axis:** Initial viscosity before adjustment.
* **Cell Color:** Higher Sensitivity (Green) means the solvent is performing at its peak efficiency.
""")

st.markdown("---")

# --- 4. DATA TABLE (RESIN & VENDOR PERFORMANCE) ---
st.subheader("📋 Resin & Vendor Performance Analysis")

# Perform the grouping for the table
detailed_summary = group_a.groupby(['Resin', 'Vendor']).agg({
    '塗料批號': 'nunique',
    '塗料重量': 'sum',
    '添加重量': 'sum',
    '黏度(秒)': 'mean',
    '黏度(秒)_1': 'mean',
    'Solvent_Ratio_Percent': 'mean'
}).rename(columns={
    '塗料批號': 'Batches',
    '塗料重量': 'Total Paint (kg)',
    '添加重量': 'Total Solvent (kg)',
    '黏度(秒)': 'Initial V (s)',
    '黏度(秒)_1': 'Final V (s)',
    'Solvent_Ratio_Percent': 'Avg Solvent %'
})

# Display the table
st.dataframe(detailed_summary.style.format({
    'Total Paint (kg)': '{:,.0f}',
    'Total Solvent (kg)': '{:,.0f}',
    'Initial V (s)': '{:.2f}',
    'Final V (s)': '{:.2f}',
    'Avg Solvent %': '{:.2f} %'
}), use_container_width=True)

st.caption("""
**Metrics Definition:**
* **Batches:** Number of valid mix events.
* **Total Paint / Solvent (kg):** Aggregate consumption.
* **Avg Solvent %:** Average solvent-to-paint ratio.
""")
