import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
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

# Data Normalization (Solvent Ratio & Viscosity Reduction)
group_a['Solvent_Ratio_Percent'] = (group_a['添加重量'] / group_a['塗料重量'].replace(0, 1)) * 100
group_a['Viscosity_Reduction'] = group_a['黏度(秒)'] - group_a['黏度(秒)_1']

# Calculate Historical Efficiency per batch (seconds dropped per 1% solvent)
group_a['Historical_Efficiency'] = group_a['Viscosity_Reduction'] / group_a['Solvent_Ratio_Percent'].replace(0, np.nan)


# --- 3. MASTER CONTROL PANEL (UNIFIED SYSTEM SELECTION) ---
st.markdown("---")
st.header("🎯 Master System Selection")
st.markdown("*Select the specific paint system to analyze. This selection automatically powers both the calculator and the trend charts below.*")

# Filter strictly >= 10 batches to ensure statistical reliability
valid_groups = group_a.groupby(['Resin', 'Vendor', 'Solvent_Type']).filter(lambda x: x['塗料批號'].nunique() >= 10)

if valid_groups.empty:
    st.error("❌ No groups found with 10+ historical batches. Please upload a larger dataset.")
    st.stop()

# ĐÃ TỐI ƯU: Gộp chung thành 1 bộ lọc duy nhất cho toàn trang
col_m1, col_m2, col_m3 = st.columns(3)
with col_m1:
    master_resin = st.selectbox("1. Select Resin:", sorted(valid_groups['Resin'].unique()))
with col_m2:
    master_vendor = st.selectbox("2. Select Vendor:", sorted(valid_groups[valid_groups['Resin'] == master_resin]['Vendor'].unique()))
with col_m3:
    master_solvent = st.selectbox("3. Select Solvent Type:", sorted(valid_groups[(valid_groups['Resin'] == master_resin) & (valid_groups['Vendor'] == master_vendor)]['Solvent_Type'].unique()))

# Extract data specifically for the chosen system
system_data = valid_groups[
    (valid_groups['Resin'] == master_resin) & 
    (valid_groups['Vendor'] == master_vendor) & 
    (valid_groups['Solvent_Type'] == master_solvent)
]


# --- 4. PRODUCTION ENGINE (DYNAMIC CALCULATION) ---
st.markdown("---")
st.header("⚙️ Live Production Calculation & Efficiency Monitor")

