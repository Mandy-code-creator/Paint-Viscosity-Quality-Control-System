import streamlit as st
import plotly.express as px
import pandas as pd

# ==========================================
# SECTION 0: PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="Viscosity Analysis Report", page_icon="🔬", layout="wide")

st.title("🔬 Viscosity Analysis Report")
st.markdown("Detailed breakdown of solvent sensitivity per resin type. Each chart represents a specific resin's reaction to different solvents.")

# ==========================================
# SECTION 1: STATE CHECK & DATA LOADING
# ==========================================
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please upload your data file first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()

# Ensure Solvent_Type is string to prevent chart spreading
group_a['Solvent_Type'] = group_a['Solvent_Type'].astype(str)

# Map standard column names
visc_before = '黏度(秒)'
visc_after = '黏度(秒)_1'
paint_weight = '塗料重量'
solvent_weight = '添加重量'

# ==========================================
# SECTION 2: DATA CLEANING & CALCULATION
# ==========================================
# Clean data to ensure valid calculations
if all(col in group_a.columns for col in [visc_before, visc_after, paint_weight, solvent_weight]):
    # Drop rows with null viscosity
    df_clean = group_a.dropna(subset=[visc_before, visc_after]).copy()
    
    # Cast critical columns to numeric
    for col in [visc_before, visc_after, paint_weight, solvent_weight]:
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
    df_clean = df_clean.dropna(subset=[visc_before, visc_after, paint_weight, solvent_weight])

    # Filter out invalid records (e.g., zero weights, no viscosity change)
    df_clean = df_clean[
        (df_clean[paint_weight] > 0) & 
        (df_clean[solvent_weight] > 0) & 
        (df_clean[visc_before] != df_clean[visc_after])
    ]

    # Recalculate sensitivity (Original logic: s/1% solvent)
    df_clean['Solvent_Ratio_Percent'] = (df_clean[solvent_weight] / df_clean[paint_weight]) * 100
    df_clean['Sensitivity'] = (df_clean[visc_before] - df_clean[visc_after]) / df_clean['Solvent_Ratio_Percent']
    
    working_df = df_clean.copy()
else:
    # Fallback to current session state Sensitivity if columns missing
    st.warning("Could not perform fresh data cleaning. Using existing 'Viscosity_Sensitivity' column.")
    working_df = group_a.copy()
    if 'Viscosity_Sensitivity' in working_df.columns:
        working_df['Sensitivity'] = working_df['Viscosity_Sensitivity']
    else:
        st.error("Critical sensitivity data column missing.")
        st.stop()

# ==========================================
# SECTION 3: GROUPING LOGIC & COLOR MAP
# ==========================================
# Perform grouping: Calculate Mean and Std Dev of Sensitivity
summary_df = working_df.groupby(['Resin', 'Solvent_Type'])['Sensitivity'].agg(['mean', 'std']).reset_index()
resins = sorted(summary_df['Resin'].unique())

# Define fixed color map for consistency across charts
# Using a professional, high-contrast palette
all_solvents = sorted(working_df['Solvent_Type'].unique())
color_map = {solvent: px.colors.qualitative.Prism[i % len(px.colors.qualitative.Prism)] 
             for i, solvent in enumerate(all_solvents)}

# ==========================================
# SECTION 4: DISPLAY REPORT (2-COLUMN GRID)
# ==========================================
st.markdown("---")

# Render report in a 2-column grid format (restoring original design)
for i in range(0, len(resins), 2):
    cols = st.columns(2)
    for j in range(2):
        if i + j < len(resins):
            resin = resins[i + j]
            with cols[j]:
                st.markdown(f"#### Resin Type: {resin}")
                resin_data = summary_df[summary_df['Resin'] == resin].copy()
                
                # --- A. CREATE BAR CHART ---
                fig_bar = px.bar(
                    resin_data,
                    x='Solvent_Type',
                    y='mean',
                    error_y='std',
                    labels={'mean': 'Sensitivity (s/1% solvent)', 'Solvent_Type': 'Solvent'},
                    color='Solvent_Type',
                    color_discrete_map=color_map,
                    title=f"Sensitivity Profile for {resin}"
                )
                
                # --- B. CONFIGURE PROFESSIONAL LAYOUT & TEXT ---
                fig_bar.update_layout(
                    plot_bgcolor='white', 
                    height=300, 
                    # Fix font to solid black, no shadows/halos, Arial for clean look
                    font=dict(size=12, color="black", family="Arial, sans-serif"),
                    margin=dict(l=40, r=40, t=40, b=30), 
                    showlegend=False
                )
                
                # Ensure category X-axis and clear line colors
                fig_bar.update_xaxes(type='category', showline=True, linecolor='black', linewidth=1)
                fig_bar.update_yaxes(showgrid=True, gridcolor='lightgray', linecolor='black', linewidth=1)
                
                # Display the chart
                st.plotly_chart(fig_bar, use_container_width=True)
                
                # --- C. DATA TABLE ---
                # Summary table for reference/copy-pasting
                st.dataframe(
                    resin_data.rename(columns={'mean': 'Mean Sensitivity', 'std': 'Std Dev'}),
                    use_container_width=True,
                    height=150
                )
