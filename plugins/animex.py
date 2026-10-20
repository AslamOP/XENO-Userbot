"""XENO anime module — Jikan API, no key. Character & anime lookup."""
from core.command import command
from core.http import get_json

import urllib.parse


@command("anime")
async def anime_cmd(event):
    """Anime search. Usage: `.anime <name>`"""
    a = event.text.split(maxsplit=1)
    q = a[1].strip() if len(a) > 1 else ""
    if not q:
        return await event.eor("Give anime name: `.anime <name>`")
    try:
        d = await get_json(f"https://api.jikan.moe/v4/anime",
                           {"q": q, "limit": 4})
        res = d.get("data", [])
        if not res:
            return await event.eor(f"Nothing for `{q}`.")
        lines = []
        for it in res[:4]:
            lines.append(f"**{it.get('title')}** ({it.get('type')}, {it.get('episodes')} eps)\n"
                         f"⭐ {it.get('score')} — {it.get('status')}\n"
                         f"`{it.get('synopsis', '—')[:120]}...`")
        await event.eor("\n\n".join(lines))
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("manga")
async def manga_cmd(event):
    """Manga search. Usage: `.manga <name>`"""
    a = event.text.split(maxsplit=1)
    q = a[1].strip() if len(a) > 1 else ""
    if not q:
        return await event.eor("Give manga name.")
    try:
        d = await get_json("https://api.jikan.moe/v4/manga", {"q": q, "limit": 3})
        res = d.get("data", [])
        if not res:
            return await event.eor(f"Nothing for `{q}`.")
        lines = [f"**{it.get('title')}** ({it.get('chapters')} ch) ⭐{it.get('score')}\n"
                 f"`{it.get('synopsis', '—')[:120]}...`" for it in res[:3]]
        await event.eor("\n\n".join(lines))
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("charx")
async def char_cmd(event):
    """Anime character search. Usage: `.char <name>`"""
    a = event.text.split(maxsplit=1)
    q = a[1].strip() if len(a) > 1 else ""
    if not q:
        return await event.eor("Give character name.")
    try:
        d = await get_json("https://api.jikan.moe/v4/characters", {"q": q, "limit": 3})
        res = d.get("data", [])
        if not res:
            return await event.eor(f"Nothing for `{q}`.")
        lines = [f"**{it.get('name')}**\n`{(it.get('about') or '—')[:160]}...`" for it in res[:3]]
        await event.eor("\n\n".join(lines))
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("topanime")
async def topanime_cmd(event):
    """Top rated anime of all time."""
    try:
        d = await get_json("https://api.jikan.moe/v4/top/anime", {"limit": 10})
        lines = ["**🏆 Top Anime:**"]
        for i, it in enumerate(d.get("data", []), 1):
            lines.append(f"{i}. {it.get('title')} ⭐{it.get('score')}")
        await event.eor("\n".join(lines))
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("animequote")
async def animequote_cmd(event):
    """Random anime quote."""
    try:
        d = await get_json("https://api.jikan.moe/v4/random/characters")
        ch = d.get("data", {})
        await event.eor(f"**{ch.get('name')}** — {ch.get('name')}\n"
                          f"\n*Featured character of the moment.*")
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("seasonx")
async def season_cmd(event):
    """Anime currently airing this season."""
    try:
        d = await get_json("https://api.jikan.moe/v4/seasons/now", {"limit": 8})
        lines = ["**📺 Airing this season:**"]
        for it in d.get("data", [])[:8]:
            lines.append(f"• {it.get('title')} ⭐{it.get('score')}")
        await event.eor("\n".join(lines))
    except Exception as e:
        await event.eor(f"Error: `{e}`")