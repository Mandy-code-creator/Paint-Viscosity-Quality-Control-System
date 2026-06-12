import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

# ==========================================
# 1. PAGE CONFIGURATION & CUSTOM CSS
# ==========================================
st.set_page_config(page_title="Solvent Adjustment Intelligence", layout="wide")

custom_css = """
<style>
    /* Light gray app background */
    .stApp { background-color: #F4F7F9; font-family: 'Segoe UI', sans-serif; }
    
    /* Reduce default Streamlit padding */
    .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 98%; }
    
    /* Main Titles */
    .main-title { font-size: 24px; font-weight: 800; color: #1E293B; margin-bottom: 5px; }
    .sub-title { font-size: 14px; color: #64748B; margin-bottom: 20px; }
    
    /* Metric Cards */
    .metric-card {
        background-color: white;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
        border: 1px solid #E2E8F0;
        display: flex;
        flex-direction: column;
        justify-content: center;
        height: 100px;
    }
    .metric-title { font-size: 13px; color: #64748B; font-weight: 600; margin-bottom: 5px;}
    .metric-value { font-size: 24px; font-weight: 700; color: #0F172A; margin:0;}
    .metric-trend-up { font-size: 12px; color: #10B981; font-weight: 600;}
    
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
    .info-table { width: 100%; font-size: 13px; color: #334155; }
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
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ==========================================
# 2. HEADER & FILTERS
# ==========================================
c_title, c_filt1, c_filt2, c_filt3, c_filt4, c_upd = st.columns([3, 1.5, 1.5, 1.5, 2, 1])

with c_title:
    st.markdown("<div class='main-title'>SOLVENT ADJUSTMENT INTELLIGENCE</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-title'>Flow Relationship: Supplier ➔ Resin ➔ Solvent</div>", unsafe_allow_html=True)

with c_filt1: st.selectbox("Supplier", ["All", "Yungchi", "CCP", "Nan Ya"])
with c_filt2: st.selectbox("Resin Type", ["All", "PE", "EPOXY", "PU"])
with c_filt3: st.selectbox("Solvent", ["All", "5203", "CB5203", "ISOPHORONE"])
with c_filt4: st.text_input("Time Period", "01/01/2024  ➔  12/31/2024")
with c_upd:
    st.markdown("<div style='font-size:12px; color:#64748B; margin-top:25px;'><i class='fas fa-clock'></i> Last updated<br><b>05/20/2024 10:30</b></div>", unsafe_allow_html=True)

# ==========================================
# 3. KPI CARDS
# ==========================================
k1, k2, k3, k4, k5 = st.columns(5)

k1.markdown("""
<div class='metric-card'>
    <div class='metric-title'>Total Batches</div>
    <div style='display:flex; justify-content:space-between; align-items:baseline;'>
        <p class='metric-value'>1,248</p>
        <span class='metric-trend-up'>↑ 12.5%</span>
    </div>
</div>""", unsafe_allow_html=True)

k2.markdown("""
<div class='metric-card'>
    <div class='metric-title'>Total Solvent Used</div>
    <div style='display:flex; justify-content:space-between; align-items:baseline;'>
        <p class='metric-value'>48,520 kg</p>
        <span class='metric-trend-up'>↑ 8.3%</span>
    </div>
