"""
SRM Dashboard: private earnings dashboard (FastAPI on Vercel).

Files:
  server.py  web routes + password login
  calc.py    all money math
  fanvue.py  Fanvue login + earnings sync
  sheet.py   expenses from the live Google Sheet
  bank.py    card charges from Plaid
  store.py   saved data (Upstash Redis on Vercel)
  agenda.py  calendar: to-dos + timed reminders, scheduled by voice / typing (Grok)
  webpush.py phone push notifications for reminders
  morning.py the "Good morning, Ryan" brief (once a day after 6 AM)
  whoop.py   WHOOP band: sleep, recovery, strain
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sys
import time

import requests
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # let Vercel find the files next to this one

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

import agenda
import morning
import weather
import whoop
import bank
import calc
import chatter
import fanvue
import feed
import monthly
import oneoff
import payouts
import sheet
import webpush
from store import db

STATIC = Path(__file__).resolve().parent / "static"
MODELS = [{"id": "levity-pavic", "name": "Levity Pavic"}]
DEFAULT_SETTINGS = {"fanvue_rate": 0.20, "chatter_rate": 0.25, "tax_rate": 0.0, "tax_enabled": False}
SESSION_SECONDS = 30 * 24 * 3600

app = FastAPI(title="SRM Dashboard", docs_url=None, redoc_url=None, openapi_url=None)


# ---------- Login ----------

def _password() -> str:
    pw = os.environ.get("DASH_PASSWORD", "")
    if not pw:
        raise HTTPException(503, "DASH_PASSWORD is not set in Vercel")
    return pw


def _sign(expires: str) -> str:
    key = hashlib.sha256(("srm-session|" + _password()).encode()).digest()
    return hmac.new(key, expires.encode(), hashlib.sha256).hexdigest()


def logged_in(request: Request) -> bool:
    expires, _, sig = request.cookies.get("srm_session", "").partition(".")
    return expires.isdigit() and int(expires) > time.time() and hmac.compare_digest(sig, _sign(expires))


def require_login(request: Request) -> None:
    if not logged_in(request):
        raise HTTPException(401, "Sign in required")


def _https(request: Request) -> bool:
    return (request.headers.get("x-forwarded-proto") or request.url.scheme) == "https"


class LoginBody(BaseModel):
    password: str


@app.post("/api/login")
def login(body: LoginBody, request: Request):
    if not hmac.compare_digest(body.password.encode(), _password().encode()):
        time.sleep(1)  # slow down password guessing
        raise HTTPException(401, "Wrong password")
    expires = str(int(time.time()) + SESSION_SECONDS)
    resp = JSONResponse({"ok": True})
    resp.set_cookie("srm_session", f"{expires}.{_sign(expires)}", max_age=SESSION_SECONDS,
                    httponly=True, secure=_https(request), samesite="lax")
    return resp


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


# App icon: browser tab + iPhone home screen ("Add to Home Screen").
ICONS = {
    "favicon.ico": "favicon.ico",
    "favicon-32.png": "favicon-32.png",
    "apple-touch-icon.png": "apple-touch-icon.png",
    "apple-touch-icon-precomposed.png": "apple-touch-icon.png",
    "icon-192.png": "icon-192.png",
    "icon-512.png": "icon-512.png",
}
@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    """Lets "Add to Home Screen" open the dashboard full-screen, like an app."""
    return JSONResponse({
        "name": "SRM Dashboard", "short_name": "SRM", "id": "/", "start_url": "/", "scope": "/",
        "display": "standalone", "background_color": "#141519", "theme_color": "#141519",
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
        ],
    }, media_type="application/manifest+json", headers={"Cache-Control": "public, max-age=3600"})


for _url, _file in ICONS.items():
    app.add_api_route("/" + _url, lambda f=_file: FileResponse(STATIC / f, headers={"Cache-Control": "public, max-age=604800"}),
                      methods=["GET"], include_in_schema=False)


# ---------- Settings ----------

def get_settings() -> dict:
    return {**DEFAULT_SETTINGS, **(db.get("settings") or {})}


class SettingsBody(BaseModel):
    fanvue_rate: float = Field(ge=0, le=0.9)
    chatter_rate: float = Field(ge=0, le=0.9)
    tax_enabled: bool = False


@app.post("/api/settings", dependencies=[Depends(require_login)])
def save_settings(body: SettingsBody):
    """A new Fanvue % / Chatter % never rewrites the past: it switches on at the start of next
    week (calc.schedule_rates). Changing it again before then just replaces the pending switch."""
    settings = get_settings()
    agency_today = datetime.now(calc.AGENCY_TZ).date()   # weeks turn over on the Serbian clock
    settings["rate_history"] = calc.schedule_rates(settings, body.fanvue_rate, body.chatter_rate, agency_today)
    settings["tax_enabled"] = body.tax_enabled
    db.set("settings", settings)
    return {**settings, "rates": calc.rate_status(settings, agency_today)}


# ---------- Dashboard ----------

def _load_everything(force_sheet: bool = False):
    warnings = []
    try:
        expenses = sheet.load_expenses(force_sheet)
    except sheet.SheetError as exc:
        expenses = []
        warnings.append(str(exc) + " Expenses show as $0 until this is fixed.")
    except Exception as exc:  # never let the sheet take the whole page down
        expenses = []
        warnings.append(f"Couldn't read the Google Sheet ({exc}).")
    if db.kind == "local" and os.environ.get("VERCEL"):
        warnings.append("Storage isn't connected in Vercel, so the Fanvue login and history won't stick (see README).")
    return db.hgetall("days"), expenses, warnings


def _first_days(days: dict, expenses: list[dict], today: date) -> tuple[date, date]:
    first_earning = date.fromisoformat(min(days)) if days else today
    first_expense = date.fromisoformat(min(e["date"] for e in expenses)) if expenses else first_earning
    return min(first_earning, first_expense), first_earning


def _sync_income_tab(days: dict, expenses: list[dict], settings: dict, today: date) -> None:
    """Keep the sheet's Income tab current: Fanvue gross per month (business income), what it cost
    (Fanvue fee, chatting, OPEX) and the profit left, plus the payouts table. Same math as the
    dashboard's Net (before tax). Rewrites only when something changed; the live month's earnings and
    chatting estimate refresh at most every 30 min."""
    if not sheet.configured() or not expenses:      # never write $0 costs because the sheet didn't load
        return
    gross = calc.gross_by_month(days, today)
    fees = {m["month"]: m["amount"] for m in calc.fanvue_months(days, settings, today)}
    logged = sheet.fanvue_logged()
    chatting: dict[str, float] = {}
    for d, v in calc.chatter_cost_by_day(days, expenses, settings, today).items():
        chatting[d[:7]] = chatting.get(d[:7], 0.0) + v
    opex: dict[str, float] = {}
    for e in expenses:
        if e["status"] == "verified" and e["category"].lower() not in calc.CHATTER_CATEGORIES and e["date"] <= today.isoformat():
            opex[e["date"][:7]] = opex.get(e["date"][:7], 0.0) + e["amount"]
    current = today.isoformat()[:7]
    months = [{"month": m, "gross": round(gross.get(m, 0.0), 2), "fee": logged.get(m, fees.get(m, 0.0)),
               "fee_logged": m in logged, "live": m == current,
               "chatting": round(chatting.get(m, 0.0), 2), "opex": round(opex.get(m, 0.0), 2)} for m in sheet._months(today)]
    deposits = payouts.merged(bank.income_deposits(), payouts.live_payouts(), today.isoformat())
    sig = hashlib.sha1(repr((months, deposits, sheet.INCOME_NOTES)).encode()).hexdigest()
    shape = repr(([(m["month"], m["fee_logged"], m["opex"], None if m["live"] else m["chatting"]) for m in months],
                  [d["id"] for d in deposits], sheet.INCOME_NOTES, "profit-v1"))
    last = db.get("income_tab") or {}
    if last.get("sig") == sig:
        return
    if last.get("shape") == shape and time.time() - last.get("at", 0) < 1800:
        return                          # only the live month's numbers moved; refresh later
    sheet.write_income_tab(months, deposits, today)
    db.set("income_tab", {"sig": sig, "shape": shape, "at": time.time()})


@app.get("/api/dashboard", dependencies=[Depends(require_login)])
def dashboard(request: Request, range_key: str = Query("today", alias="range"), fresh: bool = False,
              start: date | None = None, end: date | None = None):
    """fresh=1 on page load re-reads the Google Sheet right away (new bank charges)."""
    now = datetime.now(fanvue.PT)
    today = now.date()
    settings = get_settings()
    days, expenses, warnings = _load_everything(force_sheet=fresh)
    try:  # side tables in the sheet (Fixed Expenses + Chatting list); only writes when something's missing
        backfill = {m["month"]: m["amount"] for m in calc.fanvue_months(days, settings, today)}
        if sheet.ensure_layout(today, backfill, lambda kid: chatter.invoice_item(kid, expenses, settings)):
            expenses = sheet.load_expenses(force=True)
    except Exception as exc:
        warnings.append(f"Couldn't update the sheet's Fixed Expenses table ({exc}).")
    try:  # one-off purchases that don't come through a bank feed (oneoff.py), written once
        if sheet.configured() and oneoff.ensure(expenses):
            expenses = sheet.load_expenses(force=True)
    except Exception as exc:
        warnings.append(f"Couldn't add a one-off expense to the sheet ({exc}).")
    try:
        _sync_income_tab(days, expenses, settings, today)
    except Exception as exc:
        warnings.append(f"Couldn't update the sheet's Income tab ({exc}).")
    try:
        chatter.ensure_drafts(days, expenses, settings, now)  # weekly agency invoice → Expenses > New
    except Exception as exc:  # never let it take the page down
        warnings.append(f"Couldn't draft this week's chatting invoice ({exc}).")
    try:
        if sheet.configured():
            monthly.ensure_drafts(days, settings, today, sheet.fanvue_logged())  # month-end Fanvue → Expenses > New
    except Exception as exc:
        warnings.append(f"Couldn't draft last month's Fanvue expense ({exc}).")
    rng = calc.resolve_range(range_key, today, *_first_days(days, expenses, today), start=start, end=end)
    fv, bk = fanvue.status(), bank.status()
    if fv["error"]:
        warnings.append("Fanvue: " + fv["error"])
    if bk["error"] and not (bk.get("source") == "grok" and feed.status()["error"]):
        warnings.append("Bank: " + bk["error"])
    warnings.extend(feed.warnings())
    if bk["connected"] and not bk["mask_found"]:
        warnings.append(f"Bank: no card ending {bank.CARD_MASK} found, so every account on that login is being tracked.")
    return {
        "range": {"key": rng["key"], "label": rng["label"], "kind": rng["kind"],
                  "start": rng["lo"].isoformat(), "end": rng["hi"].isoformat()},
        "ranges": [{"key": k, "label": label} for k, label in calc.RANGES],
        "totals": calc.totals(days, calc.spread_expenses(expenses, db.hgetall(SPREADS)), settings, rng["lo"], rng["hi"], today),
        "chart": calc.chart_points(days, settings, rng, now),
        "settings": settings,
        "rates": calc.rate_status(settings, now.astimezone(calc.AGENCY_TZ).date()),
        "models": MODELS,
        "fanvue": fv,
        "bank": bk,
        "card_feed": {**feed.status(), "setup_message": feed.setup_message(_base_url(request)) if feed.active() else ""},
        "pending_expenses": len(bank.waiting()) + len(bank.waiting_deposits()) + len(chatter.waiting()) + len(monthly.waiting()) + len(chatter.coinbase_waiting()),
        "notifications": bank.notifications(),
        "sheet_url": sheet.SHEET_URL,
        "clock": now.strftime("%b %-d, %Y · %-I:%M %p PT"),
        "today": today.isoformat(),
        "business_start": calc.BUSINESS_START.isoformat(),
        "warnings": warnings,
    }


# ---------- Fanvue payout events (webhook) ----------

def _webhook_ok(request: Request, raw: bytes) -> bool:
    """Fanvue signs deliveries; accept either of its documented formats:
    X-Fanvue-Signature "t=<ts>,v0=<hex HMAC-SHA256 of '<ts>.<body>'>", or Standard-Webhooks
    headers (webhook-id / webhook-timestamp / webhook-signature "v1,<base64 HMAC of 'id.ts.body'>")."""
    import base64 as b64
    secret = os.environ.get("FANVUE_WEBHOOK_SECRET", "")
    if not secret:
        return False
    key = b64.b64decode(secret[6:]) if secret.startswith("whsec_") else secret.encode()
    now = time.time()
    sig = request.headers.get("x-fanvue-signature", "")
    if sig:
        parts = dict(p.split("=", 1) for p in sig.split(",") if "=" in p)
        ts, v0 = parts.get("t", ""), parts.get("v0", "")
        if not ts.isdigit() or abs(now - int(ts)) > 300 or not v0:
            return False
        good = hmac.new(key, f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
        return hmac.compare_digest(good, v0)
    wid, ts, wsig = (request.headers.get(h, "") for h in ("webhook-id", "webhook-timestamp", "webhook-signature"))
    if not (wid and ts.isdigit() and wsig) or abs(now - int(ts)) > 300:
        return False
    good = b64.b64encode(hmac.new(key, f"{wid}.{ts}.".encode() + raw, hashlib.sha256).digest()).decode()
    return any(hmac.compare_digest(good, part.split(",", 1)[-1]) for part in wsig.split())


@app.post("/api/fanvue/webhook", include_in_schema=False)
async def fanvue_webhook(request: Request):
    """Fanvue calls this when a payout settles (payout.paid) or fails: the Income tab's payouts
    table updates on the next dashboard load."""
    raw = await request.body()
    if not os.environ.get("FANVUE_WEBHOOK_SECRET"):
        raise HTTPException(503, "FANVUE_WEBHOOK_SECRET is not set in Vercel")
    if not _webhook_ok(request, raw):
        raise HTTPException(401, "Bad signature")
    import json as _json
    try:
        event = _json.loads(raw)
    except ValueError as exc:
        raise HTTPException(400, "Not JSON") from exc
    if payouts.record_webhook(event):
        db.delete("income_tab")             # rewrite the Income tab on the next load
    return {"ok": True}


@app.post("/api/sync", dependencies=[Depends(require_login)])
def sync(gap: int = 0):
    """Called on every page load. The page repeats it while done is false (first-time history pull).
    gap=N (the open page's background refresh): skip Fanvue when it was already pulled in the last N seconds
    (by any device), so a laptop and a phone left open never double up on Fanvue."""
    if not fanvue.is_connected():
        return {"connected": False, "done": True}
    if gap > 0:
        st = fanvue.status()
        try:
            age = (datetime.now(fanvue.PT) - datetime.fromisoformat(st["last_sync"])).total_seconds() if st["last_sync"] else None
        except (TypeError, ValueError):
            age = None
        if not st["backfilling"] and age is not None and 0 <= age < min(gap, 600):
            return {"connected": True, "done": True, "skipped": True}
    return fanvue.sync()


def _plaid_webhook_url(request: Request) -> str:
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    return os.environ.get("PLAID_WEBHOOK_URL") or (f"https://{host}/api/plaid/webhook" if host and "localhost" not in host else "")


@app.post("/api/bank/sync", dependencies=[Depends(require_login)])
def bank_sync(request: Request):
    """Called on every page load (and every few minutes while the page is open): pulls new card
    charges from Plaid, pending ones included."""
    try:
        if not feed.active():
            bank.ensure_webhook(_plaid_webhook_url(request))   # once: Plaid pings us when new charges arrive
    except Exception:  # noqa: BLE001 - never block the sync on this
        pass
    return _run_bank_sync()


@app.post("/api/plaid/webhook", include_in_schema=False)
async def plaid_webhook(request: Request):
    """Plaid's "new transactions" ping: sync right away, so charges land even with the page closed.
    The body is only a hint; everything is pulled from Plaid itself, so a fake ping can only cause
    an extra sync (at most one every 20 seconds)."""
    try:
        event = await request.json()
    except Exception:  # noqa: BLE001
        return {"ok": False}
    if not bank.wants_webhook(event) or not db.set_nx("plaid_hook_lock", 1, 20):
        return {"ok": True, "synced": False}
    try:
        _run_bank_sync()
    except Exception:  # noqa: BLE001 - Plaid only needs a 200
        pass
    return {"ok": True, "synced": True}


def _run_bank_sync():
    if feed.active():                     # Grok Bot pushes charges to /api/card-feed; Plaid is closed
        return bank.status()
    if not bank.status()["connected"]:
        return bank.status()
    try:
        expenses = sheet.load_expenses(force=True)
    except sheet.SheetError as exc:
        db.set("bank_error", f"Bank sync waited: {exc}")
        return bank.status()
    result = bank.sync(expenses)
    try:
        bank.backfill_payout_deposits()   # once: MassPay deposits already in the bank -> "Landed in Chase"
    except Exception:  # noqa: BLE001 - never block the page on this
        pass
    return result


# ---------- Card feed from Grok Bot (feed.py) ----------

def _base_url(request: Request) -> str:
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https").split(",")[0].strip()
    return os.environ.get("PUBLIC_URL", "").rstrip("/") or f"{proto}://{host}"


def _feed_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    return (auth[7:].strip() if auth.lower().startswith("bearer ") else "") or request.headers.get("x-feed-key", "") \
        or request.query_params.get("key", "")


@app.post("/api/card-feed", include_in_schema=False)
async def card_feed(request: Request):
    """Grok Bot's sweep: {"window_start", "window_end", "complete", "transactions": [...]} or {"error": "..."}."""
    if not feed.key_ok(_feed_key(request)):
        raise HTTPException(401, "Wrong or missing key")
    try:
        payload = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, "The body must be JSON") from exc
    if isinstance(payload, list):
        payload = {"transactions": payload}
    if not isinstance(payload, dict):
        raise HTTPException(400, 'Send a JSON object: {"transactions": [...]}')
    try:
        expenses = sheet.load_expenses(force=True)
    except sheet.SheetError as exc:
        raise HTTPException(503, f"The Google Sheet can't be read right now ({exc}); send again later") from exc
    try:
        return feed.ingest(payload, expenses)
    except feed.FeedError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/card-feed/instructions", include_in_schema=False)
