import streamlit as st
import pandas as pd
import graphviz

st.set_page_config(page_title="Sơ đồ Tư Duy Đối Xứng", layout="wide")

st.title("🌳 Sơ đồ Mind Map Đối Xứng (Graphviz)")
st.info("Sử dụng HTML Table trong Graphviz để tạo giao diện Infographic đối xứng.")

# --- 1. DỮ LIỆU MOCK CHUẨN (MẪU YUNGCHI) ---
data = pd.DataFrame({
    'Resin': ['PE', 'SMP_1', 'SMP_2', 'EPOXY', 'PU', 'PVDF'], # Thêm _1, _2 để phân biệt node
    'Resin_Label': ['PE', 'SMP', 'SMP', 'EPOXY', 'PU', 'PVDF'], # Tên hiển thị
    'Solvent_Type': ['5203', '5203', '5203', '5203', 'CB5203', 'Isophorone'],
    '塗料重量': [500, 400, 400, 500, 600, 300], 
    '添加重量': [17, 18, 18, 25, 12, 22],   
    'Side': ['Left', 'Left', 'Left', 'Right', 'Right', 'Right'] # Phân bổ Trái/Phải
})

# Tính toán
data['Delta_V'] = 5 # Mặc định giảm 5s theo mẫu
data['Solvent_Ratio_Percent'] = (data['添加重量'] / data['塗料重量']) * 100
data['Kg_per_1s'] = data['添加重量'] / data['Delta_V']
data['Pct_per_1s'] = data['Solvent_Ratio_Percent'] / data['Delta_V']

# --- 2. VẼ BIỂU ĐỒ GRAPHVIZ ĐỐI XỨNG ---
graph = graphviz.Digraph(engine='dot')
# rankdir='LR' (Left to Right), splines='true' để đường kẻ cong mềm mại
graph.attr(rankdir='LR', splines='true', nodesep='0.5', ranksep='1.5') 
graph.attr('node', shape='plaintext', fontname='Arial')

# --- TẠO NODE TRUNG TÂM (YUNGCHI) ---
total_paint = data['塗料重量'].sum()
total_solv = data['添加重量'].sum()
reduction_pct = ((total_solv / total_paint) * 100) / 5 

center_html = f'''<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="10">
    <TR><TD BGCOLOR="#003366" STYLE="ROUNDED">
        <FONT COLOR="white" POINT-SIZE="22"><B>🏭 Yungchi</B></FONT>
    </TD></TR>
    <TR><TD BGCOLOR="#F2F4F8" STYLE="ROUNDED">
        <FONT POINT-SIZE="14">
        <B>{total_paint:,.0f} kg Paint Used</B><BR/>
        Jan–Apr 2026<BR/><BR/>
        Initial Viscosity: <B>35 s</B><BR/>
        Target Viscosity: <B>30 s</B><BR/><BR/>
        <B>{total_solv:,.0f} kg Solvent Added</B><BR/>
        </FONT>
        <FONT COLOR="#D9534F"><B>{reduction_pct:.1f}% Solvent per 1 s Reduction</B></FONT>
    </TD></TR>
</TABLE>'''

graph.node('Center', f'<{center_html}>')

# --- TẠO CÁC NODE NHÁNH ---
for idx, row in data.iterrows():
    node_id = row['Resin']
    label = row['Resin_Label']
    is_left = row['Side'] == 'Left'
    
    # Phối màu Trái (Xanh) - Phải (Cam)
    bg_color = "#D9E6F2" if is_left else "#FDECDA"
    text_color = "#104E8B" if is_left else "#CC5500"
    drop_color = "#3399FF" if is_left else "#FF8800"
    edge_color = "#77AADD" if is_left else "#FFBB77"
    
    # Thiết kế Node (Kết hợp Resin và Thông số vào 1 khối)
    node_html = f'''<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="5">
        <TR><TD BGCOLOR="{bg_color}" STYLE="ROUNDED" BORDER="1" COLOR="{text_color}">
            <FONT COLOR="{text_color}" POINT-SIZE="16"><B>🧪 {label}</B></FONT>
        </TD></TR>
        <TR><TD ALIGN="LEFT" BGCOLOR="white">
            <B>⚖️ {row['塗料重量']:,.0f} kg Paint, {row['Solvent_Type']}</B><BR/>
            <FONT COLOR="{drop_color}">💧 {row['Kg_per_1s']:,.0f} kg Solvent per 1 s</FONT><BR/>
            <FONT COLOR="{text_color}">{row['Pct_per_1s']:.1f}% Solvent per 1 s</FONT>
        </TD></TR>
    </TABLE>'''
    
    graph.node(node_id, f'<{node_html}>')
    
    # --- THỦ THUẬT ĐỐI XỨNG ---
    # Để nhánh Trái nằm bên Trái của Center, ta cho chiều mũi tên ngược lại (dir=back)
    if is_left:
        graph.edge(node_id, 'Center', dir='back', color=edge_color, penwidth='3')
    else:
        graph.edge('Center', node_id, color=edge_color, penwidth='3')

# HIỂN THỊ LÊN STREAMLIT
st.graphviz_chart(graph, use_container_width=True)
