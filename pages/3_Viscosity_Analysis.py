import streamlit as st
import plotly.express as px
import pandas as pd

# Cấu hình trang
st.set_page_config(page_title="Viscosity Analysis Report", page_icon="🔬", layout="wide")

st.title("🔬 Viscosity Analysis Report")
st.markdown("Detailed breakdown of solvent sensitivity per resin type. Each chart represents a specific resin's reaction to different solvents.")

# 1. State Check & Data Loading
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please upload your data file first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()

# Ép kiểu dữ liệu để biểu đồ không bị dàn trải (Category/String)
group_a['Solvent_Type'] = group_a['Solvent_Type'].astype(str)

# 2. Logic: Nhóm dữ liệu 
# Lưu ý: Sử dụng toàn bộ dữ liệu để so sánh hiệu quả giữa các loại dung môi
summary_df = group_a.groupby(['Resin', 'Solvent_Type'])['Viscosity_Sensitivity'].agg(['mean', 'std']).reset_index()
resins = sorted(summary_df['Resin'].unique())

# 3. Định nghĩa bảng màu cố định cho từng loại dung môi
all_solvents = sorted(group_a['Solvent_Type'].unique())
color_map = {solvent: px.colors.qualitative.Plotly[i % len(px.colors.qualitative.Plotly)] 
             for i, solvent in enumerate(all_solvents)}

# 4. Hiển thị báo cáo dạng lưới 2 cột
st.markdown("---")
for i in range(0, len(resins), 2):
    cols = st.columns(2)
    for j in range(2):
        if i + j < len(resins):
            resin = resins[i + j]
            with cols[j]:
                st.markdown(f"#### Resin Type: {resin}")
                resin_data = summary_df[summary_df['Resin'] == resin].copy()
                
                # Vẽ biểu đồ Bar
                fig = px.bar(
                    resin_data,
                    x='Solvent_Type',
                    y='mean',
                    error_y='std',
                    labels={'mean': 'Sensitivity (sec/1%)', 'Solvent_Type': 'Solvent'},
                    color='Solvent_Type',
                    color_discrete_map=color_map,
                    title=f"Sensitivity Profile for {resin}"
                )
                
                # Cấu hình chuẩn báo cáo: Nền trắng, đường kẻ đen rõ nét
                fig.update_layout(
                    plot_bgcolor='white',
                    height=300,
                    font=dict(size=12),
                    margin=dict(l=40, r=40, t=40, b=30),
                    showlegend=False
                )
                # Ép trục X về dạng category, đảm bảo các cột hiển thị độc lập
                fig.update_xaxes(type='category', showline=True, linecolor='black', linewidth=1)
                fig.update_yaxes(showgrid=True, gridcolor='lightgray', linecolor='black', linewidth=1)
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Bảng tổng hợp số liệu để dễ copy vào Word
                st.dataframe(
                    resin_data.rename(columns={'mean': 'Mean', 'std': 'Std Dev'}),
                    use_container_width=True,
                    height=150
                )
# --- 5. Biểu đồ hồi quy so sánh nhiều resin ---
st.markdown("---")
st.subheader("📈 Comparative Regression: Solvent vs. Viscosity")

# Chuẩn bị dữ liệu giả lập hoặc thực tế
regression_df = group_a.copy()
regression_df['Solvent_Ratio_Percent'] = (regression_df['添加重量'] / regression_df['塗料重量']) * 100

# Vẽ scatter + trendline cho từng resin
fig_regression = px.scatter(
    regression_df,
    x='Solvent_Ratio_Percent',
    y='黏度(秒)',
    color='Resin',
    trendline='ols',
    labels={'Solvent_Ratio_Percent': 'Solvent Added (%)', '黏度(秒)': 'Viscosity (s)'},
    title="Solvent Added vs. Viscosity Reduction (Multi-Resin Comparison)"
)

fig_regression.update_layout(
    plot_bgcolor='white',
    font=dict(size=12),
    margin=dict(l=40, r=40, t=60, b=40),
    legend_title_text='Resin Type'
)
fig_regression.update_xaxes(showline=True, linecolor='black', linewidth=1)
fig_regression.update_yaxes(showgrid=True, gridcolor='lightgray', linecolor='black', linewidth=1)

st.plotly_chart(fig_regression, use_container_width=True)

st.caption("""
💡 **Interpretation:**
Each color represents a resin type. The slope of each trendline shows how quickly viscosity decreases as solvent increases.
* Steeper slope → higher solvent sensitivity.
* Flatter slope → lower solvent efficiency.
""")
