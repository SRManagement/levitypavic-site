"""
Bank feed: card charges straight from Plaid (no AI in between).

  - PENDING charges show up right away (marked "pending" in the sheet and the app). When the bank
    posts one, Plaid gives it a new ID that points back at the pending one (pending_transaction_id):
    the same record / sheet row is carried over to the posted ID with the posted amount, so a charge is
    never counted twice. A pending charge the bank drops (declined, voided, bounced) is taken back out
    of the sheet, the chart and the app.
  - Only the card ending in PLAID_CARD_MASK (default 0029).
  - Only charges posted on/after the day after the last row in the sheet when the
    bank was connected, so nothing Grok already logged comes in again.
  - A charge that matches a row logged before the bank was connected (same merchant,
    same amount, same day give or take one) is treated as already logged. That only
    catches the handover from Grok; it's kept tight so a second $50 Atlas top-up two
    days later still counts.

Every new charge waits in Expenses > New (and the bell) until you decide: tick it and it's written
into the sheet, cross it and it goes to Trash. Nothing is logged on its own, not even from a merchant
you've approved before. Fanvue payouts landing in checking work the same way (they reach the Income
tab only after your tick).
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

import sheet
import writeoffs
from fanvue import PT
from store import db

ENV = os.environ.get("PLAID_ENV", "production")
HOST = f"https://{ENV}.plaid.com"
CLIENT_ID = os.environ.get("PLAID_CLIENT_ID", "")
SECRET = os.environ.get("PLAID_SECRET", "")
CARD_MASK = os.environ.get("PLAID_CARD_MASK", "0029")
DEFAULT_CATEGORY = "Software/AI"



class BankError(Exception):
    def __init__(self, message: str, code: str = ""):
        super().__init__(message)
        self.code = code


def configured() -> bool:
    return bool(CLIENT_ID and SECRET)


def _plaid(path: str, body: dict) -> dict:
    if not configured():
        raise BankError("PLAID_CLIENT_ID / PLAID_SECRET aren't set in Vercel")
    req = urllib.request.Request(
        HOST + path,
        data=json.dumps({"client_id": CLIENT_ID, "secret": SECRET, **body}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            err = json.loads(exc.read().decode())
        except ValueError:
            err = {}
        raise BankError(err.get("display_message") or err.get("error_message") or f"Plaid error {exc.code}",
                        err.get("error_code", "")) from exc
    except urllib.error.URLError as exc:
        raise BankError(f"Could not reach Plaid: {exc}") from exc


# ---------- Connecting ----------

HISTORY_DAYS = 730   # how far back a new bank connection reaches (Plaid's max; can't be changed later)


def link_token(webhook: str = "") -> dict:
    """Token for Plaid's login window. Re-uses the existing connection if the bank asked you to log in again."""
    item = db.get("plaid")
    body = {"client_name": "SRM Dashboard", "user": {"client_user_id": "srm-owner"},
            "country_codes": ["US"], "language": "en"}
    if webhook:
        body["webhook"] = webhook
    if item and item.get("needs_login"):
        body["access_token"] = item["access_token"]
        mode = "update"
    else:
        body.update({"products": ["transactions"], "transactions": {"days_requested": HISTORY_DAYS}})
        mode = "new"
    return {"link_token": _plaid("/link/token/create", body)["link_token"], "mode": mode}


def connect(public_token: str, institution: str, expenses: list[dict]) -> dict:
    exchanged = _plaid("/item/public_token/exchange", {"public_token": public_token})
    access = exchanged["access_token"]
    accounts = _plaid("/accounts/get", {"access_token": access})["accounts"]
    tracked = [a["account_id"] for a in accounts if a.get("mask") == CARD_MASK]
    last_logged = max((e["date"] for e in expenses), default=None)
    start = (date.fromisoformat(last_logged) + timedelta(days=1)).isoformat() if last_logged else datetime.now(PT).date().isoformat()
    db.set("plaid", {
        "access_token": access,
        "item_id": exchanged.get("item_id"),
        "institution": institution or "Bank",
        "accounts": [{"id": a["account_id"], "name": a.get("name"), "mask": a.get("mask")} for a in accounts],
        "tracked": tracked or [a["account_id"] for a in accounts],
        "mask_found": bool(tracked),
        "start": start,
        "cursor": None,
        "history_days": HISTORY_DAYS,
    })
    db.delete("bank_error")
    return status()


