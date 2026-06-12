import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# ==========================================
# SECTION 0: PAGE CONFIGURATION & CSS FIX
# ==========================================
st.set_page_config(page_title="Solvent Intelligence Dashboard", page_icon="🧠", layout="wide")

# Inject CSS to completely remove the blurry text-shadow from Plotly Sankey nodes
st.markdown("""
<style>
g.sankey-node text {
    text-shadow: none !important;
}
</style>
""", unsafe_allow_html=True)

st.title("🧠 Solvent Adjustment Intelligence Dashboard")
st.markdown("Decision Support System (DSS) based on historical data. Standardized solvent usage ratio unit: **g solvent / kg paint / 1 viscosity second drop**.")
st.markdown("---")


# ==========================================
# SECTION 1: STATE CHECK & DATA LOADING
# ==========================================
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please upload your data file first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()
group_a['Solvent_Type'] = group_a['Solvent_Type'].astype(str)

# Ensure Vendor column exists gracefully
if 'Vendor' not in group_a.columns:
    group_a['Vendor'] = 'Unknown'


# ==========================================
# SECTION 2: PREPROCESSING & DATA CLEANING
# ==========================================
visc_before = '黏度(秒)'      # Initial Viscosity
visc_after = '黏度(秒)_1'    # Final Viscosity
paint_weight = '塗料重量'     # Paint Weight (kg)
solvent_weight = '添加重量'   # Solvent Weight (kg)

if all(col in group_a.columns for col in [visc_before, visc_after, paint_weight, solvent_weight]):
    # Drop empty rows for critical columns
    df = group_a.dropna(subset=[visc_before, visc_after, paint_weight, solvent_weight]).copy()
    
    # Cast to numeric types
    for col in [visc_before, visc_after, paint_weight, solvent_weight]:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=[visc_before, visc_after, paint_weight, solvent_weight])
    
    # Calculate Viscosity Reduction
    df['Viscosity_Reduction'] = df[visc_before] - df[visc_after]
    
    # DATA CLEANING: Paint > 0, Solvent > 0, and Reduction > 0
    df = df[
        (df[paint_weight] > 0) & 
        (df[solvent_weight] > 0) & 
        (df['Viscosity_Reduction'] > 0)
    ]
    
    # CALCULATE STANDARDIZED REFERENCE VALUE (g/kg/s)
    # Formula: (Solvent(kg) * 1000) / (Paint(kg) * Reduction(s))
    df['Reference_Value'] = (df[solvent_weight] * 1000) / (df[paint_weight] * df['Viscosity_Reduction'])
    
    # CALCULATE SOLVENT RATIO (g/kg)
    df['Solvent_Ratio_g_kg'] = (df[solvent_weight] * 1000) / df[paint_weight]

else:
    st.error("⚠️ Missing required data columns (Viscosity, Paint Weight, Solvent Weight).")
    st.stop()


# ==========================================
# SECTION 3: MASTER UI LAYOUT DEFINITION
# ==========================================
col_left, col_right = st.columns([6, 4], gap="large")


# ==========================================
# SECTION 4: LEFT COLUMN - CASCADING FILTERS
# ==========================================
with col_left:
    st.subheader("🌊 Material & Process Flow (Sankey)")
    
    c_f1, c_f2, c_f3 = st.columns(3)
    with c_f1:
        selected_vendor = st.selectbox("1. Supplier (Vendor)", options=['All'] + list(df['Vendor'].unique()))
    with c_f2:
        resins_available = df[df['Vendor'] == selected_vendor]['Resin'].unique() if selected_vendor != 'All' else df['Resin'].unique()
        selected_resin = st.selectbox("2. Resin Type", options=['All'] + list(resins_available))
    with c_f3:
        mask_solvent = pd.Series(True, index=df.index)
        if selected_vendor != 'All':
            mask_solvent &= (df['Vendor'] == selected_vendor)
        if selected_resin != 'All':
            mask_solvent &= (df['Resin'] == selected_resin)
            
        solvents_available = df[mask_solvent]['Solvent_Type'].unique()
        selected_solvent = st.selectbox("3. Solvent Type", options=['All'] + list(solvents_available))

    # --- FILTER DATA BASED ON DROPDOWN SELECTIONS ---
    filtered_df = df.copy()
    if selected_vendor != 'All': 
        filtered_df = filtered_df[filtered_df['Vendor'] == selected_vendor]
    if selected_resin != 'All': 
        filtered_df = filtered_df[filtered_df['Resin'] == selected_resin]
    if selected_solvent != 'All': 
        filtered_df = filtered_df[filtered_df['Solvent_Type'] == selected_solvent]


