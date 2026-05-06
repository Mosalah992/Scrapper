# Findings — "Zayns server paper leak discord"

_run window: 2026-05-05_

## TL;DR

There **is** Reddit content that names the **"Zayn server"** as a Discord-distributed
O-level / IGCSE exam-paper leak source. The single most informative post calls it a
**scam** along with another source named **"Paradise papers"**.

## Primary source

**Post**: [r/u_Acceptable-Gap-4520 — "Thoughts on le@ks O levels"](https://www.reddit.com/r/u_Acceptable-Gap-4520/comments/1t0zk67/thoughts_on_leks_o_levels/)
**Author**: u/Acceptable-Gap-4520
**Body (verbatim)**:

> Y'all O level leaks are mainly just pure rumors, if y'all know about **Zayn server** then it's all fake. **Paradise papers** is also fake! The only legit guy was prodigy guy who did igcse bio and a levels pure maths. Pls don't fall for any fake scams because I've got proof they're fake! Buying papers is a scam

**Intel extracted from this single post**:

| Attribute             | Value                                                              |
| --------------------- | ------------------------------------------------------------------ |
| Discord server name   | **Zayn server** (singular "Zayn", not "Zayns")                     |
| Type of operation     | Sells / distributes claimed O-level + IGCSE leaked papers          |
| OP's verdict          | Fake / scam — "all fake", "rumors", "buying papers is a scam"      |
| Other named source    | **Paradise papers** (also called fake)                             |
| Reportedly legit name | "**prodigy guy**" — IGCSE Biology + A-level Pure Maths             |
| Title obfuscation     | "le@ks" instead of "leaks" — typical mod-evasion for scam content  |

## Other Reddit hits (low signal)

The same scrape returned 15 other posts; these are **not** about the same Zayn server:

- `r/zayn` (multiple posts), `r/OneDirection` — Zayn Malik (singer) fan Discord — **false positive**
- `r/popheads`, `r/LoveAndDeepspace`, `r/SMMA` — unrelated to the topic
- `r/alevels — "MATH M1"` — not about a leak; matched by the `Zayns discord` head
- 5 results from `r/IGCSE_helps` — these are subreddit metadata / wiki entries, not posts (the parser now filters these out in subsequent runs)

Full list with permalinks: [output/zayns-20260505T185126Z.md](zayns-20260505T185126Z.md)
Raw records: [output/zayns-20260505T185126Z.jsonl](zayns-20260505T185126Z.jsonl)

## Recommended follow-ups

The most distinctive search terms to look for **now** are no longer "Zayns" — try:

```powershell
python scraper.py --query "Zayn server leak"      --max-pages 3 --delay 3
python scraper.py --query "Paradise papers IGCSE" --max-pages 3 --delay 3
python scraper.py --query "prodigy IGCSE bio"     --max-pages 3 --delay 3
python scraper.py --query "Olevels paper leak Discord" --max-pages 3 --delay 3
```

These should be run with a **3-second `--delay`** because earlier runs sensitized the
Reddit anonymous quota — many subreddit searches in the last run got 429-walled.

## Notes on the scraper itself

- The variant ladder + auto-phrase-quoting was what made this work — the bare query
  `"Zayns server paper leak discord"` returned 0, but the head-pair variants
  (`"Zayns server"`, `"Zayns discord"`, etc.) surfaced the high-signal post via the
  `all/new#head:Zayns server` source.
- The parser has been hardened to skip non-post (`kind != t3`) results; future runs
  will not include the 5 r/IGCSE_helps subreddit-stub entries that polluted this run.
- Reddit rate-limited 37 of 190 requests in the last run; the 3-attempt back-off
  saved most of them but the comment-fetch phase was effectively starved. Use
  `--no-comments` for surveys and pull comments individually for the posts that
  matter.
