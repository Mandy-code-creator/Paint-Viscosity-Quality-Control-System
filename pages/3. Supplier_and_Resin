import streamlit as st
import plotly.express as px
from data_processing import render_sidebar_filters

if 'raw_data' not in st.session_state:
    st.warning("Please upload data on the main page.")
    st.stop()

# Apply Global Sidebar Filters
df = render_sidebar_filters(st.session_state['raw_data'])

st.header("Supplier & Resin Deep Dive")

if df.empty:
    st.info("No data available for the selected filters.")
    st.stop()

resin_types = sorted(df['Resin_Type'].dropna().unique())

if len(resin_types) == 0:
    st.warning("No Resin data available.")
    st.stop()

# Phân tích theo từng Loại Nhựa (Tabs)
st.subheader("Supplier Performance by Resin Type")
tabs = st.tabs([f"Resin: {r}" for r in resin_types])

for i, resin in enumerate(resin_types):
    with tabs[i]:
        df_resin = df[df['Resin_Type'] == resin]
        
        c1, c2 = st.columns(2)
        with c1:
            st.write("##### Viscosity Variance (After Adjustment)")
            fig_box = px.box(df_resin, x='Supplier', y='Viscosity_After', color='Supplier', points="all",
                             hover_data=['Batch_Lot', 'Drum_No'])
            fig_box.update_layout(showlegend=False)
            st.plotly_chart(fig_box, use_container_width=True)
            
        with c2:
            st.write("##### Average Reduction by Supplier")
            avg_red = df_resin.groupby('Supplier')['Reduction'].mean().reset_index().sort_values('Reduction', ascending=False)
            fig_bar = px.bar(avg_red, x='Supplier', y='Reduction', text_auto='.1f',
                             labels={'Reduction': 'Avg Reduction (sec)'})
            st.plotly_chart(fig_bar, use_container_width=True)
