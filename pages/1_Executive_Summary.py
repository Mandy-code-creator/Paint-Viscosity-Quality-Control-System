import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. SETUP & DATA RETRIEVAL ---
if 'raw_data_loaded' not in st.session_state or not st.session_state['raw_data_loaded']:
    st.warning("⚠️ Please upload data on the main page (App) first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()
rejected_data = st.session_state['rejected_data'].copy()

# Global calculations for Sensitivity
group_a['Solvent_Ratio_Percent'] = (group_a['添加重量'] / group_a['塗料重量']) * 100
group_a['Sensitivity'] = group_a['Delta_V'] / (group_a['Solvent_Ratio_Percent'].replace(0, 1))

st.title("📊 Executive Summary")
st.markdown("---")

# --- 2. KPI METRICS ---
st.subheader("💡 Key Performance Indicators")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="Total Valid Batches", value=f"{len(group_a):,} batches")
with col2:
    st.metric(label="Total Paint Used", value=f"{group_a['塗料重量'].sum():,.1f} kg")
with col3:
    st.metric(label="Avg Solvent Ratio", value=f"{(group_a['Solvent_Ratio_Percent'].mean()):.2f} %")
with col4:
    st.metric(label="Data Errors (Rejected)", value=f"{len(rejected_data)} rows")

st.markdown("---")

# --- 3. HEATMAP ANALYSIS (MULTI-DIMENSIONAL) ---
st.subheader("🌡️ Process Sensitivity Heatmap")

# Filters
unique_resins = group_a['Resin'].unique()
unique_vendors = group_a['Vendor'].unique()

col_f1, col_f2 = st.columns(2)
with col_f1:
    selected_resin = st.selectbox("Filter Heatmap by Resin", unique_resins, index=0)
with col_f2:
    selected_vendors = st.multiselect("Filter Heatmap by Vendor", unique_vendors, default=unique_vendors)

# Filter data
filtered_data = group_a[
    (group_a['Resin'] == selected_resin) & 
    (group_a['Vendor'].isin(selected_vendors))
].copy()

if not filtered_data.empty:
    tab_formula, tab_env = st.tabs(["🧪 Optimal Formula (Viscosity vs Solvent)", "🌤️ Environmental Impact (Temp vs Humidity)"])
    
    # ==========================================
    # TAB 1: OPTIMAL FORMULA (VISCOSITY VS SOLVENT)
    # ==========================================
    with tab_formula:
        # Manual Bins: Define clean, readable intervals
        solvent_bins = [0, 2, 4, 6, 8, 10, 12, 15, 20]
        viscosity_bins = [50, 70, 90, 110, 130, 150, 170, 190, 210, 250]

        filtered_data['Solvent_Bin'] = pd.cut(filtered_data['Solvent_Ratio_Percent'], bins=solvent_bins)
        filtered_data['Initial_V_Bin'] = pd.cut(filtered_data['黏度(秒)'], bins=viscosity_bins)

        heatmap_data = filtered_data.groupby(['Initial_V_Bin', 'Solvent_Bin'], observed=False)['Sensitivity'].mean().reset_index()
        pivot_table = heatmap_data.pivot(index='Initial_V_Bin', columns='Solvent_Bin', values='Sensitivity')

        correct_x_order = [str(col) for col in pivot_table.columns]
        correct_y_order = [str(idx) for idx in pivot_table.index]

        pivot_table.index = pivot_table.index.astype(str)
        pivot_table.columns = pivot_table.columns.astype(str)

        fig_heatmap = px.imshow(
            pivot_table, text_auto=".1f", aspect="auto", color_continuous_scale='RdYlGn',
            labels=dict(x="Solvent Ratio (%)", y="Initial Viscosity (s)", color="Sensitivity"),
            title=f"Efficiency based on Initial Viscosity ({selected_resin})"
        )
        fig_heatmap.update_xaxes(categoryorder='array', categoryarray=correct_x_order)
        fig_heatmap.update_yaxes(categoryorder='array', categoryarray=correct_y_order)

        st.plotly_chart(fig_heatmap, use_container_width=True)
        
        st.info("""
        **SOP Calculation Guide:**
        1. Measure the actual initial viscosity of the current batch.
        2. Locate the deepest green cell (highest sensitivity) for that viscosity tier on the heatmap.
        3. Determine the target Solvent Ratio (%) from the horizontal axis.
        
        **Formula:** **Required Solvent (kg) = Paint Weight (kg) × Target Solvent Ratio (%)**
        """)

        with st.expander("🧮 Quick Calculator", expanded=False):
            c1, c2, c3 = st.columns(3)
            with c1:
                paint_weight = st.number_input("1. Paint Weight (kg)", min_value=0.0, value=200.0, step=10.0)
            with c2:
                optimal_ratio = st.number_input("2. Target Ratio (%)", min_value=0.0, value=7.0, step=0.5)
            with c3:
                required_solvent = paint_weight * (optimal_ratio / 100)
                st.success(f"**Required Solvent:**\n### {required_solvent:.2f} kg")

    # ==========================================
    # TAB 2: ENVIRONMENTAL IMPACT (TEMP VS HUMIDITY)
    # ==========================================
    with tab_env:
        # Update these column names if your dataset uses different headers for temperature and humidity
        temp_col = '溫度' 
        hum_col = '濕度'
        
        if temp_col in filtered_data.columns and hum_col in filtered_data.columns:
            temp_bins = [15, 20, 25, 30, 35, 40]
            hum_bins = [40, 50, 60, 70, 80, 90, 100]

            filtered_data['Temp_Bin'] = pd.cut(filtered_data[temp_col], bins=temp_bins)
            filtered_data['Hum_Bin'] = pd.cut(filtered_data[hum_col], bins=hum_bins)

            heatmap_env = filtered_data.groupby(['Hum_Bin', 'Temp_Bin'], observed=False)['Sensitivity'].mean().reset_index()
            pivot_env = heatmap_env.pivot(index='Hum_Bin', columns='Temp_Bin', values='Sensitivity')

            env_x_order = [str(col) for col in pivot_env.columns]
            env_y_order = [str(idx) for idx in pivot_env.index]

            pivot_env.index = pivot_env.index.astype(str)
            pivot_env.columns = pivot_env.columns.astype(str)

            fig_env = px.imshow(
                pivot_env, text_auto=".1f", aspect="auto", color_continuous_scale='RdYlGn',
                labels=dict(x="Temperature (°C)", y="Humidity (%)", color="Sensitivity"),
                title=f"Environmental Impact on Solvent Efficiency ({selected_resin})"
            )
            fig_env.update_xaxes(categoryorder='array', categoryarray=env_x_order)
            fig_env.update_yaxes(categoryorder='array', categoryarray=env_y_order)

            st.plotly_chart(fig_env, use_container_width=True)
            
            st.caption("💡 **Observation:** Watch for low sensitivity (red zones) at extreme temperatures, as rapid solvent evaporation may occur before viscosity is reduced.")
        else:
            st.error(f"Environmental columns ('{temp_col}' or '{hum_col}') not found in the dataset. Please check your column headers.")

