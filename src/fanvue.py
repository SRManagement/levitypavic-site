"""
Fanvue connection: OAuth login, token refresh, and earnings sync.

Fanvue hands out a NEW refresh token every time we refresh, and re-using an old
one kills the whole login. So the token pair lives in exactly one place (the
store) and only one request at a time is allowed to refresh it (a short lock).

Earnings are pulled from GET /insights/earnings (one row per transaction,
amounts in cents) and saved per Pacific-time day as:
    days[YYYY-MM-DD] = {"s": {source: [gross_cents, net_cents]},
                        "h": [[gross_cents, messages_tips_gross_cents] x 24 hours]}
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from store import db

PT = ZoneInfo("America/Los_Angeles")
API = "https://api.fanvue.com"
AUTH_URL = "https://auth.fanvue.com/oauth2/auth"
TOKEN_URL = "https://auth.fanvue.com/oauth2/token"
API_VERSION = "2025-06-26"
SCOPES = "openid offline_access offline read:self read:insights read:creator"
CLIENT_ID = os.environ.get("FANVUE_CLIENT_ID", "07a7708b-8725-4dda-8d93-cab779ed37f4")
CLIENT_SECRET = os.environ.get("FANVUE_CLIENT_SECRET", "")

# First day to pull history from. Earnings started in April 2026.
EARNINGS_START = date(2026, 3, 1)
SOURCE_MAP = {
    "subscription": "subs",
    "renewal": "renewals",
    "message": "messages",
    "tip": "tips",
    "post": "posts",
    "referral": "referrals",
    "checkoutLink": "checkout_link",
    "appStore": "app_store",
    "fanExperience": "fan_experience",
}  # anything else (refunds, chargebacks, media links, ...) is "other"
CHATTER_SOURCES = ("messages", "tips")


class FanvueError(Exception):
    def __init__(self, message: str, status: int = 0, retry_after: str | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


class NotConnected(FanvueError):
    pass


def today_pt() -> date:
    return datetime.now(PT).date()


# ---------- HTTP ----------

def _request(url: str, *, data: bytes | None = None, headers: dict | None = None, method: str = "GET") -> dict:
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise FanvueError(f"Fanvue {exc.code}: {detail}", exc.code, exc.headers.get("Retry-After")) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise FanvueError(f"Could not reach Fanvue: {exc}") from exc


def _token_call(form: dict) -> dict:
    if not CLIENT_SECRET:
        raise FanvueError("FANVUE_CLIENT_SECRET is not set in Vercel")
    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    return _request(
        TOKEN_URL,
        data=urllib.parse.urlencode(form).encode(),
        headers={
            "Authorization": "Basic " + basic,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )


def _save_tokens(payload: dict) -> str:
    access = payload.get("access_token")
    refresh = payload.get("refresh_token")
    if not access or not refresh:
        raise FanvueError("Fanvue did not return tokens")
    db.set("fanvue_tokens", {
        "access": access,
        "refresh": refresh,
        "expires_at": int(time.time()) + int(payload.get("expires_in") or 3600),
    })
    return access


# ---------- OAuth login ----------

def login_url(redirect_uri: str) -> tuple[str, str, str]:
    """Returns (url, state, code_verifier). State + verifier go in HttpOnly cookies."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    query = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return AUTH_URL + "?" + query, state, verifier


def finish_login(code: str, verifier: str, redirect_uri: str) -> None:
    payload = _token_call({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
    })
    _save_tokens(payload)
    db.delete("fanvue_error")


def is_connected() -> bool:
    return bool(db.get("fanvue_tokens"))


def access_token(force_refresh: bool = False) -> str:
    tokens = db.get("fanvue_tokens")
    if not tokens:
        raise NotConnected("Fanvue is not connected")
    if not force_refresh and tokens["expires_at"] > time.time() + 60:
        return tokens["access"]

    if not db.set_nx("fanvue_refresh_lock", 1, 20):
        # Another request is refreshing right now; wait for its new token.
        for _ in range(20):
            time.sleep(0.5)
            fresh = db.get("fanvue_tokens")
            if fresh and fresh["access"] != tokens["access"]:
                return fresh["access"]
        raise FanvueError("Timed out waiting for Fanvue token refresh")
    try:
        tokens = db.get("fanvue_tokens") or tokens  # re-read under the lock
        try:
            payload = _token_call({"grant_type": "refresh_token", "refresh_token": tokens["refresh"]})
        except FanvueError as exc:
            if exc.status in (400, 401):
                db.delete("fanvue_tokens")  # refresh token is dead; user must log in again
                raise NotConnected("Fanvue login expired, reconnect") from exc
            raise
        return _save_tokens(payload)
    finally:
        db.delete("fanvue_refresh_lock")


