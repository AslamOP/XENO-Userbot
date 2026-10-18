"""XENO datetime module — dates, times, calendars, countdowns."""
import asyncio
import datetime as dt
import time

from core.command import command


@command("datenow")
async def date_cmd(event):
    """Current date. Usage: `.date`"""
    return await event.reply(f"**📅 {dt.date.today().strftime('%A, %d %B %Y')}**")


@command("time")
async def time_cmd(event):
    """Current time (server TZ)."""
    return await event.reply(f"**🕐 {dt.datetime.now().strftime('%H:%M:%S')}**")


@command("unix")
async def unix_cmd(event):
    """Current unix timestamp. Usage: `.unix`"""
    return await event.reply(f"**Unix:** `{int(time.time())}`")


@command("unix2date")
async def unix2date_cmd(event):
    """Convert unix timestamp to readable date. Usage: `.unix2date <ts>`"""
    a = event.text.split(maxsplit=1)
    arg = a[1].strip() if len(a) > 1 else ""
    try:
        ts = int(arg)
    except ValueError:
        return await event.reply("Give a unix timestamp.")
    return await event.reply(f"**{ts}** → `{dt.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')}`")


@command("date2unix")
async def date2unix_cmd(event):
    """Convert date to unix. Usage: `.date2unix <YYYY-MM-DD>`"""
    a = event.text.split(maxsplit=1)
    arg = a[1].strip() if len(a) > 1 else ""
    try:
        d = dt.datetime.strptime(arg, "%Y-%m-%d")
    except ValueError:
        return await event.reply("Give date as YYYY-MM-DD.")
    return await event.reply(f"**{arg}** → `{int(d.timestamp())}`")


@command("age")
async def age_cmd(event):
    """Age from birthdate. Usage: `.age <YYYY-MM-DD>`"""
    a = event.text.split(maxsplit=1)
    arg = a[1].strip() if len(a) > 1 else ""
    try:
        b = dt.datetime.strptime(arg, "%Y-%m-%d").date()
    except ValueError:
        return await event.reply("Give birthdate as YYYY-MM-DD.")
    today = dt.date.today()
    years = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
    days = (today - b).days
    await event.reply(f"**🎂 Age:** `{years}` years ({days:,} days)")


@command("week")
async def week_cmd(event):
    """Week number & day progress."""
    now = dt.datetime.now()
    yday = now.timetuple().tm_yday
    return await event.reply(
        f"**🗓 Week info:**\nWeek: `{now.isocalendar().week}`\n"
        f"Day of year: `{yday}/365`\nYear progress: `{yday/365*100:.1f}%`")


@command("leap")
async def leap_cmd(event):
    """Is current year a leap year?"""
    y = dt.date.today().year
    a = event.text.split(maxsplit=1)
    if len(a) > 1:
        try:
            y = int(a[1])
        except ValueError:
            pass
    leap = (y % 4 == 0 and y % 100 != 0) or y % 400 == 0
    return await event.reply(f"**{y}** is {'a leap year ✅' if leap else 'not a leap year ❌'}")


@command("daysuntil")
async def daysuntil_cmd(event):
    """Days until a date. Usage: `.daysuntil <YYYY-MM-DD>`"""
    a = event.text.split(maxsplit=1)
    arg = a[1].strip() if len(a) > 1 else ""
    try:
        target = dt.datetime.strptime(arg, "%Y-%m-%d").date()
    except ValueError:
        return await event.reply("Give date as YYYY-MM-DD.")
    days = (target - dt.date.today()).days
    return await event.reply(f"**⏳ {days}** days {'until' if days >= 0 else 'since'} `{arg}`")


@command("calendar")
async def calendar_cmd(event):
    """Text calendar for a month. Usage: `.calendar [YYYY] [MM]` or `.calendar [MM]`"""
    a = event.text.split()
    now = dt.datetime.now()
    try:
        if len(a) >= 3:
            y, m = int(a[1]), int(a[2])
        elif len(a) >= 2 and len(a[1]) == 4:
            y, m = int(a[1]), now.month
        elif len(a) >= 2:
            y, m = now.year, int(a[1])
        else:
            y, m = now.year, now.month
        import calendar as cal
        return await event.reply(f"```{cal.month(y, m)}```")
    except Exception:
        return await event.reply("Usage: `.calendar [YYYY] [MM]`")


@command("todayx")
async def today_cmd(event):
    """Today's notable events? Just date + day."""
    today = dt.date.today()
    import random
    feelings = ["fresh", "random", "chaotic", "productive", "lucky", "mysterious"]
    return await event.reply(
        f"**Today: {today}** ({today.strftime('%A')})\n"
        f"🌡 A {random.choice(feelings)} day ahead — go make it count.")


@command("utc")
async def utc_cmd(event):
    """Current UTC time."""
    return await event.reply(f"**UTC:** `{dt.datetime.now(dt.timezone.utc).strftime('%H:%M:%S')}`")


@command("newyear")
async def newyear_cmd(event):
    """Days until next new year."""
    now = dt.datetime.now()
    nxt = dt.datetime(now.year + 1, 1, 1)
    left = nxt - now
    return await event.reply(f"**🎆 New Year in:** `{left.days}`d {left.seconds//3600}h")


@command("epoch")
async def epoch_cmd(event):
    """Epoch day/s since 1970."""
    days = (dt.datetime.utcnow() - dt.datetime(1970, 1, 1)).days
    return await event.reply(f"**🗓 Day since epoch:** `{days}`")


_TIMERS = {}


@command("timerx")
async def timer_cmd(event):
    """Set a timer; XENO pings this chat when it elapses.

    Usage: `.timerx <seconds> [note]` · `.timerx cancel`
    """
    a = event.text.split(maxsplit=1)
    arg = a[1].strip() if len(a) > 1 else ""

    if arg.lower() == "cancel":
        t = _TIMERS.pop((event.chat_id, event.sender_id), None)
        if not t:
            return await event.reply("No active timer to cancel.")
        t["task"].cancel()
        return await event.reply("🛑 Timer cancelled.")

    parts = arg.split(maxsplit=1)
    note = parts[1] if len(parts) > 1 else "Timer done!"
    try:
        sec = int(parts[0])
    except (ValueError, IndexError):
        return await event.reply("Usage: `.timerx <seconds> [note]` or `.timerx cancel`")
    if sec < 1 or sec > 86400:
        return await event.reply("Seconds 1..86400.")

    key = (event.chat_id, event.sender_id)
    old = _TIMERS.pop(key, None)
    if old:
        old["task"].cancel()

    await event.reply(f"⏳ Timer set for `{sec}s`. I'll ping you here.")

    async def _fire():
        try:
            await asyncio.sleep(sec)
            await event.respond(f"⏰ **{note}** ({sec}s elapsed)")
        except asyncio.CancelledError:
            pass
        finally:
            if _TIMERS.get(key, {}).get("task") is asyncio.current_task():
                _TIMERS.pop(key, None)

    task = asyncio.ensure_future(_fire())
    _TIMERS[key] = {"task": task, "seconds": sec, "note": note}


@command("badge")
async def badge_cmd(event):
    """Time-based badge for XENO. Usage: `.badge`"""
    import random
    h = dt.datetime.now().hour
    if h < 6:
        g = "🌙 Night Owl"
    elif h < 12:
        g = "🌅 Early Riser"
    elif h < 17:
        g = "☀️ Day Grinder"
    elif h < 22:
        g = "🌆 Evening Stroller"
    else:
        g = "🌃 Late Groover"
    return await event.reply(f"🏅 Time badge: **{g}**")