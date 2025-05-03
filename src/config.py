from openpyxl.utils import get_column_letter

# --- CONFIGURATION ---
EXCEL_FILE = "data/Top_1000_verbs_French.xlsx"
START_ROW = 3
VERB_COL = "B"
STATUS_COL = "AE"
# CONJUGATION_COLS = list(map(chr, range(ord("C"), ord("AV"))))  # Columns C to AU
CONJUGATION_COLS = [get_column_letter(i) for i in range(3, 48)]  # Columns C (3) to AU (47)