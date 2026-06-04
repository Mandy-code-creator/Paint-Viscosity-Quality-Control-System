import streamlit as st
import plotly.express as px
import pandas as pd
from data_processing import render_sidebar_filters

if 'raw_data' not in st.session_state:
    st.warning("Please upload data on the main page.")
    st.stop()

df = render_sidebar_filters(st.session_state['raw_data'])

st.header("Executive Dashboard & Trend Analysis")

if df.empty:
    st.info("No data available for the selected filters.")
    st.stop()

# --- Bảng phân tích chi tiết Trước/Sau theo Mã Sơn ---
st.subheader("Paint Code Performance Summary")
st.markdown("Detailed breakdown of viscosity reduction by Paint Code and Supplier.")

summary_df = df.groupby(['Color_Group', 'Resin_Type', 'Supplier', 'Paint_Code_Str']).agg(
    Total_Mixes=('Mix_ID', 'nunique'),
    Avg_Before=('Viscosity_Before', 'mean'),
    Avg_After=('Viscosity_After', 'mean'),
    Avg_Reduction=('Reduction', 'mean')
).reset_index()

summary_df['Avg_Before'] = summary_df['Avg_Before'].round(1)
summary_df['Avg_After'] = summary_df['Avg_After'].round(1)
summary_df['Avg_Reduction'] = summary_df['Avg_Reduction'].round(1)

st.dataframe(summary_df, use_container_width=True)

st.divider()

df_adjusted = df[df['Adjustment_Status'] == 'Adjusted']
df_pass = df[df['Adjustment_Status'] == 'Pass (No Thinner)']
first_time_right_pct = (len(df_pass) / len(df)) * 100 if len(df) > 0 else 0

# KPIs
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Paint Mixes", len(df['Mix_ID'].unique()))
c2.metric("First-Time Right (%)", f"{first_time_right_pct:.1f}%", "No Thinner Needed")
c3.metric("Avg Viscosity Before", f"{df['Viscosity_Before'].mean():.1f} sec")
c4.metric("Total Thinner Added", f"{df_adjusted['Thinner_Added'].sum():.1f} kg")

st.divider()

# --- Biểu đồ xu hướng NÂNG CẤP ---
st.subheader("Viscosity Trend Over Time by Resin Type")
st.markdown("Tracks adjusted mixes. **Color** = Before/After | **Symbol** = Supplier | **Hover** = Paint Code")

if not df_adjusted['Mix_Date'].isna().all() and not df_adjusted.empty:
    resin_types = sorted(df_adjusted['Resin_Type'].dropna().unique())
    
    if len(resin_types) > 0:
        tabs = st.tabs([f"Resin: {r}" for r in resin_types])
        
        for i, resin in enumerate(resin_types):
            with tabs[i]:
                df_resin_trend = df_adjusted[df_adjusted['Resin_Type'] == resin].copy()
                
                if not df_resin_trend.empty:
                    # BƯỚC QUAN TRỌNG: Ép kiểu datetime và sắp xếp tuyệt đối để chống lỗi zigzag
                    df_resin_trend['Mix_Date'] = pd.to_datetime(df_resin_trend['Mix_Date'])
                    df_resin_trend = df_resin_trend.sort_values(by=['Mix_Date', 'Mix_ID'])
                    df_resin_trend['Mix_Date_Str'] = df_resin_trend['Mix_Date'].dt.strftime('%Y-%m-%d')
                    
                    # Melt dữ liệu
                    df_melt = df_resin_trend.melt(
                        id_vars=['Mix_Date_Str', 'Mix_Date', 'Mix_ID', 'Paint_Code_Str', 'Supplier', 'Thinner_Added'],
                        value_vars=['Viscosity_Before', 'Viscosity_After'],
                        var_name='Measurement_Stage',
                        value_name='Viscosity'
                    )
                    
                    df_melt['Measurement_Stage'] = df_melt['Measurement_Stage'].replace({
                        'Viscosity_Before': 'Before',
                        'Viscosity_After': 'After'
                    })
                    
                    # Sắp xếp lại df_melt một lần nữa để giữ chuẩn trục thời gian
                    df_melt = df_melt.sort_values(by=['Mix_Date', 'Mix_ID'])
                    
                    fig_trend = px.line(
                        df_melt, 
                        x='Mix_Date_Str', 
                        y='Viscosity', 
                        color='Measurement_Stage', # Màu sắc chia theo Trước/Sau
                        color_discrete_map={'Before': '#FF4B4B', 'After': '#00BFFF'}, # Đỏ San Hô & Deep Sky Blue
                        symbol='Supplier',         # Ký hiệu theo Supplier
                        line_group='Paint_Code_Str', # KHÓA LINE GROUP: Chống vẽ đan chéo giữa các mã sơn
                        markers=True,
                        hover_data=['Paint_Code_Str', 'Mix_ID', 'Thinner_Added'],
                        title=f"Viscosity Trend (Before vs After) for {resin}"
                    )
                    
                    fig_trend.update_traces(
                        line=dict(width=2.5), 
                        marker=dict(size=9, line=dict(width=1.5, color='white'))
                    )
                    
                    fig_trend.update_layout(
                        xaxis_title="Mixing Date", 
                        yaxis_title="Viscosity (sec)", 
                        hovermode="x unified",
                        xaxis=dict(type='category'),
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        margin=dict(l=20, r=20, t=40, b=20),
                        legend_title_text='Stage & Supplier'
                    )
                    
                    fig_trend.update_xaxes(
                        showline=True, linewidth=1, linecolor='black', mirror=True, 
                        showgrid=True, gridwidth=1, gridcolor='LightGray'
                    )
                    fig_trend.update_yaxes(
                        showline=True, linewidth=1, linecolor='black', mirror=True, 
                        showgrid=True, gridwidth=1, gridcolor='LightGray'
                    )
                    
                    st.plotly_chart(fig_trend, use_container_width=True)
                else:
                    st.info(f"No adjusted data available for Resin: {resin} in this period.")
    else:
        st.info("No resin types identified.")
else:
    st.info("Insufficient adjusted data for trend analysis in this period/color.")
