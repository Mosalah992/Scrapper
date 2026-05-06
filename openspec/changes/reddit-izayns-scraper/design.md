## Context

The user is investigating chatter around an "Izayns server paper" — a paper/document associated with an Izayn(s) Discord server. Reddit aggregates a large share of Discord-leak discussion (`r/Discordapp`, `r/discordleaks`, `r/OutOfTheLoop`, fandom-specific subs), so a single-purpose Reddit scraper is the most efficient first pass.

Constraints:
- Local Windows 11 machine, Python 3.13 already installed.
- No Reddit account / OAuth credentials available; must use Reddit's public unauthenticated JSON endpoints.
- Operator wants to *watch* the run live, so terminal output is a first-class deliverable, not an afterthought.

## Goals / Non-Goals

**Goals:**
- Pull every post that matches the query "Izayns server paper discord" from `/search.json` (sorted by relevance and by new), plus per-subreddit `/r/<sub>/search.json?restrict_sr=1`.
- For each hit, also fetch the comment tree (`/comments/<id>.json`) so context isn't lost.
- De-duplicate by Reddit post `id` across all sources.
- Persist normalized records to JSONL **and** a Markdown report.
- Emit a clearly **sectioned, color-coded** terminal log: banner → config → search-phase → fetch-phase → results → summary, with explicit warning/error styling.
- Mirror everything (without colors) to a rotating log file for later forensic review.

**Non-Goals:**
- No PRAW / OAuth — keeps the tool credential-free.
- No JavaScript rendering / browser automation — Reddit's JSON endpoints are sufficient.
- No Discord API calls. The scraper observes Reddit *about* a Discord topic; it does not touch Discord itself.
- No real-time streaming — a single run produces a snapshot.
- No NLP/sentiment scoring — just retrieval and presentation.

## Decisions

### D1. Use the public `*.json` endpoints over PRAW
- **Choice**: hit `https://www.reddit.com/search.json`, `/r/<sub>/search.json`, `/comments/<id>.json` directly with `requests`.
- **Why**: zero credentials, zero quota setup, identical data shape to PRAW. The cost is a hard rate ceiling (~60 req/min anonymous), which we manage with delay + back-off.
- **Alternatives**: PRAW (needs OAuth app), Pushshift (deprecated for the public), `pmaw` (depends on Pushshift).

### D2. `rich` for terminal logging, stdlib `logging` for files
- **Choice**: a single `Logger` wrapper wraps a `rich.console.Console` and a stdlib `logging.FileHandler`. The wrapper exposes intent-named methods (`banner`, `section`, `config`, `phase`, `request`, `hit`, `warn`, `error`, `summary`) so call-sites read like a script, not like log plumbing.
- **Why**: `rich` gives panels, rules, tables, and 24-bit color out of the box; pairing with stdlib logging means file output stays grep-friendly.
- **Alternatives**: `loguru` (good, but `rich` panels/tables are stronger for sectioning); `colorama`+`logging` (too low-level for the look the user asked for).

### D3. Color & section vocabulary
A small, consistent palette so each event class is visually distinct at a glance:

| Event       | Color / Style                | Marker |
|-------------|------------------------------|--------|
| Banner      | bold magenta on default      | ascii block frame |
| Section     | bold cyan rule               | `══` rule |
| Config      | dim white in panel           | ⚙ |
| Phase start | bold blue                    | ▶ |
| Request     | dim cyan                     | → |
| Response OK | green                        | ✓ |
| Hit         | bright yellow w/ table row   | ★ |
| Warning     | bold yellow                  | ⚠ |
| Error       | bold red on default          | ✖ |
| Retry       | yellow italic                | ↻ |
| Summary     | bold green panel + table     | Σ |

Each phase (`SEARCH`, `FETCH-COMMENTS`, `PERSIST`, `SUMMARY`) is wrapped in a `rich.rule.Rule` so the operator can scroll back and find the boundary instantly.

### D4. Polite client behavior
- Custom `User-Agent: izayns-reddit-scraper/0.1 (by /u/anonymous; research)`. Reddit explicitly down-ranks generic UAs.
- 1.5 s delay between requests by default (`--delay`).
- 3 retries with exponential back-off (1 s → 2 s → 4 s) on 429, 500, 502, 503, 504, and any `requests.RequestException`.
- Hard cap of 5 pages per query (configurable via `--max-pages`) to avoid runaway pagination.

### D5. Storage layout
```
output/
  izayns-<utc-stamp>.jsonl     # one JSON object per hit
  izayns-<utc-stamp>.md        # human report grouped by subreddit
logs/
  scraper-<utc-stamp>.log      # colorless mirror of terminal output
```
Stamps are `YYYYMMDDTHHMMSSZ`. The JSONL record schema is fixed in `specs/result-persistence/spec.md`.

### D6. Subreddit allowlist
Curated list with topical relevance: `all`, `Discordapp`, `discordleaks`, `OutOfTheLoop`, `DiscordServers`, `DiscordApp`, `DiscordDrama`, `Drama`. Configurable via `--subreddits` so the operator can widen or narrow the net without editing source.

## Risks / Trade-offs

- **[Rate limit]** anonymous Reddit JSON is ~60 req/min → mitigated by `--delay` and back-off; a full run with 8 subs × 2 sorts + comment fetches stays under the ceiling at default delay.
- **[Empty result set]** the query is niche; the scraper might legitimately find nothing → handled by an explicit "0 hits" summary and a non-error exit code so it composes cleanly in scripts.
- **[Reddit JSON shape drift]** Reddit occasionally changes nested keys → parser uses `.get()` everywhere and never raises on a missing field; missing fields become `null` in JSONL.
- **[Console width]** `rich` autodetects but very narrow terminals truncate the hit table → tables use `expand=True` and overflow `fold` to stay readable.
- **[Encoding]** Windows default cp1252 can mangle emoji in titles → all file writes are explicitly `encoding="utf-8"`; the file logger uses `utf-8` too.

## Migration Plan

Greenfield project — no migration. Rollback is `del scraper.py` plus the `reddit_scraper/` folder.

## Open Questions

- Should the scraper also check `old.reddit.com` archives or `i.redd.it` image posts? Out of scope for this iteration; revisit if the first run returns thin results.
- Do we want to emit a CSV in addition to JSONL/MD? Defer until a downstream consumer asks for it.
