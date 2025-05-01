#!/usr/bin/env python3
"""
🎲  National Archives Lucky-Dip
Returns one *digitised* catalogue entry that can be opened online,
and lets the user roll again until they quit.

Run:  python archives_lucky_dip.py        # one-off
       python archives_lucky_dip.py -v    # verbose logging
"""

from __future__ import annotations
import random, sys, logging, argparse, pathlib
import requests
from typing import Dict, Any, List

API_URL = "https://discovery.nationalarchives.gov.uk/API/search/records"
VIEW_URL_FMT = "https://discovery.nationalarchives.gov.uk/details/r/{record_id}"
WORDS: List[str] = (
    # small fallback list; install `wordfreq` for thousands more
    "river castle letter crown code secret garden battle parliament church bridge".split()
)

session = requests.Session()
session.headers.update({"Accept": "application/json"})


def random_word() -> str:
    """Return a random English word."""
    try:
        from wordfreq import top_n_list      # optional
        return random.choice(top_n_list("en", 5000))
    except Exception:
        return random.choice(WORDS)


def fetch_records(query: str, page_size: int = 100) -> List[Dict[str, Any]]:
    """Hit the Discovery API and return its 'records' list."""
    params = {"query": query,
              "digitised": "true",
              "pageSize": str(page_size)}
    r = session.get(API_URL, params=params, timeout=10)
    r.raise_for_status()
    return r.json().get("records", [])


def pick_online_record(max_attempts: int = 20) -> Dict[str, Any]:
    """Loop until we find a record that resolves to an online webpage."""
    for _ in range(max_attempts):
        q = random_word()
        records = fetch_records(q)
        random.shuffle(records)
        for rec in records:
            rec_id: str | None = rec.get("id")
            if not rec_id:
                continue
            url = VIEW_URL_FMT.format(record_id=rec_id)
            try:
                session.head(url, timeout=5).raise_for_status()
                rec["view_url"] = url
                return rec
            except requests.RequestException:
                continue
    raise RuntimeError("No online record found in allotted attempts.")


def print_record(rec: Dict[str, Any]) -> None:
    print("\n— Lucky dip result —")
    print(f"Title      : {rec.get('title')}")
    print(f"Held by    : {', '.join(rec.get('heldBy', [])) or 'Unknown'}")
    if desc := rec.get("description"):
        print(f"Description: {desc}")
    print(f"Open       : {rec['view_url']}\n")


def cli() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s: %(message)s")
    print("🎲  National Archives lucky dip – digitised records\n")
    while True:
        try:
            record = pick_online_record()
            print_record(record)
        except Exception as exc:
            logging.error(exc)
            sys.exit(1)

        if input("Press ⏎ to roll again, or q + ⏎ to quit: ").strip().lower() == "q":
            break


if __name__ == "__main__":
    cli()
