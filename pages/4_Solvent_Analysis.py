import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px  # <-- Dòng này sẽ sửa lỗi 'px is not defined'
import graphviz              # <-- Dòng này để lát nữa vẽ sơ đồ Mind Map

# --- 1. Global State Check & MOCK DATA (Chế độ test) ---
# Nếu đang code và chưa có dữ liệu, tự động tạo dữ liệu giả để test UI
if not st.session_state.get('raw_data_loaded', False):
    st.info("🛠️ [Dev Mode] Đang sử dụng dữ liệu giả (Mock Data) để test giao diện...")
    
    # Tạo dữ liệu giả với các cột cần thiết
    mock_data = pd.DataFrame({
        'Vendor': np.random.choice(['Yungchi', 'Nippon', 'Kansai'], 100),
        'Resin': np.random.choice(['PE', 'PU', 'PVDF', 'SMP', 'EPOXY'], 100),
        'Feature': np.random.choice(['Top', 'Primer', 'Back'], 100),
        'Solvent_Type': np.random.choice(['5203', 'Isophorone', '4160', 'BCS'], 100),
        '塗料重量': np.random.randint(200, 800, 100), # Trọng lượng sơn
        '添加重量': np.random.randint(10, 50, 100),   # Trọng lượng dung môi
        '黏度(秒)': np.random.randint(35, 50, 100),   # Độ nhớt ban đầu
        '黏度(秒)_1': np.random.randint(25, 30, 100), # Độ nhớt mục tiêu
    })
    
    # Tính toán các cột phụ trợ
    mock_data['Solvent_Ratio'] = mock_data['添加重量'] / mock_data['塗料重量']
    
    # Ép vào session_state
    st.session_state['group_a_data'] = mock_data
    st.session_state['raw_data_loaded'] = True

# Lấy dữ liệu ra để dùng
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
# ==================================================
# 5. Resin-Solvent Intelligence View
# ==================================================

from streamlit_agraph import agraph, Node, Edge, Config

st.markdown("### 3. Resin-Solvent Intelligence View")
st.info(
    "🎯 Relationship between Vendor → Resin → Solvent. "
    "Each resin node displays paint usage and solvent efficiency."
)

tree_data = filtered_df.copy()

required_cols = [
    'Vendor',
    'Resin',
    'Solvent_Type',
    '塗料重量',
    '添加重量',
    '黏度(秒)',
    '黏度(秒)_1'
]

if all(col in tree_data.columns for col in required_cols):

    tree_data['Delta_V'] = (
        tree_data['黏度(秒)']
        - tree_data['黏度(秒)_1']
    )

    tree_data = tree_data[
        tree_data['Delta_V'] > 0
    ]

    if tree_data.empty:
        st.warning("No valid viscosity reduction records.")
        st.stop()

    tree_data['Solvent_Ratio_Pct'] = (
        tree_data['添加重量']
        / tree_data['塗料重量']
    ) * 100

    tree_data['Pct_per_1s'] = (
        tree_data['Solvent_Ratio_Pct']
        / tree_data['Delta_V']
    )

    summary = (
        tree_data
        .groupby(
            ['Vendor', 'Resin', 'Solvent_Type']
        )
        .agg(
            Paint_Weight=('塗料重量', 'sum'),
            Solvent_Added=('添加重量', 'sum'),
            Avg_Pct_1s=('Pct_per_1s', 'mean'),
            Batch_Count=('Resin', 'count')
        )
        .reset_index()
    )

    if summary.empty:
        st.warning("No summarized data available.")
        st.stop()

    # ====================================
    # Vendor Node
    # ====================================

    vendor_name = summary['Vendor'].iloc[0]

    total_paint = (
        summary['Paint_Weight']
        .sum()
    )

    total_solvent = (
        summary['Solvent_Added']
        .sum()
    )

    nodes = []
    edges = []

    center_label = (
        f"{vendor_name}\n\n"
        f"{total_paint:,.0f} kg Paint\n"
        f"{total_solvent:,.0f} kg Solvent"
    )

    nodes.append(
        Node(
            id="CENTER",
            label=center_label,
            size=50,
            color="#0B3B75",
            shape="dot"
        )
    )

    # ====================================
    # Top Resin
    # ====================================

    resin_summary = (
        summary.groupby('Resin')
        .agg(
            Paint_Weight=('Paint_Weight', 'sum')
        )
        .sort_values(
            'Paint_Weight',
            ascending=False
        )
        .head(8)
    )

    resin_list = resin_summary.index.tolist()

    for resin in resin_list:

        resin_data = summary[
            summary['Resin'] == resin
        ]

        paint_weight = (
            resin_data['Paint_Weight']
            .sum()
        )

        solvent_added = (
            resin_data['Solvent_Added']
            .sum()
        )

        avg_pct = (
            resin_data['Avg_Pct_1s']
            .mean()
        )

        top_solvent = (
            resin_data
            .sort_values(
                'Paint_Weight',
                ascending=False
            )
            .iloc[0]['Solvent_Type']
        )

        resin_label = (
            f"{resin}\n\n"
            f"{paint_weight:,.0f} kg Paint\n"
            f"{top_solvent}\n"
            f"{solvent_added:,.0f} kg Solvent\n"
            f"{avg_pct:.2f}% / 1s"
        )

        nodes.append(
            Node(
                id=resin,
                label=resin_label,
                size=30,
                shape="ellipse",
                color="#D9F2FF"
            )
        )

        edges.append(
            Edge(
                source="CENTER",
                target=resin,
                width=4
            )
        )

    # ====================================
    # Graph Config
    # ====================================

    config = Config(
        width="100%",
        height=700,
        directed=False,
        physics=True,
        hierarchical=False,
        nodeHighlightBehavior=True,
        highlightColor="#F7A7A6",
        collapsible=False
    )

    agraph(
        nodes=nodes,
        edges=edges,
        config=config
    )

else:
    st.warning(
        "Missing required columns for Resin-Solvent view."
    )
