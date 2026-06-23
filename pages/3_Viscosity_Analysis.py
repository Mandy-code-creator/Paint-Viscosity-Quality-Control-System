import streamlit as st
import plotly.express as px
import pandas as pd

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Viscosity & SOP Report", page_icon="📊", layout="wide")
st.title("📊 Viscosity & SOP Analysis Dashboard")
st.markdown("Comparative regression, SOP matrix, and line chart visualization for Resin – Vendor – Solvent.")

# --- 2. DATA VALIDATION ---
if not st.session_state.get('raw_data_loaded', False):
    st.warning("⚠️ No data loaded. Please upload your data file first.")
    st.stop()

group_a = st.session_state['group_a_data'].copy()
group_a['Solvent_Type'] = group_a['Solvent_Type'].astype(str)

# Calculate solvent ratio percentage based on batch weight (Prevents scaling issues due to batch sizes)
group_a['Solvent_Ratio_Percent'] = (group_a['添加重量'] / group_a['塗料重量'].replace(0, 1)) * 100

# --- 3. INTERACTIVE FILTERS ---
unique_resins = sorted(group_a['Resin'].unique())
unique_vendors = sorted(group_a['Vendor'].unique())
unique_solvents = sorted(group_a['Solvent_Type'].unique())

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    selected_resins = st.multiselect("Select Resin:", options=unique_resins, default=unique_resins)
with col_f2:
    selected_vendors = st.multiselect("Select Vendor:", options=unique_vendors, default=unique_vendors)
with col_f3:
    selected_solvents = st.multiselect("Select Solvent Type:", options=unique_solvents, default=unique_solvents)

filtered_df = group_a[
    (group_a['Resin'].isin(selected_resins)) &
    (group_a['Vendor'].isin(selected_vendors)) &
    (group_a['Solvent_Type'].isin(selected_solvents))
].copy()

# --- 4. CHART 1: MULTI-GROUP COMPARATIVE REGRESSION ---
st.markdown("---")
st.subheader("📈 Comparative Regression: Solvent vs. Viscosity")

fig_regression = px.scatter(
    filtered_df,
    x='Solvent_Ratio_Percent',
    y='黏度(秒)',
    color='Solvent_Type',
    symbol='Resin',
    facet_col='Vendor',
    trendline='ols',
    labels={'Solvent_Ratio_Percent': 'Solvent Added (%)', '黏度(秒)': 'Viscosity (s)'},
    title="Solvent Added vs. Viscosity Reduction (Multi-Filter Comparison)"
)
fig_regression.update_layout(plot_bgcolor='white', font=dict(size=12), margin=dict(l=40, r=40, t=60, b=40))
st.plotly_chart(fig_regression, use_container_width=True)


# --- 5. CHART 2: SOP MATRIX (With Saturation Logic & Outlier Filtering) ---
st.markdown("---")
st.subheader("📚 SOP Matrix: Resin – Vendor – Solvent (Saturation-Aware)")

# Build dynamic aggregation dictionary based on available columns
agg_funcs = {}
if '塗料批號' in group_a.columns: 
    agg_funcs['Batches'] = pd.NamedAgg(column='塗料批號', aggfunc='nunique')
if '塗料重量' in group_a.columns: 
    agg_funcs['Total Paint (kg)'] = pd.NamedAgg(column='塗料重量', aggfunc='sum')
if '添加重量' in group_a.columns: 
    agg_funcs['Total Solvent (kg)'] = pd.NamedAgg(column='添加重量', aggfunc='sum')
if '黏度(秒)' in group_a.columns: 
    agg_funcs['Avg Initial V (s)'] = pd.NamedAgg(column='黏度(秒)', aggfunc='mean')
if '黏度(秒)_1' in group_a.columns: 
    agg_funcs['Avg Final V (s)'] = pd.NamedAgg(column='黏度(秒)_1', aggfunc='mean')
    # NON-LINEAR LAW: Identify the absolute lowest physical viscosity floor ever recorded
    agg_funcs['Viscosity Floor (s) ⚠️'] = pd.NamedAgg(column='黏度(秒)_1', aggfunc='min')
if 'Solvent_Ratio_Percent' in group_a.columns:
    agg_funcs['Avg Solvent %'] = pd.NamedAgg(column='Solvent_Ratio_Percent', aggfunc='mean')
    # SAFETY LOGIC: Use 95th Percentile instead of Max to eliminate past human operational errors
    agg_funcs['Max Solvent Limit % ⚠️'] = pd.NamedAgg(column='Solvent_Ratio_Percent', aggfunc=lambda x: x.quantile(0.95))
