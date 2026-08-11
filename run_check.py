from urllib.request import Request, urlopen
from pathlib import Path
import json
import xml.etree.ElementTree as ET

SOURCES = json.loads(
    (Path(__file__).resolve().parent / "sources.json").read_text(encoding="utf-8")
)

UA = "MorningBrief/0.2 (personal-use research prototype)"
HEADERS = {
    "User-Agent": UA,
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

def fetch(url):
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=20) as r:
        return r.status, r.headers.get("Content-Type"), r.read()

def count_items(body):
    root = ET.fromstring(body)
    return (
        len(root.findall(".//item")),
        len(root.findall(".//{*}entry")),
    )

def main():
    print("Morning Brief — Phase 1A connectivity test v0.2")
    print("=" * 58)
    results = []

    for source in SOURCES:
        try:
            status, content_type, body = fetch(source["url"])
            rss_items, atom_entries = count_items(body)
            result = {
                **source,
                "http_status": status,
                "content_type": content_type,
                "bytes": len(body),
                "rss_items": rss_items,
                "atom_entries": atom_entries,
                "parse": "ok",
            }
            results.append(result)
            print(
                f"PASS  {source['name']} — {source['section']} "
                f"[{source['language']}] | HTTP {status} | "
                f"RSS={rss_items} Atom={atom_entries}"
            )
        except Exception as exc:
            results.append({**source, "error": str(exc)})
            print(f"FAIL  {source['name']} — {source['section']}: {exc}")

    out = Path("data/connectivity-check-v0.2.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"\nWrote {out}")

if __name__ == "__main__":
    main()
