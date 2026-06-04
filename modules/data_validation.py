import pandas as pd
import numpy as np

def remove_outliers_iqr(df, column):
    """Filters out extreme values using the Interquartile Range (IQR) method."""
    Q1 = df[column].quantile(0.25)
    Q3 = df[column].quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    
    return df[(df[column] >= lower_bound) & (df[column] <= upper_bound)]

def process_and_validate(raw_df):
    """
    Cleans data, enforces Strict Group A conditions, calculates Delta V,
    and prepares data for Coil-level SPC aggregation.
    """
    df = raw_df.copy()
    
    # 1. Standardize Text Columns
    df['Paint_Code'] = df['塗料編號'].astype(str).str.upper().str.strip()
    df['Solvent_Type'] = df['稀釋劑'].astype(str).str.upper().str.strip()
    
    # Ensure a Coil_ID column exists for Coil-level logic (assuming '塗料批號' or similar mapped to 'Coil_ID')
    if 'Coil_ID' not in df.columns:
        # Fallback to create a unique identifier if exact Coil ID is missing from raw columns
        df['Coil_ID'] = df['塗料批號'].astype(str) + "_" + df['塗料桶號'].astype(str)

    # 2. Strict Group A Filtering
    mask_has_weight = df['塗料重量'].notna() & (df['塗料重量'] > 0) & df['添加重量'].notna() & (df['添加重量'] > 0)
    mask_has_viscosity = df['黏度(秒)'].notna() & df['黏度(秒)_1'].notna()
    mask_has_solvent = df['Solvent_Type'].notna() & (df['Solvent_Type'] != 'NAN') & (df['Solvent_Type'] != '')
    
    df['Delta_V'] = df['黏度(秒)'] - df['黏度(秒)_1']
    mask_valid_delta = df['Delta_V'] > 0
    
    valid_mask = mask_has_weight & mask_has_viscosity & mask_has_solvent & mask_valid_delta
    
    # Segregate Data
    group_a = df[valid_mask].copy()
    rejected_data = df[~valid_mask].copy()
    
    if not group_a.empty:
        # 3. Calculate Core Metrics
        group_a['Solvent_Ratio'] = group_a['添加重量'] / group_a['塗料重量']
        group_a['Viscosity_Sensitivity'] = group_a['Delta_V'] / (group_a['Solvent_Ratio'] * 100)
        
        # 4. Outlier Removal via IQR
        group_a = remove_outliers_iqr(group_a, 'Solvent_Ratio')
        group_a = remove_outliers_iqr(group_a, 'Viscosity_Sensitivity')
        
    return group_a, rejected_data
