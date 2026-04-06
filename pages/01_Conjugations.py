import streamlit as st
from src import config as con
from src import load_data as load
from src import select_input as input
from src.session import init_session_state
from src.checking import check_user_input
from src.logging_attempts import log_incorrect_attempt
import pandas as pd
import os
from html import escape


# --- COLOUR SCHEME & STYLE --------
st.markdown("""
    <style>
    .conjugation-shell {
        max-width: 1120px;
        margin: 0 auto;
        padding-bottom: 2rem;
    }

    .intro-shell {
        width: auto;
        margin: 0 0 1.25rem;
        padding-bottom: 0.25rem;
        text-align: left;
    }

    .hero-card {
        background:
            radial-gradient(circle at top right, rgba(59, 130, 246, 0.18), transparent 32%),
            linear-gradient(135deg, #fffdf7 0%, #ffffff 48%, #f3f8ff 100%);
        border: 1px solid rgba(148, 163, 184, 0.28);
        border-radius: 26px;
        padding: 1.6rem 1.75rem;
        box-shadow: 0 22px 50px rgba(15, 23, 42, 0.08);
        margin: 0.35rem 0 1.2rem;
    }

    .hero-eyebrow {
        display: inline-block;
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #1d4ed8;
        background: rgba(219, 234, 254, 0.88);
        border-radius: 999px;
        padding: 0.35rem 0.7rem;
        margin-bottom: 0.95rem;
    }

    .hero-grid {
        display: grid;
        grid-template-columns: minmax(0, 1.7fr) minmax(240px, 1fr);
        gap: 1rem;
        align-items: start;
    }

    .hero-title {
        font-size: clamp(2rem, 3vw, 2.8rem);
        line-height: 1.05;
        font-weight: 800;
        color: #0f172a;
        margin: 0 0 0.45rem;
    }

    .hero-prompt {
        font-size: 1.12rem;
        color: #334155;
        margin: 0;
        line-height: 1.65;
    }

    .hero-prompt strong {
        color: #0f172a;
    }

    .hero-meta {
        display: grid;
        gap: 0.75rem;
    }

    .metric-card {
        background: rgba(255, 255, 255, 0.86);
        border: 1px solid rgba(148, 163, 184, 0.22);
        border-radius: 18px;
        padding: 0.9rem 1rem;
    }

    .metric-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #64748b;
        margin-bottom: 0.3rem;
        font-weight: 700;
    }

    .metric-value {
        font-size: 1.05rem;
        font-weight: 700;
        color: #0f172a;
    }

    .practice-card {
        background: #ffffff;
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 22px;
        padding: 1.35rem;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        margin-bottom: 1rem;
    }

    .section-kicker {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #64748b;
        font-weight: 700;
        margin-bottom: 0.25rem;
    }

    .intro-kicker {
        display: inline-block;
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #1d4ed8;
        background: rgba(219, 234, 254, 0.88);
        border-radius: 999px;
        padding: 0.35rem 0.7rem;
        margin-bottom: 0.85rem;
    }

    .section-title {
        font-size: clamp(1.75rem, 2.6vw, 2.25rem);
        line-height: 1.06;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 0.4rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .section-copy {
        font-size: 0.96rem;
        color: #475569;
        margin-bottom: 0;
        line-height: 1.55;
        max-width: none;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0.65rem;
        padding: 0.3rem;
        background: rgba(241, 245, 249, 0.85);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 999px;
        width: fit-content;
        margin-bottom: 1rem;
    }

    .stTabs [data-baseweb="tab"] {
        height: auto;
        border-radius: 999px;
        padding: 0.6rem 1rem;
        font-weight: 700;
        color: #475569;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #2563eb 0%, #0f766e 100%);
        color: #ffffff !important;
        box-shadow: 0 10px 24px rgba(37, 99, 235, 0.24);
    }

    div.stButton > button {
        border: none !important;
        border-radius: 14px !important;
        padding: 0.72rem 1.15rem !important;
        font-size: 1rem !important;
        font-weight: 700 !important;
        color: #ffffff !important;
        background: linear-gradient(135deg, #2563eb 0%, #0f766e 100%) !important;
        box-shadow: 0 12px 22px rgba(37, 99, 235, 0.22) !important;
        transition: transform 0.18s ease, box-shadow 0.18s ease !important;
    }

    div.stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 16px 28px rgba(37, 99, 235, 0.28) !important;
    }

    div.stTextInput input {
        border-radius: 16px !important;
        border: 1px solid rgba(148, 163, 184, 0.45) !important;
        background: #f8fafc !important;
        padding: 0.8rem 0.95rem !important;
        font-size: 1rem !important;
    }

    div.stTextInput input:focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 0.18rem rgba(37, 99, 235, 0.14) !important;
    }

    [data-testid="stExpander"] {
        border: 1px solid rgba(148, 163, 184, 0.22);
        border-radius: 18px;
        overflow: hidden;
    }

    @media (max-width: 900px) {
        .hero-grid {
            grid-template-columns: 1fr;
        }

        .hero-card,
        .practice-card {
            padding: 1.1rem;
        }
    }
    </style>
""", unsafe_allow_html=True)


