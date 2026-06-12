import streamlit as st
import pandas as pd
import plotly.express as px

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Executive Summary", page_icon="📊", layout="wide")

st.title("📊 Executive Summary")
st.markdown("High-level overview of coil-level operational performance and solvent utilization hierarchy.")
st.markdown("---")

# --- 1. STATE CHECK & SAFE DATA LOADING ---
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please upload your data file on the main App page first.")
    st.stop()

# Safe retrieval: Use .get() with an empty DataFrame fallback to prevent KeyErrors
group_a = st.session_state.get('group_a_data', pd.DataFrame()).copy()
rejected_data = st.session_state.get('rejected_data', pd.DataFrame()).copy()

if group_a.empty:
    st.error("❌ Data source is empty. Please check your uploaded files.")
    st.stop()

# Ensure critical columns exist and calculate global Sensitivity
if all(col in group_a.columns for col in ['添加重量', '塗料重量', '黏度(秒)', '黏度(秒)_1']):
    group_a['Solvent_Ratio_Percent'] = (group_a['添加重量'] / group_a['塗料重量']) * 100
    group_a['Delta_V'] = group_a['黏度(秒)'] - group_a['黏度(秒)_1']
    # Avoid division by zero
    group_a['Sensitivity'] = group_a['Delta_V'] / group_a['Solvent_Ratio_Percent'].replace(0, 1)
else:
    group_a['Sensitivity'] = 0
    group_a['Solvent_Ratio_Percent'] = 0

# --- 2. KPI METRICS (COIL-LEVEL) ---
st.subheader("💡 Key Performance Indicators")
col1, col2, col3, col4 = st.columns(4)

total_coils = len(group_a)
total_paint = group_a['塗料重量'].sum() if '塗料重量' in group_a.columns else 0
avg_solvent_ratio = group_a['Solvent_Ratio_Percent'].mean()
rejected_count = len(rejected_data)

with col1:
    st.metric(label="Total Valid Coils", value=f"{total_coils:,}")
with col2:
    st.metric(label="Total Paint Used", value=f"{total_paint:,.1f} kg")
with col3:
    st.metric(label="Avg Solvent Ratio", value=f"{avg_solvent_ratio:.2f} %")
with col4:
    st.metric(label="Data Errors (Rejected)", value=f"{rejected_count} rows")

st.markdown("---")

# --- 3. VENDOR-RESIN HIERARCHY (MIND MAP VIEW) ---
st.subheader("🌳 Solvent Usage Mind Map")
st.markdown("Hierarchical view of Paint Volume and Solvent Sensitivity. **Click on any section to zoom in.** Red areas indicate high solvent sensitivity (requires operational caution).")

# Filter controls for the Mind Map
if 'Vendor' not in group_a.columns:
    group_a['Vendor'] = 'Unknown'
if 'Solvent_Type' not in group_a.columns:
    group_a['Solvent_Type'] = 'Unknown'

vendors_list = group_a['Vendor'].dropna().unique().tolist()
selected_vendor = st.selectbox("🏢 Central Vendor Selection:", vendors_list)

tree_data = group_a[group_a['Vendor'] == selected_vendor].copy()

# Fill NaNs to prevent rendering gaps in Plotly Sunburst
tree_data['Solvent_Type'] = tree_data['Solvent_Type'].fillna('Unspecified')
tree_data['Resin'] = tree_data['Resin'].fillna('Unspecified')

if not tree_data.empty:
    # Grouping data for the hierarchy: Vendor -> Resin -> Solvent
    tree_summary = tree_data.groupby(['Vendor', 'Resin', 'Solvent_Type']).agg(
        Total_Paint_Weight=('塗料重量', 'sum'),
        Total_Solvent_Weight=('添加重量', 'sum'),
        Avg_Sensitivity=('Sensitivity', 'mean')
    ).reset_index()

    # Filter out negative or zero sensitivity for proper color mapping
    tree_summary = tree_summary[tree_summary['Avg_Sensitivity'] > 0]

    if not tree_summary.empty:
        # Create the interactive Sunburst Chart
        fig_mindmap = px.sunburst(
            tree_summary,
            path=['Vendor', 'Resin', 'Solvent_Type'],
            values='Total_Paint_Weight', 
            color='Avg_Sensitivity', 
            color_continuous_scale='RdYlGn_r', # Red = High Sensitivity (Alert), Green = Low
            hover_data={'Total_Solvent_Weight': ':,.1f', 'Avg_Sensitivity': ':.2f'},
            title=f"Hierarchical Flow - {selected_vendor}"
        )
        
        # Custom hover template
        fig_mindmap.update_traces(
            hovertemplate='<b>%{label}</b><br>' +
                          'Total Paint: %{value:,.0f} kg<br>' +
                          'Solvent Added: %{customdata[0]:,.0f} kg<br>' +
                          'Sensitivity: <b>%{color:.2f} s/%</b><extra></extra>'
        )

        fig_mindmap.update_layout(
            height=650,
            margin=dict(t=40, l=0, r=0, b=0),
            coloraxis_colorbar=dict(title="Sensitivity<br>(s / 1%)")
        )

        st.plotly_chart(fig_mindmap, use_container_width=True)
        
        # --- 4. HIGH SENSITIVITY ALERTS ---
        st.write("🚩 **Top Sensitivity Alerts (Coil Combinations):**")
        alerts = tree_summary.sort_values(by='Avg_Sensitivity', ascending=False).head(3)
        
        if not alerts.empty:
            alert_cols = st.columns(len(alerts))
            for idx, (_, row) in enumerate(alerts.iterrows()):
                with alert_cols[idx]:
                    st.error(f"""
                    **{row['Resin']}** + **{row['Solvent_Type']}**
                    * Total Paint: {row['Total_Paint_Weight']:,.0f} kg
                    * Sensitivity: **{row['Avg_Sensitivity']:.2f} s/%**
                    """)
    else:
        st.info("No positive sensitivity data available to render the Mind Map for this vendor.")
else:
    st.warning("No data available for the selected vendor.")