# ---------- Live updates (Plaid webhook) ----------
# Plaid checks the bank for new charges several times a day; with a webhook set on the connection it
# pings /api/plaid/webhook as soon as it has something, and the server syncs right then.

SYNC_CODES = {"SYNC_UPDATES_AVAILABLE", "DEFAULT_UPDATE", "INITIAL_UPDATE", "HISTORICAL_UPDATE", "TRANSACTIONS_REMOVED"}


def ensure_webhook(url: str) -> None:
    """Points the existing connection's webhook at this app (once; again only if the URL changes)."""
    item = db.get("plaid")
    if not url or not item or item.get("webhook") == url:
        return
    res = _plaid("/item/webhook/update", {"access_token": item["access_token"], "webhook": url})
    item["webhook"] = url
    item["item_id"] = (res.get("item") or {}).get("item_id") or item.get("item_id")
    db.set("plaid", item)


def wants_webhook(event: dict) -> bool:
    """A transactions ping for our connection."""
    item = db.get("plaid")
    if not item or event.get("webhook_type") != "TRANSACTIONS" or event.get("webhook_code") not in SYNC_CODES:
        return False
    return not item.get("item_id") or event.get("item_id") == item["item_id"]


def finished_relogin() -> None:
    item = db.get("plaid")
    if item:
        item.pop("needs_login", None)
        db.set("plaid", item)
        db.delete("bank_error")


def status() -> dict:
    item = db.get("plaid") or {}
    masks = [a["mask"] for a in item.get("accounts", []) if a["id"] in item.get("tracked", [])]
    return {
        "configured": configured(),
        "connected": bool(item),
        "institution": item.get("institution", ""),
        "masks": masks,
        "mask_found": item.get("mask_found", True),
        "start": item.get("start"),
        "last_sync": item.get("last_sync"),
        "needs_login": bool(item.get("needs_login")),
        "error": db.get("bank_error") or "",
    }


# ---------- Syncing ----------

def _pull(item: dict) -> tuple[list, list, str]:
    """All changes since the saved cursor. Plaid says: if a page fails mid-way, restart from the first cursor."""
    for attempt in range(3):
        added, removed, cursor = [], [], item.get("cursor")
        try:
            while True:
                body = {"access_token": item["access_token"], "count": 500}
                if cursor:
                    body["cursor"] = cursor
                page = _plaid("/transactions/sync", body)
                added += page.get("added", []) + page.get("modified", [])
                removed += [r["transaction_id"] for r in page.get("removed", [])]
                cursor = page["next_cursor"]
                if not page.get("has_more"):
                    return added, removed, cursor
        except BankError as exc:
            if exc.code == "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION" and attempt < 2:
                continue
            raise
    raise BankError("Plaid sync kept changing, try again")


def _sheet_match(rec: dict, expenses: list[dict], claimed: set, before: str) -> str | None:
    """A row logged before the bank was connected for this same charge (same merchant + amount, ±1 day)."""
    day = date.fromisoformat(rec["date"])
    best = None
    for e in expenses:
        if (e["id"] in claimed or e.get("bank_id") or e["date"] >= before or e["provider"] != rec["provider"]
                or abs(e["amount"] - rec["amount"]) > 0.01):
            continue
        gap = abs((date.fromisoformat(e["date"]) - day).days)
        if gap <= 1 and (best is None or gap < best[0]):
            best = (gap, e["id"])
    return best[1] if best else None


def sheet_row_for(rec: dict, expenses: list[dict]) -> dict:
    """Describe a bank charge the way your sheet already describes that merchant."""
    previous = [e for e in expenses if e["provider"] == rec["provider"] and not e.get("bank_id")]
    if previous:
        latest = max(previous, key=lambda e: e["date"])
        item = re.sub(r"\s+·\s+.*$", "", latest["item"])  # drop "· 13:20 PT" style suffixes
        category = latest["category"]
    else:
        item, category = rec["merchant"], rec.get("category") or DEFAULT_CATEGORY
    if rec.get("pending"):
        item += sheet.PENDING_MARK
    return {"date": rec["date"], "item": item, "category": category, "amount": rec["amount"], "bank_id": rec["id"]}


