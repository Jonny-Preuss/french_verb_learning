from __future__ import annotations

import json
import random
import sqlite3
import shutil
import unicodedata
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
SCREENSHOTS_DIR = DATA_DIR / "DuolingoScreenshots"
PROCESSED_SCREENSHOTS_DIR = SCREENSHOTS_DIR / "processed"
VOCAB_DB_PATH = DATA_DIR / "vocab.sqlite"


BASE_COLUMNS = {
    "id": "TEXT PRIMARY KEY",
    "image_path": "TEXT",
    "file_name": "TEXT",
    "file_dir": "TEXT",
    "file_size": "INTEGER",
    "file_mtime": "REAL",
    "created_ts": "DATETIME DEFAULT CURRENT_TIMESTAMP",
    "last_processed_ts": "DATETIME",
    "model_id": "TEXT",
    "prompt_ver": "INTEGER DEFAULT 1",
    "status": "TEXT DEFAULT 'ok'",
    "focused_term_fr": "TEXT",
    "sentence_fr": "TEXT",
    "translation_en": "TEXT",
    "study_context_en": "TEXT",
    "alt_translations": "TEXT",
    "notes": "TEXT",
    "raw_json": "TEXT",
}

REVIEW_COLUMNS = {
    "capture_kind": "TEXT DEFAULT 'unknown'",
    "confidence": "REAL",
    "review_status": "TEXT DEFAULT 'pending'",
    "study_phrase_fr": "TEXT",
    "study_phrase_en": "TEXT",
    "study_context_fr": "TEXT",
    "study_context_en": "TEXT",
    "user_note": "TEXT",
    "reviewed_ts": "DATETIME",
    "ignored_ts": "DATETIME",
    "practice_attempts": "INTEGER DEFAULT 0",
    "practice_correct": "INTEGER DEFAULT 0",
    "practice_incorrect": "INTEGER DEFAULT 0",
    "last_practiced_ts": "DATETIME",
}


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    ensure_data_dirs()
    con = sqlite3.connect(VOCAB_DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def archive_screenshot(item_id: str) -> str | None:
    con = get_connection()
    row = con.execute(
        "SELECT image_path, file_name FROM vocab_items WHERE id=?",
        (item_id,),
    ).fetchone()
    if row is None:
        con.close()
        return None

    source = Path(row["image_path"] or "")
    if not source.exists():
        con.close()
        return row["image_path"]
    if source.parent == PROCESSED_SCREENSHOTS_DIR:
        con.close()
        return str(source)

    PROCESSED_SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    destination = _unique_destination(PROCESSED_SCREENSHOTS_DIR, source.name)
    shutil.move(str(source), str(destination))

    con.execute(
        """
        UPDATE vocab_items
        SET image_path=?, file_dir=?, file_name=?
        WHERE id=?
        """,
        (str(destination), str(destination.parent), destination.name, item_id),
    )
    con.commit()
    con.close()
    return str(destination)


def approve_vocab_item(
    item_id: str,
    *,
    capture_kind: str,
    study_phrase_fr: str,
    study_phrase_en: str,
    study_context_fr: str,
    study_context_en: str,
    alt_translations: list[str],
    user_note: str,
) -> str | None:
    review_vocab_item(
        item_id,
        capture_kind=capture_kind,
        study_phrase_fr=study_phrase_fr,
        study_phrase_en=study_phrase_en,
        study_context_fr=study_context_fr,
        study_context_en=study_context_en,
        alt_translations=alt_translations,
        user_note=user_note,
    )
    return archive_screenshot(item_id)


def _column_names(con: sqlite3.Connection, table: str) -> set[str]:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def init_vocab_db() -> None:
    con = get_connection()
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS vocab_items (
          id TEXT PRIMARY KEY,
          image_path TEXT,
          file_name TEXT,
          file_dir  TEXT,
          file_size INTEGER,
          file_mtime REAL,
          created_ts DATETIME DEFAULT CURRENT_TIMESTAMP,
          last_processed_ts DATETIME,
          model_id TEXT,
          prompt_ver INTEGER DEFAULT 1,
          status TEXT DEFAULT 'ok',
          focused_term_fr TEXT,
          sentence_fr TEXT,
          translation_en TEXT,
          study_context_en TEXT,
          alt_translations TEXT,
          notes TEXT,
          raw_json TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS errors (
          id TEXT PRIMARY KEY,
          image_path TEXT,
          created_ts DATETIME DEFAULT CURRENT_TIMESTAMP,
          error TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS vocab_practice_attempts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          vocab_item_id TEXT NOT NULL,
          created_ts DATETIME DEFAULT CURRENT_TIMESTAMP,
          prompt_en TEXT,
          expected_answer_fr TEXT,
          user_answer_fr TEXT,
          is_correct INTEGER NOT NULL,
          FOREIGN KEY(vocab_item_id) REFERENCES vocab_items(id)
        )
        """
    )

    existing_columns = _column_names(con, "vocab_items")
    for column_name, column_sql in REVIEW_COLUMNS.items():
        if column_name not in existing_columns:
            con.execute(f"ALTER TABLE vocab_items ADD COLUMN {column_name} {column_sql}")

    con.commit()
    con.close()


def upsert_extraction(rec: dict[str, Any]) -> None:
    con = get_connection()
    con.execute(
        """
        INSERT INTO vocab_items
        (
          id, image_path, file_name, file_dir, file_size, file_mtime,
          model_id, prompt_ver, status, focused_term_fr, sentence_fr,
          translation_en, study_context_en, alt_translations, notes, raw_json, capture_kind,
          confidence, review_status, last_processed_ts
        )
        VALUES (
          ?, ?, ?, ?, ?, ?,
          ?, ?, ?, ?, ?,
          ?, ?, ?, ?, ?, ?,
          ?, ?, CURRENT_TIMESTAMP
        )
        ON CONFLICT(id) DO UPDATE SET
          image_path=excluded.image_path,
          file_name=excluded.file_name,
          file_dir=excluded.file_dir,
          file_size=excluded.file_size,
          file_mtime=excluded.file_mtime,
          model_id=excluded.model_id,
          prompt_ver=excluded.prompt_ver,
          status=excluded.status,
          focused_term_fr=excluded.focused_term_fr,
          sentence_fr=excluded.sentence_fr,
          translation_en=excluded.translation_en,
          study_context_en=excluded.study_context_en,
          alt_translations=excluded.alt_translations,
          notes=excluded.notes,
          raw_json=excluded.raw_json,
          capture_kind=excluded.capture_kind,
          confidence=excluded.confidence,
          review_status='pending',
          ignored_ts=NULL,
          last_processed_ts=CURRENT_TIMESTAMP
        """,
        (
            rec["id"],
            rec["image_path"],
            rec["file_name"],
            rec["file_dir"],
            rec["file_size"],
            rec["file_mtime"],
            rec["model_id"],
            rec["prompt_ver"],
            rec.get("status", "ok"),
            rec.get("focused_term_fr", ""),
            rec.get("sentence_fr", ""),
            rec.get("translation_en", ""),
            rec.get("study_context_en", ""),
            json.dumps(rec.get("alt_translations", []), ensure_ascii=True),
            rec.get("notes", ""),
            json.dumps(rec.get("raw", {}), ensure_ascii=True),
            rec.get("capture_kind", "unknown"),
            rec.get("confidence"),
            rec.get("review_status", "pending"),
        ),
    )
    con.commit()
    con.close()


def save_error(item_id: str, image_path: str, err: str) -> None:
    con = get_connection()
    con.execute(
        "INSERT OR REPLACE INTO errors (id,image_path,error) VALUES (?,?,?)",
        (item_id, image_path, err[:5000]),
    )
    con.commit()
    con.close()


def list_vocab_items(review_status: str | None = None) -> list[dict[str, Any]]:
    con = get_connection()
    query = "SELECT * FROM vocab_items"
    params: tuple[Any, ...] = ()
    if review_status:
        query += " WHERE review_status=?"
        params = (review_status,)
    query += " ORDER BY COALESCE(reviewed_ts, last_processed_ts, created_ts) DESC, file_name DESC"
    rows = con.execute(query, params).fetchall()
    con.close()
    return [_row_to_dict(row) for row in rows]


def get_vocab_item(item_id: str) -> dict[str, Any] | None:
    con = get_connection()
    row = con.execute("SELECT * FROM vocab_items WHERE id=?", (item_id,)).fetchone()
    con.close()
    if row is None:
        return None
    return _row_to_dict(row)


def review_vocab_item(
    item_id: str,
    *,
    capture_kind: str,
    study_phrase_fr: str,
    study_phrase_en: str,
    study_context_fr: str,
    study_context_en: str,
    alt_translations: list[str],
    user_note: str,
) -> None:
    con = get_connection()
    con.execute(
        """
        UPDATE vocab_items
        SET
          capture_kind=?,
          study_phrase_fr=?,
          study_phrase_en=?,
          study_context_fr=?,
          study_context_en=?,
          alt_translations=?,
          user_note=?,
          review_status='approved',
          reviewed_ts=CURRENT_TIMESTAMP,
          ignored_ts=NULL
        WHERE id=?
        """,
        (
            capture_kind,
            _coerce_text(study_phrase_fr),
            _coerce_text(study_phrase_en),
            _coerce_text(study_context_fr),
            _coerce_text(study_context_en),
            json.dumps(alt_translations, ensure_ascii=True),
            _coerce_text(user_note),
            item_id,
        ),
    )
    con.commit()
    con.close()


def ignore_vocab_item(item_id: str) -> None:
    con = get_connection()
    con.execute(
        """
        UPDATE vocab_items
        SET review_status='ignored', ignored_ts=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (item_id,),
    )
    con.commit()
    con.close()


def get_review_counts() -> dict[str, int]:
    con = get_connection()
    rows = con.execute(
        "SELECT review_status, COUNT(*) AS total FROM vocab_items GROUP BY review_status"
    ).fetchall()
    con.close()
    counts = {"pending": 0, "approved": 0, "ignored": 0}
    for row in rows:
        counts[row["review_status"] or "pending"] = row["total"]
    return counts


def get_approved_vocab_count() -> int:
    con = get_connection()
    row = con.execute(
        "SELECT COUNT(*) AS total FROM vocab_items WHERE review_status='approved'"
    ).fetchone()
    con.close()
    return int(row["total"] or 0)


def list_practice_vocab_items() -> list[dict[str, Any]]:
    con = get_connection()
    rows = con.execute(
        """
        SELECT *
        FROM vocab_items
        WHERE review_status='approved'
          AND TRIM(COALESCE(study_phrase_fr, '')) <> ''
          AND TRIM(COALESCE(study_phrase_en, '')) <> ''
        ORDER BY COALESCE(last_practiced_ts, reviewed_ts, created_ts) DESC, file_name DESC
        """
    ).fetchall()
    con.close()
    return [_row_to_dict(row) for row in rows]


def choose_practice_vocab_item() -> dict[str, Any] | None:
    items = list_practice_vocab_items()
    if not items:
        return None

    weights = [1 + max(0, int(item.get("practice_incorrect") or 0)) for item in items]
    return random.choices(items, weights=weights, k=1)[0]


def get_vocab_practice_stats(item_id: str) -> dict[str, int]:
    con = get_connection()
    row = con.execute(
        """
        SELECT practice_attempts, practice_correct, practice_incorrect
        FROM vocab_items
        WHERE id=?
        """,
        (item_id,),
    ).fetchone()
    con.close()
    if row is None:
        return {"practice_attempts": 0, "practice_correct": 0, "practice_incorrect": 0}
    return {
        "practice_attempts": int(row["practice_attempts"] or 0),
        "practice_correct": int(row["practice_correct"] or 0),
        "practice_incorrect": int(row["practice_incorrect"] or 0),
    }


def record_vocab_practice_attempt(
    item_id: str,
    *,
    prompt_en: str,
    expected_answer_fr: str,
    user_answer_fr: str,
    is_correct: bool,
) -> None:
    con = get_connection()
    con.execute("BEGIN")
    con.execute(
        """
        INSERT INTO vocab_practice_attempts
        (
          vocab_item_id, prompt_en, expected_answer_fr, user_answer_fr, is_correct
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            item_id,
            _coerce_text(prompt_en),
            _coerce_text(expected_answer_fr),
            _coerce_text(user_answer_fr),
            1 if is_correct else 0,
        ),
    )
    con.execute(
        """
        UPDATE vocab_items
        SET
          practice_attempts=COALESCE(practice_attempts, 0) + 1,
          practice_correct=COALESCE(practice_correct, 0) + ?,
          practice_incorrect=COALESCE(practice_incorrect, 0) + ?,
          last_practiced_ts=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (1 if is_correct else 0, 0 if is_correct else 1, item_id),
    )
    con.commit()
    con.close()


def is_vocab_answer_correct(user_answer: str, expected_answer: str) -> bool:
    return _normalize_answer_for_compare(user_answer) == _normalize_answer_for_compare(expected_answer)


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_answer_for_compare(value: str) -> str:
    lowered = _coerce_text(value).lower()
    decomposed = unicodedata.normalize("NFD", lowered)
    without_accents = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return " ".join(without_accents.split())


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["alt_translations"] = _json_loads(data.get("alt_translations"), [])
    data["raw_json"] = _json_loads(data.get("raw_json"), {})
    focused_term = data.get("focused_term_fr") or ""
    translation = data.get("translation_en") or ""
    sentence_fr = data.get("sentence_fr") or ""
    sentence_translation = data.get("study_context_en") or data["raw_json"].get("study_context_en") or ""

    default_phrase_fr = data.get("study_phrase_fr") or focused_term
    default_phrase_en = data.get("study_phrase_en") or translation
    if data.get("capture_kind") in {"sentence_completion", "full_sentence"} and focused_term:
        default_phrase_fr = focused_term
        default_phrase_en = translation
    elif not data.get("study_phrase_fr") and not data.get("study_phrase_en"):
        default_phrase_fr, default_phrase_en = _normalize_vocab_card_sides(focused_term, translation)

    context_fr = data.get("study_context_fr") or sentence_fr or ""
    context_en = sentence_translation or data.get("study_context_en") or ""
    if not context_en and context_fr:
        context_en = translation

    data["study_phrase_fr"] = default_phrase_fr
    data["study_phrase_en"] = default_phrase_en
    data["study_context_fr"] = context_fr
    data["study_context_en"] = context_en
    data["review_status"] = data.get("review_status") or "pending"
    data["capture_kind"] = data.get("capture_kind") or "unknown"
    data["practice_attempts"] = int(data.get("practice_attempts") or 0)
    data["practice_correct"] = int(data.get("practice_correct") or 0)
    data["practice_incorrect"] = int(data.get("practice_incorrect") or 0)
    return data


def _normalize_vocab_card_sides(french_text: str, english_text: str) -> tuple[str, str]:
    french = french_text.strip()
    english = english_text.strip()
    lowered = french.lower()
    if not (lowered.startswith("un ") or lowered.startswith("une ")):
        return french, english

    noun = french.split(" ", 1)[1].strip()
    if not noun or any(char in noun for char in ".!?"):
        return french, english

    english = _strip_leading_english_article(english)
    if _starts_with_vowel_or_silent_h(noun):
        source_article = french.split(" ", 1)[0].lower()
        return f"l'{noun} ({source_article})", english

    article = "le" if lowered.startswith("un ") else "la"
    return f"{article} {noun}", english


def _strip_leading_english_article(text: str) -> str:
    lowered = text.lower()
    for article in ("a ", "an ", "the "):
        if lowered.startswith(article):
            return text[len(article):].strip()
    return text


def _starts_with_vowel_or_silent_h(text: str) -> bool:
    if not text:
        return False
    return text[0].lower() in {"a", "e", "i", "o", "u", "h"}


def _unique_destination(folder: Path, file_name: str) -> Path:
    destination = folder / file_name
    if not destination.exists():
        return destination

    stem = Path(file_name).stem
    suffix = Path(file_name).suffix
    counter = 2
    while True:
        candidate = folder / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
