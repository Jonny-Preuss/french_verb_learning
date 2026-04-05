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


st.title("📝 Vocabulary Practice")
st.caption("See the English prompt, type the French answer, and revisit mistakes more often over time.")

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

with st.sidebar:
    st.subheader("Practice stats")
    st.metric("Approved cards", approved_count)
    st.metric("Session correct", st.session_state.vocab_practice_session_correct)
    st.metric("Session incorrect", st.session_state.vocab_practice_session_incorrect)

left, right = st.columns([1.4, 1], gap="large")

with left:
    st.subheader("English prompt")
    st.markdown(f"### {prompt_en}")
    if current_card.get("capture_kind") == "full_sentence":
        st.caption("Answer with the full French sentence.")
    else:
        st.caption("Answer with the French word or short phrase.")

    if current_card.get("study_context_fr") and current_card.get("study_context_en"):
        with st.expander("Context", expanded=False):
            st.write(f"**French:** {current_card['study_context_fr']}")
            st.write(f"**English:** {current_card['study_context_en']}")

with right:
    st.subheader("Current card")
    st.write(f"**Lifetime attempts:** {stats['practice_attempts']}")
    st.write(f"**Lifetime misses:** {stats['practice_incorrect']}")
    if current_card.get("last_practiced_ts"):
        st.write(f"**Last practiced:** `{current_card['last_practiced_ts']}`")

answer_key = f"vocab_practice_answer_{current_card['id']}"
if answer_key not in st.session_state:
    st.session_state[answer_key] = ""

user_answer = st.text_input(
    "French answer",
    key=answer_key,
    disabled=st.session_state.vocab_practice_checked,
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
