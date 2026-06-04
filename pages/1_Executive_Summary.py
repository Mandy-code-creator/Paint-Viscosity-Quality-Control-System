import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. CHỐT CHẶN AN TOÀN ---
if 'raw_data_loaded' not in st.session_state or not st.session_state['raw_data_loaded']:
    st.warning("⚠️ Please upload data on the main page (App) first.")
    st.stop()

# --- 2. RÚT DỮ LIỆU TỪ BỘ NHỚ (ĐÂY LÀ DÒNG FIX LỖI NAME ERROR) ---
group_a = st.session_state['group_a_data'].copy()

st.title("📊 Executive Summary")
st.markdown("---")

# --- 3. BẢNG KIỂM TRA TỪ ĐIỂN MÃ SƠN ---
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

# --- 4. TỰ ĐỘNG NHẬN DIỆN NGÀY THÁNG (Đã thêm 攪拌日期) ---
date_candidates = ['攪拌日期', '調漆日期', '日期', 'Date', '生產日期', '調漆時間']
date_column = None

for col in date_candidates:
    if col in group_a.columns:
        date_column = col
        break

# --- 5. VẼ BIỂU ĐỒ ---
st.subheader("📈 Production Activity Over Time")

if date_column is None:
    st.error("❌ System could not detect a valid Date column. Please verify your Excel file structure.")
else:
    # Logic nhóm dữ liệu không còn bị lỗi nữa vì group_a đã được định nghĩa ở bước 2
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
