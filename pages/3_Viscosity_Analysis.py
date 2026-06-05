import streamlit as st
import plotly.express as px
import pandas as pd

# Set page configuration
st.set_page_config(page_title="Viscosity Analysis", page_icon="🔬", layout="wide")

st.title("🔬 Viscosity Reduction Analysis")
st.markdown("Analyze how viscosity changes before and after solvent addition across different resin types and solvent types.")

# 1. Global State Check
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please go to the Main App page and upload your data file first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()

# 2. Sidebar Filters
st.sidebar.header("🔍 Analysis Filters")
vendors = sorted([v for v in group_a['Vendor'].unique() if v != 'Unknown'])
selected_vendor = st.sidebar.selectbox("Vendor", ["All"] + vendors)

# Apply Vendor filter
df_v = group_a[group_a['Vendor'] == selected_vendor] if selected_vendor != "All" else group_a
resins = sorted([r for r in df_v['Resin'].unique() if r != 'Unknown'])
selected_resin = st.sidebar.selectbox("Resin Type", ["All"] + resins)

# Apply Resin filter
df_vr = df_v[df_v['Resin'] == selected_resin] if selected_resin != "All" else df_v
solvents = sorted([s for s in df_vr['Solvent_Type'].unique() if s != 'Unknown'])
selected_solvent = st.sidebar.selectbox("Solvent Type", ["All"] + solvents)

# Apply all filters
filtered_df = df_vr.copy()
if selected_solvent != "All":
    filtered_df = filtered_df[filtered_df['Solvent_Type'] == selected_solvent]

if filtered_df.empty:
    st.error("No valid data available for the selected filters.")
    st.stop()

# 3. Chart: Scatter Plot (Before vs After)
st.markdown("### 1. Viscosity Shift (Before vs After)")
fig_scatter = px.scatter(
    filtered_df, 
    x="黏度(秒)", 
    y="黏度(秒)_1", 
    color="Resin",
    facet_col="Solvent_Type",
    facet_col_wrap=3,
    hover_data=["Paint_Code", "Delta_V", "Solvent_Ratio"],
    title="Initial vs Final Viscosity (Points below the red line indicate reduction)",
    labels={"黏度(秒)": "Initial Viscosity (sec)", "黏度(秒)_1": "Final Viscosity (sec)"}
)

max_val = max(filtered_df['黏度(秒)'].max(), filtered_df['黏度(秒)_1'].max())
fig_scatter.add_shape(
    type="line", line=dict(dash="dash", color="red"),
    x0=0, y0=0, x1=max_val, y1=max_val
)
fig_scatter.update_layout(height=600)
st.plotly_chart(fig_scatter, use_container_width=True)

st.divider()

# 4. Row 2: Distribution & Sensitivity
col1, col2 = st.columns(2)

with col1:
    st.markdown("### 2. Viscosity Reduction (ΔV) Distribution")
    fig_hist = px.histogram(
        filtered_df, 
        x="Delta_V", 
        color="Resin",
        nbins=20,
        title="Distribution of ΔV (Seconds Dropped)",
        labels={"Delta_V": "Viscosity Drop (sec)"}
    )
    st.plotly_chart(fig_hist, use_container_width=True)

with col2:
    st.markdown("### 3. Average Sensitivity by Resin & Solvent (Simplified)")

# Tính trung bình và độ lệch chuẩn
summary_df = filtered_df.groupby(['Resin', 'Solvent_Type'])['Viscosity_Sensitivity'].agg(['mean', 'std']).reset_index()

# Vẽ biểu đồ Bar Chart
fig_bar = px.bar(
    summary_df,
    x='Resin',
    y='mean',
    error_y='std',  # Thanh sai số thể hiện độ ổn định (càng ngắn càng đều)
    color='Resin',
    facet_col='Solvent_Type',
    facet_col_wrap=3,
    title="Average Sensitivity with Stability Range (Error Bars)",
    labels={'mean': 'Avg Sensitivity (sec/1%)', 'std': 'Variation'}
)

fig_bar.update_layout(height=600)
st.plotly_chart(fig_bar, use_container_width=True)
