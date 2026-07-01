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
if "raw_data" not in st.session_state:
    st.session_state["raw_data"] = None

if "group_a_data" not in st.session_state:
    st.session_state["group_a_data"] = None

if "rejected_data" not in st.session_state:
    st.session_state["rejected_data"] = None

if "raw_data_loaded" not in st.session_state:
    st.session_state["raw_data_loaded"] = False


# =========================================================
# 3. LOAD + PROCESS FILE
# =========================================================
@st.cache_data(show_spinner=False)
def load_and_process_file(uploaded_file):
    """
    Read uploaded CSV / Excel file and run validation logic.
    """

    file_name = uploaded_file.name.lower()

    if file_name.endswith(".csv"):
        try:
            raw_df = pd.read_csv(
                uploaded_file,
                encoding="utf-8-sig"
            )
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            raw_df = pd.read_csv(
                uploaded_file,
                encoding="big5"
            )
    else:
        raw_df = pd.read_excel(uploaded_file)

    group_a, rejected_data = process_and_validate(raw_df)

    return raw_df, group_a, rejected_data


# =========================================================
# 4. MAIN PAGE TITLE
# =========================================================
st.title("🧪 Paint Viscosity Analytics & SPC Control")


# =========================================================
# 5. SIDEBAR
# =========================================================
with st.sidebar:

    st.header("⚙️ System Initialization")

    uploaded_file = st.file_uploader(
        "Upload Raw Data (CSV/Excel)",
        type=["csv", "xlsx"]
    )

    # -----------------------------------------------------
    # LOAD FILE ONLY WHEN NO FILE IS CURRENTLY LOCKED
    # -----------------------------------------------------
    if uploaded_file is not None:

    need_reload = (
        not st.session_state.get("raw_data_loaded", False)
        or st.session_state.get("group_a_data") is None
        or st.session_state["group_a_data"].empty
    )

    if need_reload:
        try:
            with st.spinner("Processing data..."):
                raw_df, group_a, rejected_data = load_and_process_file(
                    uploaded_file
                )

            st.session_state["raw_data"] = raw_df.copy()
            st.session_state["group_a_data"] = group_a.copy()
            st.session_state["rejected_data"] = rejected_data.copy()

            # Chỉ xem là load thành công khi Group A thật sự có dữ liệu
            st.session_state["raw_data_loaded"] = not group_a.empty

            if group_a.empty:
                st.warning(
                    "⚠️ 檔案已讀取，但沒有符合 Group A 條件的有效資料。"
                )
            else:
                st.rerun()

        except Exception as e:
            st.session_state["raw_data_loaded"] = False
            st.error(f"Error while processing file: {str(e)}")

    # -----------------------------------------------------
    # DATA HEALTH STATUS
    # -----------------------------------------------------
    if st.session_state["raw_data_loaded"]:

        group_a = st.session_state.get(
            "group_a_data",
            pd.DataFrame()
        )

        rejected_data = st.session_state.get(
            "rejected_data",
            pd.DataFrame()
        )

        if group_a is None:
            group_a = pd.DataFrame()

        if rejected_data is None:
            rejected_data = pd.DataFrame()

        total_count = len(group_a) + len(rejected_data)
        valid_count = len(group_a)
        excluded_count = len(rejected_data)

        st.success("✅ File Data Locked in Memory")

        render_data_health_kpi(
            total_count=total_count,
            valid_count=valid_count,
            excluded_count=excluded_count,
            rejected_data=rejected_data
        )

        st.markdown("---")

        # -------------------------------------------------
        # CLEAR DATA
        # -------------------------------------------------
        if st.button(
            "Clear Data & Upload New File",
            type="secondary",
            use_container_width=True
        ):
            for key in [
                "raw_data",
                "group_a_data",
                "rejected_data",
                "raw_data_loaded"
            ]:
                st.session_state.pop(key, None)

            st.cache_data.clear()
            st.rerun()


# =========================================================
# 6. MAIN PAGE CONTENT
# =========================================================
if st.session_state["raw_data_loaded"]:

    group_a = st.session_state.get(
        "group_a_data",
        pd.DataFrame()
    )

    rejected_data = st.session_state.get(
        "rejected_data",
        pd.DataFrame()
    )

    if group_a is None:
        group_a = pd.DataFrame()

    if rejected_data is None:
        rejected_data = pd.DataFrame()

    st.success("✅ Data loaded successfully.")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Total Records",
        f"{len(group_a) + len(rejected_data):,}"
    )

    col2.metric(
        "Valid Group A",
        f"{len(group_a):,}"
    )

    col3.metric(
        "Excluded Records",
        f"{len(rejected_data):,}"
    )

    st.info(
        "Please select a module from the navigation menu to continue analysis."
    )

else:
    st.info("Awaiting data upload...")
