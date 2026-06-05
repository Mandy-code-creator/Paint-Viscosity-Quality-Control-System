import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. CHỐT CHẶN BẢO VỆ (GUARDRAIL) ---
# Kiểm tra xem dữ liệu đã được nạp ở trang chủ chưa
if 'raw_data_loaded' not in st.session_state or not st.session_state['raw_data_loaded']:
    st.warning("⚠️ Please upload data on the main page (app) first.")
    st.stop() # Dừng chạy các dòng lệnh bên dưới nếu chưa có file

# --- 2. RÚT DỮ LIỆU TỪ BỘ NHỚ ---
group_a = st.session_state['group_a_data']

# --- 3. DYNAMIC SIDEBAR FILTERS ---
st.sidebar.header("🔍 Data Filters")

# Base data
df = group_a.copy()

# 1. Vendor Filter
vendors = sorted([v for v in df['Vendor'].unique() if v != 'Unknown'])
selected_vendor = st.sidebar.selectbox("Vendor", ["All"] + vendors)

# Apply Vendor filter to Resin options
df_v = df[df['Vendor'] == selected_vendor] if selected_vendor != "All" else df
resins = sorted([r for r in df_v['Resin'].unique() if r != 'Unknown'])
selected_resin = st.sidebar.selectbox("Resin", ["All"] + resins)

# Apply Resin filter to Feature options
df_vr = df_v[df_v['Resin'] == selected_resin] if selected_resin != "All" else df_v
features = sorted([f for f in df_vr['Feature'].unique() if f not in ['Unknown', 'General']])
selected_feature = st.sidebar.selectbox("Application", ["All"] + features)

# --- 4. APPLY DATA FILTERS ---
filtered_df = df.copy()

if selected_vendor != "All":
    filtered_df = filtered_df[filtered_df['Vendor'] == selected_vendor]
if selected_resin != "All":
    filtered_df = filtered_df[filtered_df['Resin'] == selected_resin]
if selected_feature != "All":
    filtered_df = filtered_df[filtered_df['Feature'] == selected_feature]

# --- 5. GIAO DIỆN CHÍNH (MAIN UI) ---
st.title("Hiệu quả Điều chỉnh Dung môi")

# Hiển thị thông báo nếu lọc quá sâu không còn dữ liệu
if filtered_df.empty:
    st.info("Không có dữ liệu phù hợp với bộ lọc hiện tại. Vui lòng điều chỉnh lại Sidebar.")
    st.stop()

# Hiển thị KPI cơ bản
col1, col2 = st.columns(2)
with col1:
    avg_solvent = (filtered_df['Solvent_Ratio'].mean() * 100)
    st.metric("Trung bình Tỷ lệ Dung môi", f"{avg_solvent:.2f} %")
with col2:
    avg_delta_v = filtered_df['Delta_V'].mean()
    st.metric("Trung bình Độ giảm Nhớt (\u0394V)", f"{avg_delta_v:.2f} s")

st.markdown("---")

# --- 6. BIỂU ĐỒ TRỰC QUAN HÓA ---
st.subheader("Top 5 Resins by Solvent Consumption")

# Tính toán dữ liệu cho biểu đồ
resin_consumption = filtered_df.groupby('Resin')['Solvent_Ratio'].mean().reset_index()
resin_consumption['Solvent_Ratio'] = resin_consumption['Solvent_Ratio'] * 100 # Đổi ra %
# Lấy Top 5 cao nhất
resin_consumption = resin_consumption.sort_values(by='Solvent_Ratio', ascending=False).head(5)

# Vẽ biểu đồ Bar Chart bằng Plotly
fig = px.bar(
    resin_consumption, 
    x='Resin', 
    y='Solvent_Ratio',
    labels={'Solvent_Ratio': 'Avg Solvent Ratio (%)', 'Resin': 'Resin'},
    text_auto='.2f',
    # Sử dụng tông màu Deep Sky Blue theo chuẩn hệ thống
    color_discrete_sequence=['deepskyblue'] 
)

# Tối ưu giao diện biểu đồ
fig.update_layout(
    xaxis_title="Resin",
    yaxis_title="Avg Solvent Ratio (%)",
    plot_bgcolor='rgba(0,0,0,0)', # Nền trong suốt
    margin=dict(l=20, r=20, t=30, b=20)
)

# Hiển thị biểu đồ lên Streamlit
st.plotly_chart(fig, use_container_width=True)
