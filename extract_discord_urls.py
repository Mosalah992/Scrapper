"""Aggregate every Discord-invite / Discord URL mentioned across all
``output/*.jsonl`` files into a single ``output/DISCORD_URLS.md`` log.

This is a *post-processor*. It does not hit Reddit. Run it after one or
more ``scraper.py`` runs.

Scans, per record:

- ``url``       (Reddit's "outbound url" of a link post)
- ``permalink`` (skipped — never an invite)
- ``selftext``  (post body)
- ``title``
- ``comments[*].body``

Recognized URL shapes:

- ``discord.gg/<code>``
- ``discord.com/invite/<code>``  (and ``discordapp.com/invite/<code>``)
- ``discord.com/channels/<...>`` (specific channel deep-link)
- ``dsc.gg/<code>``               (custom vanity)
- ``discord.com/<anything>``      (catch-all, classified as ``other``)

Every unique URL gets one entry that lists every (post, snippet) pair it
appeared in. Output is sorted: invites first, then deep-links, then
``other``; within a group, by mention count descending.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import defaultdict
from typing import Iterator


# Match Discord-shaped URLs even when wrapped in markdown / parens / quotes.
# The trailing character class is conservative: invite codes are
# alphanumeric + dash; we stop at anything else so we don't swallow
# trailing punctuation like ", . ) ] >".
DISCORD_URL_RE = re.compile(
    r"""
    \b(?:https?://)?            # optional scheme
    (?:www\.)?                  # optional www
    (
      discord(?:app)?\.com/invite/[A-Za-z0-9-]+
      | discord\.gg/[A-Za-z0-9-]+
      | dsc\.gg/[A-Za-z0-9-]+
      | discord(?:app)?\.com/channels/[0-9]+(?:/[0-9]+)*
      | discord(?:app)?\.com/[A-Za-z0-9_/-]{1,80}
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def classify(url: str) -> str:
    """Return one of ``invite``, ``channel``, ``vanity``, ``other``."""
    u = url.lower()
    if "/invite/" in u or "discord.gg/" in u:
        return "invite"
    if "dsc.gg/" in u:
        return "vanity"
    if "/channels/" in u:
        return "channel"
    return "other"


CLASS_ORDER = {"invite": 0, "vanity": 1, "channel": 2, "other": 3}


def normalize(url: str) -> str:
    """Strip scheme + ``www.`` so two casings of the same invite collapse.

    Example: ``HTTPS://www.Discord.gg/abc`` → ``discord.gg/abc``.
    Casing of the invite *code* is preserved because Discord codes are
    case-sensitive.
    """
    # Lowercase only the host part. Split once on "/" after stripping scheme.
    s = url
    if s.lower().startswith("https://"):
        s = s[8:]
    elif s.lower().startswith("http://"):
        s = s[7:]
    if s.lower().startswith("www."):
        s = s[4:]
    if "/" in s:
        host, _, rest = s.partition("/")
        return host.lower() + "/" + rest
    return s.lower()


def find_in_text(text: str | None) -> Iterator[str]:
    if not text:
        return
    for m in DISCORD_URL_RE.finditer(text):
        yield m.group(1)


def snippet(text: str, url: str, span: int = 120) -> str:
    """Return ~span chars of context around the first occurrence of ``url``."""
    if not text:
        return ""
    idx = text.lower().find(url.lower())
    if idx < 0:
        return text[:span].strip()
    start = max(0, idx - span // 2)
    end = min(len(text), idx + len(url) + span // 2)
    out = text[start:end].replace("\n", " ").strip()
    if start > 0:
        out = "… " + out
    if end < len(text):
        out = out + " …"
    return out


def iter_records(jsonl_paths: list[str]) -> Iterator[tuple[dict, str]]:
    """Yield (record, source_filename) for every JSONL row."""
    for path in jsonl_paths:
        fname = os.path.basename(path)
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line), fname
                except json.JSONDecodeError:
                    continue


def collect(jsonl_paths: list[str]) -> dict:
    """Group mentions by normalized URL.

    Returns ``{ normalized_url: { 'class': ..., 'raw_examples': set,
                                  'mentions': [ ... ] } }``.
    Each mention dict carries ``post_id``, ``subreddit``, ``permalink``,
    ``title``, ``where`` (title|selftext|url|comment-by-<author>), and a
    surrounding ``snippet``.
    """
    bucket: dict[str, dict] = defaultdict(
        lambda: {"class": "other", "raw_examples": set(), "mentions": []}
    )

    for record, source_file in iter_records(jsonl_paths):
        post_id = record.get("id")
        sub = record.get("subreddit") or "?"
        permalink = record.get("permalink")
        title = record.get("title") or ""
        selftext = record.get("selftext") or ""
        out_url = record.get("url") or ""

        def add(url: str, where: str, source_text: str) -> None:
            norm = normalize(url)
            entry = bucket[norm]
            entry["class"] = classify(url)
            entry["raw_examples"].add(url)
            entry["mentions"].append(
                {
                    "post_id":   post_id,
                    "subreddit": sub,
                    "permalink": permalink,
                    "title":     title,
                    "where":     where,
                    "snippet":   snippet(source_text, url),
                    "source_file": source_file,
                }
            )

        # Title
        for u in find_in_text(title):
            add(u, "title", title)
        # Selftext
        for u in find_in_text(selftext):
            add(u, "selftext", selftext)
        # url field (link-posts)
        for u in find_in_text(out_url):
            add(u, "url", out_url)
        # Comments
        for c in (record.get("comments") or []):
            body = c.get("body") or ""
            author = c.get("author") or "?"
            for u in find_in_text(body):
                add(u, f"comment-by-u/{author}", body)

    return bucket


def render_markdown(bucket: dict, *, project_root: str) -> str:
    """Build the final DISCORD_URLS.md content."""
    if not bucket:
        return (
            "# Discord URLs found on Reddit\n\n"
            "_No Discord-shaped URLs were found in any of the scraped JSONL "
            "files. Re-run `python scraper.py` with comments enabled (drop "
            "`--no-comments`), then re-run this extractor — invite links "
            "tend to live in comments rather than post bodies._\n"
        )

    # Order entries: by class, then by mention count descending,
    # then alphabetically.
    sorted_urls = sorted(
        bucket.items(),
        key=lambda kv: (
            CLASS_ORDER.get(kv[1]["class"], 99),
            -len(kv[1]["mentions"]),
            kv[0],
        ),
    )

    lines: list[str] = []
    lines.append("# Discord URLs found on Reddit")
    lines.append("")
    lines.append(
        "_Aggregated from every `output/*.jsonl` file in this project._"
    )
    lines.append("")
    lines.append("**Legend**")
    lines.append("")
    lines.append("- **invite** — a `discord.gg/<code>` or `discord.com/invite/<code>` link. "
                 "These are real server invites; clicking joins the server.")
    lines.append("- **vanity** — `dsc.gg/<code>`, a third-party vanity-URL redirector that "
                 "wraps a Discord invite.")
    lines.append("- **channel** — `discord.com/channels/<...>` deep-link into a specific "
                 "channel; only works if you're already a member.")
    lines.append("- **other** — any other `discord.com` URL (e.g. landing page, blog, status).")
    lines.append("")

    counts_by_class: dict[str, int] = defaultdict(int)
    for entry in bucket.values():
        counts_by_class[entry["class"]] += 1

    lines.append("## Summary counts")
    lines.append("")
    lines.append("| class | unique URLs | total mentions |")
    lines.append("|-------|-------------|----------------|")
    for cls in ("invite", "vanity", "channel", "other"):
        if cls not in counts_by_class:
            continue
        unique = counts_by_class[cls]
        mentions = sum(
            len(e["mentions"]) for e in bucket.values() if e["class"] == cls
        )
        lines.append(f"| {cls} | {unique} | {mentions} |")
    lines.append("")

    # One section per class.
    last_cls = None
    for norm, entry in sorted_urls:
        cls = entry["class"]
        if cls != last_cls:
            lines.append("")
            lines.append(f"## {cls.upper()} URLs")
            lines.append("")
            last_cls = cls

        examples = sorted(entry["raw_examples"])
        primary = examples[0]
        # Render as a hyperlink — for invite/vanity these will join servers
        # if clicked, so we make the label very explicit.
        anchor = f"`{norm}`"
        lines.append(f"### {anchor}")
        lines.append("")
        lines.append(f"- **mentions**: {len(entry['mentions'])}")
        lines.append(f"- **as written**: {', '.join(examples)}")
        lines.append(f"- **clickable**: <https://{norm}>" if not primary.lower().startswith(("http://", "https://")) else f"- **clickable**: <{primary}>")
        lines.append("")

        # Individual mentions table.
        lines.append("| post | subreddit | seen in | snippet |")
        lines.append("|------|-----------|---------|---------|")
        for m in entry["mentions"]:
            link = m["permalink"] or "#"
            title = (m["title"] or "(untitled)").replace("|", r"\|")
            sub = m["subreddit"] or "?"
            where = m["where"]
            snip = (m["snippet"] or "").replace("|", r"\|")
            if len(snip) > 240:
                snip = snip[:240] + "…"
            lines.append(
                f"| [{title[:80]}]({link}) | r/{sub} | {where} | {snip} |"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(here, "output")
    pattern = os.path.join(output_dir, "*.jsonl")
    paths = sorted(glob.glob(pattern))
    if not paths:
        print(f"no JSONL files found under {output_dir}", file=sys.stderr)
        return 1
    print(f"scanning {len(paths)} JSONL file(s):")
    for p in paths:
        print(f"  - {os.path.basename(p)}")

    bucket = collect(paths)
    out_path = os.path.join(output_dir, "DISCORD_URLS.md")
    md = render_markdown(bucket, project_root=here)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(md)

    n_unique = len(bucket)
    n_total = sum(len(e["mentions"]) for e in bucket.values())
    print()
    print(f"wrote {out_path}")
    print(f"  unique Discord-shaped URLs: {n_unique}")
    print(f"  total mentions:             {n_total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
