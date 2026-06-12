import streamlit as st
import pandas as pd
import graphviz # Bắt buộc phải có

st.set_page_config(page_title="MindMap Test", layout="wide")

st.title("🌳 Test Biểu Đồ Mind Map (Graphviz)")
st.info("Bản test siêu gọn nhẹ: Chỉ vẽ nhánh Yungchi để kiểm tra giao diện Graphviz.")

# --- 1. TẠO DỮ LIỆU MOCK CHUẨN MẪU YUNGCHI ---
data = pd.DataFrame({
    'Vendor': ['Yungchi'] * 6,
    'Resin': ['PE', 'SMP', 'SMP', 'EPOXY', 'PU', 'PVDF'],
    'Solvent_Type': ['5203', '5203', '5203', '5203', 'CB5203', 'Isophorone'],
    '塗料重量': [500, 400, 400, 500, 600, 300], # kg Sơn
    '添加重量': [17, 18, 18, 25, 12, 22],   # kg Dung môi
    '黏度(秒)': [35] * 6,
    '黏度(秒)_1': [30] * 6,
})

# --- 2. TÍNH TOÁN CÁC CHỈ SỐ ---
data['Delta_V'] = data['黏度(秒)'] - data['黏度(秒)_1'] # Giảm 5 giây
data['Solvent_Ratio_Percent'] = (data['添加重量'] / data['塗料重量']) * 100
data['Kg_per_1s'] = data['添加重量'] / data['Delta_V']
data['Pct_per_1s'] = data['Solvent_Ratio_Percent'] / data['Delta_V']

# --- 3. VẼ BIỂU ĐỒ GRAPHVIZ ---
graph = graphviz.Digraph(engine='dot')
graph.attr(rankdir='LR', size='15,10') # Vẽ từ Trái sang Phải
graph.attr('node', shape='plaintext', fontname='Arial')

# TẠO NODE TRUNG TÂM (Vendor)
total_paint = data['塗料重量'].sum()
total_solv = data['添加重量'].sum()
# Tính % Solvent per 1s tổng
reduction_pct = ((total_solv / total_paint) * 100) / 5 

root_html = (
    f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">'
    f'<TR><TD ALIGN="CENTER" STYLE="rounded"><FONT FACE="Arial"><IMG SRC="https://img.icons8.com/plasticine/100/factory.png"/></FONT></TD></TR>'
    f'<TR><TD ALIGN="CENTER"><B><FONT POINT-SIZE="24" COLOR="white">Yungchi</FONT></B></TD></TR>'
    f'<TR><TD ALIGN="LEFT"><FONT COLOR="white"><BR/>{total_paint:,.0f} kg Paint Used<BR/>Jan–Apr 2026<BR/>Initial Viscosity: 35 s<BR/>Target Viscosity: 30 s<BR/>{total_solv:,.0f} kg Solvent Added<BR/></FONT></TD></TR>'
    f'<TR><TD ALIGN="LEFT"><B><FONT COLOR="red"><BR/>{reduction_pct:.1f}% Solvent per 1 s Reduction</FONT></B></TD></TR>'
    f'</TABLE>>'
)
graph.node('root', root_html, style='rounded,filled', fillcolor='#1B3C73', fontcolor='white')

# TẠO CÁC NODE NHÁNH VÀ LÁ
left_resins = ['PE', 'SMP'] # Định hướng màu sắc cho giống ảnh (Trái xanh, phải cam)

for idx, row in data.iterrows():
    resin = row['Resin']
    solvent = row['Solvent_Type']
    
    # 3.1 Node Resin (Có icon ống nghiệm)
    resin_id = f"resin_{idx}"
    fill_color = '#E1E9F0' if resin in left_resins else '#F9DFDC'
    icon_color = '#1E88E5' if resin in left_resins else '#FF8F00'
    
    graph.node(resin_id, 
               f"<<B><FONT FACE='Arial' POINT-SIZE='16' COLOR='{icon_color}'><IMG SRC='https://img.icons8.com/plasticine/100/test-tube.png'/></FONT> {resin}</B>>",
               style='rounded,filled', fillcolor=fill_color, fontcolor='black')
    
    # Nối Gốc -> Resin
    graph.edge('root', resin_id)
    
    # 3.2 Node Thông số chi tiết
    child_id = f"child_{idx}"
    child_html = (
        f"<<TABLE BORDER='0' CELLBORDER='0' CELLSPACING='3'>"
        f"<TR><TD ALIGN='LEFT'><B><FONT COLOR='#333333'>{row['塗料重量']:,.0f} kg Paint, {solvent}</FONT></B></TD></TR>"
        f"<TR><TD ALIGN='LEFT'><FONT COLOR='#D9534F'><B>{row['Kg_per_1s']:,.1f} kg Solvent per 1 s</B></FONT></TD></TR>"
        f"<TR><TD ALIGN='LEFT'><FONT COLOR='#f0ad4e'><B>{row['Pct_per_1s']:.1f}% Solvent per 1 s</B></FONT></TD></TR>"
        f"</TABLE>>"
    )
    graph.node(child_id, child_html)
    
    # Nối Resin -> Thông số
    graph.edge(resin_id, child_id)

# HIỂN THỊ LÊN STREAMLIT
st.graphviz_chart(graph, use_container_width=True)
