import streamlit as st
import plotly.graph_objects as go
from data_processing import render_sidebar_filters

if 'raw_data' not in st.session_state:
    st.warning("Please upload data on the main page.")
    st.stop()

# Apply Global Sidebar Filters
df = render_sidebar_filters(st.session_state['raw_data'])

st.header("Process Stability (SPC I-Chart)")

if df.empty:
    st.info("No data available for the selected filters.")
    st.stop()

# Local filters specific to the Control Chart
c1, c2 = st.columns(2)
selected_sup = c1.selectbox("Focus by Supplier", ['All'] + list(df['Supplier'].unique()))
selected_res = c2.selectbox("Focus by Resin", ['All'] + list(df['Resin_Type'].unique()))

df_spc = df.copy()
if selected_sup != 'All':
    df_spc = df_spc[df_spc['Supplier'] == selected_sup]
if selected_res != 'All':
    df_spc = df_spc[df_spc['Resin_Type'] == selected_res]

# Sắp xếp thời gian
if 'Mix_Date' in df_spc.columns and not df_spc['Mix_Date'].isna().all():
    df_spc = df_spc.sort_values(by=['Mix_Date', 'Coil_Level_ID']).reset_index(drop=True)
else:
    df_spc = df_spc.reset_index(drop=True)

if len(df_spc) > 1:
    mean_val = df_spc['Viscosity_After'].mean()
    std_val = df_spc['Viscosity_After'].std()
    
    ucl = mean_val + 3 * std_val
    lcl = mean_val - 3 * std_val
    mill_ucl = mean_val + 1.5 * std_val
    mill_lcl = mean_val - 1.5 * std_val
    
    line_110 = mean_val * 1.10
    line_90 = mean_val * 0.90

    fig = go.Figure()

    fig.add_trace(go.Scatter(x=df_spc.index, y=df_spc['Viscosity_After'], mode='lines+markers', 
                             name='Viscosity (After)', marker=dict(color='black'),
                             hovertext=df_spc['Coil_Level_ID']))

    fig.add_trace(go.Scatter(x=df_spc.index, y=[mean_val]*len(df_spc), mode='lines', 
                             name='Center Line', line=dict(color='green', dash='dash')))
    
    fig.add_trace(go.Scatter(x=df_spc.index, y=[ucl]*len(df_spc), mode='lines', name='UCL', line=dict(color='red')))
    fig.add_trace(go.Scatter(x=df_spc.index, y=[lcl]*len(df_spc), mode='lines', name='LCL', line=dict(color='red')))

    fig.add_trace(go.Scatter(x=df_spc.index, y=[mill_ucl]*len(df_spc), mode='lines', 
                             name='Mill Range Upper', line=dict(color='orange', dash='dot')))
    fig.add_trace(go.Scatter(x=df_spc.index, y=[mill_lcl]*len(df_spc), mode='lines', 
                             name='Mill Range Lower', line=dict(color='orange', dash='dot')))

    fig.add_trace(go.Scatter(x=df_spc.index, y=[line_110]*len(df_spc), mode='lines', 
                             name='110% Marker', line=dict(color='deepskyblue')))
    fig.add_trace(go.Scatter(x=df_spc.index, y=[line_90]*len(df_spc), mode='lines', 
                             name='90% Marker', line=dict(color='deepskyblue')))

    fig.update_layout(title="Individuals Chart (Viscosity After)",
                      xaxis_title="Mixing Sequence", yaxis_title="Viscosity (sec)",
                      hovermode="x unified")
    
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Insufficient data points to build control charts for this specific combination.")
