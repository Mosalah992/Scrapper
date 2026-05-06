"""Sectioned, color-coded logger backed by ``rich`` + stdlib ``logging``.

The whole point of this module is that the rest of the code never has to
think about ANSI codes, table widths, or panel borders. Call sites write
``logger.phase("SEARCH", "querying r/all")`` and this file owns the look.

Color / icon vocabulary (kept in lock-step with
``openspec/changes/reddit-izayns-scraper/specs/sectioned-logging/spec.md``):

    banner      bold magenta panel        (ascii block frame)
    section     bold cyan rule            ══
    config      dim white panel           ⚙
    phase       bold blue                 ▶
    request     dim cyan                  →
    response    green                     ✓
    hit         bright yellow table row   ★
    warning     bold yellow               ⚠
    error       bold red                  ✖
    retry       yellow italic             ↻
    summary     bold green panel + table  Σ

The terminal stream is rendered through a ``rich.console.Console``; the
file mirror is a plain stdlib ``logging`` handler so the on-disk log is
grep-friendly and free of ANSI sequences.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional

from rich.box import HEAVY, ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text


def _force_utf8_stdout() -> None:
    """On legacy Windows consoles stdout is cp1252 and our block-frame
    glyphs (▌ ▐ ✓ ★ ↻ Σ …) raise ``UnicodeEncodeError``. Reconfigure
    stdout/stderr to utf-8 so ``rich`` can render them. Safe no-op on
    streams that don't support ``reconfigure`` (already-utf8 ttys, pipes
    on POSIX, etc.).
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


# --- Icon constants ---------------------------------------------------------

ICON_SECTION = "══"
ICON_CONFIG = "⚙"
ICON_PHASE = "▶"
ICON_REQUEST = "→"
ICON_RESPONSE = "✓"
ICON_HIT = "★"
ICON_WARN = "⚠"
ICON_ERROR = "✖"
ICON_RETRY = "↻"
ICON_SUMMARY = "Σ"


