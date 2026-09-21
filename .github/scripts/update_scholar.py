#!/usr/bin/env python3
"""Fetch Prafulla K Jha's Google Scholar stats and write assets/stats.json.

Primary source: the `scholarly` package. If that is rate-limited/blocked,
falls back to a plain Requests + BeautifulSoup parse of the profile page.
If both fail, the existing stats.json is left untouched (site keeps the last
known good numbers) and the run exits successfully.
"""
import datetime
import json
import pathlib
import sys
import time

AUTHOR_ID = "JjyQwnAAAAAJ"
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "stats.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def existing() -> dict:
    if OUT.exists():
        try:
            return json.loads(OUT.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return {}


def from_scholarly() -> dict:
    from scholarly import scholarly

    last_err = None
    for attempt in range(3):
        try:
            author = scholarly.search_author_id(AUTHOR_ID)
            author = scholarly.fill(author, sections=["basics", "indices", "counts"])
            return {
                "citations": int(author.get("citedby") or 0),
                "hindex": int(author.get("hindex") or 0),
                "i10index": int(author.get("i10index") or 0),
            }
        except Exception as exc:  # noqa: BLE001 - retry on rate limits
            last_err = exc
            time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"scholarly failed after retries: {last_err}")


def from_page() -> dict:
    import requests
    from bs4 import BeautifulSoup

    url = f"https://scholar.google.com/citations?user={AUTHOR_ID}&hl=en"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    stats = {}
    for row in soup.select("#gsc_rsb_st tr"):
        label = row.select_one("td.gsc_rsb_f")
        if label is None:
            continue
        label_text = label.get_text(" ", strip=True).lower()
        cells = row.select("td.gsc_rsb_std")
        if not cells:
            continue
        # Columns: [All] [Since XXXX]
        def to_int(value):
            return int(value.replace(",", "")) if value else 0

        if label_text.startswith("citations"):
            stats["citations"] = to_int(cells[0].get_text(strip=True))
        elif label_text.startswith("h-index"):
            stats["hindex"] = to_int(cells[0].get_text(strip=True))
        elif label_text.startswith("i10-index"):
            stats["i10index"] = to_int(cells[0].get_text(strip=True))

    if not stats:
        raise RuntimeError("could not locate stats table in Scholar page")
    return stats


def write_stats() -> None:
    payload: dict | None = None
    errors = []

    try:
        payload = from_scholarly()
        source = "scholarly"
    except Exception as exc:  # noqa: BLE001
        errors.append(f"scholarly: {exc}")
        try:
            payload = from_page()
            source = "page"
        except Exception as exc2:  # noqa: BLE001
            errors.append(f"page: {exc2}")

    if payload is None:
        print("SKIP: keeping existing stats.json.", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return

    payload["updated"] = datetime.date.today().isoformat()
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"OK ({source}): {json.dumps(payload)}")


if __name__ == "__main__":
    write_stats()
