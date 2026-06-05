import streamlit as st
import plotly.express as px
import pandas as pd

# Set page configuration
st.set_page_config(page_title="Viscosity Analysis", page_icon="🔬", layout="wide")

st.title("🔬 Viscosity Analysis Report")

# 1. Sidebar Filters (Giữ nguyên để đảm bảo chức năng lọc)
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()

st.sidebar.header("🔍 Analysis Filters")
vendors = sorted([v for v in group_a['Vendor'].unique() if v != 'Unknown'])
selected_vendor = st.sidebar.selectbox("Vendor", ["All"] + vendors)
df_v = group_a[group_a['Vendor'] == selected_vendor] if selected_vendor != "All" else group_a

# 2. Aggregating Data
summary_df = df_v.groupby(['Resin', 'Solvent_Type'])['Viscosity_Sensitivity'].agg(['mean', 'std']).reset_index()
resins = sorted(summary_df['Resin'].unique())

# 3. Hiển thị biểu đồ theo tỉ lệ chuẩn Word
# Chiều cao 400px, chiều rộng cố định để khi copy vào Word không bị vỡ hình
st.markdown("### Sensitivity Analysis by Resin")
for resin in resins:
    st.markdown(f"**Resin: {resin}**")
    resin_data = summary_df[summary_df['Resin'] == resin]
    
    fig = px.bar(
        resin_data,
        x='Solvent_Type',
        y='mean',
        error_y='std',
        title=f"Sensitivity Profile for {resin}",
        labels={'mean': 'Sensitivity (sec/1%)', 'Solvent_Type': 'Solvent'},
        color='mean',
        color_continuous_scale='Blues'
    )
    
    # Cấu hình chuẩn báo cáo: Nền trắng, viền rõ, font to
    fig.update_layout(
        plot_bgcolor='white',
        height=350, # Chiều cao này vừa vặn trong 1 trang Word
        font=dict(size=14),
        margin=dict(l=50, r=50, t=50, b=50)
    )
    fig.update_yaxes(showgrid=True, gridcolor='lightgray', linecolor='black', linewidth=1)
    fig.update_xaxes(showline=True, linecolor='black', linewidth=1)
    
    st.plotly_chart(fig, use_container_width=True)
