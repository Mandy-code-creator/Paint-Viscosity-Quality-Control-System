import streamlit as st
import pandas as pd
import graphviz
import io
from docx import Document
from docx.shared import Inches

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

for col in ['Vendor', 'Resin', 'Solvent_Type']:
    if col not in group_a.columns:
        group_a[col] = 'Unknown'

vendor_list = sorted(group_a['Vendor'].dropna().unique().tolist())
selected_vendor = st.sidebar.selectbox("Select Vendor:", vendor_list)

filtered_df = group_a[group_a['Vendor'] == selected_vendor].copy()

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
    Avg_Pct_per_1s=('Pct_per_1s', 'mean'),
    Avg_Visc_Before=('黏度(秒)', 'mean'),
    Avg_Visc_After=('黏度(秒)_1', 'mean')
).reset_index()

tree_summary = tree_summary[tree_summary['Total_Paint'] > 0].sort_values(by='Total_Paint', ascending=False)

if tree_summary.empty:
    st.info("No valid paint consumption data available to render the hierarchy.")
    st.stop()

# --- 4. RENDER GRAPHVIZ (LEFT-TO-RIGHT CLEAN LAYOUT) ---
graph = graphviz.Digraph(engine='dot')
# Thu gọn khoảng cách các nhánh (nodesep, ranksep) để sơ đồ khít hơn
graph.attr(rankdir='LR', splines='curved', nodesep='0.2', ranksep='1.0', bgcolor='transparent') 

# ĐÃ FIX: Thêm width='0', height='0' để XÓA BỎ kích thước tối thiểu mặc định, ép node bọc chặt lấy chữ
graph.attr('node', shape='none', margin='0', width='0', height='0', fontname='Arial')
graph.attr('edge', color='#A0A0A0', penwidth='1.5', arrowsize='0.8')

# --- 4.1 ROOT NODE (VENDOR) ---
total_vendor_paint = tree_summary['Total_Paint'].sum()
total_vendor_solv = tree_summary['Total_Solvent'].sum()
avg_delta_v = filtered_df['Delta_V'].mean() if not filtered_df.empty else 1
reduction_pct = ((total_vendor_solv / total_vendor_paint) * 100) / avg_delta_v if total_vendor_paint > 0 else 0

date_cols = [col for col in filtered_df.columns if 'date' in col.lower() or '日期' in col.lower() or 'time' in col.lower()]
if date_cols:
    date_col = date_cols[0]
    try:
        min_date = pd.to_datetime(filtered_df[date_col]).min().strftime('%b %Y')
        max_date = pd.to_datetime(filtered_df[date_col]).max().strftime('%b %Y')
        date_range_str = f"{min_date} - {max_date}" if min_date != max_date else min_date
    except:
        date_range_str = "All Available Data"
else:
    date_range_str = "All Available Data"

# ĐÃ FIX: Rút gọn text (Visc Reduction thay vì Avg Viscosity Reduction) để khung không bị giãn ngang
center_html = f'''<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4">
    <TR><TD BGCOLOR="#00BFFF" STYLE="ROUNDED" ALIGN="CENTER">
        <FONT COLOR="white" POINT-SIZE="18"><B>VENDOR: {selected_vendor}</B></FONT>
    </TD></TR>
    <TR><TD BGCOLOR="#F8F9FA" STYLE="ROUNDED" ALIGN="CENTER">
        <FONT POINT-SIZE="12" COLOR="#333333">
        Period: <B>{date_range_str}</B><BR/>
        <B>{total_vendor_paint:,.0f} kg</B> Paint Used<BR/>
        Visc Reduction: <B>{avg_delta_v:.1f} s</B><BR/>
        <B>{total_vendor_solv:,.0f} kg</B> Solvent Added<BR/>
        </FONT>
        <FONT COLOR="#D9534F" POINT-SIZE="13"><B>{reduction_pct:.2f}% / 1s Red.</B></FONT>
    </TD></TR>
</TABLE>'''

