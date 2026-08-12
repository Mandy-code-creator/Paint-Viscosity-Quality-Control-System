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
def initialize_session_state():
    defaults = {
        "raw_data": None,
        "group_a_data": None,
        "rejected_data": None,
        "raw_data_loaded": False,
        "loaded_file_name": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialize_session_state()


# =========================================================
# 3. LOAD + PROCESS FILE
# =========================================================
@st.cache_data(show_spinner=False)
def load_and_process_file(uploaded_file):
    """
    Read uploaded CSV / Excel file
    and run validation logic.
    """

    file_name = uploaded_file.name.lower()

    # -----------------------------------------------------
    # CSV
    # -----------------------------------------------------
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

    # -----------------------------------------------------
    # EXCEL
    # -----------------------------------------------------
    else:
        raw_df = pd.read_excel(uploaded_file)

    # -----------------------------------------------------
    # PROCESS DATA
    # -----------------------------------------------------
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
    # LOAD FILE
    # -----------------------------------------------------
    if (
        uploaded_file is not None
        and not st.session_state["raw_data_loaded"]
    ):

        try:

            with st.spinner("Processing data..."):

                raw_df, group_a, rejected_data = (
                    load_and_process_file(uploaded_file)
                )

            # ---------------------------------------------
            # SAVE INTO SESSION
            # ---------------------------------------------
            st.session_state["raw_data"] = raw_df.copy()

            st.session_state["group_a_data"] = (
                group_a.copy()
            )

            st.session_state["rejected_data"] = (
                rejected_data.copy()
            )

            st.session_state["raw_data_loaded"] = True

            st.session_state["loaded_file_name"] = (
                uploaded_file.name
            )

            st.rerun()

        except Exception as e:

            st.session_state["raw_data_loaded"] = False

            st.error(
                f"Error while processing file: {str(e)}"
            )


    # -----------------------------------------------------
    # DATA HEALTH STATUS
    # -----------------------------------------------------
    if st.session_state["raw_data_loaded"]:

        group_a = st.session_state.get(
            "group_a_data"
        )

        rejected_data = st.session_state.get(
            "rejected_data"
        )

        if group_a is None:
            group_a = pd.DataFrame()

        if rejected_data is None:
            rejected_data = pd.DataFrame()


        total_count = (
            len(group_a)
            + len(rejected_data)
        )

        valid_count = len(group_a)

        excluded_count = len(rejected_data)


        st.success("✅ File Data Locked in Memory")


        # -------------------------------------------------
        # CURRENT FILE
        # -------------------------------------------------
        loaded_file_name = st.session_state.get(
            "loaded_file_name"
        )

        if loaded_file_name:

            st.caption(
                f"Current file: {loaded_file_name}"
            )


        # -------------------------------------------------
        # KPI
        # -------------------------------------------------
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

            keys_to_clear = [
                "raw_data",
                "group_a_data",
                "rejected_data",
                "raw_data_loaded",
                "loaded_file_name",
            ]

            for key in keys_to_clear:

                st.session_state.pop(
                    key,
                    None
                )

            st.cache_data.clear()

            st.rerun()


# =========================================================
# 6. MAIN PAGE CONTENT
# =========================================================
if st.session_state["raw_data_loaded"]:

    group_a = st.session_state.get(
        "group_a_data"
    )

    rejected_data = st.session_state.get(
        "rejected_data"
    )

    if group_a is None:
        group_a = pd.DataFrame()

    if rejected_data is None:
        rejected_data = pd.DataFrame()


    st.success(
        "✅ Data loaded successfully."
    )


    # -----------------------------------------------------
    # CURRENT FILE
    # -----------------------------------------------------
    loaded_file_name = st.session_state.get(
        "loaded_file_name"
    )

    if loaded_file_name:

        st.caption(
            f"Current Data Source: {loaded_file_name}"
        )


    # -----------------------------------------------------
    # KPI
    # -----------------------------------------------------
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


    # -----------------------------------------------------
    # DATA STATUS
    # -----------------------------------------------------
    if group_a.empty:

        st.warning(
            "⚠️ 檔案已讀取，但沒有符合 Group A "
            "條件的有效資料。"
        )

    else:

        st.info(
            "Please select a module from the "
            "navigation menu to continue analysis."
        )


else:

    st.info(
        "Awaiting data upload..."
    )
