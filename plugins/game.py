"""AI game player: LLM watches a game bot and plays it autonomously.

Actions the model may choose (one per turn):
  SEND <text>      - send a text command to the game bot
  PRESS <row>,<col>- press an inline button on the bot's last message
  WAIT <seconds>   - do nothing for N seconds
  STOP             - detach the agent

Learning: per-bot rolling memory (action -> outcome snippet) persisted to
games_memory.json and injected into every decision prompt.
"""
import asyncio
import json
import os
import re
import time

import aiohttp
from telethon import events

import config
from core.bot import bot
from core.command import command

GAME_MODEL = config.get("GAME_MODEL") or "google/gemini-2.5-flash-lite"
MEMORY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "games_memory.json"
)
MIN_ACTION_GAP = 2.5
MAX_ACTIONS = 500
MAX_MEMORY = 20
LLM_TIMEOUT = 15
MAX_TIPS = 20            # stored per session (was unbounded)
MAX_TIPS_IN_PROMPT = 3
# The agent issues one LLM call per game-bot message, and game bots post fast.
# Cap the whole process so a busy chat can't burn the key unattended.
LLM_CALLS_PER_HOUR = 120
_llm_calls = []


def _llm_budget_ok():
    now = time.time()
    _llm_calls[:] = [t for t in _llm_calls if t > now - 3600]
    if len(_llm_calls) >= LLM_CALLS_PER_HOUR:
        return False
    _llm_calls.append(now)
    return True

# chat_id -> {"actions": int, "last_action": str, "busy": bool,
#             "last_msg_id": int, "goal": str, "fails": int}
sessions = {}

# chat_id -> strategy knowledge injected into every decision prompt.
BOT_KNOWLEDGE = {
    # 🏙 Idle City: Farming Competition 17-20.09 — priority is carrots.
    1219677707: (
        "Idle City knowledge:\n"
        "- A Farming Competition (carrot contest) is active: collect as many "
        "Carrot '🥕' as possible; your contest total grows with every carrot "
        "harvested, and ranking prizes go to the top 10.\n"
        "- To farm: send 'Farm 🚜' to open the farm menu, and pick the Carrot "
        "'🥕' option to grow/process them.\n"
        "- Whenever you see 'Don't forget to harvest Carrot!' or a farmers-"
        "finished message, harvest the ready carrots immediately.\n"
        "- Diamonds '(💎' and other buildings still exist, but during the "
        "contest the carrot harvest is the priority goal."
    ),
}
_memory = {}


def _load_memory():
    global _memory
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE) as f:
                _memory = json.load(f)
        except (json.JSONDecodeError, OSError):
            _memory = {}


_memory_dirty = False


def _save_memory():
    """Blocking write; only ever called from the debounced flusher."""
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    tmp = MEMORY_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(_memory, f, indent=2)
    os.replace(tmp, MEMORY_FILE)


_load_memory()


async def _memory_flush_loop():
    global _memory_dirty
    while True:
        await asyncio.sleep(5)
        if not _memory_dirty:
            continue
        _memory_dirty = False
        try:
            await asyncio.to_thread(_save_memory)
        except OSError:
            pass


_memory_flusher = None


def _ensure_memory_flusher():
    global _memory_flusher
    if _memory_flusher is None or _memory_flusher.done():
        _memory_flusher = asyncio.ensure_future(_memory_flush_loop())


def remember(chat_id, action, outcome):
    global _memory_dirty
    key = str(chat_id)
    hist = _memory.setdefault(key, [])
    hist.append({"t": int(time.time()), "a": action, "o": outcome[:200]})
    _memory[key] = hist[-MAX_MEMORY:]
    _memory_dirty = True


SYSTEM_PROMPT = (
    "You are an autonomous agent playing a Telegram game bot. "
    "You see the bot's latest message and its buttons. Reply with EXACTLY ONE "
    "action line and nothing else — no explanations, no reasoning, no quotes:\n"
    "SEND <command>      e.g. SEND /hunt\n"
    "PRESS <row>,<col>   press a listed button\n"
    "WAIT <seconds>      nothing to do yet\n"
    "STOP                session complete\n"
    "Act fast when a wild pokemon appears (catch or flee windows are short). "
    "Be strategic toward the goal, adapt using the memory of past actions and "
    "outcomes, and never repeat a failing action."
)


