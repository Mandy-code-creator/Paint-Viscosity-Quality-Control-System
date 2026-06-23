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


# --- 4. PRODUCTION ENGINE ---
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

        if pd.isna(baseline_efficiency) or baseline_efficiency <= 0:
            baseline_efficiency = 5.0  
        if pd.isna(max_historical_ratio) or max_historical_ratio <= 0:
            max_historical_ratio = 10.0

        with st.expander("📐 Technical Formulation & Logic Reference"):
            st.markdown("##### **1. Solvent Blending Ratio Formula**")
            st.latex(r"Solvent\ Ratio\ (\%) = \frac{Solvent\ Weight\ (kg)}{Paint\ Weight\ (kg)} \times 100")
            st.markdown(r"##### **2. Recommended Solvent Weight Estimation**")
            st.latex(r"Required\ Solvent\ Weight\ (kg) = \frac{Paint\ Weight\ (kg) \times \left( \frac{\Delta V\ (Required\ Drop)}{Baseline\ Efficiency} \right)}{100}")

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

    else:
        st.info("No data available for the selected combination.")


# --- 5. BIỂU ĐỒ XU HƯỚNG PHI TUYẾN TÍNH (NÂNG CẤP PHÂN TÁCH FACET Ô THEO VENDOR & RESIN) ---
st.markdown("---")
st.subheader("📈 Multi-Vendor Trend Analysis: Viscosity Behavior Matrix")
st.markdown("*The charts are automatically broken down into columns by **Vendor** and rows by **Resin**. Colors distinguish different **Solvent Types** and their respective Before/After stages.*")

