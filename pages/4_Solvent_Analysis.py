import streamlit as st
import plotly.express as px
import pandas as pd
import graphviz


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
# --- 5. Chart: Vendor-Resin-Solvent Hierarchy (Mind Map View) ---
st.markdown("### 3. Hierarchical Solvent Usage (Mind Map View)")
st.info("🌳 Nhánh sơ đồ thể hiện luồng tiêu thụ từ Nhà cung cấp -> Loại Nhựa (Resin) -> Dung môi.")

# Lấy dữ liệu và tính toán chỉ số (Giữ nguyên phần tính toán cũ của bạn)
tree_data = filtered_df.copy()
for col in ['Vendor', 'Resin', 'Solvent_Type']:
    if col not in tree_data.columns:
        tree_data[col] = 'Unknown'

if all(col in tree_data.columns for col in ['添加重量', '塗料重量', '黏度(秒)', '黏度(秒)_1']):
    tree_data['Delta_V'] = tree_data['黏度(秒)'] - tree_data['黏度(秒)_1']
    tree_data['Solvent_Ratio_Percent'] = (tree_data['添加重量'] / tree_data['塗料重量']) * 100
    safe_delta_v = tree_data['Delta_V'].replace(0, 1)
    tree_data['Kg_per_1s'] = tree_data['添加重量'] / safe_delta_v
    tree_data['Pct_per_1s'] = tree_data['Solvent_Ratio_Percent'] / safe_delta_v
else:
    tree_data['Kg_per_1s'] = 0
    tree_data['Pct_per_1s'] = 0
    tree_data['塗料重量'] = 0

tree_summary = tree_data.groupby(['Vendor', 'Resin', 'Solvent_Type']).agg(
    Total_Paint=('塗料重量', 'sum'),
    Avg_Kg_per_1s=('Kg_per_1s', 'mean'),
    Avg_Pct_per_1s=('Pct_per_1s', 'mean')
).reset_index()

tree_summary = tree_summary[tree_summary['Total_Paint'] > 0]

if not tree_summary.empty:
    # Khởi tạo Graphviz
    graph = graphviz.Digraph(engine='dot')
    # Thiết lập hướng từ Trái sang Phải (Left to Right)
    graph.attr(rankdir='LR', size='10,10')
    graph.attr('node', shape='box', style='rounded,filled', fontname='Arial')

    # 1. Tạo Node Trung tâm (Vendor)
    vendor_name = tree_summary['Vendor'].iloc[0]
    total_vendor_paint = tree_summary['Total_Paint'].sum()
    graph.node('root', 
               f"<<B>{vendor_name}</B><BR/>Total Paint: {total_vendor_paint:,.0f} kg>", 
               fillcolor='#1B3C73', fontcolor='white') # Màu xanh đậm

    # Lấy danh sách Resin
    resins = tree_summary['Resin'].unique()
    
    for resin in resins:
        # 2. Tạo các Node Resin (Nhánh cấp 1)
        resin_data = tree_summary[tree_summary['Resin'] == resin]
        total_resin_paint = resin_data['Total_Paint'].sum()
        
        resin_id = f"resin_{resin}"
        graph.node(resin_id, 
                   f"<<B>{resin}</B><BR/>Paint: {total_resin_paint:,.0f} kg>", 
                   fillcolor='#9EC8B9', fontcolor='black') # Màu xanh nhạt
        
        # Nối Vendor -> Resin
        graph.edge('root', resin_id)

        # 3. Tạo các Node Dung môi (Nhánh cấp 2 - giống các block thông số của bạn)
        for _, row in resin_data.iterrows():
            solvent = row['Solvent_Type']
            solvent_id = f"sol_{resin}_{solvent}"
            
            # Khối text chi tiết thông số
            label_html = (
                f"<<B>{solvent}</B><BR/>"
                f"<FONT COLOR='#D9534F'><B>{row['Avg_Pct_per_1s']:.1f}%</B> Solvent per 1 s</FONT><BR/>"
                f"<FONT COLOR='#f0ad4e'>{row['Avg_Kg_per_1s']:.1f} kg Solvent per 1 s</FONT>>"
            )
            
            graph.node(solvent_id, label_html, fillcolor='#F2F2F2', fontcolor='black', color='#CCCCCC')
            
            # Nối Resin -> Solvent
            graph.edge(resin_id, solvent_id)

    # Hiển thị biểu đồ rẽ nhánh lên Streamlit
    st.graphviz_chart(graph, use_container_width=True)

else:
    st.warning("⚠️ Không có đủ dữ liệu hợp lệ để vẽ biểu đồ.")
