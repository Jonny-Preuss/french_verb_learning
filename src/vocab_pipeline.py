import argparse
import base64
import datetime
import fnmatch
import hashlib
import json
import os
import random
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

from src.vocab_repository import (
    SCREENSHOTS_DIR,
    get_connection,
    init_vocab_db,
    save_error,
    upsert_extraction,
)


ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

MODEL = "gpt-4o-mini"
CURRENT_PROMPT_VER = 2
ALLOW_HEIC = True
MAX_WIDTH = 1400
DEFAULT_MAX_WORKERS = 2

SYSTEM_PROMPT = "You are a precise French-English study assistant that analyzes Duolingo screenshots."
USER_PROMPT = """
You will see a Duolingo French-learning screenshot.

Infer what the learner most likely wanted to remember when taking the screenshot.
Sometimes it is:
- a purple-highlighted phrase,
- a hovered hint popup,
- a whole sentence,
- a mistake the learner made,
- a conversation turn,
- a word-definition card.

For sentence-completion screenshots, the underlined French answer span is the study target,
and the full French sentence should go into the context field.

Return ONLY JSON with this schema:
{
  "capture_kind": "highlighted_phrase | hint_popup | mistake_review | conversation | sentence_completion | full_sentence | definition_card | other",
  "focused_term_fr": "short French study target",
  "sentence_fr": "full French sentence if visible and useful, otherwise empty string",
  "translation_en": "best English counterpart for the study target",
  "study_context_en": "if sentence_fr is present, the English translation of that sentence; otherwise empty string",
  "alt_translations": ["optional alternatives"],
  "notes": "brief note about why this seems to be the learning focus",
  "confidence": 0.0
}

Rules:
- Prefer the phrase the learner would most likely want to study, not random surrounding UI text.
- If the screenshot shows a selected answer or hint popup, use that evidence.
- Keep `focused_term_fr` short unless the whole sentence is clearly the study target.
- If the screenshot is a sentence exercise with an underlined answer span, set `capture_kind` to `sentence_completion`.
- For `sentence_completion`, set `focused_term_fr` to the underlined French answer span, `sentence_fr` to the complete French sentence, `translation_en` to the English translation of the underlined span, and `study_context_en` to the English translation of the complete sentence.
- Do not add explanations in `study_context_en`; translate the full context sentence if one exists.
- If there is no smaller target and the screenshot is essentially the sentence itself, use `full_sentence` with the full sentence in `focused_term_fr`.
- Put a number between 0 and 1 in `confidence`.
- Use empty strings instead of null.
""".strip()

IMG_EXTS = {".png", ".jpg", ".jpeg"} | ({".heic"} if ALLOW_HEIC else set())


def has_openai_api_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def _get_client() -> OpenAI:
    if not has_openai_api_key():
        sys.exit(f"Error: OPENAI_API_KEY not found. Expected in {ENV_PATH}")
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def file_hash(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        hasher.update(handle.read())
    return hasher.hexdigest()[:24]


def normalize_to_jpg_b64(path: Path) -> str:
    if path.suffix.lower() == ".heic":
        import pillow_heif

        heif = pillow_heif.read_heif(str(path))
        image = Image.frombytes(heif.mode, heif.size, heif.data, "raw")
    else:
        image = Image.open(path)

    image = image.convert("RGB")
    if MAX_WIDTH and image.width > MAX_WIDTH:
        image = image.resize((MAX_WIDTH, int(image.height * (MAX_WIDTH / image.width))))

    tmp_path = path.with_suffix(".tmp.jpg")
    image.save(tmp_path, "JPEG", quality=90)
    image_b64 = base64.b64encode(tmp_path.read_bytes()).decode()
    tmp_path.unlink(missing_ok=True)
    return image_b64


def call_vision_llm(image_b64: str) -> dict:
    client = _get_client()
    max_retries = 5
    backoff = 1.0

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": USER_PROMPT},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                        ],
                    },
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except Exception as exc:
            if "rate limit" in str(exc).lower() or "429" in str(exc):
                wait_seconds = backoff * (2**attempt) + random.uniform(0, 0.25)
                print(f"Rate limit hit, sleeping {wait_seconds:.1f}s before retry...")
                time.sleep(wait_seconds)
                continue
            raise

    raise RuntimeError("Failed after max retries due to rate limits.")


