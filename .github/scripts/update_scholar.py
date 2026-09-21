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
import random
import sys
import threading
import time

AUTHOR_ID = "PieZW1YAAAAJ"
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "stats.json"

HARD_DEADLINE_SECONDS = 240

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Mobile; iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
]
HOSTS = ["scholar.google.com", "scholar.google.co.in"]


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def from_scholarly() -> dict:
    from scholarly import scholarly

    last_err = None
    for attempt in range(3):
        log(f"  scholarly attempt {attempt + 1}/3 ...")
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
            time.sleep(8 * (attempt + 1))
    raise RuntimeError(f"scholarly failed after retries: {last_err}")


def from_scholarly_bounded(budget_seconds: float) -> dict:
    """Run scholarly in a watchdog thread; scholarly does not set HTTP timeouts
    and can hang forever on blocked IPs, so we never wait longer than the budget."""
    result = {}

    def work() -> None:
        try:
            result["value"] = from_scholarly()
        except Exception as exc:  # noqa: BLE001
            result["error"] = exc

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(budget_seconds)
    if thread.is_alive():
        raise RuntimeError("scholarly did not finish within its time budget")
    if "error" in result:
        raise result["error"]
    return result["value"]


def _extract_stats(text: str) -> dict:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(text, "html.parser")
    if soup.select_one("#gsc_rsb_st") is None:
        raise RuntimeError("stats table not found on Scholar page")

    stats = {}
    for row in soup.select("#gsc_rsb_st tr"):
        label = row.select_one("td.gsc_rsb_f")
        if label is None:
            continue
        label_text = label.get_text(" ", strip=True).lower()
        cells = row.select("td.gsc_rsb_std")
        if not cells:
            continue

        def to_int(value):
            return int(value.replace(",", "")) if value else 0

        # Columns: [All] [Since XXXX]
        if label_text.startswith("citations"):
            stats["citations"] = to_int(cells[0].get_text(strip=True))
        elif label_text.startswith("h-index"):
            stats["hindex"] = to_int(cells[0].get_text(strip=True))
        elif label_text.startswith("i10-index"):
            stats["i10index"] = to_int(cells[0].get_text(strip=True))

    if not stats:
        raise RuntimeError("no stat values parsed from Scholar page")
    return stats


def from_page(deadline: float) -> dict:
    import requests

    last_err = None
    for host in HOSTS:
        for attempt in range(2):
            if time.monotonic() >= deadline:
                raise RuntimeError("time budget exhausted before page fetch")
            log(f"  page fetch {host} attempt {attempt + 1}/2 ...")
            try:
                session = requests.Session()
                session.mount(
                    "https://",
                    requests.adapters.HTTPAdapter(
                        max_retries=1, pool_connections=4, pool_maxsize=4
                    ),
                )
                session.headers.update(
                    {
                        "User-Agent": random.choice(USER_AGENTS),
                        "Accept-Language": "en-US,en;q=0.9",
                    }
                )
                # Warm up cookies before requesting the profile.
                session.get(f"https://{host}/", timeout=15)

                url = f"https://{host}/citations?user={AUTHOR_ID}&hl=en"
                resp = session.get(url, timeout=25)
                resp.raise_for_status()
                return _extract_stats(resp.text)
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"page fetch failed for all hosts: {last_err}")


def write_stats() -> None:
    deadline = time.monotonic() + HARD_DEADLINE_SECONDS
    payload: dict | None = None
    errors = []

    log("fetching Google Scholar stats ...")
    try:
        remaining = deadline - time.monotonic()
        payload = from_scholarly_bounded(min(remaining, 100.0))
        source = "scholarly"
    except Exception as exc:  # noqa: BLE001
        errors.append(f"scholarly: {exc}")
        log("scholarly failed, falling back to direct page fetch ...")
        try:
            payload = from_page(deadline)
            source = "page"
        except Exception as exc2:  # noqa: BLE001
            errors.append(f"page: {exc2}")

    if payload is None:
        log("SKIP: keeping existing stats.json.")
        for e in errors:
            log(f"  - {e}")
        return

    payload["updated"] = datetime.date.today().isoformat()
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    log(f"OK ({source}): {json.dumps(payload)}")


if __name__ == "__main__":
    write_stats()