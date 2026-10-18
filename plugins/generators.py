"""XENO generator series — random values, IDs, names, mini-data. Original code."""
import random
import secrets
import string
import uuid

from core.command import command


@command("genid")
async def genid_cmd(event):
    """Random UUID. Usage: `.genid`"""
    return await event.reply(f"**UUID:** `{uuid.uuid4()}`")


@command("otp")
async def otp_cmd(event):
    """Random 6-digit OTP code (CSPRNG)."""
    return await event.reply(f"**OTP (6):** `{secrets.randbelow(900000) + 100000}`")


@command("pin4")
async def pin_cmd(event):
    """Random 4-digit pin (CSPRNG)."""
    return await event.reply(f"**PIN (4):** `{secrets.randbelow(9000) + 1000}`")


@command("token")
async def token_cmd(event):
    """Random hex token (CSPRNG, 2 chars per requested unit)."""
    n = int(event.text.split(maxsplit=1)[1]) if len(event.text.split()) > 1 else 16
    n = max(4, min(64, n))
    return await event.reply(
        f"**Token ({n} bytes):**\n`{secrets.token_hex(n)}`"
    )


@command("hexcolor")
async def hexcolor_cmd(event):
    """Random hex color."""
    c = "".join(random.choices("0123456789abcdef", k=6))
    return await event.reply(f"**Hex:** `#{c}` —  [preview](tg://search_hashtag?hashtag={c})")


@command("rgbi")
async def rgbi_cmd(event):
    """Random RGB values."""
    return await event.reply(f"**RGB:** `({random.randint(0,255)}, {random.randint(0,255)}, {random.randint(0,255)})`")


@command("cointoss")
async def cointoss_cmd(event):
    """Heads or tails."""
    return await event.reply(f"**🪙** `{random.choice(['Heads', 'Tails'])}`")


@command("dicex")
async def dice_cmd(event):
    """Roll one or more dice. Usage: `.roll` / `.dice <n>` dice are via ❓ n dice of 6"""
    a = event.text.split(maxsplit=1)
    n = int(a[1]) if len(a) > 1 and a[1].isdigit() else 1
    n = max(1, min(10, n))
    vals = [random.randint(1, 6) for _ in range(n)]
    return await event.reply(f"**🎲** {vals} (sum `{sum(vals)}`)")


@command("randname")
async def randname_cmd(event):
    """Random fun username."""
    pre = ["cosmic", "neon", "lazy", "cyber", "mega", "tiny", "epic", "savage", "wild", "smart"]
    suf = ["wolf", "panda", "bot", "ninja", "ghost", "tiger", "byte", "storm", "cactus", "vibe"]
    digits = random.randint(10, 99)
    return await event.reply(f"**👤:** `@{random.choice(pre)}_{random.choice(suf)}{digits}`")


@command("pickfrom")
async def pickfrom_cmd(event):
    """Pick a random item. Usage: `.pickfrom a,b,c`"""
    a = event.text.split(maxsplit=1)
    arg = a[1].strip() if len(a) > 1 else ""
    if not arg:
        return await event.reply("Give items comma-separated: `.pickfrom a,b,c`")
    items = [x.strip() for x in arg.split(",") if x.strip()]
    return await event.reply(f"**🎯 Chosen:** `{random.choice(items)}`")


@command("rollx")
async def roll_cmd(event):
    """Roll a d20. Usage: `.roll` (aliases: .dice)"""
    return await event.reply(f"**🎲 d20:** `{random.randint(1, 20)}`")


@command("flipx")
async def flip_cmd(event):
    """Flip a coin 2 — heads/tails."""
    return await event.reply(f"**🪙 Flip:** `{random.choice(['Heads', 'Tails'])}`")


@command("gift")
async def gift_cmd(event):
    """Random made-up gift idea."""
    items = ["a mug that insults you gently", "cactus named Gerald", "one (1) mystery box",
             "a sky-blue notebook", "fancy tea sampler", "USB star projector",
             "a tiny leash for your emotions", "12-pack of random socks",
             "an AI friend for a month", "a framed picture of doge"]
    return await event.reply(f"**🎁 Gift idea:** {random.choice(items)}")


@command("colorpick")
async def colorpick_cmd(event):
    """Random palette of 3 colors."""
    cols = [f"#{''.join(random.choices('0123456789abcdef', k=6))}" for _ in range(3)]
    return await event.reply(f"**🎨 Palette:** {' '.join(cols)}")


@command("lucky")
async def lucky_cmd(event):
    """Lucky number + day."""
    return await event.reply(
        f"**🍀 Lucky today:** num `{random.randint(1, 99)}`, "
        f"day `{random.choice(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])}`")


@command("motto")
async def motto_cmd(event):
    """Random life motto."""
    ms = ["Stay curious. Stay dangerous.", "Small steps still count.",
          "Perfect is the enemy of done.", "Sleep is a power-up.",
          "Be the chaos you want to see.", "Hydrate like it's your job.",
          "Done > perfect.", "One bot to rule them all."]
    return await event.reply(f"✨ *{random.choice(ms)}*")


@command("truths")
async def truths_cmd(event):
    """Random truth-dare prompt style. Usage: `.truths`"""
    ts = ["What's your most controversial opinion?", "If you could erase one memory, which?",
          "What's your biggest guilty pleasure?", "What lie have you told recently?",
          "Which friend would you switch lives with?"]
    return await event.reply(f"🎲 *{random.choice(ts)}*")


@command("hint")
async def hint_cmd(event):
    """Random life/coding hint."""
    hs = ["Always validate input.", "Backup before you break things.",
          "Sleep well before debugging.", "Never deploy on Friday.",
          "Talks are cheap; working code speaks.", "Log generously, die proudly.",
          "Stop and read the error message.", "Regex: now you have two problems."]
    return await event.reply(f"💡 *{random.choice(hs)}*")


@command("prompt")
async def prompt_cmd(event):
    """Random creative writing prompt."""
    ps = ["You're a time traveler glued to one year. Which?",
          "The AI wrote a love letter to its dev. Go.",
          "Street festival at 3AM. What happens?",
          "You woke up as the server. POV.",
          "A cat becomes CEO of a tech firm."]
    return await event.reply(f"✍️ *{random.choice(ps)}*")


@command("trend")
async def trend_cmd(event):
    """Random made-up trend for a fictional market."""
    t = random.choice(["AI pets", "solar umbrellas", "mood rings 2.0", "telegram bots",
                       "vertical farms", "VR cafés"])
    v = random.randint(-40, 120)
    arrow = "▲" if v >= 0 else "▼"
    return await event.reply(f"**📈 Trend watch:** `{t}` is {arrow} {abs(v)}% this week.")


@command("factoid")
async def factoid_cmd(event):
    """A science-ish factoid."""
    fs = ["Honey never spoils.", "Octopuses have 3 hearts.", "Bananas are berries.",
          "A day on Venus outlasts its year.", "Water can boil and freeze at once.",
          "Sharks existed before trees.", "Humans share 60% DNA with bananas."]
    return await event.reply(f"🌱 *{random.choice(fs)}*")


@command("lucknum")
async def lucknum_cmd(event):
    """Fate's chosen number."""
    return await event.reply(f"🔢 Fate selected: `{random.randint(1, 10**6)}`")