if 'Sensitivity' in group_a.columns:
    agg_funcs['Avg Sensitivity'] = pd.NamedAgg(column='Sensitivity', aggfunc='mean')

# Execute data aggregation
summary_matrix = group_a.groupby(['Resin','Vendor','Solvent_Type']).agg(**agg_funcs).reset_index()

# Calculate technical standard based on solvent sensitivity
if 'Avg Sensitivity' in summary_matrix.columns and 'Total Paint (kg)' in summary_matrix.columns:
    summary_matrix['Solvent Factor (kg/1s drop)'] = summary_matrix.apply(
        lambda row: (row['Total Paint (kg)'] * (1.0 / row['Avg Sensitivity']) / 100)
        if row['Avg Sensitivity'] > 0 else 0,
        axis=1
    )

# Render dataframe with Streamlit advanced Column Configuration (Zero Matplotlib Dependency)
st.dataframe(
    summary_matrix,
    column_config={
        "Total Paint (kg)": st.column_config.NumberColumn(format="%d"),
        "Total Solvent (kg)": st.column_config.NumberColumn(format="%d"),
        "Avg Initial V (s)": st.column_config.NumberColumn(format="%.1f"),
        "Avg Final V (s)": st.column_config.NumberColumn(format="%.1f"),
        "Viscosity Floor (s) ⚠️": st.column_config.NumberColumn(
            format="%.1f", 
            help="The lowest viscosity ever recorded (Non-linear saturation floor). Viscosity cannot drop below this level."
        ),
        "Avg Solvent %": st.column_config.NumberColumn(format="%.2f%%"),
        "Max Solvent Limit % ⚠️": st.column_config.ProgressColumn(
            label="Max Solvent Limit % ⚠️",
            format="%.2f%%",
            min_value=0,
            max_value=30,
            help="The practical safe solvent addition ceiling (Filtered out the top 5% anomalies/historical over-addition errors)."
        ),
        "Avg Sensitivity": st.column_config.NumberColumn(format="%.3f"),
        "Solvent Factor (kg/1s drop)": st.column_config.NumberColumn(format="%.3f")
    },
    use_container_width=True
)

st.warning("""
💡 **SOP Technical Guidelines for Saturation Management:**
- **Non-Linear Law:** As the current viscosity approaches the `Viscosity Floor (s)`, the marginal dilution efficiency drops sharply. Adding more solvent will barely reduce the viscosity seconds.
- **Saturation Boundary:** Operators must never be allowed to add solvent exceeding the percentage specified in the `Max Solvent Limit % ⚠️` column to prevent destroying the core resin chemical bonds.
""")


# --- 6. CHART 3: LINE CHART (Average Initial vs Final Viscosity) ---
st.markdown("---")
st.subheader("📊 Line Chart: Average Initial vs Final Viscosity vs Solvent Ratio")

line_summary = filtered_df.groupby(['Resin','Vendor','Solvent_Type']).agg({
    'Solvent_Ratio_Percent':'mean',
    '黏度(秒)':'mean',
    '黏度(秒)_1':'mean'
}).reset_index()

fig_line = px.line(
    line_summary,
    x='Solvent_Ratio_Percent',
    y=['黏度(秒)', '黏度(秒)_1'],
    color='Vendor',
    facet_col='Resin',
    labels={'value':'Viscosity (s)', 'variable':'Stage'},
    title="Average Initial vs Final Viscosity by Solvent Ratio"
)

fig_line.update_layout(
    plot_bgcolor='white',
    font=dict(size=12),
    margin=dict(l=40, r=40, t=60, b=40),
    legend_title_text='Stage'
)
fig_line.update_xaxes(showline=True, linecolor='black', linewidth=1)
fig_line.update_yaxes(showgrid=True, gridcolor='lightgray', linecolor='black', linewidth=1)

st.plotly_chart(fig_line, use_container_width=True)

st.caption("""
💡 **Interpretation:**
- **Chart 1:** Scatter + trendline → Compares solvent efficiency across different vendors.
- **Chart 2:** SOP Matrix → Standard reference table integrating safe saturation boundaries based on batch percentage.
- **Chart 3:** Average Line Chart → Illustrates the non-linear slope of initial and final viscosity during dilution.
""")
