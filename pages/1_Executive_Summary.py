import plotly.express as px
import streamlit as st
import pandas as pd

# --- 1. RÚT DỮ LIỆU TỪ BỘ NHỚ (ĐÂY LÀ BƯỚC BẠN BỊ THIẾU) ---
# Đảm bảo hệ thống đã tải file trước khi chạy
if 'raw_data_loaded' not in st.session_state or not st.session_state['raw_data_loaded']:
    st.warning("⚠️ Please upload data on the main page (app) first.")
    st.stop()

group_a = st.session_state['group_a_data']

# --- 2. XỬ LÝ DỮ LIỆU NGÀY THÁNG ---
# BẠN LƯU Ý: Đổi chữ 'Date' dưới đây thành đúng tên cột ngày tháng trong file Excel của bạn 
# (Ví dụ: '調漆日期', 'Date', hoặc '生產日期'...)
date_column = 'Date' 

# Nhóm theo Ngày VÀ Loại nhựa (Resin)
daily_resin_activity = group_a.groupby([date_column, 'Resin']).size().reset_index(name='Number of Events')

# --- 3. VẼ BIỂU ĐỒ NHIỀU ĐƯỜNG ---
fig_activity = px.line(
    daily_resin_activity,
    x=date_column,
    y='Number of Events',
    color='Resin',        # Tách mỗi loại nhựa thành 1 đường
    markers=True,
    title="Daily Valid Mix Events by Resin Type"
)

# --- 4. TỐI ƯU GIAO DIỆN HIỂN THỊ (Tiếng Anh 100%) ---
fig_activity.update_layout(
    xaxis_title="Date",
    yaxis_title="Number of Events",
    plot_bgcolor='rgba(0,0,0,0)',   
    hovermode="x unified",          
    legend_title_text='Resin Type',
    margin=dict(l=20, r=20, t=40, b=20)
)

# Render lên giao diện
st.subheader("📈 Production Activity Over Time")
st.plotly_chart(fig_activity, use_container_width=True)