</div>""", unsafe_allow_html=True)

k3.markdown("<div class='metric-card'><div class='metric-title'>Resin Types</div><p class='metric-value'>12</p></div>", unsafe_allow_html=True)
k4.markdown("<div class='metric-card'><div class='metric-title'>Solvent Types</div><p class='metric-value'>8</p></div>", unsafe_allow_html=True)
k5.markdown("<div class='metric-card'><div class='metric-title'>Suppliers</div><p class='metric-value'>6</p></div>", unsafe_allow_html=True)

st.write("") # Spacer

# ==========================================
# 4. MAIN LAYOUT (TWO COLUMNS)
# ==========================================
col_left, col_right = st.columns([6, 4], gap="large")

# ------------------------------------------
# LEFT COLUMN: SANKEY DIAGRAM
# ------------------------------------------
with col_left:
    st.markdown("""
    <div style='background:white; padding:20px; border-radius:12px; border:1px solid #E2E8F0;'>
        <div style='font-weight:bold; color:#1E293B; font-size:16px;'>RELATIONSHIP: SUPPLIER ➔ RESIN ➔ SOLVENT</div>
        <div style='font-size:12px; color:#64748B; margin-bottom:15px;'>Flow thickness represents batch count</div>
        
        <div style='display:flex; justify-content:space-between; margin-bottom:0px; padding:0 30px;'>
            <div class='pill-header pill-blue' style='width:150px;'>SUPPLIER</div>
            <div class='pill-header pill-teal' style='width:150px;'>RESIN TYPE</div>
            <div class='pill-header pill-purple' style='width:150px;'>SOLVENT</div>
        </div>
    """, unsafe_allow_html=True)

    # Mock Data for Design Representation
    labels = ["Yungchi (420)", "CCP (310)", "Nan Ya (210)", "Atul (150)", "Formosa (100)", "Other (58)", # 0-5
              "PE (320)", "EPOXY (280)", "PU (210)", "PVDF (150)", "SMP (120)", "Other (168)", # 6-11
              "5203 (420)", "CB5203 (310)", "ISOPHORONE (250)", "PMA (220)", "BUTYL (180)", "BAC (150)"] # 12-17
    
    node_colors = ["#3B82F6"]*6 + ["#14B8A6"]*6 + ["#C4B5FD"]*6
    
    source = [0, 0, 1, 1, 2, 3, 6, 6, 7, 7, 8, 9]
    target = [6, 7, 7, 8, 9, 10, 12, 13, 13, 14, 15, 16]
    value  = [200, 220, 150, 160, 210, 150, 200, 120, 100, 180, 210, 150]
    
    fig = go.Figure(data=[go.Sankey(
        node = dict(
            pad = 20, thickness = 25,
            line = dict(color = "white", width = 0),
            label = labels,
            color = node_colors
        ),
        link = dict(
            source = source, target = target, value = value,
            color = "rgba(226, 232, 240, 0.6)" 
        )
    )])
    
    fig.update_layout(height=450, margin=dict(l=20, r=20, t=10, b=10), font=dict(size=11, color="black"))
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------
# RIGHT COLUMN: METRICS & PREDICTION
# ------------------------------------------
with col_right:
    st.markdown("<div class='content-box'>", unsafe_allow_html=True)
    
    st.markdown("<div style='font-weight:bold; margin-bottom:10px;'>DETAILED INFORMATION</div>", unsafe_allow_html=True)
    # Breadcrumb
    st.markdown("""
        <div class='breadcrumb'>
            <div class='bc-item'>Yungchi</div> ➔ 
            <div class='bc-item' style='color:#0D9488; background:#CCFBF1;'>PE</div> ➔ 
            <div class='bc-item' style='color:#7C3AED; background:#EDE9FE;'>5203</div>
        </div>
    """, unsafe_allow_html=True)
    
    c_stat, c_ref = st.columns([6, 4])
    with c_stat:
        st.markdown("<div style='font-size:12px; font-weight:bold; color:#64748B;'>PERFORMANCE STATISTICS</div>", unsafe_allow_html=True)
        st.markdown("""
        <table class='info-table'>
            <tr><td>Batch Count</td><td>186</td></tr>
            <tr><td>Avg Initial Viscosity</td><td>45.2 s</td></tr>
            <tr><td>Avg Adjusted Viscosity</td><td>39.1 s</td></tr>
            <tr><td>Avg Viscosity Drop</td><td>6.1 s</td></tr>
            <tr><td>Avg Solvent Added</td><td>3.42 kg</td></tr>
            <tr class='highlight-row'><td>REFERENCE VALUE <span style='font-size:10px; font-weight:normal;'>(g / kg paint / s)</span></td><td>1.08 g/kg/s</td></tr>
        </table>
        """, unsafe_allow_html=True)
        
    with c_ref:
        st.markdown("""
        <div class='ref-card'>
            <div class='ref-title'>💡 REFERENCE MEANING</div>
            <div class='ref-desc'>Average required</div>
            <div class='ref-val'>1.08 g</div>
            <div class='ref-desc'>of 5203 solvent<br>per 1 kg of paint<br>to reduce 1 sec<br>of viscosity</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<hr style='margin:15px 0;'>", unsafe_allow_html=True)
    
    c_scat, c_pred = st.columns([5, 5])
    
    with c_scat:
        st.markdown("<div style='font-size:12px; font-weight:bold; margin-bottom:5px;'>DATA DISTRIBUTION</div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:11px; color:#64748B;'>Each point = 1 batch</div>", unsafe_allow_html=True)
        
        np.random.seed(42)
        scatter_x = np.random.uniform(4, 12, 100)
        scatter_y = scatter_x * 0.5 + np.random.normal(0, 0.8, 100)
        df_scatter = pd.DataFrame({'drop': scatter_x, 'added': scatter_y})
        
        fig_scatter = px.scatter(df_scatter, x='drop', y='added', trendline='ols', color_discrete_sequence=['#3B82F6'])
        fig_scatter.update_layout(
            height=220, margin=dict(l=0, r=0, t=10, b=0), 
            xaxis_title="Viscosity Drop (s)", yaxis_title="Solvent Added (kg)",
            plot_bgcolor='white', xaxis=dict(showgrid=True, gridcolor='#F1F5F9'), yaxis=dict(showgrid=True, gridcolor='#F1F5F9')
        )
        fig_scatter.data[1].line.color = 'gray'
        fig_scatter.data[1].line.dash = 'dot'
        st.plotly_chart(fig_scatter, use_container_width=True, config={'displayModeBar': False})
        
    with c_pred:
        st.markdown("<div style='font-size:12px; font-weight:bold; color:#7C3AED; margin-bottom:10px;'>SOLVENT REQUIREMENT PREDICTOR</div>", unsafe_allow_html=True)
        
        col_in1, col_in2 = st.columns([6, 4])
        with col_in1: st.markdown("<div style='font-size:13px; margin-top:10px;'>Current Viscosity (s)</div>", unsafe_allow_html=True)
        with col_in2: curr_v = st.number_input("", value=45, label_visibility="collapsed")
        
        col_in3, col_in4 = st.columns([6, 4])
        with col_in3: st.markdown("<div style='font-size:13px; margin-top:10px;'>Target Viscosity (s)</div>", unsafe_allow_html=True)
        with col_in4: target_v = st.number_input("", value=40, label_visibility="collapsed")
        
        col_in5, col_in6 = st.columns([6, 4])
        with col_in5: st.markdown("<div style='font-size:13px; margin-top:10px;'>Paint Weight (kg)</div>", unsafe_allow_html=True)
        with col_in6: paint_w = st.number_input("", value=800, label_visibility="collapsed")
        
        # Calculate
        reduction = curr_v - target_v
        recommended_kg = (1.08 * paint_w * reduction) / 1000 if reduction > 0 else 0
        
        st.markdown(f"""
        <div class='result-box'>
            <div style='font-size:12px; font-weight:bold; color:#065F46;'>Recommended Result</div>
            <div style='font-size:12px; color:#065F46;'>Target Drop: {reduction} s</div>
            <div style='font-size:12px; color:#065F46;'>Required Solvent:</div>
            <div class='result-val'>➔ {recommended_kg:.2f} kg</div>
            <div style='font-size:12px; color:#065F46;'>(5203)</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
