"""
Calendar: to-dos and timed reminders (Pacific time), scheduled by voice or typing.

Items (store hash agenda:items):
  kind "timed"   a date + a time   → phone push 1 hour before (⏳) and 10 minutes before (⚠️)
  kind "todo"    a date, no time   → shows on that day; unfinished ones carry over to today
  kind "general" no date           → "Anytime" list on Today until ticked off
Past days are cleared automatically (no old months piling up), so the calendar always opens light.

Scheduling: what you say/type is read by Grok (XAI_API_KEY) into items. The date maths never comes from the model:
it picks from a list of the next 60 real days we give it, and anything it returns is checked here. Without a key, a
built-in reader handles the usual phrases ("tomorrow 3pm …", "next tuesday …", "oct 12 at 9 …", "in 2 hours …").
Voice: the recording is turned into text with xAI speech-to-text (OpenAI Whisper as a fallback if that key is set).
"""
from __future__ import annotations

import json
import os
import re
import secrets
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

import webpush
from store import db

TZ = ZoneInfo("America/Los_Angeles")
ITEMS = "agenda:items"
CLEAN_KEY = "agenda:cleaned"
TICK_KEY = "agenda:lastTick"     # when the every-minute reminder check last ran (shown in the calendar)
KINDS = ("timed", "todo", "general")
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def now_pt() -> datetime:
    return datetime.now(TZ)


FILLER = r"\b(um+|uh+|uhm+|erm+|hmm+)\b"


def _clean_title(text: str) -> str:
    text = re.sub(FILLER, " ", str(text or ""), flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" .,-–—:;")
    return (text[:1].upper() + text[1:])[:140] if text else ""


def _valid_date(value) -> str | None:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError):
        return None


def _valid_time(value) -> str | None:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", str(value or "").strip())
    if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59:
        return None
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def normalize(raw: dict, today: date) -> dict | None:
    """One item as we store it, or None if it can't be used."""
    title = _clean_title(raw.get("title"))
    if not title:
        return None
    kind = raw.get("kind") if raw.get("kind") in KINDS else None
    day, at = _valid_date(raw.get("date")), _valid_time(raw.get("time"))
    if at and not day:
        day = today.isoformat()
    if kind is None:
        kind = "timed" if at else "todo" if day else "general"
    if kind == "timed" and not (day and at):
        kind = "todo" if day else "general"
    if kind == "todo":
        at = None
        day = day or today.isoformat()
    if kind == "general":
        day, at = None, None
    if day and day < today.isoformat():
        day = today.isoformat()
    return {"title": title, "kind": kind, "date": day, "time": at}


# ---------- storage ----------

def _all() -> dict:
    return db.hgetall(ITEMS)


def _sort_key(item: dict):
    return (item.get("date") or "", item.get("time") or "99:99", item.get("created") or 0)


def tidy(force: bool = False) -> None:
    """Past days go: timed reminders and done to-dos are deleted; unfinished to-dos move to today. At most once a minute."""
    if not force and not db.set_nx(CLEAN_KEY, 1, 60):
        return
    today = now_pt().date().isoformat()
    items = _all()
    drop, move = [], {}
    for item_id, item in items.items():
        day = item.get("date")
        if item.get("kind") == "general":
            if item.get("done") and (item.get("done_day") or today) < today:
                drop.append(item_id)
            continue
        if not day or day >= today:
            continue
        if item.get("kind") == "todo" and not item.get("done"):
            move[item_id] = {**item, "date": today, "carried": True}
        else:
            drop.append(item_id)
    if drop:
        db.hdel(ITEMS, *drop)
    if move:
        db.hset(ITEMS, move)


def day_view(day: str) -> dict:
    """Everything the calendar needs for one day, plus which days of the next weeks have something on them."""
    tidy()
    items = sorted(_all().values(), key=_sort_key)
    today = now_pt().date().isoformat()
    timed = [i for i in items if i.get("kind") == "timed" and i.get("date") == day]
    todos = [i for i in items if i.get("kind") == "todo" and i.get("date") == day]
    general = [i for i in items if i.get("kind") == "general"] if day == today else []
    marks: dict[str, int] = {}
    for item in items:
        if item.get("date") and not item.get("done"):
            marks[item["date"]] = marks.get(item["date"], 0) + 1
    return {"day": day, "today": today, "now": now_pt().isoformat(timespec="minutes"),
            "timed": timed, "todos": todos, "general": general, "marks": marks,
            "push": webpush.has_subscriptions(), "reminders": status()}


