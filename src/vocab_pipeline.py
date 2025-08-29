# vocab_pipeline.py
import os, sys, json, time, base64, hashlib, sqlite3, traceback, argparse, fnmatch, datetime, random
from pathlib import Path
from PIL import Image
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv
from openai import OpenAI

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Safety check
if not os.getenv("OPENAI_API_KEY"):
    sys.exit(f"Error: OPENAI_API_KEY not found. Expected in {ENV_PATH}")

# OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ========== CONFIG ==========
REPO_PATH = "Documents/03_Code/03_Pers/03_French_Verbs/french_verb_learning"
INPUT_DIR = Path.home() / REPO_PATH / "data" / "DuolingoScreenshots"
DB_DIR    = Path.home() / REPO_PATH / "data"
DB_PATH   = DB_DIR / "vocab.sqlite"

MODEL               = "gpt-4o-mini"          # vision-capable model ID
CURRENT_PROMPT_VER  = 1                      # bump when you change instructions
ALLOW_HEIC          = True                   # needs pillow-heif if True
MAX_WIDTH           = 1400                   # downscale to control size/cost
client              = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# ===========================


SYSTEM_PROMPT = "You are a precise French–English study assistant."
USER_PROMPT = """You will see a Duolingo-style screenshot.
Find the French phrase the user likely focused on (often near an English hint bubble).
Return ONLY JSON:
{
 "focused_term_fr": "...",
 "sentence_fr": "...",
 "translation_en": "...",
 "alt_translations": ["..."],
 "notes": "why this is the focus and any grammar tips"
}
Rules: prefer the phrase tied to an English hint bubble if present. Use 'how many' vs 'how much' correctly. Keep notes short.
"""

IMG_EXTS = {".png", ".jpg", ".jpeg"} | ({".heic"} if ALLOW_HEIC else set())

def ensure_dirs():
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    DB_DIR.mkdir(parents=True, exist_ok=True)

def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute("""
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
      alt_translations TEXT,
      notes TEXT,
      raw_json TEXT
    )""")
    con.execute("""
    CREATE TABLE IF NOT EXISTS errors (
      id TEXT PRIMARY KEY,
      image_path TEXT,
      created_ts DATETIME DEFAULT CURRENT_TIMESTAMP,
      error TEXT
    )""")
    con.commit(); con.close()

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f: h.update(f.read())
    return h.hexdigest()[:24]

def normalize_to_jpg_b64(path: Path) -> str:
    if path.suffix.lower() == ".heic":
        import pillow_heif  # pip install pillow-heif
        heif = pillow_heif.read_heif(str(path))
        im = Image.frombytes(heif.mode, heif.size, heif.data, "raw")
    else:
        im = Image.open(path)
    im = im.convert("RGB")
    if MAX_WIDTH and im.width > MAX_WIDTH:
        im = im.resize((MAX_WIDTH, int(im.height * (MAX_WIDTH / im.width))))
    tmp = path.with_suffix(".tmp.jpg")
    im.save(tmp, "JPEG", quality=90)
    b64 = base64.b64encode(tmp.read_bytes()).decode()
    tmp.unlink(missing_ok=True)
    return b64

def call_vision_llm(image_b64: str) -> dict:
    max_retries = 5
    backoff = 1.0  # start with 1 second

    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": [
                        {"type": "text", "text": USER_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                    ]}
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content)

        except Exception as e:
            if "rate limit" in str(e).lower() or "429" in str(e):
                wait = backoff * (2 ** attempt) + random.uniform(0, 0.25)
                print(f"⚠️ Rate limit hit, sleeping {wait:.1f}s before retry...")
                time.sleep(wait)
            else:
                raise

    raise RuntimeError("Failed after max retries due to rate limits.")

def should_process(con, item_id: str) -> bool:
    row = con.execute(
        "SELECT model_id,prompt_ver,status FROM vocab_items WHERE id=?",
        (item_id,)
    ).fetchone()
    if not row:
        return True
    model_id, prompt_ver, status = row
    if status == "needs_review": return True
    if model_id != MODEL: return True
    if int(prompt_ver or 0) != int(CURRENT_PROMPT_VER): return True
    return False

def upsert_item(rec: dict):
    con = sqlite3.connect(DB_PATH)
    con.execute("""
      INSERT INTO vocab_items
      (id,image_path,file_name,file_dir,file_size,file_mtime,model_id,prompt_ver,status,
       focused_term_fr,sentence_fr,translation_en,alt_translations,notes,raw_json,last_processed_ts)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
      ON CONFLICT(id) DO UPDATE SET
        image_path=excluded.image_path,
        file_name=excluded.file_name,
        file_dir=excluded.file_dir,
        file_size=excluded.file_size,
        file_mtime=excluded.file_mtime,
        model_id=excluded.model_id,
        prompt_ver=excluded.prompt_ver,
        status='ok',
        focused_term_fr=excluded.focused_term_fr,
        sentence_fr=excluded.sentence_fr,
        translation_en=excluded.translation_en,
        alt_translations=excluded.alt_translations,
        notes=excluded.notes,
        raw_json=excluded.raw_json,
        last_processed_ts=CURRENT_TIMESTAMP
    """, (
        rec["id"], rec["image_path"], rec["file_name"], rec["file_dir"],
        rec["file_size"], rec["file_mtime"], rec["model_id"], rec["prompt_ver"],
        rec.get("status","ok"), rec["focused_term_fr"], rec["sentence_fr"],
        rec["translation_en"], json.dumps(rec.get("alt_translations", [])),
        rec.get("notes",""), json.dumps(rec["raw"])
    ))
    con.commit(); con.close()

