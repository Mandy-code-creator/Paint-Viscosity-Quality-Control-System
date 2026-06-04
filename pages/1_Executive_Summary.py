import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. SYSTEM GUARDRAIL (CHỐT CHẶN AN TOÀN) ---
if 'raw_data_loaded' not in st.session_state or not st.session_state['raw_data_loaded']:
    st.warning("⚠️ Please upload data on the main page (App) first.")
    st.stop()

# --- 2. DATA RETRIEVAL (RÚT DỮ LIỆU TỪ KÉT SẮT) ---
group_a = st.session_state['group_a_data'].copy()
rejected_data = st.session_state['rejected_data'].copy()

st.title("📊 Executive Summary")
st.markdown("---")

# ==============================================================
# --- 3. PHẦN MỚI PHỤC HỒI: KEY PERFORMANCE INDICATORS (KPIs) ---
# ==============================================================
st.subheader("💡 Key Performance Indicators")

# Chia màn hình thành 4 cột để hiển thị số liệu cho đẹp mắt
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="Total Valid Mixes", 
        value=f"{len(group_a):,} coils",
        help="Tổng số mẻ sơn hợp lệ được đưa vào phân tích SPC (Group A)"
    )

with col2:
    total_paint = group_a['塗料重量'].sum() if '塗料重量' in group_a.columns else 0
    st.metric(
        label="Total Paint Used", 
        value=f"{total_paint:,.1f} kg"
    )

with col3:
    avg_solvent = (group_a['Solvent_Ratio'].mean() * 100) if not group_a.empty else 0
    st.metric(
        label="Avg Solvent Ratio", 
        value=f"{avg_solvent:.2f} %"
    )

with col4:
    st.metric(
        label="Data Errors (Rejected)", 
        value=f"{len(rejected_data)} rows",
        help="Số dòng bị loại bỏ do nhập thiếu/sai dữ liệu dung môi hoặc độ nhớt"
    )

st.markdown("---")

# --- 4. PAINT CODE DICTIONARY VERIFICATION (BẢNG KIỂM TRA MÃ SƠN) ---
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

# --- 5. SMART DATE COLUMN DETECTION (NHẬN DIỆN CỘT NGÀY THÔNG MINH) ---
date_candidates = ['攪拌日期', '調漆日期', '日期', 'Date', '生產日期', '調漆時間']
date_column = None

for col in date_candidates:
    if col in group_a.columns:
        date_column = col
        break

# --- 6. PRODUCTION ACTIVITY CHART (BIỂU ĐỒ SẢN XUẤT) ---
st.subheader("📈 Production Activity Over Time")

if date_column is None:
    st.error("❌ System could not detect a valid Date column. Please verify your Excel file structure.")
else:
    daily_resin_activity = group_a.groupby([date_column, 'Resin']).size().reset_index(name='Number of Events')

    fig_activity = px.line(
        daily_resin_activity,
        x=date_column,
        y='Number of Events',
        color='Resin',
        markers=True,
        title="Daily Valid Mix Events by Resin Type"
    )

    fig_activity.update_layout(
        xaxis_title="Date",
        yaxis_title="Number of Events",
        plot_bgcolor='rgba(0,0,0,0)',   
        hovermode="x unified",          
        legend_title_text='Resin Type',
        margin=dict(l=20, r=20, t=40, b=20)
    )

    st.plotly_chart(fig_activity, use_container_width=True)