else:
    st.warning("No data available for the selected filters.")

st.markdown("---")

# --- 4. RESIN & VENDOR PERFORMANCE ANALYSIS ---
st.markdown("---")
st.subheader("📋 Resin & Vendor Performance Analysis")

# Sử dụng bản sao dữ liệu
matrix_df = group_a.copy()

# TỰ ĐỘNG PHÁT HIỆN TÊN CỘT MÃ SƠN
# Thay vì ép buộc tên cột, ta kiểm tra danh sách cột có sẵn trong file
possible_names = ['塗料代碼', '塗料代碼(Paint Code)', 'Paint Code', 'Item Code']
paint_code_col = next((col for col in matrix_df.columns if col in possible_names), None)

# Hàm giải mã (giữ nguyên logic chuẩn)
def get_clean_application(code_str):
    if not isinstance(code_str, str) or len(str(code_str).strip()) < 4: return 'Unknown/Other'
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

# Cập nhật Application
if paint_code_col:
    matrix_df['Application'] = matrix_df[paint_code_col].apply(get_clean_application)
else:
    # Nếu không tìm thấy cột mã sơn, báo lỗi rõ ràng để bạn biết tên cột thực là gì
    matrix_df['Application'] = f"Not Found: {list(matrix_df.columns)[:3]}"

# Đảm bảo các cột môi trường (nếu chưa có thì tạo giá trị mặc định để tránh lỗi)
for col in ['溫度', '濕度', 'Solvent_Type']:
    if col not in matrix_df.columns: matrix_df[col] = 'N/A'

# Grouping
detailed_summary = matrix_df.groupby(['Resin', 'Vendor', 'Application', 'Solvent_Type']).agg({
    '塗料批號': 'nunique', '塗料重量': 'sum', '添加重量': 'sum',
    '黏度(秒)': 'mean', '黏度(秒)_1': 'mean',
    '溫度': 'mean', '濕度': 'mean',
    'Solvent_Ratio_Percent': 'mean', 'Sensitivity': 'mean'
}).rename(columns={
    '塗料批號': 'Batches', '塗料重量': 'Total Paint (kg)', '添加重量': 'Total Solvent (kg)',
    '黏度(秒)': 'Initial V (s)', '黏度(秒)_1': 'Final V (s)',
    '溫度': 'Avg Temp (°C)', '濕度': 'Avg Humidity (%)',
    'Solvent_Ratio_Percent': 'Avg Solvent %', 'Sensitivity': 'Avg Sensitivity'
})

