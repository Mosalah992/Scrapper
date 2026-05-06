"""Write JSONL + Markdown reports under ``output/``.

Filenames embed a UTC ``YYYYMMDDTHHMMSSZ`` stamp so two runs in the
same minute never overwrite each other.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Iterable

from .config import FILENAME_PREFIX


# --- JSONL ------------------------------------------------------------------

def write_jsonl(path: str, records: Iterable[dict]) -> int:
    """Write one JSON object per line; return the number of records written."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    count = 0
    with open(path, "w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False))
            fh.write("\n")
            count += 1
    return count


# --- Markdown ---------------------------------------------------------------

_SNIPPET_LIMIT = 500
_TOP_COMMENTS_IN_REPORT = 5


def _truncate(text: str | None, limit: int = _SNIPPET_LIMIT) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " …"


def _md_escape(text: str | None) -> str:
    """Minimal Markdown defanging so titles with `*` or `_` don't blow up
    the layout. Not security — just readability."""
    if not text:
        return ""
    return (
        text.replace("\\", "\\\\")
        .replace("*", "\\*")
        .replace("_", "\\_")
        .replace("`", "\\`")
    )


def write_markdown(
    path: str,
    *,
    query: str,
    started_iso: str,
    records: list[dict],
) -> None:
    """Render a grouped, human-readable report."""
    # NB: section title and brand are query-driven, not hard-coded.
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        grouped[r.get("subreddit") or "?"].append(r)
    # Stable subreddit ordering, but put richest groups first.
    sorted_subs = sorted(
        grouped.keys(),
        key=lambda s: (-len(grouped[s]), s.lower()),
    )

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"# Zayns Reddit Scrape — `{query}`\n\n")
        fh.write(f"_run started: {started_iso}_\n\n")
        fh.write(f"_total unique posts: **{len(records)}**_\n\n")

        if not records:
            fh.write(
                "> No matching posts were returned by Reddit's public JSON "
                "endpoints for this query at this time.\n"
            )
            return

        fh.write("## Index\n\n")
        for sub in sorted_subs:
            fh.write(f"- [r/{sub}](#r{sub.lower()}) — {len(grouped[sub])} post(s)\n")
        fh.write("\n---\n\n")

        for sub in sorted_subs:
            fh.write(f"## r/{sub}\n\n")
            for record in grouped[sub]:
                title = _md_escape(record.get("title") or "(untitled)")
                permalink = record.get("permalink") or record.get("url") or "#"
                author = record.get("author") or "?"
                score = record.get("score")
                created_iso = record.get("created_iso") or "?"
                num_comments = record.get("num_comments")
                sources = ", ".join(record.get("sources") or []) or "?"

                fh.write(f"### [{title}]({permalink})\n\n")
                fh.write(
                    f"- **author**: u/{author}  \n"
                    f"- **score**: {score}  \n"
                    f"- **comments**: {num_comments}  \n"
                    f"- **created**: {created_iso}  \n"
                    f"- **sources**: {sources}  \n"
                )
                if record.get("over_18"):
                    fh.write("- **NSFW**: yes  \n")
                fh.write("\n")

                snippet = _truncate(record.get("selftext"))
                if snippet:
                    fh.write("> " + snippet.replace("\n", "\n> ") + "\n\n")

                comments = record.get("comments") or []
                if comments:
                    fh.write("**Top comments:**\n\n")
                    for c in comments[:_TOP_COMMENTS_IN_REPORT]:
                        c_author = c.get("author") or "?"
                        c_score = c.get("score")
                        body = _truncate(c.get("body"), 350)
                        if not body:
                            continue
                        fh.write(
                            f"- _u/{c_author}_ ({c_score}): "
                            f"{body.replace(chr(10), ' ')}\n"
                        )
                    fh.write("\n")
                fh.write("\n")


# --- Path helpers -----------------------------------------------------------

def jsonl_path(output_dir: str, run_stamp: str) -> str:
    return os.path.join(output_dir, f"{FILENAME_PREFIX}-{run_stamp}.jsonl")


def markdown_path(output_dir: str, run_stamp: str) -> str:
    return os.path.join(output_dir, f"{FILENAME_PREFIX}-{run_stamp}.md")