def card_feed_instructions(request: Request):
    if not feed.key_ok(_feed_key(request)):
        raise HTTPException(401, "Wrong or missing key")
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(feed.instructions(_base_url(request)))


@app.get("/api/card-feed/status", include_in_schema=False)
def card_feed_status(request: Request):
    if not feed.key_ok(_feed_key(request)):
        raise HTTPException(401, "Wrong or missing key")
    return {**feed.status(), "waiting_pending": [
        {"date": r["date"], "merchant": r["merchant"], "amount": r["amount"]}
        for r in db.hgetall("bank").values() if r.get("pending")]}


@app.post("/api/card-feed/setup", dependencies=[Depends(require_login)])
def card_feed_setup(request: Request):
    feed.setup(sheet.load_expenses())
    return {"message": feed.setup_message(_base_url(request)), **feed.status()}


@app.post("/api/card-feed/rotate", dependencies=[Depends(require_login)])
def card_feed_rotate(request: Request):
    try:
        feed.rotate()
    except feed.FeedError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"message": feed.setup_message(_base_url(request)), **feed.status()}


class ConnectBody(BaseModel):
    public_token: str = ""
    institution: str = ""


@app.post("/api/bank/link-token", dependencies=[Depends(require_login)])
def bank_link_token(request: Request):
    try:
        return bank.link_token(_plaid_webhook_url(request))
    except bank.BankError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/bank/connect", dependencies=[Depends(require_login)])
