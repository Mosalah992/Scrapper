## ADDED Requirements

### Requirement: Persist normalized hits as JSONL
The scraper SHALL write one JSON object per line to `output/izayns-<utc-stamp>.jsonl` for every unique post returned by the search.

#### Scenario: JSONL record schema
- **WHEN** a post is persisted
- **THEN** the record contains the keys `id`, `subreddit`, `title`, `author`, `score`, `num_comments`, `created_utc`, `created_iso`, `permalink`, `url`, `selftext`, `over_18`, `sources`, and `comments`
- **AND** each `comments` entry contains `author`, `body`, `score`, `created_utc`, `created_iso`
- **AND** missing upstream fields are written as JSON `null`, never causing an exception
- **AND** the file is written with `utf-8` encoding and a trailing newline after each record

#### Scenario: No hits returned
- **WHEN** the scraper finishes a run with zero unique posts
- **THEN** the JSONL file is still created but is empty (zero bytes after the header line, if any)
- **AND** the run exits with status code 0

### Requirement: Render a human-readable Markdown report
The scraper SHALL also write `output/izayns-<utc-stamp>.md` containing a grouped, readable summary of the same hits.

#### Scenario: Markdown report layout
- **WHEN** the scraper persists results
- **THEN** the Markdown file begins with a top-level heading containing the query and the run timestamp
- **AND** posts are grouped by subreddit under `## r/<subreddit>` sections
- **AND** each post is rendered as a sub-section with title, permalink, author, score, created date, a snippet of `selftext` (truncated to 500 chars), and the first 5 top-level comments

### Requirement: Stamp filenames with a sortable UTC timestamp
The scraper SHALL embed a `YYYYMMDDTHHMMSSZ` UTC timestamp in every output and log filename so concurrent runs never overwrite each other.

#### Scenario: Two runs in the same minute
- **WHEN** the scraper is launched twice within 60 seconds
- **THEN** the second run's filenames differ from the first by at least the seconds component
- **AND** neither run truncates or appends to the other's files

### Requirement: Mirror terminal output to a colorless log file
The scraper SHALL also write the full event stream to `logs/scraper-<utc-stamp>.log` without ANSI color codes so the file is grep-friendly.

#### Scenario: File log content matches terminal narrative
- **WHEN** any banner, section, phase, request, hit, warning, or error event is rendered to the terminal
- **THEN** an equivalent timestamped line is written to the log file
- **AND** that line contains no ANSI escape sequences
- **AND** the file is encoded in `utf-8`
