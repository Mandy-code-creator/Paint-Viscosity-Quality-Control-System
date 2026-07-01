import pandas as pd
import numpy as np
from modules.paint_decoder import decode_paint_code


def process_and_validate(raw_df):
    """
    Tiền xử lý và kiểm tra dữ liệu sơn.

    Group A:
    - Có trọng lượng sơn > 0
    - Có lượng dung môi thêm > 0
    - Có độ nhớt trước/sau
    - Có loại dung môi
    - Độ nhớt sau pha thấp hơn độ nhớt trước pha

    Các dữ liệu khác được giữ lại trong rejected_data để truy vết,
    không bị xóa khỏi file gốc.
    """

    df = raw_df.copy()

    # =========================================================
    # 1. ĐẢM BẢO CÁC CỘT CẦN THIẾT TỒN TẠI
    # =========================================================
    required_columns = [
        '塗料編號',
        '稀釋劑',
        '塗料重量',
        '添加重量',
        '黏度(秒)',
        '黏度(秒)_1',
        '塗料批號',
        '塗料桶號'
    ]

    for col in required_columns:
        if col not in df.columns:
            df[col] = np.nan

    # =========================================================
    # 2. CHUẨN HÓA CỘT TEXT
    # =========================================================
    df['Paint_Code'] = (
        df['塗料編號']
        .fillna('')
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df['Solvent_Type'] = (
        df['稀釋劑']
        .fillna('')
        .astype(str)
        .str.upper()
        .str.strip()
    )

    # Các giá trị text thường bị đọc sai thành NaN
    invalid_text_values = [
        '',
        'NAN',
        'NONE',
        'NULL',
        'N/A',
        'NA',
        '-',
        '--'
    ]

    # =========================================================
    # 3. CHUYỂN CỘT SỐ VỀ NUMERIC
    # =========================================================
    numeric_cols = [
        '塗料重量',
        '添加重量',
        '黏度(秒)',
        '黏度(秒)_1'
    ]

    for col in numeric_cols:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace(',', '', regex=False)
            .str.replace(' ', '', regex=False)
            .replace(invalid_text_values, np.nan)
        )

        df[col] = pd.to_numeric(df[col], errors='coerce')

    # =========================================================
    # 4. GIẢI MÃ PAINT CODE
    # =========================================================
    decoded_df = df['Paint_Code'].apply(decode_paint_code)

    # Trường hợp hàm decode trả về list hoặc tuple
    if isinstance(decoded_df.iloc[0], (list, tuple)):
        decoded_df = pd.DataFrame(
            decoded_df.tolist(),
            index=df.index
        )

    decoded_df.columns = [
        'Vendor',
        'Resin',
        'Feature',
        'Color',
        'Char_1'
    ]

    df = pd.concat([df, decoded_df], axis=1)

    # =========================================================
    # =========================================================
    # 5. TẠO PAINT BATCH + BUCKET ID
    # =========================================================
    batch_no = (
        df["塗料批號"]
        .fillna("")
        .astype(str)
        .str.strip()
    )
    
    bucket_no = (
        df["塗料桶號"]
        .fillna("")
        .astype(str)
        .str.strip()
    )
    
    df["Paint_Batch_Bucket_ID"] = batch_no + "_" + bucket_no
    
    empty_id_mask = df["Paint_Batch_Bucket_ID"].isin([
        "_",
        "NAN_NAN",
        "nan_nan",
        ""
    ])
    
    df.loc[empty_id_mask, "Paint_Batch_Bucket_ID"] = (
        "ROW_" + df.loc[empty_id_mask].index.astype(str)
    )

    # =========================================================
    # 6. TÍNH DELTA V
    # =========================================================
    df['Delta_V'] = (
        df['黏度(秒)'] - df['黏度(秒)_1']
    )

    # =========================================================
    # 7. GHI LÝ DO KHÔNG THUỘC GROUP A
    # =========================================================
    df['Reject_Reason'] = ''

    # 7.1 Paint code
    df.loc[
        df['Paint_Code'].isin(invalid_text_values),
        'Reject_Reason'
    ] += '缺少塗料編號；'

    # 7.2 Paint weight
    df.loc[
        df['塗料重量'].isna(),
        'Reject_Reason'
    ] += '缺少塗料重量；'

    df.loc[
        df['塗料重量'].notna() &
        (df['塗料重量'] <= 0),
        'Reject_Reason'
    ] += '塗料重量≤0；'

    # 7.3 Solvent added weight
    df.loc[
        df['添加重量'].isna(),
        'Reject_Reason'
    ] += '缺少稀釋劑添加重量；'

    df.loc[
        df['添加重量'].notna() &
        (df['添加重量'] == 0),
        'Reject_Reason'
    ] += '未添加稀釋劑；'

    df.loc[
        df['添加重量'].notna() &
        (df['添加重量'] < 0),
        'Reject_Reason'
    ] += '稀釋劑添加重量<0；'

    # 7.4 Solvent type
    df.loc[
        df['Solvent_Type'].isin(invalid_text_values),
        'Reject_Reason'
    ] += '缺少稀釋劑種類；'

    # 7.5 Viscosity before
    df.loc[
        df['黏度(秒)'].isna(),
        'Reject_Reason'
    ] += '缺少調整前黏度；'

    df.loc[
        df['黏度(秒)'].notna() &
        (df['黏度(秒)'] <= 0),
        'Reject_Reason'
    ] += '調整前黏度≤0；'

    # 7.6 Viscosity after
    df.loc[
        df['黏度(秒)_1'].isna(),
        'Reject_Reason'
    ] += '缺少調整後黏度；'

    df.loc[
        df['黏度(秒)_1'].notna() &
        (df['黏度(秒)_1'] <= 0),
        'Reject_Reason'
    ] += '調整後黏度≤0；'

    # 7.7 Delta viscosity
    df.loc[
        df['Delta_V'].notna() &
        (df['Delta_V'] == 0),
        'Reject_Reason'
    ] += '調整前後黏度相同；'

    df.loc[
        df['Delta_V'].notna() &
        (df['Delta_V'] < 0),
        'Reject_Reason'
    ] += '調整後黏度上升；'

    # =========================================================
    # 8. PHÂN LOẠI DATA STATUS
    # =========================================================
    df['Data_Status'] = np.where(
        df['Reject_Reason'] == '',
        'Valid Group A',
        'Excluded from Solvent Analysis'
    )

    # =========================================================
    # 9. TÁCH GROUP A VÀ DATA LOG
    # =========================================================
    valid_mask = df['Reject_Reason'] == ''

    group_a = df.loc[valid_mask].copy()
    rejected_data = df.loc[~valid_mask].copy()

    # =========================================================
    # 10. TÍNH TOÁN CHO GROUP A
    # =========================================================
    if not group_a.empty:

        group_a['Solvent_Ratio'] = (
            group_a['添加重量'] / group_a['塗料重量']
        )

        group_a['Solvent_Ratio_Percent'] = (
            group_a['Solvent_Ratio'] * 100
        )

        group_a['Viscosity_Sensitivity'] = np.where(
            group_a['Solvent_Ratio_Percent'] > 0,
            group_a['Delta_V'] / group_a['Solvent_Ratio_Percent'],
            np.nan
        )

        group_a['Kg_Solvent_Per_1s'] = np.where(
            group_a['Delta_V'] > 0,
            group_a['添加重量'] / group_a['Delta_V'],
            np.nan
        )

        group_a['Kg_Solvent_Per_1s_Per_100kg_Paint'] = np.where(
            (group_a['Delta_V'] > 0) &
            (group_a['塗料重量'] > 0),
            (
                group_a['添加重量']
                / group_a['Delta_V']
                / group_a['塗料重量']
                * 100
            ),
            np.nan
        )

    return group_a, rejected_data
