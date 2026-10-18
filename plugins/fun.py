"""XENO fun module: jokes, quotes, memes, magic 8-ball, advice, facts.
Mix of local curated content and free no-key APIs. Original code."""
import random
import time

from core.command import command
from core.http import get_json, get_text

_JOKES = [
    ("Why don't scientists trust atoms?", "Because they make up everything."),
    ("I told my computer I needed a break.", "Now it won't stop sending me Kit-Kat ads."),
    ("Why did the scarecrow win an award?", "He was outstanding in his field."),
    ("What do you call a fake noodle?", "An impasta."),
    ("Why did the bicycle fall over?", "Because it was two-tired."),
]
_TRUTHS = [
    "What's the most embarrassing thing you've done in public?",
    "Have you ever lied about your age?",
    "What's the biggest lie you've told to get out of plans?",
    "Who here have you had a crush on?",
    "What's a secret your parents still don't know?",
    "Worst date you've ever been on?",
    "What's the last thing you searched on your phone that you'd hide?",
    "Have you ever read someone else's messages?",
    "What possession would you save in a fire besides people?",
    "Ever cheated in an exam?",
]
_DARES = [
    "Do your best celebrity impression right now.",
    "Sing your current favorite song out loud.",
    "Send the last photo in your gallery to this chat.",
    "Do 10 push-ups right now.",
    "Speak in an accent for the next 3 turns.",
    "Post your screen time this week.",
    "Text your mom and tell her you love her.",
    "Do the worm or a dab, your choice.",
    "Reveal your most recent online purchase.",
    "Talk like a pirate until your next turn.",
]
_COMPLIMENTS = [
    "You have an amazing aura — people feel better around you.",
    "Your brain works faster than most CPUs.",
    "You're proof that kindness and brains can coexist.",
    "That confidence? It's working. Keep it.",
    "You give off main-character energy and I'm here for it.",
    "Your humor is criminally underrated.",
    "You make hard things look effortless.",
    "If energy could be bottled, yours would sell out.",
]
_ROASTS = [
    "You're like a software update — whenever I see you, I immediately think 'not now'.",
    "You have the charisma of a buffering video.",
    "If I wanted to hear from a clown, I'd visit the circus. Sit down.",
    "You're the human equivalent of a comma splice.",
    "Your Wi-Fi signal is stronger than your comebacks.",
    "You're proof that god has a sense of humor.",
    "You bring everyone so much joy — when you leave.",
    "You're not stupid; you're just possessed by a slow horse.",
]


@command("8ball")
async def ball_cmd(event):
    """Ask the magic 8-ball a yes/no question."""
    answers = [
        "It is certain.", "Without a doubt.", "You may rely on it.", "Yes definitely.",
        "As I see it, yes.", "Most likely.", "Outlook good.", "Yes.",
        "Signs point to yes.", "Reply hazy, try again.", "Ask again later.",
        "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
        "Don't count on it.", "My reply is no.", "My sources say no.",
        "Outlook not so good.", "Very doubtful.", "Absolutely not.",
    ]
    a = event.text.split(maxsplit=1)
    q = a[1].strip() if len(a) > 1 else ""
    if not q:
        return await event.reply("Ask me something: `.8ball <question>`")
    return await event.reply(f"🎱 **{q}**\n→ {random.choice(answers)}")


@command("joke")
async def joke_cmd(event):
    """Get a random joke."""
    try:
        data = await get_json("https://official-joke-api.appspot.com/random_joke")
        return await event.reply(f"**{data['setup']}**\n\n{data['punchline']}")
    except Exception:
        s, p = random.choice(_JOKES)
        return await event.reply(f"**{s}**\n\n{p}")


@command("dadjoke")
async def dadjoke_cmd(event):
    """Get a dad joke."""
    try:
        txt = await get_text(
            "https://icanhazdadjoke.com/", headers={"Accept": "text/plain"})
        return await event.reply(txt.strip())
    except Exception as e:
        return await event.reply(f"**{e}** — but here: `{random.choice(_JOKES)[0]}`")


@command("chuck")
async def chuck_cmd(event):
    """Get a Chuck Norris joke."""
    try:
        data = await get_json("https://api.chucknorris.io/jokes/random")
        return await event.reply(data.get("value", ""))
    except Exception as e:
        return await event.reply(f"Chuck is busy: `{e}`")


@command("advice")
async def advice_cmd(event):
    """Get a random piece of advice."""
    try:
        data = await get_json("https://api.adviceslip.com/advice")
        slip = data.get("slip", {})
        return await event.reply(f"💡 **{slip.get('advice', '')}**")
    except Exception as e:
        return await event.reply(f"`{e}`")


@command("fact")
async def fact_cmd(event):
    """Get a random (useless) fact."""
    try:
        data = await get_json("https://uselessfacts.jsph.pl/api/v2/facts/random")
        return await event.reply(f"ℹ️ {data.get('text', '')}")
    except Exception as e:
        hist = [
            "Honey never spoils — archaeologists have eaten 3000-year-old honey.",
            "Octopuses have three hearts and blue blood.",
            "Bananas are berries, but strawberries aren't.",
            "A group of flamingos is called a 'flamboyance'.",
            "Sharks existed before trees.",
            "Your fingernails grow about 3.5 mm per month.",
            "Lightning strikes the Empire State Building ~25 times a year.",
            "Mercury and Venus are the only planets without moons.",
        ]
        return await event.reply(f"ℹ️ {random.choice(hist)}  (api off: `{e}`)")


@command("truth")
async def truth_cmd(event):
    """Get a truth challenge."""
    return await event.reply(f"🗣 **TRUTH:** {random.choice(_TRUTHS)}")


