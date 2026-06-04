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

# Bảng phân tích chi tiết Trước/Sau theo Mã Sơn
st.subheader("Paint Code Performance Summary")
summary_df = df.groupby(['Color_Group', 'Resin_Type', 'Supplier', 'Paint_Code_Str']).agg(
    Total_Mixes=('Mix_ID', 'nunique'),
    Avg_Before=('Viscosity_Before', 'mean'),
    Avg_After=('Viscosity_After', 'mean'),
    Avg_Reduction=('Reduction', 'mean')
).reset_index().round(1)

st.dataframe(summary_df, use_container_width=True)

st.divider()

df_adjusted = df[df['Adjustment_Status'] == 'Adjusted']
df_pass = df[df['Adjustment_Status'] == 'Pass (No Thinner)']
first_time_right_pct = (len(df_pass) / len(df)) * 100 if len(df) > 0 else 0

# KPIs
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Paint Mixes", len(df['Mix_ID'].unique()))
c2.metric("First-Time Right (%)", f"{first_time_right_pct:.1f}%")
c3.metric("Avg Viscosity Before", f"{df['Viscosity_Before'].mean():.1f} sec")
c4.metric("Total Thinner Added", f"{df_adjusted['Thinner_Added'].sum():.1f} kg")

st.divider()

# --- BIỂU ĐỒ NÂNG CẤP: FACET GRID (Tách riêng mỗi Paint Code 1 biểu đồ) ---
st.subheader("Viscosity Trend by Paint Code")
st.markdown("Each Paint Code is plotted individually to eliminate overlapping lines.")

if not df_adjusted.empty:
    resin_types = sorted(df_adjusted['Resin_Type'].dropna().unique())
    
    if len(resin_types) > 0:
        tabs = st.tabs([f"Resin: {r}" for r in resin_types])
        
        for i, resin in enumerate(resin_types):
            with tabs[i]:
                df_resin = df_adjusted[df_adjusted['Resin_Type'] == resin].copy()
                df_resin['Mix_Date'] = pd.to_datetime(df_resin['Mix_Date'])
                
                # Melt để có 2 cột Viscosity và Measurement_Stage
                df_melt = df_resin.melt(
                    id_vars=['Mix_Date', 'Paint_Code_Str', 'Supplier'],
                    value_vars=['Viscosity_Before', 'Viscosity_After'],
                    var_name='Stage', value_name='Viscosity'
                )
                df_melt['Stage'] = df_melt['Stage'].replace({'Viscosity_Before': 'Before', 'Viscosity_After': 'After'})
                
                # Vẽ biểu đồ lưới (Facet Grid)
                fig = px.line(
                    df_melt, x='Mix_Date', y='Viscosity',
                    color='Stage',
                    symbol='Supplier',
                    facet_col='Paint_Code_Str',
                    facet_col_wrap=3,
                    markers=True,
                    color_discrete_map={'Before': '#FF4B4B', 'After': '#00BFFF'}
                )
                
                # --- NÂNG CẤP: TÁCH TRỤC VÀ TẠO KHUNG BAO ---
                fig.update_xaxes(matches=None, showticklabels=True) # Mỗi biểu đồ có trục X riêng
                
                # Làm sạch tiêu đề
                fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
                
                fig.update_traces(line=dict(width=2), marker=dict(size=7))
                
                # Cấu hình khung bao và đường kẻ
                fig.update_layout(
                    plot_bgcolor='white',
                    height=400 * (len(df_resin['Paint_Code_Str'].unique()) // 3 + 1),
                    margin=dict(t=80, b=50, l=50, r=20), # Tăng margin để không bị đè chữ
                    title_text=f"Viscosity Trend by Paint Code (Resin: {resin})",
                    title_x=0.5
                )
                
                # Vẽ khung bao (Mirror) và lưới rõ nét cho từng khung
                fig.update_xaxes(
                    showline=True, linecolor='black', linewidth=1, mirror=True,
                    showgrid=True, gridcolor='lightgray'
                )
                fig.update_yaxes(
                    showline=True, linecolor='black', linewidth=1, mirror=True,
                    showgrid=True, gridcolor='lightgray'
                )
                
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data for current resin.")
else:
    st.info("No adjusted data available.")
