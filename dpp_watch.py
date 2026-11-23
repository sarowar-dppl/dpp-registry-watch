"""Watches the Commission's DPP pages and writes new or changed files to feed.xml.

Every file the Commission publishes on these pages has a link like
/document/download/<id>_en?filename=...  A new id means a new file or a new
version of an existing one (for example, an updated OpenAPI ZIP).
"""
import hashlib, json, re, sys, urllib.request
from datetime import datetime, timezone
from email.utils import format_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
from xml.sax.saxutils import escape

PAGES = {
    "DPP Resources & documentation": "https://single-market-economy.ec.europa.eu/single-market/digital-product-passport/resources-documentation_en",
    "DPP Registry": "https://single-market-economy.ec.europa.eu/single-market/digital-product-passport/dpp-registry_en",
    "DPP hub": "https://single-market-economy.ec.europa.eu/single-market/digital-product-passport_en",
    "DPP for economic operators": "https://single-market-economy.ec.europa.eu/single-market/digital-product-passport/economic-operators_en",
    "DPP harmonised standards": "https://single-market-economy.ec.europa.eu/single-market/goods/european-standards/harmonised-standards/digital-product-passport-dpp_en",
}
API_WORDS = re.compile(r"api|openapi|swagger|schema|semantic|json|shacl|service account|authentication|integration|technical", re.I)
STATE, FEED, MAX_ITEMS = Path("state.json"), Path("feed.xml"), 100


class PageParser(HTMLParser):
    """Collects download links and the visible text inside <main>."""
    def __init__(self):
        super().__init__()
        self.links, self.text, self.in_main, self.skip = [], [], False, 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "main":
            self.in_main = True
        if tag in ("script", "style", "nav"):
            self.skip += 1
        if tag == "a" and "/document/download/" in (a.get("href") or ""):
            self.links.append(a["href"])
    def handle_endtag(self, tag):
        if tag == "main":
            self.in_main = False
        if tag in ("script", "style", "nav") and self.skip:
            self.skip -= 1
    def handle_data(self, data):
        if self.in_main and not self.skip and data.strip():
            self.text.append(data.strip())


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (DPP watch; RSS)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def parse(html, base):
    p = PageParser(); p.feed(html)
    files = {}
    for href in p.links:
        full = urljoin(base, unescape(href))
        doc_id = re.search(r"/document/download/([0-9a-f-]+)", full).group(1)
        name = parse_qs(urlparse(full).query).get("filename", [doc_id])[0]
        files[doc_id] = {"name": name, "url": full}
    text = "\n".join(p.text) or html
    return files, hashlib.sha256(text.encode()).hexdigest(), text


def main():
    state = json.loads(STATE.read_text()) if STATE.exists() else {"pages": {}, "items": []}
    first_run = not state["pages"]
    now = datetime.now(timezone.utc)
    new_items, seen, ok = [], set(), 0
    for label, url in PAGES.items():
        try:
            files, digest, text = parse(fetch(url), url)
        except Exception as e:
            print(f"WARN {label}: {e}", file=sys.stderr)
            continue
        ok += 1
        old = state["pages"].get(label, {"files": {}, "hash": None})
        for doc_id, f in files.items():
            if doc_id not in old["files"] and doc_id not in seen and not first_run:
                seen.add(doc_id)
                tag = "API / technical" if API_WORDS.search(f["name"]) else "File"
                new_items.append({"title": f"[{tag}] New on {label}: {f['name']}",
                                  "link": f["url"], "guid": doc_id,
                                  "desc": f"New or updated file published on {url}",
                                  "date": format_datetime(now)})
        if old["hash"] and digest != old["hash"] and not first_run:
            notes = [l for l in text.splitlines() if re.search(r"Note:|last update|V\d", l)][:5]
            new_items.append({"title": f"[Page changed] {label}", "link": url,
                              "guid": f"{label}-{digest[:12]}",
                              "desc": "Text on this page changed. " + " | ".join(notes),
                              "date": format_datetime(now)})
        state["pages"][label] = {"files": files, "hash": digest}
    if not ok:
        sys.exit("ERROR: no pages could be fetched; nothing saved")
    if first_run:
        new_items.append({"title": "DPP watch started: baseline saved", "link": PAGES["DPP Resources & documentation"],
                          "guid": f"start-{now:%Y%m%d%H%M}", "desc": "Future new files and page changes will appear here.",
                          "date": format_datetime(now)})
    state["items"] = (new_items + state["items"])[:MAX_ITEMS]
    STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False))
    items = "".join(
        f"<item><title>{escape(i['title'])}</title><link>{escape(i['link'])}</link>"
        f"<guid isPermaLink=\"false\">{escape(i['guid'])}</guid><pubDate>{i['date']}</pubDate>"
        f"<description>{escape(i['desc'])}</description></item>" for i in state["items"])
    FEED.write_text('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
                    "<title>EU DPP Registry - new files and API docs</title>"
                    f"<link>{PAGES['DPP Resources & documentation']}</link>"
                    "<description>New files and changes on the Commission's DPP and Registry pages</description>"
                    f"{items}</channel></rss>")
    print(f"{len(new_items)} new item(s)")


if __name__ == "__main__":
    main()