def should_process(item_id: str) -> bool:
    con = get_connection()
    row = con.execute(
        "SELECT model_id, prompt_ver, review_status FROM vocab_items WHERE id=?",
        (item_id,),
    ).fetchone()
    con.close()

    if row is None:
        return True
    if row["review_status"] in {"approved", "ignored"}:
        return False
    if row["review_status"] == "pending":
        return True
    if row["model_id"] != MODEL:
        return True
    if int(row["prompt_ver"] or 0) != int(CURRENT_PROMPT_VER):
        return True
    return False


def process_image(path: Path, force: bool = False) -> bool:
    try:
        if not path.exists() or path.suffix.lower() not in IMG_EXTS:
            return False

        item_id = file_hash(path)
        if not force and not should_process(item_id):
            return False

        image_b64 = normalize_to_jpg_b64(path)
        data = call_vision_llm(image_b64)
        stat = path.stat()
        record = {
            "id": item_id,
            "image_path": str(path),
            "file_name": path.name,
            "file_dir": str(path.parent),
            "file_size": stat.st_size,
            "file_mtime": stat.st_mtime,
            "model_id": MODEL,
            "prompt_ver": CURRENT_PROMPT_VER,
            "status": "ok",
            "capture_kind": data.get("capture_kind", "other"),
            "confidence": data.get("confidence"),
            "focused_term_fr": data.get("focused_term_fr", ""),
            "sentence_fr": data.get("sentence_fr", ""),
            "translation_en": data.get("translation_en", ""),
            "study_context_en": data.get("study_context_en", ""),
            "alt_translations": data.get("alt_translations", []),
            "notes": data.get("notes", ""),
            "raw": data,
        }
        upsert_extraction(record)
        print(f"Processed {path.name}: {record['focused_term_fr']} -> {record['translation_en']}")
        return True
    except Exception as exc:
        save_error(file_hash(path), str(path), f"{exc}\n{traceback.format_exc()}")
        print(f"Failed {path.name}: {exc}")
        return False


def list_processable_images(force: bool = False) -> list[Path]:
    init_vocab_db()
    paths: list[Path] = []
    for path in sorted(SCREENSHOTS_DIR.glob("*")):
        if path.suffix.lower() not in IMG_EXTS:
            continue
        if force:
            paths.append(path)
            continue
        item_id = file_hash(path)
        if should_process(item_id):
            paths.append(path)
    return paths


def batch_process_images(
    force: bool = False,
    max_workers: int = DEFAULT_MAX_WORKERS,
    progress_callback: Callable[[dict[str, int]], None] | None = None,
) -> dict[str, int]:
    paths = list_processable_images(force=force)
    if not paths:
        stats = {"eligible": 0, "processed": 0, "failed": 0, "completed": 0}
        if progress_callback:
            progress_callback(stats)
        return stats

    worker_count = max(1, min(max_workers, len(paths)))
    processed = 0
    failed = 0
    completed = 0
    failed_paths: list[Path] = []

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(process_image, path, force): path for path in paths}
        for future in as_completed(futures):
            if future.result():
                processed += 1
            else:
                failed += 1
                failed_paths.append(futures[future])
            completed += 1
            if progress_callback:
                progress_callback(
                    {
                        "eligible": len(paths),
                        "processed": processed,
                        "failed": failed,
                        "completed": completed,
                    }
                )

    if failed_paths:
        for path in failed_paths[:]:
            time.sleep(1.0)
            if process_image(path, force=force):
                processed += 1
                failed -= 1
            if progress_callback:
                progress_callback(
                    {
                        "eligible": len(paths),
                        "processed": processed,
                        "failed": failed,
                        "completed": completed,
                    }
                )

    return {"eligible": len(paths), "processed": processed, "failed": failed, "completed": completed}


