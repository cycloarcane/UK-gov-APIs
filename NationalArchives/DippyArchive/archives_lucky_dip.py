#!/usr/bin/env python3
"""
🎲 National Archives Lucky-Dip
Returns ONE random digitised record that is view-able online, plus
the random word that found it.

Used by:
  • CLI  – run this file directly
  • Flask web-app – imported by app.py
"""

from __future__ import annotations
import random, sys, logging, argparse
from typing import Dict, List, Any
import requests

API_URL  = "https://discovery.nationalarchives.gov.uk/API/search/records"
VIEW_URL = "https://discovery.nationalarchives.gov.uk/details/r/{id}"

# fallback list if 'wordfreq' isn’t installed
FALLBACK_WORDS = (
    "river castle letter crown code secret garden battle parliament church bridge"
).split()

session = requests.Session()
session.headers.update({"Accept": "application/json"})


# ---------- helpers --------------------------------------------------------

def random_word() -> str:
    """Return a random English word (tries wordfreq, else fallback)."""
    try:
        from wordfreq import top_n_list
        return random.choice(top_n_list("en", 5000))
    except Exception:
        return random.choice(FALLBACK_WORDS)


def fetch_records(query: str, page_size: int = 300) -> List[Dict[str, Any]]:
    """Fetch a page of digitised records for `query`."""
    params = {"query": query, "digitised": "true", "pageSize": str(page_size)}
    r = session.get(API_URL, params=params, timeout=10)
    r.raise_for_status()
    return r.json().get("records", [])


def pick_online_record(max_attempts: int = 20) -> Dict[str, Any]:
    """
    Keep rolling random words until we get a record whose public page
    (`/details/r/<id>`) returns HTTP 200.
    Returns the record dict plus:
        • 'view_url' – direct Discovery URL
        • 'query'    – the random word used
    """
    for _ in range(max_attempts):
        word   = random_word()
        recs   = fetch_records(word)
        random.shuffle(recs)
        for rec in recs:
            rec_id = rec.get("id")
            if not rec_id:
                continue
            url = VIEW_URL.format(id=rec_id)
            try:
                session.head(url, timeout=5).raise_for_status()
                rec.update(view_url=url, query=word)  # <— add metadata
                return rec
            except requests.RequestException:
                continue
    raise RuntimeError("No online record found after several attempts.")


# ---------- minimal CLI ----------------------------------------------------

def _print(rec: Dict[str, Any]) -> None:
    print(f"\n— lucky word: “{rec['query']}” —")
    print(f"Title      : {rec.get('title')}")
    print(f"Held by    : {', '.join(rec.get('heldBy', [])) or 'Unknown'}")
    if desc := rec.get("description"):
        print(f"Description: {desc}")
    print(f"Open       : {rec['view_url']}\n")


def cli() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="enable INFO-level logging")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s: %(message)s")

    print("🎲  National Archives lucky-dip CLI\n")
    while True:
        try:
            _print(pick_online_record())
        except Exception as exc:
            logging.error(exc)
            sys.exit(1)

        if input("⏎  roll again   |   q + ⏎  quit: ").strip().lower() == "q":
            break


if __name__ == "__main__":
    cli()
