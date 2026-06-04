import pandas as pd
import numpy as np
import streamlit as st

def load_and_preprocess(uploaded_file):
    if uploaded_file.name.endswith('.xlsx'):
        df = pd.read_excel(uploaded_file)
    else:
        df = pd.read_csv(uploaded_file)

    v_map = {'S':'Yungchi', 'T':'AKZO NOBEL(Taiwan)', 'A':'AKZO NOBEL', 'B':'Beckers', 
             'C':'Nan Pao', 'U':'Quali Poly', 'N':'Nippon', 'K':'Kansai', 
             'V':'Valspar', 'J':'Valspar (SW)', 'L':'KCC', 'R':'Noroo', 'Q':'Paoqun'}
    r_map = {'1':'PU','2':'PE','3':'EPOXY','4':'PVC','5':'PVDF','6':'SMP',
             '7':'AC','8':'WB','9':'IP','A':'PVB','B':'PVF'}
    c_map = {'0':'Clear','1':'Red','R':'Red','O':'Orange','2':'Orange','Y':'Yellow',
             '3':'Yellow','4':'Green','G':'Green','5':'Blue','L':'Blue','V':'Violet',
             '6':'Violet','N':'Brown','7':'Brown','T':'White','H':'White','W':'White',
             '8':'White','A':'Gray','C':'Gray','9':'Gray','B':'Black','S':'Silver','M':'Metallic'}

    if '塗料編號' in df.columns:
        df['Paint_Code_Str'] = df['塗料編號'].astype(str).str.upper().str.strip()
        df['Supplier'] = df['Paint_Code_Str'].str[1].map(v_map).fillna('Unknown')
        df['Resin_Type'] = df['Paint_Code_Str'].str[2].map(r_map).fillna('Unknown')
        df['Color_Group'] = df['Paint_Code_Str'].str[3].map(c_map).fillna('Unknown')

    # Xử lý Lô và Thùng thành Mix_ID thay vì Coil
    df['Batch_Lot'] = df['塗料批號'].astype(str).str.strip() if '塗料批號' in df.columns else 'Unknown'
    
    if '塗料桶號' in df.columns:
        df['Drum_No'] = df['塗料桶號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        df['Drum_No'] = df['Drum_No'].replace('nan', '0')
    else:
        df['Drum_No'] = '0'
        
    df['Mix_ID'] = df['Batch_Lot'] + '_' + df['Drum_No']

    if '攪拌日期' in df.columns:
        df['Mix_Date'] = pd.to_datetime(df['攪拌日期'], errors='coerce').dt.date
    else:
        df['Mix_Date'] = pd.NaT

    df['Viscosity_Before'] = pd.to_numeric(df['黏度(秒)'], errors='coerce') if '黏度(秒)' in df.columns else np.nan
    df['Viscosity_After'] = pd.to_numeric(df['黏度(秒)_1'], errors='coerce') if '黏度(秒)_1' in df.columns else np.nan
    df['Thinner_Added'] = pd.to_numeric(df['添加重量'], errors='coerce') if '添加重量' in df.columns else np.nan
    df['Paint_Weight'] = pd.to_numeric(df['塗料重量'], errors='coerce') if '塗料重量' in df.columns else np.nan

    df = df.dropna(subset=['Viscosity_Before'])

    no_adj_condition = df['Viscosity_After'].isna() | df['Thinner_Added'].isna() | (df['Thinner_Added'] == 0)
    df['Adjustment_Status'] = np.where(no_adj_condition, 'Pass (No Thinner)', 'Adjusted')

    df['Viscosity_After'] = np.where(no_adj_condition, df['Viscosity_Before'], df['Viscosity_After'])
    df['Thinner_Added'] = df['Thinner_Added'].fillna(0)

    df['Reduction'] = df['Viscosity_Before'] - df['Viscosity_After']
    
    df_adjusted = df[df['Adjustment_Status'] == 'Adjusted'].copy()
    if not df_adjusted.empty:
        Q1 = df_adjusted['Viscosity_After'].quantile(0.25)
        Q3 = df_adjusted['Viscosity_After'].quantile(0.75)
        IQR = Q3 - Q1
        valid_adjusted = df_adjusted[(df_adjusted['Viscosity_After'] >= Q1 - 1.5 * IQR) & (df_adjusted['Viscosity_After'] <= Q3 + 1.5 * IQR)]
        
        df_pass = df[df['Adjustment_Status'] == 'Pass (No Thinner)']
        df = pd.concat([valid_adjusted, df_pass], ignore_index=True)

    return df

def render_sidebar_filters(df):
    st.sidebar.header("Global Filters")
    
    color_list = ['All'] + sorted(df['Color_Group'].dropna().unique().tolist())
    selected_color = st.sidebar.selectbox("Color Group", color_list)
    
    if not df['Mix_Date'].isna().all():
        min_date = df['Mix_Date'].dropna().min()
        max_date = df['Mix_Date'].dropna().max()
        date_range = st.sidebar.date_input("Time Range", [min_date, max_date], min_value=min_date, max_value=max_date)
    else:
        date_range = None

    df_filtered = df.copy()
    if selected_color != 'All':
        df_filtered = df_filtered[df_filtered['Color_Group'] == selected_color]
        
    if date_range and len(date_range) == 2:
        start_date, end_date = date_range
        df_filtered = df_filtered[(df_filtered['Mix_Date'] >= start_date) & (df_filtered['Mix_Date'] <= end_date)]
        
    return df_filtered
