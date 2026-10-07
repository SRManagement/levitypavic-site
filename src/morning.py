"""
"Good morning, Ryan": the morning brief that plays the first time SRM is opened after 6 AM PT (once a day).

Everything is pulled live when it opens: WHOOP (sleep, recovery, strain), Fanvue overnight (12 AM PT → when you woke
up), your day from the calendar, and a few housekeeping counts. Plain, exact lines (the numbers as they are) are read by
the Grok voice picked in Connections, one per scene, so the visuals land with the words.
"""
from __future__ import annotations

import base64
import os
from datetime import date, datetime, time as dtime, timedelta

import requests

import agenda
import calc
import weather
import whoop
from store import db

PT = calc.PT
SEEN = "morning:seen"            # the PT day it last played
VOICE = os.environ.get("XAI_MORNING_VOICE", "leo")     # default; Connections → Morning brief → Voice overrides it
VOICES = ["leo", "ara", "eve", "rex", "sal", "carina", "zagan", "helix", "orion", "luna", "iris", "altair", "zenith", "perseus",
          "helios", "lux", "kepler", "rigel", "cosmo", "celeste", "ursa", "sirius", "lumen", "castor", "naksh", "atlas", "aurora", "liora"]


def current_voice() -> str:
    picked = str(db.get("morning:voice") or "").lower()
    return picked if picked in VOICES else VOICE


def set_voice(name: str) -> str:
    name = str(name or "").lower()
    if name not in VOICES:
        raise ValueError("Unknown voice.")
    db.set("morning:voice", name)
    return name
SCENES = ("hello", "body", "money", "weather", "day", "close")
CLOSE = "Carpe diem."   # always the last line (on screen)
CARPE = "Kar-pay dee-em."   # how the voice says it: KAR-pay DEE-em (spelled out so it can't come out as "carp")


def now_pt() -> datetime:
    return datetime.now(PT)


WINDOWS = {"morning": (dtime(6, 0), dtime(23, 59, 59)), "afternoon": (dtime(14, 0), dtime(20, 0)),
           "evening": (dtime(20, 0), dtime(23, 59, 59))}
KINDS = tuple(WINDOWS)


def kind_of(value: str | None) -> str:
    return value if value in WINDOWS else "morning"


DEVICES = ("desktop", "phone")      # each plays once a day on the computer AND once on the phone, separately


def device_of(value: str | None) -> str:
    return value if value in DEVICES else "desktop"


def _seen_key(kind: str, device: str = "desktop") -> str:
    base = SEEN if kind == "morning" else f"{kind}:seen"
    return f"{base}:{device_of(device)}"


def due(kind: str = "morning", device: str = "desktop") -> bool:
    """Morning: any time after 6 AM. Afternoon: 2 to 7:59 PM. Evening: 8 PM to midnight.
    Each once a day per device type: watching it on the computer doesn't use up the phone's showing."""
    now = now_pt()
    start, end = WINDOWS[kind]
    return start <= now.time() < end and db.get(_seen_key(kind, device)) != now.date().isoformat()


def mark_seen(kind: str = "morning", device: str = "desktop") -> None:
    today = now_pt().date().isoformat()
    db.set(_seen_key(kind, device), today)
    if kind == "evening":           # opened for the first time at night: the morning brief would be stale, skip it
        db.set(_seen_key("morning", device), today)


def _last_key(kind: str) -> str:
    return "morning:last" if kind == "morning" else f"{kind}:last"


# ---------- money ----------

def _hours_sum(rec: dict | None, last_hour: int) -> dict:
    out = {"gross": 0, "chatter": 0, "subs_gross": 0, "subs": 0}
    for hour in range(0, min(23, last_hour) + 1):
        row = ((rec or {}).get("h") or [[0, 0]] * 24)[hour]
        out["gross"] += row[0]
        out["chatter"] += row[1]
        if len(row) >= 4:
            out["subs_gross"] += row[2]
            out["subs"] += row[3]
    return out


def _net(gross_cents: int, chatter_cents: int, day: date, settings: dict) -> float:
    fee = calc.fanvue_rate(day, settings)
    return round((gross_cents * (1 - fee) - chatter_cents * (1 - fee) * calc.chatter_rate(day, settings)) / 100, 2)