def everything() -> dict:
    """Every upcoming item in one go: the calendar switches days on the phone itself (no wait per tap)."""
    tidy()
    now = now_pt()
    items = sorted(_all().values(), key=_sort_key)
    info = status()
    return {"today": now.date().isoformat(), "now": now.isoformat(timespec="minutes"), "items": items,
            "push": info["devices"] > 0, "reminders": info}


def status() -> dict:
    """For the calendar's status line: devices, when the minute check last ran, and what the last push got back."""
    tick_info = db.get(TICK_KEY) or {}
    last = webpush.last_report() or {}
    return {"devices": webpush.device_count(), "lastCheck": tick_info.get("at"),
            "lastPush": {k: last.get(k) for k in ("at", "title", "sent", "results")} if last else None}


def upcoming() -> list[dict]:
    """Timed reminders in the next hour (for the yellow / red banner when the app is open)."""
    tidy()
    now = now_pt()
    out = []
    for item in _all().values():
        if item.get("kind") != "timed" or item.get("done"):
            continue
        start = at_of(item)
        if start and now - timedelta(minutes=1) <= start <= now + timedelta(minutes=60):
            out.append({**item, "minutes": max(0, round((start - now).total_seconds() / 60))})
    return sorted(out, key=lambda i: i["minutes"])


