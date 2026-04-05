from pathlib import Path

import streamlit as st

from src.vocab_pipeline import DEFAULT_MAX_WORKERS, batch_process_images, has_openai_api_key
from src.vocab_repository import approve_vocab_item, get_review_counts, get_vocab_item, ignore_vocab_item, init_vocab_db, list_vocab_items


st.title("🗂️ Vocabulary Inbox")
st.caption("Review Duolingo screenshots, correct the draft once, and save clean study items.")

init_vocab_db()

if "vocab_filter" not in st.session_state:
    st.session_state.vocab_filter = "pending"
if "vocab_selected_id" not in st.session_state:
    st.session_state.vocab_selected_id = None
if "vocab_flash" not in st.session_state:
    st.session_state.vocab_flash = None
if "vocab_workers" not in st.session_state:
    st.session_state.vocab_workers = DEFAULT_MAX_WORKERS

if st.session_state.vocab_flash:
    st.success(st.session_state.vocab_flash)
    st.session_state.vocab_flash = None

with st.sidebar:
    st.subheader("Inbox controls")
    st.session_state.vocab_filter = st.radio(
        "Show items",
        options=["pending", "approved", "ignored"],
        index=["pending", "approved", "ignored"].index(st.session_state.vocab_filter),
    )

    counts = get_review_counts()
    st.metric("Pending review", counts["pending"])
    st.metric("Approved", counts["approved"])
    st.metric("Ignored", counts["ignored"])

    if has_openai_api_key():
        st.session_state.vocab_workers = st.slider(
            "Parallel workers",
            min_value=1,
            max_value=8,
            value=st.session_state.vocab_workers,
            help="More workers can speed up large batches, but may hit API rate limits sooner.",
        )
        if st.button("Process screenshot folder", use_container_width=True):
            progress_text = st.empty()
            progress_bar = st.progress(0)

            def update_progress(stats: dict[str, int]) -> None:
                eligible = stats["eligible"]
                completed = stats["completed"]
                ratio = 0 if eligible == 0 else completed / eligible
                progress_bar.progress(ratio)
                progress_text.info(
                    f"Processing screenshots: {completed}/{eligible} complete, "
                    f"{stats['processed']} succeeded, {stats['failed']} failed."
                )

            stats = batch_process_images(
                max_workers=st.session_state.vocab_workers,
                progress_callback=update_progress,
            )
            progress_bar.progress(1.0 if stats["eligible"] else 0)
            progress_text.empty()
            if stats["failed"]:
                st.warning(
                    f"Eligible: {stats['eligible']}, processed: {stats['processed']}, failed: {stats['failed']}. "
                    f"If the failures are rate limits, try lowering `Parallel workers`."
                )
            else:
                st.success(
                    f"Eligible: {stats['eligible']}, processed: {stats['processed']}, failed: {stats['failed']}."
                )
            st.session_state.vocab_selected_id = None
            st.rerun()
        st.caption("This refreshes pending screenshots and adds new ones. Approved and ignored items are skipped.")
    else:
        st.warning("`OPENAI_API_KEY` not found. Existing DB entries can still be reviewed.")


items = list_vocab_items(st.session_state.vocab_filter)

if not items:
    st.info(f"No items with review status `{st.session_state.vocab_filter}` yet.")
    st.stop()

item_ids = [item["id"] for item in items]
if st.session_state.vocab_selected_id not in item_ids:
    st.session_state.vocab_selected_id = item_ids[0]

selected_item = get_vocab_item(st.session_state.vocab_selected_id)
if selected_item is None:
    st.warning("The selected item could not be loaded.")
    st.stop()

current_index = item_ids.index(selected_item["id"])
current_path = Path(selected_item["image_path"])

top_left, top_right = st.columns([3, 2])
with top_left:
    labels = [
        f'{item["file_name"]} · {item["review_status"]} · {item["study_phrase_fr"][:40] or "untitled"}'
        for item in items
    ]
    selected_label = st.selectbox(
        "Screenshot",
        options=labels,
        index=current_index,
    )
    chosen_id = items[labels.index(selected_label)]["id"]
    if chosen_id != st.session_state.vocab_selected_id:
        st.session_state.vocab_selected_id = chosen_id
        st.rerun()

with top_right:
    st.write(f"**File:** `{selected_item['file_name']}`")
    st.write(f"**Draft kind:** `{selected_item['capture_kind']}`")
    confidence = selected_item.get("confidence")
    if confidence is not None:
        st.write(f"**Model confidence:** `{confidence:.2f}`")
    st.write(f"**Processed:** `{selected_item.get('last_processed_ts') or 'n/a'}`")

left, right = st.columns([0.9, 1.3], gap="large")

