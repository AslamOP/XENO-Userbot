"""Games: telegram dice, rps, guess, trivia, choose, coin — per-chat scoreboard."""
import asyncio
import json
import os
import random
from telethon.tl.types import InputMediaDice, MessageMediaDice

from core.command import command

# Lives in data/ so it survives a container rebuild (compose only mounts ./data).
SCORE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "scores.json"
)

game_state = {}
scores = {}
_dirty = False


def load_scores():
    global scores
    if os.path.exists(SCORE_FILE):
        try:
            with open(SCORE_FILE) as f:
                scores = json.load(f)
        except (json.JSONDecodeError, OSError):
            scores = {}


def save_scores():
    global _dirty
    _dirty = True


_flush_task = None


async def _scores_flush_loop():
    """Coalesce writes: the old code rewrote the file inside the event loop on
    every single point scored."""
    while True:
        await asyncio.sleep(3)
        if not _dirty:
            continue
        try:
            os.makedirs(os.path.dirname(SCORE_FILE), exist_ok=True)
            tmp = SCORE_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(scores, f, indent=2)
            os.replace(tmp, SCORE_FILE)
            _dirty = False
        except Exception:
            pass


def _ensure_flusher():
    """Start the flusher on first use, so importing the plugin spawns no task."""
    global _flush_task
    if _flush_task is None or _flush_task.done():
        _flush_task = asyncio.ensure_future(_scores_flush_loop())


def add_point(chat_id, user_id, game):
    c = str(chat_id)
    u = str(user_id)
    entry = scores.setdefault(c, {})
    user = entry.setdefault(u, {"name": "", "wins": {}})
    user["wins"][game] = user["wins"].get(game, 0) + 1
    save_scores()
    _ensure_flusher()


load_scores()


# ---------- Telegram-native dice ----------

DICE = {
    "dice": "🎲",
    "dart": "🎯",
    "basket": "🏀",
    "football": "⚽",
    "bowl": "🎳",
    "slot": "🎰",
}

DICE_MSG = {
    "🎲": "You rolled",
    "🎯": "You threw",
    "🏀": "You scored",
    "⚽": "You kicked",
    "🎳": "You bowled",
    "🎰": "Slot result",
}


def make_dice_cmd(name):
    async def handler(event):
        msg = await event.client.send_file(
            event.chat_id,
            file=InputMediaDice(emoticon=DICE[name]),
        )
        if isinstance(msg.media, MessageMediaDice):
            val = msg.media.value
            label = DICE_MSG.get(msg.media.emoticon, "Result")
            await msg.reply(f"{msg.media.emoticon} **{label}** `{val}`")
    handler.__name__ = f"{name}_cmd"
    return handler


for _n in DICE:
    command(_n)(make_dice_cmd(_n))


# ---------- Classic games ----------


@command("coin")
async def coin_cmd(event):
    """Flip a coin: heads or tails."""
    side = random.choice(["Heads", "Tails"])
    await event.eor(f"🪙 **Coin flip: {side}**")


@command("choose")
async def choose_cmd(event):
    """Pick one of several comma-separated options."""
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        return await event.eor("Usage: `.choose option1, option2, ...`")
    options = [o.strip() for o in args[1].split(",") if o.strip()]
    if len(options) < 2:
        return await event.eor("Give me at least 2 options separated by commas.")
    await event.eor(f"🔮 I pick: **{random.choice(options)}**")


RPS = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
RPS_BEATS = {"rock": "scissors", "scissors": "paper", "paper": "rock"}


@command("rps")
async def rps_cmd(event):
    """Play rock-paper-scissors: `.rps rock|paper|scissors`."""
    args = event.text.split(maxsplit=1)
    if len(args) < 2 or args[1].strip().lower() not in RPS:
        return await event.eor("Usage: `.rps rock|paper|scissors`")
    player = args[1].strip().lower()
    bot_pick = random.choice(list(RPS))

    if player == bot_pick:
        verdict = "Draw 🤝"
    elif RPS_BEATS[player] == bot_pick:
        add_point(event.chat_id, event.sender_id, "rps")
        verdict = "**You win!** 🎉"
    else:
        verdict = "**I win!** 😎"

    await event.eor(
        f"{RPS[player]} {player} vs {RPS[bot_pick]} {bot_pick}\n{verdict}"
    )


