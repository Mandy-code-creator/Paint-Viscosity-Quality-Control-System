import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Intelligent SOP System", page_icon="⚙️", layout="wide")

# Ensure data is loaded
if 'raw_data_loaded' not in st.session_state or not st.session_state['raw_data_loaded']:
    st.warning("⚠️ Please upload data on the main page first.")
    st.stop()

# --- 2. DATA PROCESSING & CLEANSING (LOGIC 2 & 4 & 6) ---
@st.cache_data
def process_data(df):
    data = df.copy()
    
    if data.empty: 
        return data

    # Logic 2: Filter Valid Group A Records
    data = data[
        (data['添加重量'] > 0) & 
        (data['塗料重量'] > 0) & 
        (data['黏度(秒)'] > data['黏度(秒)_1']) &
        (data['Resin'].notna()) & (data['Vendor'].notna()) & (data['Solvent_Type'].notna())
    ]
    
    if data.empty: 
        return data
        
    data['Delta_V'] = data['黏度(秒)'] - data['黏度(秒)_1']
    data = data[data['Delta_V'] > 0]
    
    if data.empty: 
        return data
    
    # Logic 4: Standard Formulas for Historical Data
    # Minimum Operating Paint = 120 kg
    data['Dilution_Base'] = data['塗料重量'] + 120
    data['Solvent_Ratio_Percent'] = (data['添加重量'] / data['Dilution_Base']) * 100
    data['Sensitivity'] = data['Delta_V'] / data['Solvent_Ratio_Percent'].replace(0, np.nan)
    
    # Logic 3: Viscosity Zones
    def assign_zone(v):
        if v <= 70: return '<=70 s'
        elif v <= 90: return '71-90 s'
        elif v <= 110: return '91-110 s'
        elif v <= 130: return '111-130 s'
        else: return '>130 s'
    data['Initial_Viscosity_Zone'] = data['黏度(秒)'].apply(assign_zone)
    
    # Logic 6: P1-P99 Outlier Filtering (Per Group, n>=30)
    # ĐÃ SỬA LỖI PANDAS: Dùng transform() thay vì apply() để chống mất cột (KeyError)
    group_counts = data.groupby(['Resin', 'Vendor', 'Solvent_Type'])['Sensitivity'].transform('count')
    q01 = data.groupby(['Resin', 'Vendor', 'Solvent_Type'])['Sensitivity'].transform(lambda x: x.quantile(0.01))
    q99 = data.groupby(['Resin', 'Vendor', 'Solvent_Type'])['Sensitivity'].transform(lambda x: x.quantile(0.99))
    
    mask_large_group = group_counts >= 30
    mask_in_bounds = data['Sensitivity'].between(q01, q99)
    
    # Chỉ lọc Outlier ở các nhóm có >= 30 record, các nhóm nhỏ giữ nguyên
    data_clean = data[(~mask_large_group) | (mask_large_group & mask_in_bounds)].copy()
    
    return data_clean

master_df = process_data(st.session_state['group_a_data'])

# Safety Check để chặn hoàn toàn lỗi KeyError nếu file tải lên bị rỗng sau khi lọc
if master_df.empty or 'Resin' not in master_df.columns:
    st.error("⚠️ No valid historical data available after processing. Please verify that your dataset meets all SOP logic requirements.")
    st.stop()

# --- 12. SESSION STATE MANAGEMENT ---
def reset_execution_states():
    st.session_state['exec_curr_visc'] = 0.0
    st.session_state['exec_lsl'] = 0.0
    st.session_state['exec_usl'] = 0.0
    st.session_state['exec_order_weight'] = 0.0
    st.session_state['calculation_done'] = False

# --- GLOBAL FILTERS ---
st.title("⚙️ AI-Assisted Viscosity Optimization System")
st.markdown("Automated recommendation engine governed by historical safety thresholds and approved target specifications.")
st.markdown("---")

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    selected_resin = st.selectbox("Select Resin:", sorted(master_df['Resin'].unique()), on_change=reset_execution_states)
with col_f2:
    selected_vendor = st.selectbox("Select Vendor:", sorted(master_df[master_df['Resin'] == selected_resin]['Vendor'].unique()), on_change=reset_execution_states)