def _when(t: dict, catch_up: bool = False) -> dict:
    """When the charge showed up on the card: the bank's own timestamp when it sends one, otherwise
    the moment this app first saw it (marked as such). None for the one-time catch-up (unknown)."""
    raw = t.get("authorized_datetime") or t.get("datetime")
    if raw:
        try:
            at = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(PT)
            return {"time": at.strftime("%H:%M"), "time_exact": True, "seen_day": at.date().isoformat()}
        except ValueError:
            pass
    if catch_up:
        return {"time": None, "time_exact": False, "seen_day": None}
    now = datetime.now(PT)
    return {"time": now.strftime("%H:%M"), "time_exact": False, "seen_day": now.date().isoformat()}


def _charge_rec(t: dict, item: dict) -> dict | None:
    """A card charge on the tracked card (posted or pending), or None."""
    if t.get("account_id") not in item["tracked"] or (t.get("amount") or 0) <= 0 or (t.get("date") or "") < item["start"]:
        return None
    merchant = t.get("merchant_name") or t.get("name") or "Unknown"
    guess = writeoffs.classify(t)
    return {
        "id": t["transaction_id"],
        "date": t.get("authorized_date") or t["date"],
        "merchant": merchant,
        "provider": sheet.canonical_provider(merchant),
        "amount": round(float(t["amount"]), 2),
        "pending": bool(t.get("pending")),
        "why": f"looks like {guess['why']}" if guess else None,
        "category": guess["category"] if guess else None,
        **_when(t, catch_up=bool(t.get("_catch_up"))),
    }


def _catch_up_pending(item: dict) -> list[dict]:
    """Once, right after pending support went in: the charges that are pending right now (the sync
    cursor had already gone past them while pending charges were being ignored)."""
    if db.get("pending_catch_up_done"):
        return []
    today = datetime.now(PT).date()
    start = max(item["start"], (today - timedelta(days=21)).isoformat())
    found, offset = [], 0
    while True:
        page = _plaid("/transactions/get", {"access_token": item["access_token"], "start_date": start, "end_date": today.isoformat(),
                                            "options": {"count": 500, "offset": offset, "account_ids": item["tracked"]}})
        txs = page.get("transactions", [])
        found += [{**t, "_catch_up": True} for t in txs if t.get("pending")]
        offset += len(txs)
        if not txs or offset >= page.get("total_transactions", 0):
            break
    db.set("pending_catch_up_done", True)
    return found


def _apply_sheet_fixes(fixes: dict) -> None:
    """Row changes for charges already in the sheet: {bank id: {"delete": True} | {bank_id/amount/pending}}.
    Saved first, so a sheet hiccup is retried on the next sync instead of lost."""
    if fixes:
        db.hset("bank_sheet_fixes", fixes)
    todo = db.hgetall("bank_sheet_fixes")
    if not todo:
        return
    gone = [k for k, v in todo.items() if v.get("delete")]
    edits = {k: v for k, v in todo.items() if not v.get("delete")}
    sheet.delete_bank_rows(gone)
    sheet.update_bank_rows(edits)
    db.delete("bank_sheet_fixes")


def _move_status(old: str, new: str) -> None:
    """Your Verified / Trash choice on a sheet row follows the row to its posted ID."""
    statuses = db.hgetall("expense_status")
    if "bank:" + old in statuses:
        db.hset("expense_status", {"bank:" + new: statuses["bank:" + old]})
        db.hdel("expense_status", "bank:" + old)


