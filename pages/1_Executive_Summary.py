import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. SYSTEM GUARDRAIL (CHỐT CHẶN AN TOÀN) ---
# Đảm bảo người dùng phải tải file ở trang chủ trước khi xem báo cáo
if 'raw_data_loaded' not in st.session_state or not st.session_state['raw_data_loaded']:
    st.warning("⚠️ Please upload data on the main page (App) first.")
    st.stop()

# --- 2. DATA RETRIEVAL (RÚT DỮ LIỆU TỪ KÉT SẮT) ---
group_a = st.session_state['group_a_data'].copy()
rejected_data = st.session_state['rejected_data'].copy()

st.title("📊 Executive Summary")
st.markdown("---")

# --- 3. PAINT CODE DICTIONARY VERIFICATION (BẢNG KIỂM TRA MÃ SƠN) ---
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
    
    # Chỉ hiển thị các cột giải mã nếu chúng tồn tại để tránh lỗi
    display_cols = ['塗料編號', 'Paint_Code', 'Vendor', 'Resin', 'Feature', 'Color', 'Char_1']
    available_cols = [col for col in display_cols if col in group_a.columns]
    
    if available_cols:
        sample_decode = group_a[available_cols].drop_duplicates(subset=['Paint_Code'])
        st.dataframe(sample_decode, use_container_width=True)

# --- 4. SMART DATE COLUMN DETECTION (NHẬN DIỆN CỘT NGÀY THÔNG MINH) ---
# Quét tìm tên cột ngày tháng thực tế có trong file Excel
date_candidates = ['攪拌日期', '調漆日期', '日期', 'Date', '生產日期', '調漆時間']
date_column = None

for col in date_candidates:
    if col in group_a.columns:
        date_column = col
        break

# --- 5. PRODUCTION ACTIVITY CHART (BIỂU ĐỒ SẢN XUẤT) ---
st.subheader("📈 Production Activity Over Time")

if date_column is None:
    st.error("❌ System could not detect a valid Date column. Please verify your Excel file structure.")
else:
    # Nhóm dữ liệu theo Ngày VÀ Loại nhựa (Resin)
    daily_resin_activity = group_a.groupby([date_column, 'Resin']).size().reset_index(name='Number of Events')

    # Vẽ biểu đồ đường (Multi-line chart)
    fig_activity = px.line(
        daily_resin_activity,
        x=date_column,
        y='Number of Events',
        color='Resin',        # Tự động gán mỗi loại nhựa một đường màu riêng
        markers=True,
        title="Daily Valid Mix Events by Resin Type"
    )

    # Tối ưu giao diện hiển thị biểu đồ
    fig_activity.update_layout(
        xaxis_title="Date",
        yaxis_title="Number of Events",
        plot_bgcolor='rgba(0,0,0,0)',   # Nền trong suốt
        hovermode="x unified",          # Gộp chú thích khi rê chuột
        legend_title_text='Resin Type',
        margin=dict(l=20, r=20, t=40, b=20)
    )

    # Hiển thị lên giao diện
    st.plotly_chart(fig_activity, use_container_width=True)
