# Wasabi Pipeline

Pulls daily OHLCV from Tiingo for the tickers in `tickers.txt` and publishes
`data/master_prices.csv` via GitHub Pages. The True Wasabi Screener fetches
this CSV when you click Refresh.

## One-time setup

### 1. Tiingo account
- Sign up at [tiingo.com](https://www.tiingo.com)
- Subscribe to the paid plan (around $10/month) — the free 50/hour cap is too tight
- Copy your API token from your account settings

### 2. GitHub repo
- Create a new **private** repository named `wasabi-data` (or whatever you prefer)
- Upload these files preserving the folder structure:
  ```
  /tickers.txt
  /fetch_prices.py
  /README.md
  /.github/workflows/fetch_prices.yml
  ```

### 3. Add your API key as a secret
- Repo → Settings → Secrets and variables → Actions → New repository secret
- Name: `TIINGO_API_KEY`
- Value: paste your Tiingo token
- Save

### 4. Enable GitHub Pages
- Repo → Settings → Pages
- Source: "Deploy from a branch"
- Branch: `main`, folder: `/ (root)`
- Save
- Note the URL — usually `https://<your-username>.github.io/wasabi-data/`
- The CSV will be served at: `https://<your-username>.github.io/wasabi-data/data/master_prices.csv`

  **Important:** GitHub Pages on a private repo requires either:
  - A GitHub Pro/Team/Enterprise account (private Pages supported), OR
  - You make the repo public — fine for ticker lists, your API key stays in Secrets

### 5. Run the workflow once manually to confirm it works
- Repo → Actions → "Daily Price Refresh" → Run workflow
- Watch the run for ~2 minutes. It should turn green.
- Refresh the data folder — `master_prices.csv` should now exist.

### 6. Wire the screener
- Open `True_Wasabi_Screener.html` in a text editor
- Find the line near the top: `const PRICE_URL = '...'`
- Paste your GitHub Pages CSV URL there
- Save. From now on, the Refresh button pulls fresh data automatically.

## Daily operation

The workflow runs at **6:00 PM ET weekdays** automatically. No action needed.

To trigger a refresh manually: Repo → Actions → "Daily Price Refresh" → Run workflow.

## Editing the ticker list

Open `tickers.txt` directly in GitHub. Add or remove symbols. Commit. The
next nightly run uses the new list. No code changes needed.

Lines starting with `#` are comments. Blank lines ignored. Use Tiingo's
symbol format (BRK-B not BRK.B or BRK/B).

## Troubleshooting

**Workflow fails with "failure rate exceeds 10%"**
A bunch of tickers couldn't be fetched. Check `data/last_run.log` to see
which ones. Usually one of these:
- Typo in `tickers.txt`
- Ticker was delisted (Tiingo returns 404)
- Tiingo had a brief outage — re-run manually

**Workflow runs but Refresh button in screener doesn't work**
Check that the URL in the screener matches your GitHub Pages URL exactly.
Browser console (F12) will show CORS or 404 errors if the URL is wrong.

**CSV is stale but workflow succeeded**
GitHub Pages takes a few minutes to publish updates. Wait 5 minutes.