# ==========================================
# ==========================================
# SECTION 5: LEFT COLUMN - MODERN STYLED SANKEY (DATA ON FLOW)
# ==========================================
    if filtered_df.empty:
        st.info("👈 Please select a valid combination on the left.")
    else:
        sankey_df = filtered_df.copy()
        
        # Extract unique entities
        vendors = list(sankey_df['Vendor'].unique())
        resins = list(sankey_df['Resin'].unique())
        solvents = list(sankey_df['Solvent_Type'].unique())
        
        # --- NEW: CALCULATE DATA TO DISPLAY DIRECTLY ON NODES ---
        # Count batches and calculate total solvent weights for rich labels
        v_counts = sankey_df['Vendor'].value_counts()
        r_counts = sankey_df['Resin'].value_counts()
        s_counts = sankey_df['Solvent_Type'].value_counts()
        s_weights = sankey_df.groupby('Solvent_Type')[solvent_weight].sum()
        
        # Create rich labels combining Name + Data (Batches / Weights)
        node_labels = (
            [f"🏭 {v} ({v_counts.get(v, 0)} batches)" for v in vendors] +
            [f"🧪 {r} ({r_counts.get(r, 0)} batches)" for r in resins] +
            [f"💧 {s} ({s_weights.get(s, 0):.1f} kg)" for s in solvents]
        )
        
        vendor_idx = {v: i for i, v in enumerate(vendors)}
        resin_idx = {r: i + len(vendors) for i, r in enumerate(resins)}
        solvent_idx = {s: i + len(vendors) + len(resins) for i, s in enumerate(solvents)}
        
        source, target, value, link_colors = [], [], [], []
        
        # Group 1: Vendor -> Resin
        v_r_group = sankey_df.groupby(['Vendor', 'Resin']).size().reset_index(name='count')
        for _, row in v_r_group.iterrows():
            source.append(vendor_idx[row['Vendor']])
            target.append(resin_idx[row['Resin']])
            value.append(row['count'])
            link_colors.append("rgba(135, 186, 222, 0.4)") # Softer modern blue, slightly higher opacity for contrast

        # Group 2: Resin -> Solvent
        r_s_group = sankey_df.groupby(['Resin', 'Solvent_Type']).size().reset_index(name='count')
        for _, row in r_s_group.iterrows():
            source.append(resin_idx[row['Resin']])
            target.append(solvent_idx[row['Solvent_Type']])
            value.append(row['count'])
            link_colors.append("rgba(252, 203, 163, 0.4)") # Softer modern orange

        # Build Sankey with Modern Vibe Settings
        fig_sankey = go.Figure(data=[go.Sankey(
            node=dict(
                pad=40, 
                thickness=20, # Slightly thicker to mimic the card feel
                line=dict(color="#34495E", width=2), # Dark border to mimic the left-edge styling
                label=node_labels,
                color="#FFFFFF" # White nodes to mimic the inner card
            ),
            link=dict(
                source=source, 
                target=target, 
                value=value, 
                color=link_colors
            )
        )])
        
        # Dynamic height to maintain aesthetics
        total_nodes = len(node_labels)
        dynamic_height = max(350, min(700, total_nodes * 50))
        
        fig_sankey.update_layout(
            height=dynamic_height, 
            font=dict(size=14, color="#2C3E50", family="Segoe UI, Arial, sans-serif"), # Modern font
            margin=dict(l=10, r=180, t=30, b=20), 
            # Apply the light gray/blueish background from your image
            plot_bgcolor='#F4F7F9',
            paper_bgcolor='#F4F7F9'
        )
        st.plotly_chart(fig_sankey, use_container_width=True)