def serialize_state(message, goal):
    lines = ["GAME STATE"]
    # message can be None: get_messages() returns nothing when the bot edited
    # or deleted its last message between the event firing and this call.
    chat_id = getattr(message, "chat_id", None)
    if message:
        text = (message.message or "(media only)")[:1500]
        lines.append(f"text: {text}")
        mk = getattr(message, "reply_markup", None)
        if mk and getattr(mk, "rows", None):
            lines.append("buttons:")
            for r, row in enumerate(mk.rows):
                for c, b in enumerate(row.buttons):
                    lines.append(f"  [{r},{c}] {b.text}")
    lines.append(f"goal: {goal or goal_text()}")
    tips = sessions.get(chat_id, {}).get("tips", [])
    if tips:
        lines.append("tips:")
        for t in tips[-MAX_TIPS_IN_PROMPT:]:
            lines.append(f"  {t}")
    kw = BOT_KNOWLEDGE.get(chat_id)
    if kw:
        lines.append("knowledge:")
        for ln in kw.splitlines():
            lines.append(f"  {ln.strip()}")
    hist = _memory.get(str(chat_id), [])
    if hist:
        lines.append("memory (past actions -> outcomes):")
        for h in hist[-10:]:
            lines.append(f"  {h['a']} -> {h['o']}")
    if message is None:
        lines.append("(game bot message no longer available — re-query or WAIT)")
    return "\n".join(lines)


def goal_text():
    """Goal for the session the caller is acting in; falls back to any session."""
    if not sessions:
        return "play optimally"
    s = next(iter(sessions.values()))
    return s.get("goal") or "play optimally"


async def llm_decide(state_prompt):
    if not config.OPENAI_API_KEY:
        return None
    if not _llm_budget_ok():
        return "STOP"
    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GAME_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": state_prompt},
        ],
        "max_tokens": 60,
        "temperature": 0.3,
    }
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                f"{config.OPENAI_API_BASE}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=LLM_TIMEOUT),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data["choices"][0]["message"]["content"].strip()
    except (aiohttp.ClientError, asyncio.TimeoutError, KeyError):
        return None


ACTION_RE = re.compile(r"(?:^|\n)\s*(?:action\s*[:=]\s*)?(SEND|PRESS|WAIT|STOP)\b[:\s]*([^\n]*)", re.I)
SOFT_RE = re.compile(r"\b(SEND|PRESS|WAIT|STOP)\b[:\s]*([^\n]*)", re.I)


def parse_action(text):
    if not text:
        return None
    m = ACTION_RE.search(text) or SOFT_RE.search(text)
    if not m:
        return None
    verb = m.group(1).upper()
    arg = (m.group(2) or "").strip().strip("`\"'")
    return verb, arg


async def run_turn(chat_id):
    s = sessions.get(chat_id)
    if not s or s.get("busy"):
        return
    if s["actions"] >= MAX_ACTIONS:
        await detach(chat_id, "action cap reached")
        return

    s["busy"] = True
    try:
        msgs = await bot.get_messages(chat_id, ids=[s["last_msg_id"]])
        message = msgs[0] if msgs else None
        state = serialize_state(message, s.get("goal", ""))
        raw = await llm_decide(state)
        parsed = parse_action(raw)
        if parsed is None:
            s["fails"] = s.get("fails", 0) + 1
            remember(chat_id, "?", f"unparsed reply: {str(raw)[:60] if raw else 'LLM timeout'}")
            if s["fails"] >= 3:
                await detach(chat_id, "3 bad LLM replies")
            return

        verb, arg = parsed
        if verb == "SEND":
            cmd = arg[:64].replace("\n", " ")
            await bot.send_message(chat_id, cmd)
            s["last_action"] = f"SEND {cmd}"
            s["actions"] += 1
        elif verb == "PRESS":
            m = re.match(r"^(\d+)\s*,\s*(\d+)$", arg)
            if not m:
                remember(chat_id, "PRESS ?", "bad coords")
                return
            r, c = int(m.group(1)), int(m.group(2))
            if not (message and getattr(message, "reply_markup", None)
                    and getattr(message.reply_markup, "rows", None)
                    and r < len(message.reply_markup.rows)
                    and c < len(message.reply_markup.rows[r].buttons)):
                remember(chat_id, f"PRESS {r},{c}", "button missing")
                return
            await message.click(r, c)
            s["last_action"] = f"PRESS {r},{c} ({message.reply_markup.rows[r].buttons[c].text})"
            s["actions"] += 1
        elif verb == "WAIT":
            secs = min(60, max(3, int(arg) if arg.isdigit() else 10))
            await asyncio.sleep(secs)
            asyncio.ensure_future(process_state(chat_id))
            return
        elif verb == "STOP":
            await detach(chat_id, "LLM chose STOP")
            return
    except Exception as e:
        import traceback
        traceback.print_exc()
        remember(chat_id, s.get("last_action") or "?",
                 f"error: {type(e).__name__}: {e}")
    finally:
        s["busy"] = False
        s["last_ts"] = time.time()


async def process_state(chat_id):
    s = sessions.get(chat_id)
    if not s:
        return
    now = time.time()
    since = now - s.get("last_ts", 0)
    if since < MIN_ACTION_GAP:
        await asyncio.sleep(MIN_ACTION_GAP - since)
    await run_turn(chat_id)


