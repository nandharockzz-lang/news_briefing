from __future__ import annotations

from urllib.request import Request, urlopen
from pathlib import Path
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from difflib import SequenceMatcher
import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parents[1]
SOURCES_FILE = BASE / "src" / "sources.json"
OUTPUT = BASE / "data" / "articles-v0.3.json"

UA = "MorningBrief/0.3 (personal-use research prototype)"
HEADERS = {
    "User-Agent": UA,
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 20

# Deterministic, conservative noise filters.
# These are intentionally narrow: we do not want to remove legitimate news.
NOISE_PATTERNS = [
    r"\bhoroscope\b",
    r"\bastrology\b",
    r"\btoday'?s horoscope\b",
    r"\bzodiac\b",
    r"\bmemes?\b",
    r"\bjokes?\b",
]

def clean(value: str | None) -> str | None:
    if not value:
        return None
    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or None

def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value.strip())
    except Exception:
        try:
            dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()

def fetch(url: str) -> bytes:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=TIMEOUT) as response:
        return response.read()

def parse_feed(body: bytes, source: dict) -> list[dict]:
    root = ET.fromstring(body)
    records = []

    for item in root.findall(".//item"):
        title = clean(item.findtext("title"))
        url = (item.findtext("link") or "").strip()
        description = clean(item.findtext("description"))
        published = parse_date(item.findtext("pubDate") or item.findtext("published"))
        if not title or not url:
            continue
        records.append({
            "id": hashlib.sha256(url.encode()).hexdigest()[:20],
            "source_id": source["id"],
            "source_name": source["name"],
            "source_type": source["source_type"],
            "section": source["section"],
            "language": source["language"],
            "title": title,
            "url": url,
            "published_at": published,
            "description": description,
        })

    for entry in root.findall(".//{*}entry"):
        title = clean(entry.findtext("{*}title"))
        url = None
        for link in entry.findall("{*}link"):
            href = link.attrib.get("href")
            if href:
                url = href
                break
        description = clean(
            entry.findtext("{*}summary") or entry.findtext("{*}content")
        )
        published = parse_date(
            entry.findtext("{*}published") or entry.findtext("{*}updated")
        )
        if not title or not url:
            continue
        records.append({
            "id": hashlib.sha256(url.encode()).hexdigest()[:20],
            "source_id": source["id"],
            "source_name": source["name"],
            "source_type": source["source_type"],
            "section": source["section"],
            "language": source["language"],
            "title": title,
            "url": url,
            "published_at": published,
            "description": description,
        })

    return records

def normalized_title(title: str) -> str:
    # Unicode-aware, intentionally simple normalization for candidate matching.
    text = html.unescape(title).lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()

def is_obvious_noise(title: str) -> bool:
    text = title.lower()
    return any(re.search(pattern, text) for pattern in NOISE_PATTERNS)

def near_duplicate_pairs(records: list[dict], threshold: float = 0.88) -> list[dict]:
    pairs = []
    normalized = [(r, normalized_title(r["title"])) for r in records]

    # This is intentionally O(n²) because Phase 1A has only ~100 records.
    for i in range(len(normalized)):
        left, left_title = normalized[i]
        for j in range(i + 1, len(normalized)):
            right, right_title = normalized[j]

            # Avoid treating unrelated language pairs as near duplicates.
            if left["language"] != right["language"]:
                continue

            score = SequenceMatcher(None, left_title, right_title).ratio()
            if score >= threshold and left["url"] != right["url"]:
                pairs.append({
                    "left_id": left["id"],
                    "right_id": right["id"],
                    "similarity": round(score, 4),
                    "left_source": left["source_name"],
                    "right_source": right["source_name"],
                    "left_title": left["title"],
                    "right_title": right["title"],
                })
    return pairs

def main():
    sources = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))

    raw = []
    errors = []

    for source in sources:
        try:
            body = fetch(source["url"])
            records = parse_feed(body, source)
            raw.extend(records)
            print(f"FETCH PASS  {source['name']} — {len(records)} records")
        except Exception as exc:
            errors.append({
                "source": source["name"],
                "url": source["url"],
                "error": str(exc),
            })
            print(f"FETCH FAIL  {source['name']}: {exc}")

    raw_count = len(raw)

    # URL-level deduplication.
    unique_by_url = {}
    duplicate_urls = 0
    for record in raw:
        if record["url"] in unique_by_url:
            duplicate_urls += 1
        else:
            unique_by_url[record["url"]] = record

    unique = list(unique_by_url.values())

    # Conservative deterministic noise filter.
    filtered = []
    noise = []
    for record in unique:
        if is_obvious_noise(record["title"]):
            noise.append(record)
        else:
            filtered.append(record)

    pairs = near_duplicate_pairs(filtered)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "1A-real-article-ingestion",
        "sources_attempted": len(sources),
        "raw_article_count": raw_count,
        "unique_url_count": len(unique),
        "duplicate_url_count": duplicate_urls,
        "obvious_noise_count": len(noise),
        "retained_article_count": len(filtered),
        "near_duplicate_candidate_count": len(pairs),
        "fetch_error_count": len(errors),
        "articles": sorted(
            filtered,
            key=lambda x: x.get("published_at") or "",
            reverse=True,
        ),
        "noise": noise,
        "near_duplicate_candidates": pairs,
        "fetch_errors": errors,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n=== PHASE 1A METRICS ===")
    print(f"Raw articles:              {raw_count}")
    print(f"Unique URLs:               {len(unique)}")
    print(f"Duplicate URLs removed:    {duplicate_urls}")
    print(f"Obvious noise removed:     {len(noise)}")
    print(f"Retained articles:         {len(filtered)}")
    print(f"Near-duplicate candidates: {len(pairs)}")
    print(f"Fetch errors:              {len(errors)}")
    print(f"\nSaved: {OUTPUT}")

if __name__ == "__main__":
    main()