if not filtered_df.empty:
    # Sử dụng Plotly Express để tự động tạo hệ thống lưới Facet ô lưới thông minh
    # Tạo bảng dữ liệu tạm để chuẩn hóa nhãn hiển thị cho Legend không bị chồng lấn
    df_plot = filtered_df.copy()
    
    # Định dạng bảng màu động chuẩn quốc tế cho các loại dung môi
    unique_solvents_in_df = df_plot['Solvent_Type'].unique()
    color_palette = px.colors.qualitative.Bold
    
    fig_matrix = px.scatter(
        df_plot,
        x='Solvent_Ratio_Percent',
        y='黏度(秒)',
        facet_col='Vendor',  # Tách biểu đồ thành các cột dựa trên Nhà cung ứng độc lập
        facet_row='Resin',   # Tách biểu đồ thành các hàng dựa trên hệ Nhựa độc lập
        color='Solvent_Type',
        color_discrete_sequence=color_palette,
        labels={'Solvent_Ratio_Percent': 'Solvent Blending Ratio (%)', '黏度(秒)': 'Viscosity (seconds)'},
    )

    # Thêm các cấu trúc đường nối dọc và điểm Sau (After) vào từng ô tương ứng
    # Duyệt qua từng ô subplot để cấu hình chi tiết
    for vendor in df_plot['Vendor'].unique():
        for resin in df_plot['Resin'].unique():
            sub_df = df_plot[(df_plot['Vendor'] == vendor) & (df_plot['Resin'] == resin)]
            if sub_df.empty:
                continue
                
            # Tìm tọa độ ô lưới trong đồ thị Plotly
            # (Plotly sắp xếp index hàng cột tự động dựa trên vị trí xuất hiện)
            
            # Tính toán đường nối dọc cho từng mẻ trong ô này
            x_lines = []
            y_lines = []
            for _, row in sub_df.iterrows():
                if pd.notna(row['Solvent_Ratio_Percent']) and pd.notna(row['黏度(秒)']) and pd.notna(row['黏度(秒)_1']):
                    x_lines.extend([row['Solvent_Ratio_Percent'], row['Solvent_Ratio_Percent'], None])
                    y_lines.extend([row['黏度(秒)'], row['黏度(秒)_1'], None])
            
            # Thêm đường nét đứt vào ô lưới tương ứng thông qua đồ thị gốc
            # Để vẽ chính xác vào từng ô Facet, cách tốt nhất là dùng go.Scatter bổ sung và cập nhật thông số hoành độ
            
    # Để giữ nguyên tính năng kết nối dây dọc chéo điểm Cam-Xanh siêu việt của lượt trước, 
    # chúng ta sẽ xây dựng trực tiếp bằng go.Figure với vòng lặp phân nhóm Vendor-Resin rõ ràng:
    fig_trend = go.Figure()
    
    # Thiết lập bảng màu cố định cho các loại dung môi để đồng bộ màu sắc Trước/Sau
    solvent_colors = {sol: color_palette[i % len(color_palette)] for i, sol in enumerate(unique_solvents)}
    
    # Tạo sơ đồ layout chia cột và hàng thủ công để kiểm soát 100% đường kẻ nối dọc từng mẻ sơn
    unique_v = sorted(filtered_df['Vendor'].unique())
    unique_r = sorted(filtered_df['Resin'].unique())
    
    # Thiết lập lưới Subplots dựa trên số lượng Vendor và Resin thực tế đang chọn
    from plotly.subplots import make_subplots
    fig_trend = make_subplots(
        rows=len(unique_r), 
        cols=len(unique_v),
        shared_xaxes=True,
        shared_yaxes=True,
        subplot_titles=[f"Vendor: {v} | Resin: {r}" for r in unique_r for v in unique_v],
        vertical_spacing=0.08,
        horizontal_spacing=0.04
    )
    
    # Đổ dữ liệu mẻ sơn vào từng ô tương ứng
    for r_idx, resin in enumerate(unique_r):
        for v_idx, vendor in enumerate(unique_v):
            sub_df = filtered_df[(filtered_df['Resin'] == resin) & (filtered_df['Vendor'] == vendor)]
            if sub_df.empty:
                continue
                
            row_num = r_idx + 1
            col_num = v_idx + 1
            
            # 1. Vẽ các đường kẻ dọc nối Before-After cho từng mẻ
            x_lines = []
            y_lines = []
            for _, row in sub_df.iterrows():
                if pd.notna(row['Solvent_Ratio_Percent']) and pd.notna(row['黏度(秒)']) and pd.notna(row['黏度(秒)_1']):
                    x_lines.extend([row['Solvent_Ratio_Percent'], row['Solvent_Ratio_Percent'], None])
                    y_lines.extend([row['黏度(秒)'], row['黏度(秒)_1'], None])
                    
            fig_trend.add_trace(go.Scatter(
                x=x_lines, y=y_lines, mode='lines',
                line=dict(color='lightgray', width=1, dash='dot'),
                hoverinfo='skip', showlegend=False
            ), row=row_num, col=col_num)
            
            # Phân tách theo từng loại dung môi trong ô này
            for solvent in sub_df['Solvent_Type'].unique():
                sol_df = sub_df[sub_df['Solvent_Type'] == solvent]
                sol_color = solvent_colors[solvent]
                
                # Chỉ hiển thị legend 1 lần duy nhất cho mỗi loại dung môi để tránh lặp bảng chú thích
                show_leg = True if (r_idx == 0 and v_idx == 0) else False
                
                # 2. Điểm TRƯỚC khi châm (Ký hiệu hình tròn rỗng hoặc chấm nhạt)
                fig_trend.add_trace(go.Scatter(
                    x=sol_df['Solvent_Ratio_Percent'], y=sol_df['黏度(秒)'],
                    mode='markers',
                    name=f"Solvent {solvent} (Before)" if show_leg else "",
                    legendgroup=f"sol_{solvent}_bef",
                    marker=dict(color=sol_color, size=6, symbol='circle-open', width=1.5),
                    customdata=sol_df[['黏度(秒)_1', 'Viscosity_Reduction', 'Vendor', 'Resin', 'Solvent_Type']].values,
                    hovertemplate='<b>%{customdata[2]} | %{customdata[3]} | Solvent: %{customdata[4]}</b><br>' +
                                  'Solvent Ratio: %{x:.2f}%<br>' +
                                  'Initial Visc (Before): %{y:.1f}s 🌟<br>' +
                                  'Final Visc (After): %{customdata[0]:.1f}s<br>' +
                                  'Viscosity Drop: %{customdata[1]:.1f}s<extra></extra>',
                    showlegend=show_leg
                ), row=row_num, col=col_num)
                
                # 3. Điểm SAU khi châm (Ký hiệu hình tròn đặc, màu đậm hơn)
                fig_trend.add_trace(go.Scatter(
                    x=sol_df['Solvent_Ratio_Percent'], y=sol_df['黏度(秒)_1'],
                    mode='markers',
                    name=f"Solvent {solvent} (After)" if show_leg else "",
                    legendgroup=f"sol_{solvent}_aft",
                    marker=dict(color=sol_color, size=7, symbol='circle'),
                    customdata=sol_df[['黏度(秒)', 'Viscosity_Reduction', 'Vendor', 'Resin', 'Solvent_Type']].values,
                    hovertemplate='<b>%{customdata[2]} | %{customdata[3]} | Solvent: %{customdata[4]}</b><br>' +
                                  'Solvent Ratio: %{x:.2f}%<br>' +
                                  'Initial Visc (Before): %{customdata[0]:.1f}s<br>' +
                                  'Final Visc (After): %{y:.1f}s 🌟<br>' +
                                  'Viscosity Drop: %{customdata[1]:.1f}s<extra></extra>',
                    showlegend=show_leg
                ), row=row_num, col=col_num)

    # Cấu hình Layout tổng thể cho hệ thống ma trận ô
    fig_trend.update_layout(
        plot_bgcolor='white',
        height=350 * len(unique_r) if len(unique_r) > 1 else 450, # Tự động giãn chiều cao theo số hàng Resin
        margin=dict(l=60, r=50, t=80, b=60),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.05,
            xanchor="center", x=0.5,
            bgcolor="rgba(255,255,255,0)"
        ),
        hovermode='closest'
    )
    
    # Đồng bộ hiển thị trục lưới xám cho tất cả các ô con
    fig_trend.update_xaxes(title_text='Solvent Blending Ratio (%)', showgrid=True, gridcolor='#EAEAEA', linecolor='black', row=len(unique_r), col='all')
    fig_trend.update_yaxes(title_text='Viscosity (seconds)', showgrid=True, gridcolor='#EAEAEA', linecolor='black', col=1, row='all')
    fig_trend.update_annotations(font_size=12, font_color='black') # Định dạng tiêu đề của từng ô con rõ nét
    
    st.plotly_chart(fig_trend, use_container_width=True)
else:
    st.info("No filtered data available to generate the matrix trend visualization.")


# --- 6. GLOBAL HISTORICAL REFERENCE MATRIX (BACKGROUND) ---
st.markdown("---")
st.subheader("📚 Global Historical Performance Reference (All Systems)")

agg_funcs = {
    'Batches': pd.NamedAgg(column='塗料批號', aggfunc='nunique'),
    'Total Paint (kg)': pd.NamedAgg(column='塗料重量', aggfunc='sum'),
    'Total Solvent (kg)': pd.NamedAgg(column='添加重量', aggfunc='sum'),
    'Avg Initial V (s)': pd.NamedAgg(column='黏度(秒)', aggfunc='mean'),
    'Avg Final V (s)': pd.NamedAgg(column='黏 độ(秒)_1', aggfunc='mean'),
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
