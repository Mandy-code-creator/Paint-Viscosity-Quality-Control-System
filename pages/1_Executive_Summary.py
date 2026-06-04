import plotly.express as px
import streamlit as st
import pandas as pd

# --- Đảm bảo cột ngày tháng đã chuẩn hóa ---
# Thay 'Date' bằng tên cột ngày thực tế trong file của bạn (vd: '生產日期' hoặc 'Ngày')
date_column = 'Date' 

# --- 1. XỬ LÝ DỮ LIỆU: Nhóm theo Ngày VÀ Loại nhựa (Resin) ---
# Đếm số lượng sự kiện (Coil mix) theo từng ngày cho mỗi loại Resin
daily_resin_activity = group_a.groupby([date_column, 'Resin']).size().reset_index(name='Number of Events')

# --- 2. VẼ BIỂU ĐỒ NHIỀU ĐƯỜNG (MULTI-LINE CHART) ---
fig_activity = px.line(
    daily_resin_activity,
    x=date_column,
    y='Number of Events',
    color='Resin',        # <-- ĐÂY LÀ CHÌA KHÓA: Tách mỗi loại nhựa thành 1 đường riêng biệt
    markers=True,
    title="Daily Valid Mix Events by Resin Type"
)

# --- 3. TỐI ƯU GIAO DIỆN HIỂN THỊ ---
fig_activity.update_layout(
    xaxis_title="Date",
    yaxis_title="Number of Events",
    plot_bgcolor='rgba(0,0,0,0)',   # Nền trong suốt
    hovermode="x unified",          # Gộp tooltip: Trỏ chuột vào 1 ngày sẽ hiện thông số của tất cả các loại nhựa
    legend_title_text='Resin Type',
    margin=dict(l=20, r=20, t=40, b=20)
)

# Render lên giao diện (Giao diện chuẩn tiếng Anh)
st.subheader("📈 Production Activity Over Time")
st.plotly_chart(fig_activity, use_container_width=True)