def at_of(item: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(f"{item['date']}T{item['time']}").replace(tzinfo=TZ)
    except (KeyError, TypeError, ValueError):
        return None


def add(items: list[dict]) -> list[dict]:
    today = now_pt().date()
    saved = {}
    for raw in items[:10]:
        item = normalize(raw, today)
        if not item:
            continue
        item_id = secrets.token_urlsafe(6).replace("-", "x").replace("_", "y")
        saved[item_id] = {**item, "id": item_id, "done": False, "created": int(time.time()), "sent": []}
    if saved:
        db.hset(ITEMS, saved)
    return list(saved.values())


def update(item_id: str, patch: dict) -> dict | None:
    items = _all()
    item = items.get(item_id)
    if not item:
        return None
    if "dismissed" in patch:             # cleared from the bell (it stays in the calendar and still pushes)
        item["dismissed"] = bool(patch["dismissed"])
    if "done" in patch:
        item["done"] = bool(patch["done"])
        item["done_day"] = now_pt().date().isoformat() if item["done"] else None
    if any(k in patch for k in ("title", "date", "time", "kind")):
        fixed = normalize({**item, **{k: patch[k] for k in ("title", "date", "time", "kind") if k in patch}}, now_pt().date())
        if fixed:
            if (fixed.get("date"), fixed.get("time")) != (item.get("date"), item.get("time")):
                item["sent"] = []          # moved: its reminders go out again at the new time
                item["dismissed"] = False  # and it shows in the bell again
            item.update(fixed)
    db.hset(ITEMS, {item_id: item})
    return item


def remove(item_id: str) -> None:
    db.hdel(ITEMS, item_id)


# ---------- reminders (Vercel cron, every minute) ----------

def _clock(hhmm: str) -> str:
    h, m = (int(x) for x in hhmm.split(":"))
    return f"{(h % 12) or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


def tick() -> dict:
    """⏳ about an hour before, ⚠️ ten minutes before. Each goes out once (one buzz); a reminder set inside the last
    10 minutes only gets the ⚠️ one."""
    tidy()
    now = now_pt()
    db.set(TICK_KEY, {"at": int(time.time())})
    # Vercel can now and then start the same minute's run twice: only one of them may send anything.
    if not db.set_nx("agenda:tick_lock", 1, 45):
        return {"sent": 0, "checked": now.isoformat(timespec="minutes"), "skipped": "another run is sending"}
    if not webpush.has_subscriptions():
        return {"sent": 0, "checked": now.isoformat(timespec="minutes"), "devices": 0}   # nothing is marked sent
    sent = 0
    for item_id, item in _all().items():
        if item.get("kind") != "timed" or item.get("done"):
            continue
        start = at_of(item)
        if not start:
            continue
        minutes = (start - now).total_seconds() / 60
        done = set(item.get("sent") or [])
        when = _clock(item["time"])
        if -2 <= minutes <= 10 and "ten" not in done:
            left = max(0, round(minutes))
            body = f"Now · {when}" if left <= 0 else f"In {left} minute{'s' if left != 1 else ''} · {when}"
            push = (f"⚠️ {item['title']}", body, f"cal{item_id}ten")
            done |= {"ten", "hour"}
        elif 10 < minutes <= 61 and "hour" not in done:
            left = round(minutes)
            body = "In 1 hour" if left >= 55 else f"In {left} minutes"
            push = (f"⏳ {item['title']}", f"{body} · {when}", f"cal{item_id}hr")
            done.add("hour")
        else:
            continue
        db.hset(ITEMS, {item_id: {**item, "sent": sorted(done)}})     # marked sent first: it can never go out twice
        sent += webpush.send_all(*push)
    try:
        import expense_push
        sent += expense_push.run()           # new expenses in the bell buzz the phone too
    except Exception:                        # never let an expense hiccup stop reminders
        pass
    try:
        import earnings_push
        sent += earnings_push.run()          # every new $1k on the day buzzes the phone once
    except Exception:
        pass
    return {"sent": sent, "checked": now.isoformat(timespec="minutes"), "devices": webpush.device_count()}


# ---------- reading what you said ----------

def _calendar_lines(today: date) -> str:
    """5 weeks, Mon–Sun, each day labelled, so "tuesday next week" is a lookup, not arithmetic."""
    monday = today - timedelta(days=today.weekday())
    names = ["this week", "next week", "in 2 weeks", "in 3 weeks", "in 4 weeks"]
    lines = []
    for week in range(5):
        for n in range(7):
            day = monday + timedelta(days=week * 7 + n)
            if day < today:
                continue
            tag = " (today)" if day == today else " (tomorrow)" if day == today + timedelta(days=1) else ""
            lines.append(f"{day.isoformat()} {day.strftime('%A')} · {names[week]}{tag}")
    return "\n".join(lines)


PARSE_RULES = """You read a voice note (a rough transcript) and pull out calendar items. Be fast and literal.
Output JSON only: {"items":[{"title":"...","date":"YYYY-MM-DD or null","time":"HH:MM 24h or null"}]}

For each thing they want to do, find three parts and ignore everything else:
1. TASK → title: short and plain, like a to-do ("Call the bank", "Pay rent", "Send invoices to Ana"). Keep names, places,
   amounts. Drop filler (um, uh, like, so, okay, you know), politeness, "remind me to", "I need to", "don't forget to",
   and every date/time word.
2. DAY → date, picked from the calendar list (Mon–Sun weeks; each line says which week it is in):
   today / tonight → today · tomorrow → tomorrow · "tuesday" or "this tuesday" → the next Tuesday coming (today if it's
   Tuesday and that time hasn't passed) · "next tuesday", "tuesday next week" → the Tuesday whose line says next week ·
   "next week" alone → Monday of next week · "this weekend" → Saturday · "in 3 days" → count from today ·
   "the 14th" / "Oct 14" → that date (next one coming) · "end of the week" → Friday this week. No day said → null.
3. TIME → time, only when a clock time is said: "at 3", "3:30", "half past 2" (14:30), "quarter to 5" (16:45), "noon",
   "midnight", "in 2 hours" / "in 20 minutes" (from now, and that sets the day too). Bare hour with no am/pm:
   1–6 → PM; 7–11 → AM if that hour is still ahead today (or another day), else PM; "tonight"/"this evening" → PM.
   Morning / afternoon / later / sometime → no time (null). No time said → null.

They think out loud: when they correct themselves ("at 3, no wait, 4"; "Tuesday— actually Wednesday"), use the last
one. Several separate tasks → several items, each with its own day/time (a day said once can cover tasks listed
together: "tomorrow call mom and pay rent" → both tomorrow). Never invent tasks, days or times. If nothing is a task,
return {"items":[]}."""


def _xai_text(key: str, model: str, system: str, user: str, api: str = "responses", effort: bool = True) -> str:
    """Grok with the lightest thinking (reasoning effort "low"). Responses API first; Chat Completions as a backup."""
    headers = {"Authorization": f"Bearer {key}"}
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if api == "responses":
        body = {"model": model, "store": False, "max_output_tokens": 1200, "input": messages}
        if effort:
            body["reasoning"] = {"effort": "low"}
        resp = requests.post("https://api.x.ai/v1/responses", timeout=12, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data.get("output_text"), str) and data["output_text"].strip():
            return data["output_text"]
        return "".join(c.get("text") or "" for out in data.get("output") or [] if isinstance(out, dict)
                       for c in out.get("content") or [] if isinstance(c, dict) and c.get("type") in ("output_text", "text"))
    body = {"model": model, "messages": messages, "max_tokens": 1200}
    if effort:
        body["reasoning_effort"] = "low"
    resp = requests.post("https://api.x.ai/v1/chat/completions", timeout=12, headers=headers, json=body)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"] or ""


def _grok_parse(text: str, now: datetime) -> list[dict] | None:
    key = os.environ.get("XAI_API_KEY", "").strip()
    if not key:
        return None
    prompt = (f"Now: {now.strftime('%A %Y-%m-%d %H:%M')} (Pacific time).\nCalendar:\n{_calendar_lines(now.date())}\n\n"
              f"Voice note: \"{text.strip()[:800]}\"")
    models = [m for m in (os.environ.get("XAI_CAL_MODEL", "").strip(), "grok-4.7", "grok-4.6") if m]
    # Fast path first; a 400/404 (unknown model or option) falls through to the next way in a fraction of a second.
    tries = [(m, "responses", True) for m in models[:2]] + [(models[0], "chat", True), (models[0], "chat", False)]
    started = time.monotonic()
    for model, api, effort in tries:
        if time.monotonic() - started > 14:
            return None
        try:
            content = _xai_text(key, model, PARSE_RULES, prompt, api, effort)
            block = content[content.index("{"): content.rindex("}") + 1]
            items = json.loads(block).get("items")
            if isinstance(items, list):
                return items
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code in (400, 404, 422):
                continue
            return None
        except Exception:
            return None
    return None


_MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def _rule_parse(text: str, now: datetime) -> list[dict]:
    """Backup reader for the common phrases, used when Grok isn't available."""
    s = " " + text.strip() + " "
    low = s.lower()
    today = now.date()
    day: date | None = None
    at: str | None = None
    bare = False   # an hour with no am/pm

    def cut(pattern):
        nonlocal s, low
        s = re.sub(pattern, " ", s, flags=re.I)
        low = s.lower()

    m = re.search(r"\bin (\d{1,3}) (minute|min|hour|hr)s?\b", low)
    if m:
        delta = timedelta(minutes=int(m.group(1))) if m.group(2).startswith("m") else timedelta(hours=int(m.group(1)))
        when = now + delta
        day, at = when.date(), when.strftime("%H:%M")
        cut(m.re.pattern)
    if day is None:
        if re.search(r"\b(today|tonight)\b", low):
            day = today
        elif re.search(r"\btomorrow\b", low):
            day = today + timedelta(days=1)
        elif re.search(r"\b(" + "|".join(WEEKDAYS) + r") (of )?next week\b|\bnext week (on )?(" + "|".join(WEEKDAYS) + r")\b", low):
            wd = re.search(r"\b(" + "|".join(WEEKDAYS) + r")\b", low)
            day = today + timedelta(days=(7 - today.weekday()) + WEEKDAYS.index(wd.group(1)))
            cut(r"\b(of )?next week( on)?\b")
        elif re.search(r"\bnext week\b", low):
            day = today + timedelta(days=7 - today.weekday())
        else:
            wd = re.search(r"\b(next |this )?(" + "|".join(WEEKDAYS) + r")\b", low)
            if wd:
                target = WEEKDAYS.index(wd.group(2))
                ahead = (target - today.weekday()) % 7
                if wd.group(1) and wd.group(1).strip() == "next":
                    ahead = (7 - today.weekday()) + target
                day = today + timedelta(days=ahead)
            else:
                md = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? (\d{1,2})(st|nd|rd|th)?\b", low) \
                    or re.search(r"\b(\d{1,2})/(\d{1,2})\b", low)
                if md:
                    if md.group(1).isdigit():
                        month, dom = int(md.group(1)), int(md.group(2))
                    else:
                        month, dom = _MONTHS[md.group(1)[:3]], int(md.group(2))
                    try:
                        cand = date(today.year, month, dom)
                        day = cand if cand >= today else date(today.year + 1, month, dom)
                    except ValueError:
                        day = None
                    cut(md.re.pattern)
        cut(r"\b(today|tonight|tomorrow|next week|next|this|on)\b")
        cut(r"\b(" + "|".join(WEEKDAYS) + r")\b")
    if at is None:
        tm = re.search(r"\b(?:at )?(\d{1,2})(?::(\d{2}))? ?(am|pm|a\.m\.|p\.m\.)\b", low) or re.search(r"\bat (\d{1,2})(?::(\d{2}))?\b", low) \
            or re.search(r"\b(noon|midnight)\b", low)
        if tm:
            if tm.group(1) in ("noon", "midnight"):
                at = "12:00" if tm.group(1) == "noon" else "00:00"
            else:
                hour, minute = int(tm.group(1)), int(tm.group(2) or 0)
                mer = (tm.group(3) if tm.lastindex and tm.lastindex >= 3 else None) or ""
                if mer.startswith("p") and hour < 12:
                    hour += 12
                elif mer.startswith("a") and hour == 12:
                    hour = 0
                elif not mer:
                    bare = True
                    if 1 <= hour <= 6:
                        hour += 12
                at = f"{hour % 24:02d}:{minute:02d}"
            cut(tm.re.pattern)
    title = re.sub(r"\b(remind me to|remind me|reminder to|i need to|i have to|i gotta|don't forget to|to do|todo|at|on|for)\b", " ", s, flags=re.I)
    title = re.sub(r"^\W*((so|okay|ok|and|then|like|um+|uh+)\b\W*)+", "", re.sub(FILLER, " ", title, flags=re.I).strip(), flags=re.I)
    if at and bare and (day is None or day == today):
        # "at 7" with no am/pm and no other day: the next 7 o'clock coming up
        hour, minute = (int(x) for x in at.split(":"))
        base = hour % 12
        for when in (now.replace(hour=base, minute=minute, second=0, microsecond=0),
                     now.replace(hour=base + 12, minute=minute, second=0, microsecond=0),
                     (now + timedelta(days=1)).replace(hour=base if base >= 7 else base + 12, minute=minute, second=0, microsecond=0)):
            if when > now:
                day, at = when.date(), when.strftime("%H:%M")
                break
    if at and not day:
        day = today
    return [{"title": title, "kind": "timed" if at else "todo" if day else "general",
             "date": day.isoformat() if day else None, "time": at}]


def parse(text: str) -> dict:
    now = now_pt()
    raw = _grok_parse(text, now)
    source = "grok"
    if raw is None:
        raw, source = _rule_parse(text, now), "rules"
    items = [i for i in (normalize(r, now.date()) for r in raw if isinstance(r, dict)) if i]
    return {"items": items, "source": source}


# ---------- voice → text ----------

def transcribe(audio: bytes, filename: str, content_type: str) -> str:
    """xAI speech-to-text (same key as Grok); OpenAI Whisper as a fallback."""
    if not audio:
        raise ValueError("No audio came through.")
    xai = os.environ.get("XAI_API_KEY", "").strip()
    if xai:
        try:
            resp = requests.post("https://api.x.ai/v1/stt", timeout=40, headers={"Authorization": f"Bearer {xai}"},
                                 data={"model": os.environ.get("XAI_STT_MODEL") or "grok-voice-transcribe-2.0", "language": "en", "format": "true"},
                                 files={"file": (filename, audio, content_type)})
            data = resp.json()
            text = str(data.get("text") or " ".join(str(w.get("text") or w.get("word") or "") for w in data.get("words") or [])).strip()
            if resp.ok and text:
                return text
        except Exception:
            pass
    openai = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai:
        resp = requests.post("https://api.openai.com/v1/audio/transcriptions", timeout=40, headers={"Authorization": f"Bearer {openai}"},
                             data={"model": "whisper-1", "language": "en"}, files={"file": (filename, audio, content_type)})
        if resp.ok:
            return str(resp.json().get("text") or "").strip()
    if not xai and not openai:
        raise RuntimeError("Voice needs XAI_API_KEY on Vercel (the same xAI key Autothot uses).")
    raise RuntimeError("Couldn't make out that recording. Try again or type it.")
