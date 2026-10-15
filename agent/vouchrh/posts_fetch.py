"""Real market posts for KOL mode, from Mastodon's public tag timelines.

Mastodon serves a hashtag's public timeline without an account:

    GET https://<instance>/api/v1/timelines/tag/<tag>?limit=40&max_id=<id>

Status ids are time-ordered (milliseconds since 1970, shifted left 16 bits),
so a max_id built from a date starts the page at that date: the script jumps
to a date and pages back from there, instead of reading every post since. It asks politely (a pause between requests, a cap
on the total, the client's default User-Agent) and keeps only posts in the
window that name one of the five companies and state a dollar figure (a post
with no figure cannot make a claim the 10-Q can check), so the snapshot stays
small. It says how many statuses it saw and how many named a company.

The snapshot is evidence and is committed: per post its url, instance,
account, time, text (HTML stripped), when it was fetched, and the sha256 of
the stored text.

    python -m vouchrh.posts_fetch                       # -> feed/kol/real/posts.json
    python -m vouchrh.posts_fetch --max-requests 20 --out /tmp/p.json
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "feed" / "kol" / "real" / "posts.json"
INSTANCES = ("mastodon.social", "mstdn.social", "mastodon.online")
# The window: posts about the Q2 2026 10-Qs (filed from late July to early August).
SINCE = "2026-07-15"
UNTIL = "2026-09-15"
# A post is kept if it names one of the five companies: a cashtag or the name.
COMPANY = re.compile(r"(?i)(\$(TSLA|AMZN|NFLX|PLTR|AMD)\b|#(TSLA|AMZN|NFLX|PLTR|AMD)\b|\b(Tesla|Amazon|Netflix|Palantir)\b"
                     r"|\bAMD\b)")
# ... and states a dollar figure: "$1.5B", "$587 million", "6.7 billion".
FIGURE = re.compile(r"(?i)\$\s?\d|\d\s?(b|bn|billion|m|mn|million)\b")
LABEL = ("REAL. Public posts from Mastodon hashtag timelines (no account used), fetched by "
         "agent/vouchrh/posts_fetch.py. Each is a real post by a real account; the url is the source. "
         "Kept: posts in the window that name Tesla, Amazon, Netflix, Palantir or AMD and state a dollar figure. "
         "The posters did not stake anything: the agent stakes on each story itself.")


def day(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def snowflake(when: datetime) -> int:
    """The smallest Mastodon status id at this moment: max_id=this pages back from it."""
    return int(when.timestamp() * 1000) << 16


def strip(content: str) -> str:
    """A status's HTML as plain text: line breaks kept, tags dropped, entities decoded."""
    s = re.sub(r"(?i)<br\s*/?>", "\n", content)
    s = re.sub(r"(?i)</p>\s*<p[^>]*>", "\n\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = "\n".join(" ".join(line.split()) for line in s.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def parse(statuses: list[dict], instance: str, fetched_at: str, since: str = SINCE, until: str = UNTIL,
          stats: dict | None = None) -> list[dict]:
    """The posts worth keeping from one page of a tag timeline."""
    stats = stats if stats is not None else {}
    lo, hi = day(since), day(until)
    out = []
    for s in statuses:
        s = s.get("reblog") or s
        when = datetime.fromisoformat(s["created_at"].replace("Z", "+00:00"))
        if not lo <= when < hi:
            continue
        text = strip(s.get("content") or "")
        if s.get("spoiler_text"):
            text = strip(s["spoiler_text"]) + "\n\n" + text
        if not text or not COMPANY.search(text):
            continue
        stats.setdefault("naming", set()).add(s.get("url") or s["uri"])
        if not FIGURE.search(text):
            continue
        acct = s["account"]["acct"]
        out.append({"url": s.get("url") or s["uri"], "instance": acct.split("@", 1)[1] if "@" in acct else instance,
                    "account": acct if "@" in acct else f"{acct}@{instance}", "created_at": s["created_at"],
                    "language": s.get("language"), "text": text, "fetched_at": fetched_at, "fetched_from": instance,
                    "sha256": sha(text)})
    return out


def oldest(statuses: list[dict]) -> tuple[str | None, datetime | None]:
    if not statuses:
        return None, None
    last = min(statuses, key=lambda s: int(s["id"]))
    return last["id"], datetime.fromisoformat(last["created_at"].replace("Z", "+00:00"))


def get(url: str, timeout: float = 20) -> list[dict]:
    with urllib.request.urlopen(url, timeout=timeout) as r:      # the client's default User-Agent
        return json.load(r)


