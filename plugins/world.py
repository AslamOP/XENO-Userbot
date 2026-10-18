"""XENO world module: weather, globe info, currency, zone-time, network lookups.
All free, no API keys. Original code."""
from datetime import datetime, timedelta, timezone as _tz
from zoneinfo import ZoneInfo, available_timezones

from core.command import command
from core.http import get_json, get_text


def _zone_now(zone):
    """Return (local datetime, UTC offset string, abbreviation) for an IANA zone.

    Returns (None, None, None) if the zone is unknown. Uses the system tzdata,
    so no network call and no dependency on the dead worldtimeapi.org.
    """
    try:
        tz = ZoneInfo(zone)
    except Exception:
        return None, None, None
    now = datetime.now(tz)
    off = now.utcoffset() or timedelta(0)
    sign = "+" if off >= timedelta(0) else "-"
    off_h, off_m = divmod(abs(int(off.total_seconds())), 3600)
    return now, f"UTC{sign}{off_h:02d}:{off_m:02d}", (now.tzname() or zone.split("/")[-1])


@command("zones")
async def zones_cmd(event):
    """Search available IANA timezones. Usage: `.zones <substring>`"""
    a = event.text.split(maxsplit=1)
    q = a[1].strip().lower() if len(a) > 1 else ""
    if not q:
        return await event.reply("Give a filter. Usage: `.zones kolkata`")
    try:
        names = sorted(z for z in available_timezones() if q in z.lower())[:30]
    except Exception as e:
        return await event.reply(f"Error: `{e}`")
    if not names:
        return await event.reply(f"No timezone matches `{q}`.")
    await event.reply(f"**🗺 Timezones matching `{q}`:**\n" + "\n".join(f"• `{z}`" for z in names))


@command("weather")
async def weather_cmd(event):
    """Current weather for a city. Usage: `.weather <city>`"""
    a = event.text.split(maxsplit=1)
    city = a[1].strip() if len(a) > 1 else ""
    if not city:
        return await event.reply("Give a city. Usage: `.weather <city>`")
    try:
        geo = await get_json("https://geocoding-api.open-meteo.com/v1/search",
                             {"name": city, "count": 1, "language": "en"})
        results = geo.get("results") or []
        if not results:
            return await event.reply(f"City `{city}` not found.")
        r = results[0]
        w = await get_json(
            "https://api.open-meteo.com/v1/forecast",
            {"latitude": r["latitude"], "longitude": r["longitude"],
             "current_weather": "true"})
        c = w.get("current_weather", {})
        name = r.get("name", city)
        country = r.get("country", "")
        temp = c.get("temperature", "?")
        wind = c.get("windspeed", "?")
        wcode = c.get("weathercode", 0)
        desc = _code_map().get(wcode, "Unknown")
        await event.reply(
            f"**🌤 {name}, {country}**\n"
            f"Temperature: `{temp}°C`\nWind: `{wind} km/h`\n"
            f"Sky: `{desc}`\nUpdated: `{c.get('time','')}`")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


def _code_map():
    return {0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle",
            53: "Drizzle", 55: "Dense drizzle", 61: "Light rain",
            63: "Rain", 65: "Heavy rain", 71: "Light snow", 73: "Snow",
            75: "Heavy snow", 77: "Snow grains", 80: "Light showers",
            81: "Showers", 82: "Violent showers", 85: "Snow showers",
            86: "Heavy snow showers", 95: "Thunderstorm", 96: "Thunderstorm + hail",
            99: "Severe thunderstorm"}


