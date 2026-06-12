import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

# ==========================================
# 1. PAGE CONFIGURATION & CUSTOM CSS
# ==========================================
st.set_page_config(page_title="Solvent Adjustment Intelligence", layout="wide", initial_sidebar_state="collapsed")

# CSS: Ẩn Header mặc định của Streamlit và ép giao diện hiện đại
custom_css = """
<style>
    /* Hide Streamlit default header and footer to fix overlapping */
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Light gray app background */
    .stApp { background-color: #F4F7F9; font-family: 'Segoe UI', sans-serif; }
    
    /* Reduce default Streamlit padding */
    .block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 98%; }
    
    /* Main Titles */
    .main-title { font-size: 24px; font-weight: 800; color: #1E293B; margin-bottom: 0px; }
    .sub-title { font-size: 13px; color: #64748B; margin-bottom: 15px; }
    
    /* Metric Cards */
    .metric-card {
        background-color: white; border-radius: 10px; padding: 15px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border: 1px solid #E2E8F0;
        display: flex; flex-direction: column; justify-content: center; height: 90px;
    }
    .metric-title { font-size: 13px; color: #64748B; font-weight: 600; margin-bottom: 5px;}
    .metric-value { font-size: 24px; font-weight: 700; color: #0F172A; margin:0;}
    
    /* Content Boxes */
    .content-box {
        background-color: white; border-radius: 12px; padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border: 1px solid #E2E8F0;
        margin-bottom: 20px; height: 100%;
    }
    
    /* Sankey Headers (Pills) */
    .pill-header {
        border-radius: 20px; padding: 5px 15px; color: white; font-weight: bold; font-size: 12px; text-align: center;
    }
    .pill-blue { background-color: #3B82F6; }
    .pill-teal { background-color: #14B8A6; }
    .pill-purple { background-color: #8B5CF6; }
    
    /* Breadcrumb */
    .breadcrumb { display: flex; align-items: center; gap: 10px; margin-bottom: 15px;}
    .bc-item { background-color: #EEF2FF; color: #4F46E5; padding: 5px 15px; border-radius: 6px; font-size: 13px; font-weight: 600;}
    
    /* Detail Table */
    .info-table { width: 100%; font-size: 13px; color: #334155; border-collapse: collapse; }
    .info-table td { padding: 8px 0; border-bottom: 1px dashed #E2E8F0; }
    .info-table td:last-child { text-align: right; font-weight: 600; }
    .highlight-row { color: #7C3AED; font-weight: bold; font-size: 14px;}
    
    /* Reference Value Card */
    .ref-card { background-color: #FAFAFA; border: 1px solid #E2E8F0; border-radius: 8px; padding: 15px; text-align: center; }
    .ref-title { color: #64748B; font-size: 12px; font-weight: bold; margin-bottom: 10px;}
    .ref-val { color: #7C3AED; font-size: 28px; font-weight: bold; margin: 5px 0;}
    .ref-desc { color: #64748B; font-size: 12px;}
    
    /* Result Box */
    .result-box { background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 8px; padding: 15px; margin-top: 15px;}
    .result-val { color: #059669; font-size: 24px; font-weight: bold; margin: 5px 0;}
    
    /* Remove text shadow from sankey */
    g.sankey-node text { text-shadow: none !important; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)


# ==========================================
# 2. DATA LOADING & PREPROCESSING
# ==========================================
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please upload your data file first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()
group_a['Solvent_Type'] = group_a['Solvent_Type'].astype(str)
if 'Vendor' not in group_a.columns: group_a['Vendor'] = 'Unknown'

visc_before = '黏度(秒)'
visc_after = '黏度(秒)_1'
paint_weight = '塗料重量'
solvent_weight = '添加重量'

if all(col in group_a.columns for col in [visc_before, visc_after, paint_weight, solvent_weight]):
    df = group_a.dropna(subset=[visc_before, visc_after, paint_weight, solvent_weight]).copy()
    for col in [visc_before, visc_after, paint_weight, solvent_weight]:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=[visc_before, visc_after, paint_weight, solvent_weight])
    
    df['Viscosity_Reduction'] = df[visc_before] - df[visc_after]
    df = df[(df[paint_weight] > 0) & (df[solvent_weight] > 0) & (df['Viscosity_Reduction'] > 0)]
    df['Reference_Value'] = (df[solvent_weight] * 1000) / (df[paint_weight] * df['Viscosity_Reduction'])
    df['Solvent_Ratio_g_kg'] = (df[solvent_weight] * 1000) / df[paint_weight]
else:
    st.error("⚠️ Missing required data columns.")
    st.stop()


# ==========================================
# 3. HEADER & DYNAMIC CASCADING FILTERS
# ==========================================
c_title, c_filt1, c_filt2, c_filt3, c_filt4 = st.columns([3.5, 1.5, 1.5, 1.5, 2])

with c_title:
    st.markdown("<div class='main-title'>SOLVENT ADJUSTMENT INTELLIGENCE</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-title'>Flow Relationship: Supplier ➔ Resin ➔ Solvent</div>", unsafe_allow_html=True)

with c_filt1: 
    selected_vendor = st.selectbox("Supplier", ["All"] + list(df['Vendor'].unique()))
with c_filt2: 
    resins_avail = df[df['Vendor'] == selected_vendor]['Resin'].unique() if selected_vendor != 'All' else df['Resin'].unique()
    selected_resin = st.selectbox("Resin Type", ["All"] + list(resins_avail))
with c_filt3: 
    mask_s = pd.Series(True, index=df.index)
    if selected_vendor != 'All': mask_s &= (df['Vendor'] == selected_vendor)
    if selected_resin != 'All': mask_s &= (df['Resin'] == selected_resin)
    solvs_avail = df[mask_s]['Solvent_Type'].unique()
    selected_solvent = st.selectbox("Solvent Type", ["All"] + list(solvs_avail))
with c_filt4: 
    st.text_input("Time Period (Demo)", "01/01/2024  ➔  12/31/2024")

# Áp dụng bộ lọc tạo Dataframe con
filtered_df = df.copy()
if selected_vendor != 'All': filtered_df = filtered_df[filtered_df['Vendor'] == selected_vendor]
if selected_resin != 'All': filtered_df = filtered_df[filtered_df['Resin'] == selected_resin]
if selected_solvent != 'All': filtered_df = filtered_df[filtered_df['Solvent_Type'] == selected_solvent]


# ==========================================
# 4. DYNAMIC KPI CARDS
# ==========================================
k1, k2, k3, k4, k5 = st.columns(5)
total_batches = len(filtered_df)
total_solvent_kg = filtered_df[solvent_weight].sum() if not filtered_df.empty else 0
total_resins = filtered_df['Resin'].nunique() if not filtered_df.empty else 0
total_solvents = filtered_df['Solvent_Type'].nunique() if not filtered_df.empty else 0
total_suppliers = filtered_df['Vendor'].nunique() if not filtered_df.empty else 0

k1.markdown(f"""<div class='metric-card'><div class='metric-title'>Total Batches</div>
<p class='metric-value'>{total_batches:,}</p></div>""", unsafe_allow_html=True)

k2.markdown(f"""<div class='metric-card'><div class='metric-title'>Total Solvent Used</div>
<p class='metric-value'>{total_solvent_kg:,.1f} kg</p></div>""", unsafe_allow_html=True)

k3.markdown(f"<div class='metric-card'><div class='metric-title'>Resin Types</div><p class='metric-value'>{total_resins}</p></div>", unsafe_allow_html=True)
k4.markdown(f"<div class='metric-card'><div class='metric-title'>Solvent Types</div><p class='metric-value'>{total_solvents}</p></div>", unsafe_allow_html=True)
k5.markdown(f"<div class='metric-card'><div class='metric-title'>Suppliers</div><p class='metric-value'>{total_suppliers}</p></div>", unsafe_allow_html=True)

st.write("") # Spacer


# ==========================================
# 5. MAIN LAYOUT (LEFT: SANKEY, RIGHT: METRICS)
# ==========================================
col_left, col_right = st.columns([6, 4], gap="large")

with col_left:
    st.markdown("<div class='content-box'>", unsafe_allow_html=True)
    st.markdown("<div style='font-weight:bold; color:#1E293B; font-size:16px;'>RELATIONSHIP: SUPPLIER ➔ RESIN ➔ SOLVENT</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:12px; color:#64748B; margin-bottom:15px;'>Flow thickness represents batch count</div>", unsafe_allow_html=True)
    
    # Pill Headers (Lưu ý: Không thụt lề (indent) chuỗi HTML này để tránh lỗi Markdown code block)
    html_pills = """
