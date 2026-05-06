## 1. Project scaffolding

- [ ] 1.1 Create `requirements.txt` listing `requests` and `rich`
- [ ] 1.2 Create the `reddit_scraper/` package with an empty `__init__.py`
- [ ] 1.3 Create empty `output/` and `logs/` directories with `.gitkeep`
- [ ] 1.4 Write a `README.md` covering install, usage, CLI flags, and output layout

## 2. Sectioned colored logger (`reddit_scraper/logger.py`)

- [ ] 2.1 Build a `Logger` class wrapping `rich.console.Console` and a stdlib `logging.FileHandler`
- [ ] 2.2 Implement the public methods `banner`, `section`, `config`, `phase`, `request`, `response`, `hit`, `warn`, `error`, `retry`, `summary`
- [ ] 2.3 Apply the fixed color/icon vocabulary documented in `specs/sectioned-logging/spec.md`
- [ ] 2.4 Mirror every event to the file log without ANSI codes, in `utf-8`
- [ ] 2.5 Render the startup banner as a framed `rich.panel.Panel`
- [ ] 2.6 Render hits as rows of a single `rich.table.Table` per phase
- [ ] 2.7 Render the final summary as a green-bordered panel with a 2-column table

## 3. Reddit client (`reddit_scraper/client.py`)

- [ ] 3.1 Build a `RedditClient` class around `requests.Session`
- [ ] 3.2 Set the custom `User-Agent` header on the session
- [ ] 3.3 Implement `search(query, subreddit=None, sort='relevance', limit=100)` that paginates via `after`
- [ ] 3.4 Implement `comments(post_id, limit=50)` returning the top-level comment list
- [ ] 3.5 Wrap every HTTP call in a retry helper with 3 attempts and 1/2/4-second exponential back-off on 429/5xx and `RequestException`
- [ ] 3.6 Sleep `--delay` seconds between requests using `time.sleep`
- [ ] 3.7 Push every request/response/retry event into the `Logger`

## 4. Parsing & de-duplication (`reddit_scraper/parser.py`)

- [ ] 4.1 Implement `normalize_post(raw)` returning the JSONL record schema from `specs/result-persistence/spec.md`
- [ ] 4.2 Implement `normalize_comment(raw)` for the comment sub-records
- [ ] 4.3 Implement an `add_hit(record, source)` helper on a `ResultSet` class that appends to `sources` if the id already exists, otherwise inserts a new record
- [ ] 4.4 Convert `created_utc` to ISO-8601 `created_iso` for human readability
- [ ] 4.5 Use `.get()` on every Reddit field and default missing values to `None`

## 5. Persistence (`reddit_scraper/persistence.py`)

- [ ] 5.1 Implement `write_jsonl(path, records)` with utf-8 encoding and a trailing newline per record
- [ ] 5.2 Implement `write_markdown(path, query, started_at, records)` grouped by subreddit
- [ ] 5.3 Generate the UTC `YYYYMMDDTHHMMSSZ` stamp once per run and reuse it for all paths
- [ ] 5.4 Truncate `selftext` to 500 chars in the Markdown report and include the first 5 top-level comments

## 6. CLI entry point (`scraper.py`)

- [ ] 6.1 Build an `argparse` CLI accepting `--query`, `--subreddits`, `--max-pages`, `--delay`, `--limit`, `--output-dir`, `--log-dir`
- [ ] 6.2 Default `--query` to `"Izayns server paper discord"`
- [ ] 6.3 Default `--subreddits` to `Discordapp,discordleaks,OutOfTheLoop,DiscordServers,DiscordDrama`
- [ ] 6.4 In `main()`: render banner, render config panel, then call SEARCH phase, FETCH-COMMENTS phase, PERSIST phase, SUMMARY phase in order
- [ ] 6.5 In SEARCH: search `r/all` (relevance + new), then each allowlisted subreddit, accumulating into a `ResultSet`
- [ ] 6.6 In FETCH-COMMENTS: walk the `ResultSet` and call `client.comments(post_id)` for each unique post
- [ ] 6.7 In PERSIST: write the JSONL file then the Markdown file
- [ ] 6.8 In SUMMARY: render the summary panel and exit 0

## 7. Run & verify

- [ ] 7.1 Run `python scraper.py` once with the default query
- [ ] 7.2 Confirm the JSONL and Markdown files are created under `output/`
- [ ] 7.3 Confirm a `.log` mirror is created under `logs/` and contains no ANSI codes
- [ ] 7.4 Confirm the terminal shows banner, sectioned phases, hit rows, and a final SUMMARY panel

## 8. 2026-05-05 focused academic searches

- [x] 8.1 Write `extract_discord_urls.py` to scan all JSONL files for Discord invite links
- [x] 8.2 Run query `Zayn server` on focused academic subs
- [x] 8.3 Run query `Paradise papers IGCSE` on focused academic subs
- [x] 8.4 Run query `prodigy IGCSE bio leak` on focused academic subs
- [x] 8.5 Run query `Olevels paper leak discord` on focused academic subs
- [x] 8.6 Run `extract_discord_urls.py` over all JSONL files and write `output/DISCORD_URLS.md`
