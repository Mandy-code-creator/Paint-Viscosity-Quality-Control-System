import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# --- 1. SETUP & DATA RETRIEVAL ---
st.set_page_config(page_title="Executive Summary", page_icon="📈", layout="wide")

if 'raw_data_loaded' not in st.session_state or not st.session_state['raw_data_loaded']:
    st.warning("⚠️ Please upload data on the main page first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()
rejected_data = st.session_state.get('rejected_data', pd.DataFrame())

# Ensure Delta_V exists in dataset
if 'Delta_V' not in group_a.columns:
    group_a['Delta_V'] = group_a['黏度(秒)'] - group_a['黏度(秒)_1']

# Global calculations for Sensitivity (Seconds dropped per 1% solvent)
group_a['Solvent_Ratio_Percent'] = (group_a['添加重量'] / group_a['塗料重量'].replace(0, 1)) * 100
group_a['Sensitivity'] = group_a['Delta_V'] / group_a['Solvent_Ratio_Percent'].replace(0, np.nan)

st.title("📈 Executive Summary & Portfolio Analysis")
st.markdown("High-level performance metrics, environmental sensitivity tracking, and multi-factor recommendation engine.")
st.markdown("---")

# --- 2. GLOBAL KPI METRICS ---
st.subheader("💡 Global Key Performance Indicators")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="Total Valid Batches", value=f"{len(group_a):,} batches")
with col2:
    st.metric(label="Total Paint Processed", value=f"{group_a['塗料重量'].sum():,.1f} kg")
with col3:
    st.metric(label="Global Avg Solvent Ratio", value=f"{(group_a['Solvent_Ratio_Percent'].mean()):.2f} %")
with col4:
    st.metric(label="Data Anomalies (Rejected)", value=f"{len(rejected_data)} rows")

st.markdown("---")

# --- 3. DASHBOARD TABS ARCHITECTURE ---
tab_exec, tab_env, tab_ai = st.tabs([
    "📋 Tab 1: Vendor & Resin Portfolio", 
    "🌡️ Tab 2: Sensitivity & Environment", 
    "🧠 Tab 3: Multi-Factor AI & Matrix"
])

# ==========================================
# TAB 1: VENDOR & RESIN PORTFOLIO
# ==========================================
with tab_exec:
    st.markdown("### 📋 Resin, Vendor & Application Performance Analysis")
    st.markdown("*Comprehensive breakdown of historical performance by vendor and end-product application.*")

    matrix_df = group_a.copy()
    paint_code_col = '塗料代碼' 
    
    # Advanced Decryption Logic for Application Codes
    def get_clean_application(code_str):
        if not isinstance(code_str, str) or len(str(code_str).strip()) < 4:
            return 'Unknown/Other'
        code = str(code_str).strip().upper()
        char_4 = code[3]
        f_map = {
            'B': 'Anti-Bacteria', 'C': 'High-Corrosion Resistance', 'D': 'Anti-Dust', 
            'E': 'Anti-Electrostatics', 'F': 'High Formability', 'G': 'General Usage', 
            'H': 'Thermal Insulation', 'K': 'Anti-Stain/Grease', 'L': 'Whiteboard', 
            'M': 'Mirror-like Paint', 'N': 'Neo Matt', 'P': 'Primer B', 
            'R': 'Repaint System', 'S': 'Shutter', 'T': 'Texture Surface', 
            'V': 'Variety', 'U': 'Ultra-High Formability', 'W': 'Wrinkle Paint', 'Z': 'Other'
        }
        return 'General Usage' if char_4.isdigit() else f_map.get(char_4, 'Unknown/Other')

    if paint_code_col in matrix_df.columns:
        matrix_df['Application'] = matrix_df[paint_code_col].apply(get_clean_application)
    else:
        if 'Feature' in matrix_df.columns:
            matrix_df['Application'] = matrix_df['Feature'].astype(str).apply(lambda x: x.split(' (')[0] if '(' in x else x)
        else:
            matrix_df['Application'] = 'Unknown/Other'

    for col in ['Solvent_Type', '溫度', '濕度']:
        if col not in matrix_df.columns: matrix_df[col] = 0

    detailed_summary = matrix_df.groupby(['Resin', 'Vendor', 'Application', 'Solvent_Type']).agg({
        '塗料批號': 'nunique',
        '塗料重量': 'sum',
        '添加重量': 'sum',
        '黏度(秒)': 'mean',
        '黏度(秒)_1': 'mean',
        '溫度': 'mean',
        '濕度': 'mean',
        'Solvent_Ratio_Percent': 'mean',
        'Sensitivity': 'mean'
    }).rename(columns={
        '塗料批號': 'Batches',
        '塗料重量': 'Total Paint (kg)',
        '添加重量': 'Total Solvent (kg)',
        '黏度(秒)': 'Initial V (s)',
        '黏度(秒)_1': 'Final V (s)',
        '溫度': 'Avg Temp (°C)',
        '濕度': 'Avg Humidity (%)',
        'Solvent_Ratio_Percent': 'Avg Solvent %',
        'Sensitivity': 'Avg Sensitivity'
    }).reset_index()

    detailed_summary['Solvent % / 1s Drop'] = detailed_summary['Avg Sensitivity'].apply(lambda x: (1.0 / x) if x > 0 else 0)
    detailed_summary = detailed_summary.drop(columns=['Avg Sensitivity'])

    # Advanced visualization dashboard presentation
    st.dataframe(
        detailed_summary,
        column_config={
            "Total Paint (kg)": st.column_config.NumberColumn(format="%d"),
            "Total Solvent (kg)": st.column_config.NumberColumn(format="%d"),
            "Initial V (s)": st.column_config.NumberColumn(format="%.1f"),
            "Final V (s)": st.column_config.NumberColumn(format="%.1f"),
            "Avg Temp (°C)": st.column_config.NumberColumn(format="%.1f"),
            "Avg Humidity (%)": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100),
            "Avg Solvent %": st.column_config.NumberColumn(format="%.2f%%"),
            "Solvent % / 1s Drop": st.column_config.NumberColumn(format="%.3f%%")
        },
        use_container_width=True,
        hide_index=True
    )

