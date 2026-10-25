"""Interests engine: what the user likes, from their OWN Instagram data download (Accounts Center > Your
information and permissions > Download your information, JSON) or from notes they type in.

The Instagram API cannot read saved or liked posts, so this is the only legitimate route. Nothing here fetches a
URL: links are stored as text. Topics are inferred by keyword matching on collection names, notes and creator
handles, and every inferred number is labelled as such."""

from __future__ import annotations

import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CATEGORIES, InterestItem, utcnow

MAX_ZIP_BYTES = 300 * 1024 * 1024
MAX_JSON_BYTES = 60 * 1024 * 1024
MAX_ITEMS_PER_FILE = 50_000

CATEGORY_LABEL = {
    "ai": "AI & tools",
    "tech_concepts": "How tech works",
    "career": "Jobs & career",
    "skills": "Skills & productivity",
    "relatable_learning": "Student life & relatable",
}

# Keyword map from free text (collection names, notes, handles, captions) to the app's categories.
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ai": (
        "ai",
        "chatgpt",
        "gpt",
        "llm",
        "prompt",
        "prompts",
        "claude",
        "gemini",
        "openai",
        "copilot",
        "agent",
        "agents",
        "genai",
        "midjourney",
        "automation",
        "automate",
        "ml",
        "machinelearning",
        "machine learning",
        "neural",
        "aitools",
        "artificial",
    ),
    "tech_concepts": (
        "tech",
        "api",
        "apis",
        "cloud",
        "code",
        "coding",
        "coder",
        "programming",
        "programmer",
        "developer",
        "dev",
        "software",
        "internet",
        "explained",
        "cyber",
        "security",
        "hacking",
        "web",
        "data",
        "database",
        "gadget",
        "gadgets",
        "linux",
        "python",
        "javascript",
        "java",
        "server",
        "network",
        "upi",
        "app",
        "apps",
        "techie",
        "engineering",
        "computer",
        "science",
    ),
    "career": (
        "career",
        "job",
        "jobs",
        "interview",
        "interviews",
        "resume",
        "cv",
        "salary",
        "hiring",
        "linkedin",
        "placement",
        "placements",
        "corporate",
        "office",
        "startup",
        "startups",
        "business",
        "hr",
        "fresher",
        "freshers",
        "work",
        "boss",
        "manager",
        "internship",
    ),
    "skills": (
        "skill",
        "skills",
        "productivity",
        "productive",
        "communication",
        "english",
        "speaking",
        "speak",
        "excel",
        "finance",
        "money",
        "investing",
        "notion",
        "tips",
        "hacks",
        "design",
        "editing",
        "edit",
        "learn",
        "learning",
        "howto",
        "tutorial",
        "tutorials",
        "study",
        "studytips",
        "confidence",
        "habits",
    ),
    "relatable_learning": (
        "meme",
        "memes",
        "relatable",
        "student",
        "students",
        "college",
        "exam",
        "exams",
        "funny",
        "comedy",
        "humor",
        "humour",
        "motivation",
        "life",
        "hostel",
        "school",
        "engineeringlife",
        "desi",
    ),
}
_WORD = re.compile(r"[a-z0-9]+")


def fix_text(s: str | None) -> str | None:
    """Instagram exports UTF-8 text as latin-1 escapes ("Ã©"); undo that when it round-trips cleanly."""
    if not s:
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _words(text: str) -> set[str]:
    t = text.lower()
    words = set(_WORD.findall(t.replace("_", " ").replace(".", " ")))
    return words | ({"machine learning"} if "machine learning" in t else set())


def categorise(text: str | None) -> tuple[str | None, list[str]]:
    """Best category for a piece of text and the keywords that matched. (None, []) when nothing matched."""
    if not text:
        return None, []
    w = _words(text)
    best: str | None = None
    hits: list[str] = []
    for cat in CATEGORIES:
        h = sorted(k for k in CATEGORY_KEYWORDS[cat] if k in w)
        if len(h) > len(hits):
            best, hits = cat, h
    return best, hits


# ---------------- parsing ----------------


def _walk(node: Any, key: str) -> Iterator[Any]:
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                yield v
            yield from _walk(v, key)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v, key)


def _first(node: Any, key: str, kind: type | tuple[type, ...]) -> Any:
    return next((v for v in _walk(node, key) if isinstance(v, kind) and v != ""), None)


