"""
All the money math lives here.

For any date range:
    Gross        what fans paid (Fanvue)
  - Fanvue cut   gross x Fanvue %                       (Moderator, default 20%; a change starts next week)
  - Chatter cut  real invoices / payroll where they exist; for agency weeks with
                 no invoice yet: (Messages + Tips gross) x (1 - Fanvue %) x Chatter %
  - Opex         every approved expense that isn't chatter pay
  - Tax          optional, % of what's left
  = Net

Agency weeks: see WEEK_STARTS_ON / INVOICE_LAG_DAYS below (PT). An invoice is spread
across the days of the week it pays for, in proportion to each day's Messages + Tips,
so any date range (even "Today") gets its fair share instead of landing on one day.

The chart's Net is simpler on purpose: gross - Fanvue cut - chatter formula
(no invoices, no expenses), because those can't be split by the hour.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

BUSINESS_START = date(2026, 4, 1)       # "All time" starts here everywhere (first month of Fanvue earnings)
AGENCY_START = date(2026, 7, 20)        # first day the chatting agency worked
# Agency week definition (Python weekday: Monday=0 ... Sunday=6).
#   Monday-Sunday weeks billed on that Sunday:      WEEK_STARTS_ON = 0, INVOICE_LAG_DAYS = 0
#   Sunday-Saturday weeks billed the Sunday after:  WEEK_STARTS_ON = 6, INVOICE_LAG_DAYS = 1
# The agency's invoices run Monday-Sunday (e.g. Sep 14 - Sep 20, Sep 21 - Sep 27) on SERBIAN time:
# a week closes Sunday 11:59 PM in Belgrade, which is Sunday ~2:59 PM Pacific (the 9-hour gap
# shifts by an hour for a week or two around daylight-saving changes; zoneinfo handles that).
# So the last ~9 hours of each PT Sunday already count toward the NEXT week.
WEEK_STARTS_ON = 0
INVOICE_LAG_DAYS = 0
PT = ZoneInfo("America/Los_Angeles")
AGENCY_TZ = ZoneInfo("Europe/Belgrade")
RATE_CHANGE_SUNDAY = date(2026, 8, 30)  # weeks billed on this Sunday or later use the Moderator chatter %
OLD_CHATTER_RATE = 0.20                 # agency rate for weeks billed before Aug 30, 2026
AGENCY = "agency payout"
PAYROLL = "chatter payroll"
CHATTER_CATEGORIES = {AGENCY, PAYROLL}

RANGES = [
    ("today", "Today"),
    ("yesterday", "Yesterday"),
    ("last_7", "Last 7 days"),
    ("last_14", "Last 14 days"),
    ("last_30", "Last 30 days"),
    ("this_week", "This week"),
    ("this_month", "This month"),
    ("this_year", "This year"),
    ("all_time", "All time"),
]


def sunday_on_or_before(d: date) -> date:
    return d - timedelta(days=(d.weekday() + 1) % 7)


def week_start(d: date) -> date:
    """First day of d's agency week."""
    return d - timedelta(days=(d.weekday() - WEEK_STARTS_ON) % 7)


def bill_date(d: date) -> date:
    """The day d's agency week is invoiced on (its last day + INVOICE_LAG_DAYS)."""
    return week_start(d) + timedelta(days=6 + INVOICE_LAG_DAYS)


# Weeks are keyed by their bill date.
bill_sunday = bill_date


def invoice_key(invoice_date: date) -> date:
    """Which week an invoice row pays for: the latest bill date on or before the invoice's date
    (an invoice dated a day or two late still pays for the week that just closed)."""
    key = bill_date(invoice_date)
    return key if key <= invoice_date else key - timedelta(days=7)


def week_days(key: date) -> list[date]:
    """The 7 days of the week billed on `key`."""
    first = key - timedelta(days=6 + INVOICE_LAG_DAYS)
    return [first + timedelta(days=i) for i in range(7)]


