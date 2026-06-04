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

st.header("Process Improvement Analysis (Simplified QC View)")

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
# TABLE
# =========================
st.subheader("1. Group Performance Table")

table_df = df.groupby(
    ['Color_Group', 'Resin_Type', 'Supplier', 'Paint_Code_Str']
).agg(
    Total_Mixes=('Mix_ID', 'nunique'),
    Avg_Before=('Viscosity_Before', 'mean'),
    Avg_After=('Viscosity_After', 'mean')
).reset_index()

table_df['Avg_Delta'] = table_df['Avg_After'] - table_df['Avg_Before']

st.dataframe(table_df.round(2), use_container_width=True)

st.divider()

# =========================
# 2. PROCESS SHIFT (2 GROUPS ONLY)
# =========================
st.subheader("2. Process Shift Over Time (Resin → Paint Code)")

df['Mix_Date'] = pd.to_datetime(df['Mix_Date'])
df = df.sort_values('Mix_Date')

resin_list = df['Resin_Type'].dropna().unique()

for resin in resin_list:

    st.markdown(f"## 🔹 Resin: {resin}")
    df_r = df[df['Resin_Type'] == resin]

    paint_list = df_r['Paint_Code_Str'].dropna().unique()

    # =========================
    # 🟢 GROUP 1: NORMAL CHANGE
    # =========================
    st.markdown("### 🟢 Normal Change")

    for paint in paint_list:

        df_p = df_r[df_r['Paint_Code_Str'] == paint]

        if df_p.empty:
            continue

        df_change = df_p[df_p['Viscosity_Before'] != df_p['Viscosity_After']]

        if df_change.empty:
            continue

        st.markdown(f"#### 🧪 Paint Code: {paint}")

        trend_df = df_change.groupby('Mix_Date').agg(
            Before=('Viscosity_Before', 'mean'),
            After=('Viscosity_After', 'mean')
        ).reset_index()

        fig = px.line(
            trend_df,
            x='Mix_Date',
            y=['Before', 'After'],
            markers=True,
            title=f"{resin} / {paint}"
        )

        fig.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(t=40, b=40, l=50, r=20),
            title_x=0.5
        )

        st.plotly_chart(fig, use_container_width=True)

    # =========================
    # ⚪ GROUP 2: NO EFFECT / INVALID DATA (MERGED)
    # =========================
    st.markdown("### ⚪ No Effect / Invalid Data (Detail View)")

no_effect_df = df_r[
    (df_r['Viscosity_Before'] == df_r['Viscosity_After']) |
    (df_r['黏度(秒)_1'].isna())
].copy()

if not no_effect_df.empty:

    # =========================
    # ADD DIAGNOSIS COLUMN
    # =========================
    no_effect_df['Issue_Type'] = no_effect_df.apply(
        lambda x: "Missing Data" if pd.isna(x['黏度(秒)_1']) else "No Change",
        axis=1
    )

    display_df = no_effect_df[[
        'Mix_ID',
        'Paint_Code_Str',
        'Mix_Date',
        'Viscosity_Before',
        'Viscosity_After',
        '黏度(秒)_1',
        'Issue_Type'
    ]].sort_values('Mix_Date')

    st.dataframe(display_df, use_container_width=True)

    # =========================
    # SUMMARY WITH VALUE INSIGHT
    # =========================
    value_summary = no_effect_df.groupby('Paint_Code_Str').agg(
        Count=('Mix_ID', 'nunique'),
        Avg_Before=('Viscosity_Before', 'mean'),
        Avg_After=('Viscosity_After', 'mean')
    ).reset_index()

    value_summary['Delta'] = value_summary['Avg_After'] - value_summary['Avg_Before']

    st.markdown("#### 📊 Impact Summary (Value View)")
    st.dataframe(value_summary.round(2), use_container_width=True)

    st.info("Shows actual viscosity values so you can assess severity of No Effect / Missing cases.")