def sync(expenses: list[dict]) -> dict:
    item = db.get("plaid")
    if not item:
        return status()
    try:
        added, removed, cursor = _pull(item)
    except BankError as exc:
        if exc.code == "ITEM_LOGIN_REQUIRED":
            item["needs_login"] = True
            db.set("plaid", item)
        db.set("bank_error", str(exc))
        return status()

    try:
        added = _catch_up_pending(item) + added
    except BankError:
        pass                                           # e.g. history not ready yet: tried again next sync
    known = db.hgetall("bank")
    deposits = db.hgetall("income_deposits")
    _back_to_new(known)
    notes = db.hgetall("notifications")
    claimed = {r["matched"] for r in known.values() if r.get("matched")}
    fresh: dict[str, dict] = {}      # new / changed records to save
    landed: dict[str, dict] = {}
    fixes: dict[str, dict] = {}      # sheet rows to update or delete
    replaced: dict[str, str] = {}    # pending id -> posted id
    carried: set[str] = set()        # posted ids whose pending record was already saved
    announce: list[dict] = []        # brand-new charges (bell)
    changed = False

    for t in sorted(added, key=lambda t: (t.get("date") or "", not t.get("pending"))):
        tid = t["transaction_id"]
        dep = _payout_deposit(t)                       # a Fanvue payout landing in checking (any account)
        if dep:
            if tid not in deposits:                    # new one: waits for your ✓ like a charge
                landed[tid] = {**dep, "status": "new", **_when(t)}
            continue
        rec = _charge_rec(t, item)
        if not rec:
            continue
        have = fresh.get(tid) or known.get(tid)
        if have:                                       # already seen: a pending amount can change
            if abs(have["amount"] - rec["amount"]) > 0.005 or have.get("pending") != rec["pending"]:
                fresh[tid] = {**have, "amount": rec["amount"], "pending": rec["pending"]}
                if have["status"] == "approved":
                    fixes[tid] = {"amount": rec["amount"], "pending": rec["pending"]}
                changed = True
            continue
        prev_id = t.get("pending_transaction_id")
        prev = (fresh.get(prev_id) or known.get(prev_id)) if prev_id else None
        if prev:                                       # the posted version of a pending charge we have
            fresh[tid] = {**prev, "id": tid, "amount": rec["amount"], "pending": False}
            fresh.pop(prev_id, None)
            replaced[prev_id] = tid
            if prev_id in known:                       # its row / notification already exist: carry them over
                carried.add(tid)
                if prev["status"] == "approved":
                    fixes[prev_id] = {"bank_id": tid, "amount": rec["amount"], "pending": False}
                    _move_status(prev_id, tid)
            else:                                      # went pending and posted within this one sync
                announce.append(fresh[tid])
            changed = True
            continue
        match = _sheet_match(rec, expenses, claimed, item["start"])
        if match:
            rec.update(status="in_sheet", matched=match)
            claimed.add(match)
        else:
            rec["status"] = "new"                      # always your call: ✓ to log it, ✕ to trash it
        fresh[tid] = rec
        announce.append(rec)
        changed = True

    # Removed by the bank: a pending charge that posted (handled above), or one that was dropped.
    dropped = []
    for rid in removed:
        if rid in replaced:
            continue
        rec = known.get(rid) or fresh.get(rid)
        if not rec:
            continue
        if rec.get("pending") or rec["status"] == "new":
            dropped.append(rid)
            if rec["status"] == "approved" and rid in known:
                fixes[rid] = {"delete": True}
            fresh.pop(rid, None)
            changed = True

    # Brand-new approved charges go into the sheet (pending ones with the " · pending" mark).
    to_write = [r for r in fresh.values() if r["status"] == "approved" and r["id"] not in known and r["id"] not in carried]
    try:
        sheet.append_rows([sheet_row_for(r, expenses) for r in to_write])
        _apply_sheet_fixes(fixes)
    except sheet.SheetError as exc:
        for r in to_write:
            r["status"] = "new"  # couldn't write it; leave it in New so nothing is lost
        if fixes:
            db.hset("bank_sheet_fixes", fixes)
        db.set("bank_error", str(exc))
    else:
        db.delete("bank_error")

    db.hset("bank", fresh)
    gone = list(replaced) + dropped
    if gone:
        db.hdel("bank", *gone)
    if landed:
        db.hset("income_deposits", landed)
        _notify_deposits(landed.values())
    if removed:
        db.hdel("income_deposits", *removed)
        db.hdel("notifications", *[DEP + rid for rid in removed])
    # Bell: new charges get a notification; a posted charge keeps its pending one (moved to the new id,
    # amount updated); a dropped charge's notification goes away.
    _notify(r for r in announce if r["id"] in fresh)
    moved = {new: {**notes[old], "id": new, "amount": fresh[new]["amount"], "pending": False}
             for old, new in replaced.items() if old in notes and new in fresh}
    if moved:
        db.hset("notifications", moved)
    stale = [rid for rid in gone if rid in notes]
    if stale:
        db.hdel("notifications", *stale)
    for tid, rec in fresh.items():               # keep a pending flag on the bell current
        if tid in notes and tid not in moved and (notes[tid].get("pending") != rec.get("pending")
                                                  or abs(notes[tid].get("amount", 0) - rec["amount"]) > 0.005):
            db.hset("notifications", {tid: {**notes[tid], "pending": rec.get("pending"), "amount": rec["amount"]}})
    item["cursor"] = cursor
    item["last_sync"] = datetime.now(PT).isoformat(timespec="seconds")
    db.set("plaid", item)
    return {**status(), "changed": changed or bool(landed)}


