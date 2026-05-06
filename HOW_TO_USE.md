# How to use the Zayns Reddit scraper

`cli.py` is the single entry point for everything in this repo. The
underlying scripts (`scraper.py`, `extract_discord_urls.py`) still work
exactly as before — the CLI just gives you one place to dispatch from
and adds a few utility commands on top.

If you only ever remember one command, make it this:

```powershell
python cli.py all
```

That runs a default scrape and immediately aggregates every Discord URL
it found into [`output/DISCORD_URLS.md`](output/DISCORD_URLS.md). All
defaults are tuned for the project's canonical query — *Zayns server
paper leak discord*.

---

## 1. Install

Requires **Python 3.11+** (tested on 3.13). From the project root:

```powershell
python -m pip install -r requirements.txt
```

Two third-party dependencies: `requests` (HTTP) and `rich` (the colored
terminal UI).

---

## 2. The CLI at a glance

```powershell
python cli.py            # prints the command list
python cli.py --help     # same thing
```

| Command   | What it does                                                                                         |
| --------- | ---------------------------------------------------------------------------------------------------- |
| `scrape`  | Run the Reddit scraper. Forwards every flag straight through to [`scraper.py`](scraper.py).          |
| `extract` | Re-run the Discord-URL aggregator over whatever JSONL files are already in `output/`.                |
| `all`     | `scrape` then `extract`, in one shot. Use this 99% of the time.                                      |
| `runs`    | List every persisted scrape run (newest first) with its JSONL/MD/log presence.                       |
| `latest`  | Print the most recent run's JSONL, Markdown, and log paths — handy in shell pipelines.               |
| `clean`   | Delete generated artifacts (per-run JSONL/MD + log files). Curated reports survive unless `--force`. |
| `version` | Print the package version.                                                                           |

Subcommand help is always one flag away:

```powershell
python cli.py scrape --help
python cli.py clean --help
```

---

## 3. Common workflows

### 3.1 Default run (recommended)

```powershell
python cli.py all
```

This is equivalent to running the Reddit scraper with its bundled
defaults and then post-processing the JSONL into the consolidated
Discord-URL report. You'll see:

1. A colored, sectioned terminal log (mirrored to `logs/scraper-<stamp>.log`).
2. A new `output/zayns-<stamp>.jsonl` and `output/zayns-<stamp>.md` pair.
3. An updated `output/DISCORD_URLS.md` covering **every** prior run plus
   the one you just did.

### 3.2 Custom query

```powershell
python cli.py scrape --query "different topic to investigate"
python cli.py extract           # refresh the aggregated URL log
```

You can pass any flag the underlying `scraper.py` accepts after
`scrape`. For example, to widen the subreddit list and lower the rate:

```powershell
python cli.py scrape `
  --query "exam paper leak telegram" `
  --subreddits Olevels,igcse,Alevel,Cheatingclassmates,GetStudying `
  --delay 3 `
  --max-pages 8
```

### 3.3 Fast first pass (no comments)

Comment fetching is the slowest phase. To get a quick triage report:

```powershell
python cli.py scrape --no-comments
```

Note that *invite links usually live in comments*, so if you're hunting
Discord URLs you'll want comments enabled before running `extract`.

### 3.4 Subreddit-only sweep (skip r/all)

```powershell
python cli.py scrape --no-all --subreddits Olevels,igcse,IGCSE_helps
```

### 3.5 Inspect prior runs

```powershell
python cli.py runs
python cli.py latest
```

`runs` prints a table of every run stamp it can find, marking which
artifacts (jsonl / md / log) survived. `latest` prints the newest run's
absolute paths, one per line — easy to feed into other tools:

```powershell
$paths = (python cli.py latest)
```

### 3.6 Re-aggregate Discord URLs without scraping

If you've manually added or deleted JSONL files in `output/` (e.g.
copied a run from another machine), refresh the consolidated log:

```powershell
python cli.py extract
```