@lru_cache(maxsize=20000)
def hour_key(d: date, hour: int) -> date:
    """Which agency week (bill date) the PT hour `hour` of PT day `d` belongs to (Serbian clock)."""
    return bill_date(datetime(d.year, d.month, d.day, hour, tzinfo=PT).astimezone(AGENCY_TZ).date())


def current_key(now: datetime) -> date:
    """The agency week that's open right now."""
    return bill_date(now.astimezone(AGENCY_TZ).date())


def week_close(key: date) -> datetime:
    """When the week billed on `key` closes (Sunday 11:59 PM Serbia), in PT."""
    nxt = key + timedelta(days=1)
    return datetime(nxt.year, nxt.month, nxt.day, tzinfo=AGENCY_TZ).astimezone(PT) - timedelta(minutes=1)


def week_hours(key: date):
    """(PT day, PT hour) pairs that make up the week billed on `key`."""
    for back in range(8, -1, -1):
        d = key - timedelta(days=back)
        for hour in range(24):
            if hour_key(d, hour) == key:
                yield d, hour


def hour_base(rec: dict | None, hour: int) -> float:
    """Messages + Tips gross in one PT hour."""
    return rec["h"][hour][1] / 100 if rec and rec.get("h") else 0.0


def each_day(first: date, last: date):
    d = first
    while d <= last:
        yield d
        d += timedelta(days=1)


def day_gross(rec: dict | None) -> float:
    return sum(v[0] for v in rec["s"].values()) / 100 if rec else 0.0


def day_chatter_base(rec: dict | None) -> float:
    """Messages + Tips gross for the day."""
    if not rec:
        return 0.0
    return sum(rec["s"].get(src, [0, 0])[0] for src in ("messages", "tips")) / 100


# ---------- Rates that switch on a week boundary ----------
# Changing the Fanvue % or Chatter % in Moderator never rewrites the past: the new rate is
# stored in settings["rate_history"] as {"from": <a Monday>, "fanvue_rate", "chatter_rate"} and
# applies from the start of the NEXT agency week. Days before it keep the rate they had.

def _rates(d: date, settings: dict) -> dict:
    start = week_start(d).isoformat()
    current = {"fanvue_rate": settings["fanvue_rate"], "chatter_rate": settings["chatter_rate"]}
    for entry in sorted(settings.get("rate_history") or [], key=lambda e: e["from"]):
        if entry["from"] <= start:
            current = entry
    return current


def fanvue_rate(d: date, settings: dict) -> float:
    return _rates(d, settings)["fanvue_rate"]


def chatter_rate(d: date, settings: dict) -> float:
    return _rates(d, settings)["chatter_rate"] if bill_sunday(d) >= RATE_CHANGE_SUNDAY else OLD_CHATTER_RATE


def week_rates(key: date, settings: dict) -> tuple[float, float]:
    """(Fanvue %, Chatter %) for the agency week billed on `key` (set when that week started)."""
    r = _rates(week_days(key)[0], settings)
    return r["fanvue_rate"], (r["chatter_rate"] if key >= RATE_CHANGE_SUNDAY else OLD_CHATTER_RATE)


def next_week_start(today: date) -> date:
    return week_start(today) + timedelta(days=7)


def schedule_rates(settings: dict, fanvue: float, chatter: float, today: date) -> list[dict]:
    """New rate history after asking for these rates: they start next week (or cancel a pending change)."""
    switch = next_week_start(today).isoformat()
    history = [e for e in settings.get("rate_history") or [] if e["from"] < switch]
    before = _rates(next_week_start(today) - timedelta(days=1), {**settings, "rate_history": history})
    if abs(before["fanvue_rate"] - fanvue) > 1e-9 or abs(before["chatter_rate"] - chatter) > 1e-9:
        history.append({"from": switch, "fanvue_rate": fanvue, "chatter_rate": chatter})
    return history


