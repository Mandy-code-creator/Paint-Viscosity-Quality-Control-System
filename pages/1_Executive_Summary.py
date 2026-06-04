import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Executive Summary", page_icon="📊", layout="wide")

st.title("📊 Executive Summary")
st.markdown("High-level overview of paint viscosity control and solvent utilization across the production line.")

# 1. Global State Check
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please go to the Main App page and upload your data file first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()

# 2. Top Level KPIs
st.markdown("### 🏆 Key Performance Indicators (Group A Data)")
col1, col2, col3, col4 = st.columns(4)

total_records = len(group_a)
unique_paint_configs = len(group_a.groupby(['Vendor', 'Resin', 'Feature']))
avg_solvent_ratio = group_a['Solvent_Ratio'].mean() * 100
avg_viscosity_drop = group_a['Delta_V'].mean()

col1.metric("Total Valid Mix Events", f"{total_records:,}")
col2.metric("Unique Paint Configurations", f"{unique_paint_configs:,}")
col3.metric("Avg Solvent Ratio", f"{avg_solvent_ratio:.2f}%")
col4.metric("Avg Viscosity Drop (sec)", f"{avg_viscosity_drop:.1f}")

st.divider()

# 3. Middle Section: Composition Analysis
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("### Paint Processing by Vendor")
    # Count records per vendor
    vendor_counts = group_a['Vendor'].value_counts().reset_index()
    vendor_counts.columns = ['Vendor', 'Count']
    
    fig_vendor = px.pie(
        vendor_counts, 
        names='Vendor', 
        values='Count',
        hole=0.3,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    st.plotly_chart(fig_vendor, use_container_width=True)

with col_right:
    st.markdown("### Top 5 Resins by Solvent Consumption")
    # Average solvent ratio per resin
    resin_ratio = group_a.groupby('Resin')['Solvent_Ratio'].mean().reset_index()
    resin_ratio['Solvent_Ratio_Pct'] = resin_ratio['Solvent_Ratio'] * 100
    resin_ratio = resin_ratio.sort_values(by='Solvent_Ratio_Pct', ascending=False).head(5)
    
    fig_resin = px.bar(
        resin_ratio,
        x='Resin',
        y='Solvent_Ratio_Pct',
        color='Resin',
        labels={'Solvent_Ratio_Pct': 'Avg Solvent Ratio (%)'}
    )
    fig_resin.update_layout(showlegend=False)
    st.plotly_chart(fig_resin, use_container_width=True)

st.divider()

# 4. Bottom Section: Production Timeline (Coil Level)
st.markdown("### 📈 Production Activity Over Time")

if '攪拌日期' in group_a.columns:
    # Ensure datetime format
    group_a['攪拌日期'] = pd.to_datetime(group_a['攪拌日期'], errors='coerce')
    time_series_df = group_a.dropna(subset=['攪拌日期'])
    
    if not time_series_df.empty:
        # Group by date to count number of mix events
        daily_counts = time_series_df.groupby(time_series_df['攪拌日期'].dt.date).size().reset_index(name='Daily_Mix_Events')
        daily_counts.columns = ['Date', 'Mix Events']
        
        fig_time = px.line(
            daily_counts, 
            x='Date', 
            y='Mix Events',
            markers=True,
            title="Daily Valid Mix Events (Group A)"
        )
        fig_time.update_layout(xaxis_title="Date", yaxis_title="Number of Events")
        st.plotly_chart(fig_time, use_container_width=True)
    else:
        st.info("No valid date information available for timeline generation.")
else:
    st.info("Date column not found in the dataset.")