with col_f3:
    selected_solvent = st.selectbox("Select Solvent Type:", sorted(master_df[(master_df['Resin'] == selected_resin) & (master_df['Vendor'] == selected_vendor)]['Solvent_Type'].unique()), on_change=reset_execution_states)

# Get filtered system data
system_df = master_df[(master_df['Resin'] == selected_resin) & (master_df['Vendor'] == selected_vendor) & (master_df['Solvent_Type'] == selected_solvent)]

if system_df.empty:
    st.error("No valid historical data available for this configuration.")
    st.stop()


# --- 11. TABS ARCHITECTURE ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Tab 1: Historical Analysis", 
    "🎯 Tab 2: SOP Recommendation", 
    "📚 Tab 3: Engineering Matrix",
    "📋 Tab 4: Work Instruction"
])

# ==========================================
# TAB 1: HISTORICAL ANALYSIS (For Process Engineers)
# ==========================================
with tab1:
    st.markdown("### Historical Performance Review")
    st.markdown("Validate data stability before enforcing automated SOPs. *Hover over points to trace individual batches from their Initial (Orange) to Final (Blue) state.*")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Valid Batches", len(system_df))
    c2.metric("Median Sensitivity", f"{system_df['Sensitivity'].median():.2f} s/%")
    c3.metric("P10 - P90 Ratio Range", f"{system_df['Solvent_Ratio_Percent'].quantile(0.1):.1f}% - {system_df['Solvent_Ratio_Percent'].quantile(0.9):.1f}%")
    c4.metric("Max Drop (Delta V)", f"{system_df['Delta_V'].max():.1f} s")

    # ĐÃ XÓA BOXPLOT & PHÓNG TO BIỂU ĐỒ BEFORE VS AFTER TRÀN VIỀN
    fig_scatter = go.Figure()

    # 1. Dotted lines (Nối điểm Trước và Sau)
    x_lines = []
    y_lines = []
    for _, row in system_df.iterrows():
        x_lines.extend([row['Solvent_Ratio_Percent'], row['Solvent_Ratio_Percent'], None])
        y_lines.extend([row['黏度(秒)'], row['黏度(秒)_1'], None])

    fig_scatter.add_trace(go.Scatter(
        x=x_lines, y=y_lines, mode='lines',
        line=dict(color='lightgray', width=1.5, dash='dot'),
        hoverinfo='skip', showlegend=False
    ))

    # 2. Before Points (Màu Cam)
    fig_scatter.add_trace(go.Scatter(
        x=system_df['Solvent_Ratio_Percent'], y=system_df['黏度(秒)'], mode='markers',
        name="Initial Viscosity (Before)", 
        marker=dict(color='#ED7D31', size=9, line=dict(width=1, color='white')),
        customdata=system_df[['黏度(秒)_1', 'Delta_V', 'Initial_Viscosity_Zone']].values,
        hovertemplate='<b>Zone: %{customdata[2]}</b><br>' +
                      'Solvent Ratio: %{x:.2f}%<br>' +
                      'Initial Visc (Before): %{y:.1f}s 🌟<br>' +
                      'Final Visc (After): %{customdata[0]:.1f}s<br>' +
                      'Viscosity Drop (Delta V): %{customdata[1]:.1f}s<extra></extra>'
    ))
    
    # 3. After Points (Màu Xanh Dương)
    fig_scatter.add_trace(go.Scatter(
        x=system_df['Solvent_Ratio_Percent'], y=system_df['黏度(秒)_1'], mode='markers',
        name="Final Viscosity (After)", 
        marker=dict(color='#4472C4', size=9, line=dict(width=1, color='white')),
        customdata=system_df[['黏度(秒)', 'Delta_V', 'Initial_Viscosity_Zone']].values,
        hovertemplate='<b>Zone: %{customdata[2]}</b><br>' +
                      'Solvent Ratio: %{x:.2f}%<br>' +
                      'Initial Visc (Before): %{customdata[0]:.1f}s<br>' +
                      'Final Visc (After): %{y:.1f}s 🌟<br>' +
                      'Viscosity Drop (Delta V): %{customdata[1]:.1f}s<extra></extra>'
    ))

    fig_scatter.update_layout(
        plot_bgcolor='white', height=550, margin=dict(l=40, r=40, t=30, b=30),
        xaxis=dict(title="Solvent Blending Ratio (%)", showgrid=True, gridcolor='#EAEAEA', linecolor='black'),
        yaxis=dict(title="Viscosity (seconds)", showgrid=True, gridcolor='#EAEAEA', linecolor='black'),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        hovermode='closest'
    )
    
    st.plotly_chart(fig_scatter, use_container_width=True)


