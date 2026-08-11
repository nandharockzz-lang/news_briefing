from urllib.request import Request, urlopen
from pathlib import Path
import json
import xml.etree.ElementTree as ET

SOURCES = [
    ("The Indian Express — Chennai", "https://indianexpress.com/section/cities/chennai/feed/"),
    ("Times of India — Chennai", "https://timesofindia.indiatimes.com/rssfeeds/2950623.cms"),
    ("NDTV — India", "https://feeds.feedburner.com/ndtvnews-top-stories"),
    ("OneIndia — India", "https://www.oneindia.com/rss/feeds/oneindia-news-fb.xml"),
    ("Daily Thanthi — RSS page candidate", "https://www.dailythanthi.com/rss"),
    ("Dinamani — RSS page candidate", "https://www.dinamani.com/topic/rss"),
    ("PIB — RSS page", "https://www.pib.gov.in/ViewRss.aspx?lang=1&reg=1"),
]

UA = "MorningBrief/0.1 personal research prototype"

def fetch(url):
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml"})
    with urlopen(req, timeout=20) as r:
        return r.status, r.headers.get("Content-Type"), r.read()

def main():
    print("Morning Brief — Phase 1A connectivity check")
    print("=" * 50)
    results = []
    for name, url in SOURCES:
        try:
            status, content_type, body = fetch(url)
            root = ET.fromstring(body)
            rss_items = len(root.findall(".//item"))
            atom_entries = len(root.findall(".//{*}entry"))
            results.append({
                "source": name,
                "url": url,
                "status": status,
                "content_type": content_type,
                "bytes": len(body),
                "rss_items": rss_items,
                "atom_entries": atom_entries,
                "parse": "ok",
            })
            print(f"PASS  {name}: HTTP {status}, {len(body):,} bytes, RSS={rss_items}, Atom={atom_entries}")
        except Exception as e:
            results.append({"source": name, "url": url, "error": str(e)})
            print(f"FAIL  {name}: {e}")

    out = Path("data/connectivity-check.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {out}")

if __name__ == "__main__":
    main()