def _api_get(path: str, params: dict) -> dict:
    url = API + path + "?" + urllib.parse.urlencode(params)
    force_refresh = False
    for attempt in range(3):
        try:
            return _request(url, headers={
                "Authorization": "Bearer " + access_token(force_refresh),
                "X-Fanvue-API-Version": API_VERSION,
                "Accept": "application/json",
            })
        except FanvueError as exc:
            if exc.status == 429 and attempt < 2:
                time.sleep(min(float(exc.retry_after or 5), 10))
                continue
            if exc.status == 401 and not force_refresh:
                force_refresh = True  # access token rejected: refresh once and retry
                continue
            raise
    raise FanvueError("Fanvue request failed")


# ---------- Earnings sync ----------

def _utc_iso(day: date) -> str:
    """Midnight Pacific time on `day`, as a UTC timestamp."""
    start = datetime(day.year, day.month, day.day, tzinfo=PT).astimezone(timezone.utc)
    return start.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _pt_day_hour(stamp: str) -> tuple[str, int] | None:
    try:
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(PT)
    return local.date().isoformat(), local.hour


def _empty_day() -> dict:
    # h[hour] = [gross, chatter gross, new-sub gross, new-sub count] (cents; the last two feed the morning brief)
    return {"s": {}, "h": [[0, 0, 0, 0] for _ in range(24)]}


def fetch_days(first: date, last: date) -> dict[str, dict]:
    """All earnings for Pacific days first..last (inclusive), grouped per day."""
    params = {"startDate": _utc_iso(first), "endDate": _utc_iso(last + timedelta(days=1)), "size": 50}
    days: dict[str, dict] = {}
    for _ in range(400):  # hard stop against a runaway cursor
        page = _api_get("/insights/earnings", params)
        for row in page.get("data") or []:
            when = _pt_day_hour(str(row.get("date") or ""))
            if not when:
                continue
            day, hour = when
            src = SOURCE_MAP.get(str(row.get("source")), "other")
            gross = int(round(float(row.get("gross") or 0)))
            net = int(round(float(row.get("net") or 0)))
            rec = days.setdefault(day, _empty_day())
            pair = rec["s"].setdefault(src, [0, 0])
            pair[0] += gross
            pair[1] += net
            rec["h"][hour][0] += gross
            if src in CHATTER_SOURCES:
                rec["h"][hour][1] += gross
            if src == "subs":
                rec["h"][hour][2] += gross
                rec["h"][hour][3] += 1
        cursor = page.get("nextCursor")
        if not cursor:
            break
        params["cursor"] = cursor
    return days


def _store_window(first: date, last: date) -> None:
    fresh = fetch_days(first, last)
    db.hset("days", fresh)
    empty, d = [], first
    while d <= last:
        if d.isoformat() not in fresh:
            empty.append(d.isoformat())
        d += timedelta(days=1)
    db.hdel("days", *empty)


def sync(budget_seconds: float = 7.0) -> dict:
    """
    First run: backfills history one week at a time, stopping after ~7s so we
    never hit Vercel's time limit. The page calls this again until done=True.
    Every run after that: re-pulls the last 3 days (today, yesterday, day before).
    """
    started = time.monotonic()
    today = today_pt()
    state = db.get("sync_state") or {"next": EARNINGS_START.isoformat()}
    try:
        if state.get("next"):
            nxt = date.fromisoformat(state["next"])
            while nxt <= today:
                last = min(nxt + timedelta(days=6), today)
                _store_window(nxt, last)
                nxt = last + timedelta(days=1)
                state["next"] = nxt.isoformat() if nxt <= today else None
                db.set("sync_state", state)
                if state["next"] and time.monotonic() - started > budget_seconds:
                    return {"connected": True, "done": False, "through": last.isoformat()}
        else:
            _store_window(today - timedelta(days=2), today)
    except NotConnected as exc:
        db.set("fanvue_error", str(exc))
        return {"connected": False, "done": True, "error": str(exc)}
    except FanvueError as exc:
        db.set("fanvue_error", str(exc))
        return {"connected": is_connected(), "done": True, "error": str(exc)}
    state["last_sync"] = datetime.now(PT).isoformat(timespec="seconds")
    db.set("sync_state", state)
    db.delete("fanvue_error")
    return {"connected": True, "done": True}


def status() -> dict:
    state = db.get("sync_state") or {}
    return {
        "connected": is_connected(),
        "last_sync": state.get("last_sync"),
        "backfilling": bool(state.get("next")),
        "error": db.get("fanvue_error") or "",
    }
