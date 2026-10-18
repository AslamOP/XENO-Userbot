"""XENO language module — translation & language tools."""
from core.command import command
from core.http import get_json


@command("tl")
async def tl_cmd(event):
    """Translate a phrase to English (Google's free endpoint). Usage: `.tl <text>`"""
    a = event.text.split(maxsplit=1)
    q = a[1].strip() if len(a) > 1 else ""
    if not q:
        return await event.reply("Give text: `.tl <text>`")
    import urllib.parse
    url = (f"https://translate.googleapis.com/translate_a/single?client=gtx"
           f"&sl=auto&tl=en&dt=t&q={urllib.parse.quote(q)}")
    try:
        txt = await (_text_of(url))
        return await event.reply(f"**EN:** {txt}")
    except Exception as e:
        return await event.reply(f"Error: `{e}`")


async def _text_of(url):
    h = await get_json(url)
    if isinstance(h, list) and h and h[0]:
        return "".join(seg[0] for seg in h[0] if seg and seg[0])
    return "(phrase)."


@command("trl")
async def trl_cmd(event):
    """Translate a phrase to a specified lang. Usage: `.trl <lang> <text>`"""
    a = event.text.split(maxsplit=1)
    arg = a[1].strip() if len(a) > 1 else ""
    parts = arg.split(maxsplit=1)
    if len(parts) < 2:
        return await event.reply("Usage: `.trl <lang> <text>` e.g. `.trl fr hello`")
    lang, q = parts[0], parts[1]
    import urllib.parse
    url = (f"https://translate.googleapis.com/translate_a/single?client=gtx"
           f"&sl=auto&tl={urllib.parse.quote(lang)}&dt=t&q={urllib.parse.quote(q)}")
    try:
        h = await get_json(url)
        out = "".join(seg[0] for seg in h[0] if seg and seg[0]) if h and h[0] else "(?)"
        return await event.reply(f"**{lang}:** {out}")
    except Exception as e:
        return await event.reply(f"Error: `{e}`")


@command("spellcheck")
async def spell_cmd(event):
    """Check a word spelling via Wiktionary-ish dictionary."""
    a = event.text.split(maxsplit=1)
    w = a[1].strip().lower() if len(a) > 1 else ""
    if not w:
        return await event.reply("Give a word: `.spell <word>`")
    import urllib.parse
    try:
        d = await get_json(f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(w)}")
        if not d:
            return await event.reply(f"`{w}` not found in dictionary.")
        meanings = d[0].get("meanings", [])
        lines = [f"**{d[0]['word']}**"]
        for m in meanings[:2]:
            defs = m.get("definitions", [])
            if defs:
                lines.append(f"_({m['partOfSpeech']})_ {defs[0].get('definition', '—')}")
        phon = d[0].get("phonetic")
        if phon:
            lines.insert(1, f"*Pronunciation:* `{phon}`")
        await event.reply("\n".join(lines))
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("synx")
async def synonym_cmd(event):
    """Synonyms. Usage: `.synonym <word>`"""
    a = event.text.split(maxsplit=1)
    w = a[1].strip() if len(a) > 1 else ""
    if not w:
        return await event.reply("Give a word.")
    import urllib.parse
    try:
        d = await get_json("https://api.datamuse.com/words", {"rel_syn": w, "max": 12})
        if not d:
            return await event.reply(f"No synonyms for `{w}`.")
        await event.reply(f"**🔁 Synonyms of {w}:** " + ", ".join(x["word"] for x in d))
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("antx")
async def antonym_cmd(event):
    """Antonyms. Usage: `.antonym <word>`"""
    a = event.text.split(maxsplit=1)
    w = a[1].strip() if len(a) > 1 else ""
    if not w:
        return await event.reply("Give a word.")
    import urllib.parse
    try:
        d = await get_json("https://api.datamuse.com/words", {"rel_ant": w, "max": 12})
        if not d:
            return await event.reply(f"No antonyms for `{w}`.")
        await event.reply(f"**↔ Antonyms of {w}:** " + ", ".join(x["word"] for x in d))
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("rhymex")
async def rhyme_cmd(event):
    """Rhyming words. Usage: `.rhyme <word>`"""
    a = event.text.split(maxsplit=1)
    w = a[1].strip() if len(a) > 1 else ""
    if not w:
        return await event.reply("Give a word.")
    import urllib.parse
    try:
        d = await get_json("https://api.datamuse.com/words", {"rel_rhy": w, "max": 12})
        if not d:
            return await event.reply(f"No rhymes for `{w}`.")
        await event.reply(f"**🎵 Rhymes with {w}:** " + ", ".join(x["word"] for x in d))
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("define")
async def define_cmd(event):
    """Dictionary (first definition). Usage: `.define <word>`"""
    a = event.text.split(maxsplit=1)
    w = a[1].strip() if len(a) > 1 else ""
    if not w:
        return await event.reply("Give a word.")
    import urllib.parse
    try:
        d = await get_json(f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(w)}")
        if not d:
            return await event.reply(f"`{w}` not found.")
        m = d[0]["meanings"][0]
        defn = m["definitions"][0]
        await event.reply(f"**{d[0]['word']}** _(\\{m['partOfSpeech']})_\n{defn.get('definition')}\n"
                          f"_`{defn.get('example', '')}`_")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("langcodes")
async def langs_cmd(event):
    """Common translate language codes."""
    return await event.reply(
        "**🌐 Language codes:** `en fr de es it pt ru ja ko zh hi ar tr nl pl sv`\n"
        "Use: `.trl <code> <text>`")