# ==========================================
# TAB 2: SOP RECOMMENDATION (Execution Engine)
# ==========================================
with tab2:
    st.markdown("### Process Parameter Configuration")
    
    # Initialize inputs in session state if not exist
    for key in ['exec_curr_visc', 'exec_lsl', 'exec_usl', 'exec_order_weight']:
        if key not in st.session_state: st.session_state[key] = 0.0

    col_i1, col_i2, col_i3, col_i4 = st.columns(4)
    with col_i1: curr_visc = st.number_input("Current Viscosity (s)", value=st.session_state['exec_curr_visc'], step=1.0, key='iv')
    with col_i2: app_lsl = st.number_input("Approved Target LSL (s)", value=st.session_state['exec_lsl'], step=1.0, key='ilsl')
    with col_i3: app_usl = st.number_input("Approved Target USL (s)", value=st.session_state['exec_usl'], step=1.0, key='iusl')
    with col_i4: order_weight = st.number_input("Order Paint Weight (kg)", value=st.session_state['exec_order_weight'], step=10.0, key='iow')
    
    st.markdown("---")

    if st.button("🚀 Calculate Optimized SOP", type="primary"):
        if curr_visc <= 0 or app_lsl <= 0 or app_usl <= 0 or order_weight <= 0:
            st.error("⚠️ All input parameters must be strictly greater than 0.")
        elif app_lsl >= app_usl:
            st.error("⚠️ LSL must be strictly less than USL.")
        else:
            # 5. Target Center
            target_center = (app_lsl + app_usl) / 2
            required_drop = curr_visc - target_center
            
            if required_drop <= 0:
                st.success("✅ Current viscosity is already within or below the target range. No solvent required.")
                st.session_state['calculation_done'] = False
            else:
                # 3 & 7. Dynamic Reference Logic
                def get_zone_str(v):
                    if v <= 70: return '<=70 s'
                    elif v <= 90: return '71-90 s'
                    elif v <= 110: return '91-110 s'
                    elif v <= 130: return '111-130 s'
                    else: return '>130 s'
                
                curr_zone = get_zone_str(curr_visc)
                zone_data = system_df[system_df['Initial_Viscosity_Zone'] == curr_zone]
                
                # Logic 7: Fallback and Confidence
                ref_data = None
                confidence = ""
                
                if len(zone_data) >= 5:
                    ref_data = zone_data
                    record_count = len(zone_data)
                    ref_source = f"Zone-Specific ({curr_zone})"
                else:
                    ref_data = system_df
                    record_count = len(system_df)
                    ref_source = "Overall System Fallback"
                
                if record_count >= 10: conf_msg = "🟢 Reliable"
                elif record_count >= 5: conf_msg = "🟡 Usable with Caution"
                else: conf_msg = "🔴 Insufficient Data"
                
                if record_count < 5:
                    st.error("🚨 **SYSTEM BLOCKED:** Insufficient historical data (<5 records) to generate safe automation. Manual Process Engineer verification required.")
                    st.session_state['calculation_done'] = False
                else:
                    ref_sensitivity = ref_data['Sensitivity'].median()
                    ref_ratio_p90 = ref_data['Solvent_Ratio_Percent'].quantile(0.9)
                    ref_ratio_p95 = ref_data['Solvent_Ratio_Percent'].quantile(0.95)
                    ref_drop_p90 = ref_data['Delta_V'].quantile(0.9)
                    ref_drop_max = ref_data['Delta_V'].max()
                    
                    # Core Calculations
                    dilution_base = order_weight + 120
                    required_ratio = required_drop / ref_sensitivity
                    recommended_solvent = dilution_base * (required_ratio / 100)
                    max_total_solvent = dilution_base * (ref_ratio_p90 / 100)
                    
                    # 8. Risk Control Logic
                    risk_status = ""
                    risk_color = ""
                    blocked = False
                    
                    if required_ratio > ref_ratio_p95 or required_drop > ref_drop_max:
                        risk_status = "🚨 CRITICAL OVERLOAD: Target exceeds P95 Safe Limits."
                        risk_color = "red"
                        blocked = True
                    elif (ref_ratio_p90 < required_ratio <= ref_ratio_p95) or (ref_drop_p90 < required_drop <= ref_drop_max):
                        risk_status = "⚠️ DIMINISHING RETURNS WARNING: Target exceeds P90 Optimal Zone. Extra supervision required."
                        risk_color = "orange"
                    else:
                        risk_status = "✅ NORMAL OPERATION: Target within P90 historical bounds."
                        risk_color = "green"
                    
                    st.markdown(f"### Assessment: <span style='color:{risk_color}'>{risk_status}</span>", unsafe_allow_html=True)
                    
                    if blocked:
                        st.error("Execution automatically blocked by Safety Constraints. Please escalate to Process Engineer.")
                        st.session_state['calculation_done'] = False
                    else:
                        # 9. Multi-stage Addition
                        stage1 = recommended_solvent * 0.60
                        stage2 = recommended_solvent * 0.25
                        fine_adj = recommended_solvent * 0.15
                        
                        # Store in session state for Tab 4 (Worker Instruction)
                        st.session_state.update({
                            'calculation_done': True,
                            'calc_curr_visc': curr_visc,
                            'calc_lsl': app_lsl,
                            'calc_usl': app_usl,
                            'calc_order_weight': order_weight,
                            'calc_base': dilution_base,
                            'calc_req_drop': required_drop,
                            'calc_sensitivity': ref_sensitivity,
                            'calc_ref_source': ref_source,
                            'calc_conf': conf_msg,
                            'calc_records': record_count,
                            'calc_rec_solvent': recommended_solvent,
                            'calc_max_solvent': max_total_solvent,
                            'calc_s1': stage1,
                            'calc_s2': stage2,
                            'calc_fa': fine_adj,
                            'sys_resin': selected_resin,
                            'sys_vendor': selected_vendor,
                            'sys_solvent': selected_solvent,
                            'calc_risk': risk_status
                        })
                        
                        # Display Summary in Tab 2
                        col_r1, col_r2, col_r3 = st.columns(3)
                        col_r1.metric("Required Viscosity Drop", f"{required_drop:.1f} s")
                        col_r2.metric("Reference Sensitivity", f"{ref_sensitivity:.2f} s/%", help=f"Source: {ref_source} (n={record_count})")
                        col_r3.metric("Data Confidence", conf_msg)
                        
                        st.success(f"**Calculated Total Recommendation:** `{recommended_solvent:.2f} kg` (Absolute Limit: {max_total_solvent:.2f} kg)")


