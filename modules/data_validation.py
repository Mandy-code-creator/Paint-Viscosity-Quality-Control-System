import pandas as pd
import numpy as np

from modules.paint_decoder import decode_paint_code


def process_and_validate(raw_df):
    """
    Tiền xử lý và kiểm tra dữ liệu điều chỉnh độ nhớt.

    Group A:
    - Có mã sơn
    - Có trọng lượng sơn > 0
    - Có lượng dung môi thêm > 0
    - Có loại dung môi
    - Có độ nhớt trước và sau
    - Độ nhớt sau thấp hơn độ nhớt trước

    Lưu ý:
    - Không xóa dòng trùng lặp.
    - Không tạo Coil_ID vì dữ liệu này không phải dữ liệu thép cuộn.
    - Các dòng không hợp lệ được giữ trong rejected_data.
    - Các cột Order Thickness được giữ nguyên để các module sau sử dụng.
    """

    df = raw_df.copy()


    # =========================================================
    # 1. ENSURE REQUIRED COLUMNS
    # =========================================================
    required_columns = [
        "塗料編號",
        "稀釋劑",
        "塗料重量",
        "添加重量",
        "黏度(秒)",
        "黏度(秒)_1",
        "塗料批號",
        "塗料桶號",
    ]

    for col in required_columns:
        if col not in df.columns:
            df[col] = np.nan


    # =========================================================
    # 2. INVALID TEXT VALUES
    # =========================================================
    invalid_text_values = [
        "",
        "NAN",
        "NONE",
        "NULL",
        "N/A",
        "NA",
        "-",
        "--",
    ]


    # =========================================================
    # 3. NORMALIZE MAIN TEXT FIELDS
    # =========================================================
    df["Paint_Code"] = (
        df["塗料編號"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df["Solvent_Type"] = (
        df["稀釋劑"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )


    # =========================================================
    # 4. NORMALIZE ORIGINAL TEXT COLUMNS
    # =========================================================
    #
    # Những cột này thường được dùng cho filter / groupby.
    # Chuẩn hóa về string để tránh lỗi mixed type:
    # str + int + float
    #
    text_columns = [
        "線別",
        "線別_1",
        "班別",
        "班別_1",
        "紀錄員",
        "股長",
        "課長",
        "塗料批號",
        "塗料桶號",
        "稀釋劑批號",
        "稀釋劑桶號",
        "塗裝位置",
        "訂單編號",
        "Thickness_Match_Status",
        "Thickness_Match_Detail",
        "Matched_Position",
        "Thickness_Source_File",
    ]

    for col in text_columns:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype("string")
                .str.strip()
            )


    # =========================================================
    # 5. CONVERT CORE NUMERIC FIELDS
    # =========================================================
    numeric_cols = [
        "塗料重量",
        "添加重量",
        "黏度(秒)",
        "黏度(秒)_1",
    ]

    for col in numeric_cols:

        df[col] = (
            df[col]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace(" ", "", regex=False)
            .str.strip()
            .str.upper()
            .replace(invalid_text_values, np.nan)
        )

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )


    # =========================================================
    # 6. NORMALIZE ORDER THICKNESS COLUMNS
    # =========================================================
    #
    # File mới:
    # Paint Viscosity Analytics 24-26_with_Order_Thickness
    #
    # 4 cột thickness chỉ là dữ liệu bổ sung.
    # KHÔNG dùng để quyết định Group A.
    #
    thickness_cols = [
        "TOPFILM_THICK",
        "TTMFILM_THICK",
        "BACKFILM_THICK",
        "BTMFILM_THICK",
    ]

    for col in thickness_cols:

        if col in df.columns:

            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.replace(" ", "", regex=False)
                .str.strip()
                .str.upper()
                .replace(invalid_text_values, np.nan)
            )

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )


    # =========================================================
    # 7. OPTIONAL ENVIRONMENT NUMERIC FIELDS
    # =========================================================
    optional_numeric_cols = [
        "溫度",
        "濕度",
    ]

    for col in optional_numeric_cols:

        if col in df.columns:

            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.replace(" ", "", regex=False)
                .str.strip()
            )

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )


    # =========================================================
    # 8. DECODE PAINT CODE
    # =========================================================
    decoded_df = df["Paint_Code"].apply(
        decode_paint_code
    )

    # ---------------------------------------------------------
    # decode_paint_code có thể trả về:
    # DataFrame / Series / list / tuple
    # ---------------------------------------------------------
    if isinstance(decoded_df, pd.DataFrame):

        decoded_df = decoded_df.copy()

    elif isinstance(decoded_df, pd.Series):

        if len(decoded_df) == 0:

            decoded_df = pd.DataFrame(
                index=df.index,
                columns=[
                    "Vendor",
                    "Resin",
                    "Feature",
                    "Color",
                    "Char_1",
                ]
            )

        else:

            decoded_df = pd.DataFrame(
                decoded_df.tolist(),
                index=df.index
            )

    else:

        decoded_df = pd.DataFrame(
            decoded_df,
            index=df.index
        )


    # ---------------------------------------------------------
    # Make sure decoder always returns 5 columns
    # ---------------------------------------------------------
    while decoded_df.shape[1] < 5:
        decoded_df[decoded_df.shape[1]] = np.nan

    if decoded_df.shape[1] > 5:
        decoded_df = decoded_df.iloc[:, :5]


    decoded_df.columns = [
        "Vendor",
        "Resin",
        "Feature",
        "Color",
        "Char_1",
    ]


    # =========================================================
    # 9. NORMALIZE DECODED TEXT FIELDS
    # =========================================================
    #
    # Rất quan trọng.
    #
    # Tránh trường hợp:
    # Resin = ["PE", "EPOXY", 1, 2]
    #
    # hoặc Vendor / Feature có kiểu dữ liệu trộn lẫn
    # làm sorted() trong các page bị TypeError.
    #
    decoded_text_cols = [
        "Vendor",
        "Resin",
        "Feature",
        "Color",
        "Char_1",
    ]

    for col in decoded_text_cols:

        decoded_df[col] = (
            decoded_df[col]
            .astype("string")
            .str.strip()
        )


    # ---------------------------------------------------------
    # Prevent duplicate decoder columns
    # ---------------------------------------------------------
    existing_decoder_cols = [
        col
        for col in decoded_text_cols
        if col in df.columns
    ]

    if existing_decoder_cols:
        df = df.drop(
            columns=existing_decoder_cols
        )


    df = pd.concat(
        [
            df,
            decoded_df
        ],
        axis=1
    )


    # =========================================================
    # 10. CALCULATE VISCOSITY DROP
    # =========================================================
    #
    # File mới có thể đã có cột "Delta V",
    # nhưng hệ thống vẫn tự tính Delta_V để giữ nguyên
    # logic của app hiện tại.
    #
    df["Delta_V"] = (
        df["黏度(秒)"]
        - df["黏度(秒)_1"]
    )


    # =========================================================
    # 11. ASSIGN REJECTION REASONS
    # =========================================================
    df["Reject_Reason"] = ""


    # ---------------------------------------------------------
    # Paint code
    # ---------------------------------------------------------
    df.loc[
        df["Paint_Code"].isin(
            invalid_text_values
        ),
        "Reject_Reason"
    ] += "缺少塗料編號；"


    # ---------------------------------------------------------
    # Paint weight
    # ---------------------------------------------------------
    df.loc[
        df["塗料重量"].isna(),
        "Reject_Reason"
    ] += "缺少塗料重量；"


    df.loc[
        df["塗料重量"].notna()
        & (df["塗料重量"] <= 0),
        "Reject_Reason"
    ] += "塗料重量≤0；"


    # ---------------------------------------------------------
    # Added solvent
    # ---------------------------------------------------------
    df.loc[
        df["添加重量"].isna(),
        "Reject_Reason"
    ] += "缺少稀釋劑添加重量；"


    df.loc[
        df["添加重量"].notna()
        & (df["添加重量"] == 0),
        "Reject_Reason"
    ] += "未添加稀釋劑；"


    df.loc[
        df["添加重量"].notna()
        & (df["添加重量"] < 0),
        "Reject_Reason"
    ] += "稀釋劑添加重量<0；"


    # ---------------------------------------------------------
    # Solvent type
    # ---------------------------------------------------------
    df.loc[
        df["Solvent_Type"].isin(
            invalid_text_values
        ),
        "Reject_Reason"
    ] += "缺少稀釋劑種類；"


    # ---------------------------------------------------------
    # Before viscosity
    # ---------------------------------------------------------
    df.loc[
        df["黏度(秒)"].isna(),
        "Reject_Reason"
    ] += "缺少調整前黏度；"


    df.loc[
        df["黏度(秒)"].notna()
        & (df["黏度(秒)"] <= 0),
        "Reject_Reason"
    ] += "調整前黏度≤0；"


    # ---------------------------------------------------------
    # After viscosity
    # ---------------------------------------------------------
    df.loc[
        df["黏度(秒)_1"].isna(),
        "Reject_Reason"
    ] += "缺少調整後黏度；"


    df.loc[
        df["黏度(秒)_1"].notna()
        & (df["黏度(秒)_1"] <= 0),
        "Reject_Reason"
    ] += "調整後黏度≤0；"


    # ---------------------------------------------------------
    # Viscosity relationship
    # ---------------------------------------------------------
    df.loc[
        df["Delta_V"].notna()
        & (df["Delta_V"] == 0),
        "Reject_Reason"
    ] += "調整前後黏度相同；"


    df.loc[
        df["Delta_V"].notna()
        & (df["Delta_V"] < 0),
        "Reject_Reason"
    ] += "調整後黏度上升；"


    # =========================================================
    # 12. DATA STATUS
    # =========================================================
    df["Data_Status"] = np.where(
        df["Reject_Reason"] == "",
        "Valid Group A",
        "Excluded from Solvent Analysis",
    )


    # =========================================================
    # 13. SPLIT VALID / EXCLUDED DATA
    # =========================================================
    valid_mask = (
        df["Reject_Reason"] == ""
    )

    group_a = (
        df.loc[valid_mask]
        .copy()
    )

    rejected_data = (
        df.loc[~valid_mask]
        .copy()
    )


    # =========================================================
    # 14. CALCULATIONS FOR VALID GROUP A
    # =========================================================
    if not group_a.empty:

        # -----------------------------------------------------
        # Solvent ratio
        # -----------------------------------------------------
        group_a["Solvent_Ratio"] = (
            group_a["添加重量"]
            / group_a["塗料重量"]
        )

        group_a["Solvent_Ratio_Percent"] = (
            group_a["Solvent_Ratio"]
            * 100
        )


        # -----------------------------------------------------
        # Viscosity sensitivity
        # -----------------------------------------------------
        group_a["Viscosity_Sensitivity"] = np.where(
            group_a["Solvent_Ratio_Percent"] > 0,

            group_a["Delta_V"]
            / group_a["Solvent_Ratio_Percent"],

            np.nan,
        )


        # -----------------------------------------------------
        # kg solvent per 1 second viscosity reduction
        # -----------------------------------------------------
        group_a["Kg_Solvent_Per_1s"] = np.where(
            group_a["Delta_V"] > 0,

            group_a["添加重量"]
            / group_a["Delta_V"],

            np.nan,
        )


        # -----------------------------------------------------
        # kg solvent / 1s / 100kg paint
        # -----------------------------------------------------
        group_a[
            "Kg_Solvent_Per_1s_Per_100kg_Paint"
        ] = np.where(

            (group_a["Delta_V"] > 0)
            & (group_a["塗料重量"] > 0),

            (
                group_a["添加重量"]
                / group_a["Delta_V"]
                / group_a["塗料重量"]
                * 100
            ),

            np.nan,
        )


    # =========================================================
    # 15. RETURN
    # =========================================================
    return group_a, rejected_data