<div style='display:flex; justify-content:space-between; margin-bottom:0px; padding:0 30px;'>
    <div class='pill-header pill-blue' style='width:150px;'>SUPPLIER</div>
    <div class='pill-header pill-teal' style='width:150px;'>RESIN TYPE</div>
    <div class='pill-header pill-purple' style='width:150px;'>SOLVENT</div>
</div>
"""
    st.markdown(html_pills, unsafe_allow_html=True)

    if filtered_df.empty:
        st.info("No data available for the current filter.")
    else:
        sankey_df = filtered_df.copy()
        vendors = list(sankey_df['Vendor'].unique())
        resins = list(sankey_df['Resin'].unique())
        solvents = list(sankey_df['Solvent_Type'].unique())
        
        v_counts = sankey_df['Vendor'].value_counts()
        r_counts = sankey_df['Resin'].value_counts()
        s_counts = sankey_df['Solvent_Type'].value_counts()
        
        # Format labels clearly
        node_labels = (
            [f"🏭 {v}<br>({v_counts.get(v, 0)} batches)" for v in vendors] +
            [f"🧪 {r}<br>({r_counts.get(r, 0)} batches)" for r in resins] +
            [f"💧 {s}<br>({s_counts.get(s, 0)} batches)" for s in solvents]
        )
        
        vendor_idx = {v: i for i, v in enumerate(vendors)}
        resin_idx = {r: i + len(vendors) for i, r in enumerate(resins)}
        solvent_idx = {s: i + len(vendors) + len(resins) for i, s in enumerate(solvents)}
        
        # Áp dụng màu sắc cho Nodes y hệt thiết kế
        node_colors = ["#3B82F6"] * len(vendors) + ["#14B8A6"] * len(resins) + ["#C4B5FD"] * len(solvents)
        
        source, target, value, link_colors = [], [], [], []
        
        v_r_group = sankey_df.groupby(['Vendor', 'Resin']).size().reset_index(name='count')
        for _, row in v_r_group.iterrows():
            source.append(vendor_idx[row['Vendor']])
            target.append(resin_idx[row['Resin']])
            value.append(row['count'])
            link_colors.append("rgba(226, 232, 240, 0.7)") # Xám mờ hiện đại

        r_s_group = sankey_df.groupby(['Resin', 'Solvent_Type']).size().reset_index(name='count')
        for _, row in r_s_group.iterrows():
            source.append(resin_idx[row['Resin']])
            target.append(solvent_idx[row['Solvent_Type']])
            value.append(row['count'])
            link_colors.append("rgba(226, 232, 240, 0.7)")

        fig_sankey = go.Figure(data=[go.Sankey(
            node = dict(
                pad=30, thickness=20,
                line=dict(color="white", width=1),
                label=node_labels, color=node_colors
            ),
            link = dict(source=source, target=target, value=value, color=link_colors)
        )])
        
        dynamic_height = max(400, min(800, len(node_labels) * 50))
        fig_sankey.update_layout(
            height=dynamic_height, 
            margin=dict(l=20, r=20, t=20, b=20), 
            font=dict(size=12, color="#1E293B", family="Segoe UI, sans-serif"),
            plot_bgcolor='white', paper_bgcolor='white'
        )
        st.plotly_chart(fig_sankey, use_container_width=True, config={'displayModeBar': False})
    
    st.markdown("</div>", unsafe_allow_html=True)


with col_right:
    st.markdown("<div class='content-box'>", unsafe_allow_html=True)
    
    if filtered_df.empty or len(filtered_df) < 2:
        st.info("👈 Please select a valid combination on the left.")
    else:
        avg_init_v = filtered_df[visc_before].mean()
        avg_fin_v = filtered_df[visc_after].mean()
        avg_red = filtered_df['Viscosity_Reduction'].mean()
        avg_solv_add = filtered_df[solvent_weight].mean()
        ref_mean = filtered_df['Reference_Value'].mean()
        
        st.markdown("<div style='font-weight:bold; margin-bottom:10px;'>DETAILED INFORMATION</div>", unsafe_allow_html=True)
        
        # Dynamic Breadcrumb
        v_label = selected_vendor if selected_vendor != 'All' else "All Suppliers"
        r_label = selected_resin if selected_resin != 'All' else "All Resins"
        s_label = selected_solvent if selected_solvent != 'All' else "All Solvents"
        
        html_bc = f"""