with left:
    if current_path.exists():
        st.image(str(current_path), caption=selected_item["file_name"], width=360)
    else:
        st.warning(f"Screenshot file not found: {current_path}")

    with st.expander("Model draft", expanded=False):
        st.write(f"**Focused French:** {selected_item.get('focused_term_fr') or '—'}")
        st.write(f"**Sentence:** {selected_item.get('sentence_fr') or '—'}")
        st.write(f"**Translation:** {selected_item.get('translation_en') or '—'}")
        st.write(f"**Alternatives:** {', '.join(selected_item.get('alt_translations', [])) or '—'}")
        st.write(f"**Notes:** {selected_item.get('notes') or '—'}")
        st.json(selected_item.get("raw_json") or {})

with right:
    capture_kind = selected_item.get("capture_kind") or "other"
    study_target_options = ["Word or short phrase", "Whole sentence translation"]
    default_study_target = (
        "Whole sentence translation" if capture_kind == "full_sentence" else "Word or short phrase"
    )
    study_target_state_key = f"study_target_type_{selected_item['id']}"
    if study_target_state_key not in st.session_state:
        st.session_state[study_target_state_key] = default_study_target

    study_target_type = st.selectbox(
        "Study target type",
        options=study_target_options,
        key=study_target_state_key,
        help="Choose whether this screenshot should become a short vocab card or a full sentence translation card.",
    )
    is_whole_sentence = study_target_type == "Whole sentence translation"

    with st.form("vocab_review_form"):
        if capture_kind in {"sentence_completion", "full_sentence"}:
            default_context_fr = selected_item.get("sentence_fr") or selected_item["study_context_fr"]
            default_context_en = (
                selected_item.get("study_context_en")
                or selected_item.get("raw_json", {}).get("study_context_en", "")
                or selected_item["study_context_en"]
            )
        else:
            default_context_fr = selected_item["study_context_fr"]
            default_context_en = selected_item["study_context_en"]

        if is_whole_sentence:
            default_phrase_fr = default_context_fr or selected_item["study_phrase_fr"]
            default_phrase_en = default_context_en or selected_item["study_phrase_en"]
        elif capture_kind in {"sentence_completion", "full_sentence"}:
            default_phrase_fr = selected_item.get("focused_term_fr") or selected_item.get("study_phrase_fr")
            default_phrase_en = selected_item.get("translation_en") or selected_item["study_phrase_en"]
        else:
            default_phrase_fr = selected_item["study_phrase_fr"]
            default_phrase_en = selected_item["study_phrase_en"]

        study_phrase_fr = st.text_input(
            "French sentence" if is_whole_sentence else "French side",
            value=default_phrase_fr or "",
            help=(
                "The full French sentence you want to study."
                if is_whole_sentence
                else "The exact word or short phrase you want on the French side."
            ),
        )
        study_phrase_en = st.text_input(
            "English translation" if is_whole_sentence else "English side",
            value=default_phrase_en or "",
            help=(
                "The English translation paired with the French sentence."
                if is_whole_sentence
                else "The study translation you want paired with the French side."
            ),
        )

        if is_whole_sentence:
            study_context_fr = ""
            study_context_en = ""
        else:
            study_context_fr = st.text_area(
                "French context sentence",
                value=default_context_fr or "",
                height=120,
            )
            study_context_en = st.text_area(
                "English context sentence",
                value=default_context_en or "",
                height=120,
            )
        alt_translations = st.text_input(
            "Alternative translations",
            value=", ".join(selected_item.get("alt_translations", [])),
            help="Comma-separated. Optional.",
        )
        user_note = st.text_area(
            "Notes",
            value=selected_item.get("user_note") or "",
            height=100,
            help="Optional personal reminder or nuance.",
        )
        approve = st.form_submit_button("Approve item", type="primary")

    if approve:
        approved_capture_kind = "full_sentence" if is_whole_sentence else (
            capture_kind if capture_kind != "full_sentence" else "highlighted_phrase"
        )
        try:
            archived_path = approve_vocab_item(
                selected_item["id"],
                capture_kind=approved_capture_kind,
                study_phrase_fr=study_phrase_fr,
                study_phrase_en=study_phrase_en,
                study_context_fr=study_context_fr,
                study_context_en=study_context_en,
                alt_translations=[part.strip() for part in alt_translations.split(",") if part.strip()],
                user_note=user_note,
            )
        except Exception as exc:
            st.error(f"Could not approve this item: {exc}")
        else:
            message = "Vocabulary item approved."
            if archived_path:
                message = f"{message} Screenshot archived to {archived_path}."
            st.session_state.vocab_flash = message
            st.session_state.vocab_selected_id = None
            st.rerun()

    if st.button("Ignore screenshot", use_container_width=True):
        ignore_vocab_item(selected_item["id"])
        st.session_state.vocab_selected_id = None
        st.rerun()