# ---------- Fanvue payouts landing in the bank (Income tab) ----------
# Fanvue pays out through MassPay: the deposit shows up in checking as e.g.
# "MassPay MassPay PPD ID: 945440567" or "RYAN BELL MassPay PPD ID: 9170738439", 1-3 days after the
# payout. Those deposits are picked up live (any account on the login) and matched to the payout
# records in payouts.py; a payout made after those records gets its own row from the deposit.

PAYOUT_WORDS = ("masspay",)
PAYOUTS_FROM = "2026-04-01"


def _payout_deposit(t: dict) -> dict | None:
    if t.get("pending") or (t.get("amount") or 0) >= 0 or (t.get("date") or "") < PAYOUTS_FROM:
        return None
    text = " ".join(str(x) for x in (t.get("name"), t.get("merchant_name"), t.get("original_description")) if x)
    if not any(w in text.lower() for w in PAYOUT_WORDS):
        return None
    return {"id": t["transaction_id"], "date": t["date"], "amount": round(-float(t["amount"]), 2),
            "name": re.sub(r"\s{2,}", " ", t.get("name") or "MassPay").strip()}


def backfill_payout_deposits() -> None:
    """Once: MassPay deposits already in the bank's history, so older payouts get their landed date."""
    item = db.get("plaid")
    if not item or db.get("payout_deposits_done"):
        return
    today = datetime.now(PT).date().isoformat()
    if db.get("payout_deposits_try") == today:
        return
    db.set("payout_deposits_try", today)
    found, offset = {}, 0
    while True:
        try:
            page = _plaid("/transactions/get", {"access_token": item["access_token"], "start_date": PAYOUTS_FROM, "end_date": today,
                                                "options": {"count": 500, "offset": offset, "include_original_description": True}})
        except BankError as exc:
            if exc.code == "PRODUCT_NOT_READY":
                db.delete("payout_deposits_try")
            return
        for t in page.get("transactions", []):
            rec = _payout_deposit(t)
            if rec:
                found[rec["id"]] = rec
        offset += len(page.get("transactions", []))
        if not page.get("transactions") or offset >= page.get("total_transactions", 0):
            break
    have = db.hgetall("income_deposits")
    found = {k: v for k, v in found.items() if k not in have}    # never undo a ✓ / ✕ you already gave
    if found:
        db.hset("income_deposits", found)
    db.set("payout_deposits_done", True)
    db.delete("income_tab")


def income_deposits() -> list[dict]:
    """MassPay deposits (Fanvue payouts that landed in the bank) you've approved, oldest first.
    Ones recorded before approvals existed (no status) count as approved."""
    return sorted((r for r in db.hgetall("income_deposits").values()
                   if "masspay" in r.get("name", "").lower() and r.get("status", "approved") == "approved"),
                  key=lambda r: (r["date"], r.get("id", "")))


DEP = "deposit:"   # bell id prefix for a payout landing in checking


def _notify_deposits(records) -> None:
    now = datetime.now(PT).isoformat(timespec="seconds")
    batch = {DEP + r["id"]: {"id": DEP + r["id"], "kind": "new", "merchant": "Fanvue payout → Chase", "amount": r["amount"],
                             "date": r["date"], "at": now, "deposit": True, **_time_fields(r)}
             for r in records if r.get("status") == "new"}
    if batch:
        db.hset("notifications", batch)


