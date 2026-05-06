"""Thin Reddit JSON client with retry + back-off + delay.

Scope is intentionally minimal — only the two endpoints the scraper
actually needs:

    GET /search.json
    GET /r/<sub>/search.json
    GET /comments/<id>.json

We avoid PRAW so the scraper has zero credential setup.
"""

from __future__ import annotations

import time
from typing import Iterator, Optional
from urllib.parse import urlencode

import requests

from .config import (
    REDDIT_BASE_URL,
    RETRY_BACKOFF_SECONDS,
    RETRY_MAX_ATTEMPTS,
    RETRY_STATUS_CODES,
    USER_AGENT,
)
from .logger import Logger


class RedditClient:
    """Wraps a ``requests.Session`` with retry + delay + log callbacks."""

    def __init__(self, logger: Logger, delay_seconds: float) -> None:
        self.logger = logger
        self.delay_seconds = delay_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                # Reddit returns HTML if Accept doesn't ask for JSON.
                "Accept": "application/json",
            }
        )
        # Tracks the wall-clock of the last successful response so we can
        # space subsequent requests by ``delay_seconds``.
        self._last_request_at: float = 0.0

    # ------------------------------------------------------------------
    # Public endpoints
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        subreddit: Optional[str] = None,
        sort: str = "relevance",
        limit: int = 100,
        time_filter: str = "all",
        max_pages: int = 5,
    ) -> Iterator[dict]:
        """Yield post `data` dicts across paginated search results.

        Parameters
        ----------
        query:
            Free-text query. Spaces get URL-encoded.
        subreddit:
            If set, restrict to ``/r/<sub>/search.json`` with
            ``restrict_sr=1``.  If None, hits ``/search.json``.
        sort:
            ``relevance`` | ``new`` | ``hot`` | ``top`` | ``comments``.
        limit:
            Posts per page (Reddit caps at 100).
        time_filter:
            ``all`` | ``year`` | ``month`` | ``week`` | ``day`` | ``hour``.
        max_pages:
            Hard ceiling on pagination per search.
        """
        path = (
            f"/r/{subreddit}/search.json"
            if subreddit
            else "/search.json"
        )

        # Reddit's search default-OR's whitespace-separated terms, which on
        # /r/all + sort=new turns into a firehose of unrelated posts. Wrap
        # multi-word queries in quotes so we get phrase matching unless the
        # caller already quoted it themselves.
        effective_query = query.strip()
        if (
            " " in effective_query
            and not (effective_query.startswith('"') and effective_query.endswith('"'))
        ):
            effective_query = f'"{effective_query}"'

        after: Optional[str] = None
        for page in range(max_pages):
            params: dict[str, object] = {
                "q": effective_query,
                "sort": sort,
                "limit": limit,
                "t": time_filter,
                # raw_json=1 stops Reddit double-encoding & < > in titles.
                "raw_json": 1,
            }
            if subreddit:
                params["restrict_sr"] = 1
            if after:
                params["after"] = after

            url = f"{REDDIT_BASE_URL}{path}?{urlencode(params)}"
            payload = self._get_json(url)
            if payload is None:
                # Permanent failure already logged by _get_json.
                return

            children = (
                payload.get("data", {}).get("children", []) if payload else []
            )
            if not children:
                if page == 0:
                    self.logger.info(
                        f"no results on first page for "
                        f"sort={sort} sub={subreddit or 'all'}"
                    )
                return

            for child in children:
                if not isinstance(child, dict):
                    continue
                # Reddit's search will mix in t5 (subreddit) and other
                # non-post objects when query terms match the sub's
                # description / wiki / about. We only want real posts (t3).
                if child.get("kind") != "t3":
                    continue
                data = child.get("data")
                if isinstance(data, dict):
                    yield data

            after = payload.get("data", {}).get("after")
            if not after:
                return

        # If we fell off the loop, max_pages was hit with `after` still set.
        self.logger.warn(
            f"max-pages={max_pages} reached for "
            f"sort={sort} sub={subreddit or 'all'} — more results exist"
        )

    def comments(self, post_id: str, *, limit: int = 50) -> list[dict]:
        """Return up to ``limit`` top-level comment ``data`` dicts."""
        # Reddit's /comments/<id>.json returns a 2-element list:
        #   [0] post listing, [1] comment listing
        url = f"{REDDIT_BASE_URL}/comments/{post_id}.json?raw_json=1&limit={limit}"
        payload = self._get_json(url)
        if not isinstance(payload, list) or len(payload) < 2:
            return []
        comment_listing = payload[1]
        children = (
            comment_listing.get("data", {}).get("children", [])
            if isinstance(comment_listing, dict)
            else []
        )
        out: list[dict] = []
        for child in children:
            if not isinstance(child, dict):
                continue
            # "more" stubs are skipped — they're not real comments.
            if child.get("kind") != "t1":
                continue
            data = child.get("data")
            if isinstance(data, dict):
                out.append(data)
            if len(out) >= limit:
                break
        return out

    # ------------------------------------------------------------------
    # HTTP plumbing
    # ------------------------------------------------------------------

    def _respect_delay(self) -> None:
        """Sleep so consecutive requests are spaced by ``delay_seconds``."""
        if self._last_request_at == 0.0:
            return
        elapsed = time.monotonic() - self._last_request_at
        gap = self.delay_seconds - elapsed
        if gap > 0:
            time.sleep(gap)

    def _get_json(self, url: str):
        """Issue GET with retry/back-off; return parsed JSON or None."""
        for attempt in range(1, RETRY_MAX_ATTEMPTS + 1):
            self._respect_delay()
            self.logger.request("GET", url)
            try:
                start = time.monotonic()
                resp = self.session.get(url, timeout=20)
                elapsed_ms = int((time.monotonic() - start) * 1000)
                self._last_request_at = time.monotonic()
            except requests.RequestException as exc:
                wait = self._backoff_for(attempt)
                if wait is None:
                    self.logger.error(
                        f"GET {url} failed after {attempt} attempts: {exc}"
                    )
                    return None
                self.logger.retry(
                    attempt, RETRY_MAX_ATTEMPTS, wait, f"{type(exc).__name__}: {exc}"
                )
                time.sleep(wait)
                continue

            if resp.status_code in RETRY_STATUS_CODES:
                wait = self._backoff_for(attempt)
                if wait is None:
                    self.logger.error(
                        f"GET {url} → HTTP {resp.status_code} "
                        f"after {attempt} attempts; giving up"
                    )
                    return None
                self.logger.retry(
                    attempt,
                    RETRY_MAX_ATTEMPTS,
                    wait,
                    f"HTTP {resp.status_code}",
                )
                time.sleep(wait)
                continue

            if resp.status_code >= 400:
                self.logger.error(
                    f"GET {url} → HTTP {resp.status_code} (non-retryable)"
                )
                return None

            self.logger.response(resp.status_code, url, elapsed_ms)
            try:
                return resp.json()
            except ValueError as exc:
                self.logger.error(f"GET {url} → invalid JSON: {exc}")
                return None

        # Loop exited without returning — should be unreachable.
        return None

    @staticmethod
    def _backoff_for(attempt: int) -> Optional[float]:
        """Return seconds to wait before retry, or None when out of retries."""
        idx = attempt - 1
        if idx >= len(RETRY_BACKOFF_SECONDS) or attempt >= RETRY_MAX_ATTEMPTS:
            return None
        return RETRY_BACKOFF_SECONDS[idx]
