import streamlit as st
import pandas as pd
from modules.data_validation import process_and_validate
from modules.charts import render_data_health_kpi

# 1. Page Configuration
st.set_page_config(page_title="Paint Viscosity Analytics", page_icon="🧪", layout="wide")

# 2. KHỞI TẠO BỘ NHỚ TOÀN CỤC (GLOBAL STATE)
# Đây là "Két sắt" giữ dữ liệu không bị mất khi chuyển trang
if 'group_a_data' not in st.session_state:
    st.session_state['group_a_data'] = None
if 'rejected_data' not in st.session_state:
    st.session_state['rejected_data'] = None
if 'raw_data_loaded' not in st.session_state:
    st.session_state['raw_data_loaded'] = False

# Cache hàm đọc file để tăng tốc
@st.cache_data(show_spinner=False)
def load_and_process_file(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        raw_df = pd.read_csv(uploaded_file)
    else:
        raw_df = pd.read_excel(uploaded_file)
    return process_and_validate(raw_df)

st.title("🧪 Paint Viscosity Analytics & SPC Control")

# 3. SIDEBAR TỐI ƯU
with st.sidebar:
    st.header("⚙️ System Initialization")
    
    # Nút Upload File
    uploaded_file = st.file_uploader("Upload Raw Data (CSV/Excel)", type=['csv', 'xlsx'])
    
    # LOGIC GIỮ FILE:
    # Nếu có file upload VÀ dữ liệu chưa được nạp vào két sắt -> Xử lý và cất vào két
    if uploaded_file is not None and not st.session_state['raw_data_loaded']:
        try:
            with st.spinner("Processing data..."):
                group_a, rejected = load_and_process_file(uploaded_file)
                
            # CẤT VÀO KÉT SẮT NGAY LẬP TỨC
            st.session_state['group_a_data'] = group_a
            st.session_state['rejected_data'] = rejected
            st.session_state['raw_data_loaded'] = True
            
        except Exception as e:
            st.error(f"Error: {str(e)}")

    # LOGIC HIỂN THỊ KPI:
    # Luôn đọc dữ liệu từ Két Sắt (session_state) để hiển thị, bất kể vừa upload hay chuyển trang về
    if st.session_state['raw_data_loaded']:
        group_a = st.session_state['group_a_data']
        rejected = st.session_state['rejected_data']
        total_count = len(group_a) + len(rejected)
        
        st.success("✅ File Data Locked in Memory")
        render_data_health_kpi(total_count, len(group_a), len(rejected))
        
        # Thêm nút XÓA DỮ LIỆU để người dùng chủ động reset khi cần tải file mới
        if st.button("Clear Data & Upload New File", type="secondary"):
            st.session_state['group_a_data'] = None
            st.session_state['rejected_data'] = None
            st.session_state['raw_data_loaded'] = False
            st.rerun()

# 4. TRANG CHỦ CONTENT
if st.session_state['raw_data_loaded']:
    st.success("Data loaded! Please select a module from the menu.")
else:
    st.info("Awaiting data upload...")
