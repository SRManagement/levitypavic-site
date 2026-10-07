"""
WHOOP (your band) for the morning brief: last night's sleep, this morning's recovery, yesterday's strain.

Setup (one time): create an app at developer.whoop.com, add the redirect URL
https://<your SRM domain>/api/whoop/callback, put WHOOP_CLIENT_ID and WHOOP_CLIENT_SECRET in Vercel, then
Moderator → Connect WHOOP. The "offline" scope gives a refresh token, so it stays connected.
"""
from __future__ import annotations

import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests

from store import db

AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
API = "https://api.prod.whoop.com/developer/v2"
SCOPES = "offline read:recovery read:sleep read:cycles read:workout read:profile"
TOKENS = "whoop:tokens"


class WhoopError(Exception):
    pass


def _cid() -> str:   # trimmed: a stray space or quote pasted into Vercel makes WHOOP say the app "does not exist"
    return os.environ.get("WHOOP_CLIENT_ID", "").strip().strip("\"").strip("'").strip()


def _secret() -> str:
    return os.environ.get("WHOOP_CLIENT_SECRET", "").strip().strip("\"").strip("'").strip()


def configured() -> bool:
    return bool(_cid() and _secret())


def connected() -> bool:
    return bool((db.get(TOKENS) or {}).get("refresh_token") or (db.get(TOKENS) or {}).get("access_token"))


def login_url(redirect_uri: str) -> tuple[str, str]:
    state = secrets.token_urlsafe(16)
    query = {"client_id": _cid(), "redirect_uri": redirect_uri, "response_type": "code",
             "scope": SCOPES, "state": state}
    return f"{AUTH_URL}?{urlencode(query)}", state


def _save(payload: dict) -> str:
    if not payload.get("access_token"):
        raise WhoopError(payload.get("error_description") or payload.get("error") or "WHOOP didn't return a token.")
    old = db.get(TOKENS) or {}
    db.set(TOKENS, {"access_token": payload["access_token"],
                    "refresh_token": payload.get("refresh_token") or old.get("refresh_token", ""),
                    "expires_at": int(time.time()) + int(payload.get("expires_in") or 3600) - 60})
    db.delete("whoop:error")
    return payload["access_token"]


def finish_login(code: str, redirect_uri: str) -> None:
    resp = requests.post(TOKEN_URL, timeout=20, data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
        "client_id": _cid(), "client_secret": _secret(),
    })
    _save(resp.json() if resp.content else {})


def _token(force: bool = False) -> str:
    saved = db.get(TOKENS) or {}
    if not saved:
        raise WhoopError("WHOOP isn't connected (Moderator → Connect WHOOP).")
    if not force and saved.get("access_token") and saved.get("expires_at", 0) > time.time():
        return saved["access_token"]
    if not saved.get("refresh_token"):
        raise WhoopError("WHOOP needs to be connected again (Moderator → Connect WHOOP).")
    resp = requests.post(TOKEN_URL, timeout=20, data={
        "grant_type": "refresh_token", "refresh_token": saved["refresh_token"], "scope": "offline",
        "client_id": _cid(), "client_secret": _secret(),
    })
    try:
        return _save(resp.json())
    except (ValueError, WhoopError) as exc:
        db.set("whoop:error", str(exc))
        raise WhoopError("WHOOP needs to be connected again (Moderator → Connect WHOOP).") from exc


def _get(path: str, params: dict | None = None) -> dict:
    for attempt in (0, 1):
        resp = requests.get(f"{API}{path}", params=params or {}, timeout=20,
                            headers={"Authorization": f"Bearer {_token(force=attempt == 1)}"})
        if resp.status_code == 401 and attempt == 0:
            continue
        if not resp.ok:
            detail = (resp.text or "")[:160].replace("\n", " ")
            raise WhoopError(f"WHOOP answered {resp.status_code} for {path}{': ' + detail if detail else ''}")
        return resp.json()
    raise WhoopError("WHOOP refused the login.")


def _hours(milli) -> float:
    return round((milli or 0) / 3_600_000, 2)