# ==========================================
# TAB 2: SENSITIVITY & ENVIRONMENT
# ==========================================
with tab_env:
    st.markdown("### 🌡️ Process Sensitivity & Environmental Impact Matrix")
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        selected_resin = st.selectbox("Select Target Resin to Analyze", group_a['Resin'].unique(), index=0)
    with col_f2:
        selected_vendors = st.multiselect("Select Target Vendor(s)", group_a['Vendor'].unique(), default=group_a['Vendor'].unique())

    filtered_data = group_a[(group_a['Resin'] == selected_resin) & (group_a['Vendor'].isin(selected_vendors))].copy()

    if not filtered_data.empty:
        col_heat1, col_heat2 = st.columns(2)
        
        with col_heat1:
            st.markdown("#### Formula Efficiency: Viscosity vs. Solvent")
            solvent_bins = [0, 2, 4, 6, 8, 10, 12, 15, 20]
            viscosity_bins = [50, 70, 90, 110, 130, 150, 170, 190, 210, 250]

            filtered_data['Solvent_Bin'] = pd.cut(filtered_data['Solvent_Ratio_Percent'], bins=solvent_bins)
            filtered_data['Initial_V_Bin'] = pd.cut(filtered_data['黏度(秒)'], bins=viscosity_bins)

            heatmap_data = filtered_data.groupby(['Initial_V_Bin', 'Solvent_Bin'], observed=False)['Sensitivity'].mean().reset_index()
            pivot_table = heatmap_data.pivot(index='Initial_V_Bin', columns='Solvent_Bin', values='Sensitivity')

            # --- ĐÃ SỬA LỖI Ở ĐÂY: Ép kiểu Interval thành String để chống lỗi JSON ---
            pivot_table.index = pivot_table.index.astype(str)
            pivot_table.columns = pivot_table.columns.astype(str)

            fig_heatmap = px.imshow(
                pivot_table.astype(float), text_auto=".1f", aspect="auto", color_continuous_scale='Blues',
                labels=dict(x="Solvent Ratio (%)", y="Initial Viscosity (s)", color="Sensitivity (s/%)")
            )
            fig_heatmap.update_xaxes(categoryorder='array', categoryarray=[str(c) for c in pivot_table.columns])
            fig_heatmap.update_yaxes(categoryorder='array', categoryarray=[str(i) for i in pivot_table.index])
            fig_heatmap.update_layout(plot_bgcolor='white', margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_heatmap, use_container_width=True)
            
        with col_heat2:
            st.markdown("#### Weather Impact: Temperature vs. Humidity")
            temp_col = '溫度' 
            hum_col = '濕度'
            
            if temp_col in filtered_data.columns and hum_col in filtered_data.columns:
                temp_bins = [15, 20, 25, 30, 35, 40]
                hum_bins = [40, 50, 60, 70, 80, 90, 100]

                filtered_data['Temp_Bin'] = pd.cut(filtered_data[temp_col], bins=temp_bins)
                filtered_data['Hum_Bin'] = pd.cut(filtered_data[hum_col], bins=hum_bins)

                heatmap_env = filtered_data.groupby(['Hum_Bin', 'Temp_Bin'], observed=False)['Sensitivity'].mean().reset_index()
                pivot_env = heatmap_env.pivot(index='Hum_Bin', columns='Temp_Bin', values='Sensitivity')

                # --- ĐÃ SỬA LỖI Ở ĐÂY: Ép kiểu Interval thành String để chống lỗi JSON ---
                pivot_env.index = pivot_env.index.astype(str)
                pivot_env.columns = pivot_env.columns.astype(str)

                fig_env = px.imshow(
                    pivot_env.astype(float), text_auto=".1f", aspect="auto", color_continuous_scale='Oranges',
                    labels=dict(x="Temperature (°C)", y="Humidity (%)", color="Sensitivity (s/%)")
                )
                fig_env.update_xaxes(categoryorder='array', categoryarray=[str(c) for c in pivot_env.columns])
                fig_env.update_yaxes(categoryorder='array', categoryarray=[str(i) for i in pivot_env.index])
                fig_env.update_layout(plot_bgcolor='white', margin=dict(l=20, r=20, t=30, b=20))
                st.plotly_chart(fig_env, use_container_width=True)
            else:
                st.error("Environmental condition columns ('溫度' / '濕度') not found in the dataset.")
    else:
        st.info("No data available for the selected Resin and Vendors.")