def _records(data: Any) -> list[dict]:
    """The export wraps the list in a dict with a version-specific key (likes_media_likes, saved_saved_media...),
    or is a bare list. Take the first list of dicts found."""
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)][:MAX_ITEMS_PER_FILE]
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and (not v or isinstance(v[0], dict)):
                return [d for d in v if isinstance(d, dict)][:MAX_ITEMS_PER_FILE]
    return []


def _handle_from_url(url: str | None) -> str | None:
    if not url:
        return None
    m = re.match(r"https?://(?:www\.)?instagram\.com/([A-Za-z0-9._]+)/?$", url)
    if m and m.group(1) not in ("p", "reel", "reels", "tv", "stories", "explore"):
        return m.group(1)
    m = re.match(r"https?://(?:www\.)?instagram\.com/_u/([A-Za-z0-9._]+)", url)
    return m.group(1) if m else None


def _label_pairs(node: Any, out: dict[str, str]) -> None:
    if isinstance(node, dict):
        lab, val = node.get("label"), node.get("value")
        if isinstance(lab, str) and isinstance(val, str) and val and lab.lower() not in out:
            out[lab.lower()] = val
        for v in node.values():
            _label_pairs(v, out)
    elif isinstance(node, list):
        for v in node:
            _label_pairs(v, out)


def _label_value(rec: dict, *labels: str) -> str | None:
    """Newer exports: {"label_values": [{"label": "Username", "value": "x"}, ...]}, possibly nested in "dict".
    Labels are tried in the given priority order."""
    pairs: dict[str, str] = {}
    _label_pairs(rec.get("label_values"), pairs)
    return next((pairs[lab] for lab in labels if lab in pairs), None)


def _ts(rec: dict) -> datetime | None:
    t = _first(rec, "timestamp", (int, float))
    if t is None:
        return None
    if t > 10_000_000_000:  # milliseconds
        t = t / 1000
    try:
        return datetime.fromtimestamp(t, UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _item(rec: dict, source: str, collection: str | None = None) -> dict | None:
    url = _first(rec, "href", str)
    creator = (
        (rec.get("title") if isinstance(rec.get("title"), str) else None)
        or _label_value(rec, "username", "owner", "author", "name")
        or _handle_from_url(url)
    )
    if source == "following" and not creator:
        creator = _first(rec, "value", str)
    if not (url or creator):
        return None
    creator = fix_text(creator.strip().lstrip("@")) if creator else None
    return {
        "source": source,
        "creator": creator[:120] if creator else None,
        "url": url[:1000] if url else None,
        "collection": (fix_text(collection) or "")[:200] or None,
        "happened_at": _ts(rec),
    }


def _parse_saved_collections(records: list[dict]) -> Iterator[dict]:
    """Old format: a header row per collection ({"Name": {"value": "AI tools"}, "Creation Time": ...}) followed by
    its posts (rows with an href). Newer: each row may carry the collection name itself."""
    current: str | None = None
    for rec in records:
        url = _first(rec, "href", str)
        smd_raw = rec.get("string_map_data")
        smd: dict = smd_raw if isinstance(smd_raw, dict) else {}
        name_raw = smd.get("Name")
        name_d: dict = name_raw if isinstance(name_raw, dict) else {}
        labelled = _label_value(rec, "collection", "collection name")
        if url is None:
            header = (
                name_d.get("value")
                or labelled
                or (rec.get("title") if rec.get("title") != "Collection" else None)
            )
            if header:
                current = str(header)
            continue
        if name_d.get("href") and name_d.get("value") and not rec.get("title"):
            rec = {**rec, "title": name_d["value"]}  # old format: Name = {href: post, value: creator}
        it = _item(rec, "saved", labelled or current)
        if it:
            yield it


def _parse_topics(records: list[dict]) -> Iterator[dict]:
    for rec in records:
        val = _label_value(rec, "name", "interest", "topic", "value")
        if not val:
            for v in _walk(rec, "value"):
                if isinstance(v, str) and v.strip():
                    val = v
                    break
        if not val and isinstance(rec.get("title"), str):
            val = rec["title"]
        if val:
            yield {
                "source": "topic",
                "creator": None,
                "url": None,
                "collection": (fix_text(val) or "")[:200],
                "happened_at": _ts(rec),
            }


def kind_of(path: str) -> str | None:
    p = path.lower().replace("\\", "/")
    name = p.rsplit("/", 1)[-1]
    if not name.endswith(".json"):
        return None
    if "saved_collections" in name:
        return "saved_collections"
    if "saved_posts" in name or name.startswith("saved_media"):
        return "saved"
    if "liked_posts" in name or name in ("liked_media.json", "likes.json"):
        return "liked"
    if name.startswith("following") and "hashtag" not in name:
        return "following"
    if (
        "ads_interests" in name
        or "your_topics" in name
        or "recommended_topics" in name
        or ("/your_topics/" in p and name.endswith(".json"))
    ):
        return "topic"
    return None


def parse_file(path: str, raw: bytes) -> tuple[str | None, list[dict]]:
    kind = kind_of(path)
    if kind is None:
        return None, []
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError(f"{path} is too large")
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"{path} is not valid JSON") from e
    recs = _records(data)
    if kind == "saved_collections":
        return "saved", list(_parse_saved_collections(recs))
    if kind == "topic":
        return "topic", list(_parse_topics(recs))
    if kind == "following":
        # string_list_data rows: [{"href": ".../user", "value": "user", "timestamp": ...}]
        out = []
        for rec in recs:
            rows = rec.get("string_list_data") if isinstance(rec.get("string_list_data"), list) else [rec]
            for row in rows or [rec]:
                merged = {**rec, **row} if isinstance(row, dict) else rec
                if isinstance(row, dict) and row.get("value") and not rec.get("title"):
                    merged["title"] = row["value"]
                it = _item(merged, "following")
                if it:
                    out.append(it)
        return "following", out
    return kind, [it for rec in recs if (it := _item(rec, kind))]