# ==========================================
# TAB 3: ENGINEERING MATRIX (For Process Engineers)
# ==========================================
with tab3:
    st.markdown("### 📚 Comprehensive Engineering Matrix")
    st.markdown("Full operational baseline matrix for SOP documentation and safety boundary definitions.")
    
    def generate_matrix(df):
        grouped = df.groupby('Initial_Viscosity_Zone', observed=False).agg(
            Records=('塗料批號', 'nunique'),
            Sensitivity_Median=('Sensitivity', 'median'),
            Ratio_Median=('Solvent_Ratio_Percent', 'median'),
            Ratio_P90=('Solvent_Ratio_Percent', lambda x: x.quantile(0.9)),
            Ratio_P95=('Solvent_Ratio_Percent', lambda x: x.quantile(0.95)),
            Drop_Median=('Delta_V', 'median'),
            Drop_P90=('Delta_V', lambda x: x.quantile(0.9)),
            Drop_Max=('Delta_V', 'max')
        ).reset_index()
        
        # Calculate Factor kg/100kg/1s
        grouped['Factor (kg/100kg/1s)'] = grouped['Sensitivity_Median'].apply(lambda x: (1.0/x) if x>0 else 0)
        return grouped
        
    eng_matrix = generate_matrix(system_df)
    st.dataframe(
        eng_matrix, 
        column_config={
            "Records": st.column_config.NumberColumn(format="%d"),
            "Sensitivity_Median": st.column_config.NumberColumn("Median Sensitivity (s/%)", format="%.2f"),
            "Ratio_Median": st.column_config.NumberColumn("Median Ratio %", format="%.2f"),
            "Ratio_P90": st.column_config.NumberColumn("P90 Ratio %", format="%.2f"),
            "Ratio_P95": st.column_config.NumberColumn("P95 Ratio %", format="%.2f"),
            "Drop_Median": st.column_config.NumberColumn("Median Drop (s)", format="%.1f"),
            "Drop_P90": st.column_config.NumberColumn("P90 Drop (s)", format="%.1f"),
            "Drop_Max": st.column_config.NumberColumn("Max Drop (s)", format="%.1f"),
            "Factor (kg/100kg/1s)": st.column_config.NumberColumn(format="%.3f")
        },
        use_container_width=True, hide_index=True
    )
    
    csv_export = eng_matrix.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Engineering Matrix", data=csv_export, file_name=f"Engineering_Matrix_{selected_resin}_{selected_vendor}.csv", mime='text/csv')


