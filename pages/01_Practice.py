import streamlit as st
from src import config as con
from src import load_data as load
from src import select_input as input
from openpyxl.styles import PatternFill
from datetime import datetime
import pandas as pd
import os


# --- COLOUR SCHEME --------
st.markdown("""
    <style>
    div.stButton > button {
        background-color: #f0f0f0 !important;
        color: black !important;
        border: 1px solid #ccc !important;
        padding: 0.5em 1.2em !important;
        border-radius: 6px !important;
        font-size: 1rem !important;
    }

    div.stButton > button:hover {
        background-color: #d6e4ff !important;  /* light blue */
        color: black !important;
        border-color: #a0c4ff !important;
    }
    </style>
""", unsafe_allow_html=True)


# --------- MAIN APP ---------

if "attempts" not in st.session_state:
    st.session_state.attempts = 0

if "reset_input" not in st.session_state:
    st.session_state.reset_input = False

if "last_verb" not in st.session_state:
    st.session_state.last_verb = None

st.title("🇫🇷 French Verb Conjugation Trainer")


wb = load.safe_load_workbook(con.EXCEL_FILE)
if wb is None:
    st.stop()
ws_input = wb["UserInput"]
ws_solution = wb["Solutions"]

if "current_task" not in st.session_state:
    row, col, verb, prompt = input.get_random_task(ws_solution)
    st.session_state.current_task = {
        "row": row,
        "col": col,
        "verb": verb,
        "prompt": prompt
    }
else:
    task = st.session_state.current_task
    row = task["row"]
    col = task["col"]
    verb = task["verb"]
    prompt = task["prompt"]

# If the verb has changed, trigger input reset
if verb != st.session_state.last_verb:
    st.session_state.reset_input = True
    st.session_state.last_verb = verb

if row is None:
    st.success("🎉 All verbs have been completed!")
else:
    st.subheader(f"Verb: **{verb}**")
    st.write(f"Conjugate for: **{prompt}**")

    tense = ws_solution[f"{col}1"].value
    subject = ws_solution[f"{col}2"].value
    input.show_conjugation_position(tense, subject)


    # if st.session_state.reset_input:
    #     if "user_input" in st.session_state:
    #         del st.session_state["user_input"]
    #     st.session_state.reset_input = False  # ✅ Reset the flag after deletion

    # Render input field, showing previous value unless reset_input is True
    # if st.session_state.get("reset_input", False):
    #     user_input = st.text_input("Your conjugation:", value="", key="user_input_temp")
    #     st.session_state["user_input"] = ""
    #     st.session_state.reset_input = False
    # else:
    #     user_input = st.text_input("Your conjugation:", key="user_input")

    user_input = st.text_input("Your conjugation:", key=f"user_input_{verb}")


    # user_input = st.text_input("Your conjugation:", key=f"user_input_{verb}")

    


    if st.button("Check answer"):
        st.session_state.attempts += 1

        # user_input_clean = st.session_state.get("user_input", "").strip() # capture immediately
        user_input_clean = user_input.strip() # capture immediately
        
        # Fetch the correct answer from the solution sheet
        correct_answer = str(ws_solution[f"{col}{row}"].value).strip()

        # Save user input to the input sheet
        cell = ws_input[f"{col}{row}"] # TODO: Check correct cell referencing for UserInput sheet
        cell.value = user_input_clean

        # Define fill styles
        green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
        red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

        # Compare and apply style
        if user_input_clean.lower() == correct_answer.lower():
            # TODO: Check on past participle correct forms (", ...")
            st.success("✅ Correct!")
            cell.fill = green_fill
            st.session_state.attempts = 0
            st.session_state.reset_input = True
            

        else:
            st.error(f"❌ Incorrect. Try again or reveal answer.")
            print(correct_answer)
            print(st.session_state.attempts)

            if st.session_state.attempts >= 1:
                
                with st.expander("📖 Show correct answer"):
                    st.markdown(f"**Correct answer:** `{correct_answer}`")

            cell.fill = red_fill
            # TODO: Retrying incorrect tries empties the input cell, but here we would want to keep it


            # Append incorrect attempt to log
            log_entry = {
                "timestamp": datetime.now().strftime("%Y-%m-%d"),
                "verb": verb,
                "tense": ws_solution[f"{col}1"].value,
                "subject": ws_solution[f"{col}2"].value,
                "user_input": user_input_clean,
                "correct_answer": correct_answer
            }

            log_df = pd.DataFrame([log_entry])
            log_path = "error_log.csv"

            if os.path.exists(log_path):
                log_df.to_csv(log_path, mode="a", header=False, index=False)
            else:
                log_df.to_csv(log_path, mode="w", header=True, index=False)

        # Check if full row is complete
        filled = all(ws_input[f"{c}{row}"].value not in [None, ""] for c in con.CONJUGATION_COLS)
        if filled:
            ws_input[f"{con.STATUS_COL}{row}"].value = "True"

        wb.save(con.EXCEL_FILE)

        # # ✅ Clear the input field AFTER saving and feedback
        st.session_state.clear_input = True

if st.button("Next verb"):
    st.session_state.pop("current_task", None)
    st.session_state.reset_input = True  # ✅ sets flag
    st.rerun()


# TODO: Exclude "auxiliaire" verb from the checks
# TODO: Allow accent's to be omitted for the word to be correct?
# TODO: Set possible filters upfront (e.g. only -er/ir/-... verbs, specific tenses, ...)
# TODO: Not use the English translation as an input, but use it for a hidden field that shows the translation so you can also practice your vocabulary -> potential for a third tab with vocac trainer
# TODO: Link to full table of conjugations for given verb?
# TODO: Audio playback (using an MP3 and st.audio())?