def read_upload(filename: str, raw: bytes) -> Iterator[tuple[str, bytes]]:
    """Yield (path, bytes) for every JSON in a zip, or the single uploaded JSON."""
    if filename.lower().endswith(".zip") or raw[:2] == b"PK":
        if len(raw) > MAX_ZIP_BYTES:
            raise ValueError("Zip is larger than 300 MB. Upload the individual JSON files instead.")
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for info in z.infolist():
                if info.is_dir() or not info.filename.lower().endswith(".json"):
                    continue
                if kind_of(info.filename) is None:
                    continue
                if info.file_size > MAX_JSON_BYTES:
                    continue
                yield info.filename, z.read(info)
    else:
        yield filename, raw


def import_files(db: Session, files: Iterable[tuple[str, bytes]], demo: bool) -> dict:
    """Parse and store. Idempotent: re-importing the same download adds nothing."""
    stats: dict[str, int] = Counter()
    used, skipped, errors = [], [], []
    seen_html = False
    for name, raw in files:
        if name.lower().endswith(".html"):
            seen_html = True
            continue
        try:
            for path, content in read_upload(name, raw):
                try:
                    kind, items = parse_file(path, content)
                except ValueError as e:
                    errors.append(str(e))
                    continue
                if kind is None:
                    skipped.append(path)
                    continue
                used.append(path)
                stats[kind] += _store(db, items, demo, origin="import")
        except zipfile.BadZipFile:
            errors.append(f"{name}: not a valid zip")
        except ValueError as e:
            errors.append(str(e))
    hint = None
    if seen_html:
        hint = "This looks like the HTML version. Request the download again and choose Format: JSON."
    elif not used:
        hint = (
            "No saved, liked, following or topic files were found. In the download, look for "
            "your_instagram_activity/saved/saved_posts.json and your_instagram_activity/likes/liked_posts.json."
        )
    return {
        "added": dict(stats),
        "added_total": sum(stats.values()),
        "files_used": used[:50],
        "files_skipped": len(skipped),
        "errors": errors[:20],
        "hint": hint,
    }


def _key(it: dict) -> str:
    when = it["happened_at"].strftime("%Y%m%d%H%M%S") if it.get("happened_at") else ""
    return (
        f"{it['source']}|{it.get('url') or ''}|{it.get('creator') or ''}|{it.get('collection') or ''}|{when}"[
            :300
        ]
    )


def _store(db: Session, items: list[dict], demo: bool, origin: str) -> int:
    existing = set(db.scalars(select(InterestItem.dedupe_key).where(InterestItem.is_demo.is_(demo))))
    n = 0
    for it in items:
        k = _key(it)
        if k in existing:
            continue
        existing.add(k)
        db.add(InterestItem(**it, origin=origin, dedupe_key=k, is_demo=demo))
        n += 1
    db.flush()
    return n


