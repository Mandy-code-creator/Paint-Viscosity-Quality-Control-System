import streamlit as st
import plotly.express as px
import pandas as pd

# --- 1. Cấu hình trang ---
st.set_page_config(page_title="Viscosity & SOP Report", page_icon="📊", layout="wide")
st.title("📊 Viscosity & SOP Analysis Dashboard")
st.markdown("Comparative regression, SOP matrix, and trendline visualization for Resin – Vendor – Solvent.")

# --- 2. Kiểm tra dữ liệu ---
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please upload your data file first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()
group_a['Solvent_Type'] = group_a['Solvent_Type'].astype(str)
group_a['Solvent_Ratio_Percent'] = (group_a['添加重量'] / group_a['塗料重量']) * 100

# --- 3. Bộ lọc ---
unique_resins = sorted(group_a['Resin'].unique())
unique_vendors = sorted(group_a['Vendor'].unique())
unique_solvents = sorted(group_a['Solvent_Type'].unique())

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    selected_resins = st.multiselect("Chọn Resin", options=unique_resins, default=unique_resins)
with col_f2:
    selected_vendors = st.multiselect("Chọn Vendor", options=unique_vendors, default=unique_vendors)
with col_f3:
    selected_solvents = st.multiselect("Chọn Solvent Type", options=unique_solvents, default=unique_solvents)

filtered_df = group_a[
    (group_a['Resin'].isin(selected_resins)) &
    (group_a['Vendor'].isin(selected_vendors)) &
    (group_a['Solvent_Type'].isin(selected_solvents))
].copy()

# --- 4. Biểu đồ 1: Hồi quy so sánh nhiều nhóm ---
st.markdown("---")
st.subheader("📈 Comparative Regression: Solvent vs. Viscosity")

fig_regression = px.scatter(
    filtered_df,
    x='Solvent_Ratio_Percent',
    y='黏度(秒)',
    color='Solvent_Type',       # Màu theo dung môi
    symbol='Resin',             # Ký hiệu theo resin
    facet_col='Vendor',         # Phân cột theo Vendor
    trendline='ols',
    labels={'Solvent_Ratio_Percent': 'Solvent Added (%)', '黏度(秒)': 'Viscosity (s)'},
    title="Solvent Added vs. Viscosity Reduction (Multi-Filter Comparison)"
)
fig_regression.update_layout(plot_bgcolor='white', font=dict(size=12), margin=dict(l=40, r=40, t=60, b=40))
st.plotly_chart(fig_regression, use_container_width=True)

# --- 5. Biểu đồ 2: Ma trận SOP ---
st.markdown("---")
st.subheader("📚 SOP Matrix: Resin – Vendor – Solvent")

summary_matrix = group_a.groupby(['Resin', 'Vendor', 'Solvent_Type']).agg({
    '塗料批號': 'nunique',
    '塗料重量': 'sum',
    '添加重量': 'sum',
    '黏度(秒)': 'mean',
    '黏度(秒)_1': 'mean',
    'Solvent_Ratio_Percent': 'mean',
    'Sensitivity': 'mean'
}).rename(columns={
    '塗料批號': 'Batches',
    '塗料重量': 'Total Paint (kg)',
    '添加重量': 'Total Solvent (kg)',
    '黏度(秒)': 'Initial V (s)',
    '黏度(秒)_1': 'Final V (s)',
    'Solvent_Ratio_Percent': 'Avg Solvent %',
    'Sensitivity': 'Avg Sensitivity'
})

summary_matrix['Solvent Factor (kg/1s drop)'] = summary_matrix.apply(
    lambda row: (row['Total Paint (kg)'] * (1.0 / row['Avg Sensitivity']) / 100) if row['Avg Sensitivity'] > 0 else 0,
    axis=1
)

st.dataframe(summary_matrix.style.format({
    'Total Paint (kg)': '{:,.0f}',
    'Total Solvent (kg)': '{:,.0f}',
    'Initial V (s)': '{:.2f}',
    'Final V (s)': '{:.2f}',
    'Avg Solvent %': '{:.2f} %',
    'Avg Sensitivity': '{:.2f}',
    'Solvent Factor (kg/1s drop)': '{:.3f}'
}), use_container_width=True)

# --- 6. Biểu đồ 3: Xu hướng dung môi – resin – vendor ---
st.markdown("---")
st.subheader("📊 Trendline: Solvent vs. Viscosity by Resin – Vendor – Solvent")

fig_trend = px.scatter(
    filtered_df,
    x='Solvent_Ratio_Percent',
    y='黏度(秒)',
    color='Solvent_Type',
    symbol='Resin',
    facet_col='Vendor',
    trendline='ols',
    labels={'Solvent_Ratio_Percent': 'Solvent Added (%)', '黏度(秒)': 'Viscosity (s)'},
    title="Trendline Comparison (Resin – Vendor – Solvent)"
)
fig_trend.update_layout(plot_bgcolor='white', font=dict(size=12), margin=dict(l=40, r=40, t=60, b=40))
st.plotly_chart(fig_trend, use_container_width=True)

st.caption("""
💡 **Interpretation:**
- Biểu đồ 1: So sánh hồi quy nhiều nhóm → độ dốc trendline cho thấy hiệu quả dung môi.
- Biểu đồ 2: Ma trận SOP → bảng chuẩn để tính lượng dung môi cần thêm.
- Biểu đồ 3: Xu hướng trực quan → nhìn rõ dung môi nào giảm độ nhớt nhanh, dung môi nào kém hiệu quả.
""")
