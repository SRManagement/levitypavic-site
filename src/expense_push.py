"""
Phone pushes for expenses: everything that lands in the bell (new card charges waiting for ✓ / ✕, charges logged
automatically, Fanvue payouts landing, chatting / Fanvue drafts) also buzzes your phone once.

Runs inside the every-minute reminder check (agenda.tick). Each bell item is pushed once (ids kept in push:bell_sent).
The very first run only remembers what's already there, so turning this on never replays old charges.
"""
from __future__ import annotations

import time

from store import db
import webpush

SENT = "push:bell_sent"
PRINTS = "push:bell_prints"   # what each pushed charge looked like (place · amount · day), kept 7 days
KEEP = 7 * 86400
MAX_EACH = 3          # more than this at once → the first few, then one "+N more"


def _money(amount) -> str:
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return ""
    return f"-${abs(value):,.2f}" if value < 0 else f"${value:,.2f}"


def message(note: dict) -> tuple[str, str]:
    name = str(note.get("merchant") or "Expense")
    money = _money(note.get("amount"))
    pending = " · pending" if note.get("pending") else ""
    if note.get("deposit"):
        return f"💰 {name}", f"+{money.lstrip('-')} landed{pending}"
    if note.get("kind") == "new":
        return f"💳 {name} · {money}", f"Needs your approval{pending}. Tap to review."
    return f"✅ {name} · {money}", f"Logged to the sheet{pending}"


def _print(note: dict) -> str:
    """Same charge = same fingerprint, even when the bank swaps its id (pending → posted)."""
    try:
        amount = f"{abs(float(note.get('amount') or 0)):.2f}"
    except (TypeError, ValueError):
        amount = "?"
    name = " ".join(str(note.get("merchant") or "").lower().split())
    return f"{'dep' if note.get('deposit') else note.get('kind', '')}|{name}|{amount}|{str(note.get('date') or '')[:10]}"


def run() -> int:
    notes = db.hgetall("notifications") or {}
    saved = db.get(SENT)
    if saved is None:                                  # first run: remember what's there, push nothing old
        db.set(SENT, sorted(notes))
        return 0
    sent = set(saved)
    fresh = sorted((n for nid, n in notes.items() if nid not in sent and not n.get("done")),
                   key=lambda n: (n.get("at", ""), n.get("date", "")))
    now = int(time.time())
    prints = {k: v for k, v in (db.get(PRINTS) or {}).items() if now - int(v or 0) < KEEP}
    unseen = []
    for note in fresh:                                  # a charge that already buzzed once never buzzes again
        fp = _print(note)
        if fp not in prints:
            prints[fp] = now
            unseen.append(note)
    if fresh:
        db.set(PRINTS, prints)
    fresh = unseen
    pushed = 0
    for note in fresh[:MAX_EACH]:
        title, body = message(note)
        pushed += webpush.send_all(title, body, f"exp{note.get('id', '')}", url="/?expenses=1")
    if len(fresh) > MAX_EACH:
        more = len(fresh) - MAX_EACH
        pushed += webpush.send_all(f"💳 +{more} more expense{'s' if more != 1 else ''}", "Open Expenses to review them.",
                                   "exp-more", url="/?expenses=1")
    if set(notes) != sent:
        db.set(SENT, sorted(set(notes)))               # only ids still in the bell, so this list stays small
    return pushed
