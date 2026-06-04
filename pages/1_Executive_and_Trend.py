import streamlit as st
import plotly.express as px
import pandas as pd
from data_processing import render_sidebar_filters

# =====================
# CHECK DATA
# =====================
if 'raw_data' not in st.session_state:
    st.warning("Please upload data on the main page.")
    st.stop()

df = render_sidebar_filters(st.session_state['raw_data'])

st.header("Executive Dashboard & Trend Analysis")

if df.empty:
    st.info("No data available for the selected filters.")
    st.stop()

# =====================
# SUMMARY TABLE
# =====================
st.subheader("Paint Code Performance Summary")

summary_df = df.groupby(
    ['Color_Group', 'Resin_Type', 'Supplier', 'Paint_Code_Str']
).agg(
    Total_Mixes=('Mix_ID', 'nunique'),
    Avg_Before=('Viscosity_Before', 'mean'),
    Avg_After=('Viscosity_After', 'mean'),
    Avg_Reduction=('Reduction', 'mean')
).reset_index().round(1)

st.dataframe(summary_df, use_container_width=True)
st.divider()

# =====================
# KPI
# =====================
df_adjusted = df[df['Adjustment_Status'] == 'Adjusted']
df_pass = df[df['Adjustment_Status'] == 'Pass (No Thinner)']

first_time_right_pct = (len(df_pass) / len(df)) * 100 if len(df) > 0 else 0

c1, c2, c3, c4 = st.columns(4)

# ✅ FIXED (NO len on nunique)
c1.metric("Total Mixes", df['Mix_ID'].nunique())
c2.metric("First Time Right (%)", f"{first_time_right_pct:.1f}%")
c3.metric("Avg Viscosity Before", f"{df['Viscosity_Before'].mean():.1f}")
c4.metric("Total Thinner", f"{df_adjusted['Thinner_Added'].sum():.1f}")

st.divider()

# =====================
# TREND CHART (SEPARATE PLOTS)
# =====================
st.subheader("Viscosity Trend by Paint Code")

if not df_adjusted.empty:

    df_adjusted['Mix_Date'] = pd.to_datetime(df_adjusted['Mix_Date'])
    df_adjusted = df_adjusted.sort_values('Mix_Date')

    resin_types = df_adjusted['Resin_Type'].dropna().unique()

    for resin in resin_types:

        st.markdown(f"### Resin: {resin}")

        df_resin = df_adjusted[df_adjusted['Resin_Type'] == resin]

        paint_codes = df_resin['Paint_Code_Str'].unique()

        for pc in paint_codes:

            df_pc = df_resin[df_resin['Paint_Code_Str'] == pc]

            df_melt = df_pc.melt(
                id_vars=['Mix_Date', 'Supplier'],
                value_vars=['Viscosity_Before', 'Viscosity_After'],
                var_name='Stage',
                value_name='Viscosity'
            )

            df_melt['Stage'] = df_melt['Stage'].replace({
                'Viscosity_Before': 'Before',
                'Viscosity_After': 'After'
            })

            fig = px.line(
                df_melt,
                x='Mix_Date',
                y='Viscosity',
                color='Stage',
                symbol='Supplier',
                markers=True,
                color_discrete_map={
                    'Before': '#FF4B4B',
                    'After': '#00BFFF'
                },
                title=f"{pc}"
            )

            fig.update_layout(
                plot_bgcolor='white',
                paper_bgcolor='white',
                margin=dict(t=50, b=40, l=60, r=20),
                title_x=0.5
            )

            fig.update_xaxes(
                tickformat="%Y-%m-%d",
                showgrid=True,
                gridcolor="lightgray",
                showline=True,
                linecolor="black",
                mirror=True
            )

            fig.update_yaxes(
                showgrid=True,
                gridcolor="lightgray",
                showline=True,
                linecolor="black",
                mirror=True
            )

            fig.update_traces(line=dict(width=2), marker=dict(size=6))

            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("No adjusted data available.")
