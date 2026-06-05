import pandas as pd

def decode_paint_code(paint_code_str):
    """
    Decodes the paint code based on the established factory structure (e.g., PT2N10B07)
    - Index 0 (1st char): Primary Classification (Char_1)
    - Index 1 (2nd char): Vendor (V_MAP)
    - Index 2 (3rd char): Resin (R_MAP)
    - Index 3 (4th char): Application / Feature (F_MAP) - Numbers default to 'General Usage'
    - Index 6 (7th char): Color (C_MAP)
    """
    if not isinstance(paint_code_str, str) or len(paint_code_str) < 1:
        return pd.Series(['Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown'])

    code = paint_code_str.strip().upper()

    # 1. Vendor Dictionary
    v_map = {
        'S': 'Yungchi', 'T': 'AKZO NOBEL(Taiwan)', 'A': 'AKZO NOBEL', 'B': 'Beckers', 
        'C': 'Nan Pao', 'U': 'Quali Poly', 'N': 'Nippon', 'K': 'Kansai', 
        'V': 'Valspar', 'J': 'Valspar (SW)', 'L': 'KCC', 'R': 'Noroo', 'Q': 'Paoqun'
    }
    
    # 2. Resin Dictionary
    r_map = {
        '1': 'PU', '2': 'PE', '3': 'EPOXY', '4': 'PVC', '5': 'PVDF', '6': 'SMP',
        '7': 'AC', '8': 'WB', '9': 'IP', 'A': 'PVB', 'B': 'PVF'
    }
    
    # 3. Application / Feature Dictionary
    f_map = {
        'B': 'Anti-Bacteria', 'C': 'High-Corrosion Resistance', 'D': 'Anti-Dust', 
        'E': 'Anti-Electrostatics', 'F': 'High Formability', 'G': 'General Usage', 
        'H': 'Thermal Insulation', 'K': 'Anti-Stain/Grease', 'L': 'Whiteboard', 
        'M': 'Mirror-like Paint', 'N': 'Neo Matt', 'P': 'Primer B', 
        'R': 'Repaint System', 'S': 'Shutter', 'T': 'Texture Surface', 
        'V': 'Variety', 'U': 'Ultra-High Formability', 'W': 'Wrinkle Paint', 'Z': 'Other'
    }

    # 4. Color Dictionary
    c_map = {
        '0': 'Clear', '1': 'Red', 'R': 'Red', 'O': 'Orange', '2': 'Orange', 
        'Y': 'Yellow', '3': 'Yellow', '4': 'Green', 'G': 'Green', '5': 'Blue', 
        'L': 'Blue', 'V': 'Violet', '6': 'Violet', 'N': 'Brown', '7': 'Brown', 
        'T': 'White', 'H': 'White', 'W': 'White', '8': 'White', 'A': 'Gray', 
        'C': 'Gray', '9': 'Gray', 'B': 'Black', 'S': 'Silver', 'M': 'Metallic'
    }

    # Extract based on verified positions
    char_1 = code[0] if len(code) >= 1 else 'Unknown'
    vendor = v_map.get(code[1], 'Unknown') if len(code) >= 2 else 'Unknown'
    resin = r_map.get(code[2], 'Unknown') if len(code) >= 3 else 'Unknown'
    
    # Extract Application from the 4th character
    if len(code) >= 4:
        char_4 = code[3]
        if char_4.isdigit():  
            feature = f_map.get('G')  # Default numeric codes to General Usage
        else:
            feature = f_map.get(char_4, 'Unknown')
    else:
        feature = 'Unknown'
    
    # Extract Color (7th character -> Index 6)
    color = c_map.get(code[6], 'Unknown') if len(code) >= 7 else 'Unknown'
    
    return pd.Series([vendor, resin, feature, color, char_1])
