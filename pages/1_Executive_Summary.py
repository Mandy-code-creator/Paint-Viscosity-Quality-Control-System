import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. SYSTEM GUARDRAIL ---
if 'raw_data_loaded' not in st.session_state or not st.session_state['raw_data_loaded']:
    st.warning("⚠️ Please upload data on the main page (App) first.")
    st.stop()

# --- 2. DATA RETRIEVAL ---
group_a = st.session_state['group_a_data'].copy()
rejected_data = st.session_state['rejected_data'].copy()

st.title("📊 Executive Summary")
st.markdown("---")

# --- 3. PHÂN TÍCH HIỆU QUẢ THEO NHỰA, NHÀ CUNG CẤP & ĐỊNH MỨC DUNG MÔI ---
st.subheader("💡 Resin & Vendor Performance Analysis")

# Tính toán tỷ lệ dung môi cho từng mẻ
group_a['Solvent_Ratio_Percent'] = (group_a['添加重量'] / group_a['塗料重量']) * 100

# Nhóm dữ liệu theo Resin VÀ Vendor
detailed_summary = group_a.groupby(['Resin', 'Vendor']).agg({
    '塗料批號': 'nunique',                # Tổng số mẻ
    '塗料重量': 'sum',                    # Tổng trọng lượng sơn
    '添加重量': 'sum',                    # Tổng trọng lượng dung môi
    '黏度(秒)': 'mean',                   # Độ nhớt gốc
    '黏度(秒)_1': 'mean',                 # Độ nhớt sau pha
    'Solvent_Ratio_Percent': 'mean'       # Tỷ lệ dung môi (%)
}).rename(columns={
    '塗料批號': 'Batches',
    '塗料重量': 'Total Paint (kg)',
    '添加重量': 'Total Solvent (kg)',
    '黏度(秒)': 'Initial V (s)',
    '黏度(秒)_1': 'Final V (s)',
    'Solvent_Ratio_Percent': 'Avg Solvent %'
})

# Hiển thị bảng phân tích chi tiết
st.dataframe(detailed_summary.style.format({
    'Total Paint (kg)': '{:,.0f}',
    'Total Solvent (kg)': '{:,.0f}',
    'Initial V (s)': '{:.2f}',
    'Final V (s)': '{:.2f}',
    'Avg Solvent %': '{:.2f} %'
}), use_container_width=True)

st.markdown("""
* **Total Batches:** Số lượng mẻ sơn hợp lệ.
* **Total Paint / Solvent (kg):** Tổng khối lượng sơn và dung môi đã tiêu thụ.
* **Avg Solvent %:** Tỷ lệ trung bình của dung môi so với sơn (Cảnh báo: Nếu tỷ lệ này vượt ngưỡng chuẩn cho từng loại nhựa, cần kiểm tra lại quy trình).
""")
st.markdown("---")

# --- 4. PAINT CODE DICTIONARY VERIFICATION ---
with st.expander("📖 Paint Code Dictionary Verification"):
    st.markdown("""
    **System Decoding Logic:**
    * **Index 0:** Primary Classification (Char_1)
    * **Index 1:** Vendor
    * **Index 2:** Resin
    * **Index 3:** Application / Feature
    * **Index 6:** Color
    """)
    
    st.info("👇 Auto-decoded results from your raw data:")
    
    display_cols = ['塗料編號', 'Paint_Code', 'Vendor', 'Resin', 'Feature', 'Color', 'Char_1']
    available_cols = [col for col in display_cols if col in group_a.columns]
    
    if available_cols:
        sample_decode = group_a[available_cols].drop_duplicates(subset=['Paint_Code'])
        st.dataframe(sample_decode, use_container_width=True)

# --- 5. SMART DATE COLUMN DETECTION ---
date_candidates = ['攪拌日期', '調漆日期', '日期', 'Date', '生產日期', '調漆時間']
date_column = None

for col in date_candidates:
    if col in group_a.columns:
        date_column = col
        break

# --- 6. VISCOSITY TREND CHARTS (SEPARATED BY RESIN) ---
st.subheader("📈 Viscosity Trend Over Time by Resin")

if date_column is None:
    st.error("❌ System could not detect a valid Date column.")
else:
    # Group data by Date and Resin, calculate the MEAN of Viscosity
    # Chúng ta sử dụng '黏度(秒)' để xem độ nhớt gốc (Initial Viscosity)
    daily_viscosity_trend = group_a.groupby([date_column, 'Resin'])['黏度(秒)'].mean().reset_index()
    
    unique_resins = sorted([r for r in daily_viscosity_trend['Resin'].unique() if pd.notna(r)])
    cols = st.columns(2)

    for i, resin in enumerate(unique_resins):
        resin_data = daily_viscosity_trend[daily_viscosity_trend['Resin'] == resin]

        fig_viscosity = px.line(
            resin_data,
            x=date_column,
            y='黏度(秒)',
            markers=True,
            title=f"Average Initial Viscosity: {resin}",
            color_discrete_sequence=['deepskyblue'] 
        )

        fig_viscosity.update_layout(
            xaxis_title="Date",
            yaxis_title="Viscosity (s)",
            plot_bgcolor='rgba(0,0,0,0)',   
            hovermode="x unified",          
            margin=dict(l=20, r=20, t=40, b=20)
        )

        cols[i % 2].plotly_chart(fig_viscosity, use_container_width=True)
