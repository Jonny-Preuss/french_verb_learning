from openpyxl.utils import get_column_letter

# --- CONFIGURATION ---
EXCEL_FILE = "data/Top_1000_verbs_French_USE_test.xlsx"
START_ROW = 3
VERB_COL = "B"
TRANSLATION_COL = "C"
FILTER_COL = "F"
STATUS_COL = "AW"
CONJUGATION_COLS = [get_column_letter(i) for i in range(6, 48)]  # Columns G to AV


# ---- COLOUR SCHEME ------
base = "light"
primaryColor = "#1f77b4"  # Streamlit's default blue


# ---- TENSE MAPPING ----
PRESENT_COLS = [get_column_letter(i) for i in range(14, 20)]  # Columns O to T
IMPARFAIT_COLS = [get_column_letter(i) for i in range(20, 26)]  # Columns U to Z
FUTUR_COLS = [get_column_letter(i) for i in range(27, 33)]  # Columns AB to AG
SUBJONCTIF_COLS = [get_column_letter(i) for i in range(34, 40)]  # Columns AI to AN
CONDITIONNEL_COLS = [get_column_letter(i) for i in range(41, 47)]  # Columns AP to AU
IMPERATIF_COLS = [get_column_letter(i) for i in range(11, 14)]  # Columns L to N
OTHER_COLS = ["G", "H", "I", "J", "K", "AA", "AH", "AO", "AV"]

TENSES = {
    "Présent": PRESENT_COLS,
    "Imparfait": IMPARFAIT_COLS,
    "Futur": FUTUR_COLS,
    "Subjonctif": SUBJONCTIF_COLS,
    "Conditionnel": CONDITIONNEL_COLS,
    "Impératif": IMPERATIF_COLS,
    "Autres": OTHER_COLS,
}
