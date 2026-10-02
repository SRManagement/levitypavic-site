"""
SRM Dashboard: private earnings dashboard (FastAPI on Vercel).

Files:
  server.py  web routes + password login
  calc.py    all money math
  fanvue.py  Fanvue login + earnings sync
  sheet.py   expenses from the live Google Sheet
  bank.py    card charges from Plaid
  store.py   saved data (Upstash Redis on Vercel)
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # let Vercel find the files next to this one

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

import bank
import calc
import chatter
import fanvue
import monthly
import payouts
import sheet
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


def _sync_income_tab(days: dict, settings: dict, today: date) -> None:
    """Keep the sheet's Income tab current: Fanvue gross per month (business income) + deposits.
    Rewrites only when something changed; the live current month refreshes at most every 30 min."""
    if not sheet.configured():
        return
    gross = calc.gross_by_month(days, today)
    fees = {m["month"]: m["amount"] for m in calc.fanvue_months(days, settings, today)}
    logged = sheet.fanvue_logged()
    current = today.isoformat()[:7]
    months = [{"month": m, "gross": round(gross.get(m, 0.0), 2), "fee": logged.get(m, fees.get(m, 0.0)),
               "fee_logged": m in logged, "live": m == current} for m in sheet._months(today)]
    deposits = payouts.merged(bank.income_deposits(), payouts.live_payouts(), today.isoformat())
    sig = hashlib.sha1(repr((months, deposits, sheet.INCOME_NOTES)).encode()).hexdigest()
    shape = repr(([(m["month"], m["fee_logged"]) for m in months], [d["id"] for d in deposits], sheet.INCOME_NOTES))
    last = db.get("income_tab") or {}
    if last.get("sig") == sig:
        return
    if last.get("shape") == shape and time.time() - last.get("at", 0) < 1800:
        return                          # only the live month's numbers moved; refresh later
    sheet.write_income_tab(months, deposits, today)
    db.set("income_tab", {"sig": sig, "shape": shape, "at": time.time()})


@app.get("/api/dashboard", dependencies=[Depends(require_login)])
def dashboard(range_key: str = Query("today", alias="range"), fresh: bool = False,
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
    try:
        _sync_income_tab(days, settings, today)
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
    if bk["error"]:
        warnings.append("Bank: " + bk["error"])
    if bk["connected"] and not bk["mask_found"]:
        warnings.append(f"Bank: no card ending {bank.CARD_MASK} found, so every account on that login is being tracked.")
    return {
        "range": {"key": rng["key"], "label": rng["label"], "kind": rng["kind"],
                  "start": rng["lo"].isoformat(), "end": rng["hi"].isoformat()},
        "ranges": [{"key": k, "label": label} for k, label in calc.RANGES],
        "totals": calc.totals(days, expenses, settings, rng["lo"], rng["hi"], today),
        "chart": calc.chart_points(days, settings, rng, now),
        "settings": settings,
        "rates": calc.rate_status(settings, now.astimezone(calc.AGENCY_TZ).date()),
        "models": MODELS,
        "fanvue": fv,
        "bank": bk,
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
def sync():
    """Called on every page load. The page repeats it while done is false (first-time history pull)."""
    if not fanvue.is_connected():
        return {"connected": False, "done": True}
    return fanvue.sync()


def _plaid_webhook_url(request: Request) -> str:
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    return os.environ.get("PLAID_WEBHOOK_URL") or (f"https://{host}/api/plaid/webhook" if host and "localhost" not in host else "")


@app.post("/api/bank/sync", dependencies=[Depends(require_login)])
def bank_sync(request: Request):
    """Called on every page load (and every few minutes while the page is open): pulls new card
    charges from Plaid, pending ones included."""
    try:
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
        g["items"].append({**{k: e[k] for k in ("id", "date", "item", "category", "amount", "qty")}, "pending": bool(e.get("pending"))})
    return sorted(groups.values(), key=lambda g: (-g["total"], g["provider"]))


@app.get("/api/expenses", dependencies=[Depends(require_login)])
def expenses_desk():
    try:
        expenses = sheet.load_expenses(force=True)
    except sheet.SheetError as exc:
        raise HTTPException(503, str(exc)) from exc
    newest_first = sorted(expenses, key=lambda e: e["date"], reverse=True)
    verified = [e for e in newest_first if e["status"] == "verified"]
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