def bank_connect(body: ConnectBody):
    try:
        if not body.public_token:  # finished logging back in to an existing connection
            bank.finished_relogin()
        else:
            bank.connect(body.public_token, body.institution, sheet.load_expenses(force=True))
    except (bank.BankError, sheet.SheetError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return _run_bank_sync()


@app.post("/api/bank/{tid}/approve", dependencies=[Depends(require_login)])
def bank_approve(tid: str):
    try:
        bank.approve(tid, sheet.load_expenses())
    except (bank.BankError, sheet.SheetError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


@app.post("/api/bank/{tid}/skip", dependencies=[Depends(require_login)])
def bank_skip(tid: str):
    try:
        bank.skip(tid)
    except bank.BankError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


@app.post("/api/deposit/{did}/approve", dependencies=[Depends(require_login)])
def deposit_approve(did: str):
    """A Fanvue payout that landed in checking: ✓ = it goes on the Income tab."""
    try:
        bank.decide_deposit(did, True)
    except bank.BankError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


@app.post("/api/deposit/{did}/skip", dependencies=[Depends(require_login)])
def deposit_skip(did: str):
    try:
        bank.decide_deposit(did, False)
    except bank.BankError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


class AmountBody(BaseModel):
    amount: float = Field(ge=0, le=1_000_000)


@app.post("/api/chatter/{kid}/approve", dependencies=[Depends(require_login)])
def chatter_approve(kid: str, body: AmountBody):
    try:
        chatter.approve(kid, body.amount, sheet.load_expenses(), get_settings(), datetime.now(fanvue.PT).date())
    except (chatter.ChatterError, sheet.SheetError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


@app.post("/api/coinbase-payout/{kid}/approve", dependencies=[Depends(require_login)])
def coinbase_payout_approve(kid: str, body: AmountBody):
    try:
        chatter.coinbase_approve(kid, body.amount, datetime.now(fanvue.PT).date())
    except chatter.ChatterError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


@app.post("/api/coinbase-payout/{kid}/skip", dependencies=[Depends(require_login)])
def coinbase_payout_skip(kid: str):
    try:
        chatter.coinbase_skip(kid)
    except chatter.ChatterError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


@app.post("/api/chatter/{kid}/skip", dependencies=[Depends(require_login)])
def chatter_skip(kid: str):
    try:
        chatter.skip(kid)
    except chatter.ChatterError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


@app.post("/api/fanvue-month/{month}/approve", dependencies=[Depends(require_login)])
def fanvue_month_approve(month: str, body: AmountBody):
    try:
        monthly.approve(month, body.amount, datetime.now(fanvue.PT).date())
    except (monthly.MonthlyError, sheet.SheetError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


@app.post("/api/fanvue-month/{month}/skip", dependencies=[Depends(require_login)])
def fanvue_month_skip(month: str):
    try:
        monthly.skip(month)
    except monthly.MonthlyError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


@app.post("/api/notifications/clear", dependencies=[Depends(require_login)])
def notifications_clear_all():
    bank.clear_notifications()
    return {"ok": True}


@app.post("/api/notifications/{tid}/clear", dependencies=[Depends(require_login)])
def notification_clear(tid: str):
    bank.clear_notifications(tid)
    return {"ok": True}


@app.post("/api/tax/estimate", dependencies=[Depends(require_login)])
def tax_estimate():
    today = datetime.now(fanvue.PT).date()
    settings = {**get_settings(), "tax_enabled": False}
    days, expenses, _ = _load_everything()
    year_start = max(today.replace(month=1, day=1), calc.BUSINESS_START)
    profit = calc.totals(days, expenses, settings, year_start, today, today)["after_opex"]
    estimate = calc.estimate_tax(profit)
    db.set("settings", {**get_settings(), "tax_rate": estimate["rate"]})
    return {"profit_ytd": profit, **estimate}


# ---------- Expenses desk ----------

def _group_by_provider(rows: list[dict]) -> list[dict]:
    """One entry per merchant: total, number of charges (an "(x3 units)" row counts as 3), latest date, charges."""
    groups: dict[str, dict] = {}
    for e in rows:
        g = groups.setdefault(e["provider"], {"provider": e["provider"], "total": 0.0, "count": 0, "last": e["date"],
                                              "chatter": True, "items": []})
        g["total"] = round(g["total"] + e["amount"], 2)
        g["count"] += e["qty"]
        g["last"] = max(g["last"], e["date"])
        g["chatter"] = g["chatter"] and e["category"].lower() in calc.CHATTER_CATEGORIES
        g["items"].append({**{k: e[k] for k in ("id", "date", "item", "category", "amount", "qty")}, "pending": bool(e.get("pending")),
                           **({"spread": e["spread"]} if e.get("spread") else {})})
    return sorted(groups.values(), key=lambda g: (-g["total"], g["provider"]))


@app.get("/api/expenses", dependencies=[Depends(require_login)])
def expenses_desk():
    try:
        expenses = sheet.load_expenses(force=True)
    except sheet.SheetError as exc:
        raise HTTPException(503, str(exc)) from exc
    newest_first = sorted(expenses, key=lambda e: e["date"], reverse=True)
    verified = sorted(calc.spread_expenses([e for e in newest_first if e["status"] == "verified"], db.hgetall(SPREADS)),
                      key=lambda e: e["date"], reverse=True)
    trashed = [{**e, "kind": "sheet"} for e in newest_first if e["status"] == "trash"]
    trashed += [{**r, "item": r["merchant"], "kind": "bank"} for r in bank.skipped()]
    trashed += [{**r, "item": "Fanvue payout landed in Chase", "kind": "deposit"} for r in bank.skipped_deposits()]
    now = datetime.now(fanvue.PT)
    today = now.date()
    days = db.hgetall("days")
    settings = get_settings()
    logged = sheet.fanvue_logged()
    drafts = {d["id"]: d["amount"] for d in monthly.waiting()}
    # Fanvue per month: what's in the sheet if confirmed, otherwise the live calculation.
    months = [{**m, "logged": logged.get(m["month"]), "draft": drafts.get(m["month"])}
              for m in calc.fanvue_months(days, settings, today)]
    return {
        "month": today.isoformat()[:7],
        "business_start": calc.BUSINESS_START.isoformat(),
        "gross_months": calc.gross_by_month(days, today),
        "pending": [{**r, "item": r["merchant"]} for r in bank.waiting()],
        "deposits": bank.waiting_deposits(),
        "chatter_drafts": chatter.waiting(),
        "coinbase_drafts": chatter.coinbase_waiting(),
        "chatter_live": chatter.live_week(days, settings, now),
        "fanvue_drafts": monthly.waiting(),
        "fanvue": {"months": months},
        "verified": _group_by_provider(verified),
        "trash": sorted(trashed, key=lambda e: e["date"], reverse=True),
        "bank": bank.status(),
        "sheet_url": sheet.SHEET_URL,
    }


class StatusBody(BaseModel):
    status: str


class ProviderBody(BaseModel):
    provider: str


@app.post("/api/expenses/{expense_id}/status", dependencies=[Depends(require_login)])
def set_expense_status(expense_id: str, body: StatusBody):
    if body.status not in ("verified", "trash"):
        raise HTTPException(400, "status must be verified or trash")
    db.hset("expense_status", {expense_id: body.status})
    return {"ok": True}


SPREADS = "expense_spread"   # expense id → months (Monthly payment: dashboard OPEX only, the sheet is untouched)


class SpreadBody(BaseModel):
    months: int = Field(ge=0, le=60)


@app.post("/api/expenses/{expense_id}/spread", dependencies=[Depends(require_login)])
def set_expense_spread(expense_id: str, body: SpreadBody):
    if body.months >= 2:
        db.hset(SPREADS, {expense_id: body.months})
    else:
        db.hdel(SPREADS, expense_id)
    return {"ok": True, "months": body.months if body.months >= 2 else 0}


@app.post("/api/providers/trash", dependencies=[Depends(require_login)])
def trash_provider(body: ProviderBody):
    rows = [e for e in sheet.load_expenses() if e["provider"] == body.provider and e["status"] == "verified"]
    db.hset("expense_status", {e["id"]: "trash" for e in rows})
    db.hset("merchant_rules", {body.provider: "skip"})  # future card charges from them get skipped too
    return {"ok": True, "trashed": len(rows)}


# ---------- Fanvue login ----------

def _redirect_uri(request: Request) -> str:
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    return os.environ.get("FANVUE_REDIRECT_URI") or f"https://{host}/api/fv-callback"


def fanvue_start(request: Request):
    if not logged_in(request):
        return RedirectResponse("/")
    if not fanvue.CLIENT_SECRET:
        db.set("fanvue_error", "FANVUE_CLIENT_SECRET is not set in Vercel")
        return RedirectResponse("/?fanvue=error")
    redirect_uri = _redirect_uri(request)
    url, state, verifier = fanvue.login_url(redirect_uri)
    resp = RedirectResponse(url, status_code=302)
    for name, value in (("fv_state", state), ("fv_verifier", verifier), ("fv_redirect", redirect_uri)):
        resp.set_cookie(name, value, max_age=600, httponly=True, secure=_https(request), samesite="lax")
    return resp


def fanvue_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    if error or not code:
        return RedirectResponse("/?fanvue=denied")
    if not state or state != request.cookies.get("fv_state") or not request.cookies.get("fv_verifier"):
        return RedirectResponse("/?fanvue=expired")
    try:
        fanvue.finish_login(code, request.cookies["fv_verifier"], request.cookies.get("fv_redirect") or _redirect_uri(request))
    except fanvue.FanvueError as exc:
        db.set("fanvue_error", str(exc))
        return RedirectResponse("/?fanvue=error")
    resp = RedirectResponse("/?fanvue=ok")
    for name in ("fv_state", "fv_verifier", "fv_redirect"):
        resp.delete_cookie(name)
    return resp


# Both spellings, so whichever redirect URL is saved in your Fanvue app keeps working.
for _path in ("/api/fanvue/start", "/api/fv-start"):
    app.add_api_route(_path, fanvue_start, methods=["GET"])
for _path in ("/api/fanvue/callback", "/api/fv-callback"):
    app.add_api_route(_path, fanvue_callback, methods=["GET"])


# ---------- Calendar (agenda.py) + phone notifications (webpush.py) ----------

class AgendaParseBody(BaseModel):
    text: str = Field(min_length=1, max_length=800)


class AgendaAddBody(BaseModel):
    items: list[dict] = Field(max_length=10)


class AgendaPatchBody(BaseModel):
    done: bool | None = None
    title: str | None = Field(default=None, max_length=200)
    date: str | None = None
    time: str | None = None
    kind: str | None = None
    dismissed: bool | None = None       # ✕ on its "coming up" line in the bell


@app.get("/api/agenda", dependencies=[Depends(require_login)])
def agenda_day(day: str = "", all: bool = False):
    if all:                                # the calendar's normal load: everything, days are switched on the phone
        return agenda.everything()
    today = agenda.now_pt().date().isoformat()
    try:
        picked = date.fromisoformat(day).isoformat() if day else today
    except ValueError:
        picked = today
    view = agenda.day_view(max(picked, today))
    view["soon"] = agenda.upcoming()
    return view


@app.get("/api/agenda/soon", dependencies=[Depends(require_login)])
def agenda_soon():
    """Light poll for the yellow / red banner on the dashboard."""
    return {"soon": agenda.upcoming()}


@app.post("/api/agenda/parse", dependencies=[Depends(require_login)])
def agenda_parse(body: AgendaParseBody):
    return agenda.parse(body.text)


@app.post("/api/agenda/items", dependencies=[Depends(require_login)])
def agenda_add(body: AgendaAddBody):
    return {"items": agenda.add(body.items)}


@app.patch("/api/agenda/items/{item_id}", dependencies=[Depends(require_login)])
def agenda_patch(item_id: str, body: AgendaPatchBody):
    item = agenda.update(item_id, {k: v for k, v in body.model_dump().items() if v is not None})
    if not item:
        raise HTTPException(404, "That reminder is gone.")
    return {"item": item}


@app.delete("/api/agenda/items/{item_id}", dependencies=[Depends(require_login)])
def agenda_delete(item_id: str):
    agenda.remove(item_id)
    return {"ok": True}


@app.post("/api/agenda/transcribe", dependencies=[Depends(require_login)])
async def agenda_transcribe(request: Request, parse: bool = False):
    """The recording comes in as the raw request body (audio/webm or audio/mp4 from the phone).
    parse=1 also reads it (day, time, task) in the same call, so there's one wait instead of two."""
    audio = await request.body()
    if len(audio) > 8_000_000:
        raise HTTPException(413, "That recording is too long. Keep it under a minute.")
    kind = (request.headers.get("content-type") or "audio/webm").split(";")[0]
    name = "speech.mp4" if "mp4" in kind or "m4a" in kind or "aac" in kind else "speech.webm"
    try:
        text = agenda.transcribe(audio, name, kind)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(503, str(exc))
    if not parse or not text:
        return {"text": text}
    return {"text": text, **agenda.parse(text)}


@app.get("/api/agenda/tick", include_in_schema=False)
def agenda_tick(request: Request):
    """Vercel cron (every minute, see vercel.json): sends due reminders. Safe to call any time."""
    secret = os.environ.get("CRON_SECRET", "")
    if secret and request.headers.get("authorization", "") != f"Bearer {secret}":
        raise HTTPException(401, "Not allowed")
    return agenda.tick()


@app.get("/api/push/key", dependencies=[Depends(require_login)])
def push_key():
    return {"key": webpush.public_key()}


@app.post("/api/push/subscribe", dependencies=[Depends(require_login)])
async def push_subscribe(request: Request):
    try:
        webpush.save_subscription(await request.json(), _base_url(request))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@app.post("/api/push/test", dependencies=[Depends(require_login)])
def push_test(sample: bool = False):
    """First turn-on: one ✅. "Send test" in the calendar: the two real reminder messages, so you see exactly what comes."""
    if not sample:
        report = webpush.send_report("✅ Reminders are on", "You'll get a ⏳ an hour before and a ⚠️ ten minutes before.", "srm-test")
        return {"sent": report["sent"], "devices": report["devices"], "results": report["results"]}
    hour = webpush.send_report("⏳ Call the bank (test)", "In 1 hour · 3:00 PM", "srm-test-hr")
    ten = webpush.send_report("⚠️ Call the bank (test)", "In 10 minutes · 3:00 PM", "srm-test-ten")
    return {"sent": min(hour["sent"], ten["sent"]), "devices": ten["devices"], "results": ten["results"] or hour["results"]}


# ---------- Morning brief (morning.py) + WHOOP (whoop.py) ----------

@app.get("/api/morning/status", dependencies=[Depends(require_login)])
def morning_status(device: str = "desktop"):
    device = morning.device_of(device)   # the computer and the phone each get their own showing
    return {"due": morning.due("morning", device), "afternoon_due": morning.due("afternoon", device),
            "evening_due": morning.due("evening", device), "whoop": {"configured": whoop.configured(), "connected": whoop.connected(),
                                             "error": db.get("whoop:error") or ""}}


class MorningBody(BaseModel):
    lat: float | None = None      # where the device is (its own location services), for the morning weather
    lon: float | None = None
    city: str = ""


@app.post("/api/morning", dependencies=[Depends(require_login)])
def morning_build(request: Request, body: MorningBody | None = None, kind: str = "morning"):
    """Pulled live when it opens (the page has just synced Fanvue): WHOOP, overnight money, your day, the script."""
    pending = len(bank.waiting()) + len(bank.waiting_deposits()) + len(chatter.waiting()) + len(monthly.waiting()) + len(chatter.coinbase_waiting())
    if kind == "afternoon":   # 2 to 7:59 PM: strain + workouts + steps, today's money, tasks
        return morning.build_afternoon(db.hgetall("days"), get_settings())
    if kind == "evening":     # 8 PM to midnight: today's money, the checklist, the full training day, tonight's bedtime
        return morning.build_evening(db.hgetall("days"), get_settings(), pending)
    spot = weather.location(body.lat if body else None, body.lon if body else None, body.city if body else "",
                            ip=weather.from_headers(request.headers))
    return morning.build(db.hgetall("days"), get_settings(), pending, spot)


@app.get("/api/morning/intro", dependencies=[Depends(require_login)])
def morning_intro(v: str = "", kind: str = "morning"):
    from fastapi.responses import Response
    try:
        audio = morning.intro(morning.kind_of(kind))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


@app.get("/api/morning/voice", dependencies=[Depends(require_login)])
def morning_voice(i: int = 0, t: str = "", kind: str = "morning"):
    from fastapi.responses import Response
    try:
        audio = morning.voice(i, morning.kind_of(kind))
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(503, str(exc))
    # never cached by the browser: each brief (and each voice change) gets freshly spoken lines
    return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


class CityBody(BaseModel):
    city: str = ""


@app.get("/api/weather/city", dependencies=[Depends(require_login)])
def weather_city():
    return {"city": db.get(weather.CITY)}


@app.post("/api/weather/city", dependencies=[Depends(require_login)])
def weather_set_city(body: CityBody):
    try:
        return {"city": weather.set_city(body.city)}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/whoop/test", dependencies=[Depends(require_login)])
def whoop_test():
    return whoop.check()


class VoiceBody(BaseModel):
    voice: str


@app.get("/api/morning/voices", dependencies=[Depends(require_login)])
def morning_voices():
    return {"voices": morning.VOICES, "current": morning.current_voice()}


@app.post("/api/morning/voices", dependencies=[Depends(require_login)])
def morning_set_voice(body: VoiceBody):
    try:
        return {"current": morning.set_voice(body.voice)}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/morning/preview", dependencies=[Depends(require_login)])
def morning_preview(voice: str = ""):
    from fastapi.responses import Response
    name = voice.lower() if voice.lower() in morning.VOICES else morning.current_voice()
    try:
        audio = morning.speak("Good morning, Ryan. Here's your night, your money, and your day. Carpe diem.", name)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=86400"})


@app.post("/api/morning/seen", dependencies=[Depends(require_login)])
def morning_seen(kind: str = "morning", device: str = "desktop"):
    morning.mark_seen(morning.kind_of(kind), morning.device_of(device))
    return {"ok": True}


def _whoop_redirect(request: Request) -> str:
    return os.environ.get("WHOOP_REDIRECT_URI") or f"{_base_url(request)}/api/whoop/callback"


@app.get("/api/whoop/start", include_in_schema=False)
def whoop_start(request: Request):
    if not logged_in(request):
        return RedirectResponse("/")
    if not whoop.configured():
        db.set("whoop:error", "Add WHOOP_CLIENT_ID and WHOOP_CLIENT_SECRET in Vercel first.")
        return RedirectResponse("/?whoop=error")
    url, state = whoop.login_url(_whoop_redirect(request))
    resp = RedirectResponse(url, status_code=302)
    resp.set_cookie("wh_state", state, max_age=600, httponly=True, secure=_https(request), samesite="lax")
    return resp


@app.get("/api/whoop/callback", include_in_schema=False)
def whoop_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    if error or not code:
        return RedirectResponse("/?whoop=denied")
    if not state or state != request.cookies.get("wh_state"):
        return RedirectResponse("/?whoop=expired")
    try:
        whoop.finish_login(code, _whoop_redirect(request))
    except (whoop.WhoopError, ValueError, requests.RequestException) as exc:
        db.set("whoop:error", str(exc))
        return RedirectResponse("/?whoop=error")
    resp = RedirectResponse("/?whoop=ok")
    resp.delete_cookie("wh_state")
    return resp


SERVICE_WORKER = """
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));
self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = { title: 'SRM', body: event.data ? event.data.text() : '' }; }
  event.waitUntil(self.registration.showNotification(data.title || 'SRM', {
    body: data.body || '', tag: data.tag || 'srm', icon: '/icon-192.png', badge: '/icon-192.png',
    data: { url: data.url || '/?calendar=today' }, vibrate: [180], silent: false,
  }));
});
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/?calendar=today';
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
    for (const client of list) { if ('focus' in client) { client.postMessage({ type: url.includes('expenses') ? 'open-expenses' : 'open-calendar' }); return client.focus(); } }
    return self.clients.openWindow(url);
  }));
});
"""


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    from fastapi.responses import Response
    return Response(SERVICE_WORKER, media_type="application/javascript",
                    headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})