def _when(stamp: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def morning() -> dict:
    """Last night's main sleep (not a nap), the recovery that came from it, and yesterday's strain. Live."""
    sleeps = [s for s in (_get("/activity/sleep", {"limit": 5}).get("records") or []) if not s.get("nap")]
    sleep = sleeps[0] if sleeps else None
    recoveries = _get("/recovery", {"limit": 8}).get("records") or []      # last night + a week to compare HRV against
    recovery = next((r for r in recoveries if sleep and r.get("sleep_id") == sleep.get("id")), recoveries[0] if recoveries else None)
    cycles = _get("/cycle", {"limit": 2}).get("records") or []
    out: dict = {"connected": True}
    if sleep:
        score = sleep.get("score") or {}
        stages = score.get("stage_summary") or {}
        need = score.get("sleep_needed") or {}
        light, deep, rem, awake = (stages.get(k) or 0 for k in ("total_light_sleep_time_milli", "total_slow_wave_sleep_time_milli",
                                                                  "total_rem_sleep_time_milli", "total_awake_time_milli"))
        asleep = light + deep + rem
        needed = sum(need.get(k) or 0 for k in ("baseline_milli", "need_from_sleep_debt_milli", "need_from_recent_strain_milli", "need_from_recent_nap_milli"))
        out["sleep"] = {
            "scored": sleep.get("score_state") == "SCORED",
            "start": sleep.get("start"), "end": sleep.get("end"),
            "hours": _hours(asleep), "needed": _hours(needed), "in_bed": _hours(stages.get("total_in_bed_time_milli")),
            "performance": score.get("sleep_performance_percentage"), "efficiency": score.get("sleep_efficiency_percentage"),
            "respiratory": score.get("respiratory_rate"),
            "debt": _hours(need.get("need_from_sleep_debt_milli")),
            "stages": {  # share of time asleep + awake in bed
                "rem": rem, "deep": deep, "light": light, "awake": awake,
            },
            "disturbances": stages.get("disturbance_count"), "cycles": stages.get("sleep_cycle_count"),
        }
    if recovery:
        score = recovery.get("score") or {}
        out["recovery"] = {"scored": recovery.get("score_state") == "SCORED", "score": score.get("recovery_score"),
                           "hrv": score.get("hrv_rmssd_milli"), "rhr": score.get("resting_heart_rate"),
                           "spo2": score.get("spo2_percentage"), "skin_temp": score.get("skin_temp_celsius")}
        hrvs = [(r.get("score") or {}).get("hrv_rmssd_milli") for r in recoveries if r is not recovery and (r.get("score") or {}).get("hrv_rmssd_milli")]
        if hrvs:
            out["recovery"]["hrv_recent"] = round(sum(hrvs) / len(hrvs), 1)
    done = [c for c in cycles if c.get("end")]
    if done:
        out["strain"] = (done[0].get("score") or {}).get("strain")
    return out


def window() -> tuple[datetime, datetime] | None:
    """When you were asleep last night (UTC), for "overnight" money."""
    try:
        sleeps = [s for s in (_get("/activity/sleep", {"limit": 5}).get("records") or []) if not s.get("nap")]
    except WhoopError:
        return None
    if not sleeps:
        return None
    start, end = _when(sleeps[0].get("start")), _when(sleeps[0].get("end"))
    return (start, end) if start and end else None


def check() -> dict:
    """For Connections → Test WHOOP: what it can see right now (or exactly why not)."""
    if not configured():
        return {"ok": False, "message": "Add WHOOP_CLIENT_ID and WHOOP_CLIENT_SECRET in Vercel, then redeploy."}
    if not connected():
        return {"ok": False, "message": "Not connected yet: tap Connect WHOOP."}
    try:
        data = morning()
    except WhoopError as exc:
        return {"ok": False, "message": str(exc)}
    rec, sleep = data.get("recovery") or {}, data.get("sleep") or {}
    bits = []
    if rec.get("score") is not None:
        bits.append(f"recovery {round(rec['score'])}%")
    if sleep.get("hours"):
        bits.append(f"{sleep['hours']:.1f}h sleep")
    if data.get("strain") is not None:
        bits.append(f"strain {data['strain']:.1f}")
    return {"ok": bool(bits), "message": ("Sees " + ", ".join(bits)) if bits else "Connected, but WHOOP returned no scored sleep or recovery yet."}


ZONES = ("zone_zero_milli", "zone_one_milli", "zone_two_milli", "zone_three_milli", "zone_four_milli", "zone_five_milli")


def _workout(w: dict) -> dict:
    score = w.get("score") or {}
    zones = score.get("zone_durations") or {}
    start, end = _when(w.get("start")), _when(w.get("end"))
    mins = [round((zones.get(z) or 0) / 60000, 1) for z in ZONES]          # minutes in zones 0-5
    busiest = max(range(1, 6), key=lambda k: mins[k]) if any(mins[1:]) else None
    meters = score.get("distance_meter")
    return {
        "sport": str(w.get("sport_name") or "Workout").replace("_", " ").title(),
        "strain": score.get("strain"), "avg_hr": score.get("average_heart_rate"), "max_hr": score.get("max_heart_rate"),
        "calories": round((score.get("kilojoule") or 0) / 4.184) if score.get("kilojoule") else None,
        "minutes": round((end - start).total_seconds() / 60) if start and end else None,
        "miles": round(meters / 1609.344, 2) if meters else None,
        "zones": mins, "main_zone": busiest, "start": w.get("start"),
    }


def afternoon(day_start_utc: datetime) -> dict:
    """Today's day strain + steps so far (the open cycle) and every workout WHOOP detected today, with its zones."""
    cycles = _get("/cycle", {"limit": 1}).get("records") or []
    out: dict = {"connected": True}
    if cycles:
        c = cycles[0]
        score = c.get("score") or {}
        out["day_strain"] = score.get("strain")
        steps = c.get("step_count", score.get("step_count"))
        out["steps"] = int(steps) if isinstance(steps, (int, float)) else None
        out["calories"] = round(score["kilojoule"] / 4.184) if score.get("kilojoule") else None
        out["avg_hr"], out["max_hr"] = score.get("average_heart_rate"), score.get("max_heart_rate")   # whole cycle: since you fell asleep
        out["cycle_start"] = c.get("start")
    recent = _get("/activity/workout", {"limit": 15}).get("records") or []
    scored = [w for w in recent if w.get("score_state") == "SCORED"]
    today = [w for w in scored if (_when(w.get("start")) or day_start_utc) >= day_start_utc]
    workouts = [_workout(w) for w in reversed(today)]                       # oldest first, the way the day went
    out["workouts"] = workouts
    if workouts:
        top = max(workouts, key=lambda x: x.get("strain") or 0)
        others = [(x.get("score") or {}).get("strain") for x in scored if x not in today and (x.get("score") or {}).get("strain") is not None]
        if others:
            top["avg_strain"] = round(sum(others) / len(others), 1)
        out["workout"] = top
    return out


def _clock(moment: datetime) -> str:
    return moment.strftime("%-I:%M %p")


def bedtime(now: datetime, day_strain: float | None, sleeps: list | None = None) -> dict:
    """Tonight's bedtime (an estimate built from your own WHOOP data):
    sleep need = your baseline + part of last night's shortfall + extra for today's strain - any nap today,
    time in bed = need / your usual sleep efficiency, and bedtime = your usual wake-up time minus that.
    `now` is Pacific time (aware)."""
    tz = now.tzinfo
    if sleeps is None:
        sleeps = _sleeps()
    sleeps = [s for s in sleeps if s.get("score_state") == "SCORED"]
    nights = [s for s in sleeps if not s.get("nap")]
    if not nights:
        return {}
    last = nights[0].get("score") or {}
    need = last.get("sleep_needed") or {}
    stages = last.get("stage_summary") or {}
    baseline = (need.get("baseline_milli") or 0) / 3_600_000 or 8.0
    needed_last = sum(need.get(k) or 0 for k in ("baseline_milli", "need_from_sleep_debt_milli", "need_from_recent_strain_milli",
                                                  "need_from_recent_nap_milli")) / 3_600_000
    got_last = sum(stages.get(k) or 0 for k in ("total_light_sleep_time_milli", "total_slow_wave_sleep_time_milli",
                                                 "total_rem_sleep_time_milli")) / 3_600_000
    debt = min(1.0, max(0.0, needed_last - got_last) * 0.5)                  # half of last night's shortfall, at most an hour
    strain_extra = min(1.0, max(0.0, ((day_strain or 0) - 8) * 5 / 60))    # about 5 min per strain point above 8, max an hour
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    nap = 0.0
    for s in sleeps:
        start = _when(s.get("start"))
        if s.get("nap") and start and start.astimezone(tz) >= midnight:
            st = (s.get("score") or {}).get("stage_summary") or {}
            nap += sum(st.get(k) or 0 for k in ("total_light_sleep_time_milli", "total_slow_wave_sleep_time_milli",
                                               "total_rem_sleep_time_milli")) / 3_600_000
    nap = min(nap, 1.5)
    total = max(6.0, baseline + debt + strain_extra - nap)
    effs = [(s.get("score") or {}).get("sleep_efficiency_percentage") for s in nights[:7]]
    effs = [e for e in effs if e]
    eff = sum(effs) / len(effs) if effs else 90.0
    in_bed = total / (max(70.0, min(99.0, eff)) / 100)
    wakes = []
    for s in nights[:10]:
        end = _when(s.get("end"))
        if end:
            local = end.astimezone(tz)
            if 240 <= local.hour * 60 + local.minute <= 720:               # wake-ups between 4 AM and noon
                wakes.append(local.hour * 60 + local.minute)
    wakes.sort()
    wake_min = wakes[len(wakes) // 2] if wakes else 7 * 60                  # your usual (median) wake-up
    wake_min = int(round(wake_min / 5) * 5)
    tomorrow = (midnight + timedelta(days=1 if now.hour >= 12 else 0))
    wake_at = tomorrow + timedelta(minutes=wake_min)
    bed = wake_at - timedelta(hours=in_bed)
    bed = bed.replace(second=0, microsecond=0) - timedelta(minutes=bed.minute % 5)   # round down to 5 minutes
    left = int((bed - now).total_seconds() // 60)
    return {"bedtime": _clock(bed), "bedtime_at": bed.isoformat(), "wake": _clock(wake_at), "need": round(total, 1),
            "in_bed": round(in_bed, 1), "efficiency": round(eff), "minutes_left": left,
            "parts": {"baseline": round(baseline, 2), "debt": round(debt, 2), "strain": round(strain_extra, 2), "nap": round(nap, 2)}}


def _sleeps() -> list:
    return _get("/activity/sleep", {"limit": 25}).get("records") or []


def awake_hr(out: dict, sleeps: list, now: datetime) -> int | None:
    """Average heart rate while you've been awake today.
    WHOOP's day (cycle) starts when you fall asleep, so its average includes last night. Take the sleep back out:
    cycle beats - sleep beats (sleep at about your resting HR + 8%, WHOOP's RHR is your lowest stretch) over the awake minutes."""
    avg, start = out.get("avg_hr"), _when(out.get("cycle_start"))
    if not avg or not start:
        return None
    night = next((s for s in sleeps if not s.get("nap") and _when(s.get("start")) and abs((_when(s.get("start")) - start).total_seconds()) < 4 * 3600), None)
    if not night or not _when(night.get("end")):
        return None
    try:
        rec = next((r for r in (_get("/recovery", {"limit": 3}).get("records") or []) if r.get("sleep_id") == night.get("id")), None)
    except WhoopError:
        rec = None
    rhr = ((rec or {}).get("score") or {}).get("resting_heart_rate")
    if not rhr:
        return None
    sleep_min = (_when(night["end"]) - _when(night["start"])).total_seconds() / 60
    total_min = (now.astimezone(timezone.utc) - start).total_seconds() / 60
    awake_min = total_min - sleep_min
    if awake_min < 60:
        return None
    value = (avg * total_min - rhr * 1.08 * sleep_min) / awake_min
    top = out.get("max_hr") or 220
    return round(value) if rhr <= value <= top else None


def evening(now: datetime) -> dict:
    """Everything for the evening report: today's strain / steps / calories / every workout, your awake heart rate,
    plus tonight's bedtime."""
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    out = afternoon(midnight)
    try:
        sleeps = _sleeps()
    except WhoopError as exc:
        out["bed"] = {"error": str(exc)}
        return out
    out["awake_hr"] = awake_hr(out, sleeps, now)
    try:
        out["bed"] = bedtime(now, out.get("day_strain"), sleeps)
    except WhoopError as exc:
        out["bed"] = {"error": str(exc)}
    return out
