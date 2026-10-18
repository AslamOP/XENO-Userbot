"""XENO media-news module — headlines, Reddit pivots, trending tags."""
from core.command import command
from core.http import get_json, get_text

import re as _re


@command("headline")
async def headline_cmd(event):
    """Top world news headlines (free feed). Usage: `.headline`"""
    try:
        txt = await get_text("https://feeds.bbci.co.uk/news/rss.xml")
        titles = _re.findall(r"<title>(.*?)</title>", txt)[1:8]
        if not titles:
            return await event.reply("News feed empty.")
        lines = ["**📰 Top headlines:**"]
        for i, t in enumerate(titles, 1):
            lines.append(f"{i}. {t}")
        await event.reply("\n".join(lines), link_preview=False)
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("technews")
async def technews_cmd(event):
    """Latest tech news via Hacker News."""
    try:
        ids = await get_json("https://hacker-news.firebaseio.com/v0/topstories.json")
        lines = ["**💻 Tech / HN top:**"]
        for i in ids[:6]:
            item = await get_json(f"https://hacker-news.firebaseio.com/v0/item/{i}.json")
            title = (item or {}).get("title", "?")
            score = (item or {}).get("score", 0)
            lines.append(f"• {title}  _(+{score})_")
        await event.reply("\n".join(lines), link_preview=False)
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("reddit")
async def reddit_cmd(event):
    """Top posts in a subreddit (SFW). Usage: `.reddit <sub>`"""
    a = event.text.split(maxsplit=1)
    sub = a[1].strip() if len(a) > 1 else "programming"
    try:
        d = await get_json(f"https://www.reddit.com/r/{sub}/hot.json",
                           headers={"User-Agent": "xeno-userbot/1.0"})
        posts = d["data"]["children"]
        lines = [f"**🔴 r/{sub}**"]
        n = 0
        for p in posts:
            data = p["data"]
            if data.get("over_18"):
                continue
            title = data["title"][:80]
            score = data.get("score", 0)
            lines.append(f"• {title}  _(+{score})_")
            n += 1
            if n >= 7:
                break
        await event.reply("\n".join(lines), link_preview=False)
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("subinfo")
async def subinfo_cmd(event):
    """Info about a subreddit. Usage: `.subinfo <sub>`"""
    a = event.text.split(maxsplit=1)
    sub = a[1].strip() if len(a) > 1 else "programming"
    try:
        d = await get_json(f"https://www.reddit.com/r/{sub}/about.json",
                           headers={"User-Agent": "xeno-userbot/1.0"})
        data = d["data"]
        await event.reply(
            f"**r/{data['display_name']}**\n"
            f"👥 Subscribers: `{data.get('subscribers', 0):,}`\n"
            f"🟢 Active: `{data.get('active_user_count', 0):,}`\n"
            f"📝 Description: `{(data.get('public_description') or '—')[:160]}`")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("udef")
async def udef_cmd(event):
    """Urban Dictionary. Usage: `.udef <word>`"""
    a = event.text.split(maxsplit=1)
    w = a[1].strip() if len(a) > 1 else ""
    if not w:
        return await event.reply("Give a word: `.udef <word>`")
    import urllib.parse
    try:
        d = await get_json("https://api.urbandictionary.com/v0/define",
                           {"term": w})
        if not d.get("list"):
            return await event.reply(f"No Urban Dictionary entry for `{w}`.")
        e = d["list"][0]
        await event.reply(
            f"**{e['word']}**\n{e['definition'][:400]}\n\n"
            f"_Example: {e.get('example', '—')[:200]}_\n👍 {e['thumbs_up']} 👎 {e['thumbs_down']}")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("wikishort")
async def wikishort_cmd(event):
    """Short Wikipedia summary. Usage: `.wikishort <term>`"""
    a = event.text.split(maxsplit=1)
    q = a[1].strip() if len(a) > 1 else ""
    if not q:
        return await event.reply("Give a term: `.wikishort <term>`")
    import urllib.parse
    try:
        d = await get_json("https://en.wikipedia.org/api/rest_v1/page/summary/"
                           + urllib.parse.quote(q))
        await event.reply(
            f"**{d.get('title', q)}**\n{d.get('extract', 'No extract.')[:800]}\n\n"
            f"[Open]({d.get('content_urls', {}).get('desktop', {}).get('page', '#')})",
            link_preview=True)
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("iss")
async def iss_cmd(event):
    """Track the ISS live position."""
    try:
        d = await get_json("https://api.wheretheiss.at/v1/satellites/25544")
        await event.reply(
            "**🛰 ISS live:**\n"
            f"Lat: `{d['latitude']:.3f}`\nLon: `{d['longitude']:.3f}`\n"
            f"Alt: `{d['altitude']:.1f} km`\nVel: `{d['velocity']:.1f} km/h`")
    except Exception as e:
        await event.reply(f"Error: `{e}`")