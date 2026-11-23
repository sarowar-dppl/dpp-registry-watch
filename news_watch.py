"""Fetches DPP-related news searches (Google News, with Bing as backup) and
merges them into one RSS feed, news.xml, that any feed reader can open.
"""
import re, sys, time, urllib.request
import xml.etree.ElementTree as ET
from email.utils import format_datetime, parsedate_to_datetime
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus
from xml.sax.saxutils import escape

SEARCHES = {
    "DPP & Registry": '"digital product passport" OR "DPP registry" OR "product passport" EU',
    "Battery passport": '"battery passport" OR "Batteries Regulation" OR "EU battery regulation"',
    "ESPR / Ecodesign": 'ESPR OR "Ecodesign for Sustainable Products Regulation" OR "ecodesign delegated act"',
    "Other EU product rules": '"Construction Products Regulation" OR "Toy Safety Regulation" OR "Detergents Regulation" OR PPWR OR "End-of-Life Vehicles Regulation"',
    "DPP technical": '"digital product passport" (API OR OpenAPI OR standard OR CEN OR interoperability OR "data carrier")',
    "Raw materials & traceability": '"Critical Raw Materials Act" OR "supply chain traceability" EU',
    "Commission site": 'site:ec.europa.eu "product passport"',
}
BING_BACKUP = ['"digital product passport"', '"battery passport"', '"Batteries Regulation"', "ESPR", '"ecodesign"', "PPWR"]
FEED, MAX_ITEMS = Path("news.xml"), 300
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def items_from(xml_bytes, topic):
    out = []
    for it in ET.fromstring(xml_bytes).iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if not title or not link:
            continue
        try:
            when = parsedate_to_datetime(it.findtext("pubDate"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except Exception:
            when = datetime.now(timezone.utc)
        src = (it.findtext("source") or "").strip()
        out.append({"title": title, "link": link, "date": when, "topic": topic, "source": src})
    return out


def key(title):
    # Same story from Google and Bing: compare titles without the " - Source" suffix.
    return re.sub(r"\W+", " ", title.rsplit(" - ", 1)[0]).strip().lower()


def main():
    found, ok, google_ok = {}, 0, 0
    jobs = [(t, f"https://news.google.com/rss/search?q={quote_plus(q)}&hl=en-GB&gl=GB&ceid=GB:en", True) for t, q in SEARCHES.items()]
    jobs += [(q.strip('"'), f"https://www.bing.com/news/search?q={quote_plus(q)}&format=rss", False) for q in BING_BACKUP]
    for topic, url, is_google in jobs:
        try:
            got = items_from(fetch(url), topic)
            ok += 1
            google_ok += is_google
            print(f"OK   {topic}: {len(got)} items")
        except Exception as e:
            print(f"WARN {topic}: {e}", file=sys.stderr)
            continue
        for i in got:
            found.setdefault(key(i["title"]), i)
        time.sleep(2)  # be polite: one request every couple of seconds
    if not ok:
        sys.exit("ERROR: no news searches could be fetched")
    print(f"Google searches working: {google_ok}/{len(SEARCHES)}")
    items = sorted(found.values(), key=lambda i: i["date"], reverse=True)[:MAX_ITEMS]
    body = "".join(
        f"<item><title>{escape(f'[{i['topic']}] ' + i['title'])}</title><link>{escape(i['link'])}</link>"
        f"<guid isPermaLink=\"false\">{escape(i['link'])}</guid><pubDate>{format_datetime(i['date'])}</pubDate>"
        f"<description>{escape(i['source'] or i['topic'])}</description></item>" for i in items)
    FEED.write_text('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
                    "<title>EU DPP news (Google + Bing)</title>"
                    "<link>https://github.com/sarowar-dppl/dpp-registry-watch</link>"
                    "<description>News on Digital Product Passports, ESPR, batteries and related EU rules</description>"
                    f"{body}</channel></rss>", encoding="utf-8")
    print(f"{len(items)} items written to {FEED}")


if __name__ == "__main__":
    main()