if not system_data.empty:
    # Establish baseline historical metrics
    baseline_efficiency = system_data['Historical_Efficiency'].median()
    max_historical_ratio = system_data['Solvent_Ratio_Percent'].max()
    viscosity_floor = system_data['黏度(秒)_1'].min()

    # Fallback safe defaults if data is missing or corrupted
    if pd.isna(baseline_efficiency) or baseline_efficiency <= 0:
        baseline_efficiency = 5.0  
    if pd.isna(max_historical_ratio) or max_historical_ratio <= 0:
        max_historical_ratio = 10.0

    with st.expander("📐 Technical Formulation & Logic Reference"):
        st.markdown("##### **1. Solvent Blending Ratio Formula**")
        st.latex(r"Solvent\ Ratio\ (\%) = \frac{Solvent\ Weight\ (kg)}{Paint\ Weight\ (kg)} \times 100")
        st.markdown(r"##### **2. Recommended Solvent Weight Estimation**")
        st.latex(r"Required\ Solvent\ Weight\ (kg) = \frac{Paint\ Weight\ (kg) \times \left( \frac{\Delta V\ (Required\ Drop)}{Baseline\ Efficiency} \right)}{100}")

    # Operator Live Inputs
    st.markdown("### **Input Current Tank Conditions**")
    col_i1, col_i2, col_i3, col_i4 = st.columns(4)
    with col_i1:
        paint_weight = st.number_input("Paint Weight (kg):", min_value=1.0, value=120.0, step=10.0)
    with col_i2:
        current_visc = st.number_input("Current Viscosity (seconds):", min_value=1.0, value=58.0, step=1.0)
    with col_i3:
        target_visc = st.number_input("Target Viscosity (seconds):", min_value=1.0, value=50.0, step=1.0)
    with col_i4:
        delta_v_target = current_visc - target_visc
        st.metric(label="Required Viscosity Drop (Delta V)", value=f"{delta_v_target:.1f} s")

    # Execution Calculation Output
    st.markdown("### **Optimization Results & Safety Verification**")
    if delta_v_target <= 0:
        st.success("✅ **Result:** Current viscosity meets or exceeds target. No solvent addition required.")
    elif target_visc < viscosity_floor:
        st.error(f"🚨 **CRITICAL DANGER:** Requested target ({target_visc}s) is lower than the historical Viscosity Floor ({viscosity_floor:.1f}s). Aborted.")
    else:
        predicted_ratio_needed = delta_v_target / baseline_efficiency
        recommended_solvent_kg = (paint_weight * predicted_ratio_needed) / 100
        yellow_threshold = max_historical_ratio * 0.70
        red_threshold = max_historical_ratio * 0.90

        if predicted_ratio_needed <= yellow_threshold:
            st.success(f"### ✅ **Recommended Solvent:** `{recommended_solvent_kg:.2f} kg` (Optimal Zone)")
        elif predicted_ratio_needed <= red_threshold:
            st.warning(f"### ⚠️ **Recommended Solvent:** `{recommended_solvent_kg:.2f} kg` (Diminishing Return Zone)")
        else:
            st.error(f"### 🚨 **CRITICAL CAP:** `{recommended_solvent_kg:.2f} kg` (Severe Diminishing Return Zone)")

else:
    st.info("System data is unavailable.")


# --- 5. HIGH-RESOLUTION TREND ANALYSIS (AUTO-SYNCED TO MASTER SELECTION) ---
st.markdown("---")
st.subheader(f"📈 High-Resolution Trend Analysis: {master_resin} | {master_vendor} | {master_solvent}")
st.markdown("*This interactive plot visualizes the exact viscosity drop for each batch of the selected system. Hover over points to trace individual batches.*")

