import streamlit as st
import plotly.express as px
import statsmodels.api as sm


if 'raw_data' not in st.session_state:
    st.warning("Please upload data on the main page.")
    st.stop()

# Apply Global Sidebar Filters
df = render_sidebar_filters(st.session_state['raw_data'])

st.header("Adjustment Effectiveness")

if df.empty:
    st.info("No data available for the selected filters.")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    st.subheader("Reduction Distribution")
    fig_hist = px.histogram(df, x='Reduction', nbins=30, marginal="box",
                            labels={'Reduction': 'Viscosity Reduction (sec)'})
    st.plotly_chart(fig_hist, use_container_width=True)

with col2:
    st.subheader("Reduction by Resin Type")
    fig_box = px.box(df, x='Resin_Type', y='Reduction', color='Resin_Type')
    st.plotly_chart(fig_box, use_container_width=True)

st.divider()

# Thinner Impact
st.subheader("Thinner Impact & Theoretical Value")

# Khắc phục lỗi NaN: Loại bỏ các dòng thiếu dữ liệu Paint_Weight trước khi vẽ biểu đồ bong bóng
df_scatter = df.dropna(subset=['Thinner_Added', 'Reduction', 'Paint_Weight']).copy()

if not df_scatter.empty:
    fig_scatter = px.scatter(df_scatter, x='Thinner_Added', y='Reduction', color='Resin_Type', size='Paint_Weight',
                             hover_data=['Batch_Lot', 'Drum_No', 'Supplier'],
                             labels={'Thinner_Added': 'Thinner Added (kg)', 'Reduction': 'Viscosity Reduction (sec)', 'Paint_Weight': 'Paint Weight (kg)'},
                             title="Correlation: Thinner vs Viscosity Drop")
    st.plotly_chart(fig_scatter, use_container_width=True)
else:
    st.info("Not enough complete data (missing Paint Weight) to draw the scatter plot.")

# Regression Model
st.write("#### Regression Model (Theoretical Value)")
try:
    # Mô hình OLS chỉ cần Thinner_Added và Reduction
    df_model = df.dropna(subset=['Thinner_Added', 'Reduction'])
    
    if df_model['Thinner_Added'].nunique() > 1:
        X = df_model['Thinner_Added']
        y = df_model['Reduction']
        X = sm.add_constant(X)
        model = sm.OLS(y, X).fit()
        
        theoretical_val = model.params['Thinner_Added']
        r_squared = model.rsquared
        
        c1, c2 = st.columns(2)
        c1.metric("Theoretical Value (sec/kg)", f"{theoretical_val:.2f}")
        c2.metric("R-Squared (Correlation Strength)", f"{r_squared:.2f}")
    else:
        st.write("Not enough variance in Thinner to compute the theoretical model.")
except Exception as e:
    st.error("Could not compute regression model.")
