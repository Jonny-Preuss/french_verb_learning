from openpyxl.utils import get_column_letter

# --- CONFIGURATION ---
EXCEL_FILE = "data/Top_1000_verbs_French_USE.xlsx"
START_ROW = 3
VERB_COL = "B"
TRANSLATION_COL = "C"
FILTER_COL = "F"
STATUS_COL = "AW"
# CONJUGATION_COLS = list(map(chr, range(ord("G"), ord("AV"))))  # Columns G to AU
CONJUGATION_COLS = [get_column_letter(i) for i in range(5, 48)]  # Columns G (3) to AV (47)

# ---- COLOUR SCHEME ------
base = "light"
primaryColor = "#1f77b4"  # Streamlit's default blue
