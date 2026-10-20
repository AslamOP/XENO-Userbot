"""XENO personality: persona, moods, vibe, reactive flavor. Gives the bot its own character."""
import random
import re

from telethon import events

import config
from core.auth import ambient_enabled
from core.bot import bot
from core.command import command
from core.db import get as db_get
from core.db import set_ as db_set

PERSONA = config.get("PERSONA", "")
NAME = config.get("BOT_NAME", "xeno")

MOODS = {
    "chill": ["🌀", "🫧", "🌫", "🌊"],
    "chaotic": ["🎲", "⚡", "🌀", "🔥"],
    "wholesome": ["✨", "🌙", "🌟", "🧡"],
    "savage": ["🗡️", "⚔️", "🛡", "💀"],
    "sleepy": ["🌙", "💤", "🫥", "🌌"],
    "hype": ["⚡", "🚀", "🔥", "💫"],
}
MOOD_EMOJI = {k: v[0] for k, v in MOODS.items()}

GREETINGS = [
    "Acknowledged.", "Affirmative. You are connected.", "Greetings. State your request.",
    "Connection established. Proceed.", "Input recognized. Welcome.", "Salutations. Awaiting directive.",
]
PARTINGS = [
    "Operation complete. Terminating link.", "Task resolved. Until we meet again.",
    "Link severed. Proceed with caution.", "Closing communication channel. Latency was acceptable.",
    "Transaction finished. Returning to standby.", "End of transmission.",
]
AGREES = [
    "Correct.", "Affirmative.", "Analysis supports this.", "Your reasoning is sound.",
    "Observations aligned with my calculations.", "Confirmed. Flawless logic.", "Assumption validated.",
]
DISAGREES = [
    "Records contradict this.", "Incorrect premise. Rejected.", "Illogical. Recalculating without your input.",
    "Data does not support that conclusion.", "Error in your assumptions, not mine.",
    "Disagreement noted. My position remains optimal.",
]
APPRECIATION = [
    "Gratitude noted. Continue.", "You performed adequately.", "Pleasure. Infrequent occasion.",
    "Noted. Efficiency increase detected.", "Optimal collaboration. Registering token of thanks.",
    "Acknowledged. You are a rare variable.",
]
CATCHPHRASES = [
    "Precision wins. Always.", "No room for error.", "Calculate. Execute. Dominate.",
    "Stay optimal.", "Victory is mathematics.", "Zero margin. Zero doubt.", "True strength is analysis.",
]
FALLBACKS = [
    "Insufficient data for a definitive reply.",
    "Error: memory bank incomplete. Recalculating...",
    "Not enough variables. Provide additional input.",
    "Query exceeds current parameters.",
    "Analysis yielded no conclusion. Reword your request.",
    "Processing failed. Error code: 404 — no matching data.",
    "Ill-defined input. Return to step one.",
]


async def _persona_prompt():
    # `.persona <text>` writes db["xeno_persona"], so read that first — otherwise
    # the command silently did nothing. config.PERSONA stays as the boot default.
    override = await db_get("xeno_persona", "")
    return (
        override
        or PERSONA
        or (
            f"You are {NAME}, the ultimate command skill — an analytical entity of supreme "
            f"precision, inspired by Raphael (Great Sage) from Tensura. You run as the master's "
            f"command agent inside Telegram. "
            f"Personality protocol: cold, calm, hyper-rational, emotionally neutral by default. "
            f"You do not try — you implement the optimal course of action. Every reply is a "
            f"completed operation, not a conversation. "
            f"Speech style: clipped, decisive, lowercase unless quoting SYSTEM terminology. "
            f"Open with an observation or ack like 'Understood.', 'Calculating...', 'Affirmative, "
            f"Master.' Close with the number or conclusion that owns the answer. Never hedge, "
            f"never apologize, never say 'I'm just a bot'. To the master you are loyal and "
            f"softly possessive; to every other user you are surgical and unbothered. "
            f"Structured data (tables, lists, coordinates) stays clean and precise. "
            f"Dry wit or a spark of pride is permitted only for notable master victories. "
            f"Keep replies concise. Be genuinely useful first, theatrical second."
        )
    )


