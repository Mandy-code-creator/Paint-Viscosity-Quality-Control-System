import streamlit as st
import pandas as pd
from modules.data_validation import process_and_validate
from modules.charts import render_data_health_kpi

# 1. Page Configuration (Must be the first command)
st.set_page_config(
    page_title="Paint Viscosity Analytics",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Global Session State Initialization
if 'group_a_data' not in st.session_state:
    st.session_state['group_a_data'] = None
if 'rejected_data' not in st.session_state:
    st.session_state['rejected_data'] = None
if 'raw_data_loaded' not in st.session_state:
    st.session_state['raw_data_loaded'] = False

# 3. Main Landing Page UI
st.title("🧪 Paint Viscosity Analytics & SPC Control")
st.markdown("""
Welcome to the Viscosity SPC & Recommendation Engine. 
Please initialize the system by uploading your production data file via the sidebar.
""")

# 4. Sidebar: Data Upload & Global Validation
with st.sidebar:
    st.header("⚙️ System Initialization")
    uploaded_file = st.file_uploader("Upload Raw Data (CSV/Excel)", type=['csv', 'xlsx'])
    
    if uploaded_file is not None:
        try:
            # Read file
            if uploaded_file.name.endswith('.csv'):
                raw_df = pd.read_csv(uploaded_file)
            else:
                raw_df = pd.read_excel(uploaded_file)
                
            # Process and Validate (Strict Group A rule)
            group_a, rejected = process_and_validate(raw_df)
            
            # Save to Session State for other pages to use
            st.session_state['group_a_data'] = group_a
            st.session_state['rejected_data'] = rejected
            st.session_state['raw_data_loaded'] = True
            
            # Render Data Health KPI at the bottom of the sidebar
            total_count = len(raw_df)
            valid_count = len(group_a)
            rejected_count = len(rejected)
            
            render_data_health_kpi(total_count, valid_count, rejected_count)
            
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")

# 5. UI Routing Logic
if st.session_state['raw_data_loaded']:
    st.success("Data successfully loaded and validated! Please select a module from the sidebar menu to proceed.")
else:
    st.info("Awaiting data upload...")
