import streamlit as st
import pandas as pd
import graphviz

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Solvent Hierarchy", page_icon="🌳", layout="wide")

st.title("🌳 Solvent Consumption Hierarchy")
st.markdown("Coil-level analysis of solvent utilization mapping from Vendor to specific Resin and Solvent types.")

# --- 1. DATA LOADING & SAFE CHECK ---
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please upload your dataset on the Main App page.")
    st.stop()

group_a = st.session_state.get('group_a_data', pd.DataFrame()).copy()

if group_a.empty:
    st.error("❌ The dataset is empty. Please check the uploaded file.")
    st.stop()

# --- 2. SIDEBAR FILTERS ---
st.sidebar.header("🔍 Hierarchy Filters")

# Ensure columns exist safely
for col in ['Vendor', 'Resin', 'Solvent_Type']:
    if col not in group_a.columns:
        group_a[col] = 'Unknown'

# Data Filtering (Assuming Coil level calculation based on system defaults)
vendor_list = sorted(group_a['Vendor'].dropna().unique().tolist())
selected_vendor = st.sidebar.selectbox("🏭 Select Vendor:", vendor_list)

filtered_df = group_a[group_a['Vendor'] == selected_vendor].copy()

# Optional: Filter for Grade A-B if the column exists in your dataset
if 'Grade' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['Grade'].isin(['A', 'B', 'A-B'])]

if filtered_df.empty:
    st.warning(f"⚠️ No valid coil data available for {selected_vendor}.")
    st.stop()

# --- 3. METRIC CALCULATIONS ---
required_cols = ['塗料重量', '添加重量', '黏度(秒)', '黏度(秒)_1']
if not all(col in filtered_df.columns for col in required_cols):
    st.error(f"❌ Missing required columns for calculation: {', '.join(required_cols)}")
    st.stop()

filtered_df['Delta_V'] = filtered_df['黏度(秒)'] - filtered_df['黏度(秒)_1']
filtered_df['Delta_V'] = filtered_df['Delta_V'].replace(0, 1) 

filtered_df['Solvent_Ratio_Percent'] = (filtered_df['添加重量'] / filtered_df['塗料重量'].replace(0, 1)) * 100
filtered_df['Kg_per_1s'] = filtered_df['添加重量'] / filtered_df['Delta_V']
filtered_df['Pct_per_1s'] = filtered_df['Solvent_Ratio_Percent'] / filtered_df['Delta_V']

tree_summary = filtered_df.groupby(['Resin', 'Solvent_Type']).agg(
    Total_Paint=('塗料重量', 'sum'),
    Total_Solvent=('添加重量', 'sum'),
    Avg_Kg_per_1s=('Kg_per_1s', 'mean'),
    Avg_Pct_per_1s=('Pct_per_1s', 'mean')
).reset_index()

tree_summary = tree_summary[tree_summary['Total_Paint'] > 0].sort_values(by='Total_Paint', ascending=False)

if tree_summary.empty:
    st.info("No valid paint consumption data available to render the hierarchy.")
    st.stop()

# --- 4. RENDER GRAPHVIZ (LEFT-TO-RIGHT CLEAN LAYOUT) ---
graph = graphviz.Digraph(engine='dot')
# Using curved splines, optimized spacing, and transparent background
graph.attr(rankdir='LR', splines='curved', nodesep='0.4', ranksep='1.5', bgcolor='transparent') 
graph.attr('node', shape='none', margin='0', fontname='Arial')
graph.attr('edge', color='#A0A0A0', penwidth='1.5', arrowsize='0.8')

# --- 4.1 ROOT NODE (VENDOR) ---
total_vendor_paint = tree_summary['Total_Paint'].sum()
total_vendor_solv = tree_summary['Total_Solvent'].sum()
avg_delta_v = filtered_df['Delta_V'].mean() if not filtered_df.empty else 1
reduction_pct = ((total_vendor_solv / total_vendor_paint) * 100) / avg_delta_v if total_vendor_paint > 0 else 0

