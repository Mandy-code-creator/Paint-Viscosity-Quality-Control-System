import pandas as pd
import numpy as np
from modules.paint_decoder import decode_paint_code

def process_and_validate(raw_df):
    """
    Tiền xử lý dữ liệu: Làm sạch, áp dụng bộ lọc Strict Group A, tính toán Delta V,
    giải mã mã sơn thành các đặc tính kỹ thuật, và chuẩn bị dữ liệu cấp độ cuộn (Coil-level) cho SPC.
    
    *Lưu ý: Đã loại bỏ thuật toán IQR để giữ nguyên 100% các điểm bất thường (Outliers), 
    giúp biểu đồ SPC phản ánh chính xác các mẻ sơn lỗi trên dây chuyền.*
    """
    df = raw_df.copy()
    
    # 1. Chuẩn hóa cột văn bản (Xóa khoảng trắng, in hoa)
    if '塗料編號' in df.columns:
        df['Paint_Code'] = df['塗料編號'].astype(str).str.upper().str.strip()
    else:
        df['Paint_Code'] = 'UNKNOWN'
        
    if '稀釋劑' in df.columns:
        df['Solvent_Type'] = df['稀釋劑'].astype(str).str.upper().str.strip()
    else:
        df['Solvent_Type'] = 'UNKNOWN'
    
    # 2. GIẢI MÃ MÃ SƠN (DECODE PAINT CODE)
    # Áp dụng hàm từ file paint_decoder.py cho từng dòng
    decoded_df = df['Paint_Code'].apply(decode_paint_code)
    
    # Đặt tên 4 cột mới khớp 100% với giá trị trả về từ paint_decoder.py
    decoded_df.columns = ['Vendor', 'Resin', 'Feature', 'Color', 'Char_1']
    
    # Gộp 4 cột mới này vào bảng dữ liệu gốc
    df = pd.concat([df, decoded_df], axis=1)
    
    # 3. Tạo ID Cấp độ Cuộn (Coil-Level Logic)
    if 'Coil_ID' not in df.columns:
        if '塗料批號' in df.columns and '塗料桶號' in df.columns:
            df['Coil_ID'] = df['塗料批號'].astype(str) + "_" + df['塗料桶號'].astype(str)
        else:
            df['Coil_ID'] = df.index.astype(str) # Fallback nếu thiếu cột

    # 4. BỘ LỌC NGHIÊM NGẶT (Strict Group A Filtering)
    # 4a. Phải có trọng lượng sơn và trọng lượng dung môi > 0
    mask_has_weight = df['塗料重量'].notna() & (df['塗料重量'] > 0) & df['添加重量'].notna() & (df['添加重量'] > 0)
    
    # 4b. Phải có dữ liệu độ nhớt trước và sau khi pha
    mask_has_viscosity = df['黏度(秒)'].notna() & df['黏度(秒)_1'].notna()
    
    # 4c. Phải có mã dung môi hợp lệ
    mask_has_solvent = df['Solvent_Type'].notna() & (df['Solvent_Type'] != 'NAN') & (df['Solvent_Type'] != '')
    
    # 4d. Độ nhớt phải giảm sau khi pha (Delta V > 0)
    df['Delta_V'] = df['黏度(秒)'] - df['黏度(秒)_1']
    mask_valid_delta = df['Delta_V'] > 0
    
    # Tổng hợp các điều kiện lọc
    valid_mask = mask_has_weight & mask_has_viscosity & mask_has_solvent & mask_valid_delta
    
    # 5. Phân tách Dữ liệu
    group_a = df[valid_mask].copy()        # Dữ liệu sạch đưa vào tính toán SPC
    rejected_data = df[~valid_mask].copy() # Dữ liệu rác/lỗi nhập liệu
    
    # 6. Tính toán các chỉ số cốt lõi cho Group A
    if not group_a.empty:
        # Tỷ lệ dung môi (%) = Trọng lượng dung môi / Trọng lượng sơn
        group_a['Solvent_Ratio'] = group_a['添加重量'] / group_a['塗料重量']
        
        # Độ nhạy độ nhớt = Delta V / Tỷ lệ dung môi
        group_a['Viscosity_Sensitivity'] = group_a['Delta_V'] / (group_a['Solvent_Ratio'] * 100)
            
    return group_a, rejected_data