# ==========================================
# SECTION 6: RIGHT COLUMN - DATA AGGREGATION
# ==========================================
with col_right:
    if filtered_df.empty or len(filtered_df) < 2:
        st.info("👈 Please select a valid combination on the left (Requires at least 2 batches to analyze).")
    else:
        sample_size = len(filtered_df)
        avg_paint_w = filtered_df[paint_weight].mean()
        avg_init_v = filtered_df[visc_before].mean()
        avg_fin_v = filtered_df[visc_after].mean()
        avg_red = filtered_df['Viscosity_Reduction'].mean()
        avg_solv_add = filtered_df[solvent_weight].mean()
        avg_solv_ratio = filtered_df['Solvent_Ratio_g_kg'].mean()
        
        ref_mean = filtered_df['Reference_Value'].mean()
        ref_median = filtered_df['Reference_Value'].median()
        ref_std = filtered_df['Reference_Value'].std()


# ==========================================
# SECTION 7: RIGHT COLUMN - REFERENCE TABLES
# ==========================================
        st.subheader("📊 Historical Reference Table")
        metrics_df = pd.DataFrame({
            "Metric": [
                "Sample Size (Batches)", 
                "Avg Paint Weight (kg)", 
                "Avg Initial Viscosity (s)", 
                "Avg Final Viscosity (s)", 
                "Avg Viscosity Reduction (s)", 
                "Avg Solvent Added (kg)",
                "Avg Solvent Ratio (g/kg paint)" 
            ],
            "Value": [
                f"{sample_size}", 
                f"{avg_paint_w:.1f}",
                f"{avg_init_v:.1f}", 
                f"{avg_fin_v:.1f}", 
                f"{avg_red:.1f}", 
                f"{avg_solv_add:.2f}",
                f"{avg_solv_ratio:.2f}" 
            ]
        })
        st.dataframe(metrics_df, hide_index=True, use_container_width=True)

        st.markdown(f"""
        <div style="background-color: #f0f8ff; padding: 20px; border-radius: 10px; border-left: 5px solid #0066cc; margin-bottom: 20px;">
            <h4 style="margin-top: 0; color: #0066cc;">⭐ Reference Value</h4>
            <p style="font-size: 14px; margin-bottom: 5px;">Combination: <b>{selected_vendor} → {selected_resin} → {selected_solvent}</b></p>
            <h1 style="margin: 0; color: #333;">{ref_mean:.2f} <span style="font-size: 18px; color: #666;">g/kg/s</span></h1>
            <p style="font-size: 13px; color: #666; margin-top: 5px;"><i>(Median: {ref_median:.2f} | Std Dev: {ref_std:.2f})</i></p>
            <p style="margin-bottom: 0;"><b>Meaning:</b> On average, add {ref_mean:.2f} grams of solvent per 1 kg of paint to reduce viscosity by 1 second.</p>
        </div>
        """, unsafe_allow_html=True)


