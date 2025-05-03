import os
import sys

# print("Working directory:", os.getcwd())
# Ensure project root is in the Python path
# sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import streamlit as st
from src import config as con
from src import load_data as load
from src import select_input as input


# --- MAIN APP ---
st.title("🇫🇷 French Verb Conjugation Trainer")

wb, ws = load.load_workbook_sheet()
row, col, verb, prompt = input.get_random_task(ws)

if row is None:
    st.success("🎉 All verbs have been completed!")
else:
    st.subheader(f"Verb: **{verb}**")
    st.write(f"Conjugate for: **{prompt}**")

    user_input = st.text_input("Your conjugation:")

    if st.button("Save answer"):
        ws[f"{col}{row}"].value = user_input

        # Check if the entire row is now filled
        filled = all(ws[f"{c}{row}"].value not in [None, ""] for c in con.CONJUGATION_COLS)
        if filled:
            ws[f"{con.STATUS_COL}{row}"].value = "True"

        wb.save(con.EXCEL_FILE)
        st.success("✅ Answer saved! Refresh to get a new verb.")