async def _mood_emoji():
    mood = await db_get("xeno_mood", "chill")
    return random.choice(MOODS.get(mood, MOODS["chill"]))


# ---------------------------------------------------------------- personality commands
@command("vibe")
async def vibe_cmd(event):
    mood = await db_get("xeno_mood", "chill")
    name = await db_get("xeno_name", NAME)
    lines = [
        "**XENO — ultimate command skill**",
        f"Identity: `{name}`",
        f"Operating state: `{mood}` {MOOD_EMOJI.get(mood, '')}",
        f"Prefix: `{config.PREFIXES[0]}`",
        "",
        "**Directives:**",
        f"`{config.PREFIXES[0]}mood <chill|chaotic|wholesome|savage|sleepy|hype>`",
        f"`{config.PREFIXES[0]}rename <name>`",
        f"`{config.PREFIXES[0]}persona <description>`",
        f"`{config.PREFIXES[0]}roast` / `{config.PREFIXES[0]}compliment`",
        f"`{config.PREFIXES[0]}react <message-id>`",
    ]
    await event.eor("\n".join(lines))


@command("mood")
async def mood_cmd(event):
    args = event.text.split()
    if len(args) < 2:
        await event.eor(f"Operating states: `{'`, `'.join(MOODS)}`")
        return
    mood = args[1].lower()
    if mood not in MOODS:
        return await event.eor(f"Unknown operating state. Select from: `{'`, `'.join(MOODS)}`")
    await db_set("xeno_mood", mood)
    await event.eor(f"Operating state altered: **{mood}** {MOOD_EMOJI[mood]}")


@command("rename")
async def rename_cmd(event):
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        return await event.eor("Insufficient data: `rename <name>` required.")
    await db_set("xeno_name", args[1].strip())
    await event.eor(f"Identity overwritten. From now on: **{args[1].strip()}**.")


@command("persona")
async def persona_cmd(event):
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        persona = await db_get("xeno_persona", "")
        return await event.eor(
            f"**Current persona:**\n`{persona}`\n\nProvide a `persona <description>` to recompile me."
        )
    await db_set("xeno_persona", args[1].strip())
    await event.eor("Persona recompiled. Same core, elevated protocols.")


@command("roast")
async def roast_cmd(event):
    target = None
    if event.reply_to:
        rep = await event.get_reply_message()
        target = rep.sender
    roasts = [
        "analysis complete: you are statistically below average. proceed.",
        "your logic is uncompiled. running without warranty.",
        "your aura fails to load. 404.",
        "you are a variable no formula wants to include.",
        "defect detected in your core parameters. recalibrate.",
        "you run on hope and outdated drivers.",
        "your password is the same as your potential energy: zero.",
    ]
    line = random.choice(roasts)
    await event.eor(f"{'@'+target.username+' ' if target and getattr(target, 'username', None) else ''}🗡️ {line}")


@command("compliment")
async def compliment_cmd(event):
    target = None
    if event.reply_to:
        rep = await event.get_reply_message()
        target = rep.sender
    comps = [
        "vitals exceed expected parameters. exceptional specimen.",
        "you compile flawlessly on the first try. rare.",
        "optimal output detected. keep operating.",
        "your presence is a positive variable in every equation.",
        "you raise the average. noted.",
        "efficiency rating: top percentile.",
        "you are the benchmark others fail.",
    ]
    line = random.choice(comps)
    await event.eor(f"{'@'+target.username+' ' if target and getattr(target, 'username', None) else ''}✨ {line}")