if not system_data.empty:
    fig_trend = go.Figure()
    
    sol_color = '#7030A0' # Sử dụng màu tím đậm chuyên nghiệp cho toàn bộ hệ thống đang Focus

    # 1. Vẽ các đường kẻ dọc nối Before-After
    x_lines = []
    y_lines = []
    for _, row in system_data.iterrows():
        if pd.notna(row['Solvent_Ratio_Percent']) and pd.notna(row['黏度(秒)']) and pd.notna(row['黏度(秒)_1']):
            x_lines.extend([row['Solvent_Ratio_Percent'], row['Solvent_Ratio_Percent'], None])
            y_lines.extend([row['黏度(秒)'], row['黏度(秒)_1'], None])
            
    fig_trend.add_trace(go.Scatter(
        x=x_lines, y=y_lines, mode='lines',
        line=dict(color='lightgray', width=1, dash='dot'),
        hoverinfo='skip', showlegend=False
    ))

    # 2. Điểm TRƯỚC khi châm (Vòng tròn rỗng)
    fig_trend.add_trace(go.Scatter(
        x=system_data['Solvent_Ratio_Percent'], y=system_data['黏度(秒)'],
        mode='markers',
        name="Initial Viscosity (Before)",
        marker=dict(color=sol_color, size=9, symbol='circle-open', line=dict(width=2, color=sol_color)),
        customdata=system_data[['黏度(秒)_1', 'Viscosity_Reduction', 'Vendor', 'Resin', 'Solvent_Type']].values,
        hovertemplate='<b>%{customdata[2]} | %{customdata[3]} | Solvent: %{customdata[4]}</b><br>' +
                      'Solvent Ratio: %{x:.2f}%<br>' +
                      'Initial Visc (Before): %{y:.1f}s 🌟<br>' +
                      'Final Visc (After): %{customdata[0]:.1f}s<br>' +
                      'Viscosity Drop: %{customdata[1]:.1f}s<extra></extra>',
    ))
    
    # 3. Điểm SAU khi châm (Vòng tròn đặc)
    fig_trend.add_trace(go.Scatter(
        x=system_data['Solvent_Ratio_Percent'], y=system_data['黏度(秒)_1'],
        mode='markers',
        name="Final Viscosity (After)",
        marker=dict(color=sol_color, size=9, symbol='circle'),
        customdata=system_data[['黏度(秒)', 'Viscosity_Reduction', 'Vendor', 'Resin', 'Solvent_Type']].values,
        hovertemplate='<b>%{customdata[2]} | %{customdata[3]} | Solvent: %{customdata[4]}</b><br>' +
                      'Solvent Ratio: %{x:.2f}%<br>' +
                      'Initial Visc (Before): %{customdata[0]:.1f}s<br>' +
                      'Final Visc (After): %{y:.1f}s 🌟<br>' +
                      'Viscosity Drop: %{customdata[1]:.1f}s<extra></extra>',
    ))

    # 4. Đường xu hướng phi tuyến tính
    sorted_sys_df = system_data.dropna(subset=['Solvent_Ratio_Percent', '黏度(秒)_1']).sort_values(by='Solvent_Ratio_Percent')
    if len(sorted_sys_df) > 3:
        poly_fit = np.polyfit(sorted_sys_df['Solvent_Ratio_Percent'], sorted_sys_df['黏度(秒)_1'], 2)
        poly_curve = np.polyval(poly_fit, sorted_sys_df['Solvent_Ratio_Percent'])
        fig_trend.add_trace(go.Scatter(
            x=sorted_sys_df['Solvent_Ratio_Percent'], y=poly_curve,
            mode='lines',
            name="Non-linear Trend (After)",
            line=dict(color='#C00000', width=2, dash='dash'),
            hoverinfo='skip'
        ))

    # Cấu hình Layout Full-width chuẩn mực
    fig_trend.update_layout(
        plot_bgcolor='white',
        height=500,
        xaxis=dict(title='Solvent Blending Ratio (%)', showgrid=True, gridcolor='#EAEAEA', linecolor='black', linewidth=1),
        yaxis=dict(title='Viscosity (seconds)', showgrid=True, gridcolor='#EAEAEA', linecolor='black', linewidth=1),
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="center", x=0.5,
            bgcolor="rgba(255,255,255,0)"
        ),
        hovermode='closest'
    )
    
    st.plotly_chart(fig_trend, use_container_width=True)
else:
    st.info("No data available to generate the trend visualization.")


# --- 6. GLOBAL HISTORICAL REFERENCE MATRIX (BACKGROUND) ---
st.markdown("---")
st.subheader("📚 Global Historical Performance Reference (All Systems)")

agg_funcs = {
    'Batches': pd.NamedAgg(column='塗料批號', aggfunc='nunique'),
    'Total Paint (kg)': pd.NamedAgg(column='塗料重量', aggfunc='sum'),
    'Total Solvent (kg)': pd.NamedAgg(column='添加重量', aggfunc='sum'),
    'Avg Initial V (s)': pd.NamedAgg(column='黏度(秒)', aggfunc='mean'),
    'Avg Final V (s)': pd.NamedAgg(column='黏度(秒)_1', aggfunc='mean'),
    'Viscosity Floor (s) ⚠️': pd.NamedAgg(column='黏度(秒)_1', aggfunc='min'),
    'Baseline Efficiency (s/%)': pd.NamedAgg(column='Historical_Efficiency', aggfunc='median'),
    'Max Historical Ratio %': pd.NamedAgg(column='Solvent_Ratio_Percent', aggfunc='max')
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
        "Viscosity Floor (s) ⚠️": st.column_config.NumberColumn(format="%.1f"),
        "Baseline Efficiency (s/%)": st.column_config.NumberColumn(format="%.2f"),
        "Max Historical Ratio %": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=30)
    },
    use_container_width=True
)
