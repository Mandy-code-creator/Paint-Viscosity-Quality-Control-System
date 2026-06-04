import streamlit as st
import plotly.express as px
import pandas as pd

# =========================
# CHECK DATA
# =========================
if 'raw_data' not in st.session_state:
    st.warning("Please upload data on main page.")
    st.stop()

df = st.session_state['raw_data']

st.header("Process Improvement Analysis (No Spec Required)")

if df.empty:
    st.info("No data available.")
    st.stop()

# =========================
# PREP DATA
# =========================
df = df.copy()
df['Mix_Date'] = pd.to_datetime(df['Mix_Date'])
df = df.sort_values('Mix_Date')

# =========================
# KPI - SHIFT OVERALL
# =========================
df_before = df.groupby('Mix_ID')['Viscosity_Before'].mean()
df_after = df.groupby('Mix_ID')['Viscosity_After'].mean()

overall_before = df['Viscosity_Before'].mean()
overall_after = df['Viscosity_After'].mean()

delta = overall_after - overall_before

c1, c2, c3 = st.columns(3)
c1.metric("Avg Before", f"{overall_before:.1f} s")
c2.metric("Avg After", f"{overall_after:.1f} s")
c3.metric("Δ Change (After - Before)", f"{delta:.1f} s")

st.divider()

# =========================
# 1. SHIFT TREND OVER TIME
# =========================
st.subheader("1. Process Shift Over Time")

trend_df = df.groupby('Mix_Date').agg(
    Before=('Viscosity_Before', 'mean'),
    After=('Viscosity_After', 'mean')
).reset_index()

fig1 = px.line(
    trend_df,
    x='Mix_Date',
    y=['Before', 'After'],
    markers=True,
    title="Viscosity Shift (Before vs After)"
)

fig1.update_layout(
    plot_bgcolor='white',
    paper_bgcolor='white',
    margin=dict(t=60, b=40, l=60, r=20),
    title_x=0.5
)

fig1.update_xaxes(
    tickformat="%Y-%m-%d",
    showgrid=True,
    gridcolor="lightgray"
)

fig1.update_yaxes(
    showgrid=True,
    gridcolor="lightgray"
)

st.plotly_chart(fig1, use_container_width=True)

# =========================
# 2. IMPROVEMENT (Δ PER BATCH)
# =========================
st.subheader("2. Improvement per Batch (After - Before)")

improve_df = df.groupby('Mix_ID').agg(
    Before=('Viscosity_Before', 'mean'),
    After=('Viscosity_After', 'mean')
).reset_index()

improve_df['Delta'] = improve_df['After'] - improve_df['Before']

fig2 = px.bar(
    improve_df,
    x='Mix_ID',
    y='Delta',
    title="Viscosity Change per Batch (Negative = Improvement)",
    color='Delta',
    color_continuous_scale='RdYlGn_r'
)

fig2.update_layout(
    plot_bgcolor='white',
    paper_bgcolor='white',
    margin=dict(t=60, b=40, l=60, r=20),
    title_x=0.5
)

fig2.update_xaxes(showgrid=True, gridcolor="lightgray")
fig2.update_yaxes(showgrid=True, gridcolor="lightgray")

st.plotly_chart(fig2, use_container_width=True)

# =========================
# 3. DISTRIBUTION SHIFT
# =========================
st.subheader("3. Distribution Shift (Process Stability)")

dist_df = df.melt(
    id_vars=['Mix_ID'],
    value_vars=['Viscosity_Before', 'Viscosity_After'],
    var_name='Stage',
    value_name='Viscosity'
)

dist_df['Stage'] = dist_df['Stage'].replace({
    'Viscosity_Before': 'Before',
    'Viscosity_After': 'After'
})

fig3 = px.box(
    dist_df,
    x='Stage',
    y='Viscosity',
    color='Stage',
    title="Before vs After Distribution"
)

fig3.update_layout(
    plot_bgcolor='white',
    paper_bgcolor='white',
    margin=dict(t=60, b=40, l=60, r=20),
    title_x=0.5
)

fig3.update_yaxes(showgrid=True, gridcolor="lightgray")

st.plotly_chart(fig3, use_container_width=True)
