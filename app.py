import streamlit as st
from data_processing import load_and_preprocess, render_sidebar_filters

st.set_page_config(page_title="Paint QC Dashboard", layout="wide")
st.title("Paint Viscosity Quality Control System")

uploaded_file = st.sidebar.file_uploader("Upload Production Data", type=["csv", "xlsx"])

if uploaded_file is not None:
    try:
        # Tải dữ liệu 1 lần duy nhất
        if 'raw_data' not in st.session_state:
            df = load_and_preprocess(uploaded_file)
            st.session_state['raw_data'] = df
        else:
            df = st.session_state['raw_data']

        st.success("Data loaded successfully. Please select a page from the sidebar.")
        
        # Áp dụng bộ lọc Global từ Sidebar
        df_filtered = render_sidebar_filters(df)
        
        st.write("### Filtered Production Data Overview")
        preview_columns = ['Mix_Date', 'Batch_Lot', 'Drum_No', 'Paint_Code_Str', 'Supplier', 
                           'Resin_Type', 'Color_Group', 'Viscosity_Before', 'Viscosity_After', 'Reduction']
        existing_cols = [col for col in preview_columns if col in df_filtered.columns]
        st.dataframe(df_filtered[existing_cols].head(15))
        
    except Exception as e:
        st.error(f"Error processing file: {e}")
else:
    st.info("Please upload the production dataset to begin.")
