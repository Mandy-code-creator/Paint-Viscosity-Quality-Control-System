import streamlit as st
import plotly.express as px
import pandas as pd

# Set page configuration
st.set_page_config(page_title="Viscosity Analysis", page_icon="🔬", layout="wide")

st.title("🔬 Viscosity Reduction Analysis (Per Resin)")
st.markdown("Detailed view: Each chart shows how different solvents perform on a specific resin type.")

# 1. Global State Check
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please go to the Main App page and upload your data file first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()

# 2. Sidebar Filters
st.sidebar.header("🔍 Analysis Filters")
vendors = sorted([v for v in group_a['Vendor'].unique() if v != 'Unknown'])
selected_vendor = st.sidebar.selectbox("Vendor", ["All"] + vendors)

# Apply Vendor filter
df_v = group_a[group_a['Vendor'] == selected_vendor] if selected_vendor != "All" else group_a

# 3. Aggregating Data
summary_df = df_v.groupby(['Resin', 'Solvent_Type'])['Viscosity_Sensitivity'].agg(['mean', 'std']).reset_index()

# 4. Generating Charts Per Resin
resins = sorted(summary_df['Resin'].unique())

for resin in resins:
    st.markdown(f"---")
    st.markdown(f"### Resin: {resin}")
    
    # Filter data for the current resin
    resin_data = summary_df[summary_df['Resin'] == resin]
    
    # Create Bar Chart
    fig = px.bar(
        resin_data,
        x='Solvent_Type',
        y='mean',
        error_y='std', # Stability range
        title=f"Sensitivity Profile for {resin} (How much viscosity drops per 1% solvent)",
        labels={'mean': 'Avg Sensitivity (sec/1%)', 'Solvent_Type': 'Solvent Type'},
        color='mean',
        color_continuous_scale='Blues'
    )
    
    # Formatting for clarity
    fig.update_yaxes(
        showgrid=True, 
        gridwidth=1, 
        gridcolor='black', 
        showline=True, 
        linecolor='black'
    )
    fig.update_layout(height=450, margin=dict(t=50, b=50))
    
    st.plotly_chart(fig, use_container_width=True)
