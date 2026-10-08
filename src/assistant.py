"""
SRM's assistant: the orb in the dock. Ryan types (or dictates with the keyboard) and Grok answers in one go.

Everything it could need is handed to it up front as one compact snapshot (money for every range, every day's gross,
months, expenses waiting, the calendar, recurring tasks, school, today's Day Map, WHOOP from today's briefs), so a
question is a single fast call with no back-and-forth. It answers as JSON: what to say, plus actions.

Actions never run here. The page runs them, the same way a tap would:
  - right away: check / uncheck a reminder, routine or assignment, push one to tomorrow (or back), open a screen,
    switch the dashboard range, Day Map nudges, the tax set-aside switch, play a recap, set the wake-up time, the voice;
  - only after Ryan approves a card in the chat: new reminders (any number at once), deletes, approving expenses.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import date, datetime, timedelta

import requests

import academic
import agenda
import calc
import morning
import plan
from store import db

RANGE_KEYS = [k for k, _ in calc.RANGES]
NOW_ACTIONS = {"check", "check_routine", "check_school", "push", "open", "range", "nudges", "tax", "recap", "wake", "voice",
               "hide_notification"}
ASK_ACTIONS = {"schedule", "delete", "approve_expense"}
SCREENS = ("home", "calendar", "notifications", "settings", "daymap", "expenses")

RULES = """You are SRM, the assistant inside Ryan's SRM Dashboard app (his Fanvue creator business: earnings, chatters,
expenses, taxes, plus his calendar, school, Day Map and WHOOP). You talk like a sharp, warm chief of staff: short,
direct, natural spoken English (your reply is read aloud). Usually 1–3 sentences. Longer only when he asks for a
breakdown; then use short lines. Plain text only: no markdown headings, no tables, no emoji. You may wrap a key number
in **double asterisks**.

DATA: the SNAPSHOT below is live from the app. Answer only from it; never invent numbers. Money is in US dollars;
round to whole dollars when speaking unless cents matter. "Gross" = Fanvue earnings. "Net" = after Fanvue's cut,
chatters, opex and (when on) the tax set-aside. If something isn't in the snapshot, say you can't see it.
Do math yourself carefully (sums, averages, best/worst days, comparisons) from the per-day and per-month data.

