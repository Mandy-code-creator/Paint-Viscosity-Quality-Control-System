import pandas as pd

def decode_paint_code(paint_code_str):
    """
    Giải mã chuẩn xác theo cấu trúc mã xưởng thực tế (VD: PT2N10B07)
    """
    # Xử lý nếu mã trống
    if not isinstance(paint_code_str, str) or len(paint_code_str) < 1:
        return pd.Series(['Unknown', 'Unknown', 'Unknown', 'Unknown'])

    code = paint_code_str.strip().upper()

    v_map = {
        'S':'Yungchi', 'T':'AKZO NOBEL(Taiwan)', 'A':'AKZO NOBEL', 'B':'Beckers', 
        'C':'Nan Pao', 'U':'Quali Poly', 'N':'Nippon', 'K':'Kansai', 
        'V':'Valspar', 'J':'Valspar (SW)', 'L':'KCC', 'R':'Noroo', 'Q':'Paoqun'
    }
    
    r_map = {
        '1':'PU', '2':'PE', '3':'EPOXY', '4':'PVC', '5':'PVDF', '6':'SMP',
        '7':'AC', '8':'WB', '9':'IP', 'A':'PVB', 'B':'PVF'
    }
    
    c_map = {
        '0':'Clear', '1':'Red', 'R':'Red', 'O':'Orange', '2':'Orange', 
        'Y':'Yellow', '3':'Yellow', '4':'Green', 'G':'Green', '5':'Blue', 
        'L':'Blue', 'V':'Violet', '6':'Violet', 'N':'Brown', '7':'Brown', 
        'T':'White', 'H':'White', 'W':'White', '8':'White', 'A':'Gray', 
        'C':'Gray', '9':'Gray', 'B':'Black', 'S':'Silver', 'M':'Metallic'
    }

    # 1. Ký tự đầu (Vị trí 0)
    char_1 = code[0] if len(code) >= 1 else 'Unknown'
    
    # 2. Nhà cung cấp (Vị trí 1)
    vendor = v_map.get(code[1], 'Unknown') if len(code) >= 2 else 'Unknown'
    
    # 3. Loại nhựa (Vị trí 2)
    resin = r_map.get(code[2], 'Unknown') if len(code) >= 3 else 'Unknown'
    
    # 4. Màu sắc (Vị trí 3)
    color = c_map.get(code[3], 'Unknown') if len(code) >= 4 else 'Unknown'
    
    # 5. Phần đuôi còn lại
    tail = code[4:] if len(code) >= 5 else ''
    
    # Ghép Màu sắc và Phần đuôi thành Mục đích sử dụng (Feature)
    # Ví dụ: "Brown (10B07)"
    feature = f"{color} ({tail})" if tail else color

    # Trả về đúng 4 giá trị để khớp với file data_validation
    return pd.Series([vendor, resin, feature, char_1])