def render_page_intro() -> None:
    st.markdown(
        """
        <div class="intro-shell">
            <div class="intro-kicker">Conjugation Studio</div>
            <div class="section-title">Train one verb form at a time with clearer visual focus.</div>
            <p class="section-copy">
                Filter by tense or verb group, answer from memory, then move straight to the next prompt.
            </p>
        """,
        unsafe_allow_html=True,
    )


def render_practice_hero(verb: str, prompt: str, translation: str, attempts: int) -> None:
    prompt_parts = prompt.split(" — ", maxsplit=1)
    tense = escape(prompt_parts[0] if prompt_parts else prompt)
    subject = escape(prompt_parts[1] if len(prompt_parts) > 1 else "Mixed pronoun")
    safe_verb = escape(verb)
    safe_translation = escape(translation)

    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-grid">
                <div>
                    <div class="hero-eyebrow">Current Drill</div>
                    <div class="hero-title">{safe_verb}</div>
                    <p class="hero-prompt">
                        Conjugate in <strong>{tense}</strong> for <strong>{subject}</strong>.
                    </p>
                </div>
                <div class="hero-meta">
                    <div class="metric-card">
                        <div class="metric-label">English Meaning</div>
                        <div class="metric-value">{safe_translation}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Attempts On This Prompt</div>
                        <div class="metric-value">{attempts}</div>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_mistakes_log(log_path: str = "error_log.csv") -> None:
    st.subheader("📉 Mistakes Log")

    if os.path.exists(log_path):
        df = pd.read_csv(log_path)
        st.dataframe(
            df.style.set_properties(
                **{
                    "text-align": "left",
                    "background-color": "#fdfdfd",
                }
            ),
            width="stretch",
        )
        st.download_button(
            "Download log as CSV",
            data=df.to_csv(index=False),
            file_name="error_log.csv",
        )
    else:
        st.info("No mistakes logged yet. Perfect streak! 🥳")


# --------- MAIN APP ---------
init_session_state()


# --------- APP TITLE ---------
render_page_intro()


# --------- LOAD WORKBOOK ---------
wb = load.safe_load_workbook(con.EXCEL_FILE)
if wb is None:
    st.stop()
ws_input = wb["UserInput"]
ws_solution = wb["Solutions"]


# --- FILTER UI SIDEBAR ---
filter_options = set()
for r in range(con.START_ROW, ws_solution.max_row + 1):
    val = ws_solution[f"{con.FILTER_COL}{r}"].value
    if val: filter_options.add(val.strip())

filter_options = sorted(filter_options)
with st.sidebar:
    selected_filter = st.radio("🔍 Filter by verb group:", ["(All)"] + filter_options, horizontal=False)
    st.markdown("---")
    selected_tense = st.multiselect(
        "🎯 Filter by tense:",
        con.TENSE_OPTIONS,
        default=["(Random)"]
    )

    # Remove the random option when other tenses are selected
    if "(Random)" in selected_tense and len(selected_tense) > 1:
        selected_tense = [t for t in selected_tense if t != "(Random)"]

    selected_tense = selected_tense or ["(Random)"]


# Reset task if filter changes
if "last_filter" not in st.session_state:
    st.session_state["last_filter"] = selected_filter
if "last_tense" not in st.session_state:
    st.session_state["last_tense"] = selected_tense

# if selected_filter != st.session_state["last_filter"]:
if (selected_filter != st.session_state["last_filter"]) or (selected_tense != st.session_state["last_tense"]):
    st.session_state["last_filter"] = selected_filter
    st.session_state["last_tense"] = selected_tense
    st.session_state.pop("current_task", None)
    st.session_state.reset_input = True
    st.rerun()




