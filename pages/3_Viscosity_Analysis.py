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
st.subheader("📚 SOP Matrix: Resin – Vendor – Solvent (Saturation Aware)")

# Cập nhật phương pháp agg để lấy thêm min/max cảnh báo bão hòa
agg_funcs = {}
available_cols = group_a.columns

if '塗料批號' in available_cols: agg_funcs['Batches'] = ('塗料批號', 'nunique')
if '塗料重量' in available_cols: agg_funcs['Total Paint (kg)'] = ('塗料重量', 'sum')
if '添加重量' in available_cols: agg_funcs['Total Solvent (kg)'] = ('添加重量', 'sum')
if '黏度(秒)' in available_cols: agg_funcs['Avg Initial V (s)'] = ('黏度(秒)', 'mean')
if '黏度(秒)_1' in available_cols: 
    agg_funcs['Avg Final V (s)'] = ('黏度(秒)_1', 'mean')
    # Thêm đáy bão hòa độ nhớt (thấp nhất từng đạt)
    agg_funcs['Viscosity Floor (s) ⚠️'] = ('黏度(秒)_1', 'min') 
if 'Solvent_Ratio_Percent' in available_cols: 
    agg_funcs['Avg Solvent %'] = ('Solvent_Ratio_Percent', 'mean')
    # Thêm điểm bão hòa dung môi (cao nhất từng châm)
    agg_funcs['Max Solvent Limit % ⚠️'] = ('Solvent_Ratio_Percent', 'max')
if 'Sensitivity' in available_cols: 
    agg_funcs['Avg Sensitivity'] = ('Sensitivity', 'mean')

# Tạo dataframe phẳng (flat dataframe)
summary_matrix = group_a.groupby(['Resin','Vendor','Solvent_Type']).agg(**agg_funcs).reset_index()

# Tính toán định mức SOP
if 'Avg Sensitivity' in summary_matrix.columns:
    summary_matrix['Solvent Factor (kg/1s drop)'] = summary_matrix.apply(
        lambda row: (row['Total Paint (kg)'] * (1.0 / row['Avg Sensitivity']) / 100)
        if row['Avg Sensitivity'] > 0 else 0,
        axis=1
    )

# Format lại giao diện hiển thị (Đã bỏ background_gradient để không cần matplotlib)
st.dataframe(
    summary_matrix.style.format({
        'Total Paint (kg)': '{:,.0f}',
        'Total Solvent (kg)': '{:,.0f}',
        'Avg Initial V (s)': '{:.1f}',
        'Avg Final V (s)': '{:.1f}',
        'Viscosity Floor (s) ⚠️': '{:.1f}',
        'Avg Solvent %': '{:.2f}%',
        'Max Solvent Limit % ⚠️': '{:.2f}%',
        'Avg Sensitivity': '{:.3f}',
        'Solvent Factor (kg/1s drop)': '{:.3f}'
    }),
    use_container_width=True
)

st.info("⚠️ **Lưu ý SOP:** `Viscosity Floor` là ngưỡng độ nhớt bão hòa (không thể giảm thêm). Không khuyến nghị thêm dung môi vượt quá `Max Solvent Limit %` để tránh phá vỡ cấu trúc sơn.")

# --- 6. Biểu đồ 3: Line chart trung bình Initial vs Final Viscosity ---
st.markdown("---")
st.subheader("📊 Line Chart: Average Initial vs Final Viscosity vs Solvent Ratio")

# Gom nhóm để tránh nhiều đường chồng lên nhau
line_summary = filtered_df.groupby(['Resin','Vendor','Solvent_Type']).agg({
    'Solvent_Ratio_Percent':'mean',
    '黏度(秒)':'mean',
    '黏度(秒)_1':'mean'
}).reset_index()

fig_line = px.line(
    line_summary,
    x='Solvent_Ratio_Percent',
    y=['黏度(秒)', '黏度(秒)_1'],
    color='Vendor',
    facet_col='Resin',
    labels={'value':'Viscosity (s)', 'variable':'Stage'},
    title="Average Initial vs Final Viscosity by Solvent Ratio"
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
- Biểu đồ 3: Line chart trung bình → hiển thị rõ xu hướng độ nhớt ban đầu và sau khi thêm dung môi theo % dung môi, gọn gàng hơn.
""")
