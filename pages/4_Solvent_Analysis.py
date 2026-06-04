import streamlit as st
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="Solvent Analysis", page_icon="💧", layout="wide")

st.title("💧 Solvent Usage & Ratio Analysis")
st.markdown("Evaluate solvent consumption patterns, popular solvent types, and average mixing ratios across different paint configurations.")

# 1. Global State Check
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please go to the Main App page and upload your data file first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()

# 2. Sidebar Filters
st.sidebar.header("🔍 Solvent Filters")
selected_vendor = st.sidebar.selectbox("Vendor", ["All"] + sorted(group_a['Vendor'].unique().tolist()))
selected_resin = st.sidebar.selectbox("Resin Type", ["All"] + sorted(group_a['Resin'].unique().tolist()))

# Apply Filters
filtered_df = group_a.copy()
if selected_vendor != "All":
    filtered_df = filtered_df[filtered_df['Vendor'] == selected_vendor]
if selected_resin != "All":
    filtered_df = filtered_df[filtered_df['Resin'] == selected_resin]

if filtered_df.empty:
    st.error("No valid data available for the selected filters.")
    st.stop()

# 3. Chart: Solvent Usage Ranking
st.markdown("### 1. Most Utilized Solvents")
col1, col2 = st.columns([2, 1])

with col1:
    # Count frequency of each solvent
    solvent_counts = filtered_df['Solvent_Type'].value_counts().reset_index()
    solvent_counts.columns = ['Solvent_Type', 'Usage_Count']
    
    fig_bar = px.bar(
        solvent_counts, 
        x='Solvent_Type', 
        y='Usage_Count',
        color='Solvent_Type',
        title="Frequency of Solvent Usage (Number of Mix Events)",
        labels={"Solvent_Type": "Solvent Type", "Usage_Count": "Mix Count"}
    )
    fig_bar.update_layout(showlegend=False)
    st.plotly_chart(fig_bar, use_container_width=True)

with col2:
    st.markdown("#### Distribution")
    fig_pie = px.pie(
        solvent_counts, 
        names='Solvent_Type', 
        values='Usage_Count',
        hole=0.4
    )
    fig_pie.update_layout(showlegend=False)
    st.plotly_chart(fig_pie, use_container_width=True)

st.divider()

# 4. Chart: Average Solvent Ratio by Paint Code
st.markdown("### 2. Average Solvent Ratio by Paint Configuration")
st.info("💡 Shows the average percentage of solvent added relative to the total paint weight.")

# Aggregate data by Vendor, Resin, and Feature
ratio_df = filtered_df.groupby(['Vendor', 'Resin', 'Feature'])['Solvent_Ratio'].mean().reset_index()
ratio_df['Solvent_Ratio_Pct'] = ratio_df['Solvent_Ratio'] * 100
ratio_df['Paint_Config'] = ratio_df['Vendor'] + " | " + ratio_df['Resin'] + " | " + ratio_df['Feature']

# Sort to show top consumers
ratio_df = ratio_df.sort_values(by='Solvent_Ratio_Pct', ascending=False)

fig_ratio_bar = px.bar(
    ratio_df,
    x='Solvent_Ratio_Pct',
    y='Paint_Config',
    orientation='h',
    color='Resin',
    title="Average Solvent Consumption Ratio (%) by Paint Type",
    labels={"Solvent_Ratio_Pct": "Solvent Ratio (%)", "Paint_Config": "Paint Configuration"}
)
fig_ratio_bar.update_layout(yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_ratio_bar, use_container_width=True)
