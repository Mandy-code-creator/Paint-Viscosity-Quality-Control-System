import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

# ==========================================
# 1. PAGE CONFIGURATION & CUSTOM CSS
# ==========================================
st.set_page_config(page_title="Solvent Adjustment Intelligence", layout="wide", initial_sidebar_state="collapsed")

# CSS: Ẩn Header mặc định của Streamlit và ép giao diện hiện đại
custom_css = """
<style>
    /* Hide Streamlit default header and footer to fix overlapping */
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Light gray app background */
    .stApp { background-color: #F4F7F9; font-family: 'Segoe UI', sans-serif; }
    
    /* Reduce default Streamlit padding */
    .block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 98%; }
    
    /* Main Titles */
    .main-title { font-size: 24px; font-weight: 800; color: #1E293B; margin-bottom: 0px; }
    .sub-title { font-size: 13px; color: #64748B; margin-bottom: 15px; }
    
    /* Metric Cards */
    .metric-card {
        background-color: white; border-radius: 10px; padding: 15px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border: 1px solid #E2E8F0;
        display: flex; flex-direction: column; justify-content: center; height: 90px;
    }
    .metric-title { font-size: 13px; color: #64748B; font-weight: 600; margin-bottom: 5px;}
    .metric-value { font-size: 24px; font-weight: 700; color: #0F172A; margin:0;}
    
    /* Content Boxes */
    .content-box {
        background-color: white; border-radius: 12px; padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border: 1px solid #E2E8F0;
        margin-bottom: 20px; height: 100%;
    }
    
    /* Sankey Headers (Pills) */
    .pill-header {
        border-radius: 20px; padding: 5px 15px; color: white; font-weight: bold; font-size: 12px; text-align: center;
    }
    .pill-blue { background-color: #3B82F6; }
    .pill-teal { background-color: #14B8A6; }
    .pill-purple { background-color: #8B5CF6; }
    
    /* Breadcrumb */
    .breadcrumb { display: flex; align-items: center; gap: 10px; margin-bottom: 15px;}
    .bc-item { background-color: #EEF2FF; color: #4F46E5; padding: 5px 15px; border-radius: 6px; font-size: 13px; font-weight: 600;}
    
    /* Detail Table */
    .info-table { width: 100%; font-size: 13px; color: #334155; border-collapse: collapse; }
    .info-table td { padding: 8px 0; border-bottom: 1px dashed #E2E8F0; }
    .info-table td:last-child { text-align: right; font-weight: 600; }
    .highlight-row { color: #7C3AED; font-weight: bold; font-size: 14px;}
    
    /* Reference Value Card */
    .ref-card { background-color: #FAFAFA; border: 1px solid #E2E8F0; border-radius: 8px; padding: 15px; text-align: center; }
    .ref-title { color: #64748B; font-size: 12px; font-weight: bold; margin-bottom: 10px;}
    .ref-val { color: #7C3AED; font-size: 28px; font-weight: bold; margin: 5px 0;}
    .ref-desc { color: #64748B; font-size: 12px;}
    
    /* Result Box */
    .result-box { background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 8px; padding: 15px; margin-top: 15px;}
    .result-val { color: #059669; font-size: 24px; font-weight: bold; margin: 5px 0;}
    
    /* Remove text shadow from sankey */
    g.sankey-node text { text-shadow: none !important; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)
/* Mind Map Layout */
    .mindmap-container { display: flex; justify-content: space-between; align-items: center; position: relative; padding: 20px 0; min-height: 450px;}
    .mindmap-col { display: flex; flex-direction: column; gap: 30px; z-index: 2; width: 30%; }
    .mindmap-center { z-index: 2; width: 35%; display: flex; justify-content: center; }
    
    /* Spoke Cards (Vệ tinh) */
    .mm-card { background: white; border-radius: 40px; padding: 15px 25px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05); border: 1px solid #E2E8F0; }
    .mm-card-header { font-size: 16px; font-weight: 800; color: #0F172A; display: flex; align-items: center; gap: 8px; margin-bottom: 8px;}
    .mm-card-row { font-size: 13px; color: #475569; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;}
    .mm-highlight { font-weight: 700; color: #D97706; } /* Orange highlight like the image */
    
    /* Center Hub Card (Tâm điểm) */
    .mm-hub { background: white; border-radius: 15px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); border: 1px solid #E2E8F0; width: 100%; max-width: 280px; overflow: hidden; }
    .mm-hub-header { background: #0F172A; color: white; padding: 15px; text-align: center; font-size: 20px; font-weight: bold; }
    .mm-hub-body { padding: 20px; text-align: center; }
    .mm-hub-stat { font-size: 14px; color: #334155; padding: 8px 0; border-bottom: 1px solid #F1F5F9; font-weight: 500;}
    .mm-hub-stat:last-child { border-bottom: none; }

# ==========================================
# 2. DATA LOADING & PREPROCESSING
# ==========================================
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please upload your data file first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()
group_a['Solvent_Type'] = group_a['Solvent_Type'].astype(str)
if 'Vendor' not in group_a.columns: group_a['Vendor'] = 'Unknown'

visc_before = '黏度(秒)'
visc_after = '黏度(秒)_1'
paint_weight = '塗料重量'
solvent_weight = '添加重量'

if all(col in group_a.columns for col in [visc_before, visc_after, paint_weight, solvent_weight]):
    df = group_a.dropna(subset=[visc_before, visc_after, paint_weight, solvent_weight]).copy()
    for col in [visc_before, visc_after, paint_weight, solvent_weight]:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=[visc_before, visc_after, paint_weight, solvent_weight])
    
    df['Viscosity_Reduction'] = df[visc_before] - df[visc_after]
    df = df[(df[paint_weight] > 0) & (df[solvent_weight] > 0) & (df['Viscosity_Reduction'] > 0)]
    df['Reference_Value'] = (df[solvent_weight] * 1000) / (df[paint_weight] * df['Viscosity_Reduction'])
    df['Solvent_Ratio_g_kg'] = (df[solvent_weight] * 1000) / df[paint_weight]
else:
    st.error("⚠️ Missing required data columns.")
    st.stop()


# ==========================================
# 3. HEADER & DYNAMIC CASCADING FILTERS
# ==========================================
c_title, c_filt1, c_filt2, c_filt3, c_filt4 = st.columns([3.5, 1.5, 1.5, 1.5, 2])

with c_title:
    st.markdown("<div class='main-title'>SOLVENT ADJUSTMENT INTELLIGENCE</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-title'>Flow Relationship: Supplier ➔ Resin ➔ Solvent</div>", unsafe_allow_html=True)

with c_filt1: 
    selected_vendor = st.selectbox("Supplier", ["All"] + list(df['Vendor'].unique()))
with c_filt2: 
    resins_avail = df[df['Vendor'] == selected_vendor]['Resin'].unique() if selected_vendor != 'All' else df['Resin'].unique()
    selected_resin = st.selectbox("Resin Type", ["All"] + list(resins_avail))
with c_filt3: 
    mask_s = pd.Series(True, index=df.index)
    if selected_vendor != 'All': mask_s &= (df['Vendor'] == selected_vendor)
    if selected_resin != 'All': mask_s &= (df['Resin'] == selected_resin)
    solvs_avail = df[mask_s]['Solvent_Type'].unique()
    selected_solvent = st.selectbox("Solvent Type", ["All"] + list(solvs_avail))
with c_filt4: 
    st.text_input("Time Period (Demo)", "01/01/2024  ➔  12/31/2024")

# Áp dụng bộ lọc tạo Dataframe con
filtered_df = df.copy()
if selected_vendor != 'All': filtered_df = filtered_df[filtered_df['Vendor'] == selected_vendor]
if selected_resin != 'All': filtered_df = filtered_df[filtered_df['Resin'] == selected_resin]
if selected_solvent != 'All': filtered_df = filtered_df[filtered_df['Solvent_Type'] == selected_solvent]


# ==========================================
# 4. DYNAMIC KPI CARDS
# ==========================================
k1, k2, k3, k4, k5 = st.columns(5)
total_batches = len(filtered_df)
total_solvent_kg = filtered_df[solvent_weight].sum() if not filtered_df.empty else 0
total_resins = filtered_df['Resin'].nunique() if not filtered_df.empty else 0
total_solvents = filtered_df['Solvent_Type'].nunique() if not filtered_df.empty else 0
total_suppliers = filtered_df['Vendor'].nunique() if not filtered_df.empty else 0

k1.markdown(f"""<div class='metric-card'><div class='metric-title'>Total Batches</div>
<p class='metric-value'>{total_batches:,}</p></div>""", unsafe_allow_html=True)

k2.markdown(f"""<div class='metric-card'><div class='metric-title'>Total Solvent Used</div>
<p class='metric-value'>{total_solvent_kg:,.1f} kg</p></div>""", unsafe_allow_html=True)

k3.markdown(f"<div class='metric-card'><div class='metric-title'>Resin Types</div><p class='metric-value'>{total_resins}</p></div>", unsafe_allow_html=True)
k4.markdown(f"<div class='metric-card'><div class='metric-title'>Solvent Types</div><p class='metric-value'>{total_solvents}</p></div>", unsafe_allow_html=True)
k5.markdown(f"<div class='metric-card'><div class='metric-title'>Suppliers</div><p class='metric-value'>{total_suppliers}</p></div>", unsafe_allow_html=True)

st.write("") # Spacer


# ==========================================
# ==========================================
# SECTION 5: LEFT COLUMN - HUB & SPOKE MIND MAP
# ==========================================
    if filtered_df.empty:
        st.info("👈 Please select a valid combination on the left.")
    else:
        # TÍNH TOÁN DỮ LIỆU TỔNG CHO HUB TÂM ĐIỂM
        hub_title = selected_vendor if selected_vendor != 'All' else "All Suppliers"
        total_paint_used = filtered_df[paint_weight].sum()
        avg_init_visc = filtered_df[visc_before].mean()
        avg_target_visc = filtered_df[visc_after].mean()
        total_solvent_added = filtered_df[solvent_weight].sum()
        
        # Tính tỷ lệ % dung môi trung bình trên 1s giảm
        # Công thức: (Solvent / Paint * 100) / Reduction
        filtered_df['Pct_Per_Sec'] = (filtered_df[solvent_weight] / filtered_df[paint_weight] * 100) / filtered_df['Viscosity_Reduction']
        avg_pct_per_sec = filtered_df['Pct_Per_Sec'].mean()

        # NHÓM DỮ LIỆU THEO NHỰA (CÁC VỆ TINH)
        resin_groups = filtered_df.groupby('Resin')
        spoke_data = []
        for resin, group in resin_groups:
            # Tìm dung môi phổ biến nhất cho loại nhựa này
            top_solvent = group['Solvent_Type'].mode()[0] if not group['Solvent_Type'].empty else "Mixed"
            r_paint = group[paint_weight].sum()
            r_solvent = group[solvent_weight].sum()
            r_pct = group['Pct_Per_Sec'].mean()
            spoke_data.append({"resin": resin, "paint": r_paint, "solv_name": top_solvent, "solv_weight": r_solvent, "pct": r_pct})
        
        # Chia đều vệ tinh ra 2 bên (Trái và Phải)
        mid_idx = (len(spoke_data) + 1) // 2
        left_spokes = spoke_data[:mid_idx]
        right_spokes = spoke_data[mid_idx:]

        # HÀM TẠO CARD VỆ TINH (SPOKE)
        def build_spoke_card(data, icon="🧪", color_class="text-blue-500"):
            return f"""
            <div class='mm-card' style='position:relative; z-index:2;'>
                <div class='mm-card-header'>{icon} {data['resin']}</div>
                <div class='mm-card-row'>⚖️ <b>{data['paint']:,.0f} kg</b> Paint, {data['solv_name']}</div>
                <div class='mm-card-row'>💧 <b>{data['solv_weight']:,.1f} kg</b> Solvent</div>
                <div class='mm-card-row'>📉 <span class='mm-highlight'>{data['pct']:.2f}%</span> Solvent per 1 s</div>
            </div>
            """

        # --- TẠO MÃ SVG ĐỘNG ĐỂ VẼ ĐƯỜNG CONG KẾT NỐI ---
        # Tính toán tọa độ y dựa trên số lượng card để đường cong chỉa đúng vị trí
        svg_paths = ""
        
        # Đường cong bên trái
        for i in range(len(left_spokes)):
            y_percent = 20 + (60 / max(1, len(left_spokes) - 1)) * i if len(left_spokes) > 1 else 50
            # Vẽ đường cong Bezier (C) từ giữa (50%,50%) ra rìa trái (0%, y_percent)
            svg_paths += f"""<path d="M 50 50 C 25 50, 25 {y_percent}, 0 {y_percent}" stroke="#3B82F6" stroke-width="4" fill="none" opacity="0.3"/>"""
            
        # Đường cong bên phải
        for i in range(len(right_spokes)):
            y_percent = 20 + (60 / max(1, len(right_spokes) - 1)) * i if len(right_spokes) > 1 else 50
            # Vẽ đường cong Bezier (C) từ giữa (50%,50%) ra rìa phải (100%, y_percent)
            svg_paths += f"""<path d="M 50 50 C 75 50, 75 {y_percent}, 100 {y_percent}" stroke="#F97316" stroke-width="4" fill="none" opacity="0.3"/>"""

        # RÁP TOÀN BỘ GIAO DIỆN MIND MAP
        mindmap_html = f"""
        <div style="background: white; border-radius: 12px; border: 1px solid #E2E8F0; padding: 20px; position: relative; overflow: hidden;">
            
            <svg style="position:absolute; top:0; left:0; width:100%; height:100%; z-index:1;" viewBox="0 0 100 100" preserveAspectRatio="none">
                {svg_paths}
            </svg>

            <div class="mindmap-container">
                
                <div class="mindmap-col">
                    {''.join([build_spoke_card(d, "🧪") for d in left_spokes])}
                </div>
                
                <div class="mindmap-center">
                    <div class="mm-hub">
                        <div class="mm-hub-header">🏭 {hub_title}</div>
                        <div class="mm-hub-body">
                            <div class="mm-hub-stat"><b>{total_paint_used:,.0f} kg</b> Paint Used</div>
                            <div class="mm-hub-stat" style="color:#64748B; font-size:12px;">Jan - Dec 2024</div>
                            <div class="mm-hub-stat">Initial Viscosity: <b>{avg_init_visc:.1f} s</b></div>
                            <div class="mm-hub-stat">Target Viscosity: <b>{avg_target_visc:.1f} s</b></div>
                            <div class="mm-hub-stat"><b>{total_solvent_added:,.1f} kg</b> Solvent Added</div>
                            <div class="mm-hub-stat" style="font-style:italic; color:#0F172A; font-weight:700;">
                                {avg_pct_per_sec:.2f}% Solvent per 1 s Reduction
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="mindmap-col">
                    {''.join([build_spoke_card(d, "🧪") for d in right_spokes])}
                </div>

            </div>
        </div>
        """
        
        st.markdown(mindmap_html, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
