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

# --- 3. KEY PERFORMANCE INDICATORS BY RESIN (PHÂN TÍCH THEO NHỰA) ---
st.subheader("💡 Performance by Resin Type")

# Tính toán số lượng mẻ duy nhất (nunique) và độ giảm nhớt trung bình
resin_summary = group_a.groupby('Resin').agg({
    '塗料批號': 'nunique',        # Đếm số lượng Batch duy nhất
    'Delta_V': 'mean',           # Độ giảm nhớt trung bình (hiệu quả điều chỉnh)
    '塗料重量': 'sum'            # Tổng khối lượng sơn
}).rename(columns={
    '塗料批號': 'Total Batches',
    'Delta_V': 'Avg Delta V (s)',
    '塗料重量': 'Total Paint (kg)'
})

# Hiển thị bảng phân tích
st.dataframe(resin_summary.style.format({
    'Avg Delta V (s)': '{:.2f}',
    'Total Paint (kg)': '{:,.0f}'
}), use_container_width=True)

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

# --- 6. PRODUCTION ACTIVITY CHARTS (SEPARATED BY RESIN) ---
st.subheader("📈 Production Activity Over Time by Resin")

if date_column is None:
    st.error("❌ System could not detect a valid Date column. Please verify your Excel file structure.")
else:
    # Group data by Date and Resin
    daily_resin_activity = group_a.groupby([date_column, 'Resin']).size().reset_index(name='Number of Events')
    
    # Get a sorted list of unique resins
    unique_resins = sorted([r for r in daily_resin_activity['Resin'].unique() if pd.notna(r)])

    # Create a grid layout (2 columns) for better space utilization
    cols = st.columns(2)

    # Loop through each resin and create a separate chart
    for i, resin in enumerate(unique_resins):
        # Filter data for the specific resin
        resin_data = daily_resin_activity[daily_resin_activity['Resin'] == resin]

        # Generate individual chart
        fig_activity = px.line(
            resin_data,
            x=date_column,
            y='Number of Events',
            markers=True,
            title=f"Resin Type: {resin}",
            color_discrete_sequence=['deepskyblue'] 
        )

        # Optimize chart layout
        fig_activity.update_layout(
            xaxis_title="Date",
            yaxis_title="Number of Events",
            plot_bgcolor='rgba(0,0,0,0)',   
            hovermode="x unified",          
            margin=dict(l=20, r=20, t=40, b=20)
        )

        # Assign to alternating columns (Left/Right)
        cols[i % 2].plotly_chart(fig_activity, use_container_width=True)