# ==========================================
# TAB 4: WORK INSTRUCTION (Shop Floor Operator View)
# ==========================================
with tab4:
    if not st.session_state.get('calculation_done', False):
        st.info("⚠️ Please generate and validate the SOP in **Tab 2** before issuing the Work Instruction.")
    else:
        st.markdown("## 🏭 Standard Dilution Work Instruction")
        st.markdown(f"**Execution Material:** {st.session_state['sys_resin']} | {st.session_state['sys_vendor']} | Solvent: {st.session_state['sys_solvent']}")
        
        # Current status read-only
        c_status1, c_status2, c_status3, c_status4 = st.columns(4)
        c_status1.metric("Current Viscosity", f"{st.session_state['calc_curr_visc']:.1f} s")
        c_status2.metric("Approved Target", f"{st.session_state['calc_lsl']:.1f} - {st.session_state['calc_usl']:.1f} s")
        c_status3.metric("Order Paint Weight", f"{st.session_state['calc_order_weight']:.1f} kg")
        c_status4.metric("Dilution Base", f"{st.session_state['calc_base']:.1f} kg")

        st.markdown("---")
        st.markdown("### 🛠️ Execution Protocol (3-Stage Addition)")
        
        st.markdown(f"""
        <div style='background-color: #F0F8FF; padding: 20px; border-radius: 10px; border-left: 8px solid #0066CC; margin-bottom: 20px;'>
            <h4 style='margin-top:0;'>STEP 1: Primary Addition (60%)</h4>
            <h2>Add <span style='color: #0066CC;'>{st.session_state['calc_s1']:.2f} kg</span> of Solvent</h2>
            <p><i>Action: Agitate under standard conditions, then re-measure viscosity.</i></p>
        </div>
        
        <div style='background-color: #F5FFFA; padding: 20px; border-radius: 10px; border-left: 8px solid #00CC66; margin-bottom: 20px;'>
            <h4 style='margin-top:0;'>STEP 2: Secondary Addition (25%)</h4>
            <h2>Add <span style='color: #00CC66;'>{st.session_state['calc_s2']:.2f} kg</span> of Solvent</h2>
            <p><i>Action: Only execute if viscosity is still > USL. Agitate and re-measure.</i></p>
        </div>
        
        <div style='background-color: #FFF5EE; padding: 20px; border-radius: 10px; border-left: 8px solid #FF9933; margin-bottom: 20px;'>
            <h4 style='margin-top:0;'>STEP 3: Fine Micro-Adjustment (15%)</h4>
            <h2>Gradually add up to <span style='color: #FF9933;'>{st.session_state['calc_fa']:.2f} kg</span></h2>
            <p><i>Action: Add incrementally until the target range is perfectly achieved.</i></p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("### 🛑 Safety & Escalation Constraints")
        st.error(f"**ABSOLUTE MAXIMUM SOLVENT LIMIT:** `{st.session_state['calc_max_solvent']:.2f} kg`")
        st.warning("**ESCALATION RULE:** If viscosity remains above USL after reaching the Absolute Maximum Limit, STOP operation immediately and contact the Quality Engineer (QE).")
        
        if "WARNING" in st.session_state['calc_risk']:
            st.warning(f"**QE NOTICE FOR THIS BATCH:** {st.session_state['calc_risk']}")