def rate_status(settings: dict, today: date) -> dict:
    """What Moderator shows: the rate in effect now and any change waiting for next week."""
    now, nxt = _rates(today, settings), _rates(next_week_start(today), settings)
    pending = now != nxt
    return {"fanvue_now": now["fanvue_rate"], "chatter_now": now["chatter_rate"],
            "fanvue_set": nxt["fanvue_rate"], "chatter_set": nxt["chatter_rate"],
            "switch_on": next_week_start(today).isoformat() if pending else None}


def chatter_formula(messages_tips_gross: float, d: date, settings: dict) -> float:
    return messages_tips_gross * (1 - fanvue_rate(d, settings)) * chatter_rate(d, settings)


def chatter_cost_by_day(days: dict, expenses: list[dict], settings: dict, today: date) -> dict[str, float]:
    """Chatter cost per PT day. Weeks follow the Serbian clock, so they're built hour by hour:
    an invoice is spread over its week's hours by Messages + Tips; a week with no invoice yet
    uses the formula hour by hour. Payroll lands on its own date."""
    cost: dict[str, float] = defaultdict(float)
    invoices: dict[date, float] = defaultdict(float)
    for e in expenses:
        if e["status"] != "verified":
            continue
        cat = e["category"].lower()
        if cat == AGENCY:
            invoices[invoice_key(date.fromisoformat(e["date"]))] += e["amount"]
        elif cat == PAYROLL:
            cost[e["date"]] += e["amount"]

    first_key, last_key = bill_date(AGENCY_START), bill_date(today) + timedelta(days=7)
    keys = sorted({*invoices, *(first_key + timedelta(days=7 * i) for i in range((last_key - first_key).days // 7 + 1))})
    for key in keys:
        hours = [(d, h) for d, h in week_hours(key) if d <= today]
        if not hours:
            continue
        weights = [hour_base(days.get(d.isoformat()), h) for d, h in hours]
        if key in invoices:
            total = sum(weights)
            for (d, _), w in zip(hours, weights):
                cost[d.isoformat()] += invoices[key] * (w / total if total > 0 else 1 / len(hours))
        elif key >= first_key:
            fv, ch = week_rates(key, settings)
            for (d, _), w in zip(hours, weights):
                cost[d.isoformat()] += w * (1 - fv) * ch
    return cost


def week_formula(days: dict, key: date, settings: dict) -> float:
    """What the agency is owed for the week billed on `key`, by the formula (Serbian-clock week)."""
    if key < bill_date(AGENCY_START):
        return 0.0
    fv, ch = week_rates(key, settings)
    return round(sum(hour_base(days.get(d.isoformat()), h) for d, h in week_hours(key)) * (1 - fv) * ch, 2)


def gross_by_month(days: dict, today: date) -> dict[str, float]:
    """Gross earnings per calendar month (PT), e.g. {"2026-10": 1234.5}."""
    months: dict[str, float] = defaultdict(float)
    for d, rec in days.items():
        if BUSINESS_START.isoformat() <= d <= today.isoformat():
            months[d[:7]] += day_gross(rec)
    return {m: round(v, 2) for m, v in months.items()}


def fanvue_months(days: dict, settings: dict, today: date) -> list[dict]:
    """Fanvue's cut per calendar month (PT), newest first. The current month is live."""
    months: dict[str, float] = defaultdict(float)
    for d, rec in days.items():
        if BUSINESS_START.isoformat() <= d <= today.isoformat():
            months[d[:7]] += day_gross(rec) * fanvue_rate(date.fromisoformat(d), settings)
    current = today.isoformat()[:7]
    months.setdefault(current, 0.0)
    return [
        {"month": m, "label": date.fromisoformat(m + "-01").strftime("%B %Y"), "amount": round(v, 2), "live": m == current}
        for m, v in sorted(months.items(), reverse=True)
    ]


def _add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    year, month = d.year + y, m + 1
    last = (date(year + (month // 12), month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(d.day, last))


def spread_expenses(expenses: list[dict], spreads: dict) -> list[dict]:
    """Monthly payment (dashboard only, never the sheet): a big OPEX charge counted as N equal monthly parts,
    the first on the day it was paid, then the same day each following month (last part takes the rounding)."""
    if not spreads:
        return expenses
    out = []
    for e in expenses:
        months = int(spreads.get(e.get("id")) or 0)
        if months < 2 or e.get("category", "").lower() in CHATTER_CATEGORIES:
            out.append(e)
            continue
        paid = date.fromisoformat(e["date"])
        each = round(e["amount"] / months, 2)
        for k in range(months):
            amount = each if k < months - 1 else round(e["amount"] - each * (months - 1), 2)
            out.append({**e, "date": _add_months(paid, k).isoformat(), "amount": amount,
                        "spread": {"part": k + 1, "of": months, "total": e["amount"], "paid": e["date"]}})
    return out


def totals(days: dict, expenses: list[dict], settings: dict, lo: date, hi: date, today: date) -> dict:
    lo_s, hi_s = lo.isoformat(), hi.isoformat()
    gross = sum(day_gross(rec) for d, rec in days.items() if lo_s <= d <= hi_s)
    fanvue_cut = sum(day_gross(rec) * fanvue_rate(date.fromisoformat(d), settings) for d, rec in days.items() if lo_s <= d <= hi_s)
    chatter = sum(v for d, v in chatter_cost_by_day(days, expenses, settings, today).items() if lo_s <= d <= hi_s)
    opex = sum(
        e["amount"] for e in expenses
        if e["status"] == "verified" and e["category"].lower() not in CHATTER_CATEGORIES and lo_s <= e["date"] <= hi_s
    )
    after_opex = gross - fanvue_cut - chatter - opex
    tax = max(after_opex, 0) * settings["tax_rate"] if settings["tax_enabled"] else 0.0
    out = {
        "gross": gross,
        "fanvue_cut": fanvue_cut,
        "chatter_cut": chatter,
        "opex": opex,
        "after_opex": after_opex,
        "tax_cut": tax,
        "net": after_opex - tax,
    }
    return {k: round(v, 2) for k, v in out.items()}


def _custom_label(lo: date, hi: date) -> str:
    if lo == hi:
        return lo.strftime("%b %-d, %Y")
    if lo.year == hi.year:
        return f"{lo.strftime('%b %-d')} – {hi.strftime('%b %-d')}"
    return f"{lo.strftime('%b %-d, %Y')} – {hi.strftime('%b %-d, %Y')}"


def resolve_range(key: str, today: date, first_day: date, first_earning_day: date,
                  start: date | None = None, end: date | None = None) -> dict:
    """A preset range, or key="custom" with start/end from the calendar picker.
    Custom: one day = hourly bars, up to 14 days = daily bars, longer = line."""
    if key == "custom" and start:
        clamp = lambda d: max(BUSINESS_START, min(d, today))  # noqa: E731
        lo, hi = sorted((clamp(start), clamp(end or start)))
        span = (hi - lo).days + 1
        kind = "hourly" if span == 1 else "bars" if span <= 14 else "line"
        return {"key": "custom", "label": _custom_label(lo, hi), "lo": lo, "hi": hi,
                "chart_lo": lo, "chart_hi": hi, "kind": kind}
    labels = dict(RANGES)
    key = key if key in labels else "today"
    kind, chart_hi = "line", None
    if key == "today":
        lo, hi, kind = today, today, "hourly"
    elif key == "yesterday":
        lo = hi = today - timedelta(days=1)
        kind = "hourly"
    elif key == "last_7":
        lo, hi, kind = today - timedelta(days=6), today, "bars"
    elif key == "this_week":
        lo, hi, kind = today - timedelta(days=today.weekday()), today, "bars"
        chart_hi = lo + timedelta(days=6)  # show the whole week through Sunday
    elif key == "last_14":
        lo, hi = today - timedelta(days=13), today
    elif key == "last_30":
        lo, hi = today - timedelta(days=29), today
    elif key == "this_month":
        lo, hi = today.replace(day=1), today
    elif key == "this_year":
        lo, hi = today.replace(month=1, day=1), today
    else:  # all_time: everything since BUSINESS_START
        return {"key": key, "label": labels[key], "lo": BUSINESS_START, "hi": today,
                "chart_lo": BUSINESS_START, "chart_hi": today, "kind": "line"}
    lo = max(lo, BUSINESS_START)  # nothing before the business started (e.g. "This year")
    return {"key": key, "label": labels[key], "lo": lo, "hi": hi,
            "chart_lo": lo, "chart_hi": chart_hi or hi, "kind": kind}


def chart_points(days: dict, settings: dict, rng: dict, now: datetime) -> list[dict]:
    today = now.date()
    points = []

    def point(label: str, gross: float, chatter_base: float, d: date, future: bool) -> dict:
        if future:
            return {"label": label, "gross": None, "net": None}
        net = gross - gross * fanvue_rate(d, settings) - chatter_formula(chatter_base, d, settings)
        return {"label": label, "gross": round(gross, 2), "net": round(net, 2)}

    if rng["kind"] == "hourly":
        d = rng["lo"]
        rec = days.get(d.isoformat())
        for h in range(24):
            gross, base = (rec["h"][h][0] / 100, rec["h"][h][1] / 100) if rec else (0.0, 0.0)
            label = f"{(h % 12) or 12} {'AM' if h < 12 else 'PM'}"
            points.append(point(label, gross, base, d, d == today and h > now.hour))
        return points

    for d in each_day(rng["chart_lo"], rng["chart_hi"]):
        rec = days.get(d.isoformat())
        label = (d.strftime("%b %-d") if rng["key"] == "custom" else d.strftime("%a %-d")) if rng["kind"] == "bars" else d.strftime("%b %-d, %Y")
        points.append(point(label, day_gross(rec), day_chatter_base(rec), d, d > today))
    return points


# ---------- Tax estimate (2026, single, California sole proprietor; an estimate, not a filing) ----------

FED_BRACKETS = [(12400, 0.10), (50400, 0.12), (105700, 0.22), (201775, 0.24),
                (256225, 0.32), (640600, 0.35), (float("inf"), 0.37)]
CA_BRACKETS = [(11079, 0.01), (26264, 0.02), (41452, 0.04), (57542, 0.06), (72724, 0.08),
               (371479, 0.093), (445771, 0.103), (742953, 0.113), (1000000, 0.123), (float("inf"), 0.133)]
FED_STANDARD_DEDUCTION = 16100
CA_STANDARD_DEDUCTION = 5706
CA_PERSONAL_CREDIT = 153


def _bracket_tax(income: float, brackets: list[tuple[float, float]]) -> float:
    tax, floor = 0.0, 0.0
    for ceiling, rate in brackets:
        if income <= floor:
            break
        tax += (min(income, ceiling) - floor) * rate
        floor = ceiling
    return tax


def estimate_tax(profit: float) -> dict:
    if profit <= 0:
        return {"self_employment": 0.0, "federal": 0.0, "california": 0.0, "total": 0.0, "rate": 0.0}
    se = profit * 0.9235 * 0.153
    agi = profit - se / 2
    before_qbi = max(agi - FED_STANDARD_DEDUCTION, 0)
    qbi = min(agi * 0.20, before_qbi * 0.20)
    federal = _bracket_tax(before_qbi - qbi, FED_BRACKETS)
    california = max(_bracket_tax(max(agi - CA_STANDARD_DEDUCTION, 0), CA_BRACKETS) - CA_PERSONAL_CREDIT, 0)
    total = se + federal + california
    return {
        "self_employment": round(se, 2),
        "federal": round(federal, 2),
        "california": round(california, 2),
        "total": round(total, 2),
        "rate": round(total / profit, 4),
    }
