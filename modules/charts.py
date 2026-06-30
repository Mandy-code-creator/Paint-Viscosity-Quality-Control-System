import streamlit as st
import pandas as pd


def render_data_health_kpi(
    total_count,
    valid_count,
    excluded_count,
    rejected_data=None
):
    """
    Hiển thị tình trạng dữ liệu trong sidebar.

    Parameters
    ----------
    total_count : int
        Tổng số dòng dữ liệu.
    valid_count : int
        Số dòng hợp lệ thuộc Group A.
    excluded_count : int
        Số dòng không thuộc Group A.
    rejected_data : pd.DataFrame
        Bảng dữ liệu bị loại khỏi phân tích dung môi.
    """

    # =========================================================
    # 1. DATA SAFETY
    # =========================================================
    if rejected_data is None:
        rejected_data = pd.DataFrame()

    if not isinstance(rejected_data, pd.DataFrame):
        rejected_data = pd.DataFrame()

    total_count = int(total_count or 0)
    valid_count = int(valid_count or 0)
    excluded_count = int(excluded_count or 0)

    valid_rate = (
        valid_count / total_count * 100
        if total_count > 0 else 0
    )

    # =========================================================
    # 2. KPI HEADER
    # =========================================================
    st.markdown("---")
    st.markdown("📊 **Data Health Status**")

    col1, col2 = st.columns(2)

    with col1:
        st.caption("Total Records")
        st.markdown(
            f"""
            <div style="
                font-size:28px;
                font-weight:700;
                color:#1F3855;
                line-height:1.1;
                margin-top:-5px;
            ">
                {total_count:,}
            </div>
            """,
            unsafe_allow_html=True
        )

    with col2:
        st.caption("Valid (Group A)")
        st.markdown(
            f"""
            <div style="
                font-size:28px;
                font-weight:700;
                color:#1F3855;
                line-height:1.1;
                margin-top:-5px;
            ">
                {valid_count:,}
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            f"""
            <div style="
                display:inline-block;
                margin-top:7px;
                padding:3px 8px;
                border-radius:12px;
                background-color:#DDF3E8;
                color:#14804A;
                font-size:12px;
                font-weight:600;
            ">
                ✓ {valid_rate:.1f}%
            </div>
            """,
            unsafe_allow_html=True
        )

    # =========================================================
    # 3. EXCLUDED DATA LOG
    # =========================================================
    if excluded_count > 0:

        with st.expander(
            f"⚠️ {excluded_count:,} records excluded from solvent analysis",
            expanded=False
        ):
            st.caption(
                "These records remain in the source file but do not meet "
                "the Group A solvent-adjustment conditions."
            )

            # -------------------------------------------------
            # 3.1 Reason Summary
            # Không gây lỗi nếu dữ liệu cũ chưa có Reject_Reason
            # -------------------------------------------------
            if "Reject_Reason" in rejected_data.columns:

                reason_summary = (
                    rejected_data["Reject_Reason"]
                    .fillna("未分類")
                    .astype(str)
                    .replace("", "未分類")
                    .value_counts()
                    .reset_index()
                )

                reason_summary.columns = [
                    "Excluded Reason",
                    "Records"
                ]

                st.caption("Exclusion Summary")

                st.dataframe(
                    reason_summary,
                    use_container_width=True,
                    hide_index=True,
                    height=min(250, 45 * (len(reason_summary) + 1))
                )

            else:
                st.warning(
                    "This file was loaded using the previous validation logic. "
                    "Please click 'Clear Data & Upload New File', then upload again."
                )

            # -------------------------------------------------
            # 3.2 Detailed Log
            # -------------------------------------------------
            log_columns = [
                "Coil_ID",
                "Paint_Code",
                "Vendor",
                "Resin",
                "Solvent_Type",
                "塗料重量",
                "添加重量",
                "黏度(秒)",
                "黏度(秒)_1",
                "Delta_V",
                "Reject_Reason"
            ]

            display_columns = [
                col for col in log_columns
                if col in rejected_data.columns
            ]

            if display_columns:
                st.caption("Detailed Data Log")

                st.dataframe(
                    rejected_data[display_columns],
                    use_container_width=True,
                    hide_index=True,
                    height=300
                )
            else:
                st.info("No detailed columns are available in the current data log.")

            # -------------------------------------------------
            # 3.3 Download Log
            # -------------------------------------------------
            if not rejected_data.empty:

                csv_data = rejected_data.to_csv(
                    index=False
                ).encode("utf-8-sig")

                st.download_button(
                    label="⬇️ Download Data Log",
                    data=csv_data,
                    file_name="excluded_solvent_analysis_log.csv",
                    mime="text/csv",
                    use_container_width=True
                )

    else:
        st.success("✅ All records meet Group A conditions.")
