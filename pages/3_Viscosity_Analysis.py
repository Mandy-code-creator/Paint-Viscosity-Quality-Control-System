import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Viscosity & SOP Report", page_icon="📊", layout="wide")
st.title("📊 Viscosity & SOP Analysis Dashboard")
st.markdown("Production-driven regression, dynamic recommendation engine, and optimized workshop SOP matrix.")

# --- 2. DATA VALIDATION ---
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please upload your data file first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()
group_a['Solvent_Type'] = group_a['Solvent_Type'].astype(str)

# STEP 1: Data Normalization (Solvent Ratio & Viscosity Reduction)
group_a['Solvent_Ratio_Percent'] = (group_a['添加重量'] / group_a['塗料重量'].replace(0, 1)) * 100
group_a['Viscosity_Reduction'] = group_a['黏度(秒)'] - group_a['黏度(秒)_1']

# Step 2: Calculate Historical Efficiency per batch (seconds dropped per 1% solvent)
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


# --- 4. PRODUCTION ENGINE & OPTIMIZED WORKSHOP SOP MATRIX ---
st.markdown("---")
st.header("⚙️ Live Production Calculation & Efficiency Monitor")

# Filter combinations that strictly have >= 10 batches to ensure statistical reliability
valid_groups = group_a.groupby(['Resin', 'Vendor', 'Solvent_Type']).filter(lambda x: x['塗料批號'].nunique() >= 10)

if valid_groups.empty:
    st.info("No groups found with 10+ historical batches to run the production engine.")