@command("dare")
async def dare_cmd(event):
    """Get a dare challenge."""
    return await event.reply(f"🔥 **DARE:** {random.choice(_DARES)}")


@command("wyr")
async def wyr_cmd(event):
    """Ask a would-you-rather question."""
    qs = [
        ("Live without music or without movies?", ""),
        ("Only swim in the ocean or only hike mountains forever?", ""),
        ("Know the date of your death or the cause of it?", ""),
        ("Be famous now but irrelevant later, or unknown now and legendary later?", ""),
        ("Never use the internet again or never eat carbs again?", ""),
        ("Have 100 followers who know you, or 100k who don't?", ""),
        ("Lose all memories before age 20, or memories after 20?", ""),
        ("Be feared or be loved?", ""),
        ("Be able to talk to animals or speak every human language?", ""),
        ("Get $10k now or $100k in 10 years?", ""),
    ]
    return await event.reply(f"⚖️ **Would you rather…**\n{random.choice(qs)[0]}")


@command("topic")
async def topic_cmd(event):
    """Suggest a conversation topic."""
    ideas = [
        "What's a hill you'd die on?",
        "If you could instantly master one skill, what would it be?",
        "What movie could you watch a hundred times?",
        "What's the best life advice you've ever received?",
        "If money didn't matter, what would your dream day look like?",
        "What's something you think is overrated?",
        "Where's the most beautiful place you've ever been?",
        "What childhood possession do you still wish you had?",
        "What's a small habit that changed your life?",
        "If you could have dinner with any 3 people, living or dead, who?",
    ]
    return await event.reply(f"💬 **Talk:** {random.choice(ideas)}")


@command("insult")
async def insult_cmd(event):
    """Get an insult (API, falls back to local roasts)."""
    try:
        txt = await get_text(
            "https://insult.mattbas.org/api/insult?lang=en",
            headers={"User-Agent": "xeno/1.0"})
        if txt and txt.strip():
            return await event.reply(txt.strip())
        raise ValueError("empty")
    except Exception:
        return await event.reply(f"😈 {random.choice(_ROASTS)}")


@command("truthordare")
async def tod_cmd(event):
    """Random truth-or-dare."""
    return await event.reply(f"{random.choice(_TRUTHS if random.random() < 0.5 else _DARES)}")


@command("horoscope")
async def horoscope_cmd(event):
    """Daily horoscope: `.horoscope <sign>`."""
    signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
             "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    a = event.text.split(maxsplit=1)
    s = a[1].strip().title() if len(a) > 1 else random.choice(signs)
    if s not in signs:
        return await event.reply(f"Pick a real sign: {', '.join(signs)}")
    try:
        data = await get_json(f"https://horoscope-app-api.vercel.app/api/v1/get-horoscope/daily?sign={s.lower()}&day=today")
        d = data.get("data", {})
        moods = d.get("mood", "curious")
        return await event.reply(
            f"**♈ {s} — {d.get('date', '')}**\n\n"
            f"{d.get('horoscope_data', '')}\n\n_Mood: {moods}_")
    except Exception:
        # The old ternary keyed off `if not a`, but event.text.split() always
        # returns at least one element, so the six-item list was unreachable.
        pred = [
            "Embrace the chaos — today's a gift wrapped in confusion.",
            "A message you've been waiting for arrives. Stay by your phone.",
            "Energy is high. Spend it on you, not on everyone else.",
            "Old friends reach out. Answer.",
            "Money flows in, patience pays out.",
            "Something ends — and that's the setup for something better.",
        ]
        return await event.reply(f"{s}: {random.choice(pred)}")


@command("handshake")
async def handshake_cmd(event):
    """Fun handshake encounter line."""
    funs = [
        "🤝 Hey, you seem cool. Nice to meet ya.",
        "🤝 Firm grip. You've been to the gym.",
        "🤝 That was a solid handshake. A+.",
        "🤝 Awkward pause... but we got there.",
        "🤝 Cold hands, warm heart?",
        "🤝 Hand me a snack next time. Deal?",
    ]
    return await event.reply(random.choice(funs))


@command("flip")
async def flip_cmd(event):
    """Flip a coin (heads or tails)."""
    return await event.reply(random.choice(["Heads!", "Tails!"]))


@command("mpc")
async def mpc_cmd(event):
    """Generate an absurd fake prophecy."""
    lines = [
        "I'm a potato who sold his yacht to buy a star and now banks in the void.",
        "You will become a space-taco tycoon, then lose it all to a literal raccoon.",
        "A shadow whispers your name at 3 PM. It just wants directions.",
        "Your next pet will be an AI goldfish that remembers every lie you tell.",
        "Beware of the cosmic geese. They collect quarters and everything unravels.",
        "Tomorrow: a pigeon grants you one wish but misspells it.",
        "You will find a sock that changed your life. Then lose it.",
        "The moon is watching. No, seriously. It called your name.",
    ]
    return await event.reply(random.choice(lines))


@command("nameme")
async def nameme_cmd(event):
    """Random title, or moniker for `<name>`."""
    a = event.text.split(maxsplit=1)
    name = a[1].strip() if len(a) > 1 else ""
    titles = ["The Bold", "The Silent Storm", "of the Void", "The Unstoppable",
              "the Cheese Wizard", "The Nightmare", "the Pixel Knight", "The Oracle",
              "the Crypto Queen", "The Professor", "the Last Human", "the Tidebreaker"]
    suffix = random.choice(titles)
    if name:
        return await event.reply(f"🏷 From now on you are **{name} {suffix}**.")
    return await event.reply(f"🏷 Your title shall be **{random.choice(titles)}**.")