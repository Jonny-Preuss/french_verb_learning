import streamlit as st

from src.vocab_repository import (
    choose_practice_vocab_item,
    get_approved_vocab_count,
    get_vocab_item,
    get_vocab_practice_stats,
    init_vocab_db,
    is_vocab_answer_correct,
    record_vocab_practice_attempt,
)


st.markdown(
    """
    <style>
    .practice-shell {
        max-width: 1220px;
        margin: 0;
        padding-bottom: 2rem;
    }

    .practice-intro {
        width: auto;
        margin: 0 0 1.25rem;
        padding-bottom: 0.25rem;
        text-align: left;
    }

    .practice-kicker {
        display: inline-block;
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #1d4ed8;
        background: rgba(219, 234, 254, 0.88);
        border-radius: 999px;
        padding: 0.35rem 0.7rem;
        margin-bottom: 0.9rem;
    }

    .practice-title {
        font-size: clamp(2rem, 3vw, 2.7rem);
        line-height: 1.05;
        font-weight: 800;
        color: #0f172a;
        margin: 0 0 0.45rem;
    }

    .practice-copy {
        font-size: 0.96rem;
        color: #334155;
        margin: 0;
        line-height: 1.6;
        max-width: none;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .practice-focus {
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, rgba(243, 248, 255, 0.98) 100%);
        border: 1px solid rgba(148, 163, 184, 0.22);
        border-radius: 26px;
        padding: 1.5rem 1.6rem;
        box-shadow: 0 16px 34px rgba(15, 23, 42, 0.06);
        margin: 1rem 0 1rem;
        text-align: center;
    }

    .practice-focus-kicker {
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #1d4ed8;
        font-weight: 700;
        margin-bottom: 0.6rem;
    }

    .practice-focus-term {
        width: 100%;
        font-size: clamp(1.9rem, 3vw, 3.25rem);
        line-height: 1.05;
        font-weight: 800;
        color: #0f172a;
        margin: 0 auto 0.5rem;
        max-width: none;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .practice-focus-note {
        font-size: 1rem;
        color: #475569;
        margin: 0 auto;
        max-width: 52ch;
    }

    .practice-copy strong {
        color: #0f172a;
    }

    .practice-stats {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.8rem;
        margin-top: 1rem;
    }

    .practice-stat {
        background: rgba(255, 255, 255, 0.85);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 18px;
        padding: 0.9rem 1rem;
    }

    .practice-stat-label {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #64748b;
        font-weight: 700;
        margin-bottom: 0.3rem;
    }

    .practice-stat-value {
        font-size: 1.05rem;
        font-weight: 800;
        color: #0f172a;
    }

    .practice-card {
        background: #ffffff;
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 22px;
        padding: 1.1rem;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
        margin-bottom: 1rem;
    }

    .practice-card-title {
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #1d4ed8;
        font-weight: 700;
        margin-bottom: 0.3rem;
    }

    .practice-card-copy {
        color: #334155;
        margin: 0;
        line-height: 1.55;
    }

    .practice-answer-wrap {
        background: #ffffff;
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 24px;
        padding: 1.1rem 1.15rem 1.2rem;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
        margin-top: 1rem;
    }

    .practice-answer-label {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #1d4ed8;
        font-weight: 700;
        margin-bottom: 0.35rem;
    }

    .practice-answer-copy {
        color: #334155;
        margin: 0 0 0.85rem;
        line-height: 1.55;
    }

    div[data-testid="stTextArea"] textarea {
        border-radius: 18px !important;
        border: 1px solid rgba(148, 163, 184, 0.45) !important;
        background: #f8fafc !important;
        padding: 1rem 1.1rem !important;
        font-size: 1.08rem !important;
        min-height: 130px !important;
        line-height: 1.55 !important;
    }

    div[data-testid="stTextArea"] textarea:focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 0.18rem rgba(37, 99, 235, 0.14) !important;
    }

    .practice-footer {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.8rem;
        margin-top: 1rem;
    }

    .practice-footer-card {
        background: rgba(248, 250, 252, 0.96);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 18px;
        padding: 0.85rem 0.95rem;
    }

    .practice-footer-label {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #64748b;
        font-weight: 700;
        margin-bottom: 0.25rem;
    }

    .practice-footer-value {
        color: #0f172a;
        font-weight: 700;
    }

    .practice-footer-note {
        margin-top: 0.25rem;
        color: #64748b;
        font-size: 0.82rem;
        line-height: 1.35;
    }

    div.stButton > button,
    div[data-testid="stFormSubmitButton"] button,
    div[data-testid="stFormSubmitButton"] button[kind="primary"],
    button[kind="primary"] {
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

    div.stButton > button:hover,
    div[data-testid="stFormSubmitButton"] button:hover,
    div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
    button[kind="primary"]:hover {
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

    .stSelectbox [data-baseweb="select"] > div {
        border-radius: 16px;
    }

    @media (max-width: 960px) {
        .practice-stats {
            grid-template-columns: 1fr;
        }

        .practice-footer {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

init_vocab_db()

if "vocab_practice_card_id" not in st.session_state:
    st.session_state.vocab_practice_card_id = None
if "vocab_practice_checked" not in st.session_state:
    st.session_state.vocab_practice_checked = False
if "vocab_practice_result" not in st.session_state:
    st.session_state.vocab_practice_result = None
if "vocab_practice_reveal" not in st.session_state:
    st.session_state.vocab_practice_reveal = None
if "vocab_practice_session_correct" not in st.session_state:
    st.session_state.vocab_practice_session_correct = 0
if "vocab_practice_session_incorrect" not in st.session_state:
    st.session_state.vocab_practice_session_incorrect = 0
if "vocab_practice_flash" not in st.session_state:
    st.session_state.vocab_practice_flash = None


def _reset_current_card() -> None:
    st.session_state.vocab_practice_card_id = None
    st.session_state.vocab_practice_checked = False
    st.session_state.vocab_practice_result = None
    st.session_state.vocab_practice_reveal = None


def _load_next_card() -> dict | None:
    card = choose_practice_vocab_item()
    if card is None:
        return None
    st.session_state.vocab_practice_card_id = card["id"]
    st.session_state.vocab_practice_checked = False
    st.session_state.vocab_practice_result = None
    st.session_state.vocab_practice_reveal = None
    return card


approved_count = get_approved_vocab_count()
if approved_count == 0:
    st.info("No approved vocabulary cards yet. Approve a few items in Vocabulary Inbox first.")
    st.stop()

if st.session_state.vocab_practice_flash:
    st.warning(st.session_state.vocab_practice_flash)
    st.session_state.vocab_practice_flash = None

current_card = None
if st.session_state.vocab_practice_card_id:
    current_card = get_vocab_item(st.session_state.vocab_practice_card_id)

if current_card is None:
    current_card = _load_next_card()

if current_card is None:
    st.info("No practice-ready vocabulary cards were found. Check that approved cards have both English and French filled in.")
    st.stop()

expected_answer = (current_card.get("study_phrase_fr") or "").strip()
prompt_en = (current_card.get("study_phrase_en") or "").strip()

if not expected_answer or not prompt_en:
    st.session_state.vocab_practice_flash = (
        f"Skipped `{current_card.get('file_name') or current_card['id']}` because its approved English or French side is blank."
    )
    _reset_current_card()
    st.rerun()

stats = get_vocab_practice_stats(current_card["id"])

st.markdown(
    f"""
    <div class="practice-shell">
        <div class="practice-intro">
            <div class="practice-kicker">Vocabulary Practice</div>
            <div class="practice-title">Answer from memory, then move straight to the next card.</div>
            <p class="practice-copy">
                Train the French side one prompt at a time, keep the review loop quick, and let mistakes come back
                more often until they stick.
            </p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.subheader("Practice stats")
    st.metric("Approved cards", approved_count)
    st.metric("Session correct", st.session_state.vocab_practice_session_correct)
    st.metric("Session incorrect", st.session_state.vocab_practice_session_incorrect)

st.markdown(
    f"""
    <div class="practice-focus">
        <div class="practice-focus-kicker">Translate this</div>
        <div class="practice-focus-term">{prompt_en}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if current_card.get("study_context_fr") and current_card.get("study_context_en"):
    with st.expander("Context", expanded=False):
        st.write(f"**French:** {current_card['study_context_fr']}")
        st.write(f"**English:** {current_card['study_context_en']}")

answer_key = f"vocab_practice_answer_{current_card['id']}"
if answer_key not in st.session_state:
    st.session_state[answer_key] = ""

st.markdown(
    """
    <div class="practice-answer-wrap">
        <div class="practice-answer-label">French answer</div>
        <div class="practice-answer-copy">Type your translation here before checking it against the card.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

user_answer = st.text_area(
    "",
    key=answer_key,
    disabled=st.session_state.vocab_practice_checked,
    height=140,
    label_visibility="collapsed",
    placeholder="Write the French translation here...",
)

check_disabled = st.session_state.vocab_practice_checked or not user_answer.strip()
if st.button("Check answer", type="primary", disabled=check_disabled):
    is_correct = is_vocab_answer_correct(user_answer, expected_answer)
    record_vocab_practice_attempt(
        current_card["id"],
        prompt_en=prompt_en,
        expected_answer_fr=expected_answer,
        user_answer_fr=user_answer,
        is_correct=is_correct,
    )
    st.session_state.vocab_practice_checked = True
    st.session_state.vocab_practice_result = is_correct
    st.session_state.vocab_practice_reveal = expected_answer
    if is_correct:
        st.session_state.vocab_practice_session_correct += 1
    else:
        st.session_state.vocab_practice_session_incorrect += 1
    st.rerun()

if st.session_state.vocab_practice_checked:
    if st.session_state.vocab_practice_result:
        st.success("✅ Correct!")
    else:
        st.error("❌ Incorrect.")
        st.markdown(f"**Correct answer:** `{st.session_state.vocab_practice_reveal}`")

    if st.button("Next vocab", use_container_width=True):
        st.session_state.pop(answer_key, None)
        _reset_current_card()
        st.rerun()

st.markdown(
    f"""
    <div class="practice-footer">
        <div class="practice-footer-card">
            <div class="practice-footer-label">Approved cards</div>
            <div class="practice-footer-value">{approved_count}</div>
            <div class="practice-footer-note">Cards already approved in the inbox and ready for practice.</div>
        </div>
        <div class="practice-footer-card">
            <div class="practice-footer-label">Lifetime attempts</div>
            <div class="practice-footer-value">{stats['practice_attempts']}</div>
            <div class="practice-footer-note">Total times this exact card has been shown and answered.</div>
        </div>
        <div class="practice-footer-card">
            <div class="practice-footer-label">Lifetime misses</div>
            <div class="practice-footer-value">{stats['practice_incorrect']}</div>
            <div class="practice-footer-note">How many of those attempts were marked incorrect.</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
