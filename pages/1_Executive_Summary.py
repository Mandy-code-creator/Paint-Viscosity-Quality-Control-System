import streamlit as st
import plotly.express as px
import pandas as pd

# Cấu hình trang
st.set_page_config(page_title="Viscosity Analysis Report", page_icon="🔬", layout="wide")

st.title("🔬 Viscosity Analysis Report")
st.markdown("Detailed breakdown of solvent sensitivity per resin type. Each chart represents a specific resin's reaction to different solvents.")

# 1. State Check & Data Loading
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please upload your data file first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()

# Ép kiểu dữ liệu để biểu đồ không bị dàn trải (Category/String)
group_a['Solvent_Type'] = group_a['Solvent_Type'].astype(str)

# ==========================================
# --- BƯỚC LÀM SẠCH DỮ LIỆU (DATA CLEANING) ---
# ==========================================
visc_before = '黏度(秒)'     # Độ nhớt trước khi pha
visc_after = '黏度(秒)_1'   # Độ nhớt sau khi pha
paint_weight = '塗料重量'    # Trọng lượng sơn
solvent_weight = '添加重量'  # Trọng lượng dung môi

# Kiểm tra xem các cột có tồn tại không trước khi làm sạch
if all(col in group_a.columns for col in [visc_before, visc_after, paint_weight, solvent_weight]):
    # 1. Loại bỏ các dòng bị trống (Null/NA)
    clean_data = group_a.dropna(subset=[visc_before, visc_after]).copy()

    # 2. Loại bỏ các dòng có giá trị bằng 0 (Sơn, Dung môi, Độ nhớt)
    clean_data = clean_data[
        (clean_data[visc_before] > 0) & 
        (clean_data[visc_after] > 0) & 
        (clean_data[paint_weight] > 0) & 
        (clean_data[solvent_weight] > 0)
    ]

    # 3. Loại bỏ các dòng mà Độ nhớt trước và sau GIỐNG Y HỆT NHAU
    clean_data = clean_data[clean_data[visc_before] != clean_data[visc_after]]

    group_a = clean_data.copy()
    st.caption("🧹 **Hệ thống tự động:** Đã lọc bỏ các dữ liệu rác (Giá trị trống, bằng 0, hoặc độ nhớt không thay đổi).")
else:
    st.warning("⚠️ Bỏ qua bước làm sạch do không tìm thấy đủ các cột: Độ nhớt, Trọng lượng sơn, Trọng lượng dung môi.")
# ==========================================

# Đảm bảo cột Vendor tồn tại (tránh lỗi nếu data thiếu)
if 'Vendor' not in group_a.columns:
    group_a['Vendor'] = 'Unknown'

# 2. Logic: Nhóm dữ liệu 
# Sử dụng toàn bộ dữ liệu sạch để so sánh hiệu quả giữa các loại dung môi
summary_df = group_a.groupby(['Resin', 'Solvent_Type'])['Viscosity_Sensitivity'].agg(['mean', 'std']).reset_index()
resins = sorted(summary_df['Resin'].unique())

# 3. Định nghĩa bảng màu cố định cho từng loại dung môi
all_solvents = sorted(group_a['Solvent_Type'].unique())
color_map = {solvent: px.colors.qualitative.Plotly[i % len(px.colors.qualitative.Plotly)] 
             for i, solvent in enumerate(all_solvents)}

# 4. Hiển thị báo cáo dạng lưới 2 cột
st.markdown("---")
for i in range(0, len(resins), 2):
    cols = st.columns(2)
    for j in range(2):
        if i + j < len(resins):
            resin = resins[i + j]
            with cols[j]:
                st.markdown(f"#### Resin Type: {resin}")
                
                # --- A. BIỂU ĐỒ BAR CHART (ĐỘ NHẠY) ---
                resin_data = summary_df[summary_df['Resin'] == resin].copy()
                
                fig_bar = px.bar(
                    resin_data,
                    x='Solvent_Type',
                    y='mean',
                    error_y='std',
                    labels={'mean': 'Sensitivity (sec/1%)', 'Solvent_Type': 'Solvent'},
                    color='Solvent_Type',
                    color_discrete_map=color_map,
                    title=f"Sensitivity Profile for {resin}"
                )
                
                # Cấu hình chuẩn báo cáo
                fig_bar.update_layout(
                    plot_bgcolor='white', height=300, font=dict(size=12),
                    margin=dict(l=40, r=40, t=40, b=30), showlegend=False
                )
                fig_bar.update_xaxes(type='category', showline=True, linecolor='black', linewidth=1)
                fig_bar.update_yaxes(showgrid=True, gridcolor='lightgray', linecolor='black', linewidth=1)
                
                st.plotly_chart(fig_bar, use_container_width=True)
                
                # --- B. BẢNG DỮ LIỆU ---
                st.dataframe(
                    resin_data.rename(columns={'mean': 'Mean', 'std': 'Std Dev'}),
                    use_container_width=True,
                    height=150
                )

                # --- C. BIỂU ĐỒ SCATTER KÈM ĐƯỜNG XU HƯỚNG ---
                st.markdown(f"**📈 Trend: Paint vs Solvent Usage ({resin})**")
                
                # Lọc dữ liệu thô cho loại nhựa hiện tại
                resin_raw_data = group_a[group_a['Resin'] == resin].copy()
                
                if not resin_raw_data.empty and paint_weight in resin_raw_data.columns and solvent_weight in resin_raw_data.columns:
                    try:
                        # Dùng color & symbol gom chung vào 1 chart để không bị dính chữ trên layout hẹp
                        fig_trend = px.scatter(
                            resin_raw_data,
                            x=paint_weight,
                            y=solvent_weight,
                            color='Solvent_Type',
                            symbol='Vendor',
                            trendline='ols', # Đường xu hướng tuyến tính
                            color_discrete_map=color_map,
                            labels={
                                paint_weight: 'Paint Weight (kg)',
                                solvent_weight: 'Solvent Added (kg)',
                                'Solvent_Type': 'Solvent',
                                'Vendor': 'Vendor'
                            }
                        )
                        
                        fig_trend.update_layout(
                            plot_bgcolor='white', 
                            height=350,
                            margin=dict(l=40, r=40, t=10, b=30),
                            legend=dict(
                                orientation="h", # Chuyển chú thích nằm ngang bên dưới
                                yanchor="top", y=-0.2, 
                                xanchor="center", x=0.5
                            )
                        )
                        fig_trend.update_xaxes(showline=True, linecolor='black', showgrid=True, gridcolor='lightgray')
                        fig_trend.update_yaxes(showline=True, linecolor='black', showgrid=True, gridcolor='lightgray')
                        
                        st.plotly_chart(fig_trend, use_container_width=True)
                        
                    except Exception as e:
                        st.error("⚠️ Lỗi vẽ xu hướng. Vui lòng cài đặt 'statsmodels' (chạy lệnh: `pip install statsmodels`).")
                else:
                    st.info("Không đủ dữ liệu Trọng lượng sơn/dung môi để vẽ biểu đồ.")
                    
    st.markdown("---") # Gạch ngang phân cách giữa các hàng Resins
