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
st.subheader("🌡️ Process Sensitivity Heatmap (Solvent Efficiency)")

# Filters
unique_resins = group_a['Resin'].unique()
unique_vendors = group_a['Vendor'].unique()

col_f1, col_f2 = st.columns(2)
with col_f1:
    selected_resin = st.selectbox("Filter Heatmap by Resin", unique_resins, index=0)
with col_f2:
    selected_vendors = st.multiselect("Filter Heatmap by Vendor", unique_vendors, default=unique_vendors)

# Filter data
filtered_data = group_a[
    (group_a['Resin'] == selected_resin) & 
    (group_a['Vendor'].isin(selected_vendors))
].copy()

if not filtered_data.empty:
    # 1. Manual Bins: Define clean, readable intervals
    solvent_bins = [0, 2, 4, 6, 8, 10, 12, 15, 20]
    viscosity_bins = [50, 70, 90, 110, 130, 150, 170, 190, 210, 250]

    filtered_data['Solvent_Bin'] = pd.cut(filtered_data['Solvent_Ratio_Percent'], bins=solvent_bins)
    filtered_data['Initial_V_Bin'] = pd.cut(filtered_data['黏度(秒)'], bins=viscosity_bins)

    # Group and pivot
    heatmap_data = filtered_data.groupby(['Initial_V_Bin', 'Solvent_Bin'], observed=False)['Sensitivity'].mean().reset_index()
    pivot_table = heatmap_data.pivot(index='Initial_V_Bin', columns='Solvent_Bin', values='Sensitivity')

    # 2. Extract mathematical order BEFORE converting to strings
    correct_x_order = [str(col) for col in pivot_table.columns]
    correct_y_order = [str(idx) for idx in pivot_table.index]

    # FIX: Convert Interval indices/columns to strings to avoid JSON errors
    pivot_table.index = pivot_table.index.astype(str)
    pivot_table.columns = pivot_table.columns.astype(str)

    # Draw Heatmap
    fig_heatmap = px.imshow(
        pivot_table,
        text_auto=".1f",
        aspect="auto",
        color_continuous_scale='RdYlGn',
        labels=dict(x="Solvent Ratio (%)", y="Initial Viscosity (s)", color="Sensitivity"),
        title=f"Efficiency based on Initial Viscosity ({selected_resin})"
    )

    # 3. Force Plotly to respect the mathematical order, not alphabetical
    fig_heatmap.update_xaxes(categoryorder='array', categoryarray=correct_x_order)
    fig_heatmap.update_yaxes(categoryorder='array', categoryarray=correct_y_order)

    st.plotly_chart(fig_heatmap, use_container_width=True)
    
    # --- THÊM MỚI: CÔNG THỨC VÀ MÁY TÍNH DƯỚI BIỂU ĐỒ ---
    st.info("""
    **SOP: HƯỚNG DẪN TÍNH TOÁN LƯỢNG DUNG MÔI CẦN CHÂM**
    1. Đo độ nhớt thực tế của thùng sơn hiện tại.
    2. Dóng trên biểu đồ để tìm ô **Màu Xanh Lá (Sensitivity cao nhất)** tương ứng với độ nhớt đó.
    3. Nhìn xuống trục ngang để lấy **Tỷ lệ dung môi tối ưu (%)**.
    
    **Công thức:** **Khối lượng dung môi (kg) = Khối lượng sơn (kg) × Tỷ lệ dung môi tối ưu (%)**
    """)

    with st.expander("🧮 Máy Tính Pha Dung Môi Nhanh (Quick Calculator)", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            paint_weight = st.number_input("1. Nhập Khối lượng sơn (kg)", min_value=0.0, value=200.0, step=10.0)
        with c2:
            optimal_ratio = st.number_input("2. Nhập Tỷ lệ tối ưu từ biểu đồ (%)", min_value=0.0, value=7.0, step=0.5)
        with c3:
            required_solvent = paint_weight * (optimal_ratio / 100)
            st.success(f"**Lượng dung môi cần đổ:**\n### {required_solvent:.2f} kg")

else:
    st.warning("No data available for the selected filters.")

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