detailed_summary['Solvent % / 1s Drop'] = detailed_summary['Avg Sensitivity'].apply(lambda x: (1.0 / x) if x > 0 else 0)
detailed_summary = detailed_summary.drop(columns=['Avg Sensitivity'])

st.dataframe(detailed_summary.style.format({
    'Total Paint (kg)': '{:,.0f}', 'Total Solvent (kg)': '{:,.0f}',
    'Initial V (s)': '{:.2f}', 'Final V (s)': '{:.2f}',
    'Avg Temp (°C)': '{:.1f}', 'Avg Humidity (%)': '{:.1f}',
    'Avg Solvent %': '{:.2f} %', 'Solvent % / 1s Drop': '{:.3f} %'
}), use_container_width=True)

# --- 5. SMART RECOMMENDATION ENGINE (MULTI-FACTOR) ---
st.markdown("---")
st.subheader("🧠 Smart Recommendation Engine")
st.caption("Calculates the Theoretical Value of solvent required to hit a specific target viscosity based on historical environmental data.")

with st.container():
    # User Inputs
    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
    with col_m1:
        curr_viscosity = st.number_input("Current Viscosity (s)", value=55.0, step=1.0)
    with col_m2:
        target_viscosity = st.number_input("Target Viscosity (s)", value=52.0, step=1.0)
    with col_m3:
        curr_temp = st.number_input("Temp (°C)", value=32.0, step=1.0)
    with col_m4:
        curr_humidity = st.number_input("Humidity (%)", value=85.0, step=5.0)
    with col_m5:
        coil_paint_qty = st.number_input("Coil Paint Weight (kg)", value=200.0, step=10.0)

    # Logic Calculation
    if target_viscosity >= curr_viscosity:
        st.info("Target viscosity is higher than or equal to current viscosity. No solvent required.")
    else:
        viscosity_drop = curr_viscosity - target_viscosity
        
        # Base filter: Resin and Vendor
        base_subset = group_a[
            (group_a['Resin'] == selected_resin) &
            (group_a['Vendor'].isin(selected_vendors))
        ]
        
        # Define condition masks
        visc_mask = (base_subset['黏度(秒)'] >= curr_viscosity - 15) & (base_subset['黏度(秒)'] <= curr_viscosity + 15)
        
        weather_mask = True
        if '溫度' in base_subset.columns and '濕度' in base_subset.columns:
            weather_mask = (base_subset['溫度'] >= curr_temp - 5) & (base_subset['溫度'] <= curr_temp + 5) & \
                           (base_subset['濕度'] >= curr_humidity - 10) & (base_subset['濕度'] <= curr_humidity + 10)
        
        # --- FALLBACK ALGORITHM ---
        # Attempt 1: Strict Match (Viscosity + Weather)
        subset_strict = base_subset[visc_mask & weather_mask]
        
        # Attempt 2: Partial Match (Viscosity only)
        subset_partial = base_subset[visc_mask]
        
        # Attempt 3: General Match (Resin/Vendor overall average)
        subset_general = base_subset
        
        expected_sensitivity = 0
        match_level = ""
        
        # Cascade through attempts to find valid historical data
        if not subset_strict.empty and subset_strict['Sensitivity'].mean() > 0:
            expected_sensitivity = subset_strict['Sensitivity'].mean()
            match_level = "High (Matched Viscosity & Environment)"
        elif not subset_partial.empty and subset_partial['Sensitivity'].mean() > 0:
            expected_sensitivity = subset_partial['Sensitivity'].mean()
            match_level = "Medium (Matched Viscosity only, ignoring environment)"
        elif not subset_general.empty and subset_general['Sensitivity'].mean() > 0:
            expected_sensitivity = subset_general['Sensitivity'].mean()
            match_level = "Low (Based on overall Resin average)"
            
        # Final Output Generation
        if expected_sensitivity > 0:
            theoretical_ratio = viscosity_drop / expected_sensitivity
            theoretical_solvent_kg = coil_paint_qty * (theoretical_ratio / 100)

            st.success(f"""
            ### 🎯 Theoretical Value to Add: {theoretical_solvent_kg:.2f} kg
            
            **Calculation Breakdown:**
            * Required Viscosity Drop: **{viscosity_drop:.1f} s**
            * Historical Sensitivity: **{expected_sensitivity:.2f} s reduction per 1% solvent**
            * Theoretical Solvent Ratio: **{theoretical_ratio:.2f}%**
            * Data Confidence: **{match_level}**
            """)
        else:
            st.error("Unable to calculate Theoretical Value. Historical sensitivity data is invalid or missing.")
            
