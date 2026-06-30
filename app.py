import streamlit as st
import pandas as pd
from modules.data_validation import process_and_validate
from modules.charts import render_data_health_kpi

# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="Paint Viscosity Analytics",
    page_icon="🧪",
    layout="wide"
)

# =========================================================
# 2. GLOBAL SESSION STATE
# =========================================================
if 'group_a_data' not in st.session_state:
    st.session_state['group_a_data'] = None

if 'rejected_data' not in st.session_state:
    st.session_state['rejected_data'] = None

if 'raw_data' not in st.session_state:
    st.session_state['raw_data'] = None

if 'raw_data_loaded' not in st.session_state:
    st.session_state['raw_data_loaded'] = False


# =========================================================
# 3. LOAD + PROCESS DATA
# =========================================================
@st.cache_data(show_spinner=False)
def load_and_process_file(uploaded_file):
    if uploaded_file.name.lower().endswith('.csv'):
        raw_df = pd.read_csv(uploaded_file)
    else:
        raw_df = pd.read_excel(uploaded_file)

    group_a, rejected_data = process_and_validate(raw_df)

    return raw_df, group_a, rejected_data


# =========================================================
# 4. MAIN TITLE
# =========================================================
st.title("🧪 Paint Viscosity Analytics & SPC Control")


# =========================================================
# 5. SIDEBAR
# =========================================================
with st.sidebar:
    st.header("⚙️ System Initialization")

    uploaded_file = st.file_uploader(
        "Upload Raw Data (CSV/Excel)",
        type=['csv', 'xlsx']
    )

    # Upload only when no active data is stored
    if uploaded_file is not None and not st.session_state['raw_data_loaded']:
        try:
            with st.spinner("Processing data..."):
                raw_df, group_a, rejected_data = load_and_process_file(uploaded_file)

            st.session_state['raw_data'] = raw_df
            st.session_state['group_a_data'] = group_a
            st.session_state['rejected_data'] = rejected_data
            st.session_state['raw_data_loaded'] = True

            st.rerun()

        except Exception as e:
            st.error(f"Error while processing file: {str(e)}")

    # =====================================================
    # DATA HEALTH STATUS
    # =====================================================
    if st.session_state['raw_data_loaded']:

        raw_df = st.session_state['raw_data']
        group_a = st.session_state['group_a_data']
        rejected_data = st.session_state['rejected_data']

        total_count = len(raw_df)
        valid_count = len(group_a)
        excluded_count = len(rejected_data)

        st.success("✅ File Data Locked in Memory")

        # Truyền rejected_data vào để nút mở log hoạt động
        render_data_health_kpi(
            total_count=total_count,
            valid_count=valid_count,
            excluded_count=excluded_count,
            rejected_data=rejected_data
        )

        st.markdown("---")

        if st.button(
            "Clear Data & Upload New File",
            type="secondary",
            use_container_width=True
        ):
            keys_to_clear = [
                'raw_data',
                'group_a_data',
                'rejected_data',
                'raw_data_loaded'
            ]

            for key in keys_to_clear:
                st.session_state.pop(key, None)

            st.cache_data.clear()
            st.rerun()


# =========================================================
# 6. MAIN PAGE CONTENT
# =========================================================
if st.session_state['raw_data_loaded']:
    st.success("Data loaded! Please select a module from the menu.")
else:
    st.info("Awaiting data upload...")
