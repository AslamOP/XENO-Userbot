"""Wordsmith (Xeno): meaning, synonym, antonym, rhymes, ud (Urban Dictionary), wordapi.
Pure original code. No API keys — uses free public dictionaries (DictionaryAPI.dev, Datamuse, Urban Dictionary)."""
import urllib.parse

from core.command import command
from core.http import get_json


def _join(items, fallback=""):
    return ", ".join(f"`{x}`" for x in items[:15]) if items else fallback


@command("meaning")
async def meaning_cmd(event):
    """Get the definition(s) of a word. Usage: `.meaning <word>`"""
    args = event.text.split(maxsplit=1)
    word = args[1].strip() if len(args) > 1 else ""
    if not word:
        return await event.reply("Give a word. Usage: `.meaning <word>`")
    try:
        data = await get_json(f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(word)}")
    except Exception as e:
        return await event.reply(f"Error: `{e}`")
    if isinstance(data, dict) and data.get("title"):
        return await event.reply(f"❌ No definition found for `{word}`.\n`{data.get('message','')}`")
    if not isinstance(data, list) or not data:
        return await event.reply("No result.")
    entry = data[0]
    lines = [f"**📖 {entry.get('word','').title()}**"]
    phone = entry.get("phonetic")
    if phone:
        lines.append(f"🗣 `{phone}`")
    for n, meaning in enumerate(entry.get("meanings", [])[:5], 1):
        pos = meaning.get("partOfSpeech", "")
        for d in meaning.get("definitions", [])[:15]:
            lines.append(f"\n**{pos}** — {d.get('definition','')}")
            if d.get("example"):
                lines.append(f"   _e.g. {d.get('example')}_")
    syn = _join(entry.get("meanings", [{}])[0].get("synonyms", [])) if entry.get("meanings") else ""
    if syn:
        lines.append(f"\n**Synonyms:** {syn}")
    await event.reply("\n".join(lines)[:4000])


@command("synonym")
async def synonym_cmd(event):
    """Get synonyms of a word via Datamuse. Usage: `.synonym <word>`"""
    args = event.text.split(maxsplit=1)
    word = args[1].strip() if len(args) > 1 else ""
    if not word:
        return await event.reply("Give a word. Usage: `.synonym <word>`")
    try:
        data = await get_json("https://api.datamuse.com/words", {"rel_syn": word, "max": 20})
    except Exception as e:
        return await event.reply(f"Error: `{e}`")
    if not data:
        return await event.reply(f"No synonyms for `{word}`.")
    res = [f"**🔁 Synonyms of `{word}`:**", ""]
    res.append("\n".join(f"• `{x['word']}`" for x in data))
    await event.reply("\n".join(res))


@command("antonym")
async def antonym_cmd(event):
    """Get antonyms of a word via Datamuse. Usage: `.antonym <word>`"""
    args = event.text.split(maxsplit=1)
    word = args[1].strip() if len(args) > 1 else ""
    if not word:
        return await event.reply("Give a word. Usage: `.antonym <word>`")
    try:
        data = await get_json("https://api.datamuse.com/words", {"rel_ant": word, "max": 20})
    except Exception as e:
        return await event.reply(f"Error: `{e}`")
    if not data:
        return await event.reply(f"No antonyms for `{word}`.")
    res = [f"**⚖️ Antonyms of `{word}`:**", ""]
    res.append("\n".join(f"• `{x['word']}`" for x in data))
    await event.reply("\n".join(res))


@command("rhyme")
async def rhyme_cmd(event):
    """Find words that rhyme with the given word (Datamuse)."""
    args = event.text.split(maxsplit=1)
    word = args[1].strip() if len(args) > 1 else ""
    if not word:
        return await event.reply("Give a word. Usage: `.rhyme <word>`")
    try:
        data = await get_json("https://api.datamuse.com/words", {"rel_rhy": word, "max": 25})
    except Exception as e:
        return await event.reply(f"Error: `{e}`")
    if not data:
        return await event.reply(f"No rhymes for `{word}`.")
    res = [f"**🎶 Rhymes with `{word}`:**", ""]
    res.append("\n".join(f"• `{x['word']}`" for x in data))
    await event.reply("\n".join(res))


@command("ud")
async def ud_cmd(event):
    """Get an Urban Dictionary definition. Usage: `.ud <term>`"""
    args = event.text.split(maxsplit=1)
    term = args[1].strip() if len(args) > 1 else ""
    if not term:
        return await event.reply("Give a term. Usage: `.ud <term>`")
    try:
        data = await get_json(
            "https://api.urbandictionary.com/v0/define",
            {"term": term},
        )
    except Exception as e:
        return await event.reply(f"Error: `{e}`")
    lst = data.get("list", [])
    if not lst:
        return await event.reply(f"No definition for `{term}` on Urban Dictionary.")
    d = lst[0]
    defn = d.get("definition", "").replace("[", "**").replace("]", "**")
    ex = d.get("example", "").replace("[", "**").replace("]", "**")
    await event.reply(
        f"**📚 {d.get('word','').upper()}**\n"
        f"\n{defn[:1800]}\n"
        f"\n**Example:**\n{ex[:800]}\n"
        f"\n👍 {d.get('thumbs_up',0)} · 👎 {d.get('thumbs_down',0)}"
    )


@command("wordapi")
async def wordapi_cmd(event):
    """Pit a word: get random word + its definition + sample (Datamuse + free dict)."""
    try:
        words = await get_json("https://api.datamuse.com/words", {"sp": "?????", "max": 1})
    except Exception as e:
        return await event.reply(f"Error: `{e}`")
    if not words:
        return await event.reply("Could not pick a random word.")
    word = words[0]["word"]
    try:
        data = await get_json(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}")
    except Exception as e:
        # Was unguarded: the exception escaped the handler and the user got
        # no reply at all.
        return await event.reply(f"**🎲 Random word: `{word}`**\n*(No dictionary entry: `{e}`.)*")
    lines = [f"**🎲 Random word: `{word}`**"]
    if isinstance(data, list) and data:
        for m in data[0].get("meanings", [])[:2]:
            for d in m.get("definitions", [])[:3]:
                lines.append(f"*{m.get('partOfSpeech','')}*: {d.get('definition','')}")
                if d.get("example"):
                    lines.append(f"   _e.g. {d.get('example')}_")
    await event.reply("\n".join(lines)[:3000])
