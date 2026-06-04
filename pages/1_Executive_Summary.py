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

# --- 3. HEATMAP ANALYSIS ---
st.subheader("🌡️ Process Sensitivity Heatmap (Temperature vs Humidity)")

col_f1, col_f2 = st.columns(2)
with col_f1:
    selected_resin = st.selectbox("Filter Heatmap by Resin", group_a['Resin'].unique())
with col_f2:
    selected_vendors = st.multiselect("Filter Heatmap by Vendor", group_a['Vendor'].unique(), default=group_a['Vendor'].unique())

filtered_data = group_a[(group_a['Resin'] == selected_resin) & (group_a['Vendor'].isin(selected_vendors))]
filtered_data['Temp_Bin'] = filtered_data['Temperature'].round(0)
filtered_data['Hum_Bin'] = filtered_data['Humidity'].round(0)
heatmap_data = filtered_data.groupby(['Hum_Bin', 'Temp_Bin'])['Sensitivity'].mean().reset_index()
pivot_table = heatmap_data.pivot(index='Hum_Bin', columns='Temp_Bin', values='Sensitivity').sort_index(ascending=False)

fig_heatmap = px.imshow(
    pivot_table,
    text_auto=".1f",
    aspect="auto",
    color_continuous_scale='RdBu_r',
    labels=dict(x="Temperature (°C)", y="Humidity (%)", color="Sensitivity"),
    title=f"Avg Sensitivity: How environment affects solvent efficiency ({selected_resin})"
)
st.plotly_chart(fig_heatmap, use_container_width=True)
st.caption("**Sensitivity:** Viscosity reduction (s) achieved per 1% of solvent added. Darker blue indicates higher efficiency.")

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
