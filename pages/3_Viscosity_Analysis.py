import streamlit as st
import plotly.express as px
import pandas as pd

# Set page configuration
st.set_page_config(page_title="Viscosity Analysis Report", page_icon="🔬", layout="wide")

st.title("🔬 Viscosity Analysis Report")

# 1. State Check & Data Loading
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()

# 2. Sidebar Filters
st.sidebar.header("🔍 Analysis Filters")
vendors = sorted([v for v in group_a['Vendor'].unique() if v != 'Unknown'])
selected_vendor = st.sidebar.selectbox("Vendor", ["All"] + vendors)
df_v = group_a[group_a['Vendor'] == selected_vendor] if selected_vendor != "All" else group_a

# 3. Aggregating Data
summary_df = df_v.groupby(['Resin', 'Solvent_Type'])['Viscosity_Sensitivity'].agg(['mean', 'std']).reset_index()
resins = sorted(summary_df['Resin'].unique())

# 4. Định nghĩa bảng màu cố định cho từng loại dung môi
all_solvents = sorted(group_a['Solvent_Type'].unique())
color_map = {solvent: px.colors.qualitative.Plotly[i % len(px.colors.qualitative.Plotly)] 
             for i, solvent in enumerate(all_solvents)}

# 5. Hiển thị biểu đồ và bảng dữ liệu cho từng loại nhựa
st.markdown("### Sensitivity Analysis by Resin")
for resin in resins:
    st.markdown(f"---")
    st.markdown(f"#### Resin Type: {resin}")
    resin_data = summary_df[summary_df['Resin'] == resin].copy()
    
    # Vẽ biểu đồ Bar
    fig = px.bar(
        resin_data,
        x='Solvent_Type',
        y='mean',
        error_y='std',
        title=f"Sensitivity Profile for {resin}",
        labels={'mean': 'Avg Sensitivity (sec/1%)', 'Solvent_Type': 'Solvent'},
        color='Solvent_Type', # Gán màu theo dung môi
        color_discrete_map=color_map # Áp dụng bảng màu đồng nhất
    )
    
    # Cấu hình chuẩn báo cáo
    fig.update_layout(
        plot_bgcolor='white',
        height=350,
        font=dict(size=14),
        margin=dict(l=50, r=50, t=50, b=50),
        showlegend=True
    )
    fig.update_yaxes(showgrid=True, gridcolor='lightgray', linecolor='black', linewidth=1)
    fig.update_xaxes(showline=True, linecolor='black', linewidth=1)
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Bảng tổng hợp giá trị
    st.markdown(f"**Data Summary for {resin}:**")
    st.dataframe(
        resin_data.rename(columns={'mean': 'Mean Sensitivity', 'std': 'Std Dev'}),
        use_container_width=True
    )