@command("guess")
async def guess_cmd(event):
    """Start a guess-the-number game (1-10). Answer with `.g <n>`."""
    game_state.setdefault(event.chat_id, {})["guess"] = random.randint(1, 10)
    await event.eor("🔢 I picked a number **1-10**. Reply `.g <n>` to guess!")


@command("g")
async def guess_answer_cmd(event):
    """Answer the active guess game: `.g <1-10>`."""
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        return await event.eor("Usage: `.g <1-10>`")
    try:
        n = int(args[1])
    except ValueError:
        return await event.eor("That's not a number.")
    if not 1 <= n <= 10:
        return await event.eor("Pick a number between 1 and 10.")

    target = game_state.get(event.chat_id, {}).get("guess")
    if target is None:
        return await event.eor("No active game. Start with `.guess`.")

    if n == target:
        add_point(event.chat_id, event.sender_id, "guess")
        game_state[event.chat_id].pop("guess", None)
        await event.eor(f"🎯 **Correct!** It was {target}. +1 point")
    elif n < target:
        await event.eor(f"⬆️ Higher. ({n} -> ?)")
    else:
        await event.eor(f"⬇️ Lower. ({n} -> ?)")


TRIVIA = [
    ("Which planet is known as the Red Planet?", ["Venus", "Mars", "Jupiter", "Saturn"], 1),
    ("What is 7 x 8?", ["54", "56", "64", "72"], 1),
    ("Who wrote 'Romeo and Juliet'?", ["Dickens", "Shakespeare", "Austen", "Hemingway"], 1),
    ("Capital of Japan?", ["Seoul", "Beijing", "Tokyo", "Bangkok"], 2),
    ("Which element has symbol 'O'?", ["Gold", "Oxygen", "Osmium", "Iron"], 1),
    ("How many continents are there?", ["5", "6", "7", "8"], 2),
    ("What does a computer speak?", ["English", "Binary", "French", "HTML"], 1),
    ("Most populous country?", ["USA", "India", "Russia", "Brazil"], 1),
    ("Fastest land animal?", ["Lion", "Cheetah", "Horse", "Greyhound"], 1),
    ("How many sides does a hexagon have?", ["5", "6", "7", "8"], 1),
]


@command("trivia")
async def trivia_cmd(event):
    """Start a trivia question. Answer with `.t A/B/C/D`."""
    q, opts, correct = random.choice(TRIVIA)
    game_state.setdefault(event.chat_id, {})["trivia"] = (q, opts, correct)
    lines = [f"❓ **{q}**"]
    for i, o in enumerate(opts):
        lines.append(f"`{'ABCD'[i]}` {o}")
    lines.append("Reply `.t A/B/C/D` to answer!")
    await event.eor("\n".join(lines))


@command("t")
async def trivia_answer_cmd(event):
    """Answer the active trivia: `.t A/B/C/D`."""
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        return await event.eor("Usage: `.t A/B/C/D`")
    idx = "ABCD".find(args[1].strip().upper())
    if idx < 0:
        return await event.eor("Use A, B, C or D.")

    state = game_state.get(event.chat_id, {})
    entry = state.get("trivia")
    if not entry:
        return await event.eor("No active trivia. Start with `.trivia`.")
    q, opts, correct = entry

    if idx == correct:
        add_point(event.chat_id, event.sender_id, "trivia")
        state.pop("trivia", None)
        await event.eor(f"✅ **Correct!** Answer: {opts[correct]}. +1 point")
    else:
        await event.eor(f"❌ Wrong. Correct is `{'ABCD'[correct]}`: {opts[correct]}. New round? `.trivia`")


@command("score")
async def score_cmd(event):
    """Show the chat game leaderboard."""
    c = str(event.chat_id)
    entry = scores.get(c)
    if not entry:
        return await event.eor("No scores yet in this chat. Play `.rps` to start!")

    lines = ["🏆 **Leaderboard**"]
    rows = []
    for uid, data in entry.items():
        total = sum(data.get("wins", {}).values())
        rows.append((total, uid, data))
    for total, uid, data in sorted(rows, reverse=True)[:10]:
        wins = ", ".join(f"{k}:{v}" for k, v in data["wins"].items())
        name = data.get("name") or f"user {uid}"
        try:
            ent = await event.client.get_entity(int(uid))
            name = getattr(ent, "first_name", None) or name
        except Exception:
            pass
        lines.append(f"`{total:>3}` pts | {name} | ({wins})")
    await event.eor("\n".join(lines))