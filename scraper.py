"""CLI entry point for the Zayns Reddit scraper.

Run with no arguments to scrape with the default query
(``Zayns server paper leak discord``):

    python scraper.py

Or override:

    python scraper.py --query "different topic" --subreddits all,Discordapp
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from reddit_scraper import __version__
from reddit_scraper.client import RedditClient
from reddit_scraper.config import (
    DEFAULT_COMMENT_LIMIT,
    DEFAULT_DELAY_SECONDS,
    DEFAULT_LOG_DIR,
    DEFAULT_MAX_PAGES,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PAGE_LIMIT,
    DEFAULT_QUERY,
    DEFAULT_SUBREDDITS,
    SEARCH_SORTS,
)
from reddit_scraper.logger import Logger
from reddit_scraper.parser import ResultSet, hit_summary
from reddit_scraper.persistence import (
    jsonl_path,
    markdown_path,
    write_jsonl,
    write_markdown,
)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="scraper.py",
        description="Search Reddit for the Zayns Discord paper-leak and friends.",
    )
    parser.add_argument(
        "--query", default=DEFAULT_QUERY,
        help=f"Search query (default: {DEFAULT_QUERY!r})",
    )
    parser.add_argument(
        "--subreddits",
        default=",".join(DEFAULT_SUBREDDITS),
        help=(
            "Comma-separated list of subreddits to also search "
            "(in addition to r/all)."
        ),
    )
    parser.add_argument(
        "--max-pages", type=int, default=DEFAULT_MAX_PAGES,
        help=f"Max pages per search (default: {DEFAULT_MAX_PAGES}).",
    )
    parser.add_argument(
        "--delay", type=float, default=DEFAULT_DELAY_SECONDS,
        help=f"Seconds between requests (default: {DEFAULT_DELAY_SECONDS}).",
    )
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_PAGE_LIMIT,
        help=f"Posts per page, max 100 (default: {DEFAULT_PAGE_LIMIT}).",
    )
    parser.add_argument(
        "--comment-limit", type=int, default=DEFAULT_COMMENT_LIMIT,
        help=f"Top-level comments per post (default: {DEFAULT_COMMENT_LIMIT}).",
    )
    parser.add_argument(
        "--output-dir", default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for JSONL + Markdown (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--log-dir", default=DEFAULT_LOG_DIR,
        help=f"Directory for the colorless .log mirror (default: {DEFAULT_LOG_DIR}).",
    )
    parser.add_argument(
        "--no-comments", action="store_true",
        help="Skip the FETCH-COMMENTS phase entirely (faster, lower fidelity).",
    )
    parser.add_argument(
        "--no-all", action="store_true",
        help="Skip r/all and search only the comma-separated subreddit list.",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------

def _build_variants(query: str) -> list[str]:
    """Generate progressively broader query variants.

    Reddit's search OR's whitespace-separated terms by default, which on a
    multi-word query like ``Zayns server paper leak discord`` floods us
    with unrelated noise. The client already auto-quotes multi-word inputs
    to enforce phrase matching, so we layer the search:

    * variant 0: the operator's full query (phrase-matched after auto-quote)
    * variant 1+: useful 2-term combos pairing the unique "head" token
      with each remaining content word (e.g. ``Zayns leak``,
      ``Zayns paper``, ``Zayns server``). These are quoted too, so we
      get phrase matches like the literal string "Zayns leak" rather
      than a flood of unrelated OR results.
    * variant N: the head token alone (broadest fallback).

    Stopwords (incl. ``server``, ``discord``, ``paper`` for *this* topic)
    don't qualify as the head token, but they're fine on the right-hand
    side of a 2-term combo.
    """
    head_stopwords = {
        "the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "at",
        "by", "with", "is", "are", "was", "were", "be", "been", "as",
        # These are everywhere on Reddit; they don't identify our topic.
        "server", "servers", "paper", "papers", "discord", "leak", "leaks",
        "study", "studying",
    }
    parts = [p for p in query.split() if p]
    variants: list[str] = [query.strip()]
    if len(parts) <= 1:
        return variants

    candidates = [p for p in parts if p.lower() not in head_stopwords]
    if not candidates:
        return variants

    head = max(candidates, key=len)
    # 2-term phrase combos: head + every other word in the query.
    for other in parts:
        if other == head:
            continue
        combo = f"{head} {other}"
        if combo not in variants:
            variants.append(combo)

    # Broadest single-word fallback last.
    if head not in variants:
        variants.append(head)

    return variants


def phase_search(
    *,
    logger: Logger,
    client: RedditClient,
    query: str,
    subreddits: list[str],
    max_pages: int,
    limit: int,
    include_all: bool = True,
) -> ResultSet:
    """Run all search variants and accumulate hits into a ResultSet."""
    logger.section("PHASE 1 — SEARCH")
    results = ResultSet()

    variants = _build_variants(query)
    if len(variants) > 1:
        logger.info(
            "query variants: " + " | ".join(repr(v) for v in variants)
        )

    for variant_idx, variant in enumerate(variants):
        variant_label = "phrase" if variant_idx == 0 else f"head:{variant}"

        # 1) r/all under both sort orders for each variant, unless the
        # operator deliberately wants a subreddit-only sweep.
        if include_all:
            for sort in SEARCH_SORTS:
                logger.phase(
                    "SEARCH",
                    f"r/all  sort={sort}  variant={variant_label}",
                )
                for raw in client.search(
                    variant, subreddit=None, sort=sort,
                    limit=limit, max_pages=max_pages,
                ):
                    source = f"all/{sort}#{variant_label}"
                    if results.add(raw, source):
                        logger.hit(*hit_summary(raw))
                logger.flush_hits()

        # 2) Each curated subreddit under relevance for each variant.
        for sub in subreddits:
            logger.phase(
                "SEARCH",
                f"r/{sub}  sort=relevance  variant={variant_label}",
            )
            for raw in client.search(
                variant, subreddit=sub, sort="relevance",
                limit=limit, max_pages=max_pages,
            ):
                source = f"{sub}/relevance#{variant_label}"
                if results.add(raw, source):
                    logger.hit(*hit_summary(raw))
            logger.flush_hits()

    return results


def phase_fetch_comments(
    *,
    logger: Logger,
    client: RedditClient,
    results: ResultSet,
    comment_limit: int,
) -> None:
    """Fetch top-level comments for every unique post."""
    logger.section("PHASE 2 — FETCH-COMMENTS")
    if not results:
        logger.info("no posts to fetch comments for; skipping")
        return

    logger.phase("FETCH-COMMENTS", f"{len(results)} unique post(s)")
    for record in results.values():
        post_id = record.get("id")
        if not post_id:
            continue
        try:
            comments = client.comments(post_id, limit=comment_limit)
        except Exception as exc:  # noqa: BLE001
            logger.warn(f"comments fetch failed for {post_id}: {exc}")
            comments = []
        if comments:
            logger.info(
                f"r/{record.get('subreddit')}  {post_id}  "
                f"+{len(comments)} comment(s)"
            )
        results.attach_comments(post_id, comments)


def phase_persist(
    *,
    logger: Logger,
    results: ResultSet,
    query: str,
    output_dir: str,
    run_stamp: str,
    started_iso: str,
) -> tuple[str, str]:
    """Write JSONL and Markdown; return their paths."""
    logger.section("PHASE 3 — PERSIST")
    os.makedirs(output_dir, exist_ok=True)

    j_path = jsonl_path(output_dir, run_stamp)
    m_path = markdown_path(output_dir, run_stamp)

    n = write_jsonl(j_path, results.values())
    logger.phase("PERSIST", f"wrote {n} record(s) → {j_path}")

    write_markdown(
        m_path,
        query=query,
        started_iso=started_iso,
        records=results.values(),
    )
    logger.phase("PERSIST", f"wrote markdown report → {m_path}")
    return j_path, m_path


def phase_summary(
    *,
    logger: Logger,
    results: ResultSet,
    j_path: str,
    m_path: str,
) -> None:
    logger.section("PHASE 4 — SUMMARY")
    total_comments = sum(
        len(r.get("comments") or []) for r in results.values()
    )
    logger.summary(
        {
            "unique posts":      len(results),
            "comments captured": total_comments,
            "jsonl":             j_path,
            "markdown":          m_path,
            "log file":          logger.log_path,
        }
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    started = datetime.now(timezone.utc)
    started_iso = started.isoformat()
    run_stamp = started.strftime("%Y%m%dT%H%M%SZ")

    logger = Logger(log_dir=args.log_dir, run_stamp=run_stamp)
    logger.banner(args.query)

    subreddits = [s.strip() for s in args.subreddits.split(",") if s.strip()]
    logger.config(
        {
            "tool":          f"zayns-reddit-scraper v{__version__}",
            "query":         args.query,
            "subreddits":    ", ".join(subreddits) if subreddits else "(none, r/all only)",
            "sorts":         ", ".join(SEARCH_SORTS),
            "max pages":     args.max_pages,
            "page limit":    args.limit,
            "delay":         f"{args.delay}s between requests",
            "comments":      "skipped" if args.no_comments else f"top {args.comment_limit}",
            "r/all":         "skipped" if args.no_all else "included",
            "output dir":    os.path.abspath(args.output_dir),
            "log dir":       os.path.abspath(args.log_dir),
            "run stamp":     run_stamp,
        }
    )

    client = RedditClient(logger=logger, delay_seconds=args.delay)

    try:
        results = phase_search(
            logger=logger,
            client=client,
            query=args.query,
            subreddits=subreddits,
            max_pages=args.max_pages,
            limit=args.limit,
            include_all=not args.no_all,
        )

        if not args.no_comments:
            phase_fetch_comments(
                logger=logger,
                client=client,
                results=results,
                comment_limit=args.comment_limit,
            )
        else:
            logger.section("PHASE 2 — FETCH-COMMENTS (skipped)")
            logger.info("--no-comments flag set; comment fetch skipped")

        j_path, m_path = phase_persist(
            logger=logger,
            results=results,
            query=args.query,
            output_dir=args.output_dir,
            run_stamp=run_stamp,
            started_iso=started_iso,
        )
        phase_summary(
            logger=logger,
            results=results,
            j_path=j_path,
            m_path=m_path,
        )
    except KeyboardInterrupt:
        logger.error("interrupted by user (Ctrl-C)")
        return 130
    except Exception as exc:  # noqa: BLE001
        logger.error(f"unhandled exception: {type(exc).__name__}: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
