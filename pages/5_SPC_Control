import streamlit as st
from modules.spc_engine import generate_i_chart

st.set_page_config(page_title="SPC Control", page_icon="📈", layout="wide")

st.title("📈 Statistical Process Control (SPC)")
st.markdown("Monitor production stability using Sigma limits and Mill Range parameters at the **Coil Level**.")

# Check if data is loaded
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please go to the Main App page and upload your data file first.")
    st.stop()

group_a = st.session_state['group_a_data']

# Sidebar Filters specific to this page
st.sidebar.header("🔍 SPC Filters")
selected_vendor = st.sidebar.selectbox("Filter by Vendor:", ["All"] + sorted(group_a['Vendor'].unique().tolist()))
selected_resin = st.sidebar.selectbox("Filter by Resin:", ["All"] + sorted(group_a['Resin'].unique().tolist()))

# Apply filters
filtered_df = group_a.copy()
if selected_vendor != "All":
    filtered_df = filtered_df[filtered_df['Vendor'] == selected_vendor]
if selected_resin != "All":
    filtered_df = filtered_df[filtered_df['Resin'] == selected_resin]

if filtered_df.empty:
    st.error("No valid Group A data available for the selected filters.")
    st.stop()

# Render Charts
st.markdown("### Viscosity Stability (Before vs After)")
col1, col2 = st.columns(2)

with col1:
    fig_before = generate_i_chart(filtered_df, '黏度(秒)', "Initial Viscosity I-Chart")
    st.plotly_chart(fig_before, use_container_width=True)

with col2:
    fig_after = generate_i_chart(filtered_df, '黏度(秒)_1', "Final Viscosity I-Chart")
    st.plotly_chart(fig_after, use_container_width=True)

st.divider()

st.markdown("### Solvent Addition Consistency")
fig_ratio = generate_i_chart(filtered_df, 'Solvent_Ratio', "Solvent Ratio I-Chart")
st.plotly_chart(fig_ratio, use_container_width=True)