### 3.7 Clean up

`clean` prompts before deleting. Generated per-run files only — your
hand-curated reports (`DISCORD_URLS.md`, `FINDINGS.md`) survive by
default.

```powershell
python cli.py clean              # interactive
python cli.py clean --yes        # non-interactive
python cli.py clean --yes --force # also wipe DISCORD_URLS.md / FINDINGS.md
```

---

## 4. Where the output lands

Every scrape run produces three files, all sharing the same UTC
timestamp `YYYYMMDDTHHMMSSZ`:

```
output/zayns-<stamp>.jsonl   # one JSON object per matched post
output/zayns-<stamp>.md      # human-readable report grouped by subreddit
logs/scraper-<stamp>.log     # colorless terminal mirror
```

The Discord-URL aggregator writes a single rolling file:

```
output/DISCORD_URLS.md       # all Discord-shaped URLs across all runs
```

`output/FINDINGS.md` is a human-curated brief — the CLI never touches
it unless you pass `clean --force`.

The JSONL record schema is documented in
[`README.md`](README.md#output) and pinned by the OpenSpec change
[`openspec/changes/reddit-izayns-scraper/specs/result-persistence/spec.md`](openspec/changes/reddit-izayns-scraper/specs/result-persistence/spec.md).

---

## 5. Reading the terminal output

Phases are wrapped in `══`-titled rules and each event class has a
dedicated color + leading icon, so you can scroll back and land on the
boundary instantly:

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

Hits in a phase are buffered and rendered as a single table so multiple
results stay vertically aligned. The closing `Σ SUMMARY` panel reports
total requests, retries, warnings, errors, unique posts captured,
comments captured, and the three output paths.

---

## 6. Exit codes

| Code | Meaning                                             |
| ---- | --------------------------------------------------- |
| `0`  | Success.                                            |
| `1`  | Unhandled exception inside a phase.                 |
| `2`  | Bad CLI usage (unknown command, bad flag, etc.).    |
| `130`| Cancelled with Ctrl-C.                              |

`cli.py all` short-circuits if `scrape` returns non-zero — the extract
step won't run on a failed scrape.

---

## 7. Politeness & legal note

The scraper hits **public** Reddit endpoints with a descriptive
`User-Agent`, a 1.5 s default gap between requests, and exponential
back-off on 429/5xx responses. It does not authenticate, write, or
touch Discord at all — every Discord URL in `DISCORD_URLS.md` was
already published in plaintext on Reddit.

If you raise the request rate (`--delay 0.5` or similar), you take on
responsibility for staying inside Reddit's published rate limits.

---

## 8. Troubleshooting

**"no JSONL files found" when running `extract`**
You haven't done a scrape yet, or your `output/` directory was wiped.
Run `python cli.py scrape` (or `all`).

**Empty results / "no matching posts"**
Reddit's relevance ranking on long phrasal queries is noisy. The
scraper already tries a phrase variant, head-token combos, and a
broad single-word fallback — but a query with *no unique head token*
(e.g. all stop-words) won't expand. Pick one distinctive term.

**429 / rate-limit warnings in the log**
Increase `--delay`. The default 1.5 s is conservative but a saturated
home network or a previously-hammered IP can still trip the limiter.

**Garbled box-drawing characters on Windows console**
The `rich` library renders fine in modern Windows Terminal and
PowerShell 7+. On legacy `cmd.exe` you may see `?` boxes — switch
terminals; the underlying log file is plain UTF-8 and unaffected.

---

## 9. Going deeper

- [`README.md`](README.md) — quick overview and the JSONL record schema.
- [`scraper.py`](scraper.py) — the underlying CLI; every flag is documented.
- [`reddit_scraper/`](reddit_scraper/) — the package: client, parser,
  logger, persistence, config.
- [`openspec/changes/reddit-izayns-scraper/`](openspec/changes/reddit-izayns-scraper/) —
  the OpenSpec proposal, design notes, specs, and tasks.
