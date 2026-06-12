import streamlit as st
import pandas as pd
import numpy as np
import graphviz

st.set_page_config(page_title="Sơ đồ Tư Duy Phân Tích", layout="wide")

st.title("🌳 Sơ đồ Phân Bổ Dung Môi (Mind Map)")
st.markdown("Phân tích cấu trúc tiêu thụ dung môi theo Nhà cung cấp, Loại nhựa và Loại dung môi.")

# --- 1. KIỂM TRA DỮ LIỆU HOẶC TẠO DỮ LIỆU MOCK ---
if not st.session_state.get('raw_data_loaded', False):
    st.info("🛠️ [Dev Mode] Đang sử dụng dữ liệu giả (Mock Data) để test giao diện...")
    
    # Tạo dữ liệu giả phong phú để test bộ lọc
    mock_data = pd.DataFrame({
        'Vendor': np.random.choice(['Yungchi', 'Nippon', 'Kansai', 'Akzo Nobel'], 300),
        'Resin': np.random.choice(['PE', 'PU', 'PVDF', 'SMP', 'EPOXY', 'ACRYLIC'], 300),
        'Solvent_Type': np.random.choice(['5203', 'Isophorone', '4160', 'BCS', 'CB5203'], 300),
        '塗料重量': np.random.randint(100, 800, 300), # kg Sơn
        '添加重量': np.random.randint(5, 50, 300),   # kg Dung môi
        '黏度(秒)': np.random.randint(35, 50, 300),
        '黏度(秒)_1': np.random.randint(25, 30, 300),
    })
    st.session_state['group_a_data'] = mock_data
    st.session_state['raw_data_loaded'] = True

group_a = st.session_state['group_a_data'].copy()

# --- 2. BỘ LỌC (SIDEBAR FILTERS) ---
st.sidebar.header("🔍 Bộ Lọc Dữ Liệu")

# Tạo danh sách bộ lọc
vendor_list = sorted(group_a['Vendor'].unique().tolist())
resin_list = ['Tất cả'] + sorted(group_a['Resin'].unique().tolist())
solvent_list = ['Tất cả'] + sorted(group_a['Solvent_Type'].unique().tolist())

# Chọn nhà cung cấp (Bắt buộc chọn 1 để làm Node trung tâm)
selected_vendor = st.sidebar.selectbox("🏭 Nhà cung cấp (Vendor):", vendor_list, 
                                       index=vendor_list.index('Yungchi') if 'Yungchi' in vendor_list else 0)

# Chọn Loại Nhựa & Dung môi
selected_resin = st.sidebar.selectbox("🧪 Loại nhựa (Resin):", resin_list)
selected_solvent = st.sidebar.selectbox("💧 Loại dung môi (Solvent):", solvent_list)

# Áp dụng bộ lọc
filtered_df = group_a[group_a['Vendor'] == selected_vendor].copy()

if selected_resin != 'Tất cả':
    filtered_df = filtered_df[filtered_df['Resin'] == selected_resin]
if selected_solvent != 'Tất cả':
    filtered_df = filtered_df[filtered_df['Solvent_Type'] == selected_solvent]

if filtered_df.empty:
    st.warning("⚠️ Không có dữ liệu phù hợp với bộ lọc hiện tại.")
    st.stop()

# --- 3. TÍNH TOÁN CÁC CHỈ SỐ ---
filtered_df['Delta_V'] = filtered_df['黏度(秒)'] - filtered_df['黏度(秒)_1']
# Đảm bảo Delta_V không bằng 0 để tránh lỗi chia
filtered_df['Delta_V'] = filtered_df['Delta_V'].replace(0, 1)

filtered_df['Solvent_Ratio_Percent'] = (filtered_df['添加重量'] / filtered_df['塗料重量']) * 100
filtered_df['Kg_per_1s'] = filtered_df['添加重量'] / filtered_df['Delta_V']
filtered_df['Pct_per_1s'] = filtered_df['Solvent_Ratio_Percent'] / filtered_df['Delta_V']

# Gom nhóm dữ liệu theo Resin và Solvent
tree_summary = filtered_df.groupby(['Resin', 'Solvent_Type']).agg(
    Total_Paint=('塗料重量', 'sum'),
    Total_Solvent=('添加重量', 'sum'),
    Avg_Kg_per_1s=('Kg_per_1s', 'mean'),
    Avg_Pct_per_1s=('Pct_per_1s', 'mean')
).reset_index()

