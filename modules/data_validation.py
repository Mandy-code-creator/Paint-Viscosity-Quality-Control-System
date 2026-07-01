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
    # 2. NORMALIZE TEXT FIELDS
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
    # 3. CONVERT NUMERIC FIELDS
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
            .replace(invalid_text_values, np.nan)
        )

        df[col] = pd.to_numeric(df[col], errors="coerce")

    # =========================================================
    # 4. DECODE PAINT CODE
    # =========================================================
    if df.empty:
        return df.copy(), df.copy()

    decoded_series = df["Paint_Code"].apply(decode_paint_code)

    decoded_df = pd.DataFrame(
        decoded_series.tolist(),
        index=df.index,
        columns=[
            "Vendor",
            "Resin",
            "Feature",
            "Color",
            "Char_1",
        ],
    )

    df = pd.concat([df, decoded_df], axis=1)

    # =========================================================
    # 5. CALCULATE VISCOSITY DROP
    # =========================================================
    df["Delta_V"] = (
        df["黏度(秒)"] - df["黏度(秒)_1"]
    )

    # =========================================================
    # 6. ASSIGN REJECTION REASONS
    # =========================================================
    df["Reject_Reason"] = ""

    # Paint code
    df.loc[
        df["Paint_Code"].isin(invalid_text_values),
        "Reject_Reason"
    ] += "缺少塗料編號；"

    # Paint weight
    df.loc[
        df["塗料重量"].isna(),
        "Reject_Reason"
    ] += "缺少塗料重量；"

    df.loc[
        df["塗料重量"].notna()
        & (df["塗料重量"] <= 0),
        "Reject_Reason"
    ] += "塗料重量≤0；"

    # Added solvent
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

    # Solvent type
    df.loc[
        df["Solvent_Type"].isin(invalid_text_values),
        "Reject_Reason"
    ] += "缺少稀釋劑種類；"

    # Before viscosity
    df.loc[
        df["黏度(秒)"].isna(),
        "Reject_Reason"
    ] += "缺少調整前黏度；"

    df.loc[
        df["黏度(秒)"].notna()
        & (df["黏度(秒)"] <= 0),
        "Reject_Reason"
    ] += "調整前黏度≤0；"

    # After viscosity
    df.loc[
        df["黏度(秒)_1"].isna(),
        "Reject_Reason"
    ] += "缺少調整後黏度；"

    df.loc[
        df["黏度(秒)_1"].notna()
        & (df["黏度(秒)_1"] <= 0),
        "Reject_Reason"
    ] += "調整後黏度≤0；"

    # Viscosity relationship
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
    # 7. DATA STATUS
    # =========================================================
    df["Data_Status"] = np.where(
        df["Reject_Reason"] == "",
        "Valid Group A",
        "Excluded from Solvent Analysis",
    )

    # =========================================================
    # 8. SPLIT VALID / EXCLUDED DATA
    # =========================================================
    valid_mask = df["Reject_Reason"] == ""

    group_a = df.loc[valid_mask].copy()
    rejected_data = df.loc[~valid_mask].copy()

    # =========================================================
    # 9. CALCULATIONS FOR VALID GROUP A
    # =========================================================
    if not group_a.empty:
        group_a["Solvent_Ratio"] = (
            group_a["添加重量"] / group_a["塗料重量"]
        )

        group_a["Solvent_Ratio_Percent"] = (
            group_a["Solvent_Ratio"] * 100
        )

        group_a["Viscosity_Sensitivity"] = np.where(
            group_a["Solvent_Ratio_Percent"] > 0,
            group_a["Delta_V"]
            / group_a["Solvent_Ratio_Percent"],
            np.nan,
        )

        group_a["Kg_Solvent_Per_1s"] = np.where(
            group_a["Delta_V"] > 0,
            group_a["添加重量"] / group_a["Delta_V"],
            np.nan,
        )

        group_a["Kg_Solvent_Per_1s_Per_100kg_Paint"] = np.where(
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

    return group_a, rejected_data
