import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Viscosity & SOP Report", page_icon="📊", layout="wide")
st.title("📊 Viscosity & SOP Analysis Dashboard")
st.markdown("Production-driven regression, dynamic recommendation engine, and diminishing return monitoring.")

# --- 2. DATA VALIDATION ---
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please upload your data file first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()
group_a['Solvent_Type'] = group_a['Solvent_Type'].astype(str)

# STEP 1: Data Normalization (Solvent Ratio & Viscosity Reduction)
group_a['Solvent_Ratio_Percent'] = (group_a['添加重量'] / group_a['塗料重量'].replace(0, 1)) * 100
group_a['Viscosity_Reduction'] = group_a['黏度(秒)'] - group_a['黏度(秒)_1']

# Calculate Historical Efficiency per batch (seconds dropped per 1% solvent)
group_a['Historical_Efficiency'] = group_a['Viscosity_Reduction'] / group_a['Solvent_Ratio_Percent'].replace(0, np.nan)

# --- 3. INTERACTIVE GLOBAL FILTERS ---
unique_resins = sorted(group_a['Resin'].unique())
unique_vendors = sorted(group_a['Vendor'].unique())
unique_solvents = sorted(group_a['Solvent_Type'].unique())

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    selected_resins = st.multiselect("Select Resin:", options=unique_resins, default=unique_resins)
with col_f2:
    selected_vendors = st.multiselect("Select Vendor:", options=unique_vendors, default=unique_vendors)
with col_f3:
    selected_solvents = st.multiselect("Select Solvent Type:", options=unique_solvents, default=unique_solvents)

filtered_df = group_a[
    (group_a['Resin'].isin(selected_resins)) &
    (group_a['Vendor'].isin(selected_vendors)) &
    (group_a['Solvent_Type'].isin(selected_solvents))
].copy()


# --- 4. MODULE 1 & 2: DYNAMIC RECOMMENDATION ENGINE & EFFICIENCY MONITOR ---
st.markdown("---")
st.subheader("💡 Dynamic Recommendation Engine & Efficiency Monitor")

# Filter combinations that strictly have >= 10 batches to ensure statistical reliability
valid_groups = group_a.groupby(['Resin', 'Vendor', 'Solvent_Type']).filter(lambda x: x['塗料批號'].nunique() >= 10)
if valid_groups.empty:
    st.info("No groups found with 10+ historical batches to run the recommendation engine.")
else:
    # Dropdowns for specific batch execution
    col_e1, col_e2, col_e3 = st.columns(3)
    with col_e1:
        engine_resin = st.selectbox("Execution Resin:", valid_groups['Resin'].unique())
    with col_e2:
        engine_vendor = st.selectbox("Execution Vendor:", valid_groups[valid_groups['Resin'] == engine_resin]['Vendor'].unique())
    with col_e3:
        engine_solvent = st.selectbox("Execution Solvent Type:", valid_groups[(valid_groups['Resin'] == engine_resin) & (valid_groups['Vendor'] == engine_vendor)]['Solvent_Type'].unique())

    # Get baseline historical metrics for the selected group
    group_data = valid_groups[
        (valid_groups['Resin'] == engine_resin) & 
        (group_data_vendor := valid_groups['Vendor'] == engine_vendor) & 
        (valid_groups['Solvent_Type'] == engine_solvent)
    ]
    
    # STEP 3: Establish baseline efficiency curve reference
    baseline_efficiency = group_data['Historical_Efficiency'].median()
    max_safe_ratio = group_data['Solvent_Ratio_Percent'].quantile(0.95)
    viscosity_floor = group_data['黏度(秒)_1'].min()

    # Operator Live Inputs
    st.markdown("#### **Operator Input Panel**")
    col_i1, col_i2, col_i3, col_i4 = st.columns(4)
    with col_i1:
        paint_weight = st.number_input("Paint Weight (kg):", min_value=1.0, value=120.0, step=10.0)
    with col_i2:
        current_visc = st.number_input("Current Viscosity (s):", min_value=1.0, value=58.0, step=1.0)
    with col_i3:
        target_visc = st.number_input("Target Viscosity (s):", min_value=1.0, value=50.0, step=1.0)
    with col_i4:
        st.metric(label="Target Reduction (Delta V)", value=f"{current_visc - target_visc:.1f} s")

    # STEP 5: Recommendation Engine Calculations
    delta_v_target = current_visc - target_visc
    
    if delta_v_target <= 0:
        st.success("✅ Target viscosity is already achieved or higher than current viscosity. No solvent needed.")
    elif target_visc < viscosity_floor:
        st.error(f"❌ Critical Warning: Target viscosity ({target_visc}s) is below the historical Viscosity Floor ({viscosity_floor:.1f}s) for this system. Production cannot proceed safely.")
    else:
        # Calculate expected ratio using baseline efficiency
        predicted_ratio_needed = delta_v_target / baseline_efficiency
        recommended_solvent_kg = (paint_weight * predicted_ratio_needed) / 100

        # STEP 4: Diminishing Return Zone Verification
        # Evaluate how far the predicted ratio goes against historical bounds
        yellow_threshold_ratio = max_safe_ratio * 0.75
        
        st.markdown("#### **System Output Recommendation**")
        
        if predicted_ratio_needed <= yellow_threshold_ratio:
            # Green Zone: Normal High-Efficiency Zone
            st.success(f"**Recommended Solvent Weight:** {recommended_solvent_kg:.2f} kg")
            st.markdown(f"ℹ️ **Status:** `Optimal Efficiency Zone`. Expected Solvent Ratio: **{predicted_ratio_needed:.2f}%** (Within safe historical baseline).")
            
        elif predicted_ratio_needed <= max_safe_ratio:
            # Yellow Zone: Diminishing Return Zone (Efficiency dropped to ~50% of peak capability)
            st.warning(f"⚠️ **Recommended Solvent Weight:** {recommended_solvent_kg:.2f} kg")
            st.markdown(f"⚠️ **Status:** `Diminishing Return Zone (Yellow Alert)`. Expected Solvent Ratio will reach **{predicted_ratio_needed:.2f}%**. Dilution efficiency is dropping; monitor closely.")
            
        else:
            # Red Zone: Critical Diminishing Return / Saturation Overload (<30% expected efficiency)
            st.error(f"🚨 **Critical Alert: Recommended Solvent Weight Cap:** {recommended_solvent_kg:.2f} kg")
            st.markdown(f"🚨 **Status:** `Critical Diminishing Return Zone (Red Alert)`. Expected Solvent Ratio: **{predicted_ratio_needed:.2f}%** exceeds the safe threshold (**{max_safe_ratio:.2f}%**). Adding more solvent will damage film properties without dropping viscosity.")