def waiting_deposits() -> list[dict]:
    return sorted((r for r in db.hgetall("income_deposits").values() if r.get("status") == "new"), key=lambda r: r["date"], reverse=True)


def skipped_deposits() -> list[dict]:
    return sorted((r for r in db.hgetall("income_deposits").values() if r.get("status") == "skipped"), key=lambda r: r["date"], reverse=True)


def decide_deposit(did: str, ok: bool) -> None:
    rec = db.hgetall("income_deposits").get(did)
    if not rec:
        raise BankError("That payout isn't in the bank feed anymore")
    rec["status"] = "approved" if ok else "skipped"
    db.hset("income_deposits", {did: rec})
    db.hdel("notifications", DEP + did)
    db.delete("income_tab")       # rewrite the Income tab with (or without) it


# ---------- Your decisions ----------

def approve(tid: str, expenses: list[dict]) -> None:
    rec = db.hgetall("bank").get(tid)
    if not rec:
        raise BankError("That charge isn't in the bank feed anymore")
    if rec["status"] != "approved":
        sheet.append_rows([sheet_row_for(rec, expenses)])  # raises if the sheet can't be written
        rec["status"] = "approved"
        db.hset("bank", {tid: rec})
    db.hset("merchant_rules", {rec["provider"]: "approve"})
    _drop_new_notification(tid)


def skip(tid: str) -> None:
    rec = db.hgetall("bank").get(tid)
    if not rec:
        raise BankError("That charge isn't in the bank feed anymore")
    if rec["status"] == "new":
        rec["status"] = "skipped"
        db.hset("bank", {tid: rec})
    db.hset("merchant_rules", {rec["provider"]: "skip"})
    _drop_new_notification(tid)


def _drop_new_notification(tid: str) -> None:
    """Once you've decided on a charge, its "needs approval" notification is done."""
    note = db.hgetall("notifications").get(tid)
    if note and note.get("kind") == "new":
        db.hdel("notifications", tid)


def _time_fields(r: dict) -> dict:
    return {k: r.get(k) for k in ("time", "time_exact", "seen_day")}


def _back_to_new(known: dict) -> None:
    """Once: charges the old merchant rule logged on its own (their bell note still says "logged")
    come out of the sheet and go back to New for your ✓ / ✕."""
    if db.get("auto_log_undone"):
        return
    notes = db.hgetall("notifications")
    auto = [tid for tid, n in notes.items() if n.get("kind") == "auto" and known.get(tid, {}).get("status") == "approved"]
    if auto:
        db.hset("bank", {tid: {**known[tid], "status": "new"} for tid in auto})
        db.hset("bank_sheet_fixes", {tid: {"delete": True} for tid in auto})
        db.hset("notifications", {tid: {**notes[tid], "kind": "new"} for tid in auto})
        for tid in auto:
            known[tid] = {**known[tid], "status": "new"}
    db.set("auto_log_undone", True)


# ---------- Notifications (the bell) ----------
# One per new charge, keyed by the charge id:
#   kind "auto" = logged to the sheet automatically (you approved this merchant before)
#   kind "new"  = waiting for your approval in Expenses > New

def _notify(records) -> None:
    now = datetime.now(PT).isoformat(timespec="seconds")
    batch = {}
    for r in records:
        if r["status"] == "new":
            batch[r["id"]] = {"id": r["id"], "kind": "new", "merchant": r["merchant"], "amount": r["amount"], "date": r["date"], "at": now,
                              "pending": bool(r.get("pending")), **_time_fields(r)}
    if batch:
        db.hset("notifications", batch)


def notifications() -> list[dict]:
    return sorted(db.hgetall("notifications").values(), key=lambda n: (n.get("at", ""), n.get("date", "")), reverse=True)


def clear_notifications(tid: str | None = None) -> None:
    if tid:
        db.hdel("notifications", tid)
    else:
        db.delete("notifications")


def waiting() -> list[dict]:
    return sorted((r for r in db.hgetall("bank").values() if r["status"] == "new"), key=lambda r: r["date"], reverse=True)


def skipped() -> list[dict]:
    return sorted((r for r in db.hgetall("bank").values() if r["status"] == "skipped"), key=lambda r: r["date"], reverse=True)