# ==========================================
# SECTION 8: RIGHT COLUMN - 2-WAY PREDICTION TOOL
# ==========================================
        with st.expander("🛠️ PRODUCTION CALCULATORS", expanded=True):
            tab1, tab2 = st.tabs(["🎯 Find Solvent Amount", "📉 Predict Viscosity Drop"])
            
            # Mode 1: Known Target Viscosity -> Calculate Solvent
            with tab1:
                c1, c2 = st.columns(2)
                with c1:
                    t1_paint = st.number_input("Paint Batch Weight (kg)", value=800.0, step=50.0, key='t1_p')
                    t1_curr_v = st.number_input("Current Viscosity (s)", value=float(int(avg_init_v)), step=1.0, key='t1_cv')
                with c2:
                    t1_target_v = st.number_input("Target Viscosity (s)", value=float(int(avg_fin_v)), step=1.0, key='t1_tv')
                
                req_reduction = t1_curr_v - t1_target_v
                
                if req_reduction <= 0:
                    st.warning("Target viscosity must be lower than current viscosity.")
                else:
                    rec_solvent_kg = (ref_mean * t1_paint * req_reduction) / 1000
                    st.success(f"""
                    ### 💧 Recommended Solvent: {rec_solvent_kg:.2f} kg
                    *(Formula: {ref_mean:.2f} * {t1_paint} * {req_reduction:.1f} / 1000)*
                    """)
                    
            # Mode 2: Known Solvent Added -> Predict Viscosity Drop
            with tab2:
                c3, c4 = st.columns(2)
                with c3:
                    t2_paint = st.number_input("Paint Batch Weight (kg)", value=800.0, step=50.0, key='t2_p')
                    t2_curr_v = st.number_input("Current Viscosity (s)", value=float(int(avg_init_v)), step=1.0, key='t2_cv')
                with c4:
                    # Provide a realistic default solvent weight based on historical average ratio
                    default_solv = (avg_solv_ratio * 800.0) / 1000
                    t2_solv_added = st.number_input("Solvent Added (kg)", value=float(f"{default_solv:.1f}"), step=0.5, key='t2_s')
                
                if t2_solv_added > 0:
                    # Reverse Formula: Reduction = (Solvent * 1000) / (Paint * Reference)
                    pred_reduction = (t2_solv_added * 1000) / (t2_paint * ref_mean)
                    pred_final_v = t2_curr_v - pred_reduction
                    
                    st.info(f"""
                    ### 📉 Predicted Drop: {pred_reduction:.1f} seconds
                    **Predicted Final Viscosity:** {pred_final_v:.1f} s
                    """)


# ==========================================
# SECTION 9: RIGHT COLUMN - CAUSAL SCATTER PLOT
# ==========================================
        st.subheader("🎯 Solvent Ratio vs. Viscosity Drop")
        st.caption("Shows the causal relationship: How many seconds dropped based on the solvent ratio added.")
        
        try:
            fig_scatter = px.scatter(
                filtered_df,
                x='Solvent_Ratio_g_kg',   # X-Axis: The CAUSE (Solvent Ratio)
                y='Viscosity_Reduction',  # Y-Axis: The EFFECT (Viscosity Drop)
                trendline='ols',
                labels={
                    'Solvent_Ratio_g_kg': 'Solvent Ratio (g / 1kg Paint)',
                    'Viscosity_Reduction': 'Viscosity Reduction (seconds)'
                },
                color_discrete_sequence=['#e67e22'] # Matched with Sankey orange theme
            )
            fig_scatter.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor='white')
            fig_scatter.update_xaxes(showline=True, linecolor='lightgray', showgrid=True, gridcolor='whitesmoke')
            fig_scatter.update_yaxes(showline=True, linecolor='lightgray', showgrid=True, gridcolor='whitesmoke')
            st.plotly_chart(fig_scatter, use_container_width=True)
            
        except Exception:
            fig_scatter = px.scatter(
                filtered_df, 
                x='Solvent_Ratio_g_kg', 
                y='Viscosity_Reduction', 
                labels={
                    'Solvent_Ratio_g_kg': 'Solvent Ratio (g / 1kg Paint)',
                    'Viscosity_Reduction': 'Viscosity Reduction (seconds)'
                }
            )
            fig_scatter.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor='white')
            st.plotly_chart(fig_scatter, use_container_width=True)