@command("forecast")
async def forecast_cmd(event):
    """7-day forecast for a city. Usage: `.forecast <city>`"""
    a = event.text.split(maxsplit=1)
    city = a[1].strip() if len(a) > 1 else ""
    if not city:
        return await event.reply("Give a city. Usage: `.forecast <city>`")
    try:
        geo = await get_json("https://geocoding-api.open-meteo.com/v1/search",
                             {"name": city, "count": 1})
        results = geo.get("results") or []
        if not results:
            return await event.reply(f"City `{city}` not found.")
        r = results[0]
        w = await get_json(
            "https://api.open-meteo.com/v1/forecast",
            {"latitude": r["latitude"], "longitude": r["longitude"],
             "daily": "temperature_2m_max,temperature_2m_min,weathercode",
             "forecast_days": 7})
        daily = w.get("daily", {})
        dmax = daily.get("temperature_2m_max", [])
        dmin = daily.get("temperature_2m_min", [])
        dcode = daily.get("weathercode", [])
        dates = daily.get("time", [])
        cmap = _code_map()
        lines = [f"**📅 Forecast: {r.get('name', city)}**", ""]
        for i, day in enumerate(dates):
            import datetime
            name = datetime.date.fromisoformat(day).strftime("%a")
            lines.append(f"`{name}` {cmap.get(dcode[i], '?')} | {dmin[i]}° / {dmax[i]}°")
        await event.reply("\n".join(lines))
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("country")
async def country_cmd(event):
    """Country info by name or code. Usage: `.country <name|code>`"""
    a = event.text.split(maxsplit=1)
    q = a[1].strip() if len(a) > 1 else ""
    if not q:
        return await event.reply("Give a country name or ISO code.")
    try:
        data = await get_json(f"https://restcountries.com/v3.1/name/{q}")
        if isinstance(data, dict):
            data = [data]
        if not data:
            return await event.reply(f"No country `{q}`.")
        c = data[0]
        lat = c.get("latlng", ["?", "?"])
        await event.reply(
            f"**🌍 {c.get('name', {}).get('common', q)}**\n"
            f"Code: `{c.get('cca3','?')}` | Capital: `{', '.join(c.get('capital', []) or ['?'])}`\n"
            f"Region: `{c.get('region','?')}` / `{c.get('subregion','?')}`\n"
            f"Population: `{c.get('population','?'):,}`\n"
            f"Languages: `{', '.join((c.get('languages') or {}).values())}`\n"
            f"Currency: `{', '.join((c.get('currencies') or {}).keys())}`\n"
            f"Coords: lat `{lat[0]}`, lon `{lat[1]}`")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("timezone")
async def timezone_cmd(event):
    """Current time in an IANA timezone. Usage: `.timezone <Asia/Kolkata>`"""
    a = event.text.split(maxsplit=1)
    zone = a[1].strip() if len(a) > 1 else ""
    if not zone:
        return await event.reply("Give a timezone. Usage: `.timezone <America/New_York>`")
    # Resolved locally with zoneinfo. The old worldtimeapi.org endpoint this used
    # has been shut down, so every call failed with a bare "not found".
    now, off, abbr = _zone_now(zone)
    if now is None:
        return await event.reply(f"Unknown timezone `{zone}`. Try `Asia/Kolkata`, `Europe/Berlin`.")
    await event.reply(
        f"**🕐 {zone}**\n"
        f"Time: `{now.strftime('%Y-%m-%d %H:%M:%S %Z')}`\n"
        f"UTC offset: `{off}`\n"
        f"Abbr: `{abbr}`"
    )


@command("cur")
async def cur_cmd(event):
    """Currency conversion. Usage: `.cur <amount> <USD> <INR>`"""
    a = event.text.split(maxsplit=3)
    if len(a) < 4:
        return await event.reply("Usage: `.cur <amount> <from> <to>`  e.g. `.cur 100 usd inr`")
    amount = a[1]
    frm = a[2].upper()
    to = a[3].upper()
    try:
        rate = await get_json(
            f"https://api.frankfurter.app/latest", {"from": frm, "to": to})
        if "rates" not in rate:
            return await event.reply(f"Cannot convert `{frm}` → `{to}`. Try USD/INR/EUR/GBP.")
        val = rate["rates"].get(to)
        amt = float(amount)
        total = amt * val
        await event.reply(f"**💱 {amount} {frm}** = `{total:,.2f} {to}`\n*(rate: 1 {frm} = {val:.4f} {to})*")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("rates")
