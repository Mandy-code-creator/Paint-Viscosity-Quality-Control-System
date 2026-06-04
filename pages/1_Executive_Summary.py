import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. SYSTEM GUARDRAIL ---
if 'raw_data_loaded' not in st.session_state or not st.session_state['raw_data_loaded']:
    st.warning("⚠️ Please upload data on the main page (App) first.")
    st.stop()

# --- 2. DATA RETRIEVAL ---
group_a = st.session_state['group_a_data'].copy()
rejected_data = st.session_state['rejected_data'].copy()

st.title("📊 Executive Summary")
st.markdown("---")

# --- 3. UPDATED RESIN & VENDOR PERFORMANCE ANALYSIS ---
st.subheader("💡 Resin & Vendor Performance Analysis")

# ... (đoạn code tính toán dataframe của bạn ở đây) ...

# Display the dataframe
st.dataframe(detailed_summary.style.format({
    'Total Paint (kg)': '{:,.0f}',
    'Total Solvent (kg)': '{:,.0f}',
    'Initial V (s)': '{:.2f}',
    'Final V (s)': '{:.2f}',
    'Avg Solvent %': '{:.2f} %'
}), use_container_width=True)

# --- CHỖ SỬA: Đưa chú thích vào đây và dùng tiếng Anh ---
st.caption("""
**Metrics Definition:**
* **Batches:** Number of valid mix events.
* **Total Paint / Solvent (kg):** Aggregate consumption of raw paint and solvent.
* **Avg Solvent %:** Average solvent-to-paint ratio. *Note: If this value exceeds the defined threshold for a specific resin, please review the adjustment process.*
""")
st.markdown("---")

# --- 4. PAINT CODE DICTIONARY VERIFICATION ---
with st.expander("📖 Paint Code Dictionary Verification"):
    st.markdown("""
    **System Decoding Logic:**
    * **Index 0:** Primary Classification (Char_1)
    * **Index 1:** Vendor
    * **Index 2:** Resin
    * **Index 3:** Application / Feature
    * **Index 6:** Color
    """)
    
    st.info("👇 Auto-decoded results from your raw data:")
    
    display_cols = ['塗料編號', 'Paint_Code', 'Vendor', 'Resin', 'Feature', 'Color', 'Char_1']
    available_cols = [col for col in display_cols if col in group_a.columns]
    
    if available_cols:
        sample_decode = group_a[available_cols].drop_duplicates(subset=['Paint_Code'])
        st.dataframe(sample_decode, use_container_width=True)

# --- 5. SMART DATE COLUMN DETECTION ---
date_candidates = ['攪拌日期', '調漆日期', '日期', 'Date', '生產日期', '調漆時間']
date_column = None

for col in date_candidates:
    if col in group_a.columns:
        date_column = col
        break

# --- 6. VISCOSITY TREND CHARTS (SEPARATED BY RESIN) ---
st.subheader("📈 Viscosity Trend Over Time by Resin")

if date_column is None:
    st.error("❌ System could not detect a valid Date column.")
else:
    # Group data by Date and Resin, calculate the MEAN of Viscosity
    # Chúng ta sử dụng '黏度(秒)' để xem độ nhớt gốc (Initial Viscosity)
    daily_viscosity_trend = group_a.groupby([date_column, 'Resin'])['黏度(秒)'].mean().reset_index()
    
    unique_resins = sorted([r for r in daily_viscosity_trend['Resin'].unique() if pd.notna(r)])
    cols = st.columns(2)

    for i, resin in enumerate(unique_resins):
        resin_data = daily_viscosity_trend[daily_viscosity_trend['Resin'] == resin]

        fig_viscosity = px.line(
            resin_data,
            x=date_column,
            y='黏度(秒)',
            markers=True,
            title=f"Average Initial Viscosity: {resin}",
            color_discrete_sequence=['deepskyblue'] 
        )

        fig_viscosity.update_layout(
            xaxis_title="Date",
            yaxis_title="Viscosity (s)",
            plot_bgcolor='rgba(0,0,0,0)',   
            hovermode="x unified",          
            margin=dict(l=20, r=20, t=40, b=20)
        )

        cols[i % 2].plotly_chart(fig_viscosity, use_container_width=True)