def save_error(item_id: str, path: Path, err: str):
    con = sqlite3.connect(DB_PATH)
    con.execute("INSERT OR REPLACE INTO errors (id,image_path,error) VALUES (?,?,?)",
                (item_id, str(path), err[:5000]))
    con.commit(); con.close()

def process_image(path: Path, force: bool = False):
    try:
        if not path.exists():
            print(f"! Missing file: {path}")
            return
        if path.suffix.lower() not in IMG_EXTS:
            return

        item_id = file_hash(path)
        stat = path.stat()
        con = sqlite3.connect(DB_PATH)
        if not force and not should_process(con, item_id):
            con.close()
            return
        con.close()

        b64 = normalize_to_jpg_b64(path)
        data = call_vision_llm(b64)

        rec = {
            "id": item_id,
            "image_path": str(path),
            "file_name": path.name,
            "file_dir": str(path.parent),
            "file_size": stat.st_size,
            "file_mtime": stat.st_mtime,
            "model_id": MODEL,
            "prompt_ver": CURRENT_PROMPT_VER,
            "focused_term_fr": data.get("focused_term_fr",""),
            "sentence_fr": data.get("sentence_fr",""),
            "translation_en": data.get("translation_en",""),
            "alt_translations": data.get("alt_translations",[]),
            "notes": data.get("notes",""),
            "raw": data
        }
        upsert_item(rec)
        print(f"✓ {path.name}: {rec['focused_term_fr']} → {rec['translation_en']}")
    except Exception as e:
        save_error(file_hash(path), path, f"{e}\n{traceback.format_exc()}")
        print(f"✗ {path.name}: {e}")

class Handler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory: return
        p = Path(event.src_path)
        if p.suffix.lower() in IMG_EXTS:
            time.sleep(1.5)  # allow write to finish
            process_image(p)

def initial_scan():
    for p in sorted(INPUT_DIR.glob("*")):
        if p.suffix.lower() in IMG_EXTS:
            process_image(p)

def watch_loop():
    print(f"Watching: {INPUT_DIR}")
    initial_scan()
    obs = Observer()
    obs.schedule(Handler(), str(INPUT_DIR), recursive=False)
    obs.start()
    try:
        while True: time.sleep(2)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()

# ---------- Reprocess controls ----------
def mark_for_review_by_name(pattern: str):
    con = sqlite3.connect(DB_PATH)
    cur = con.execute("SELECT id,file_name FROM vocab_items")
    ids = []
    for _id, name in cur.fetchall():
        if fnmatch.fnmatch(name, pattern):
            ids.append(_id)
    if ids:
        con.executemany("UPDATE vocab_items SET status='needs_review' WHERE id=?", [(i,) for i in ids])
        con.commit()
    con.close()
    print(f"Marked {len(ids)} item(s) for review by name='{pattern}'.")

def mark_for_review_by_id(item_id: str):
    con = sqlite3.connect(DB_PATH)
    con.execute("UPDATE vocab_items SET status='needs_review' WHERE id=?", (item_id,))
    con.commit(); con.close()
    print(f"Marked id={item_id} for review.")

def mark_outdated_for_review():
    con = sqlite3.connect(DB_PATH)
    con.execute("UPDATE vocab_items SET status='needs_review' WHERE model_id<>? OR prompt_ver<>?",
                (MODEL, CURRENT_PROMPT_VER))
    n = con.total_changes
    con.commit(); con.close()
    print(f"Marked {n} outdated item(s) for review (model/prompt mismatch).")

def mark_since_for_review(since_iso: str):
    # since format: YYYY-MM-DD
    dt = datetime.datetime.fromisoformat(since_iso)
    con = sqlite3.connect(DB_PATH)
    cur = con.execute("SELECT id,last_processed_ts FROM vocab_items")
    ids = []
    for _id, ts in cur.fetchall():
        if ts and datetime.datetime.fromisoformat(ts) >= dt:
            ids.append(_id)
    if ids:
        con.executemany("UPDATE vocab_items SET status='needs_review' WHERE id=?", [(i,) for i in ids])
        con.commit()
    con.close()
    print(f"Marked {len(ids)} item(s) processed since {since_iso} for review.")

def reprocess_queue():
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT id,image_path FROM vocab_items WHERE status='needs_review'").fetchall()
    con.close()
    if not rows:
        print("No items marked for review.")
        return
    for _id, p in rows:
        process_image(Path(p), force=True)
        # set status back to ok happens in upsert_item()

# -------------- CLI ----------------
def main():
    ensure_dirs()
    init_db()

    ap = argparse.ArgumentParser(description="Vocab pipeline: watch folder, extract terms via vision LLM, store in SQLite.")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("watch", help="Watch the folder and process new images (default).")

    rp = sub.add_parser("reprocess", help="Mark items for review and reprocess.")
    rp.add_argument("--name", help='Glob pattern on file_name, e.g. "*combien*"', default=None)
    rp.add_argument("--id", help="Exact content-hash id to reprocess", default=None)
    rp.add_argument("--outdated", action="store_true", help="Mark all items with old model/prompt for review")
    rp.add_argument("--since", help='Mark items processed on/after date (YYYY-MM-DD) for review', default=None)
    rp.add_argument("--run", action="store_true", help="After marking, immediately reprocess the queue")

    args = ap.parse_args()

    if args.cmd in (None, "watch"):
        watch_loop()
        return

    if args.cmd == "reprocess":
        if args.name:    mark_for_review_by_name(args.name)
        if args.id:      mark_for_review_by_id(args.id)
        if args.outdated: mark_outdated_for_review()
        if args.since:   mark_since_for_review(args.since)
        if args.run:     reprocess_queue()
        else:            print("Use --run to process immediately (otherwise items are marked and will be picked up later).")

if __name__ == "__main__":
    main()