# --- 6. COMPREHENSIVE REFERENCE MATRIX (SOP LOOKUP) ---
st.markdown("---")
st.subheader("📚 SOP Coefficient Matrix (Coil-Level)")
st.caption("A robust lookup table providing a standard 'Solvent Factor' for ALL resins and clean applications. Multiply this factor by your required viscosity drop to get the exact Theoretical Value of solvent.")

with st.container():
    c_ref1, c_ref2 = st.columns([1, 2])
    with c_ref1:
        ref_coil_weight = st.number_input("Standard Coil Paint Weight (kg)", value=200.0, step=10.0)

    matrix_data = []
    matrix_df = group_a.copy()

    # Paint code column configuration
    paint_code_col = '塗料代碼' 
    
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
        
        if char_4.isdigit():
            return 'General Usage'
            
        return f_map.get(char_4, 'Unknown/Other')

    if paint_code_col in matrix_df.columns:
        matrix_df['Application'] = matrix_df[paint_code_col].apply(get_clean_application)
    elif 'Feature' in matrix_df.columns:
        # Strip out any legacy tail format text from the string if present
        matrix_df['Application'] = matrix_df['Feature'].astype(str).apply(lambda x: x.split(' (')[0] if '(' in x else x)
    else:
        matrix_df['Application'] = 'Unknown/Other'

    def generate_dynamic_bins(series):
        if len(series) < 4:
            return pd.cut(series, bins=1, precision=0)
        try:
            return pd.qcut(series, q=4, precision=0, duplicates='drop')
        except ValueError:
            return pd.cut(series, bins=4, precision=0)

    matrix_df['Viscosity_Zone'] = matrix_df.groupby('Resin')['黏度(秒)'].transform(generate_dynamic_bins)

    grouping_cols = ['Resin', 'Vendor', 'Application', 'Viscosity_Zone']
    has_solvent_type = 'Solvent_Type' in matrix_df.columns
    if has_solvent_type:
        grouping_cols.insert(2, 'Solvent_Type')

    target_viscosity_map = matrix_df.groupby(['Resin', 'Vendor', 'Application'])['黏度(秒)_1'].median().reset_index()
    target_viscosity_map = target_viscosity_map.rename(columns={'黏度(秒)_1': 'Typical_Target'})

    sensitivity_map = matrix_df.groupby(grouping_cols, observed=False)['Sensitivity'].mean().reset_index()
    sensitivity_map = sensitivity_map[sensitivity_map['Sensitivity'] > 0]

    sop_grouped = pd.merge(sensitivity_map, target_viscosity_map, on=['Resin', 'Vendor', 'Application'], how='inner')

    for _, row in sop_grouped.iterrows():
        sens = row['Sensitivity']
        theo_ratio_per_sec = 1.0 / sens
        factor_kg_per_sec = ref_coil_weight * (theo_ratio_per_sec / 100.0)

        record = {
            'Resin': row['Resin'],
            'Vendor': row['Vendor'],
            'Application': row['Application'],
            'Current Viscosity Zone': str(row['Viscosity_Zone']),
            'Typical Target (s)': round(row['Typical_Target'], 1),
            'Sensitivity Applied (s/%)': round(sens, 2),
            'Solvent Factor (kg / 1s drop)': round(factor_kg_per_sec, 3)
        }
        if has_solvent_type:
            record['Solvent Type'] = row['Solvent_Type']

        matrix_data.append(record)

    df_matrix = pd.DataFrame(matrix_data)

    if not df_matrix.empty:
        cols = df_matrix.columns.tolist()
        if has_solvent_type:
            cols.insert(2, cols.pop(cols.index('Solvent Type')))
        df_matrix = df_matrix[cols]

        df_matrix = df_matrix.sort_values(by=['Resin', 'Vendor', 'Application', 'Current Viscosity Zone'])

        st.dataframe(df_matrix.style.format({
            'Typical Target (s)': '{:.1f}',
            'Sensitivity Applied (s/%)': '{:.2f}',
            'Solvent Factor (kg / 1s drop)': '{:.3f}'
        }), use_container_width=True)

        st.info("""
        **SOP Execution Guide:**
        1. Measure the coil's current viscosity.
        2. Calculate the drop: `(Current Viscosity - Typical Target)`.
        3. Match the current viscosity to the correct `Viscosity Zone` row.
        4. **Theoretical Value (kg) = Required Drop × Solvent Factor**
        """)

        csv = df_matrix.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Coefficient Matrix as CSV",
            data=csv,
            file_name='SOP_Coefficient_Matrix_Clean.csv',
            mime='text/csv',
        )
    else:
        st.warning("Not enough valid historical data to generate the SOP Coefficient Matrix.")
