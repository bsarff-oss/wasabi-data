#!/usr/bin/env python3
"""
fetch_prices.py — pulls daily OHLCV from Tiingo for the ticker list in tickers.txt
and writes data/master_prices.csv in the schema the Wasabi Screener expects.

Run locally:
    export TIINGO_API_KEY="your_key_here"
    python fetch_prices.py

In GitHub Actions, TIINGO_API_KEY is provided as a repo secret.

Output schema (per the Wasabi Screener):
    Date,Ticker,Open,High,Low,Close,Volume

Pulls last ~3 years of history per ticker. That covers all moving averages
(50/150/250) plus a buffer for P&F. Larger history would slow the workflow
without changing the screener's output.
"""

import csv
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

API_BASE = "https://api.tiingo.com/tiingo/daily"
HISTORY_DAYS = 1100  # ~3 trading years + buffer
RATE_LIMIT_DELAY = 0.05  # seconds between requests; paid tier handles this easily
MAX_RETRIES = 3
TIMEOUT = 30  # per-request timeout in seconds

ROOT = Path(__file__).resolve().parent
TICKER_FILE = ROOT / "tickers.txt"
OUTPUT_FILE = ROOT / "data" / "master_prices.csv"
LOG_FILE = ROOT / "data" / "last_run.log"


def load_tickers():
    """Read tickers.txt — one symbol per line, # comments stripped, blanks ignored."""
    if not TICKER_FILE.exists():
        sys.exit(f"ERROR: {TICKER_FILE} not found")
    tickers = []
    seen = set()
    for line in TICKER_FILE.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        line = line.upper()
        if line in seen:
            continue  # dedupe silently
        seen.add(line)
        tickers.append(line)
    return tickers


def fetch_one(ticker, token, start_date):
    """Fetch a single ticker. Returns list of dicts or empty list on failure."""
    url = f"{API_BASE}/{ticker}/prices"
    headers = {"Content-Type": "application/json", "Authorization": f"Token {token}"}
    params = {"startDate": start_date, "format": "json"}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                # Ticker not found in Tiingo's universe — common for delisted or weird symbols
                return None
            if r.status_code == 429:
                # Rate limit — back off
                time.sleep(2 ** attempt)
                continue
            # Other HTTP errors
            print(f"  {ticker}: HTTP {r.status_code} — {r.text[:100]}")
            return []
        except requests.exceptions.RequestException as e:
            print(f"  {ticker}: network error attempt {attempt} — {e}")
            if attempt == MAX_RETRIES:
                return []
            time.sleep(2 ** attempt)
    return []


def main():
    token = os.environ.get("TIINGO_API_KEY", "").strip()
    if not token:
        sys.exit("ERROR: TIINGO_API_KEY environment variable is not set")

    tickers = load_tickers()
    start_date = (datetime.utcnow() - timedelta(days=HISTORY_DAYS)).strftime("%Y-%m-%d")
    print(f"Fetching {len(tickers)} tickers from Tiingo, history from {start_date}")
    print("=" * 60)

    rows = []  # list of (Date, Ticker, Open, High, Low, Close, Volume)
    succeeded = []
    failed = []
    not_found = []
    started = time.time()

    for i, ticker in enumerate(tickers, 1):
        # Tiingo uses - for share classes (BRK-B); strip just in case input had slashes
        clean = ticker.replace("/", "-").replace(".", "-")
        bars = fetch_one(clean, token, start_date)

        if bars is None:
            not_found.append(ticker)
            print(f"  [{i:>3}/{len(tickers)}] {ticker:<8}  NOT FOUND")
        elif not bars:
            failed.append(ticker)
            print(f"  [{i:>3}/{len(tickers)}] {ticker:<8}  FAILED")
        else:
            for b in bars:
                # adjusted prices (handles splits and dividends consistently across history)
                rows.append((
                    b["date"][:10],
                    ticker,
                    b.get("adjOpen") or b.get("open"),
                    b.get("adjHigh") or b.get("high"),
                    b.get("adjLow") or b.get("low"),
                    b.get("adjClose") or b.get("close"),
                    b.get("adjVolume") or b.get("volume") or 0,
                ))
            succeeded.append(ticker)
            if i % 25 == 0:
                elapsed = time.time() - started
                rate = i / elapsed
                eta = (len(tickers) - i) / rate
                print(f"  [{i:>3}/{len(tickers)}] {rate:.1f} req/s, ETA {eta:.0f}s")

        time.sleep(RATE_LIMIT_DELAY)

    # Sort rows by date then ticker for clean output
    rows.sort(key=lambda r: (r[0], r[1]))

    # Write the CSV
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"])
        w.writerows(rows)

    # Write a run log
    elapsed = time.time() - started
    latest_date = max((r[0] for r in rows), default="—")
    log_lines = [
        f"Run finished {datetime.utcnow().isoformat()}Z",
        f"Elapsed: {elapsed:.1f}s",
        f"Tickers requested: {len(tickers)}",
        f"Succeeded: {len(succeeded)}",
        f"Not found: {len(not_found)} {not_found if not_found else ''}",
        f"Failed: {len(failed)} {failed if failed else ''}",
        f"Total bars: {len(rows)}",
        f"Latest date in data: {latest_date}",
        f"CSV size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB",
    ]
    log_text = "\n".join(log_lines)
    LOG_FILE.write_text(log_text + "\n")
    print()
    print(log_text)

    # Exit non-zero if too many tickers failed (alerts the workflow)
    failure_rate = (len(failed) + len(not_found)) / len(tickers)
    if failure_rate > 0.1:
        sys.exit(f"ERROR: failure rate {failure_rate:.0%} exceeds 10% threshold")


if __name__ == "__main__":
    main()