def add_manual(
    db: Session, url: str | None, note: str | None, creator: str | None, demo: bool
) -> InterestItem:
    creator = (creator or "").strip().lstrip("@") or _creator_from_post_url(url)
    it = {
        "source": "manual",
        "creator": creator or None,
        "url": url,
        "collection": None,
        "happened_at": utcnow(),
    }
    row = InterestItem(**it, note=note, origin="manual", dedupe_key=_key(it), is_demo=demo)
    db.add(row)
    db.flush()
    return row


def _creator_from_post_url(url: str | None) -> str | None:
    """instagram.com/<user>/reel/<id> carries the handle; /reel/<id> alone does not. Never fetched."""
    if not url:
        return None
    m = re.match(r"https?://(?:www\.)?instagram\.com/([A-Za-z0-9._]+)/(?:p|reel|reels)/", url)
    return m.group(1) if m else None


# ---------------- profile ----------------


def profile(db: Session, demo: bool) -> dict:
    rows = db.scalars(select(InterestItem).where(InterestItem.is_demo.is_(demo))).all()
    counts = Counter(r.source for r in rows)
    creators: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        if r.creator and r.source in ("saved", "liked", "manual"):
            creators[r.creator][r.source] += 1
    top_creators = sorted(
        ({"creator": c, "n": sum(v.values()), "sources": dict(v)} for c, v in creators.items()),
        key=lambda x: -int(str(x["n"])),
    )[:10]
    coll = Counter(r.collection for r in rows if r.source == "saved" and r.collection)
    collections = [
        {"name": name, "n": n, "category": categorise(name)[0]} for name, n in coll.most_common(12)
    ]
    monthly: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        if r.happened_at and r.source in ("saved", "liked"):
            monthly[r.happened_at.strftime("%Y-%m")][r.source] += 1
    months = [
        {"month": m, "saved": c["saved"], "liked": c["liked"]} for m, c in sorted(monthly.items())[-12:]
    ]

    # Category evidence, weighted: your own notes 3, collection names 2 (per item), topics 1, handles 1.
    score: dict[str, float] = defaultdict(float)
    evidence: dict[str, list[str]] = defaultdict(list)
    n_items: Counter = Counter()

    def credit(cat: str | None, w: float, why: str) -> None:
        if cat:
            score[cat] += w
            n_items[cat] += 1
            if why not in evidence[cat] and len(evidence[cat]) < 4:
                evidence[cat].append(why)

    for r in rows:
        if r.note:
            c, hits = categorise(r.note)
            credit(c, 3, f"your note “{r.note[:50]}”")
        if r.collection and r.source == "saved":
            c, _ = categorise(r.collection)
            credit(c, 2, f"collection “{r.collection}”")
        if r.source == "topic" and r.collection:
            c, _ = categorise(r.collection)
            credit(c, 1, f"Instagram topic “{r.collection}”")
        if r.creator and r.source in ("saved", "liked", "manual"):
            c, hits = categorise(r.creator)
            credit(c, 1, f"you save/like @{r.creator}")
    total = sum(score.values()) or 1
    cats = [
        {
            "category": c,
            "label": CATEGORY_LABEL[c],
            "share": round(score[c] / total * 100),
            "matches": n_items[c],
            "evidence": evidence[c],
            "confidence": "medium" if n_items[c] >= 10 else "low",
        }
        for c in sorted(score, key=lambda k: -score[k])
    ]
    notes = sorted(
        (r for r in rows if r.source == "manual"), key=lambda r: r.created_at or utcnow(), reverse=True
    )
    last_import = max((r.created_at for r in rows if r.origin in ("import", "demo")), default=None)
    return {
        "counts": {s: counts.get(s, 0) for s in ("saved", "liked", "following", "topic", "manual")},
        "total": len(rows),
        "top_creators": top_creators,
        "collections": collections,
        "monthly": months,
        "categories": cats,
        "topics": [r.collection for r in rows if r.source == "topic" and r.collection][:20],
        "notes": [
            {
                "id": r.id,
                "url": r.url,
                "note": r.note,
                "creator": r.creator,
                "at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in notes[:20]
        ],
        "last_import_at": last_import.isoformat() if last_import else None,
        "inferred_note": "Topics are guessed by matching words in your collection names, your notes, Instagram's "
        "topic list and creator handles. Instagram doesn't say what a saved reel is about, so treat these as "
        "hints, not facts.",
    }
