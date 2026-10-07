"""
Today's weather for the morning brief, from Open-Meteo (free, no key).

The location comes from the device itself (the phone's / Mac's own location services, asked by the browser when the
brief opens), so nothing is set in Moderator. The last spot is remembered, so the brief still has weather if the
location answer is slow or turned off.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import unquote

import requests

from store import db

LAST = "weather:last_location"
CITY = "weather:city"              # set in Moderator: beats every automatic guess
GEO = "https://geocoding-api.open-meteo.com/v1/search"
API = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes → (plain words, icon)
CODES = {
    0: ("clear", "sun"), 1: ("mostly clear", "sun"), 2: ("partly cloudy", "partly"), 3: ("cloudy", "cloud"),
    45: ("foggy", "fog"), 48: ("foggy", "fog"),
    51: ("light drizzle", "rain"), 53: ("drizzle", "rain"), 55: ("heavy drizzle", "rain"), 56: ("freezing drizzle", "rain"), 57: ("freezing drizzle", "rain"),
    61: ("light rain", "rain"), 63: ("rain", "rain"), 65: ("heavy rain", "rain"), 66: ("freezing rain", "rain"), 67: ("freezing rain", "rain"),
    71: ("light snow", "snow"), 73: ("snow", "snow"), 75: ("heavy snow", "snow"), 77: ("snow", "snow"),
    80: ("showers", "rain"), 81: ("showers", "rain"), 82: ("heavy showers", "rain"), 85: ("snow showers", "snow"), 86: ("snow showers", "snow"),
    95: ("thunderstorms", "storm"), 96: ("thunderstorms", "storm"), 99: ("thunderstorms", "storm"),
}


def uv_level(uv: float) -> str:
    return "low" if uv < 3 else "moderate" if uv < 6 else "high" if uv < 8 else "very high" if uv < 11 else "extreme"


def _clock(stamp: str) -> str:
    return datetime.fromisoformat(stamp).strftime("%-I:%M %p").replace(":00 ", " ")


def from_headers(headers) -> dict | None:
    """Where the request came from, as Vercel sees it (city-level, from the network). No permission needed."""
    try:
        lat, lon = headers.get("x-vercel-ip-latitude"), headers.get("x-vercel-ip-longitude")
        if lat and lon:
            return {"lat": round(float(lat), 3), "lon": round(float(lon), 3), "city": unquote(headers.get("x-vercel-ip-city") or "")[:60]}
    except (TypeError, ValueError):
        pass
    return None


def location(lat=None, lon=None, city: str = "", ip: dict | None = None) -> dict | None:
    """The spot to use, best first: the device's own location (sent when its permission is already on, remembered),
    the last device location if you're still in that area (the network's guess only says you're nearby),
    the network's location (you're somewhere else: travelling), and finally the last spot we had."""
    fixed = db.get(CITY)
    if fixed and fixed.get("lat") is not None:
        return fixed
    saved = db.get(LAST) or None
    try:
        if lat is not None and lon is not None and -90 <= float(lat) <= 90 and -180 <= float(lon) <= 180:
            spot = {"lat": round(float(lat), 3), "lon": round(float(lon), 3), "city": str(city or "")[:60]}
            if not spot["city"] and _near(saved, spot, 0.2):
                spot["city"] = saved.get("city", "")
            db.set(LAST, spot)
            return spot
    except (TypeError, ValueError):
        pass
    if ip:
        if saved and _near(saved, ip, 0.7):          # about 50 miles: same area, keep the precise spot
            return saved
        return ip
    return saved


def find_city(text: str) -> dict | None:
    """'Austin' or 'Austin, TX' / 'Paris, France' → the place (Open-Meteo's free geocoder)."""
    name, _, hint = str(text or "").partition(",")
    name, hint = name.strip(), hint.strip().lower()
    if not name:
        return None
    try:
        resp = requests.get(GEO, timeout=8, params={"name": name, "count": 10, "language": "en", "format": "json"})
        results = (resp.json() if resp.ok else {}).get("results") or []
    except (requests.RequestException, ValueError):
        raise RuntimeError("Couldn't look that city up right now. Try again.")
    if hint:
        states = {"al": "alabama", "ak": "alaska", "az": "arizona", "ar": "arkansas", "ca": "california", "co": "colorado", "ct": "connecticut",
                  "de": "delaware", "fl": "florida", "ga": "georgia", "hi": "hawaii", "id": "idaho", "il": "illinois", "in": "indiana", "ia": "iowa",
                  "ks": "kansas", "ky": "kentucky", "la": "louisiana", "me": "maine", "md": "maryland", "ma": "massachusetts", "mi": "michigan",
                  "mn": "minnesota", "ms": "mississippi", "mo": "missouri", "mt": "montana", "ne": "nebraska", "nv": "nevada", "nh": "new hampshire",
                  "nj": "new jersey", "nm": "new mexico", "ny": "new york", "nc": "north carolina", "nd": "north dakota", "oh": "ohio", "ok": "oklahoma",
                  "or": "oregon", "pa": "pennsylvania", "ri": "rhode island", "sc": "south carolina", "sd": "south dakota", "tn": "tennessee", "tx": "texas",
                  "ut": "utah", "vt": "vermont", "va": "virginia", "wa": "washington", "wv": "west virginia", "wi": "wisconsin", "wy": "wyoming"}
        want = states.get(hint, hint)
        matched = [r for r in results if want in (str(r.get("admin1", "")) + " " + str(r.get("country", "")) + " " + str(r.get("country_code", ""))).lower()]
        results = matched or results
    if not results:
        return None
    r = results[0]                                                  # the geocoder lists the biggest match first
    return {"lat": round(r["latitude"], 3), "lon": round(r["longitude"], 3), "city": r.get("name", name),
            "label": ", ".join(x for x in (r.get("name"), r.get("admin1"), None if r.get("country_code") == "US" else r.get("country")) if x)}


def set_city(text: str) -> dict | None:
    """Moderator → Weather city. Empty = automatic again."""
    if not str(text or "").strip():
        db.delete(CITY)
        return None
    spot = find_city(text)
    if not spot:
        raise ValueError(f"Couldn't find \"{text.strip()}\". Try adding the state, like \"Austin, TX\".")
    db.set(CITY, spot)
    return spot


def _near(a: dict | None, b: dict, degrees: float) -> bool:
    return bool(a) and abs(a["lat"] - b["lat"]) < degrees and abs(a["lon"] - b["lon"]) < degrees


def today(spot: dict | None, now: datetime) -> dict | None:
    """High / low, conditions, UV (peak and when), rain chance, sunset, and a few hours ahead. None if it can't be had."""
    if not spot:
        return None
    cache = f"weather:v3:{now.date().isoformat()}:{spot['lat']:.2f}:{spot['lon']:.2f}:{now.hour}"
    saved = db.get(cache)
    if saved:
        return saved
    try:
        resp = requests.get(API, timeout=8, params={
            "latitude": spot["lat"], "longitude": spot["lon"], "timezone": "auto", "forecast_days": 2,   # 2 days: the strip runs past midnight
            "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
            "current": "temperature_2m,weather_code,is_day,apparent_temperature",
            "hourly": "temperature_2m,weather_code,uv_index,precipitation_probability,is_day",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,uv_index_max,precipitation_probability_max,sunrise,sunset,wind_speed_10m_max",
        })
        data = resp.json() if resp.ok else {}
    except (requests.RequestException, ValueError):
        return None
    daily, hourly, current = data.get("daily") or {}, data.get("hourly") or {}, data.get("current") or {}
    if not daily.get("time"):
        return None
    first = lambda key: (daily.get(key) or [None])[0]
    code = first("weather_code") or 0
    words, icon = CODES.get(code, ("mixed", "partly"))
    times = hourly.get("time") or []
    uvs = hourly.get("uv_index") or []
    day_idx = [i for i, t in enumerate(times) if t.startswith(now.date().isoformat())]   # today's hours only
    peak_i = max(day_idx, key=lambda i: uvs[i] or 0) if uvs and day_idx else None
    hours = _strip(now, times, hourly, first("sunset") or "")
    uv = first("uv_index_max") or 0
    out = {
        "city": spot.get("city", ""),
        "words": words, "icon": icon, "code": code,
        "now": round(current.get("temperature_2m")) if current.get("temperature_2m") is not None else None,
        "feels": round(current.get("apparent_temperature")) if current.get("apparent_temperature") is not None else None,
        "high": round(first("temperature_2m_max") or 0), "low": round(first("temperature_2m_min") or 0),
        "rain": first("precipitation_probability_max") or 0,
        "wind": round(first("wind_speed_10m_max") or 0),
        "uv": round(uv, 1), "uv_level": uv_level(uv),
        "uv_peak": _clock(times[peak_i]) if peak_i is not None and times else None,
        "sunrise": _clock(first("sunrise")) if first("sunrise") else None,
        "sunset": _clock(first("sunset")) if first("sunset") else None,
        "hours": hours,
    }
    db.set(cache, out, ttl=3600)
    return out


def _strip(now: datetime, times: list, hourly: dict, sunset_at: str) -> list[dict]:
    """The hourly strip: the day in even steps up to an hour after sunset (rounded to the nearest hour), the exact
    sunset time in its place, then one value for the night (tonight's low)."""
    temps = hourly.get("temperature_2m") or []
    codes = hourly.get("weather_code") or []
    rain = hourly.get("precipitation_probability") or []
    is_day = hourly.get("is_day") or []

    def cell(i: int, label: str) -> dict:
        c = codes[i] if i < len(codes) and codes[i] is not None else 0
        return {"time": label, "temp": round(temps[i] or 0) if i < len(temps) else None, "icon": CODES.get(c, ("", "partly"))[1],
                "night": not (is_day[i] if i < len(is_day) else 1), "rain": (rain[i] if i < len(rain) else 0) or 0}

    stamp = lambda dt: dt.strftime("%Y-%m-%dT%H:00")
    index = {t: i for i, t in enumerate(times)}
    here = now.replace(minute=0, second=0, microsecond=0, tzinfo=None)
    start = index.get(stamp(here))
    if start is None:
        return []
    try:
        sunset = datetime.fromisoformat(sunset_at) if sunset_at else None
    except ValueError:
        sunset = None
    if sunset is None:
        sunset = here.replace(hour=19)
    after = sunset + timedelta(hours=1)                                   # an hour after sunset, to the nearest hour
    cutoff = after.replace(minute=0) + (timedelta(hours=1) if after.minute >= 30 else timedelta(0))
    out: list[dict] = [cell(start, "Now")]
    span = int((cutoff - here).total_seconds() // 3600)
    if span > 0:
        step = max(3, -(-span // 4))                                       # at most 4 steps after "now"
        k = step
        while k < span - 1:                                                # even steps, then the cutoff hour itself
            i = index.get(stamp(here + timedelta(hours=k)))
            if i is not None:
                out.append(cell(i, _clock(times[i])))
            k += step
        i = index.get(stamp(cutoff))
        if i is not None:
            out.append(cell(i, _clock(times[i])))
    sunset_cell = {"time": _clock(sunset_at), "sunset": True} if sunset_at else None
    if sunset_cell:                                                        # the exact sunset, in time order
        pos = 0 if sunset <= now.replace(tzinfo=None) else next((n for n, c in enumerate(out) if n > 0 and _cell_time(c, here) > sunset), len(out))
        out.insert(pos, sunset_cell)
    # one value for the night: the low between then and 6 AM, with the conditions around midnight
    night_end = (cutoff + timedelta(days=1)).replace(hour=6) if cutoff.hour >= 6 else cutoff.replace(hour=6)
    span_idx = [index[stamp(cutoff + timedelta(hours=h))] for h in range(1, 13)
                if stamp(cutoff + timedelta(hours=h)) in index and cutoff + timedelta(hours=h) <= night_end]
    if span_idx:
        low_i = min(span_idx, key=lambda i: temps[i] if i < len(temps) and temps[i] is not None else 999)
        mid_i = span_idx[len(span_idx) // 2]
        tonight = cell(mid_i, "Tonight")
        tonight.update({"temp": round(temps[low_i] or 0), "night": True, "tonight": True,
                        "rain": max((rain[i] or 0) for i in span_idx) if rain else 0})
        out.append(tonight)
    return out


def _cell_time(c: dict, here: datetime) -> datetime:
    """When a strip cell is (for placing sunset among them)."""
    if c.get("time") == "Now":
        return here
    t = datetime.strptime(c["time"].replace(" ", ""), "%I%p") if ":" not in c["time"] else datetime.strptime(c["time"].replace(" ", ""), "%I:%M%p")
    moment = here.replace(hour=t.hour, minute=t.minute)
    return moment if moment >= here else moment + timedelta(days=1)


def line(w: dict | None) -> str:
    """The spoken weather line."""
    if not w:
        return ""
    where = f" in {w['city']}" if w.get("city") else ""
    text = f"Today{where}: {w['words']}, with a high of {w['high']} and a low of {w['low']}."
    if w.get("rain", 0) >= 30:
        text += f" There's a {w['rain']} percent chance of rain."
    uv = round(w.get("uv") or 0)
    text += f" UV peaks at {uv}, {w['uv_level']}" + (f", around {w['uv_peak']}." if w.get("uv_peak") and uv >= 1 else ".")
    if w.get("sunset"):
        text += f" Sunset is at {w['sunset']}."
    return text