else:
    # Dropdowns for specific batch execution
    st.markdown("### **Step 1: Select Target Paint System**")
    col_e1, col_e2, col_e3 = st.columns(3)
    with col_e1:
        engine_resin = st.selectbox("Execution Resin:", sorted(valid_groups['Resin'].unique()))
    with col_e2:
        engine_vendor = st.selectbox("Execution Vendor:", sorted(valid_groups[valid_groups['Resin'] == engine_resin]['Vendor'].unique()))
    with col_e3:
        engine_solvent = st.selectbox("Execution Solvent Type:", sorted(valid_groups[(valid_groups['Resin'] == engine_resin) & (valid_groups['Vendor'] == engine_vendor)]['Solvent_Type'].unique()))

    # Extract historical parameters properly for the selected group
    group_data = valid_groups[
        (valid_groups['Resin'] == engine_resin) & 
        (valid_groups['Vendor'] == engine_vendor) & 
        (valid_groups['Solvent_Type'] == engine_solvent)
    ]
    
    if not group_data.empty:
        # Establish baseline historical metrics for comparison
        baseline_efficiency = group_data['Historical_Efficiency'].median()
        max_historical_ratio = group_data['Solvent_Ratio_Percent'].max()
        viscosity_floor = group_data['黏度(秒)_1'].min()

        # Fallback safe defaults if data is missing or corrupted
        if pd.isna(baseline_efficiency) or baseline_efficiency <= 0:
            baseline_efficiency = 5.0  
        if pd.isna(max_historical_ratio) or max_historical_ratio <= 0:
            max_historical_ratio = 10.0

        # --- TECHNICAL FORMULA DISPLAY PANEL ---
        with st.expander("📐 Technical Formulation & Logic Reference"):
            st.markdown("##### **1. Solvent Blending Ratio Formula**")
            st.latex(r"Solvent\ Ratio\ (\%) = \frac{Solvent\ Weight\ (kg)}{Paint\ Weight\ (kg)} \times 100")
            st.markdown(r"##### **2. Recommended Solvent Weight Estimation**")
            st.latex(r"Required\ Solvent\ Weight\ (kg) = \frac{Paint\ Weight\ (kg) \times \left( \frac{\Delta V\ (Required\ Drop)}{Baseline\ Efficiency} \right)}{100}")

        # Operator Live Inputs
        st.markdown("### **Step 2: Input Current Tank Conditions (Dynamic Calc)**")
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

        # EXECUTION CALCULATION
        st.markdown("### **Step 3: Dynamic Calculation Output**")
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

        # --- ĐÃ TỐI ƯU HÓA TOÀN DIỆN: XUẤT BẢNG SOP CAO CẤP CHO NHÀ XƯỞNG ---
        st.markdown("---")
        st.header("📋 Standard SOP Reference Matrix for Workshop Layout")
        st.markdown(f"**Target System:** Resin: `{engine_resin}` | Vendor: `{engine_vendor}` | Solvent: `{engine_solvent}`")
        st.markdown("*This matrix provides clean, pre-calculated numerical values (in kg) for workshop operators. Visual risk boundaries are mapped natively using cell colors.*")

        # Define standard workshop baselines for table generation
        standard_paint_weights = [50, 100, 150, 200, 250, 300, 400, 500]  # Rows (kg)
        standard_delta_v = [2, 4, 6, 8, 10, 12]  # Columns (seconds drop)

        sop_data = []
        for w in standard_paint_weights:
            row_dict = {"Paint Weight (kg)": f"{w} kg"}
            for dv in standard_delta_v:
                ratio_needed = dv / baseline_efficiency
                solvent_kg = (w * ratio_needed) / 100
                row_dict[f"Drop {dv}s"] = float(solvent_kg) # Giữ giá trị số thuần túy để format sạch vẽ màu
            sop_data.append(row_dict)

        sop_df = pd.DataFrame(sop_data)
        
        # Hàm nội bộ áp dụng ma trận màu sắc Pastel chuyên nghiệp (Không lỗi phụ thuộc thư viện)
        def style_sop_matrix(df):
            styles = pd.DataFrame('', index=df.index, columns=df.columns)
            for col in df.columns:
                if col == 'Paint Weight (kg)':
                    continue
                try:
                    dv = float(col.replace('Drop ', '').replace('s', ''))
                except:
                    continue
                for idx in df.index:
                    try:
                        w_val = float(str(df.loc[idx, 'Paint Weight (kg)']).replace(' kg', ''))
                        ratio = dv / baseline_efficiency
                        if ratio > max_historical_ratio * 0.90:
                            styles.loc[idx, col] = 'background-color: #FCE4D6; color: #C00000; font-weight: bold;' # Soft Light Red
                        elif ratio > max_historical_ratio * 0.70:
                            styles.loc[idx, col] = 'background-color: #FFF2CC; color: #7F6000;' # Soft Light Yellow
                        else:
                            styles.loc[idx, col] = 'background-color: #E2F0D9; color: #385723;' # Soft Light Green
                    except:
                        pass
            return styles

        # Áp dụng bộ định dạng số hiển thị đuôi "kg" đồng bộ
        formatter = {col: "{:.2f} kg" for col in sop_df.columns if col != 'Paint Weight (kg)'}
        
        # Xuất bảng SOP tối ưu hóa lên giao diện
        st.dataframe(
            sop_df.style.apply(style_sop_matrix, axis=None).format(formatter),
            use_container_width=True,
            hide_index=True
        )
        
        st.markdown("""
        <div style="background-color: #F8F9FA; padding: 12px; border-left: 4px solid #00BFFF; border-radius: 4px;">
            <span style="font-weight: bold; color: #333333;">🎨 Color Coding Guide for Operators on the Shop Floor:</span><br/>
            🟢 <b>Soft Green Cells:</b> Optimal Zone. High dilution performance. Safe to proceed.<br/>
            🟡 <b>Soft Yellow Cells:</b> Diminishing Return Zone. Efficiency is dropping. <b>Action:</b> Add 80% of the target weight first, mix, and re-test.<br/>
            🔴 <b>Soft Red Cells:</b> Severe Risk Zone. Saturation overload. <b>Action:</b> Do NOT add this volume. Stop and consult the quality supervisor.
        </div>
        """, unsafe_allow_html=True)

    else:
        st.info("No data available for the selected combination.")


# --- 5. HISTORICAL BACKGROUND REFERENCE MATRIX ---
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
