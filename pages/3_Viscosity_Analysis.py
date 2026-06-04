import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(page_title="Viscosity Analysis", page_icon="🔬", layout="wide")

st.title("🔬 Viscosity Reduction Analysis")
st.markdown("Analyze how viscosity changes before and after solvent addition across different resin types and features.")

# 1. Global State Check
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please go to the Main App page and upload your data file first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()

# 2. Sidebar Filters
st.sidebar.header("🔍 Analysis Filters")
selected_vendor = st.sidebar.selectbox("Vendor", ["All"] + sorted(group_a['Vendor'].unique().tolist()))
selected_resin = st.sidebar.selectbox("Resin Type", ["All"] + sorted(group_a['Resin'].unique().tolist()))

# Apply Filters
filtered_df = group_a.copy()
if selected_vendor != "All":
    filtered_df = filtered_df[filtered_df['Vendor'] == selected_vendor]
if selected_resin != "All":
    filtered_df = filtered_df[filtered_df['Resin'] == selected_resin]

if filtered_df.empty:
    st.error("No valid data available for the selected filters.")
    st.stop()

# 3. Chart: Scatter Plot (Before vs After)
st.markdown("### 1. Viscosity Shift (Before vs After)")
# Create a scatter plot with a reference line (y=x)
fig_scatter = px.scatter(
    filtered_df, 
    x="黏度(秒)", 
    y="黏度(秒)_1", 
    color="Resin",
    hover_data=["Paint_Code", "Delta_V", "Solvent_Ratio"],
    title="Initial vs Final Viscosity (Points below the line indicate reduction)",
    labels={"黏度(秒)": "Initial Viscosity (sec)", "黏度(秒)_1": "Final Viscosity (sec)"}
)

# Add y=x line (No reduction line)
max_val = max(filtered_df['黏度(秒)'].max(), filtered_df['黏度(秒)_1'].max())
fig_scatter.add_shape(
    type="line", line=dict(dash="dash", color="red"),
    x0=0, y0=0, x1=max_val, y1=max_val
)
st.plotly_chart(fig_scatter, use_container_width=True)

st.divider()

# 4. Row 2: Distribution & Sensitivity
col1, col2 = st.columns(2)

with col1:
    st.markdown("### 2. Viscosity Reduction (ΔV) Distribution")
    fig_hist = px.histogram(
        filtered_df, 
        x="Delta_V", 
        color="Resin",
        nbins=20,
        title="Distribution of ΔV (Seconds Dropped)",
        labels={"Delta_V": "Viscosity Drop (sec)"}
    )
    st.plotly_chart(fig_hist, use_container_width=True)

with col2:
    st.markdown("### 3. Sensitivity by Resin Type")
    # Box plot to show how sensitive different resins are to solvent
    fig_box = px.box(
        filtered_df, 
        x="Resin", 
        y="Viscosity_Sensitivity",
        color="Resin",
        title="Viscosity Reduction per 1% Solvent Added",
        labels={"Viscosity_Sensitivity": "Sensitivity (sec drop per 1% solvent)"}
    )
    st.plotly_chart(fig_box, use_container_width=True)