# --- 5. CHART 2: HISTORICAL SOP MATRIX REFERENCE ---
st.markdown("---")
st.subheader("📚 SOP Reference Matrix (Only Groups with 10+ Batches)")

# Build static matrix summary for reference
agg_funcs = {
    'Batches': pd.NamedAgg(column='塗料批號', aggfunc='nunique'),
    'Total Paint (kg)': pd.NamedAgg(column='塗料重量', aggfunc='sum'),
    'Total Solvent (kg)': pd.NamedAgg(column='添加重量', aggfunc='sum'),
    'Avg Initial V (s)': pd.NamedAgg(column='黏度(秒)', aggfunc='mean'),
    'Avg Final V (s)': pd.NamedAgg(column='黏度(秒)_1', aggfunc='mean'),
    'Viscosity Floor (s) ⚠️': pd.NamedAgg(column='黏度(秒)_1', aggfunc='min'),
    'Baseline Efficiency (s/%)': pd.NamedAgg(column='Historical_Efficiency', aggfunc='median'),
    'Max Safe Solvent Limit %': pd.NamedAgg(column='Solvent_Ratio_Percent', aggfunc=lambda x: x.quantile(0.95))
}

summary_matrix = group_a.groupby(['Resin','Vendor','Solvent_Type']).agg(**agg_funcs).reset_index()
summary_matrix = summary_matrix[summary_matrix['Batches'] >= 10].reset_index(drop=True)

st.dataframe(
    summary_matrix,
    column_config={
        "Total Paint (kg)": st.column_config.NumberColumn(format="%d"),
        "Total Solvent (kg)": st.column_config.NumberColumn(format="%d"),
        "Avg Initial V (s)": st.column_config.NumberColumn(format="%.1f"),
        "Avg Final V (s)": st.column_config.NumberColumn(format="%.1f"),
        "Viscosity Floor (s) ⚠️": st.column_config.NumberColumn(format="%.1f", help="Absolute lowest recorded viscosity in history."),
        "Baseline Efficiency (s/%)": st.column_config.NumberColumn(format="%.2f", help="Median viscosity seconds dropped per 1% of solvent added."),
        "Max Safe Solvent Limit %": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=30)
    },
    use_container_width=True
)


# --- 6. CHART 3: MULTI-GROUP COMPARATIVE REGRESSION VIZ ---
st.markdown("---")
st.subheader("📈 Visual Distribution: Solvent Ratio vs. Viscosity")

fig_regression = px.scatter(
    filtered_df,
    x='Solvent_Ratio_Percent',
    y='黏度(秒)',
    color='Solvent_Type',
    symbol='Resin',
    facet_col='Vendor',
    trendline='ols',
    labels={'Solvent_Ratio_Percent': 'Solvent Added (%)', '黏度(秒)': 'Viscosity (s)'},
    title="Historical Scatter Distribution Analysis"
)
fig_regression.update_layout(plot_bgcolor='white', font=dict(size=12))
st.plotly_chart(fig_regression, use_container_width=True)
