from __future__ import annotations

import ast
import hashlib
import json
import math
import re
import unicodedata
from dataclasses import asdict, fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Type, TypeVar

T = TypeVar("T")

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "my",
    "of",
    "on",
    "or",
    "our",
    "so",
    "that",
    "the",
    "their",
    "then",
    "there",
    "these",
    "this",
    "to",
    "was",
    "we",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "you",
    "your",
}


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def truncate_text(text: str, limit: int, suffix: str = "...") -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - len(suffix))].rstrip() + suffix


def slugify(value: str, max_length: int = 80) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    value = re.sub(r"-{2,}", "-", value)
    return value[:max_length].strip("-") or "item"


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def safe_filename(value: str, max_length: int = 120) -> str:
    return slugify(value, max_length=max_length)


def serialize_for_json(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=timezone.utc)
        return obj.astimezone(timezone.utc).isoformat()
    if is_dataclass(obj):
        return {k: serialize_for_json(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): serialize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [serialize_for_json(v) for v in obj]
    return obj


def safe_json_dumps(obj: Any, indent: int = 2) -> str:
    return json.dumps(serialize_for_json(obj), indent=indent, ensure_ascii=False)


def parse_json_like(text: str) -> Any | None:
    if not text:
        return None

    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    candidates: list[str] = [cleaned]
    for open_char, close_char in [("{", "}"), ("[", "]")]:
        start = cleaned.find(open_char)
        end = cleaned.rfind(close_char)
        if start != -1 and end != -1 and end > start:
            candidates.append(cleaned[start : end + 1])

    for candidate in candidates:
        candidate = re.sub(r",(\s*[}\]])", r"\1", candidate)
        try:
            return json.loads(candidate)
        except Exception:
            pass
        try:
            return ast.literal_eval(candidate)
        except Exception:
            pass
    return None


def coerce_dataclass(cls: Type[T], data: Any) -> T:
    if isinstance(data, cls):
        return data
    if data is None:
        return cls()
    if not isinstance(data, dict):
        return cls()

    valid_fields = {f.name for f in fields(cls)}
    kwargs = {key: value for key, value in data.items() if key in valid_fields}
    return cls(**kwargs)


def extract_keywords(text: str, limit: int = 12) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_\-']+", (text or "").lower())
    counts: dict[str, int] = {}
    for token in tokens:
        token = token.strip("'-_")
        if len(token) < 3 or token in STOPWORDS or token.isdigit():
            continue
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, _ in ranked[:limit]]


def extract_video_id(url_or_id: str) -> str:
    if not url_or_id:
        return ""
    match = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", url_or_id)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_id):
        return url_or_id
    return ""


def normalize_video_url(url_or_id: str) -> str:
    video_id = extract_video_id(url_or_id)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    if url_or_id.startswith("http"):
        return url_or_id
    return f"https://www.youtube.com/watch?v={url_or_id}"


def iso_from_timestamp(timestamp: int | float | None) -> str:
    if not timestamp:
        return ""
    return datetime.fromtimestamp(float(timestamp), tz=timezone.utc).isoformat()


def parse_iso_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def compute_age_days(published_at_iso: str | None) -> float:
    published = parse_iso_date(published_at_iso)
    if not published:
        return 0.0
    now = datetime.now(timezone.utc)
    delta = now - published.astimezone(timezone.utc)
    return max(delta.total_seconds() / 86400.0, 0.0)


def build_transcript_digest(title: str, transcript_text: str, segments: list[dict[str, Any]] | None = None, excerpt_chars: int = 3500) -> dict[str, Any]:
    transcript_text = normalize_whitespace(transcript_text or "")
    opening = ""
    if segments:
        opening = " ".join(str(seg.get("text", "")) for seg in segments[:6])
    opening = normalize_whitespace(opening)

    first_excerpt = truncate_text(transcript_text, excerpt_chars)
    keywords = extract_keywords(transcript_text, 12)
    word_count = len(transcript_text.split())
    line_count = len(segments or [])

    return {
        "title": title,
        "word_count": word_count,
        "line_count": line_count,
        "opening_moments": truncate_text(opening, 500),
        "excerpt": first_excerpt,
        "top_keywords": keywords,
    }


def chunk_text(text: str, chunk_size: int = 4000) -> list[str]:
    text = text or ""
    if len(text) <= chunk_size:
        return [text]
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def format_number(value: int | float | None) -> str:
    if value is None:
        return "0"
    try:
        value = float(value)
    except Exception:
        return str(value)
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    if value.is_integer():
        return str(int(value))
    return f"{value:.1f}"

