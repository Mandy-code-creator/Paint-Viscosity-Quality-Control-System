import streamlit as st
import pandas as pd
import numpy as np

# ==========================================
# 1. PAGE CONFIG & CSS
# ==========================================
st.set_page_config(page_title="Mind Map Analysis", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    header {visibility: hidden;}
    .stApp { background-color: #F4F7F9; font-family: 'Segoe UI', sans-serif; }
    .main-title { font-size: 26px; font-weight: 800; color: #1E293B; margin-bottom: 20px; }
    
    /* Mind Map Styling */
    .mindmap-wrapper { background: white; border-radius: 16px; border: 1px solid #E2E8F0; padding: 40px; position: relative; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .mindmap-container { display: flex; justify-content: space-between; align-items: center; position: relative; min-height: 450px; z-index: 2;}
    .mindmap-col { display: flex; flex-direction: column; gap: 30px; width: 30%; }
    .mindmap-center { width: 35%; display: flex; justify-content: center; }
    
    .mm-card { background: white; border-radius: 40px; padding: 15px 20px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); border: 1px solid #E2E8F0; }
    .mm-card-header { font-size: 15px; font-weight: 800; color: #0F172A; margin-bottom: 5px; }
    .mm-card-row { font-size: 13px; color: #475569; margin-bottom: 3px; }
    
    .mm-hub { background: white; border-radius: 16px; box-shadow: 0 10px 20px rgba(0,0,0,0.1); border: 2px solid #0F172A; width: 280px; }
    .mm-hub-header { background: #0F172A; color: white; padding: 15px; text-align: center; font-size: 20px; font-weight: bold; }
    .mm-hub-body { padding: 20px; text-align: center; }
    .mm-hub-stat { font-size: 14px; color: #334155; padding: 8px 0; border-bottom: 1px solid #F1F5F9; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATA LOADING & AUTOMATIC MAPPING
# ==========================================
if 'group_a_data' not in st.session_state:
    st.error("Please upload data on the main page first!")
    st.stop()

df = st.session_state['group_a_data'].copy()

# Tự động map cột để tránh KeyError
mapping = {
    'Vendor': ['Vendor', 'Nhà cung cấp'],
    'Resin': ['Resin', 'Loại nhựa'],
    'Solvent_Type': ['Solvent_Type', 'Dung môi', 'Loại dung môi', 'Solvent', '稀釋劑'],
    'Paint_Weight': ['塗料重量', 'Paint Weight', 'Trọng lượng sơn'],
    'Solvent_Weight': ['添加重量', 'Solvent Weight', 'Lượng dung môi'],
    'Visc_Before': ['黏度(秒)', 'Initial Viscosity', 'Độ nhớt đầu'],
    'Visc_After': ['黏度(秒)_1', 'Final Viscosity', 'Độ nhớt sau']
}

for std, aliases in mapping.items():
    for col in df.columns:
        if col in aliases:
            df.rename(columns={col: std}, inplace=True)

# Đảm bảo các cột cần thiết tồn tại
for std in mapping.keys():
    if std not in df.columns: df[std] = "Unknown"

# Ép kiểu số
for col in ['Paint_Weight', 'Solvent_Weight', 'Visc_Before', 'Visc_After']:
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

df['Delta_V'] = df['Visc_Before'] - df['Visc_After']
df['Pct'] = (df['Solvent_Weight'] / df['Paint_Weight']) * 100

# ==========================================
# 3. FILTERS
# ==========================================
st.markdown("<div class='main-title'>Viscosity Analysis Hub</div>", unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
with c1: v = st.selectbox("Supplier", ["All"] + list(df['Vendor'].unique()))
with c2: r = st.selectbox("Resin", ["All"] + list(df['Resin'].unique()))
with c3: s = st.selectbox("Solvent", ["All"] + list(df['Solvent_Type'].unique()))

mask = (df['Vendor']==v if v!="All" else True) & (df['Resin']==r if r!="All" else True) & (df['Solvent_Type']==s if s!="All" else True)
filtered = df[mask]

# ==========================================
# 4. RENDERING MIND MAP
# ==========================================
if filtered.empty:
    st.info("No data found.")
else:
    # Aggregation
    spokes = filtered.groupby('Resin').agg({'Paint_Weight':'sum', 'Solvent_Weight':'sum', 'Pct':'mean'}).reset_index()
    mid = (len(spokes)+1)//2
    left, right = spokes[:mid], spokes[mid:]

    def card(row):
        return f"""<div class='mm-card'>
            <div class='mm-card-header'>🧪 {row['Resin']}</div>
            <div class='mm-card-row'>Paint: {row['Paint_Weight']:.0f} kg</div>
            <div class='mm-card-row'>Solvent: {row['Solvent_Weight']:.1f} kg</div>
            <div class='mm-card-row'>Ratio: {row['Pct']:.2f}%</div>
        </div>"""

    # Render HTML/SVG
    paths = "".join([f'<path d="M 50 50 C 25 50, 25 {20+(60/max(1,len(left)-1))*i}, 0 {20+(60/max(1,len(left)-1))*i}" stroke="#3B82F6" stroke-width="3" fill="none" opacity="0.4"/>' for i in range(len(left))])
    paths += "".join([f'<path d="M 50 50 C 75 50, 75 {20+(60/max(1,len(right)-1))*i}, 100 {20+(60/max(1,len(right)-1))*i}" stroke="#F97316" stroke-width="3" fill="none" opacity="0.4"/>' for i in range(len(right))])

    st.markdown(f"""
    <div class="mindmap-wrapper">
        <svg style="position:absolute; top:0; left:0; width:100%; height:100%; z-index:1;" viewBox="0 0 100 100" preserveAspectRatio="none">{paths}</svg>
        <div class="mindmap-container">
            <div class="mindmap-col">{"".join([card(r) for _, r in left.iterrows()])}</div>
            <div class="mindmap-center">
                <div class="mm-hub">
                    <div class="mm-hub-header">🏭 {v if v!="All" else "All Suppliers"}</div>
                    <div class="mm-hub-body">
                        <div class="mm-hub-stat">Paint: {filtered['Paint_Weight'].sum():,.0f} kg</div>
                        <div class="mm-hub-stat">Solvent: {filtered['Solvent_Weight'].sum():,.1f} kg</div>
                    </div>
                </div>
            </div>
            <div class="mindmap-col">{"".join([card(r) for _, r in right.iterrows()])}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
