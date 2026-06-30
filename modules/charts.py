import streamlit as st
import pandas as pd


def render_data_health_kpi(
    total_count,
    valid_count,
    excluded_count,
    rejected_data=None
):
    """
    Hiển thị Data Health Status trong sidebar.
    rejected_data được truyền vào để xem chi tiết các dòng
    không thuộc Group A.
    """

    valid_rate = (
        valid_count / total_count * 100
        if total_count > 0 else 0
    )

    st.markdown("---")
    st.markdown("📊 **Data Health Status**")

    col1, col2 = st.columns(2)

    with col1:
        st.caption("Total Records")
        st.markdown(
            f"""
            <div style="
                font-size: 28px;
                font-weight: 700;
                color: #1F3855;
                line-height: 1.1;
                margin-top: -6px;
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
                font-size: 28px;
                font-weight: 700;
                color: #1F3855;
                line-height: 1.1;
                margin-top: -6px;
            ">
                {valid_count:,}
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            f"""
            <div style="
                display: inline-block;
                margin-top: 8px;
                padding: 3px 8px;
                border-radius: 12px;
                background-color: #DDF3E8;
                color: #14804A;
                font-size: 12px;
                font-weight: 600;
            ">
                ↑ {valid_rate:.1f}%
            </div>
            """,
            unsafe_allow_html=True
        )

    # Không gọi là rejected nữa vì có thể chỉ là chưa thêm dung môi
    if excluded_count > 0:
        with st.expander(
            f"⚠️ {excluded_count:,} records excluded from solvent analysis",
            expanded=False
        ):
            st.caption(
                "These records remain in the source file but do not meet "
                "the Group A solvent-adjustment conditions."
            )

            if rejected_data is None or rejected_data.empty:
                st.info("No detailed exclusion log is available.")

            else:
                log_columns = [
                    'Coil_ID',
                    'Paint_Code',
                    'Vendor',
                    'Resin',
                    'Solvent_Type',
                    '塗料重量',
                    '添加重量',
                    '黏度(秒)',
                    '黏度(秒)_1',
                    'Delta_V',
                    'Reject_Reason'
                ]

                display_columns = [
                    col for col in log_columns
                    if col in rejected_data.columns
                ]

                if display_columns:
                    st.dataframe(
                        rejected_data[display_columns],
                        use_container_width=True,
                        hide_index=True,
                        height=300
                    )

                reason_summary = (
                    rejected_data['Reject_Reason']
                    .fillna('未分類')
                    .value_counts()
                    .reset_index()
                )

                reason_summary.columns = [
                    'Excluded Reason',
                    'Records'
                ]

                st.caption("Exclusion Summary")

                st.dataframe(
                    reason_summary,
                    use_container_width=True,
                    hide_index=True
                )

                csv_data = rejected_data.to_csv(
                    index=False
                ).encode('utf-8-sig')

                st.download_button(
                    label="⬇️ Download Data Log",
                    data=csv_data,
                    file_name="excluded_solvent_analysis_log.csv",
                    mime="text/csv",
                    use_container_width=True
                )

    else:
        st.success("✅ All records meet Group A conditions.")
