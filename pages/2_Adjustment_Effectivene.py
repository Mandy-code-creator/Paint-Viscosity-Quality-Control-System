import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. GUARDRAIL ---
if 'raw_data_loaded' not in st.session_state or not st.session_state['raw_data_loaded']:
    st.warning("⚠️ Please upload data on the main page (app) first.")
    st.stop()

# --- 2. DATA RETRIEVAL ---
group_a = st.session_state['group_a_data']
df = group_a.copy()

# --- 3. DYNAMIC SIDEBAR FILTERS ---
st.sidebar.header("🔍 Data Filters")

# Vendor Filter
vendors = sorted([v for v in df['Vendor'].unique() if v != 'Unknown'])
selected_vendor = st.sidebar.selectbox("Vendor", ["All"] + vendors)
df_v = df[df['Vendor'] == selected_vendor] if selected_vendor != "All" else df

# Resin Filter
resins = sorted([r for r in df_v['Resin'].unique() if r != 'Unknown'])
selected_resin = st.sidebar.selectbox("Resin", ["All"] + resins)
df_vr = df_v[df_v['Resin'] == selected_resin] if selected_resin != "All" else df_v

# Feature (Application) Filter
features = sorted([f for f in df_vr['Feature'].unique() if f not in ['Unknown', 'General']])
selected_feature = st.sidebar.selectbox("Application", ["All"] + features)
df_vrf = df_vr[df_vr['Feature'] == selected_feature] if selected_feature != "All" else df_vr

# Solvent Type Filter
solvents = sorted([s for s in df_vrf['Solvent_Type'].unique() if s != 'Unknown'])
selected_solvent = st.sidebar.selectbox("Solvent Type", ["All"] + solvents)

# --- 4. APPLY DATA FILTERS ---
filtered_df = df_vrf.copy()
if selected_solvent != "All":
    filtered_df = filtered_df[filtered_df['Solvent_Type'] == selected_solvent]

# --- 5. MAIN UI ---
st.title("Solvent Adjustment Efficiency")

if filtered_df.empty:
    st.info("No data matches the selected filters. Please adjust your Sidebar.")
    st.stop()

# KPIs
col1, col2 = st.columns(2)
with col1:
    avg_solvent = (filtered_df['Solvent_Ratio'].mean() * 100)
    st.metric("Avg Solvent Ratio", f"{avg_solvent:.2f} %")
with col2:
    avg_delta_v = filtered_df['Delta_V'].mean()
    st.metric("Avg Viscosity Drop (\u0394V)", f"{avg_delta_v:.2f} s")

st.markdown("---")

# --- 6. VISUALIZATION ---
st.subheader("Top 5 Resin & Solvent Combinations by Consumption")

# Calculate data
combination_consumption = filtered_df.groupby(['Resin', 'Solvent_Type'])['Solvent_Ratio'].mean().reset_index()
combination_consumption['Solvent_Ratio'] = combination_consumption['Solvent_Ratio'] * 100
combination_consumption['Label'] = combination_consumption['Resin'] + " (" + combination_consumption['Solvent_Type'] + ")"
combination_consumption = combination_consumption.sort_values(by='Solvent_Ratio', ascending=False).head(5)

# Bar Chart
fig = px.bar(
    combination_consumption, 
    x='Label', 
    y='Solvent_Ratio',
    labels={'Solvent_Ratio': 'Avg Solvent Ratio (%)', 'Label': 'Resin + Solvent Type'},
    text_auto='.2f',
    color_discrete_sequence=['deepskyblue'] 
)

fig.update_layout(
    xaxis_title="Resin & Solvent Type",
    yaxis_title="Avg Solvent Ratio (%)",
    plot_bgcolor='rgba(0,0,0,0)', 
    margin=dict(l=20, r=20, t=30, b=20)
)

st.plotly_chart(fig, use_container_width=True)