# --------- TASK SETUP ---------
if "current_task" not in st.session_state:
    tense_filter = [t for t in selected_tense if t != "(Random)"]
    row, col, verb, prompt, translation = input.get_random_task(
        ws_solution,
        selected_filter,
        tense_filter if tense_filter else None,
    )
    st.session_state.current_task = {
        "row": row,
        "col": col,
        "verb": verb,
        "prompt": prompt,
        "translation": translation
    }
else:
    task = st.session_state.current_task
    row = task["row"]
    col = task["col"]
    verb = task["verb"]
    prompt = task["prompt"]
    translation = task["translation"]

# If the verb has changed, trigger input reset
if verb != st.session_state.last_verb:
    st.session_state.reset_input = True
    st.session_state.last_verb = verb

practice_tab, mistakes_tab = st.tabs(["Practice", "Mistakes Log"])

with practice_tab:
    # --------- UI + LOGIC ---------
    if row is None:
        st.success("🎉 All verbs have been completed!")
    else:
        tense = ws_solution[f"{col}1"].value
        subject = ws_solution[f"{col}2"].value

        render_practice_hero(verb, prompt, translation, st.session_state.attempts)

        st.markdown(
            """
            <div class="practice-card">
                <div class="section-kicker">Answer Zone</div>
                <div class="section-title">Write the conjugated form from memory.</div>
                <p class="section-copy">
                    Use the tense and pronoun guides below if you need a quick orientation.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        input.show_conjugation_position(tense, subject)

        user_input = st.text_input("Your conjugation:", key=f"user_input_{verb}")

        action_col, next_col = st.columns([1.3, 1])
        with action_col:
            check_answer = st.button("Check answer")
        with next_col:
            next_verb = st.button("Next verb")

        if check_answer:
            next_attempt = st.session_state.attempts + 1
            st.session_state.attempts = next_attempt

            correct_answer = str(ws_solution[f"{col}{row}"].value).strip()

            cell = ws_input[f"{col}{row}"]

            is_correct, cleaned_input = check_user_input(user_input, correct_answer, cell)

            if is_correct:
                st.success("✅ Correct!")
                st.session_state.attempts = 0
                st.session_state.reset_input = True
            else:
                st.error("❌ Incorrect. Try again or reveal answer.")
                if next_attempt >= 1:
                    with st.expander("📖 Show correct answer"):
                        st.markdown(f"**Correct answer:** `{correct_answer}`")

                log_incorrect_attempt(
                    verb,
                    tense,
                    subject,
                    user_input,
                    correct_answer,
                    log_path="error_log.csv",
                )

            filled = all(ws_input[f"{c}{row}"].value not in [None, ""] for c in con.CONJUGATION_COLS)
            if filled:
                ws_input[f"{con.STATUS_COL}{row}"].value = "True"

            wb.save(con.EXCEL_FILE)
            st.session_state.clear_input = True

    if row is not None and next_verb:
        st.session_state.pop("current_task", None)
        st.session_state.reset_input = True
        st.rerun()

with mistakes_tab:
    st.markdown(
        """
        <div class="practice-card">
            <div class="section-kicker">Review Queue</div>
            <div class="section-title">Keep an eye on the forms that still need work.</div>
            <p class="section-copy">
                Use this log to spot recurring trouble tenses and download your mistakes for later review.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_mistakes_log()

st.markdown("</div>", unsafe_allow_html=True)


# TODO: Allow accent's to be omitted for the word to be correct? (e.g. with unidecode library)
# TODO: Set option of different modes: random verb and form / go through verb one by one in all forms / go through one tense entirely for a verb but only that one tense (and show all personal pronouns at once with input fields)
# TODO: Check if a word has been "learned" if all inputs in the UserInput Sheet are correct and then mark it as TRUE (boolean) and not "True"
# TODO: Show progress (e.g. "50/1000 verbs completed") and a score of this session/today/always
# TODO: Show example/practice sentences (and formulate them in a certain style, e.g. dark humour, on a certain topic, e.g. current French politics)

# WRITEBACK:
# TODO: Fill (by hand!) remaining empty cells in the Excel tab "Solutions"
# TODO: Fix that the wrong answer is written back to the wrong cell in Excel somehow...
# TODO: Should previously wrong answers be overwritten? Excluded from future runs? Excluded unless you do X?


# SHIPPING:
# TODO: Include a user feedback field
# TODO: Write user signup
# TODO: Write docker file


# FURTHER IDEAS:
# TODO: Link to full table of conjugations for given verb?
# TODO: Audio playback (using an MP3 and st.audio())?
# TODO: A third tab with vocab trainer? You could for example add a button on the Practice tab that adds a word to the vocab trainer with translation
# TODO: Use database instead of Excel as backend