def watch_loop() -> None:
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "watchdog is required only for folder watching. Install it or use the scan/process flow instead."
        ) from exc

    class Handler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory:
                return
            path = Path(event.src_path)
            if path.suffix.lower() in IMG_EXTS:
                time.sleep(1.5)
                process_image(path)

    init_vocab_db()
    print(f"Watching: {SCREENSHOTS_DIR}")
    batch_process_images()
    observer = Observer()
    observer.schedule(Handler(), str(SCREENSHOTS_DIR), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def mark_for_review_by_name(pattern: str) -> None:
    con = get_connection()
    rows = con.execute("SELECT id, file_name FROM vocab_items").fetchall()
    ids = [row["id"] for row in rows if fnmatch.fnmatch(row["file_name"], pattern)]
    if ids:
        con.executemany("UPDATE vocab_items SET review_status='pending' WHERE id=?", [(item_id,) for item_id in ids])
        con.commit()
    con.close()
    print(f"Marked {len(ids)} item(s) for review by name='{pattern}'.")


def mark_for_review_by_id(item_id: str) -> None:
    con = get_connection()
    con.execute("UPDATE vocab_items SET review_status='pending' WHERE id=?", (item_id,))
    con.commit()
    con.close()
    print(f"Marked id={item_id} for review.")


def mark_outdated_for_review() -> None:
    con = get_connection()
    con.execute(
        "UPDATE vocab_items SET review_status='pending' WHERE model_id<>? OR prompt_ver<>?",
        (MODEL, CURRENT_PROMPT_VER),
    )
    changed = con.total_changes
    con.commit()
    con.close()
    print(f"Marked {changed} outdated item(s) for review.")


def mark_since_for_review(since_iso: str) -> None:
    since_dt = datetime.datetime.fromisoformat(since_iso)
    con = get_connection()
    rows = con.execute("SELECT id, last_processed_ts FROM vocab_items").fetchall()
    ids = []
    for row in rows:
        timestamp = row["last_processed_ts"]
        if timestamp and datetime.datetime.fromisoformat(timestamp) >= since_dt:
            ids.append(row["id"])
    if ids:
        con.executemany("UPDATE vocab_items SET review_status='pending' WHERE id=?", [(item_id,) for item_id in ids])
        con.commit()
    con.close()
    print(f"Marked {len(ids)} item(s) processed since {since_iso} for review.")


def reprocess_queue() -> None:
    con = get_connection()
    rows = con.execute("SELECT image_path FROM vocab_items WHERE review_status='pending'").fetchall()
    con.close()
    if not rows:
        print("No items marked for review.")
        return
    for row in rows:
        process_image(Path(row["image_path"]), force=True)


def main() -> None:
    init_vocab_db()

    parser = argparse.ArgumentParser(
        description="Watch Duolingo screenshots, extract vocabulary drafts, and store them in SQLite."
    )
    subparsers = parser.add_subparsers(dest="cmd")

    subparsers.add_parser("watch", help="Watch the folder and process new images.")
    subparsers.add_parser("scan", help="Process the screenshot folder once.")

    reprocess_parser = subparsers.add_parser("reprocess", help="Mark items for review and optionally re-run extraction.")
    reprocess_parser.add_argument("--name", help='Glob pattern on file_name, e.g. "IMG_63*.jpeg"', default=None)
    reprocess_parser.add_argument("--id", help="Exact content-hash id to reprocess", default=None)
    reprocess_parser.add_argument("--outdated", action="store_true", help="Mark items with old model/prompt versions")
    reprocess_parser.add_argument("--since", help="Mark items processed on or after YYYY-MM-DD", default=None)
    reprocess_parser.add_argument("--run", action="store_true", help="Immediately reprocess pending items")

    args = parser.parse_args()

    if args.cmd in (None, "watch"):
        watch_loop()
        return

    if args.cmd == "scan":
        stats = batch_process_images()
        print(
            f"Processed {stats['processed']} screenshot(s), "
            f"failed {stats['failed']}, eligible {stats['eligible']}."
        )
        return

    if args.cmd == "reprocess":
        if args.name:
            mark_for_review_by_name(args.name)
        if args.id:
            mark_for_review_by_id(args.id)
        if args.outdated:
            mark_outdated_for_review()
        if args.since:
            mark_since_for_review(args.since)
        if args.run:
            reprocess_queue()
        else:
            print("Use --run to process immediately. Otherwise items stay in the pending review queue.")


if __name__ == "__main__":
    main()
