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
group_a['Solvent_Type'] = group_a['Solvent_Type'].astype(str)

# 2. Sidebar Filters
st.sidebar.header("🔍 Analysis Filters")
vendors = sorted([v for v in group_a['Vendor'].unique() if v != 'Unknown'])
selected_vendor = st.sidebar.selectbox("Vendor", ["All"] + vendors)
df_v = group_a[group_a['Vendor'] == selected_vendor] if selected_vendor != "All" else group_a

# 3. Aggregating Data
summary_df = df_v.groupby(['Resin', 'Solvent_Type'])['Viscosity_Sensitivity'].agg(['mean', 'std']).reset_index()
resins = sorted(summary_df['Resin'].unique())

# 4. Định nghĩa bảng màu cố định
all_solvents = sorted(group_a['Solvent_Type'].unique())
color_map = {solvent: px.colors.qualitative.Plotly[i % len(px.colors.qualitative.Plotly)] 
             for i, solvent in enumerate(all_solvents)}

# 5. Hiển thị biểu đồ theo cặp (2 biểu đồ/hàng)
st.markdown("### Sensitivity Analysis by Resin")

# Chia danh sách nhựa thành các cặp
for i in range(0, len(resins), 2):
    cols = st.columns(2) # Tạo 2 cột
    
    for j in range(2):
        if i + j < len(resins):
            resin = resins[i + j]
            with cols[j]:
                st.markdown(f"#### Resin Type: {resin}")
                resin_data = summary_df[summary_df['Resin'] == resin].copy()
                
                fig = px.bar(
                    resin_data,
                    x='Solvent_Type',
                    y='mean',
                    error_y='std',
                    labels={'mean': 'Sensitivity (sec/1%)', 'Solvent_Type': 'Solvent'},
                    color='Solvent_Type',
                    color_discrete_map=color_map
                )
                
                fig.update_layout(
                    plot_bgcolor='white',
                    height=300, # Chiều cao gọn để báo cáo
                    font=dict(size=12),
                    margin=dict(l=40, r=40, t=30, b=30),
                    showlegend=False # Tắt legend để hình to hơn
                )
                fig.update_xaxes(type='category', showline=True, linecolor='black')
                fig.update_yaxes(showgrid=True, gridcolor='lightgray', linecolor='black')
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Bảng dữ liệu thu gọn
                st.dataframe(
                    resin_data.rename(columns={'mean': 'Mean', 'std': 'Std Dev'}),
                    use_container_width=True,
                    height=150
                )
