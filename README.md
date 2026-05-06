#  Reddit Scraper

A small, credential-free Reddit scraper that searches the public JSON
endpoints for the operator-supplied query and renders progress as a
**sectioned, color-coded** terminal log while mirroring everything to a
plain-text log file and persisting results as JSONL + Markdown.

The default query is the one this project was created for:

> **Zayns server paper leak discord**

The project layout follows
[OpenSpec](https://github.com/Fission-AI/OpenSpec) — proposal,
design, specs, and tasks for the work live under
[`openspec/changes/reddit-izayns-scraper/`](openspec/changes/reddit-izayns-scraper/).

## Install

Requires **Python 3.11+** (tested on 3.13).

```powershell
python -m pip install -r requirements.txt
```

## Run

Default run (uses the canonical query):

```powershell
python scraper.py
```

Common overrides:

```powershell
# Different query, narrow subreddit set
python scraper.py --query "some other discord leak" `
                  --subreddits Discordapp,OutOfTheLoop

# Be even gentler on Reddit (3s between requests)
python scraper.py --delay 3

# Skip the comment-fetch phase for a fast first pass
python scraper.py --no-comments
```

All flags:

| Flag              | Default                                           | Description                                           |
| ----------------- | ------------------------------------------------- | ----------------------------------------------------- |
| `--query`         | `Zayns server paper leak discord`                     | Reddit search query.                                  |
| `--subreddits`    | `Olevels,igcse,IGCSE_helps,Alevel,Alevels,CIE,edexcel,GCSE,6thForm,Discordapp,OutOfTheLoop,SubredditDrama,Cheatingclassmates,GetStudying,studytips,college,university,cybersecurity,AskNetsec` | Subs searched in addition to `r/all`. |
| `--max-pages`     | `5`                                               | Max pagination per search.                            |
| `--delay`         | `1.5`                                             | Seconds between HTTP requests.                        |
| `--limit`         | `100`                                             | Posts per page (Reddit cap is 100).                   |
| `--comment-limit` | `50`                                              | Max top-level comments captured per post.             |
| `--output-dir`    | `output`                                          | Where the JSONL + Markdown reports land.              |
| `--log-dir`       | `logs`                                            | Where the colorless log mirror is written.            |
| `--no-comments`   | off                                               | Skip the FETCH-COMMENTS phase entirely.               |

## Output

Every run produces three files, all tagged with the same UTC stamp
(`YYYYMMDDTHHMMSSZ`) so concurrent runs never collide:

```
output/zayns-<stamp>.jsonl   # one JSON object per matched post
output/zayns-<stamp>.md      # human-readable report grouped by subreddit
logs/scraper-<stamp>.log      # colorless terminal mirror, utf-8
```

The JSONL record schema is fixed in
[`openspec/changes/reddit-izayns-scraper/specs/result-persistence/spec.md`](openspec/changes/reddit-izayns-scraper/specs/result-persistence/spec.md):

```jsonc
{
  "id": "abc123",
  "subreddit": "Discordapp",
  "title": "...",
  "author": "u/someone",
  "score": 42,
  "num_comments": 17,
  "created_utc": 1714809600.0,
  "created_iso": "2026-05-04T08:00:00+00:00",
  "permalink": "https://www.reddit.com/r/Discordapp/comments/abc123/...",
  "url": "https://...",
  "selftext": "...",
  "over_18": false,
  "sources": ["all/relevance", "Discordapp/relevance"],
  "comments": [{"author": "...", "body": "...", "score": 3, ... }]
}
```

## Logging — what to expect on the terminal

Phases are wrapped in `══`-titled rules and each event class has a
dedicated color + leading icon, so a live viewer can scroll back and
land on the boundary instantly:

| Event        | Color           | Icon |
| ------------ | --------------- | ---- |
| Banner       | bold magenta    | ▌▐   |
| Section      | bold cyan       | `══` |
| Config       | dim white       | `⚙`  |
| Phase        | bold blue       | `▶`  |
| Request      | dim cyan        | `→`  |
| Response OK  | green           | `✓`  |
| Hit row      | bright yellow   | `★`  |
| Warning      | bold yellow     | `⚠`  |
| Error        | bold red        | `✖`  |
| Retry        | yellow italic   | `↻`  |
| Summary      | bold green      | `Σ`  |

Hits inside a phase are buffered and rendered as a single
`rich.table.Table`, so multiple results line up vertically and stay
scannable. The closing `Σ SUMMARY` panel reports requests, retries,
warnings, errors, unique posts, comments captured, and the three
output paths.

## OpenSpec workflow

This project was scaffolded with `openspec init` and a single change
proposal `reddit-izayns-scraper`:

```powershell
openspec status --change reddit-izayns-scraper
openspec validate reddit-izayns-scraper
openspec show reddit-izayns-scraper
```

Once you've finished iterating, archive the change to bake the specs
into `openspec/specs/`:

```powershell
openspec archive reddit-izayns-scraper
```

## Politeness & legal note

This scraper hits **public** Reddit endpoints with a descriptive
`User-Agent`, a default 1.5 s gap between requests, and exponential
back-off on 429/5xx — well within Reddit's published rate limits for
unauthenticated traffic. It does not authenticate, write, or touch
Discord. Use responsibly.