async def detach(chat_id, reason):
    s = sessions.pop(chat_id, None)
    try:
        await bot.send_message(
            chat_id, f"🛑 Game agent detached: {reason}. "
            f"Actions used: {s.get('actions', 0) if s else 0}."
        )
    except Exception:
        pass


@bot.on(events.NewMessage(incoming=True))
async def game_listener(event):
    await handle_state_event(event)


@bot.on(events.MessageEdited(incoming=True))
async def game_edited(event):
    await handle_state_event(event)


async def handle_state_event(event):
    chat_id = event.chat_id
    if chat_id not in sessions:
        return
    s = sessions[chat_id]
    s["last_msg_id"] = event.message.id
    if s.get("last_action"):
        remember(chat_id, s["last_action"],
                 (event.message.message or "(media)")[:80].replace("\n", " "))
        s["last_action"] = None
    asyncio.ensure_future(process_state(chat_id))


async def watchdog(chat_id):
    """Keep the agent moving when the game bot sends nothing new."""
    while chat_id in sessions:
        await asyncio.sleep(12)
        s = sessions.get(chat_id)
        if not s:
            return
        idle = time.time() - s.get("last_ts", 0)
        if idle >= 10 and not s.get("busy"):
            asyncio.ensure_future(process_state(chat_id))


async def resolve_entity(target):
    target = target.strip()
    if target.startswith("@"):
        return await bot.get_entity(target)
    if target.isdigit():
        return int(target)
    raise ValueError("pass @username or numeric chat id")


@command(r"play(?:\s+(.+))?")
async def play_cmd(event):
    """Attach the AI agent to a game bot. Usage: `.play @gamebot [goal]`"""
    if event.sender_id != config.OWNER_ID:
        return await event.reply("🔒 Owner only.")
    args = (event.pattern_match.group(1) or "").split(maxsplit=1)
    if not args:
        return await event.reply("Usage: `.play @gamebot [goal]`")
    target = args[0]
    goal = args[1] if len(args) > 1 else "play optimally"
    try:
        ent = await resolve_entity(target)
    except Exception as e:
        return await event.reply(f"Cannot resolve `{target}`: {e}")
    # `.play 12345` used to resolve to a *user*, and the agent would then try to
    # drive a DM conversation. Only attach to chats/bots.
    if isinstance(ent, int) or not getattr(ent, "bot", True):
        return await event.reply(f"`{target}` isn't a bot. Give the game bot's @username.")
    chat_id = ent.id
    sessions[chat_id] = {
        "goal": goal, "actions": 0, "fails": 0,
        "busy": False, "last_action": None, "last_msg_id": 0,
        "last_ts": 0,
    }
    _ensure_memory_flusher()
    last = await bot.get_messages(chat_id, limit=1)
    if last and last[0]:
        sessions[chat_id]["last_msg_id"] = last[0].id
    asyncio.ensure_future(watchdog(chat_id))
    await event.reply(
        f"🎮 Agent attached to `{target}`\nGoal: {goal}\n"
        f"Model: `{GAME_MODEL}`\n`.stopplay` to stop, "
        f"`.tip <text>` to guide it."
    )
    asyncio.ensure_future(process_state(chat_id))


@command("stopplay")
async def stopplay_cmd(event):
    """Stop all active AI game agents."""
    if event.sender_id != config.OWNER_ID:
        return
    if not sessions:
        return await event.reply("No active game sessions.")
    for cid in list(sessions):
        await detach(cid, "stopped by owner")
    await event.reply("All game agents stopped.")


@command("playstatus")
async def playstatus_cmd(event):
    """Show status of active AI game agents."""
    if event.sender_id != config.OWNER_ID:
        return await event.reply("🔒 Owner only.")
    if not sessions:
        return await event.reply("No active game sessions.")
    lines = ["🎮 **Game agents**"]
    for cid, s in sessions.items():
        lines.append(
            f"`{cid}` — actions: `{s['actions']}/{MAX_ACTIONS}`, "
            f"last: `{s.get('last_action') or 'idle'}`"
        )
    await event.reply("\n".join(lines))


@command(r"tip(?:\s+(.+))?")
async def tip_cmd(event):
    """Give the active agent a strategy hint. Usage: `.tip <text>`"""
    if event.sender_id != config.OWNER_ID:
        return await event.reply("🔒 Owner only.")
    text = (event.pattern_match.group(1) or "").strip()
    if not sessions:
        return await event.reply("No active game sessions.")
    if not text:
        return await event.reply("Usage: `.tip <what to do or avoid>`")
    targets = []
    for cid, s in sessions.items():
        tips = s.setdefault("tips", [])
        tips.append(text)
        del tips[:-MAX_TIPS]  # was unbounded: grew the prompt forever
        remember(cid, "TIP", text)
        targets.append(f"`{cid}`")
    await event.reply(f"💡 Tip noted for {', '.join(targets)}.")
