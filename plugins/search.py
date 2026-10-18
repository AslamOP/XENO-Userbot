"""Search (Xeno): github, websearch, wikip, books, hackernews, randomuser.
Pure original. No API keys (GitHub search is unauthenticated, DDG lite for web, HN firebase, RandomUser free)."""
import urllib.parse

from core.command import command
from core.http import get_json, get_text


@command("github")
async def github_cmd(event):
    """Search GitHub for a repo. Usage: `.github <query>`"""
    args = event.text.split(maxsplit=1)
    q = args[1].strip() if len(args) > 1 else ""
    if not q:
        return await event.reply("Give a search query. Usage: `.github <query>`")
    try:
        data = await get_json(
            "https://api.github.com/search/repositories",
            {"q": q, "sort": "stars", "order": "desc", "per_page": 8},
            headers={"Accept": "application/vnd.github+json", "User-Agent": "xeno-userbot"},
        )
    except Exception as e:
        return await event.reply(f"Error: `{e}`")
    items = data.get("items", [])
    if not items:
        return await event.reply(f"No repos found for `{q}`.")
    lines = [f"**🐙 GitHub: `{q}`**", ""]
    for r in items:
        lines.append(
            f"**[{r['full_name']}]({r['html_url']})** ⭐{r.get('stargazers_count', 0)}\n"
            f"`{(r.get('description') or '')[:90]}`"
        )
    await event.reply("\n".join(lines))


@command("search")
async def search_cmd(event):
    """Search the web (DDG lite) — no key needed. Usage: `.search <query>`"""
    args = event.text.split(maxsplit=1)
    q = args[1].strip() if len(args) > 1 else ""
    if not q:
        return await event.reply("Give a query. Usage: `.search <query>`")
    url = "https://lite.duckduckgo.com/lite/"
    try:
        html = await get_text(url, params={"q": q})
    except Exception as e:
        return await event.reply(f"Error: `{e}`")
    # lift results from the classic lite HTML: <a rel="nofollow" href="...">title</a> + snippet rows
    import re as _re
    links = _re.findall(r'<a rel="nofollow" href="([^"]+)"[^>]*>(.*?)</a>', html)[:8]
    lines = [f"**🔎 Web: `{q}`**", ""]
    seen = set()
    for href, title in links:
        text = _re.sub(r"<[^>]+>", "", title)
        text = text.replace("&amp;", "&").replace("&#x27;", "'")[:70]
        if href.startswith(("http", "//")) and text and href not in seen:
            seen.add(href)
            if href.startswith("//"):
                href = "https:" + href
            lines.append(f"**[{text}]({href})**")
    if len(lines) == 2:
        return await event.reply(f"No results for `{q}`.")
    await event.reply("\n".join(lines))


@command("wikip")
async def wikip_cmd(event):
    """Get a Wikipedia summary. Usage: `.wikip <article title>`"""
    args = event.text.split(maxsplit=1)
    topic = args[1].strip() if len(args) > 1 else ""
    if not topic:
        return await event.reply("Give an article title. Usage: `.wikip <title>`")
    try:
        data = await get_json(
            "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(topic),
        )
    except Exception as e:
        return await event.reply(f"Error: `{e}`")
    if data.get("type") == "disambiguation":
        return await event.reply(f"`{topic}` is ambiguous — be more specific.")
    title = data.get("title", topic)
    extract = data.get("extract", "")
    url = data.get("content_urls", {}).get("desktop", {}).get("page", "#")
    thumb = data.get("thumbnail", {}).get("source")
    lines = [f"**📚 {title}**", "", extract[:1600]]
    if url and url != "#":
        lines.append(f"\n[Wikipedia]({url})")
    if thumb:
        try:
            await event.reply("\n".join(lines), file=thumb)
        except Exception:
            await event.reply("\n".join(lines))
    else:
        await event.reply("\n".join(lines))


@command("books")
async def books_cmd(event):
    """Search Google Books. Usage: `.books <query>`"""
    args = event.text.split(maxsplit=1)
    q = args[1].strip() if len(args) > 1 else ""
    if not q:
        return await event.reply("Give a book query. Usage: `.books <query>`")
    try:
        data = await get_json(
            "https://www.googleapis.com/books/v1/volumes",
            {"q": q, "maxResults": 5},
        )
    except Exception as e:
        return await event.reply(f"Error: `{e}`")
    items = data.get("items", [])
    if not items:
        return await event.reply("No books found.")
    lines = [f"**📔 Google Books: `{q}`**", ""]
    for it in items:
        vi = it.get("volumeInfo", {})
        title = vi.get("title", "?")
        authors = ", ".join(vi.get("authors", []) or ["?"])
        link = it.get("selfLink", "")
        lines.append(f"**{title}** — by {authors}")
    await event.reply("\n".join(lines))


@command("hn")
async def hn_cmd(event):
    """Latest top Hacker News stories (Firebase API, no key)."""
    try:
        ids = await get_json("https://hacker-news.firebaseio.com/v0/topstories.json")
    except Exception as e:
        return await event.reply(f"Error: `{e}`")
    await event.client.send_message(
        event.chat_id,
        f"**📰 Top Hacker News:**\n*(fetching…)*",
    )
    lines = []
    for i in ids[:8]:
        try:
            st = await get_json(f"https://hacker-news.firebaseio.com/v0/item/{i}.json")
            title = st.get("title", "")
            score = st.get("score", 0)
            url = st.get("url", "")
            lines.append(f"🔹 **{title}** · ⬆{score} · [link]({url})" if url else f"🔹 **{title}** · ⬆{score}")
        except Exception:
            continue
    if not lines:
        return await event.reply("No stories right now.")
    await event.client.send_message(event.chat_id, "\n".join(["**📰 Top Hacker News:**", ""] + lines))


@command("randomuser")
async def randomuser_cmd(event):
    """Fetch a random fake user profile (RandomUser API, no key)."""
    try:
        data = await get_json(
            "https://randomuser.me/api/",
            params={"nat": "us"},
        )
    except Exception as e:
        return await event.reply(f"Error: `{e}`")
    u = data["results"][0]
    name = f"{u['name']['first']} {u['name']['last']}"
    loc = f"{u['location']['city']}, {u['location']['state']}"
    await event.reply(
        f"**👤 {name}**\n"
        f"Gender: `{u['gender']}`\n"
        f"Email: `{u['email']}`\n"
        f"Location: `{loc}`\n"
        f"Username: @{u['login']['username']}\n"
        f"Age: `{u['dob']['age']}`\n"
        f"Phone: `{u['phone']}`"
    )