def money(days: dict, settings: dict, wake: datetime) -> dict:
    today = wake.date()
    hour = wake.hour
    now = _hours_sum(days.get(today.isoformat()), hour)
    week = today - timedelta(days=7)
    then = _hours_sum(days.get(week.isoformat()), hour)
    first = today.replace(day=1)
    last_month_end = first - timedelta(days=1)
    lm_first = last_month_end.replace(day=1)
    mtd = sum(calc.day_gross(days.get(d.isoformat())) for d in calc.each_day(first, today))
    lm_same = sum(calc.day_gross(days.get(d.isoformat())) for d in calc.each_day(lm_first, min(last_month_end, lm_first.replace(day=min(today.day, last_month_end.day)))))
    lm_total = sum(calc.day_gross(days.get(d.isoformat())) for d in calc.each_day(lm_first, last_month_end))
    month_days = ((first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).day
    done_days = (today.day - 1) + (wake.hour + wake.minute / 60) / 24          # whole days so far + the part of today
    projected = mtd / done_days * month_days if done_days >= 1 else None
    best_hour, best = None, 0
    rec = days.get(today.isoformat()) or {}
    for h in range(0, min(23, hour) + 1):
        value = ((rec.get("h") or [[0, 0]] * 24)[h])[0]
        if value > best:
            best_hour, best = h, value
    return {
        "window": f"12 AM – {wake.strftime('%-I:%M %p')}",
        "gross": round(now["gross"] / 100, 2),
        "net": _net(now["gross"], now["chatter"], today, settings),
        "subs": now["subs"], "subs_gross": round(now["subs_gross"] / 100, 2),
        "chatter": round(now["chatter"] / 100, 2),
        "last_week": round(then["gross"] / 100, 2),
        "vs_last_week": round((now["gross"] - then["gross"]) / then["gross"] * 100) if then["gross"] else None,
        "best_hour": datetime(2000, 1, 1, best_hour).strftime("%-I %p") if best_hour is not None else None,
        "best_hour_gross": round(best / 100, 2),
        "mtd": round(mtd, 2), "last_month_same": round(lm_same, 2), "last_month_total": round(lm_total, 2),
        "projected": round(projected, 2) if projected else None,
        "mtd_vs": round((mtd - lm_same) / lm_same * 100) if lm_same else None,
    }


# ---------- record day (bonus slide in the morning brief) ----------

def record_day(days: dict, settings: dict, day: date) -> dict | None:
    """Was `day` (a whole finished day, 12 AM to 11:59 PM) the best day ever? Compared with every day before it
    (needs a week of history). None if not."""
    rec = days.get(day.isoformat())
    gross = calc.day_gross(rec)
    if not rec or gross <= 0:
        return None
    best_day, best, history = None, 0.0, 0
    for key, other in days.items():
        if key >= day.isoformat():
            continue
        history += 1
        value = calc.day_gross(other)
        if value > best:
            best_day, best = key, value
    if history < 7 or gross <= best:
        return None
    hours = _hours_sum(rec, 23)
    return {"day": day.isoformat(), "label": day.strftime("%A, %B %-d"), "gross": round(gross, 2),
            "net": _net(round(gross * 100), hours["chatter"], day, settings), "subs": hours["subs"],
            "prev_best": round(best, 2), "prev_best_day": best_day,
            "beat_by": round(gross - best, 2), "beat_pct": round((gross - best) / best * 100) if best else None}


# ---------- the brief ----------

def build(days: dict, settings: dict, pending: int, spot: dict | None = None) -> dict:
    now = now_pt()
    body: dict = {"connected": whoop.connected()}
    wake = now
    if body["connected"]:
        try:
            body = whoop.morning()
            end = body.get("sleep", {}).get("end")
            if end:
                woke = datetime.fromisoformat(str(end).replace("Z", "+00:00")).astimezone(PT)
                if woke.date() == now.date() and woke <= now:
                    wake = woke
        except whoop.WhoopError as exc:
            body = {"connected": True, "error": str(exc)}
    view = agenda.day_view(now.date().isoformat())
    day = {
        "timed": [{"title": i["title"], "time": i["time"]} for i in view["timed"] if not i.get("done")],
        "todos": [i["title"] for i in view["todos"] if not i.get("done")],
        "general": [i["title"] for i in view["general"] if not i.get("done")],
    }
    brief = {
        "date": now.strftime("%A, %B %-d"),
        "hour": now.hour,
        "body": body,
        "money": money(days, settings, wake),
        "day": day,
        "weather": weather.today(spot, now),
        "pending_expenses": pending,
        "record": record_day(days, settings, now.date() - timedelta(days=1)),
    }
    brief["lines"] = script(brief)
    brief["scenes"] = list(SCENES)
    brief["at"] = now.isoformat()
    brief["voice"] = current_voice()
    db.set("morning:last", {"lines": brief["lines"], "at": brief["at"]}, ttl=20 * 3600)
    return brief


INTRO = "Good morning, Ryan. Syncing data now."   # spoken while the night is pulled


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def script(brief: dict) -> list[str]:
    """Plain, exact lines (no personality): the numbers, said as they are. The last scene says "Carpe diem." (spelled for the voice as KAR-pay DEE-em)."""
    m, b, d = brief["money"], brief["body"], brief["day"]
    weekday = brief["date"].split(",")[0]
    rec = (b.get("recovery") or {}).get("score")
    perf = (b.get("sleep") or {}).get("performance")
    if rec is not None and perf is not None:
        body = f"You had a {round(rec)} percent recovery and a {round(perf)} percent sleep score."
    elif rec is not None:
        body = f"You had a {round(rec)} percent recovery."
    elif perf is not None:
        body = f"You had a {round(perf)} percent sleep score."
    else:
        body = ("WHOOP isn't connected yet." if not b.get("connected") else "I couldn't reach WHOOP this morning." if b.get("error")
                else "WHOOP hasn't scored last night yet.")
    money = f"Overnight you made ${m['gross']:,.0f} gross and {_plural(m['subs'], 'new sub')}."   # month comparison: evening only
    first = d["timed"][0] if d["timed"] else None
    day = (f"You have {_plural(len(d['timed']), 'thing')} scheduled today, starting with {first['title']} at {agenda._clock(first['time'])}."
           if first else "Nothing is scheduled at a set time today.")
    if d["todos"]:
        day += f" And {_plural(len(d['todos']), 'to-do')}."
    lines = [f"Happy {weekday}, let's review your overnight data.", body, money, weather.line(brief.get("weather")), day, CARPE]
    r = brief.get("record")
    if r:   # bonus slide right after the overnight money: yesterday was the best day ever
        lines.insert(3, f"Yesterday was a record high. You made ${r['gross']:,.0f} gross, beating your previous best of "
                        f"${r['prev_best']:,.0f}. That's an all time high, congratulations.")
    return lines


# ---------- voice ----------

def speak(text: str, voice_id: str | None = None) -> bytes:
    key = os.environ.get("XAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("The voice needs XAI_API_KEY on Vercel.")
    resp = requests.post("https://api.x.ai/v1/tts", timeout=40, headers={"Authorization": f"Bearer {key}"}, json={
        "text": text, "voice_id": voice_id or current_voice(), "language": "en",
        "output_format": {"codec": "mp3", "sample_rate": 24000, "bit_rate": 64000},
    })
    if not resp.ok or not resp.content or resp.headers.get("content-type", "").startswith("application/json"):
        raise RuntimeError("Grok's voice didn't answer. The brief plays without sound.")
    return resp.content


def voice(index: int, kind: str = "morning") -> bytes:
    """The chosen voice reading line `index` of this brief's script (mp3), kept for the day."""
    last = db.get(_last_key(kind)) or {}
    lines = last.get("lines") or []
    if not 0 <= index < len(lines):
        raise ValueError("No morning brief yet.")
    who = current_voice()
    cache = f"{kind}:voice:v2:{who}:{last.get('at', '')}:{index}"
    saved = db.get(cache)
    if saved:
        return base64.b64decode(saved)
    if not lines[index]:
        raise ValueError("This scene has no voice.")
    audio = speak(lines[index], who)
    db.set(cache, base64.b64encode(audio).decode(), ttl=20 * 3600)
    return audio


INTROS = {"morning": INTRO, "afternoon": "Good afternoon, Ryan. Syncing data now.", "evening": "Good evening, Ryan. Syncing data now."}


def intro(kind: str = "morning") -> bytes:
    """"Good morning / afternoon, Ryan. Syncing data now." in the chosen voice (kept, so it plays the instant it opens)."""
    who = current_voice()
    cache = f"{kind}:intro:{who}" if kind != "morning" else f"morning:intro:{who}"
    saved = db.get(cache)
    if saved:
        return base64.b64decode(saved)
    audio = speak(INTROS[kind], who)
    db.set(cache, base64.b64encode(audio).decode())
    return audio



# ---------- afternoon review (2 to 7:59 PM) ----------

def _workout_lines(workouts: list[dict]) -> str:
    """" Running: 31 minutes, 3.1 miles, strain 10.4, average heart rate 151, mostly in zone 4." for each workout."""
    out = ""
    for w in workouts[:4]:   # what you did, how long, how far, how hard
        bits = [f"{w['minutes']} minutes" if w.get("minutes") else ""]
        if w.get("miles") and w["miles"] >= 0.1:
            bits.append(f"{w['miles']:.1f} miles")
        if w.get("strain") is not None:
            bits.append(f"strain {w['strain']:.1f}")
        if w.get("avg_hr"):
            bits.append(f"average heart rate {round(w['avg_hr'])}")
        if w.get("main_zone"):
            bits.append(f"mostly in zone {w['main_zone']}")
        out += f" {w['sport']}: " + ", ".join(x for x in bits if x) + "."
    return out


def _money_line(m: dict, compare: bool = False) -> str:
    """Morning / afternoon are updates on the day; only the evening report compares the month with last month."""
    line = f"So far today you've made ${m['gross']:,.0f} gross and {_plural(m['subs'], 'new sub')}."
    if compare and m.get("mtd_vs") is not None:
        line += f" Month to date you're at ${m['mtd']:,.0f}, {abs(m['mtd_vs'])} percent {'ahead of' if m['mtd_vs'] >= 0 else 'behind'} last month."
    return line

def _tasks(day: str) -> dict:
    """Every reminder for today, checked ones included. A timed one counts as done once its time has passed."""
    view = agenda.day_view(day)
    now = now_pt()
    items = []
    for i in view["timed"]:
        start = agenda.at_of(i)
        items.append({"title": i["title"], "time": i["time"], "done": bool(i.get("done")) or bool(start and start <= now)})
    items += [{"title": i["title"], "done": bool(i.get("done"))} for i in view["todos"]]
    items += [{"title": i["title"], "done": bool(i.get("done")), "anytime": True} for i in view["general"]]
    return {"items": items, "done": sum(1 for i in items if i["done"]), "total": len(items)}


def build_afternoon(days: dict, settings: dict) -> dict:
    now = now_pt()
    body: dict = {"connected": whoop.connected()}
    if body["connected"]:
        try:
            midnight = datetime(now.year, now.month, now.day, tzinfo=PT).astimezone(whoop.timezone.utc)
            body = whoop.afternoon(midnight)
        except whoop.WhoopError as exc:
            body = {"connected": True, "error": str(exc)}
    m = money(days, settings, now)
    m["window"] = f"12 AM – {now.strftime('%-I:%M %p')}"
    tasks = _tasks(now.date().isoformat())
    brief = {"kind": "afternoon", "date": now.strftime("%A, %B %-d"), "hour": now.hour, "body": body, "money": m, "tasks": tasks}
    brief["lines"] = afternoon_script(brief)
    brief["at"] = now.isoformat()
    brief["voice"] = current_voice()
    db.set(_last_key("afternoon"), {"lines": brief["lines"], "at": brief["at"]}, ttl=12 * 3600)
    return brief


def afternoon_script(brief: dict) -> list[str]:
    b, m, t = brief["body"], brief["money"], brief["tasks"]
    if not b.get("connected"):
        body = "WHOOP isn't connected yet."
    elif b.get("error"):
        body = "I couldn't reach WHOOP this afternoon."
    else:
        strain, steps, workouts = b.get("day_strain"), b.get("steps"), b.get("workouts") or []
        body = f"Your day strain is {strain:.1f}" if strain is not None else "Your day strain isn't in yet"
        if steps:
            body += f", and you're at {steps:,} steps"
        if not workouts:
            body += ", with no weightlifting detected for today yet."
        else:
            body += f". WHOOP detected {_plural(len(workouts), 'workout')} today." + _workout_lines(workouts)
    money_line = _money_line(m)
    tasks = f"You have {t['done']} out of {t['total']} tasks completed for the day." if t["total"] else "You have no tasks on the list today."
    return ["Here's your afternoon update.", body, money_line, tasks, "Stay sharp."]


# ---------- evening report (8 PM to midnight) ----------

def build_evening(days: dict, settings: dict, pending: int) -> dict:
    now = now_pt()
    body: dict = {"connected": whoop.connected()}
    if body["connected"]:
        try:
            body = whoop.evening(now)
        except whoop.WhoopError as exc:
            body = {"connected": True, "error": str(exc)}
    m = money(days, settings, now)
    m["window"] = f"12 AM – {now.strftime('%-I:%M %p')}"
    brief = {"kind": "evening", "date": now.strftime("%A, %B %-d"), "hour": now.hour, "body": body, "money": m,
             "tasks": _tasks(now.date().isoformat()), "pending_expenses": pending}
    brief["lines"] = evening_script(brief)
    brief["at"] = now.isoformat()
    brief["voice"] = current_voice()
    db.set(_last_key("evening"), {"lines": brief["lines"], "at": brief["at"]}, ttl=8 * 3600)
    return brief


def _hm(hours: float) -> str:
    h, mins = int(hours), int(round((hours - int(hours)) * 60))
    if mins == 60:
        h, mins = h + 1, 0
    return f"{h} hours" + (f" {mins} minutes" if mins else "")


def evening_script(brief: dict) -> list[str]:
    b, m, t = brief["body"], brief["money"], brief["tasks"]
    tasks = f"You have {t['done']} out of {t['total']} tasks completed for the day." if t["total"] else "You have no tasks on the list today."
    still = [i["title"] for i in t["items"] if not i["done"]]
    if still and len(still) <= 3:
        said = still[0] if len(still) == 1 else f"{still[0]} and {still[1]}" if len(still) == 2 else f"{still[0]}, {still[1]}, and {still[2]}"
        tasks += f" Still open: {said}."
    elif still:
        tasks += f" {len(still)} are still open."
    rolling = [i for i in t["items"] if not i["done"] and not i.get("time")]   # timed ones past their time count as done
    if rolling:
        tasks += f" {'It' if len(rolling) == 1 else 'They'} will roll over to tomorrow."
    if not b.get("connected"):
        training, bed = "WHOOP isn't connected yet.", ""
    elif b.get("error"):
        training, bed = "I couldn't reach WHOOP tonight.", ""
    else:
        strain, steps, workouts = b.get("day_strain"), b.get("steps"), b.get("workouts") or []
        extras = [f"{steps:,} steps" if steps else "", f"{b['calories']:,} calories burned" if b.get("calories") else ""]
        extras = [x for x in extras if x]
        training = (f"Your day strain is {strain:.1f}" if strain is not None else "Your day strain isn't in yet") + \
                   (", with " + " and ".join(extras) if extras else "") + "."
        if workouts:
            active = sum(w.get("minutes") or 0 for w in workouts)
            training += f" WHOOP detected {_plural(len(workouts), 'workout')} today" + (f", {active} active minutes in total." if active else ".")
            training += _workout_lines(workouts)
        else:
            training += " No workout was detected today."
        r = b.get("bed") or {}
        if r.get("bedtime"):
            if r.get("minutes_left", 0) > 0:
                bed = (f"Aim to be in bed by {r['bedtime']}. You need about {_hm(r['need'])} of sleep tonight "
                       f"to wake up recovered around {r['wake']}.")
            else:
                bed = (f"Your ideal bedtime was {r['bedtime']}, so head to bed now. "
                       f"You need about {_hm(r['need'])} of sleep to wake up recovered around {r['wake']}.")
        else:
            bed = "WHOOP doesn't have enough sleep history yet to set a bedtime."
    return ["Here's your evening report.", _money_line(m, compare=True), tasks, training, bed, "Rest well."]
