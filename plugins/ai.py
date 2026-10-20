"""AI auto-reply plugin using Gemini or OpenAI."""
import time

import aiohttp
from telethon import events

import config
from core.auth import is_owner
from core.bot import bot
from core.command import command

# In-memory conversation history, keyed by (chat_id, user_id).
# Keying by chat alone meant that in a group, whoever typed .ai next got the
# previous person's context handed to them.
conversations = {}
MAX_HISTORY = 20


def _hist_key(event):
    return (event.chat_id, event.sender_id)

# Auto-reply spends money per message, so cap it: at most one LLM call per
# user per MIN_REPLY_GAP seconds, and stop entirely after AUTO_REPLY_BUDGET
# calls in a rolling hour. Both are per-process and reset on restart.
MIN_REPLY_GAP = 10
AUTO_REPLY_BUDGET = 30
_replied_at = {}
_call_times = []


def _budget_ok(user_id):
    """Sliding-window per-user throttle + global hourly budget."""
    now = time.time()
    last = _replied_at.get(user_id, 0)
    if now - last < MIN_REPLY_GAP:
        return False
    cutoff = now - 3600
    _call_times[:] = [t for t in _call_times if t > cutoff]
    if len(_call_times) >= AUTO_REPLY_BUDGET:
        return False
    _call_times.append(now)
    _replied_at[user_id] = now
    return True


async def ask_ai(prompt, chat_history=None):
    """Send prompt to available AI provider."""
    messages = []
    if chat_history:
        messages.extend(chat_history[-MAX_HISTORY:])
    messages.append({"role": "user", "content": prompt})

    # Try OpenAI-compatible API first
    if config.OPENAI_API_KEY:
        return await call_openai(messages)

    # Try Gemini
    if config.GEMINI_API_KEY:
        return await call_gemini(prompt, chat_history)

    return "No AI API key configured. Set OPENAI_API_KEY or GEMINI_API_KEY in .env"


async def call_openai(messages):
    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.AI_MODEL,
        "messages": [{"role": "system", "content": "You are a helpful assistant. Be concise."}] + messages,
        "max_tokens": 1024,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{config.OPENAI_API_BASE}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                return f"AI API error: {resp.status}"
            data = await resp.json()
            return data["choices"][0]["message"]["content"]


async def call_gemini(prompt, history=None):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={config.GEMINI_API_KEY}"

    contents = []
    if history:
        for msg in history[-MAX_HISTORY:]:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    payload = {"contents": contents}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=30) as resp:
            if resp.status != 200:
                return f"Gemini API error: {resp.status}"
            data = await resp.json()
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError):
                return "Failed to parse Gemini response."


@command("ai")
async def ai_cmd(event):
    """Ask the AI assistant anything. Usage: `.ai <question>`."""
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        return await event.eor(f"Usage: `{config.PREFIXES[0]}ai <your message>`")

    prompt = args[1]
    status = await event.eor("Thinking...")

    key = _hist_key(event)
    history = conversations.get(key, [])

    response = await ask_ai(prompt, history)

    # Update history
    history.append({"role": "user", "content": prompt})
    history.append({"role": "assistant", "content": response})
    conversations[key] = history[-MAX_HISTORY:]

    await status.edit(f"**AI:**\n{response}")


@command("auto")
async def auto_cmd(event):
    """Toggle AI auto-reply in DMs (`auto on`/`auto off`)."""
    if not await is_owner(event):
        return await event.eor("🔒 Owner only.")
    args = event.text.split()
    if len(args) < 2:
        current = "ON" if config.AI_AUTO_REPLY else "OFF"
        allow = config.get("AI_ALLOWED_IDS", "") or "anyone"
        await event.eor(
            f"Auto-reply: `{current}`\nAllowed IDs: `{allow}`\nUse `auto on/off`\n"
            f"Throttle: 1 reply per {MIN_REPLY_GAP}s, {AUTO_REPLY_BUDGET}/hour."
        )
        return

    state = args[1].lower()
    if state == "on":
        config.AI_AUTO_REPLY = True
        await event.eor("**Auto-reply enabled.**")
    elif state == "off":
        config.AI_AUTO_REPLY = False
        await event.eor("**Auto-reply disabled.**")


@command("clearhistory")
async def clearhistory_cmd(event):
    """Clear YOUR AI conversation history in this chat. Usage: `.clearhistory`"""
    conversations.pop(_hist_key(event), None)
    await event.eor("**Conversation history cleared.**")


# Auto-reply listener
@bot.on(events.NewMessage(func=lambda e: e.is_private and not e.out))
async def auto_reply_handler(event):
    if not config.AI_AUTO_REPLY:
        return
    if not config.OPENAI_API_KEY and not config.GEMINI_API_KEY:
        return
    # Optionally restrict to a known set of people.
    allow = config.get("AI_ALLOWED_IDS", "")
    if allow:
        allowed = {int(x) for x in allow.replace(",", " ").split() if x.strip().lstrip("-").isdigit()}
        if event.sender_id not in allowed:
            return
    if not _budget_ok(event.sender_id):
        return

    # Don't reply to commands or forwarded messages
    text = event.text or ""
    if text.startswith(tuple(config.PREFIXES)):
        return
    if not text.strip():
        return

    key = _hist_key(event)
    history = conversations.get(key, [])

    response = await ask_ai(text, history)

    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": response})
    conversations[key] = history[-MAX_HISTORY:]

    await event.eor(response)