<div class='breadcrumb'>
    <div class='bc-item'>{v_label}</div> ➔ 
    <div class='bc-item' style='color:#0D9488; background:#CCFBF1;'>{r_label}</div> ➔ 
    <div class='bc-item' style='color:#7C3AED; background:#EDE9FE;'>{s_label}</div>
</div>
"""
        st.markdown(html_bc, unsafe_allow_html=True)
        
        c_stat, c_ref = st.columns([5.5, 4.5])
        with c_stat:
            st.markdown("<div style='font-size:12px; font-weight:bold; color:#64748B;'>PERFORMANCE STATISTICS</div>", unsafe_allow_html=True)
            html_table = f"""
<table class='info-table'>
    <tr><td>Batch Count</td><td>{total_batches}</td></tr>
    <tr><td>Avg Initial Viscosity</td><td>{avg_init_v:.1f} s</td></tr>
    <tr><td>Avg Adjusted Viscosity</td><td>{avg_fin_v:.1f} s</td></tr>
    <tr><td>Avg Viscosity Drop</td><td>{avg_red:.1f} s</td></tr>
    <tr><td>Avg Solvent Added</td><td>{avg_solv_add:.2f} kg</td></tr>
    <tr class='highlight-row'><td>REFERENCE VALUE <br><span style='font-size:10px; font-weight:normal; color:#64748B;'>(g / kg paint / s)</span></td><td>{ref_mean:.2f} g/kg/s</td></tr>
