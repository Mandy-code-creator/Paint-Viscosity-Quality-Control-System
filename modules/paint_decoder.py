import pandas as pd

# Mapping Dictionaries
V_MAP = {'S':'Yungchi', 'T':'AKZO NOBEL(Taiwan)', 'A':'AKZO NOBEL', 'B':'Beckers', 
         'C':'Nan Pao', 'U':'Quali Poly', 'N':'Nippon', 'K':'Kansai', 
         'V':'Valspar', 'J':'Valspar (SW)', 'L':'KCC', 'R':'Noroo', 'Q':'Paoqun'}

R_MAP = {'1':'PU', '2':'PE', '3':'EPOXY', '4':'PVC', '5':'PVDF', '6':'SMP', 
         '7':'AC', '8':'WB', '9':'IP', 'A':'PVB', 'B':'PVF'}

C_MAP = {'0':'Clear', '1':'Red', 'R':'Red', 'O':'Orange', '2':'Orange', 'Y':'Yellow', 
         '3':'Yellow', '4':'Green', 'G':'Green', '5':'Blue', 'L':'Blue', 'V':'Violet', 
         '6':'Violet', 'N':'Brown', '7':'Brown', 'T':'White', 'H':'White', 'W':'White', 
         '8':'White', 'A':'Gray', 'C':'Gray', '9':'Gray', 'B':'Black', 'S':'Silver', 'M':'Metallic'}

F_MAP = {'B':'Anti-Bacteria', 'C':'High-Corrosion Resistance', 'D':'Anti-Dust', 
         'E':'Anti-Electrostatics', 'F':'High Formability', 'G':'General Usage', 
         'H':'Thermal Insulation', 'K':'Anti-Stain/Grease', 'L':'Whiteboard', 
         'M':'Mirror-like Paint', 'N':'Neo Matt', 'P':'Primer B', 
         'R':'Repaint System', 'S':'Shutter', 'T':'Texture Surface', 
         'V':'Variety', 'U':'Ultra-High Formability', 'W':'Wrinkle Paint', 'Z':'Other'}

def decode_paint_code(code_str):
    """Decodes the 4-character paint code into Vendor, Resin, Color, and Feature."""
    code = str(code_str).upper().strip()
    
    if len(code) < 4 or code == 'NAN':
        return pd.Series(['Unknown', 'Unknown', 'Unknown', 'Unknown'])
    
    vendor = V_MAP.get(code[0], 'Unknown')
    resin = R_MAP.get(code[1], 'Unknown')
    color = C_MAP.get(code[2], 'Unknown')
    feature = F_MAP.get(code[3], 'Unknown')
    
    return pd.Series([vendor, resin, color, feature])
