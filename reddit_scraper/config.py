"""Static defaults shared between the CLI and the modules.

Anything you would reasonably want to change without editing the rest
of the code lives here. Real overrides come in via the CLI flags in
``scraper.py`` so this file stays the single source of truth.
"""

from __future__ import annotations

# --- Query defaults ---------------------------------------------------------

# The exact query the operator asked for. Spaces are URL-encoded later.
# Context: this is about a *study / exam paper leak* shared through a
# Discord server called "Zayn" / "Zayns". Adding "leak" sharpens the
# query considerably.
DEFAULT_QUERY: str = "Zayns server paper leak discord"

# Subreddits where exam-paper leaks, study-group Discord drama, and
# academic-cheating discussion typically surface, plus the Discord-app
# meta subs. We always also search r/all on top of this list.
#
# O-level / IGCSE / A-level subs are at the top because that's where
# Cambridge / Edexcel / CIE paper-leak chatter actually lives — these
# communities discuss specific syllabus codes, session leaks, and the
# Discord servers that traffic them.
DEFAULT_SUBREDDITS: tuple[str, ...] = (
    # Cambridge / Edexcel / O-level / A-level — primary target
    "Olevels",
    "igcse",
    "IGCSE_helps",
    "Alevel",
    "Alevels",
    "CIE",
    "edexcel",
    "GCSE",
    "6thForm",
    # Discord-meta / drama
    "Discordapp",
    "OutOfTheLoop",
    "SubredditDrama",
    # Academic-leak / cheating / studying
    "Cheatingclassmates",
    "GetStudying",
    "studytips",
    "college",
    "university",
    # Cybersecurity / SOC angles (the project root is "SOC Diploma")
    "cybersecurity",
    "AskNetsec",
)

# Reddit's two most useful sort orders for our purpose: relevance to find
# the canonical thread, "new" to catch breaking discussion.
SEARCH_SORTS: tuple[str, ...] = ("relevance", "new")

# --- HTTP / rate-limit defaults --------------------------------------------

REDDIT_BASE_URL: str = "https://www.reddit.com"

# Reddit explicitly down-ranks generic User-Agents. A descriptive one keeps
# the anonymous quota honest.
USER_AGENT: str = (
    "zayns-reddit-scraper/0.1 "
    "(+https://github.com/Fission-AI/OpenSpec; research; contact: anonymous)"
)

# Seconds between consecutive requests. 1.5s keeps a full default run well
# under the ~60 req/min anonymous ceiling.
DEFAULT_DELAY_SECONDS: float = 1.5

# Per-search pagination cap (each "page" = up to `limit` posts).
DEFAULT_MAX_PAGES: int = 5

# Posts per page; Reddit caps this at 100.
DEFAULT_PAGE_LIMIT: int = 100

# Maximum top-level comments captured per post.
DEFAULT_COMMENT_LIMIT: int = 50

# Retry policy applied uniformly to every Reddit request.
RETRY_MAX_ATTEMPTS: int = 3
RETRY_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 2.0, 4.0)
RETRY_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# --- Filesystem layout ------------------------------------------------------

DEFAULT_OUTPUT_DIR: str = "output"
DEFAULT_LOG_DIR: str = "logs"
FILENAME_PREFIX: str = "zayns"
LOG_FILENAME_PREFIX: str = "scraper"
