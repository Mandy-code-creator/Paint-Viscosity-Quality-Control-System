import pandas as pd
import plotly.graph_objects as go
import numpy as np

def generate_i_chart(df, metric_col, title):
    """
    Generates an I-Chart (Individual Chart) aggregated at the Coil level, 
    incorporating Mill Range and Sigma-based control limits.
    """
    # Force data aggregation to Coil level to ensure metric uniformity across dashboard tabs
    if 'Coil_ID' not in df.columns:
        return go.Figure() # Return empty figure if missing primary key
        
    coil_df = df.groupby('Coil_ID')[metric_col].mean().reset_index()
    coil_df = coil_df.dropna()
    
    data_series = coil_df[metric_col]
    mean_val = data_series.mean()
    std_dev = data_series.std()
    
    # 3-Sigma Control Limits
    ucl = mean_val + (3 * std_dev)
    lcl = mean_val - (3 * std_dev)
    
    # Internal Warning Lines (Mill Range)
    limit_90 = mean_val * 0.90
    limit_110 = mean_val * 1.10
    
    fig = go.Figure()
    
    # Main data line
    fig.add_trace(go.Scatter(
        x=coil_df['Coil_ID'], 
        y=data_series,
        mode='lines+markers',
        name=metric_col,
        line=dict(color='black')
    ))
    
    # Center Line (Mean)
    fig.add_hline(y=mean_val, line_dash="dash", line_color="green", annotation_text="Mean")
    
    # Control Limits (UCL/LCL)
    fig.add_hline(y=ucl, line_dash="dash", line_color="red", annotation_text="UCL (3σ)")
    fig.add_hline(y=lcl, line_dash="dash", line_color="red", annotation_text="LCL (3σ)")
    
    # Mill Range Warning Markers (90% / 110%)
    fig.add_hline(y=limit_110, line_dash="dot", line_color="deepskyblue", annotation_text="110% Mill Range")
    fig.add_hline(y=limit_90, line_dash="dot", line_color="deepskyblue", annotation_text="90% Mill Range")
    
    fig.update_layout(
        title=f"{title} (Coil Level Aggregation)",
        xaxis_title="Coil ID",
        yaxis_title=metric_col,
        template="plotly_white",
        showlegend=False,
        hovermode="x"
    )
    
    return fig