# ==========================================
# TAB 3: MULTI-FACTOR AI & MATRIX
# ==========================================
with tab_ai:
    st.markdown("### 🧠 Smart Multi-Factor Recommendation Engine")
    st.markdown("*Calculates theoretical solvent targets by cross-referencing real-time shop floor environmental indicators.*")

    col_i1, col_i2, col_i3, col_i4, col_i5 = st.columns(5)
    with col_i1: curr_viscosity = st.number_input("Current Tank Viscosity (s)", value=55.0, step=1.0)
    with col_i2: target_viscosity = st.number_input("Target Viscosity Target (s)", value=52.0, step=1.0)
    with col_i3: curr_temp = st.number_input("Shop Temperature (°C)", value=32.0, step=1.0)
    with col_i4: curr_humidity = st.number_input("Shop Humidity (%)", value=85.0, step=5.0)
    with col_i5: coil_paint_qty = st.number_input("Total Batch Weight (kg)", value=200.0, step=10.0)

    if target_viscosity >= curr_viscosity:
        st.info("✅ Target viscosity is already achieved. No solvent addition required.")
    else:
        viscosity_drop = curr_viscosity - target_viscosity
        
        base_subset = group_a.copy()
        if 'selected_resin' in locals():
            base_subset = group_a[(group_a['Resin'] == selected_resin) & (group_a['Vendor'].isin(selected_vendors))]

        visc_mask = (base_subset['黏度(秒)'] >= curr_viscosity - 15) & (base_subset['黏度(秒)'] <= curr_viscosity + 15)
        
        weather_mask = True
        if '溫度' in base_subset.columns and '濕度' in base_subset.columns:
            weather_mask = (base_subset['溫度'] >= curr_temp - 5) & (base_subset['溫度'] <= curr_temp + 5) & \
                           (base_subset['濕度'] >= curr_humidity - 10) & (base_subset['濕度'] <= curr_humidity + 10)
        
        subset_strict = base_subset[visc_mask & weather_mask]
        subset_partial = base_subset[visc_mask]
        subset_general = base_subset
        
        expected_sensitivity = 0
        match_level = ""
        
        if not subset_strict.empty and subset_strict['Sensitivity'].mean() > 0:
            expected_sensitivity = subset_strict['Sensitivity'].mean()
            match_level = "High Confidence (Matched Viscosity & Environment)"
            m_color = "green"
        elif not subset_partial.empty and subset_partial['Sensitivity'].mean() > 0:
            expected_sensitivity = subset_partial['Sensitivity'].mean()
            match_level = "Medium Confidence (Matched Viscosity Only)"
            m_color = "orange"
        elif not subset_general.empty and subset_general['Sensitivity'].mean() > 0:
            expected_sensitivity = subset_general['Sensitivity'].mean()
            match_level = "Low Confidence (System Average)"
            m_color = "red"
            
        if expected_sensitivity > 0:
            theoretical_ratio = viscosity_drop / expected_sensitivity
            theoretical_solvent_kg = coil_paint_qty * (theoretical_ratio / 100)

            st.markdown(f"""
            <div style="background-color: #F8F9FA; padding: 20px; border-radius: 8px; border-left: 6px solid #4472C4; margin-top: 15px;">
                <h3 style="margin-top: 0; color: #333;">Recommended Addition Target: <span style="color: #4472C4;">{theoretical_solvent_kg:.2f} kg</span></h3>
                <p style="margin-bottom: 5px;"><b>Required Viscosity Drop (Delta V):</b> {viscosity_drop:.1f} seconds</p>
                <p style="margin-bottom: 5px;"><b>Historical System Sensitivity:</b> {expected_sensitivity:.2f} seconds drop per 1% solvent</p>
                <p style="margin-bottom: 0;"><b>Data Match Quality:</b> <span style="color: {m_color}; font-weight: bold;">{match_level}</span></p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.error("Unable to calculate target value due to insufficient historical sensitivity boundaries.")

    st.markdown("---")
    st.markdown("#### 📚 Standard Operating Procedure (SOP) Reference Coefficient Matrix")
    st.markdown("*Robust master coefficient index. Multiply the 'Solvent Factor' by your required viscosity drop to estimate targets manually.*")
    
    matrix_data = []
    matrix_df = group_a.copy()
    
    if '塗料代碼' in matrix_df.columns:
        matrix_df['Application'] = matrix_df['塗料代碼'].apply(get_clean_application)
    else:
        matrix_df['Application'] = 'General Usage'

    def generate_dynamic_bins(series):
        if len(series) < 4: return pd.cut(series, bins=1, precision=0)
        try: return pd.qcut(series, q=4, precision=0, duplicates='drop')
        except: return pd.cut(series, bins=4, precision=0)

    matrix_df['Viscosity_Zone'] = matrix_df.groupby('Resin')['黏度(秒)'].transform(generate_dynamic_bins)

    target_viscosity_map = matrix_df.groupby(['Resin', 'Vendor', 'Application'])['黏度(秒)_1'].median().reset_index().rename(columns={'黏度(秒)_1': 'Typical_Target'})
    sensitivity_map = matrix_df.groupby(['Resin', 'Vendor', 'Application', 'Viscosity_Zone'], observed=False)['Sensitivity'].mean().reset_index()
    sensitivity_map = sensitivity_map[sensitivity_map['Sensitivity'] > 0]

    sop_grouped = pd.merge(sensitivity_map, target_viscosity_map, on=['Resin', 'Vendor', 'Application'], how='inner')

    for _, row in sop_grouped.iterrows():
        sens = row['Sensitivity']
        matrix_data.append({
            'Resin': row['Resin'],
            'Vendor': row['Vendor'],
            'Application': row['Application'],
            'Viscosity Range (s)': str(row['Viscosity_Zone']),
            'Typical Target (s)': round(row['Typical_Target'], 1),
            'Sensitivity (s/%)': round(sens, 2),
            'Factor (kg per 100kg paint)': round(1.0 / sens, 3)
        })

    df_matrix = pd.DataFrame(matrix_data)
    if not df_matrix.empty:
        st.dataframe(df_matrix.sort_values(by=['Resin', 'Vendor']), use_container_width=True, hide_index=True)
        
        # Enable executive export function
        csv = df_matrix.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download SOP Coefficient Matrix as CSV",
            data=csv,
            file_name='SOP_Master_Coefficient_Matrix.csv',
            mime='text/csv',
        )
