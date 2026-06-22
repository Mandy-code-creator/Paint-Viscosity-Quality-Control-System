import streamlit as st
import plotly.express as px
import pandas as pd

# --- 1. Cấu hình trang ---
st.set_page_config(page_title="Viscosity Analysis Report", page_icon="🔬", layout="wide")
st.title("🔬 Viscosity Analysis Report")
st.markdown("Detailed breakdown of solvent sensitivity per resin, vendor, and solvent type.")

# --- 2. Kiểm tra dữ liệu ---
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please upload your data file first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()

# Ép kiểu dữ liệu để tránh lỗi
group_a['Solvent_Type'] = group_a['Solvent_Type'].astype(str)

# --- 3. Bộ lọc đa chiều ---
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

# --- 4. Lọc dữ liệu ---
filtered_df = group_a[
    (group_a['Resin'].isin(selected_resins)) &
    (group_a['Vendor'].isin(selected_vendors)) &
    (group_a['Solvent_Type'].isin(selected_solvents))
].copy()

# Tính % dung môi thêm
filtered_df['Solvent_Ratio_Percent'] = (filtered_df['添加重量'] / filtered_df['塗料重量']) * 100

# --- 5. Biểu đồ hồi quy ---
st.markdown("---")
st.subheader("📈 Comparative Regression: Solvent vs. Viscosity")

fig_regression = px.scatter(
    filtered_df,
    x='Solvent_Ratio_Percent',
    y='黏度(秒)',
    color='Resin',
    symbol='Solvent_Type',
    facet_col='Vendor',
    trendline='ols',
    labels={'Solvent_Ratio_Percent': 'Solvent Added (%)', '黏度(秒)': 'Viscosity (s)'},
    title="Solvent Added vs. Viscosity Reduction (Multi-Filter Comparison)"
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
- Mỗi màu = Resin khác nhau.
- Mỗi ký hiệu = loại dung môi.
- Mỗi cột (facet) = Vendor khác nhau.
Độ dốc trendline cho thấy mức độ nhạy dung môi:
* Steeper slope → dung môi hiệu quả, giảm độ nhớt nhanh.
* Flatter slope → dung môi kém hiệu quả, cần nhiều hơn để đạt mục tiêu.
""")
