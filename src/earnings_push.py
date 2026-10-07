"""
Phone pushes for earnings milestones: every time the day's gross crosses another $1,000 (1k, 2k, 3k ...),
your phone gets one push, e.g. "You have hit 2k on the day 🫣".

Runs inside the every-minute reminder check (agenda.tick). Fanvue is re-pulled for today at most every 5 minutes
here, so it works with SRM closed. Each milestone is claimed before it's sent, so it can never go out twice.
The first run after installing only remembers where today already is (no burst of old milestones).
"""
from __future__ import annotations

from datetime import datetime

import calc
import fanvue
import webpush
from store import db

EMOJI = {1: "😛", 2: "🫣", 3: "😮‍💨", 4: "😳", 5: "🤑"}
EXTRA = ["🔥", "💸", "🚀", "👑", "🤯"]   # 6k and up
PULL_EVERY = 300                          # seconds between Fanvue pulls from here


def emoji(k: int) -> str:
    return EMOJI.get(k) or EXTRA[min(len(EXTRA) - 1, k - 6)]


def message(k: int, gross: float, now: datetime) -> tuple[str, str]:
    return f"You have hit {k}k on the day {emoji(k)}", f"${gross:,.0f} gross so far · {now.strftime('%-I:%M %p')}"


def run() -> int:
    if not fanvue.is_connected():
        return 0
    today = fanvue.today_pt()
    key = f"earn:milestone:{today.isoformat()}"
    if db.set_nx("earn:pull", 1, PULL_EVERY):           # fresh numbers for today, every 5 minutes at most
        try:
            fanvue._store_window(today, today)
        except Exception:                               # a Fanvue hiccup just means we check again next time
            pass
    gross = calc.day_gross((db.hgetall("days") or {}).get(today.isoformat()))
    reached = int(gross // 1000)
    done = db.get(key)
    if done is None:
        if not db.get("earn:ready"):                    # first run ever: start from where today already is, silently
            db.set("earn:ready", 1)
            db.set(key, reached, ttl=3 * 86400)
            return 0
        done = 0
    done = int(done)
    if reached <= done or reached < 1:
        return 0
    db.set(key, reached, ttl=3 * 86400)                 # claimed first: never twice
    title, body = message(reached, gross, datetime.now(fanvue.PT))   # jumped two at once? just the newest one
    return webpush.send_all(title, body, f"earn{today.isoformat()}{reached}", "/")