graph.node('Root', f'<{center_html}>')

# --- 4.2 CHILD NODES (RESIN & SOLVENT FLOW) ---
unique_resins = tree_summary['Resin'].unique()

for resin in unique_resins:
    resin_id = f"resin_{resin}"
    resin_data = tree_summary[tree_summary['Resin'] == resin]
    
    resin_paint_sum = resin_data['Total_Paint'].sum()
    resin_solvent_sum = resin_data['Total_Solvent'].sum()
    
    # ĐÃ FIX: CELLPADDING="2" (Rất nhỏ để ôm sát)
    resin_html = f'''<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="2">
        <TR><TD BGCOLOR="#E6F2FF" STYLE="ROUNDED" BORDER="1" COLOR="#00BFFF" ALIGN="CENTER">
            <FONT COLOR="#005A9E" POINT-SIZE="14"><B>RESIN: {resin}</B></FONT><BR/>
            <FONT COLOR="#555555" POINT-SIZE="11">{resin_paint_sum:,.0f} kg Paint</FONT><BR/>
            <FONT COLOR="#D9534F" POINT-SIZE="11">{resin_solvent_sum:,.0f} kg Solvent</FONT>
        </TD></TR>
    </TABLE>'''
    graph.node(resin_id, f'<{resin_html}>')
    graph.edge('Root', resin_id)
    
    for idx, row in resin_data.iterrows():
        solvent = row['Solvent_Type']
        leaf_id = f"leaf_{resin}_{solvent}_{idx}"
        
        # ĐÃ FIX: CELLPADDING="2" (Rất nhỏ để ôm sát)
        leaf_html = f'''<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="2">
            <TR><TD ALIGN="CENTER" BGCOLOR="white" STYLE="ROUNDED" BORDER="1" COLOR="#CCCCCC">
                <B><FONT COLOR="#333333">SOLVENT: {solvent}</FONT></B><BR/>
                <FONT COLOR="#888888" POINT-SIZE="10">Visc Before: {row['Avg_Visc_Before']:.1f} s</FONT><BR/>
                <FONT COLOR="#888888" POINT-SIZE="10">Visc After: {row['Avg_Visc_After']:.1f} s</FONT><BR/>
                <FONT COLOR="#00BFFF">{row['Avg_Kg_per_1s']:,.2f} kg / 1s</FONT><BR/>
                <FONT COLOR="#D9534F">{row['Avg_Pct_per_1s']:.2f}% / 1s</FONT>
            </TD></TR>
        </TABLE>'''
        
        graph.node(leaf_id, f'<{leaf_html}>')
        graph.edge(resin_id, leaf_id)

# --- 5. RENDER & EXPORT ---
# ĐÃ FIX: use_container_width=False -> Ngăn chặn Streamlit kéo giãn bức ảnh ra toàn màn hình
st.graphviz_chart(graph, use_container_width=False)

try:
    graph.attr(dpi='300') 
    
    png_data = graph.pipe(format='png')
    if not png_data:
        st.error("Lỗi: Không tạo được dữ liệu ảnh từ Graphviz.")
        st.stop()
        
    image_stream = io.BytesIO(png_data)
    
    doc = Document()
    doc.add_heading(f'Solvent Consumption & Viscosity Control: {selected_vendor}', 0)
    doc.add_paragraph('Report Level: Coil-Level Data')
    doc.add_paragraph('Quality Filter: Grade A-B and above')
    doc.add_picture(image_stream, width=Inches(6.5))
    
    doc_io = io.BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)
    
    col_empty, col_btn = st.columns([4, 1])
    with col_btn:
        st.download_button(
            label="📄 Download Word Report",
            data=doc_io,
            file_name=f"Solvent_Report_{selected_vendor}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

except Exception as e:
    st.error(f"Đã xảy ra lỗi khi tạo file Word: {e}")
    st.exception(e)
