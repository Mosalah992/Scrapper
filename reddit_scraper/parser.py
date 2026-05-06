"""Normalize Reddit JSON into our fixed JSONL schema and de-duplicate.

The shape we persist is documented in
``openspec/changes/reddit-izayns-scraper/specs/result-persistence/spec.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


def _iso(epoch: Optional[float]) -> Optional[str]:
    """Return UTC ISO-8601 string for a Reddit ``created_utc`` value."""
    if epoch is None:
        return None
    try:
        return datetime.fromtimestamp(float(epoch), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def normalize_post(raw: dict) -> dict:
    """Map a raw Reddit post `data` dict to our flat schema.

    Every field uses ``.get()`` so missing keys never raise — they just
    become ``None`` in the persisted record.
    """
    permalink = raw.get("permalink")
    created = raw.get("created_utc")
    return {
        "id":           raw.get("id"),
        "subreddit":    raw.get("subreddit"),
        "title":        raw.get("title"),
        "author":       raw.get("author"),
        "score":        raw.get("score"),
        "num_comments": raw.get("num_comments"),
        "created_utc":  created,
        "created_iso":  _iso(created),
        "permalink":    f"https://www.reddit.com{permalink}" if permalink else None,
        "url":          raw.get("url"),
        "selftext":     raw.get("selftext"),
        "over_18":      raw.get("over_18"),
        "sources":      [],   # populated by ResultSet.add
        "comments":     [],   # populated later by the FETCH-COMMENTS phase
    }


def normalize_comment(raw: dict) -> dict:
    """Map a raw Reddit comment `data` dict to our flat sub-schema."""
    created = raw.get("created_utc")
    return {
        "author":      raw.get("author"),
        "body":        raw.get("body"),
        "score":       raw.get("score"),
        "created_utc": created,
        "created_iso": _iso(created),
    }


@dataclass
class ResultSet:
    """De-duplicating store keyed by Reddit post id.

    Notes
    -----
    A post can be returned by several search calls (e.g. once via the
    global ``/search.json`` and once via ``/r/Discordapp/search.json``).
    We keep a single record per id and append every search that hit it
    to the record's ``sources`` list — useful when investigating which
    surface a leak first appeared on.
    """

    records: dict[str, dict] = field(default_factory=dict)

    def add(self, raw: dict, source: str) -> bool:
        """Insert or merge.

        Returns True if this is the *first* time we've seen the id
        (i.e. a brand-new hit), False if we've merely added a source
        to an existing record. The boolean lets the SEARCH phase decide
        whether to surface the hit in the live ★ table.
        """
        post_id = raw.get("id")
        if not post_id:
            return False
        if post_id in self.records:
            sources = self.records[post_id].setdefault("sources", [])
            if source not in sources:
                sources.append(source)
            return False
        record = normalize_post(raw)
        record["sources"] = [source]
        self.records[post_id] = record
        return True

    def attach_comments(self, post_id: str, comments: list[dict]) -> None:
        """Replace a record's ``comments`` list with normalized data."""
        if post_id not in self.records:
            return
        self.records[post_id]["comments"] = [
            normalize_comment(c) for c in comments
        ]

    # ----- read views ---------------------------------------------------

    def values(self) -> list[dict]:
        """Records in insertion order — handy for stable file output."""
        return list(self.records.values())

    def __len__(self) -> int:
        return len(self.records)

    def __contains__(self, post_id: object) -> bool:
        return post_id in self.records


# A helper used by callers that need a structured record for logging
# without committing it to the ResultSet (e.g. when echoing a hit row).
def hit_summary(raw: dict) -> tuple[str, int, int, str]:
    """Return ``(subreddit, score, num_comments, title)`` for the hit table."""
    return (
        str(raw.get("subreddit") or "?"),
        int(raw.get("score") or 0),
        int(raw.get("num_comments") or 0),
        str(raw.get("title") or "(untitled)"),
    )
