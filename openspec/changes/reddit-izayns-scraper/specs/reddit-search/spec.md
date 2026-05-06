## ADDED Requirements

### Requirement: Query Reddit's public JSON search endpoint
The scraper SHALL issue HTTP GET requests to `https://www.reddit.com/search.json` with the operator-supplied query string and SHALL accept the response as JSON without authentication.

#### Scenario: Default query is dispatched against r/all
- **WHEN** the operator runs `python scraper.py` with no overrides
- **THEN** the scraper issues a GET to `https://www.reddit.com/search.json?q=Izayns+server+paper+discord&sort=relevance&limit=100&t=all`
- **AND** the request carries a non-default `User-Agent` header identifying the tool
- **AND** the JSON body is parsed as a Reddit `Listing` and walked for `data.children[*].data` posts

#### Scenario: Operator overrides the query at the CLI
- **WHEN** the operator runs `python scraper.py --query "different topic"`
- **THEN** the scraper URL-encodes `different topic` into the `q` parameter and uses it instead of the default

### Requirement: Search a curated subreddit allowlist
The scraper SHALL additionally search a list of topically relevant subreddits using `https://www.reddit.com/r/<sub>/search.json?restrict_sr=1` so subreddit-scoped results that `r/all` may bury are still surfaced.

#### Scenario: Default subreddit list is searched
- **WHEN** the scraper runs with no `--subreddits` flag
- **THEN** it iterates the default list (at minimum `Discordapp`, `discordleaks`, `OutOfTheLoop`, `DiscordServers`, `DiscordDrama`) and issues one search request per subreddit
- **AND** each subreddit request uses `restrict_sr=1` so off-sub results are excluded

#### Scenario: Operator narrows the subreddit list
- **WHEN** the operator passes `--subreddits Discordapp,OutOfTheLoop`
- **THEN** only those two subreddits are searched in addition to `r/all`

### Requirement: Paginate via the Reddit `after` cursor
The scraper SHALL follow the `after` field returned in each Reddit `Listing` to retrieve subsequent pages, up to a configurable maximum page count.

#### Scenario: Multiple pages are fetched
- **WHEN** a search response includes a non-null `data.after` and the page count is below `--max-pages`
- **THEN** the scraper issues a follow-up request with `&after=<token>` and merges the new posts into the result set

#### Scenario: Max pages cap is honored
- **WHEN** the scraper has fetched `--max-pages` pages for a single search
- **THEN** it stops paginating that search even if `after` is still non-null and logs a warning indicating the cap was reached

### Requirement: Fetch comment threads for every matched post
The scraper SHALL retrieve `https://www.reddit.com/comments/<id>.json` for each post returned by search and SHALL store at least the top-level comment bodies and authors with the post record.

#### Scenario: Comment fetch succeeds
- **WHEN** a post id is in the results set
- **THEN** the scraper issues GET `/comments/<id>.json`
- **AND** captures up to the first 50 top-level comments' `body`, `author`, `score`, and `created_utc` into the post record's `comments` field

#### Scenario: Comment fetch fails
- **WHEN** the comment endpoint returns a non-2xx status after retries
- **THEN** the scraper records an empty `comments` list, logs a warning, and continues with remaining posts

### Requirement: De-duplicate posts across all sources
The scraper SHALL ensure that a post returned by multiple search calls (e.g., once via `r/all` and once via a sub-scoped search) appears at most once in the persisted output.

#### Scenario: Same post hit by two searches
- **WHEN** post id `t3_abc123` is returned by both an `r/all` search and an `r/Discordapp` search
- **THEN** exactly one record with id `abc123` is written to the JSONL output
- **AND** the record's `sources` field lists every search that surfaced it

### Requirement: Apply polite rate-limiting and back-off
The scraper SHALL space requests by a configurable delay (default 1.5 seconds) and SHALL retry transient failures with exponential back-off.

#### Scenario: Default delay between requests
- **WHEN** consecutive HTTP requests are issued during a run
- **THEN** the second request begins no earlier than `--delay` seconds after the first response was received

#### Scenario: Retry on 429 / 5xx
- **WHEN** Reddit returns HTTP 429, 500, 502, 503, or 504
- **THEN** the scraper waits 1, 2, then 4 seconds before retrying, up to 3 attempts total
- **AND** logs each retry as a distinct retry event

#### Scenario: Permanent failure after retries
- **WHEN** a request still fails after the third attempt
- **THEN** the scraper logs an error for that endpoint and continues with the rest of the run rather than aborting