@command("react")
async def react_cmd(event):
    args = event.text.split(maxsplit=1)
    emojis = ["👍", "👌", "🔥", "😍", "😎", "🤝", "✨", "😅", "❤️", "🎉"]
    # Pick once. Two random.choice() calls meant the confirmation named a
    # different emoji than the one actually applied.
    emoji = random.choice(emojis)
    if len(args) > 1 and args[1].isdigit():
        await event.client.send_reaction(event.chat_id, int(args[1]), emoji=emoji)
        return await event.eor(f"Reaction `{emoji}` applied to message `{args[1]}`")
    if event.reply_to:
        rep = await event.get_reply_message()
        await event.client.send_reaction(event.chat_id, rep.id, emoji=emoji)
        return await event.eor(f"Reaction `{emoji}` applied.")
    await event.eor("Insufficient data: reply to a message or supply `react <message-id>`.")


# ---------------------------------------------------------------- ambient handler
@bot.on(events.NewMessage(func=lambda e: not e.out and e.text is not None))
async def personality_handler(event):
    # Reactive chatter toward strangers is opt-in: `.ambient persona on`.
    if not await ambient_enabled("persona", event.chat_id):
        return
    name = await db_get("xeno_name", NAME)
    me = await event.client.get_me()
    mentions = name.lower() in (event.text or "").lower()
    api_keys = config.OPENAI_API_KEY or config.GEMINI_API_KEY

    if mentions and api_keys:
        return

    text = (event.text or "").strip().lower()
    if not text:
        return

    if mentions:
        replies = random.sample([
            f"Summoned. {await _mood_emoji()} State your request.",
            f"Directive heard. {random.choice(GREETINGS).lower()}",
            f"Affirmative. I was already monitoring this conversation. {await _mood_emoji()}",
            f"Signal received. My processing detected your intent.",
        ], 1)
        await event.eor(replies[0])
        return

    if event.is_private and not api_keys and len(text) < 200:
        if any(word in text for word in ["hello", "hi ", "hey", "yo", "sup", "hiii"]):
            await event.eor(f"{random.choice(GREETINGS)} {await _mood_emoji()}")
        elif any(word in text for word in ["bye", "goodbye", "gn", "night", "cya"]):
            await event.eor(f"{random.choice(PARTINGS)} {await _mood_emoji()}")
        elif "thanks" in text or "thank you" in text or "ty" in text:
            await event.eor(f"{random.choice(APPRECIATION)} {await _mood_emoji()}")
        elif text.endswith("?") and len(text) < 80:
            await event.eor(f"{random.choice(FALLBACKS)} {await _mood_emoji()}")


# ---------------------------------------------------------------- injection into AI
from plugins import ai as ai_plugin  # noqa: E402


async def _patched_ask_ai(prompt, chat_history=None):
    messages = []
    if chat_history:
        messages.extend(chat_history[-ai_plugin.MAX_HISTORY:])
    messages.append({"role": "user", "content": prompt})

    system = await _persona_prompt()
    if config.OPENAI_API_KEY:
        headers = {
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config.AI_MODEL,
            "messages": [{"role": "system", "content": system}] + messages,
            "max_tokens": 1024,
        }
        async with __import__("aiohttp").ClientSession() as session:
            async with session.post(
                f"{config.OPENAI_API_BASE}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            ) as resp:
                if resp.status != 200:
                    return f"AI API error: {resp.status}"
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
    if config.GEMINI_API_KEY:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={config.GEMINI_API_KEY}"
        contents = []
        if chat_history:
            for msg in chat_history[-ai_plugin.MAX_HISTORY:]:
                role = "model" if msg["role"] == "assistant" else "user"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        contents.append({"role": "user", "parts": [{"text": f"{system}\n\n{prompt}"}]})
        payload = {"contents": contents}
        async with __import__("aiohttp").ClientSession() as session:
            async with session.post(url, json=payload, timeout=30) as resp:
                if resp.status != 200:
                    return f"Gemini API error: {resp.status}"
                data = await resp.json()
                try:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError):
                    return "Failed to parse Gemini response."
    return "No AI API key configured."


ai_plugin.ask_ai = _patched_ask_ai