# Tự động tìm cột thời gian để trích xuất Data Period
date_cols = [col for col in filtered_df.columns if 'date' in col.lower() or '日期' in col.lower() or 'time' in col.lower()]
if date_cols:
    date_col = date_cols[0]
    try:
        # Định dạng hiển thị thời gian (ví dụ: Jan 2026 - Apr 2026)
        min_date = pd.to_datetime(filtered_df[date_col]).min().strftime('%b %Y')
        max_date = pd.to_datetime(filtered_df[date_col]).max().strftime('%b %Y')
        date_range_str = f"{min_date} - {max_date}" if min_date != max_date else min_date
    except:
        date_range_str = "All Available Data"
else:
    date_range_str = "All Available Data"

# Cấu trúc Node trung tâm với màu Deep Sky Blue và bổ sung Data Period
center_html = f'''<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="12">
    <TR><TD BGCOLOR="#00BFFF" STYLE="ROUNDED">
        <FONT COLOR="white" POINT-SIZE="20"><B>🏭 {selected_vendor}</B></FONT>
    </TD></TR>
    <TR><TD BGCOLOR="#F8F9FA" STYLE="ROUNDED">
        <FONT POINT-SIZE="13" COLOR="#333333">
        Data Period: <B>{date_range_str}</B><BR/><BR/>
        <B>{total_vendor_paint:,.0f} kg</B> Paint Used<BR/>
        Avg Viscosity Reduction: <B>{avg_delta_v:.1f} s</B><BR/>
        <B>{total_vendor_solv:,.0f} kg</B> Solvent Added<BR/>
        </FONT>
        <FONT COLOR="#D9534F" POINT-SIZE="14"><B>{reduction_pct:.2f}% / 1s Reduction</B></FONT>
    </TD></TR>
</TABLE>'''

graph.node('Root', f'<{center_html}>')

# --- 4.2 CHILD NODES (RESIN & SOLVENT FLOW) ---
# Group by Resin first to create the middle layer
unique_resins = tree_summary['Resin'].unique()

for resin in unique_resins:
    resin_id = f"resin_{resin}"
    resin_data = tree_summary[tree_summary['Resin'] == resin]
    resin_paint_sum = resin_data['Total_Paint'].sum()
    
    # Resin Node (Middle Layer)
    resin_html = f'''<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="8">
        <TR><TD BGCOLOR="#E6F2FF" STYLE="ROUNDED" BORDER="1" COLOR="#00BFFF">
            <FONT COLOR="#005A9E" POINT-SIZE="15"><B>🧪 {resin}</B></FONT><BR/>
            <FONT COLOR="#555555" POINT-SIZE="11">{resin_paint_sum:,.0f} kg Paint</FONT>
        </TD></TR>
    </TABLE>'''
    graph.node(resin_id, f'<{resin_html}>')
    graph.edge('Root', resin_id)
    
    # Solvent Nodes (Leaf Layer)
    for idx, row in resin_data.iterrows():
        solvent = row['Solvent_Type']
        leaf_id = f"leaf_{resin}_{solvent}_{idx}"
        
        leaf_html = f'''<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="6">
            <TR><TD ALIGN="LEFT" BGCOLOR="white" STYLE="ROUNDED" BORDER="1" COLOR="#CCCCCC">
                <B><FONT COLOR="#333333">💧 {solvent}</FONT></B><BR/>
                <FONT COLOR="#00BFFF">{row['Avg_Kg_per_1s']:,.2f} kg / 1s</FONT><BR/>
                <FONT COLOR="#D9534F">{row['Avg_Pct_per_1s']:.2f}% / 1s</FONT>
            </TD></TR>
        </TABLE>'''
        
        graph.node(leaf_id, f'<{leaf_html}>')
        graph.edge(resin_id, leaf_id)

# --- 5. RENDER ---
st.graphviz_chart(graph, use_container_width=True)
