import random
from src import config as con

# --- SELECT RANDOM VERB AND COLUMN ---
def get_random_task(ws):
    rows = range(con.START_ROW, ws.max_row + 1)
    available_rows = [r for r in rows if str(ws[f"{con.STATUS_COL}{r}"].value).strip().lower() != "true"]
    if not available_rows:
        return None, None, None, None

    row = random.choice(available_rows)
    col = random.choice(con.CONJUGATION_COLS)

    verb = ws[f"{con.VERB_COL}{row}"].value
    tense = ws[f"{col}1"].value
    subject = ws[f"{col}2"].value
    return row, col, verb, f"{tense} — {subject}"