async def rates_cmd(event):
    """Currencies list supported (USD as base). Usage: `.rates`"""
    try:
        r = await get_json("https://api.frankfurter.app/currencies")
        if not isinstance(r, dict):
            return await event.reply("Rate service unavailable.")
        text = "**💱 Supported currencies:**\n" + "\n".join(f"• `{k}` — {v}" for k, v in sorted(r.items()))
        await event.reply(text[:4000])
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("ip")
async def ip_cmd(event):
    """Owner: this host's public IP + geo. Usage: `.ip`"""
    # Ungated before: printed the server's egress IP, city and ISP into whatever
    # chat asked, which is both a leak and a mapping request to a third party.
    import config

    if event.sender_id != config.OWNER_ID:
        return await event.reply("🔒 Owner only.")
    try:
        data = await get_json("https://ipapi.co/json/")
        if not data or "ip" not in data:
            raise ValueError("no data")
        await event.reply(
            f"**🌐 Public IP: `{data.get('ip')}`**\n"
            f"City: `{data.get('city','?')}` | Region: `{data.get('region','?')}` | Country: `{data.get('country_name','?')}`\n"
            f"Org: `{data.get('org','?')}`\n"
            f"Timezone: `{data.get('timezone','?')}` | ASN: `{data.get('asn','?')}`"
        )
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("dns")
async def dns_cmd(event):
    """DNS records lookup via DoH (Google). Usage: `.dns <domain>` `.dns <domain> A`"""
    a = event.text.split(maxsplit=2)
    domain = a[1].strip() if len(a) > 1 else ""
    rtype = a[2].upper() if len(a) > 2 else "A"
    if not domain:
        return await event.reply("Give a domain. Usage: `.dns example.com A`")
    try:
        data = await get_json(
            "https://dns.google/resolve", {"name": domain, "type": rtype})
        answers = data.get("Answer", [])
        if not answers:
            return await event.reply(f"No `{rtype}` records for `{domain}`.")
        lines = [f"**🔍 DNS {rtype} records for {domain}:**", ""]
        for ans in answers:
            lines.append(f"`{ans.get('data', '?')}`" + (f" (TTL {ans.get('TTL','?')})" if "TTL" in ans else ""))
        await event.reply("\n".join(lines[:20]))
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("geo")
async def geo_cmd(event):
    """Geolocate an address / landmarks near coords. Usage: `.geo <lat> <lon>`"""
    a = event.text.split()
    if len(a) < 3:
        return await event.reply("Usage: `.geo <lat> <lon>` e.g. `.geo 28.61 77.20`")
    try:
        lat, lon = float(a[1]), float(a[2])
    except ValueError:
        return await event.reply("Coordinates must be numbers.")
    try:
        data = await get_json(
            "https://nominatim.openstreetmap.org/reverse",
            {"lat": lat, "lon": lon, "format": "jsonv2"},
            headers={"User-Agent": "xeno-userbot/1.0"})
        disp = data.get("display_name", "Unknown place")
        await event.reply(
            f"**🗺[{lat}, {lon}]**\n`{disp}`\n"
            f"Type: `{data.get('type','?')}`")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("coords")
async def coords_cmd(event):
    """Lat/long for a place. Usage: `.coords <place>`"""
    a = event.text.split(maxsplit=1)
    q = a[1].strip() if len(a) > 1 else ""
    if not q:
        return await event.reply("Give a place. Usage: `.coords <place>`")
    try:
        data = await get_json(
            "https://nominatim.openstreetmap.org/search",
            {"q": q, "format": "json", "limit": 1},
            headers={"User-Agent": "xeno-userbot/1.0"})
        if not data:
            return await event.reply(f"Place `{q}` not found.")
        d = data[0]
        await event.reply(
            f"**📍 {q}**\nLat: `{d['lat']}`\nLon: `{d['lon']}`\n"
            f"Display: `{d.get('display_name','')[:150]}`")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("station")
async def station_cmd(event):
    """ISS live position. Usage: `.station`"""
    try:
        s = await get_json("https://api.wheretheiss.at/v1/satellites/25544")
        await event.reply(
            f"**🛰 ISS**\nLat: `{s.get('latitude','?')}`\nLon: `{s.get('longitude','?')}`\n"
            f"Altitude: `{s.get('altitude','?')} km`\nVelocity: `{s.get('velocity','?')} km/h`\n"
            f"Visibility: `{s.get('visibility','?')}`")
    except Exception as e:
        await event.reply(f"Error: `{e}`")