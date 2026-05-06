"""Centralized CLI for the Zayns Reddit scraper.

A single entry point that dispatches to every script in this project,
so day-to-day operation never needs to remember which file to invoke:

    python cli.py scrape           # run the Reddit scraper
    python cli.py extract          # aggregate Discord URLs from prior runs
    python cli.py all              # scrape, then extract, in one shot
    python cli.py runs             # list every persisted scrape run
    python cli.py latest           # print the newest run's md/jsonl/log paths
    python cli.py clean            # delete output/* and logs/* (with confirm)
    python cli.py version          # print the package version

Pass ``-h`` / ``--help`` after any subcommand to see its own flags.
The ``scrape`` subcommand forwards every flag straight through to
``scraper.py`` — see ``python cli.py scrape --help`` for the full list.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from typing import Sequence

# Re-use the existing modules rather than shelling out — keeps the CLI
# in-process so KeyboardInterrupt, exit codes and tracebacks behave
# identically to the underlying scripts.
import scraper as scraper_module
import extract_discord_urls as extract_module
from reddit_scraper import __version__, __tool_name__
from reddit_scraper.config import (
    DEFAULT_LOG_DIR,
    DEFAULT_OUTPUT_DIR,
    FILENAME_PREFIX,
    LOG_FILENAME_PREFIX,
)


HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _abs(path: str) -> str:
    """Resolve ``path`` relative to the project root if it isn't absolute."""
    return path if os.path.isabs(path) else os.path.join(HERE, path)


def _list_runs(output_dir: str) -> list[tuple[str, str | None, str | None]]:
    """Return ``[(run_stamp, jsonl_path|None, md_path|None), ...]`` newest first."""
    output_dir = _abs(output_dir)
    if not os.path.isdir(output_dir):
        return []
    stamps: dict[str, dict[str, str]] = {}
    for path in glob.glob(os.path.join(output_dir, f"{FILENAME_PREFIX}-*.*")):
        base = os.path.basename(path)
        # zayns-<stamp>.<ext>
        stem, ext = os.path.splitext(base)
        if not stem.startswith(f"{FILENAME_PREFIX}-"):
            continue
        stamp = stem[len(FILENAME_PREFIX) + 1:]
        stamps.setdefault(stamp, {})[ext.lstrip(".").lower()] = path
    rows = [
        (stamp, files.get("jsonl"), files.get("md"))
        for stamp, files in stamps.items()
    ]
    rows.sort(key=lambda r: r[0], reverse=True)
    return rows


def _latest_log(log_dir: str, run_stamp: str) -> str | None:
    candidate = os.path.join(
        _abs(log_dir), f"{LOG_FILENAME_PREFIX}-{run_stamp}.log"
    )
    return candidate if os.path.isfile(candidate) else None


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_scrape(rest: list[str]) -> int:
    """Forward every remaining arg to ``scraper.main``."""
    return scraper_module.main(rest)


def cmd_extract(rest: list[str]) -> int:
    """Forward every remaining arg to ``extract_discord_urls.main``."""
    return extract_module.main(rest)


def cmd_all(rest: list[str]) -> int:
    """Run ``scrape`` then ``extract`` so a single command produces a full
    deliverable: JSONL + Markdown report **and** the aggregated Discord-URL
    log. Any flags after ``all`` are forwarded to ``scrape`` only — the
    extractor takes no flags today.
    """
    print(f"[{__tool_name__}] step 1/2 — scraping Reddit", flush=True)
    rc = scraper_module.main(rest)
    if rc != 0:
        print(
            f"[{__tool_name__}] scraper exited with code {rc}; "
            f"skipping extract step",
            file=sys.stderr,
        )
        return rc
    print(f"\n[{__tool_name__}] step 2/2 — aggregating Discord URLs", flush=True)
    return extract_module.main([])