# The busy tags (a company's name, #earnings, #stocks) carry a day of posts per
# page, so they are read around each Q2 10-Q's release (filed date + 3 days,
# paging back over the earnings call). The cashtags are quiet enough to read
# across the whole window.
FILED = {"NFLX": "2026-07-17", "TSLA": "2026-07-23", "AMZN": "2026-07-31", "PLTR": "2026-08-04", "AMD": "2026-08-05"}
NAME = {"TSLA": "Tesla", "AMZN": "Amazon", "NFLX": "Netflix", "PLTR": "Palantir", "AMD": "AMD"}


def plan(instances=INSTANCES, since: str = SINCE, until: str = UNTIL) -> list[tuple[str, str, str, int]]:
    """(instance, tag, start paging back from this date, at most this many pages)."""
    from datetime import timedelta
    after = lambda d, n: (day(d) + timedelta(days=n)).strftime("%Y-%m-%d")
    jobs = []
    for i, instance in enumerate(instances):
        deep = i == 0                     # the first instance is read most fully; the others add what it missed
        for t in FILED:
            jobs.append((instance, t, until, 4 if deep else 2))
        for t, filed in FILED.items():
            if NAME[t] != t:
                jobs.append((instance, NAME[t], after(filed, 3), 5 if deep else 2))
        jobs.append((instance, "AMD", after(FILED["AMD"], 4), 4 if deep else 2))
        for tag in ("earnings", "stocks"):
            for filed in FILED.values():
                jobs.append((instance, tag, after(filed, 2), 2 if deep else 1))
    return jobs


def fetch(jobs=None, since: str = SINCE, until: str = UNTIL, max_requests: int = 150, pause: float = 1.5,
          log=print, fetch_page=get) -> dict:
    jobs = plan(since=since, until=until) if jobs is None else jobs
    lo = day(since)
    posts, requests, asked, dead, stats = {}, 0, [], set(), {"statuses_seen": 0}
    for instance, tag, anchor, pages in jobs:
        if requests >= max_requests:
            log(f"  stopped at the cap of {max_requests} requests")
            break
        if instance in dead:
            continue
        max_id, n, kept = snowflake(day(anchor)), 0, 0
        while n < pages and requests < max_requests:
            url = f"https://{instance}/api/v1/timelines/tag/{tag}?limit=40&max_id={max_id}"
            requests += 1
            n += 1
            try:
                page = fetch_page(url)
            except (urllib.error.URLError, TimeoutError, ValueError) as e:
                log(f"  {instance} #{tag}: {e}")
                asked.append({"url": url, "error": str(e)[:200]})
                if isinstance(e, urllib.error.HTTPError) and e.code in (401, 403, 404, 422):
                    dead.add(instance)            # this instance does not serve public tag timelines
                time.sleep(pause)
                break
            fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            asked.append({"url": url, "statuses": len(page), "at": fetched_at})
            stats["statuses_seen"] += len(page)
            for p in parse(page, instance, fetched_at, since, until, stats):
                if p["url"] not in posts:
                    posts[p["url"]] = p
                    kept += 1
            last, when = oldest(page)
            time.sleep(pause)
            if not last or when < lo or len(page) < 40:
                break
            max_id = last
        log(f"  {instance:16} #{tag:9} from {anchor}: {n} page(s), {kept} new posts kept")
    ordered = sorted(posts.values(), key=lambda p: p["created_at"])
    return {"label": LABEL, "source": "Mastodon public tag timelines (GET /api/v1/timelines/tag/<tag>)",
            "window": {"since": since, "until": until}, "counts": {"statuses_seen": stats["statuses_seen"], "naming_a_company": len(stats.get("naming", ())),
                                                      "kept": len(ordered)},
            "requests": asked, "posts": ordered}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m vouchrh.posts_fetch")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--since", default=SINCE)
    ap.add_argument("--until", default=UNTIL)
    ap.add_argument("--max-requests", type=int, default=150)
    ap.add_argument("--pause", type=float, default=1.5, help="seconds between requests")
    ap.add_argument("--instances", default=",".join(INSTANCES))
    args = ap.parse_args(argv)
    snap = fetch(plan(args.instances.split(","), args.since, args.until), args.since, args.until,
                 args.max_requests, args.pause)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(snap, indent=1, ensure_ascii=False) + "\n")
    print(f"-> {args.out}  ({len(snap['posts'])} posts, {len(snap['requests'])} requests)")


if __name__ == "__main__":
    main()
