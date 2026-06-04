import streamlit as st
import plotly.express as px
import pandas as pd
from data_processing import render_sidebar_filters

# =========================
# CHECK DATA
# =========================
if 'raw_data' not in st.session_state:
    st.warning("Please upload data on main page.")
    st.stop()

# =========================
# FILTER
# =========================
df = render_sidebar_filters(st.session_state['raw_data'])

st.header("Process Improvement Analysis (No Spec Required)")

if df.empty:
    st.info("No data available.")
    st.stop()

# =========================
# PREP
# =========================
df = df.copy()
df['Mix_Date'] = pd.to_datetime(df['Mix_Date'])
df = df.sort_values('Mix_Date')

# =========================
# KPI
# =========================
overall_before = df['Viscosity_Before'].mean()
overall_after = df['Viscosity_After'].mean()
delta = overall_after - overall_before

c1, c2, c3 = st.columns(3)
c1.metric("Avg Before", f"{overall_before:.1f} s")
c2.metric("Avg After", f"{overall_after:.1f} s")
c3.metric("Δ Change", f"{delta:.1f} s")

st.divider()

# =========================
# 📊 TABLE (GROUP ANALYSIS)
# =========================
st.subheader("1. Group Performance Table (Color / Resin / Supplier / Paint Code)")

table_df = df.groupby(
    ['Color_Group', 'Resin_Type', 'Supplier', 'Paint_Code_Str']
).agg(
    Total_Mixes=('Mix_ID', 'nunique'),
    Avg_Before=('Viscosity_Before', 'mean'),
    Avg_After=('Viscosity_After', 'mean'),
    Avg_Delta=('Viscosity_After', lambda x: None)  # placeholder fixed below
).reset_index()

# FIX delta properly
table_df['Avg_Delta'] = table_df['Avg_After'] - table_df['Avg_Before']

table_df = table_df.round(2)

st.dataframe(table_df, use_container_width=True)

st.divider()

# =========================
st.subheader("2. Process Shift Over Time (Resin → Paint Code)")

df['Mix_Date'] = pd.to_datetime(df['Mix_Date'])
df = df.sort_values('Mix_Date')

resin_list = df['Resin_Type'].dropna().unique()

for resin in resin_list:

    st.markdown(f"## 🔹 Resin: {resin}")
    df_r = df[df['Resin_Type'] == resin]

    paint_list = df_r['Paint_Code_Str'].dropna().unique()

    for paint in paint_list:

        st.markdown(f"### 🧪 Paint Code: {paint}")

        df_p = df_r[df_r['Paint_Code_Str'] == paint]

        if df_p.empty:
            continue

        trend_df = df_p.groupby('Mix_Date').agg(
            Before=('Viscosity_Before', 'mean'),
            After=('Viscosity_After', 'mean')
        ).reset_index()

        fig = px.line(
            trend_df,
            x='Mix_Date',
            y=['Before', 'After'],
            markers=True,
            title=f"{resin} / {paint} (Before vs After)"
        )

        fig.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(t=40, b=40, l=50, r=20),
            title_x=0.5
        )

        fig.update_xaxes(
            tickformat="%Y-%m-%d",
            showgrid=True,
            gridcolor="lightgray"
        )

        fig.update_yaxes(
            showgrid=True,
            gridcolor="lightgray"
        )

        st.plotly_chart(fig, use_container_width=True)

# =========================
# 3. IMPROVEMENT PER BATCH
# =========================
st.subheader("3. Improvement per Batch")

improve_df = df.groupby('Mix_ID').agg(
    Before=('Viscosity_Before', 'mean'),
    After=('Viscosity_After', 'mean')
).reset_index()

improve_df['Delta'] = improve_df['After'] - improve_df['Before']

fig2 = px.bar(
    improve_df,
    x='Mix_ID',
    y='Delta',
    color='Delta',
    color_continuous_scale='RdYlGn_r',
    title="Batch Improvement (After - Before)"
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
# 4. DISTRIBUTION SHIFT
# =========================
st.subheader("4. Distribution Shift (Stability)")

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