def cmd_runs(rest: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cli.py runs",
        description="List every persisted scrape run, newest first.",
    )
    parser.add_argument(
        "--output-dir", default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to scan (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--log-dir", default=DEFAULT_LOG_DIR,
        help=f"Directory holding the colorless log mirrors (default: {DEFAULT_LOG_DIR}).",
    )
    args = parser.parse_args(rest)

    rows = _list_runs(args.output_dir)
    if not rows:
        print(f"no runs found in {_abs(args.output_dir)}")
        return 0

    print(f"{'run stamp':<20}  {'jsonl':<7}  {'md':<5}  {'log':<5}  files")
    print(f"{'-' * 20}  {'-' * 7}  {'-' * 5}  {'-' * 5}  -----")
    for stamp, jsonl, md in rows:
        log = _latest_log(args.log_dir, stamp)
        print(
            f"{stamp:<20}  "
            f"{'yes' if jsonl else 'no':<7}  "
            f"{'yes' if md else 'no':<5}  "
            f"{'yes' if log else 'no':<5}  "
            f"{os.path.basename(jsonl) if jsonl else '-'}, "
            f"{os.path.basename(md) if md else '-'}"
        )
    print(f"\ntotal runs: {len(rows)}")
    return 0


def cmd_latest(rest: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cli.py latest",
        description="Print the newest run's jsonl, md, and log paths.",
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--log-dir", default=DEFAULT_LOG_DIR)
    args = parser.parse_args(rest)

    rows = _list_runs(args.output_dir)
    if not rows:
        print(f"no runs found in {_abs(args.output_dir)}", file=sys.stderr)
        return 1

    stamp, jsonl, md = rows[0]
    log = _latest_log(args.log_dir, stamp)
    print(f"run stamp: {stamp}")
    print(f"jsonl:     {jsonl or '(missing)'}")
    print(f"markdown:  {md or '(missing)'}")
    print(f"log:       {log or '(missing)'}")
    return 0


def cmd_clean(rest: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cli.py clean",
        description=(
            "Delete generated artifacts under output/ and logs/. "
            "Always preserves the project's curated DISCORD_URLS.md and "
            "FINDINGS.md unless --force is given."
        ),
    )
    parser.add_argument(
        "--output-dir", default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to scrub (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--log-dir", default=DEFAULT_LOG_DIR,
        help=f"Log directory to scrub (default: {DEFAULT_LOG_DIR}).",
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="Skip the interactive confirmation prompt.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help=(
            "Also delete curated reports (DISCORD_URLS.md, FINDINGS.md). "
            "Without --force these survive a clean."
        ),
    )
    args = parser.parse_args(rest)

    output_dir = _abs(args.output_dir)
    log_dir = _abs(args.log_dir)

    # Build deletion list. Run files only — never touch .gitkeep or the
    # operator's manually curated docs unless --force.
    targets: list[str] = []
    targets.extend(glob.glob(os.path.join(output_dir, f"{FILENAME_PREFIX}-*.jsonl")))
    targets.extend(glob.glob(os.path.join(output_dir, f"{FILENAME_PREFIX}-*.md")))
    targets.extend(glob.glob(os.path.join(log_dir, f"{LOG_FILENAME_PREFIX}-*.log")))
    if args.force:
        for name in ("DISCORD_URLS.md", "FINDINGS.md"):
            p = os.path.join(output_dir, name)
            if os.path.isfile(p):
                targets.append(p)

    if not targets:
        print("nothing to clean.")
        return 0

    print(f"about to delete {len(targets)} file(s):")
    for p in targets:
        print(f"  - {p}")
    if not args.yes:
        try:
            answer = input("proceed? [y/N] ").strip().lower()
        except EOFError:
            answer = ""
        if answer not in {"y", "yes"}:
            print("aborted.")
            return 1

    failed = 0
    for p in targets:
        try:
            os.remove(p)
        except OSError as exc:
            print(f"  ! failed to delete {p}: {exc}", file=sys.stderr)
            failed += 1
    print(f"deleted {len(targets) - failed} file(s); {failed} failure(s).")
    return 0 if failed == 0 else 2


def cmd_version(rest: list[str]) -> int:
    if rest:
        print("version takes no arguments", file=sys.stderr)
        return 2
    print(f"{__tool_name__} {__version__}")
    return 0


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

# Each entry: (subcommand, one-line help, callable taking the remaining argv).
COMMANDS: dict[str, tuple[str, callable]] = {
    "scrape":  ("Run the Reddit scraper (forwards all flags to scraper.py).", cmd_scrape),
    "extract": ("Aggregate Discord URLs across every output/*.jsonl.",       cmd_extract),
    "all":     ("Scrape, then extract Discord URLs, in one command.",        cmd_all),
    "runs":    ("List every persisted scrape run, newest first.",            cmd_runs),
    "latest":  ("Print the newest run's jsonl/md/log paths.",                cmd_latest),
    "clean":   ("Delete generated JSONL/Markdown/log artifacts.",            cmd_clean),
    "version": ("Print the package version and exit.",                       cmd_version),
}


def _print_top_help() -> None:
    print(f"{__tool_name__} v{__version__} — centralized CLI\n")
    print("usage: python cli.py <command> [options]\n")
    print("commands:")
    width = max(len(name) for name in COMMANDS)
    for name, (help_text, _) in COMMANDS.items():
        print(f"  {name:<{width}}  {help_text}")
    print("\nrun 'python cli.py <command> --help' for command-specific flags.")


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in {"-h", "--help", "help"}:
        _print_top_help()
        return 0

    if argv[0] in {"-V", "--version"}:
        return cmd_version([])

    name, *rest = argv
    if name not in COMMANDS:
        print(f"unknown command: {name!r}\n", file=sys.stderr)
        _print_top_help()
        return 2

    _, handler = COMMANDS[name]
    return handler(rest)


if __name__ == "__main__":
    sys.exit(main())
