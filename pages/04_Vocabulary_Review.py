from pathlib import Path

import streamlit as st

from src.vocab_pipeline import DEFAULT_MAX_WORKERS, batch_process_images, has_openai_api_key
from src.vocab_repository import approve_vocab_item, get_review_counts, get_vocab_item, ignore_vocab_item, init_vocab_db, list_vocab_items


st.markdown(
    """
    <style>
    .inbox-shell {
        max-width: 1220px;
        margin: 0 auto;
        padding-bottom: 2rem;
    }

    .inbox-hero {
        background:
            radial-gradient(circle at top right, rgba(59, 130, 246, 0.18), transparent 32%),
            linear-gradient(135deg, #fffdf7 0%, #ffffff 48%, #f3f8ff 100%);
        border: 1px solid rgba(148, 163, 184, 0.24);
        border-radius: 26px;
        padding: 1.45rem 1.6rem;
        box-shadow: 0 18px 42px rgba(15, 23, 42, 0.07);
        margin: 0 0 1rem;
    }

    .inbox-kicker {
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

    .inbox-title {
        font-size: clamp(2rem, 3vw, 2.7rem);
        line-height: 1.05;
        font-weight: 800;
        color: #0f172a;
        margin: 0 0 0.45rem;
    }

    .inbox-copy {
        font-size: 1.05rem;
        color: #334155;
        margin: 0;
        line-height: 1.6;
        max-width: 64ch;
    }

    .inbox-copy strong {
        color: #0f172a;
    }

    .inbox-stats {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.8rem;
        margin-top: 1rem;
    }

    .inbox-stat {
        background: rgba(255, 255, 255, 0.85);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 18px;
        padding: 0.9rem 1rem;
    }

    .inbox-stat-label {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #64748b;
        font-weight: 700;
        margin-bottom: 0.3rem;
    }

    .inbox-stat-value {
        font-size: 1.15rem;
        font-weight: 800;
        color: #0f172a;
    }

    .inbox-grid {
        display: grid;
        grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
        gap: 1rem;
        align-items: start;
        margin-top: 1rem;
    }

    .inbox-card {
        background: #ffffff;
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 22px;
        padding: 1.1rem;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
    }

    .inbox-card--soft {
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.92) 0%, rgba(248, 250, 252, 0.98) 100%);
        padding: 0.85rem 0.95rem;
        border-radius: 18px;
    }

    .inbox-card--tint {
        background:
            radial-gradient(circle at top right, rgba(59, 130, 246, 0.10), transparent 35%),
            linear-gradient(180deg, rgba(255, 255, 255, 0.94) 0%, rgba(243, 248, 255, 0.96) 100%);
    }

    .inbox-card-title {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #1d4ed8;
        font-weight: 700;
        margin-bottom: 0.3rem;
    }

    .inbox-card-copy {
        color: #334155;
        margin: 0 0 0.9rem;
        line-height: 1.55;
    }

    .inbox-preview {
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 18px;
        overflow: hidden;
        background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
    }

    .inbox-preview img {
        display: block;
        width: 100%;
        height: auto;
    }

    .inbox-meta {
        display: grid;
        gap: 0.7rem;
        margin-top: 0.9rem;
    }

    .inbox-meta-card {
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, rgba(243, 248, 255, 0.98) 100%);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 18px;
        padding: 0.95rem 1rem;
    }

    .meta-label {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #64748b;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }

    .meta-value {
        color: #0f172a;
        font-weight: 700;
        font-size: 0.98rem;
        word-break: break-word;
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

    [data-baseweb="select"] {
        border-radius: 16px;
    }

    .stSelectbox [data-baseweb="select"] > div {
        border-radius: 16px;
    }

    @media (max-width: 960px) {
        .inbox-stats,
        .inbox-grid {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

init_vocab_db()

if "vocab_filter" not in st.session_state:
    st.session_state.vocab_filter = "pending"
if "vocab_selected_id" not in st.session_state:
    st.session_state.vocab_selected_id = None
if "vocab_flash" not in st.session_state:
    st.session_state.vocab_flash = None
if "vocab_workers" not in st.session_state:
    st.session_state.vocab_workers = DEFAULT_MAX_WORKERS

counts = get_review_counts()

st.markdown(
    f"""
    <div class="inbox-shell">
        <div class="inbox-hero">
            <div class="inbox-kicker">Vocabulary Inbox</div>
            <div class="inbox-title">Review captured phrases with clearer visual focus.</div>
            <p class="inbox-copy">
                Clean up each screenshot once, choose the right study shape, then promote it into your deck.
                <strong>{counts["pending"]}</strong> items are waiting for review right now.
            </p>
            <div class="inbox-stats">
                <div class="inbox-stat">
                    <div class="inbox-stat-label">Pending</div>
                    <div class="inbox-stat-value">{counts["pending"]}</div>
                </div>
                <div class="inbox-stat">
                    <div class="inbox-stat-label">Approved</div>
                    <div class="inbox-stat-value">{counts["approved"]}</div>
                </div>
                <div class="inbox-stat">
                    <div class="inbox-stat-label">Ignored</div>
                    <div class="inbox-stat-value">{counts["ignored"]}</div>
                </div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

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
        if st.button("Process screenshots", use_container_width=True):
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

st.markdown('<div class="inbox-shell">', unsafe_allow_html=True)

labels = [
    f'{item["file_name"]} · {item["review_status"]} · {item["study_phrase_fr"][:40] or "untitled"}'
    for item in items
]

st.markdown(
    """
    <div class="inbox-card inbox-card--soft inbox-card--tint">
        <div class="inbox-card-title">Queue</div>
        <p class="inbox-card-copy">Pick the next screenshot to review. The selector stays compact so the page can focus on the current card.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

selected_label = st.selectbox(
    "Screenshot",
    options=labels,
    index=current_index,
)
chosen_id = items[labels.index(selected_label)]["id"]
if chosen_id != st.session_state.vocab_selected_id:
    st.session_state.vocab_selected_id = chosen_id
    st.rerun()

capture_kind = selected_item.get("capture_kind") or "other"
study_target_options = ["Word or short phrase", "Whole sentence translation"]
default_study_target = (
    "Whole sentence translation" if capture_kind == "full_sentence" else "Word or short phrase"
)
study_target_state_key = f"study_target_type_{selected_item['id']}"
if study_target_state_key not in st.session_state:
    st.session_state[study_target_state_key] = default_study_target

left, right = st.columns([0.95, 1.05], gap="large")

with left:
    if current_path.exists():
        st.image(str(current_path), caption=selected_item["file_name"], width=360)
    else:
        st.warning(f"Screenshot file not found: {current_path}")

    with st.expander("Item details", expanded=False):
        st.markdown(
            f"""
            <div class="inbox-meta-card">
                <div class="meta-label">File</div>
                <div class="meta-value">{selected_item["file_name"]}</div>
                <div class="meta-label" style="margin-top:0.7rem;">Draft kind</div>
                <div class="meta-value">{selected_item.get("capture_kind") or "other"}</div>
                <div class="meta-label" style="margin-top:0.7rem;">Model confidence</div>
                <div class="meta-value">{f'{selected_item.get("confidence"):.2f}' if selected_item.get("confidence") is not None else "n/a"}</div>
                <div class="meta-label" style="margin-top:0.7rem;">Processed</div>
                <div class="meta-value">{selected_item.get("last_processed_ts") or "n/a"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander("Model draft", expanded=False):
        st.write(f"**Focused French:** {selected_item.get('focused_term_fr') or '—'}")
        st.write(f"**Sentence:** {selected_item.get('sentence_fr') or '—'}")
        st.write(f"**Translation:** {selected_item.get('translation_en') or '—'}")
        st.write(f"**Alternatives:** {', '.join(selected_item.get('alt_translations', [])) or '—'}")
        st.write(f"**Notes:** {selected_item.get('notes') or '—'}")
        st.json(selected_item.get("raw_json") or {})

with right:
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
        action_col, ignore_col = st.columns([1, 1])
        with action_col:
            approve = st.form_submit_button("Approve item", type="primary")
        with ignore_col:
            ignore = st.form_submit_button("Ignore screenshot")

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

    if ignore:
        ignore_vocab_item(selected_item["id"])
        st.session_state.vocab_selected_id = None
        st.rerun()

st.markdown("</div>", unsafe_allow_html=True)
