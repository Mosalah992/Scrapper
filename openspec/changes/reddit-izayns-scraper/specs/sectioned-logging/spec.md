## ADDED Requirements

### Requirement: Provide a single Logger facade with intent-named methods
The scraper SHALL expose one `Logger` class whose public methods are named after event types — `banner`, `section`, `config`, `phase`, `request`, `response`, `hit`, `warn`, `error`, `retry`, `summary` — so call-sites describe *intent*, not formatting.

#### Scenario: Call sites are intent-driven
- **WHEN** scraper code wants to announce a new phase
- **THEN** it calls `logger.phase("SEARCH", "querying r/all")` and never constructs ANSI codes or rich markup directly
- **AND** the formatting/color choice is owned entirely by the `Logger` class

### Requirement: Render a startup banner
The scraper SHALL print a multi-line banner at the start of every run identifying the tool name, version, query, and run timestamp.

#### Scenario: Banner appears first
- **WHEN** the scraper starts
- **THEN** the first thing rendered to stdout is a bold, colored, framed banner containing the literal string `IZAYNS REDDIT SCRAPER`, the run query, and the UTC start timestamp

### Requirement: Use horizontal rules to separate sections
The scraper SHALL emit a `rich` horizontal rule between every major section so the terminal output is visually paginated.

#### Scenario: Section rules surround each phase
- **WHEN** a new phase begins (e.g. `SEARCH`, `FETCH-COMMENTS`, `PERSIST`, `SUMMARY`)
- **THEN** a labelled colored rule is rendered immediately before the first event of that phase
- **AND** another labelled rule closes the previous phase's output

### Requirement: Use a fixed color and icon vocabulary
The scraper SHALL use a fixed mapping of event class to color + leading icon so an operator who has watched one run can read another at a glance.

#### Scenario: Event styling is consistent
- **WHEN** any event is rendered
- **THEN** it follows this mapping:

| Event class | Color           | Leading icon |
|-------------|-----------------|--------------|
| banner      | bold magenta    | block frame  |
| section     | bold cyan       | `══`         |
| config      | dim white       | `⚙`          |
| phase       | bold blue       | `▶`          |
| request     | dim cyan        | `→`          |
| response-ok | green           | `✓`          |
| hit         | bright yellow   | `★`          |
| warning     | bold yellow     | `⚠`          |
| error       | bold red        | `✖`          |
| retry       | yellow italic   | `↻`          |
| summary     | bold green      | `Σ`          |

### Requirement: Render hits as a live-updating table
The scraper SHALL render each hit's identifying fields (`#`, subreddit, score, comments, title) as a row in a `rich.table.Table` so they line up vertically and remain scannable.

#### Scenario: Multiple hits in a phase
- **WHEN** more than one hit is found within a phase
- **THEN** all hits in that phase appear as rows of a single table with consistent column widths
- **AND** the table header is bold yellow with the leading icon `★`

### Requirement: Render the final summary as a panel + table
The scraper SHALL close every run with a `SUMMARY` panel containing a small table of counts (requests issued, posts found, unique posts, comments captured, warnings, errors, output paths).

#### Scenario: Summary panel after a successful run
- **WHEN** the scraper finishes a run without an unrecoverable error
- **THEN** a green-bordered panel labelled `Σ SUMMARY` is the last thing rendered
- **AND** it contains a 2-column table whose rows include `requests`, `posts found`, `unique posts`, `comments captured`, `warnings`, `errors`, `jsonl`, `markdown`, `log file`