</table>
"""
            st.markdown(html_table, unsafe_allow_html=True)
            
        with c_ref:
            html_ref = f"""
<div class='ref-card'>
    <div class='ref-title'>💡 REFERENCE MEANING</div>
    <div class='ref-desc'>Average required</div>
    <div class='ref-val'>{ref_mean:.2f} g</div>
    <div class='ref-desc'>of {s_label} solvent<br>per 1 kg of paint<br>to reduce 1 sec<br>of viscosity</div>
</div>
"""
            st.markdown(html_ref, unsafe_allow_html=True)
        
        st.markdown("<hr style='margin:15px 0;'>", unsafe_allow_html=True)
        
        c_scat, c_pred = st.columns([5, 5])
        with c_scat:
            st.markdown("<div style='font-size:12px; font-weight:bold; margin-bottom:5px;'>DATA DISTRIBUTION</div>", unsafe_allow_html=True)
            st.markdown("<div style='font-size:11px; color:#64748B;'>Each point = 1 batch</div>", unsafe_allow_html=True)
            
            fig_scatter = px.scatter(
                filtered_df, x='Viscosity_Reduction', y=solvent_weight, 
                trendline='ols', color_discrete_sequence=['#3B82F6']
            )
            fig_scatter.update_layout(
                height=240, margin=dict(l=0, r=0, t=10, b=0), 
                xaxis_title="Viscosity Drop (s)", yaxis_title="Solvent Added (kg)",
                plot_bgcolor='white', xaxis=dict(showgrid=True, gridcolor='#F1F5F9'), yaxis=dict(showgrid=True, gridcolor='#F1F5F9')
            )
            if len(fig_scatter.data) > 1: # Tweak trendline if statsmodels is present
                fig_scatter.data[1].line.color = 'gray'
                fig_scatter.data[1].line.dash = 'dot'
            st.plotly_chart(fig_scatter, use_container_width=True, config={'displayModeBar': False})
            
        with c_pred:
            st.markdown("<div style='font-size:12px; font-weight:bold; color:#7C3AED; margin-bottom:10px;'>SOLVENT REQUIREMENT PREDICTOR</div>", unsafe_allow_html=True)
            
            col_in1, col_in2 = st.columns([6, 4])
            with col_in1: st.markdown("<div style='font-size:13px; margin-top:10px;'>Current Viscosity (s)</div>", unsafe_allow_html=True)
            with col_in2: curr_v = st.number_input("", value=float(int(avg_init_v)), label_visibility="collapsed")
            
            col_in3, col_in4 = st.columns([6, 4])
            with col_in3: st.markdown("<div style='font-size:13px; margin-top:10px;'>Target Viscosity (s)</div>", unsafe_allow_html=True)
            with col_in4: target_v = st.number_input("", value=float(int(avg_fin_v)), label_visibility="collapsed")
            
            col_in5, col_in6 = st.columns([6, 4])
            with col_in5: st.markdown("<div style='font-size:13px; margin-top:10px;'>Paint Weight (kg)</div>", unsafe_allow_html=True)
            with col_in6: paint_w = st.number_input("", value=800.0, step=50.0, label_visibility="collapsed")
            
            reduction = curr_v - target_v
            recommended_kg = (ref_mean * paint_w * reduction) / 1000 if reduction > 0 else 0
            
            html_result = f"""
<div class='result-box'>
    <div style='font-size:12px; font-weight:bold; color:#065F46;'>Recommended Result</div>
    <div style='font-size:12px; color:#065F46;'>Target Drop: {reduction:.1f} s</div>
    <div style='font-size:12px; color:#065F46;'>Required Solvent:</div>
    <div class='result-val'>➔ {recommended_kg:.2f} kg</div>
    <div style='font-size:12px; color:#065F46;'>({s_label})</div>
</div>
"""
            if reduction > 0:
                st.markdown(html_result, unsafe_allow_html=True)
            else:
                st.warning("Target viscosity must be lower.")

    st.markdown("</div>", unsafe_allow_html=True)
