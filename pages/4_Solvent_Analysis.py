import streamlit as st
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="Solvent Analysis", page_icon="💧", layout="wide")

st.title("💧 Solvent Usage & Ratio Analysis")
st.markdown("Evaluate solvent consumption patterns, popular solvent types, and average mixing ratios across different paint configurations.")

# 1. Global State Check
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please go to the Main App page and upload your data file first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()

# 2. Sidebar Filters
st.sidebar.header("🔍 Solvent Filters")
selected_vendor = st.sidebar.selectbox("Vendor", ["All"] + sorted(group_a['Vendor'].unique().tolist()))
selected_resin = st.sidebar.selectbox("Resin Type", ["All"] + sorted(group_a['Resin'].unique().tolist()))

# Apply Filters
filtered_df = group_a.copy()
if selected_vendor != "All":
    filtered_df = filtered_df[filtered_df['Vendor'] == selected_vendor]
if selected_resin != "All":
    filtered_df = filtered_df[filtered_df['Resin'] == selected_resin]

if filtered_df.empty:
    st.error("No valid data available for the selected filters.")
    st.stop()

# 3. Chart: Solvent Usage Ranking
st.markdown("### 1. Most Utilized Solvents")
col1, col2 = st.columns([2, 1])

with col1:
    # Count frequency of each solvent
    solvent_counts = filtered_df['Solvent_Type'].value_counts().reset_index()
    solvent_counts.columns = ['Solvent_Type', 'Usage_Count']
    
    fig_bar = px.bar(
        solvent_counts, 
        x='Solvent_Type', 
        y='Usage_Count',
        color='Solvent_Type',
        title="Frequency of Solvent Usage (Number of Mix Events)",
        labels={"Solvent_Type": "Solvent Type", "Usage_Count": "Mix Count"}
    )
    fig_bar.update_layout(showlegend=False)
    st.plotly_chart(fig_bar, use_container_width=True)

with col2:
    st.markdown("#### Distribution")
    fig_pie = px.pie(
        solvent_counts, 
        names='Solvent_Type', 
        values='Usage_Count',
        hole=0.4
    )
    fig_pie.update_layout(showlegend=False)
    st.plotly_chart(fig_pie, use_container_width=True)

st.divider()

# 4. Chart: Average Solvent Ratio by Paint Code
st.markdown("### 2. Average Solvent Ratio by Paint Configuration")
st.info("💡 Shows the average percentage of solvent added relative to the total paint weight.")

# Aggregate data by Vendor, Resin, and Feature
ratio_df = filtered_df.groupby(['Vendor', 'Resin', 'Feature'])['Solvent_Ratio'].mean().reset_index()
ratio_df['Solvent_Ratio_Pct'] = ratio_df['Solvent_Ratio'] * 100
ratio_df['Paint_Config'] = ratio_df['Vendor'] + " | " + ratio_df['Resin'] + " | " + ratio_df['Feature']

# Sort to show top consumers
ratio_df = ratio_df.sort_values(by='Solvent_Ratio_Pct', ascending=False)

fig_ratio_bar = px.bar(
    ratio_df,
    x='Solvent_Ratio_Pct',
    y='Paint_Config',
    orientation='h',
    color='Resin',
    title="Average Solvent Consumption Ratio (%) by Paint Type",
    labels={"Solvent_Ratio_Pct": "Solvent Ratio (%)", "Paint_Config": "Paint Configuration"}
)
fig_ratio_bar.update_layout(yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_ratio_bar, use_container_width=True)
# --- 5. Chart: Vendor-Resin-Solvent Hierarchy (Mind Map / Sunburst View) ---
st.markdown("### 3. Hierarchical Solvent Usage (Mind Map View)")
st.info("🌳 Visualizes the relationship between Vendor, Resin, and Solvent Type along with viscosity sensitivity metrics.")

# Lấy dữ liệu đã qua bộ lọc ở sidebar
tree_data = filtered_df.copy()

# Đảm bảo các cột phân tầng tồn tại (tránh lỗi KeyError)
for col in ['Vendor', 'Resin', 'Solvent_Type']:
    if col not in tree_data.columns:
        tree_data[col] = 'Unknown'

# Tính toán các chỉ số độ nhạy (Sensitivity) giống trong ảnh
if all(col in tree_data.columns for col in ['添加重量', '塗料重量', '黏度(秒)', '黏度(秒)_1']):
    # Mức giảm độ nhớt (Delta Viscosity)
    tree_data['Delta_V'] = tree_data['黏度(秒)'] - tree_data['黏度(秒)_1']
    
    # Tính % dung môi đã thêm
    tree_data['Solvent_Ratio_Percent'] = (tree_data['添加重量'] / tree_data['塗料重量']) * 100
    
    # Tránh lỗi chia cho 0
    safe_delta_v = tree_data['Delta_V'].replace(0, 1)
    
    # Tính: Số kg dung môi làm giảm 1 giây (kg/s)
    tree_data['Kg_per_1s'] = tree_data['添加重量'] / safe_delta_v
    
    # Tính: % dung môi làm giảm 1 giây (%/s)
    tree_data['Pct_per_1s'] = tree_data['Solvent_Ratio_Percent'] / safe_delta_v
else:
    tree_data['Kg_per_1s'] = 0
    tree_data['Pct_per_1s'] = 0
    tree_data['塗料重量'] = 0

# Gom nhóm dữ liệu theo cấu trúc: Vendor -> Resin -> Solvent
tree_summary = tree_data.groupby(['Vendor', 'Resin', 'Solvent_Type']).agg(
    Total_Paint=('塗料重量', 'sum'),
    Avg_Kg_per_1s=('Kg_per_1s', 'mean'),
    Avg_Pct_per_1s=('Pct_per_1s', 'mean')
).reset_index()

# Lọc bỏ các giá trị âm hoặc lỗi để biểu đồ hiển thị đúng
tree_summary = tree_summary[tree_summary['Total_Paint'] > 0]

if not tree_summary.empty:
    # Vẽ biểu đồ Sunburst
    fig_mindmap = px.sunburst(
        tree_summary,
        path=['Vendor', 'Resin', 'Solvent_Type'],
        values='Total_Paint', # Độ lớn của khối dựa trên tổng lượng sơn
        color='Avg_Pct_per_1s', # Màu sắc cảnh báo dựa trên độ nhạy (%)
        color_continuous_scale='Blues', # Dùng tone xanh giống ảnh
        title="Vendor - Resin - Solvent Hierarchy"
    )
    
    # Tùy chỉnh thông tin khi trỏ chuột (Hover) giống các block trong ảnh
    fig_mindmap.update_traces(
        customdata=tree_summary[['Avg_Kg_per_1s', 'Avg_Pct_per_1s']],
        hovertemplate='<b>%{label}</b><br>' +
                      'Total Paint: %{value:,.0f} kg<br>' +
                      'Solvent Added: %{customdata[0]:,.1f} kg per 1 s<br>' +
                      'Sensitivity: <b>%{customdata[1]:,.2f}% per 1 s</b><extra></extra>'
    )
    
    fig_mindmap.update_layout(
        height=600,
        margin=dict(t=40, l=0, r=0, b=0),
        coloraxis_colorbar=dict(title="% Solvent<br>per 1 s")
    )
    
    st.plotly_chart(fig_mindmap, use_container_width=True)
else:
    st.warning("⚠️ Không có đủ dữ liệu hợp lệ (trọng lượng sơn > 0) để vẽ biểu đồ phân tầng.")
