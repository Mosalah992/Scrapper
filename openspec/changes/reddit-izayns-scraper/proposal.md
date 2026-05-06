## Why

We need a focused intelligence-gathering tool that searches Reddit for any news, discussion, or leaks tied to the query **"Zayns server paper leak discord"** — a study/exam paper that was distributed through a "Zayn" / "Zayns" Discord server. Reddit is one of the highest-signal places where students, classmates, and onlookers repost, summarize, and discuss exam leaks. A scraper purpose-built for this query gives us a reproducible audit trail that a manual browser session cannot.

Operators running this scraper are often watching the terminal live, so the second goal is **legibility**: extensive, sectioned, color-coded logs so the run reads more like a dashboard than a dump.

## What Changes

- New Python CLI `scraper.py` that searches Reddit for the query "Izayns server paper discord" using Reddit's public JSON endpoints (no API key required).
- Searches both global Reddit and a configurable list of likely subreddits (`r/all`, `r/Discordapp`, `r/discordleaks`, `r/OutOfTheLoop`, etc.) and follows the comment trees of every hit.
- Persists results as JSONL (machine-readable) and Markdown (human-readable) under `output/`, plus a plain-text colorless log under `logs/`.
- Implements a `rich`-powered logging layer with **clearly sectioned, color-coded** phases — banner, configuration, network, results, summary — so a live viewer can instantly spot warnings, hits, and errors.
- Adds polite scraping behavior: a real `User-Agent`, configurable rate-limit delay, exponential back-off on 429/5xx, and de-duplication by post id.

## Capabilities

### New Capabilities
- `reddit-search`: Query Reddit's public JSON endpoints for posts and comments matching a given search term, across `r/all` and a curated subreddit list, with pagination and de-duplication.
- `result-persistence`: Write normalized hits to JSONL and Markdown report files under `output/`, including title, subreddit, author, score, permalink, created date, and snippet.
- `sectioned-logging`: A reusable `rich`-based logger that renders banner, configuration, phase, network, hit, warning, error, and summary events with consistent colors, icons, and panel layouts both to the terminal and to a colorless rotating log file.

### Modified Capabilities
<!-- None — this is a greenfield project. -->

## Impact

- **New code**: `scraper.py`, `reddit_scraper/` package (`__init__.py`, `client.py`, `parser.py`, `persistence.py`, `logger.py`, `config.py`), `requirements.txt`, `README.md`.
- **New runtime dependencies**: `requests`, `rich`. Both pure-Python and already validated to install on the local Python 3.13 interpreter.
- **New artifacts at runtime**: `output/*.jsonl`, `output/*.md`, `logs/scraper-*.log`.
- **External systems**: read-only HTTP traffic to `https://www.reddit.com/`. No authentication, no writes, no Discord API contact.
