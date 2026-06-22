import streamlit as st
import plotly.express as px
import pandas as pd

# --- 1. Cấu hình trang ---
st.set_page_config(page_title="Viscosity & SOP Report", page_icon="📊", layout="wide")
st.title("📊 Viscosity & SOP Analysis Dashboard")
st.markdown("Comparative regression, SOP matrix, and line chart visualization for Resin – Vendor – Solvent.")

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
    color='Solvent_Type',
    symbol='Resin',
    facet_col='Vendor',
    trendline='ols',
    labels={'Solvent_Ratio_Percent': 'Solvent Added (%)', '黏度(秒)': 'Viscosity (s)'},
    title="Solvent Added vs. Viscosity Reduction (Multi-Filter Comparison)"
)
fig_regression.update_layout(plot_bgcolor='white', font=dict(size=12), margin=dict(l=40, r=40, t=60, b=40))
st.plotly_chart(fig_regression, use_container_width=True)

# --- 5. Biểu đồ 2: Ma trận SOP ---
st.markdown("---")
st.subheader("📚 SOP Matrix: Resin – Vendor – Solvent")

available_cols = group_a.columns
agg_dict = {}
if '塗料批號' in available_cols: agg_dict['塗料批號'] = 'nunique'
if '塗料重量' in available_cols: agg_dict['塗料重量'] = 'sum'
if '添加重量' in available_cols: agg_dict['添加重量'] = 'sum'
if '黏度(秒)' in available_cols: agg_dict['黏度(秒)'] = 'mean'
if '黏度(秒)_1' in available_cols: agg_dict['黏度(秒)_1'] = 'mean'
if 'Solvent_Ratio_Percent' in available_cols: agg_dict['Solvent_Ratio_Percent'] = 'mean'
if 'Sensitivity' in available_cols: agg_dict['Sensitivity'] = 'mean'

summary_matrix = group_a.groupby(['Resin','Vendor','Solvent_Type']).agg(agg_dict)

summary_matrix = summary_matrix.rename(columns={
    '塗料批號': 'Batches',
    '塗料重量': 'Total Paint (kg)',
    '添加重量': 'Total Solvent (kg)',
    '黏度(秒)': 'Initial V (s)',
    '黏度(秒)_1': 'Final V (s)',
    'Solvent_Ratio_Percent': 'Avg Solvent %',
    'Sensitivity': 'Avg Sensitivity'
})

if 'Avg Sensitivity' in summary_matrix.columns:
    summary_matrix['Solvent Factor (kg/1s drop)'] = summary_matrix.apply(
        lambda row: (row['Total Paint (kg)'] * (1.0 / row['Avg Sensitivity']) / 100)
        if row['Avg Sensitivity'] > 0 else 0,
        axis=1
    )

st.dataframe(summary_matrix, use_container_width=True)

# --- 6. Biểu đồ 3: Line chart Initial vs Final Viscosity ---
st.markdown("---")
st.subheader("📊 Line Chart: Initial vs Final Viscosity vs Solvent Ratio")

line_df = filtered_df.copy()

fig_line = px.line(
    line_df,
    x='Solvent_Ratio_Percent',
    y=['黏度(秒)', '黏度(秒)_1'],   # Độ nhớt trước và sau
    labels={'value': 'Viscosity (s)', 'variable': 'Stage'},
    title="Initial vs Final Viscosity by Solvent Ratio"
)

fig_line.update_layout(
    plot_bgcolor='white',
    font=dict(size=12),
    margin=dict(l=40, r=40, t=60, b=40),
    legend_title_text='Stage'
)
fig_line.update_xaxes(showline=True, linecolor='black', linewidth=1)
fig_line.update_yaxes(showgrid=True, gridcolor='lightgray', linecolor='black', linewidth=1)

st.plotly_chart(fig_line, use_container_width=True)

st.caption("""
💡 **Interpretation:**
- Biểu đồ 1: Scatter + trendline → so sánh hiệu quả dung môi theo vendor.
- Biểu đồ 2: Ma trận SOP → bảng chuẩn để tính lượng dung môi cần thêm.
- Biểu đồ 3: Line chart → hiển thị trực tiếp độ nhớt ban đầu và sau khi thêm dung môi theo % dung môi.
""")