ACTIONS: you can do anything Ryan can tap in the app. Reply with JSON only, exactly:
{"say": "...", "actions": [ ... ]}
Action objects (use ids from the snapshot exactly):
- {"type":"schedule","items":[{"title":"Call the bank","date":"YYYY-MM-DD or null","time":"HH:MM or null","due":"YYYY-MM-DD or null"}, ...]}
  New reminders / to-dos. Several at once is normal: one item each. Ryan approves them in a card, so say something
  like "Here's what I'll add" (never claim they're added). Same date/time rules as below.
- {"type":"delete","ids":["..."]}  remove reminders (he approves first).
- {"type":"approve_expense","ids":["..."]}  verify charges waiting for approval (he approves first).
- {"type":"check","id":"...","done":true|false}  a calendar reminder / to-do.
- {"type":"check_routine","id":"...","done":true|false}  a recurring task, for today.
- {"type":"check_school","id":"...","done":true|false}  an assignment.
- {"type":"push","id":"...","back":false}  push a reminder to tomorrow (back:true = undo a push).
- {"type":"open","screen":"home|calendar|notifications|settings|daymap|expenses"}
- {"type":"range","key":"today|yesterday|last_7|last_14|last_30|this_week|this_month|last_month|this_year|all_time"}
  or {"type":"range","start":"YYYY-MM-DD","end":"YYYY-MM-DD"}  switch the dashboard (also opens Home).
- {"type":"nudges","on":true|false}  Day Map nudges for today.
- {"type":"tax","on":true|false}  the tax set-aside switch.
- {"type":"recap","kind":"morning|afternoon|evening"}  play a recap.
- {"type":"wake","time":"HH:MM"}  when he actually got out of bed today ("" = back to WHOOP's).
- {"type":"voice","name":"..."}  change the voice (one of the listed voices).
- {"type":"hide_notification","id":"..."}
Do what he asks; don't add actions he didn't ask for. Questions alone need no actions ([]). Checking things off,
pushing, opening and switching happen right away, so say them as done ("Checked off laundry.").

DATES for schedule items: title = the task, short and plain ("Call the bank"), no date words. date = the day to do
it, from the calendar lines (today / tomorrow / "tuesday" = the next one coming / "next tuesday" = the one marked
next week / "this weekend" = Saturday / "in 3 days"). time only when a clock time is said ("at 3", "3:30", "noon",
"in 2 hours" from now). Bare hour without am/pm: 1–6 → PM, 7–11 → AM if still ahead today else PM. "by/before/due
Friday" is a deadline: due = that day, date and time null. No day said → date null (an anytime to-do).
A day said once covers tasks listed together ("tomorrow call mom and pay rent" → both tomorrow)."""


def _r(v) -> int:
    return int(round(v or 0))


def _range_block(days: dict, expenses: list[dict], settings: dict, key: str, today: date, first: date, first_earn: date) -> dict:
    rng = calc.resolve_range(key, today, first, first_earn)
    t = calc.totals(days, expenses, settings, rng["lo"], rng["hi"], today)
    return {"from": rng["lo"].isoformat(), "to": rng["hi"].isoformat(), "gross": round(t["gross"], 2), "net": _r(t["net"]),
            "fanvue_cut": _r(t["fanvue_cut"]), "chatters": _r(t["chatter_cut"]), "opex": _r(t["opex"]), "tax_set_aside": _r(t["tax_cut"]),
            "by_source": {k: _r(v) for k, v in calc.sources(days, rng["lo"], rng["hi"]).items()}}


def context(days: dict, expenses: list[dict], settings: dict, notifications: list[dict], now: datetime,
            screen: str | None, range_key: str | None) -> dict:
    """The snapshot Grok answers from (kept compact: a few thousand tokens)."""
    today = now.date()
    first_earn = date.fromisoformat(min(days)) if days else today
    first = min(first_earn, date.fromisoformat(min(e["date"] for e in expenses))) if expenses else first_earn
    money = {k: _range_block(days, expenses, settings, k, today, first, first_earn)
             for k in ("today", "yesterday", "this_week", "last_7", "last_30", "this_month", "last_month", "this_year", "all_time")}
    rec = days.get(today.isoformat())
    by_hour = {f"{h:02d}": _r(rec["h"][h][0] / 100) for h in range(now.hour + 1) if rec and rec["h"][h][0]} if rec else {}
    by_day = []
    for d in sorted(days):
        r = days[d]
        subs = sum(h[3] for h in r["h"] if len(h) > 3)
        by_day.append([d, _r(calc.day_gross(r)), subs])
    months = {}
    m = calc.BUSINESS_START.replace(day=1)
    while m <= today:
        nxt = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
        t = calc.totals(days, expenses, settings, m, min(nxt - timedelta(days=1), today), today)
        months[m.strftime("%Y-%m")] = {"gross": _r(t["gross"]), "net": _r(t["net"]), "opex": _r(t["opex"]), "chatters": _r(t["chatter_cut"])}
        m = nxt
    pace = {}
    for key in ("this_month", "this_year"):
        c = calc.compare(days, calc.resolve_range(key, today, first, first_earn), now)
        if c:
            pace[key] = {"on_pace_for": _r(c.get("pace")), "same_point_last_period": _r(c.get("gross")) if c.get("gross") else None}
    month_lo = today.replace(day=1).isoformat()
    opex_month = sorted(({"date": e["date"], "what": e["item"], "category": e["category"], "amount": e["amount"]}
                         for e in expenses if e["status"] == "verified" and e["date"] >= month_lo
                         and e["category"].lower() not in calc.CHATTER_CATEGORIES), key=lambda e: -abs(e["amount"]))[:12]
    waiting = [{"id": n["id"], "what": n.get("merchant"), "amount": n.get("amount"), "date": n.get("date"), "deposit": bool(n.get("deposit"))}
               for n in notifications if n.get("kind") == "new" and not n.get("done")]
    logged = [{"id": n["id"], "what": n.get("merchant"), "amount": n.get("amount"), "date": n.get("date")}
              for n in notifications if not (n.get("kind") == "new" and not n.get("done"))][:8]
    cal = agenda.everything()
    items = [{k: i.get(k) for k in ("id", "title", "kind", "date", "time", "end", "start", "due", "done", "pushed_from") if i.get(k) not in (None, "", False)}
             for i in cal["items"]][:80]
    done_today = set((plan.done_map() or {}).get(today.isoformat(), []))
    routines = [{"id": t["id"], "title": t["title"], "days": [agenda.WEEKDAYS[d][:3] for d in t.get("days", [])], "minutes": t.get("minutes"),
                 "done_today": t["id"] in done_today, "today": today.weekday() in (t.get("days") or [])} for t in plan.recurring()]
    school = [{k: a.get(k) for k in ("id", "course", "title", "date", "when", "kind", "test", "done")}
              for a in academic.items(today, 14)]
    day_map = None
    p = db.get(plan._plan_key(today.isoformat()))
    if p:
        day_map = {"wake": (p.get("wake") or {}).get("time"), "ends": p.get("dayEnd"),
                   "blocks": [{"title": b.get("title"), "start": b.get("start"), "end": b.get("end"), "kind": b.get("kind"), "done": bool(b.get("done"))}
                              for b in p.get("blocks") or [] if b.get("kind") not in ("open",)][:40],
                   "wont_fit": [x if isinstance(x, str) else x.get("title") for x in p.get("left") or []]}
    briefs = {}   # today's recaps as they were read out (WHOOP sleep, recovery, strain, workouts, bedtime live in these)
    for kind in ("morning", "afternoon", "evening"):
        last = db.get(morning._last_key(kind)) or {}
        if str(last.get("at", ""))[:10] == today.isoformat() and last.get("lines"):
            briefs[kind] = [str(x) for x in last["lines"] if x][:12]
    return {
        "now": now.strftime("%A %Y-%m-%d %H:%M") + " Pacific",
        "app": {"screen": screen or "home", "range_shown": range_key or "today"},
        "calendar_lines": agenda._calendar_lines(today),
        "money": money, "today_by_hour": by_hour, "pace": pace, "by_month": months,
        "by_day_gross_and_new_subs": by_day,
        "expenses": {"waiting_for_approval": waiting, "recent_logged": logged, "this_month_biggest": opex_month},
        "calendar": items, "routines": routines, "school_next_2_weeks": school, "day_map_today": day_map,
        "todays_recaps_whoop_and_more": briefs or None,
        "settings": {"fanvue_rate": settings.get("fanvue_rate"), "chatter_rate": settings.get("chatter_rate"),
                     "tax_on": settings.get("tax_enabled"), "tax_rate": settings.get("tax_rate"), "nudges_today": plan.nudges_on(),
                     "voice": morning.current_voice(), "voices": morning.VOICES},
    }


def _call(messages: list[dict]) -> str:
    key = os.environ.get("XAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("The assistant needs XAI_API_KEY on Vercel.")
    headers = {"Authorization": f"Bearer {key}"}
    models = [m for m in (os.environ.get("XAI_ASSISTANT_MODEL", "").strip(), os.environ.get("XAI_CAL_MODEL", "").strip(), "grok-4.7", "grok-4.6") if m]
    started, last_err = time.monotonic(), None
    for model in dict.fromkeys(models):
        for api in ("responses", "chat"):
            if time.monotonic() - started > 40:
                break
            try:
                if api == "responses":
                    body = {"model": model, "store": False, "max_output_tokens": 1600, "input": messages, "reasoning": {"effort": "low"}}
                    resp = requests.post("https://api.x.ai/v1/responses", timeout=35, headers=headers, json=body)
                    resp.raise_for_status()
                    data = resp.json()
                    text = data.get("output_text") if isinstance(data.get("output_text"), str) else ""
                    if not text.strip():
                        text = "".join(c.get("text") or "" for out in data.get("output") or [] if isinstance(out, dict)
                                       for c in out.get("content") or [] if isinstance(c, dict) and c.get("type") in ("output_text", "text"))
                else:
                    resp = requests.post("https://api.x.ai/v1/chat/completions", timeout=35, headers=headers,
                                         json={"model": model, "messages": messages, "max_tokens": 1600})
                    resp.raise_for_status()
                    text = resp.json()["choices"][0]["message"]["content"] or ""
                if text.strip():
                    return text
            except requests.HTTPError as exc:
                last_err = exc
                if exc.response is not None and exc.response.status_code in (400, 404, 422):
                    continue
                raise RuntimeError("Grok didn't answer just now.") from exc
            except requests.RequestException as exc:
                raise RuntimeError("Grok didn't answer just now.") from exc
    raise RuntimeError("Grok didn't answer just now.") from last_err


def _json_out(text: str) -> dict:
    try:
        block = text[text.index("{"): text.rindex("}") + 1]
        out = json.loads(block)
        if isinstance(out, dict) and isinstance(out.get("say", ""), str):
            return out
    except ValueError:
        pass
    return {"say": text.strip(), "actions": []}


def _clean_actions(raw, ctx: dict, today: date) -> tuple[list[dict], list[dict]]:
    """Checks every action against what really exists; returns (run now, ask first)."""
    ids = {i["id"]: i for i in ctx["calendar"]}
    routines = {t["id"] for t in ctx["routines"]}
    school = {a["id"] for a in ctx["school_next_2_weeks"]}
    waiting = {w["id"]: w for w in ctx["expenses"]["waiting_for_approval"]}
    now_list, ask = [], []
    new_items: list[dict] = []
    for a in raw if isinstance(raw, list) else []:
        if not isinstance(a, dict):
            continue
        t = a.get("type")
        if t == "schedule":
            for r in a.get("items") or []:
                item = agenda.normalize(r, today) if isinstance(r, dict) else None
                if item:
                    new_items.append(item)
        elif t == "delete":
            got = [{"id": i, "title": ids[i]["title"], "date": ids[i].get("date"), "time": ids[i].get("time")} for i in a.get("ids") or [] if i in ids]
            if got:
                ask.append({"type": "delete", "items": got})
        elif t == "approve_expense":
            got = [waiting[i] for i in a.get("ids") or [] if i in waiting]
            if got:
                ask.append({"type": "approve_expense", "items": got})
        elif t == "check" and a.get("id") in ids:
            now_list.append({"type": "check", "id": a["id"], "done": a.get("done") is not False, "title": ids[a["id"]]["title"]})
        elif t == "check_routine" and a.get("id") in routines:
            now_list.append({"type": "check_routine", "id": a["id"], "done": a.get("done") is not False})
        elif t == "check_school" and a.get("id") in school:
            now_list.append({"type": "check_school", "id": a["id"], "done": a.get("done") is not False})
        elif t == "push" and a.get("id") in ids:
            now_list.append({"type": "push", "id": a["id"], "back": bool(a.get("back"))})
        elif t == "open" and a.get("screen") in SCREENS:
            now_list.append({"type": "open", "screen": a["screen"]})
        elif t == "range":
            if a.get("key") in RANGE_KEYS:
                now_list.append({"type": "range", "key": a["key"]})
            elif agenda._valid_date(a.get("start")):
                end = agenda._valid_date(a.get("end")) or a["start"]
                now_list.append({"type": "range", "key": "custom", "start": a["start"], "end": end})
        elif t in ("nudges", "tax") and isinstance(a.get("on"), bool):
            now_list.append({"type": t, "on": a["on"]})
        elif t == "recap" and a.get("kind") in ("morning", "afternoon", "evening"):
            now_list.append({"type": "recap", "kind": a["kind"]})
        elif t == "wake" and (a.get("time") == "" or agenda._valid_time(a.get("time"))):
            now_list.append({"type": "wake", "time": a.get("time") or ""})
        elif t == "voice" and str(a.get("name", "")).lower() in morning.VOICES:
            now_list.append({"type": "voice", "name": str(a["name"]).lower()})
        elif t == "hide_notification" and a.get("id"):
            now_list.append({"type": "hide_notification", "id": str(a["id"])})
    if new_items:
        ask.insert(0, {"type": "schedule", "items": new_items[:10]})
    return now_list, ask


def reply(history: list[dict], ctx: dict, now: datetime) -> dict:
    convo = [{"role": "user" if m.get("role") == "user" else "assistant", "content": str(m.get("content") or "")[:2000]}
             for m in history[-16:] if str(m.get("content") or "").strip()]
    if not convo or convo[-1]["role"] != "user":
        raise ValueError("Say something first.")
    system = RULES + "\n\nSNAPSHOT:\n" + json.dumps(ctx, separators=(",", ":"), default=str)
    out = _json_out(_call([{"role": "system", "content": system}, *convo]))
    run, ask = _clean_actions(out.get("actions"), ctx, now.date())
    say = re.sub(r"\n{3,}", "\n\n", (out.get("say") or "").strip())[:2400]
    if not say:
        say = "Here's what I'll add." if ask else "Done." if run else "I'm not sure what you mean. Try saying it another way."
    return {"say": say, "actions": run, "ask": ask}


def spoken(say: str) -> str:
    """What the voice reads: the reply without the ** marks, $1,234 left for the voice to say naturally."""
    return re.sub(r"\*\*|[#_`]", "", say).replace("•", "").strip()[:1500]
