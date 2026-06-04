import streamlit as st
import plotly.graph_objects as go

def render_data_health_kpi(total_rows, valid_rows, rejected_rows):
    """
    Renders a compact Data Quality KPI card for the Streamlit Sidebar.
    Strictly uses English for UI components.
    """
    st.divider()
    st.markdown("### 📊 Data Health Status")
    
    health_pct = (valid_rows / total_rows * 100) if total_rows > 0 else 0
    
    # Display Streamlit Metrics
    col1, col2 = st.columns(2)
    col1.metric("Total Records", f"{total_rows:,}")
    col2.metric("Valid (Group A)", f"{valid_rows:,}", f"{health_pct:.1f}%", delta_color="normal")
    
    if rejected_rows > 0:
        st.error(f"⚠️ {rejected_rows:,} records rejected (See Data Log)")
    else:
        st.success("✅ 100% Data Compliance")
