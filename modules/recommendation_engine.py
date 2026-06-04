import pandas as pd

def calculate_theoretical_value(group_a_df, vendor, resin, feature, paint_weight, current_viscosity, target_viscosity):
    """
    Calculates the Theoretical Value of solvent required to reach target viscosity.
    UI outputs strictly enforce English terminology.
    """
    delta_v_target = current_viscosity - target_viscosity
    
    if delta_v_target <= 0:
        return {"Status": "Error", "Message": "Target viscosity must be lower than current viscosity."}
        
    # Filter historical data for specific paint configuration
    subset = group_a_df[
        (group_a_df['Vendor'] == vendor) & 
        (group_a_df['Resin'] == resin) & 
        (group_a_df['Feature'] == feature)
    ]
    
    if subset.empty:
        return {"Status": "Insufficient Data", "Message": "No historical data for this paint configuration."}
        
    # 1. Determine Standard Solvent
    standard_solvent = subset['Solvent_Type'].mode()[0]
    
    # 2. Calculate Average Viscosity Sensitivity
    avg_sensitivity = subset['Viscosity_Sensitivity'].mean()
    
    if avg_sensitivity <= 0:
        return {"Status": "Error", "Message": "Invalid sensitivity calculated from historical data."}
        
    # 3. Calculate Required Solvent Ratio (%)
    required_ratio = delta_v_target / avg_sensitivity
    
    # 4. Calculate Theoretical Value (kg)
    theoretical_value = (required_ratio / 100) * paint_weight
    
    return {
        "Status": "Success",
        "Standard_Solvent": standard_solvent,
        "Sensitivity_Factor": round(avg_sensitivity, 2),
        "Theoretical_Value": round(theoretical_value, 2)
    }