def _stamp() -> str:
    """UTC ``YYYYMMDDTHHMMSSZ`` stamp — sortable, filesystem-safe."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class Logger:
    """Single facade the rest of the codebase talks to.

    Parameters
    ----------
    log_dir:
        Directory where the colorless ``.log`` mirror is created.
    run_stamp:
        UTC stamp shared with the persistence layer so terminal log,
        JSONL, and Markdown report can be correlated by filename.
    """

    def __init__(self, log_dir: str, run_stamp: Optional[str] = None) -> None:
        self.run_stamp = run_stamp or _stamp()
        os.makedirs(log_dir, exist_ok=True)

        # Make sure non-ASCII glyphs (▌ ✓ ★ Σ) survive a legacy Windows
        # console before we hand the stream to rich.
        _force_utf8_stdout()

        # Force color on even if stdout is being captured (e.g. by IDE
        # consoles that don't advertise a tty). We still respect NO_COLOR.
        self.console = Console(
            highlight=False,
            soft_wrap=False,
            force_terminal=True if not os.environ.get("NO_COLOR") else False,
            legacy_windows=False,
        )

        # File mirror: plain text, utf-8, no ANSI.
        self.log_path = os.path.join(log_dir, f"scraper-{self.run_stamp}.log")
        self._file_logger = logging.getLogger(f"izayns.{id(self)}")
        self._file_logger.setLevel(logging.DEBUG)
        self._file_logger.propagate = False
        # Wipe any handlers a previous instance may have added.
        for h in list(self._file_logger.handlers):
            self._file_logger.removeHandler(h)
        handler = logging.FileHandler(self.log_path, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)-7s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%SZ",
            )
        )
        self._file_logger.addHandler(handler)

        # Internal counters surfaced in the final SUMMARY panel.
        self.counters = {
            "requests": 0,
            "responses_ok": 0,
            "retries": 0,
            "warnings": 0,
            "errors": 0,
            "hits": 0,
        }

        # Hits collected for the *current* phase, rendered as a single
        # table when ``flush_hits()`` is called.
        self._pending_hits: list[tuple[int, str, int, int, str]] = []

    # ------------------------------------------------------------------
    # Banner / sections
    # ------------------------------------------------------------------

    def banner(self, query: str) -> None:
        """Render the framed startup banner. First thing on every run."""
        body = Text()
        body.append("ZAYNS REDDIT SCRAPER\n", style="bold magenta")
        body.append("spec-driven via OpenSpec\n\n", style="dim")
        body.append("query     : ", style="bold")
        body.append(f"{query}\n")
        body.append("started   : ", style="bold")
        body.append(f"{datetime.now(timezone.utc).isoformat()}\n")
        body.append("log file  : ", style="bold")
        body.append(self.log_path)

        panel = Panel(
            body,
            box=HEAVY,
            border_style="bold magenta",
            padding=(1, 4),
            title="[bold magenta]▌ ZAYNS ▐[/bold magenta]",
            title_align="left",
        )
        self.console.print(panel)
        self._file_only(
            "BANNER",
            f"ZAYNS REDDIT SCRAPER — query={query!r} log={self.log_path}",
        )

    def section(self, label: str) -> None:
        """Horizontal rule that opens or closes a major block."""
        title = f"{ICON_SECTION} {label} {ICON_SECTION}"
        self.console.print(Rule(title, style="bold cyan"))
        self._file_only("SECTION", label)

    # ------------------------------------------------------------------
    # Config / phase
    # ------------------------------------------------------------------

    def config(self, items: dict[str, object]) -> None:
        """Dim panel describing the resolved CLI configuration."""
        table = Table.grid(padding=(0, 1), expand=False)
        table.add_column(style="dim white", no_wrap=True)
        table.add_column(style="white")
        for key, value in items.items():
            table.add_row(f"{key}", str(value))

        panel = Panel(
            table,
            box=ROUNDED,
            border_style="dim white",
            title=f"[dim white]{ICON_CONFIG} CONFIG[/dim white]",
            title_align="left",
            padding=(0, 2),
        )
        self.console.print(panel)
        for k, v in items.items():
            self._file_only("CONFIG", f"{k}={v}")

    def phase(self, name: str, detail: str = "") -> None:
        """Bold-blue "▶ PHASE-NAME — detail" line."""
        line = Text()
        line.append(f"{ICON_PHASE} ", style="bold blue")
        line.append(name, style="bold blue")
        if detail:
            line.append(" — ", style="dim")
            line.append(detail, style="white")
        self.console.print(line)
        self._file_only("PHASE", f"{name} {detail}".rstrip())

    # ------------------------------------------------------------------
    # Network events
    # ------------------------------------------------------------------

    def request(self, method: str, url: str) -> None:
        """Outgoing HTTP request — dim cyan."""
        self.counters["requests"] += 1
        line = Text()
        line.append(f"  {ICON_REQUEST} ", style="dim cyan")
        line.append(f"{method} ", style="dim cyan bold")
        line.append(url, style="dim cyan")
        self.console.print(line)
        self._file_only("REQUEST", f"{method} {url}")

    def response(self, status: int, url: str, elapsed_ms: int) -> None:
        """Successful HTTP response — green."""
        self.counters["responses_ok"] += 1
        line = Text()
        line.append(f"  {ICON_RESPONSE} ", style="green")
        line.append(f"{status} ", style="green bold")
        line.append(f"{elapsed_ms} ms ", style="green")
        line.append(url, style="dim")
        self.console.print(line)
        self._file_only("RESPONSE", f"{status} {elapsed_ms}ms {url}")

    def retry(self, attempt: int, max_attempts: int, wait_s: float, reason: str) -> None:
        """Pending retry — yellow italic."""
        self.counters["retries"] += 1
        line = Text()
        line.append(f"  {ICON_RETRY} ", style="yellow italic")
        line.append(
            f"retry {attempt}/{max_attempts} in {wait_s:.1f}s — {reason}",
            style="yellow italic",
        )
        self.console.print(line)
        self._file_only("RETRY", f"{attempt}/{max_attempts} wait={wait_s:.1f}s {reason}")

    # ------------------------------------------------------------------
    # Hits / warnings / errors
    # ------------------------------------------------------------------

    def hit(self, subreddit: str, score: int, num_comments: int, title: str) -> None:
        """Buffer a hit; flushed as a single table per phase.

        Buffering is what gives every phase a clean ★-titled hit table
        instead of an inconsistent stream of individual lines.
        """
        self.counters["hits"] += 1
        n = len(self._pending_hits) + 1
        self._pending_hits.append((n, subreddit, score, num_comments, title))
        # File mirror gets the line right away so live-tailing the file works.
        self._file_only(
            "HIT",
            f"#{n} r/{subreddit} score={score} comments={num_comments} title={title!r}",
        )

    def flush_hits(self) -> None:
        """Render and clear the buffered hits as a single table."""
        if not self._pending_hits:
            return
        table = Table(
            title=f"[bold yellow]{ICON_HIT} HITS[/bold yellow]",
            title_justify="left",
            border_style="bright_yellow",
            header_style="bold yellow",
            expand=True,
        )
        table.add_column("#", justify="right", no_wrap=True, style="bright_yellow")
        table.add_column("subreddit", no_wrap=True, style="bright_yellow")
        table.add_column("score", justify="right", no_wrap=True, style="bright_yellow")
        table.add_column("comments", justify="right", no_wrap=True, style="bright_yellow")
        table.add_column("title", overflow="fold", style="white")
        for row in self._pending_hits:
            n, sub, score, num_comments, title = row
            table.add_row(str(n), f"r/{sub}", str(score), str(num_comments), title)
        self.console.print(table)
        self._pending_hits.clear()

    def warn(self, message: str) -> None:
        self.counters["warnings"] += 1
        line = Text()
        line.append(f"  {ICON_WARN} ", style="bold yellow")
        line.append("WARN ", style="bold yellow")
        line.append(message, style="yellow")
        self.console.print(line)
        self._file_only("WARNING", message)

    def error(self, message: str) -> None:
        self.counters["errors"] += 1
        line = Text()
        line.append(f"  {ICON_ERROR} ", style="bold red")
        line.append("ERROR ", style="bold red")
        line.append(message, style="red")
        self.console.print(line)
        self._file_only("ERROR", message)

    def info(self, message: str) -> None:
        """Plain-white informational line for low-importance prose."""
        line = Text()
        line.append("  · ", style="dim")
        line.append(message, style="white")
        self.console.print(line)
        self._file_only("INFO", message)

    # ------------------------------------------------------------------
    # Final summary
    # ------------------------------------------------------------------

    def summary(self, extras: dict[str, object]) -> None:
        """Render the closing green-bordered summary panel."""
        table = Table.grid(padding=(0, 2), expand=False)
        table.add_column(style="bold green", no_wrap=True)
        table.add_column(style="white")

        merged: dict[str, object] = {
            "requests":        self.counters["requests"],
            "responses ok":    self.counters["responses_ok"],
            "retries":         self.counters["retries"],
            "hits (raw)":      self.counters["hits"],
            "warnings":        self.counters["warnings"],
            "errors":          self.counters["errors"],
        }
        merged.update(extras)
        for key, value in merged.items():
            table.add_row(str(key), str(value))

        panel = Panel(
            table,
            box=HEAVY,
            border_style="bold green",
            title=f"[bold green]{ICON_SUMMARY} SUMMARY[/bold green]",
            title_align="left",
            padding=(1, 3),
        )
        self.console.print(panel)
        for k, v in merged.items():
            self._file_only("SUMMARY", f"{k}={v}")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _file_only(self, level: str, message: str) -> None:
        """Write a single line to the colorless file mirror."""
        # We use logging.INFO uniformly; level distinction is conveyed by the
        # bracketed tag we prepend, which keeps grep-by-tag trivial.
        self._file_logger.info(f"[{level}] {message}")
