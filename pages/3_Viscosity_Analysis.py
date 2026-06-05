import streamlit as st
import plotly.express as px
import pandas as pd

# Set page configuration
st.set_page_config(page_title="Viscosity Analysis", page_icon="🔬", layout="wide")

st.title("🔬 Viscosity Analysis Dashboard")
st.markdown("Select a Resin Type to view its detailed sensitivity profile.")

# 1. Global State Check
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()

# 2. Logic: Nhóm dữ liệu
summary_df = group_a.groupby(['Resin', 'Solvent_Type'])['Viscosity_Sensitivity'].agg(['mean', 'std']).reset_index()
resins = sorted(summary_df['Resin'].unique())

# 3. Tạo Tabs để tách biệt các nhựa - Nhìn sẽ cực kỳ gọn và chuyên nghiệp
tabs = st.tabs(resins)

for i, resin in enumerate(resins):
    with tabs[i]:
        st.subheader(f"Sensitivity Profile: {resin}")
        
        # Lọc dữ liệu
        resin_data = summary_df[summary_df['Resin'] == resin]
        
        # Vẽ biểu đồ với thiết kế tối giản, chuyên nghiệp
        fig = px.bar(
            resin_data,
            x='Solvent_Type',
            y='mean',
            error_y='std',
            title=f"How solvents affect {resin}",
            labels={'mean': 'Sensitivity (sec/1%)', 'Solvent_Type': 'Solvent Type'},
            color='mean',
            color_continuous_scale='Viridis'
        )
        
        # Cấu hình để biểu đồ "đẹp" hơn
        fig.update_layout(
            plot_bgcolor='white',
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor='lightgray'),
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Thêm bảng dữ liệu chi tiết bên dưới để tiện tra cứu
        st.dataframe(resin_data.sort_values(by='mean', ascending=False), use_container_width=True)