# --- 4. VẼ BIỂU ĐỒ GRAPHVIZ ---
graph = graphviz.Digraph(engine='dot')
# splines='curved' giúp các đường nối uốn lượn thay vì thẳng đơ
graph.attr(rankdir='LR', splines='curved', nodesep='0.6', ranksep='2.0') 
graph.attr('node', shape='plaintext', fontname='Arial')

# --- 4.1 TẠO NODE TRUNG TÂM ---
total_vendor_paint = tree_summary['Total_Paint'].sum()
total_vendor_solv = tree_summary['Total_Solvent'].sum()

# Tránh lỗi chia cho 0
avg_delta_v = filtered_df['Delta_V'].mean() if not filtered_df.empty else 1
reduction_pct = ((total_vendor_solv / total_vendor_paint) * 100) / avg_delta_v if total_vendor_paint > 0 else 0

center_html = f'''<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="10">
    <TR><TD BGCOLOR="#003366" STYLE="ROUNDED">
        <FONT COLOR="white" POINT-SIZE="22"><B>🏭 {selected_vendor}</B></FONT>
    </TD></TR>
    <TR><TD BGCOLOR="#F2F4F8" STYLE="ROUNDED">
        <FONT POINT-SIZE="14">
        <B>{total_vendor_paint:,.0f} kg Paint Used</B><BR/>
        Filtered Data<BR/><BR/>
        Avg Reduction: <B>{avg_delta_v:.1f} s</B><BR/><BR/>
        <B>{total_vendor_solv:,.0f} kg Solvent Added</B><BR/>
        </FONT>
        <FONT COLOR="#D9534F"><B>{reduction_pct:.1f}% Solvent per 1 s Reduction</B></FONT>
    </TD></TR>
</TABLE>'''

graph.node('Center', f'<{center_html}>')

# --- 4.2 LOGIC CHIA NHÁNH TRÁI/PHẢI TỰ ĐỘNG ---
unique_resins = tree_summary['Resin'].unique().tolist()
midpoint = (len(unique_resins) + 1) // 2 
left_resins = unique_resins[:midpoint] # Nửa đầu sang trái
right_resins = unique_resins[midpoint:] # Nửa sau sang phải

# --- 4.3 TẠO CÁC NODE NHÁNH VÀ NỐI ĐƯỜNG ---
for idx, row in tree_summary.iterrows():
    resin = row['Resin']
    solvent = row['Solvent_Type']
    node_id = f"node_{idx}"
    
    is_left = resin in left_resins
    
    # Phối màu Trái (Xanh) - Phải (Cam)
    bg_color = "#D9E6F2" if is_left else "#FDECDA"
    text_color = "#104E8B" if is_left else "#CC5500"
    drop_color = "#3399FF" if is_left else "#FF8800"
    edge_color = "#77AADD" if is_left else "#FFBB77"
    
    node_html = f'''<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="5">
        <TR><TD BGCOLOR="{bg_color}" STYLE="ROUNDED" BORDER="1" COLOR="{text_color}">
            <FONT COLOR="{text_color}" POINT-SIZE="16"><B>🧪 {resin}</B></FONT>
        </TD></TR>
        <TR><TD ALIGN="LEFT" BGCOLOR="white">
            <B>⚖️ {row['Total_Paint']:,.0f} kg Paint, {solvent}</B><BR/>
            <FONT COLOR="{drop_color}">💧 {row['Avg_Kg_per_1s']:,.1f} kg Solvent per 1 s</FONT><BR/>
            <FONT COLOR="{text_color}">{row['Avg_Pct_per_1s']:.1f}% Solvent per 1 s</FONT>
        </TD></TR>
    </TABLE>'''
    
    graph.node(node_id, f'<{node_html}>')
    
    # Nối đường (Mũi tên ngược cho bên trái để giữ bố cục rẽ sang 2 bên)
    if is_left:
        graph.edge(node_id, 'Center', dir='back', color=edge_color, penwidth='2.5')
    else:
        graph.edge('Center', node_id, color=edge_color, penwidth='2.5')

# --- 5. HIỂN THỊ VÀ XUẤT FILE ---
st.graphviz_chart(graph, use_container_width=True)

# Lấy dữ liệu dạng hình ảnh (PNG) từ Graphviz để tải về
try:
    png_data = graph.pipe(format='png')
    col_empty, col_btn = st.columns([4, 1])
    with col_btn:
        st.download_button(
            label="⬇️ Tải biểu đồ (PNG)",
            data=png_data,
            file_name=f"mindmap_{selected_vendor}.png",
            mime="image/png"
        )
except Exception as e:
    st.caption("Cần cài đặt Graphviz trên hệ thống để sử dụng tính năng tải file PNG.")
