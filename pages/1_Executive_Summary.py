import streamlit as st
import pandas as pd
import numpy as np

# ==========================================
# 1. PAGE CONFIGURATION & CUSTOM CSS
# ==========================================
st.set_page_config(page_title="Solvent Mind Map", layout="wide", initial_sidebar_state="expanded")

custom_css = """
<style>
    /* Hide default Streamlit elements */
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    
    /* App background */
    .stApp { background-color: #F4F7F9; font-family: 'Segoe UI', sans-serif; }
    .block-container { padding-top: 2rem; max-width: 95%; }
    
    /* Titles */
    .main-title { font-size: 26px; font-weight: 800; color: #1E293B; margin-bottom: 5px; }
    .sub-title { font-size: 14px; color: #64748B; margin-bottom: 25px; }
    
    /* MIND MAP STYLES */
    .mindmap-wrapper { background: white; border-radius: 16px; border: 1px solid #E2E8F0; padding: 40px 20px; position: relative; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    .mindmap-container { display: flex; justify-content: space-between; align-items: center; position: relative; min-height: 500px; z-index: 2;}
    
    /* Columns */
    .mindmap-col { display: flex; flex-direction: column; gap: 35px; width: 30%; max-width: 320px; }
    .mindmap-center { width: 40%; display: flex; justify-content: center; }
    
    /* Spoke Cards (Outer Nodes) */
    .mm-card { background: white; border-radius: 40px; padding: 18px 25px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.08); border: 1px solid #E2E8F0; transition: transform 0.2s;}
    .mm-card:hover { transform: translateY(-3px); }
    .mm-card-header { font-size: 17px; font-weight: 800; color: #0F172A; display: flex; align-items: center; gap: 8px; margin-bottom: 10px;}
    .mm-card-row { font-size: 14px; color: #475569; margin-bottom: 6px; display: flex; align-items: center; gap: 8px;}
    .mm-highlight { font-weight: 700; color: #D97706; } 
    
    /* Center Hub */
    .mm-hub { background: white; border-radius: 16px; box-shadow: 0 25px 30px -5px rgba(0,0,0,0.15); border: 2px solid #E2E8F0; width: 100%; max-width: 320px; overflow: hidden; }
    .mm-hub-header { background: #0F172A; color: white; padding: 20px; text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 0.5px;}
    .mm-hub-body { padding: 25px; text-align: center; }
    .mm-hub-stat { font-size: 15px; color: #334155; padding: 10px 0; border-bottom: 1px solid #F1F5F9; font-weight: 500;}
    .mm-hub-stat:last-child { border-bottom: none; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ==========================================
# 2. DATA LOADING (STANDALONE & SESSION)
# ==========================================
if 'raw_data_loaded' in st.session_state and st.session_state['raw_data_loaded']:
    group_a = st.session_state['group_a_data'].copy()
else:
    st.sidebar.markdown("### 📂 Data Input")
    uploaded_file = st.sidebar.file_uploader("Upload Data (CSV/Excel)", type=["csv", "xlsx"])

    if uploaded_file is not None:
        if uploaded_file.name.endswith('.csv'):
            group_a = pd.read_csv(uploaded_file)
        else:
            group_a = pd.read_excel(uploaded_file)
        st.session_state['raw_data_loaded'] = True
        st.session_state['group_a_data'] = group_a
        st.rerun()
    else:
        st.warning("⚠️ No data loaded. Please upload your data file in the sidebar, or click below to test with sample data.")
        if st.button("🚀 Load Sample Data for Testing"):
            np.random.seed(42)
            n = 1248
            mock_data = pd.DataFrame({
                'Vendor': np.random.choice(['Yungchi', 'CCP', 'Nan Ya', 'Atul', 'Formosa', 'Other'], n, p=[0.35, 0.25, 0.15, 0.1, 0.1, 0.05]),
                'Resin': np.random.choice(['PE', 'EPOXY', 'PU', 'PVDF', 'SMP', 'Other'], n),
                'Solvent_Type': np.random.choice(['5203', 'CB5203', 'ISOPHORONE', 'PMA', 'BUTYL ACETATE', 'BAC'], n),
                '黏度(秒)': np.random.uniform(45, 55, n),
                '黏度(秒)_1': np.random.uniform(35, 44, n),
                '塗料重量': np.random.uniform(400, 1000, n),
                '添加重量': np.random.uniform(5, 25, n)
            })
            # Giả lập Delta_V cho sample data
            mock_data['Delta_V'] = mock_data['黏度(秒)'] - mock_data['黏度(秒)_1']
            
            st.session_state['raw_data_loaded'] = True
            st.session_state['group_a_data'] = mock_data
            st.rerun()
        st.stop()

# ==========================================
# ==========================================
# 3. ROBUST DATA PREPROCESSING (SỬ DỤNG DANH SÁCH CỘT CỦA BẠN)
# ==========================================

# 1. Bảng ánh xạ linh hoạt (Mapping)
# Dù bạn đặt tên cột thế nào, hệ thống cũng tự nhận diện được
col_mapping = {
    'Nhà cung cấp': 'Vendor',
    'Loại nhựa': 'Resin',
    'Dung môi': 'Solvent_Type',
    'Loại dung môi': 'Solvent_Type',
    'Solvent': 'Solvent_Type',
    'Mã sơn': '塗料代碼',
    'Feature': '塗料代碼'
}
group_a.rename(columns=col_mapping, inplace=True)

# 2. Xử lý dữ liệu an toàn
required_cols = ['塗料重量', '添加重量', '黏度(秒)', '黏度(秒)_1']

# Kiểm tra nếu thiếu cột bắt buộc
missing = [c for c in required_cols if c not in group_a.columns]
if missing:
    st.error(f"🚨 Missing columns: {missing}. Please check your file headers.")
    st.stop()

# Chuyển đổi dữ liệu sang dạng số
for col in required_cols:
    group_a[col] = pd.to_numeric(group_a[col], errors='coerce')

# Tính toán Delta_V nếu file chưa có
if 'Delta_V' not in group_a.columns:
    group_a['Delta_V'] = group_a['黏度(秒)'] - group_a['黏度(秒)_1']

# Lọc dữ liệu hợp lệ
df = group_a.dropna(subset=required_cols).copy()
df = df[(df['塗料重量'] > 0) & (df['添加重量'] > 0) & (df['Delta_V'] > 0)]

# Tính Sensitivity (dựa trên logic code của bạn)
# Tỷ lệ % dung môi
df['Solvent_Ratio_Percent'] = (df['添加重量'] / df['塗料重量']) * 100
# Độ nhạy (Sensitivity): Delta_V chia cho Tỷ lệ %
df['Sensitivity'] = df['Delta_V'] / df['Solvent_Ratio_Percent'].replace(0, 1)

# Gán giá trị mặc định cho cột phân loại nếu thiếu
for col in ['Vendor', 'Resin', 'Solvent_Type']:
    if col not in df.columns:
        df[col] = 'Unknown'
    df[col] = df[col].astype(str)

# Lưu lại vào session để các phần sau của app sử dụng
st.session_state['group_a_data'] = df


# ==========================================
# 4. HEADER & FILTERS
# ==========================================
st.markdown("<div class='main-title'>SOLVENT FLOW INTELLIGENCE</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Interactive Mind Map: Supplier ➔ Resin ➔ Solvent Relationship</div>", unsafe_allow_html=True)

c_filt1, c_filt2, c_filt3, c_spacer = st.columns([2, 2, 2, 4])

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

# Apply Filters
filtered_df = df.copy()
if selected_vendor != 'All': filtered_df = filtered_df[filtered_df['Vendor'] == selected_vendor]
if selected_resin != 'All': filtered_df = filtered_df[filtered_df['Resin'] == selected_resin]
if selected_solvent != 'All': filtered_df = filtered_df[filtered_df['Solvent_Type'] == selected_solvent]

st.write("") # Spacer

# ==========================================
# 5. DYNAMIC MIND MAP RENDERER
# ==========================================
if filtered_df.empty:
    st.info("👈 No data available for the current selection. Please adjust your filters.")
else:
    # 1. Hub Data Aggregation
    hub_title = selected_vendor if selected_vendor != 'All' else "All Suppliers"
    total_paint_used = filtered_df[paint_weight].sum()
    total_solvent_added = filtered_df[solvent_weight].sum()
    
    avg_init_visc = filtered_df[visc_before].mean() if visc_before in filtered_df.columns else 0.0
    avg_target_visc = filtered_df[visc_after].mean() if visc_after in filtered_df.columns else 0.0
    
    avg_pct_per_sec = filtered_df['Pct_Per_Sec'].mean()
    if pd.isna(avg_pct_per_sec) or avg_pct_per_sec == float('inf'): avg_pct_per_sec = 0.0

    # 2. Spoke Data Aggregation (Grouped by Resin)
    spoke_data = []
    for resin, group in filtered_df.groupby('Resin'):
        top_solvent = group['Solvent_Type'].mode()[0] if not group['Solvent_Type'].empty else "Mixed"
        r_paint = group[paint_weight].sum()
        r_solvent = group[solvent_weight].sum()
        r_pct = group['Pct_Per_Sec'].mean()
        if pd.isna(r_pct) or r_pct == float('inf'): r_pct = 0.0
        spoke_data.append({"resin": resin, "paint": r_paint, "solv_name": top_solvent, "solv_weight": r_solvent, "pct": r_pct})
    
    # Sort spokes by paint weight descending for better visualization
    spoke_data = sorted(spoke_data, key=lambda x: x['paint'], reverse=True)
    
    # Split Spokes Left & Right
    mid_idx = (len(spoke_data) + 1) // 2
    left_spokes = spoke_data[:mid_idx]
    right_spokes = spoke_data[mid_idx:]

    # 3. HTML Builder for Spoke Cards
    def build_spoke_card(data):
        return f"""
        <div class='mm-card'>
            <div class='mm-card-header'>🧪 {data['resin']}</div>
            <div class='mm-card-row'>⚖️ <b>{data['paint']:,.0f} kg</b> Paint, {data['solv_name']}</div>
            <div class='mm-card-row'>💧 <b>{data['solv_weight']:,.1f} kg</b> Solvent</div>
            <div class='mm-card-row'>📉 <span class='mm-highlight'>{data['pct']:.3f}%</span> Solvent / 1s</div>
        </div>
        """

    left_spokes_html = "".join([build_spoke_card(d) for d in left_spokes])
    right_spokes_html = "".join([build_spoke_card(d) for d in right_spokes])

    # 4. SVG Dynamic Connections
    svg_paths = ""
    # Left connections
    for i in range(len(left_spokes)):
        y_percent = 20 + (60 / max(1, len(left_spokes) - 1)) * i if len(left_spokes) > 1 else 50
        svg_paths += f'<path d="M 50 50 C 25 50, 25 {y_percent}, 0 {y_percent}" stroke="#3B82F6" stroke-width="4" fill="none" opacity="0.4"/>'
        
    # Right connections
    for i in range(len(right_spokes)):
        y_percent = 20 + (60 / max(1, len(right_spokes) - 1)) * i if len(right_spokes) > 1 else 50
        svg_paths += f'<path d="M 50 50 C 75 50, 75 {y_percent}, 100 {y_percent}" stroke="#F97316" stroke-width="4" fill="none" opacity="0.4"/>'

    # 5. Render Final Map
    mindmap_html = f"""
    <div class="mindmap-wrapper">
        <svg style="position:absolute; top:0; left:0; width:100%; height:100%; z-index:1;" viewBox="0 0 100 100" preserveAspectRatio="none">
            {svg_paths}
        </svg>
        <div class="mindmap-container">
            <div class="mindmap-col">
                {left_spokes_html}
            </div>
            
            <div class="mindmap-center">
                <div class="mm-hub">
                    <div class="mm-hub-header">🏭 {hub_title}</div>
                    <div class="mm-hub-body">
                        <div class="mm-hub-stat"><b>{total_paint_used:,.0f} kg</b> Paint Used</div>
                        <div class="mm-hub-stat">Avg Initial Visc: <b>{avg_init_visc:.1f} s</b></div>
                        <div class="mm-hub-stat">Avg Target Visc: <b>{avg_target_visc:.1f} s</b></div>
                        <div class="mm-hub-stat"><b>{total_solvent_added:,.1f} kg</b> Solvent Added</div>
                        <div class="mm-hub-stat" style="font-style:italic; color:#0F172A; font-weight:700;">
                            {avg_pct_per_sec:.3f}% Solvent / 1s Drop
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="mindmap-col">
                {right_spokes_html}
            </div>
        </div>
    </div>
    """
    st.markdown(mindmap_html, unsafe_allow_html=True)
