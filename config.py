import os
from dotenv import load_dotenv

load_dotenv()


def get(key: str, default=None):
    return os.getenv(key, default)


def get_int(key: str, default=0) -> int:
    """Int from env, tolerating '' and junk — a half-written .env is common."""
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


API_ID = get_int("API_ID", 0)
API_HASH = (get("API_HASH", "") or "").strip()
SESSION_NAME = get("SESSION_NAME", "userbot_session")
SESSION = get("SESSION", "")
OWNER_ID = get_int("OWNER_ID", 0)
PREFIXES = get("PREFIXES", ".,!,#").split(",")
LOG_CHAT_ID = get_int("LOG_CHAT_ID", 0)

# --- credential source ------------------------------------------------------
# An API_ID/API_HASH pair is not a secret and it cannot be derived from a
# Telegram account — it only exists once someone has filled in the form at
# my.telegram.org. If a user genuinely can't get their own, these are the
# credentials Telegram itself ships in tdesktop's public source. They work,
# but Telegram rate-limits them harder than a personal registration, and their
# docs say using them for anything real gets you API_ID_PUBLISHED_FLOOD.
#
# Set ALLOW_SHARED_CREDENTIALS=true to accept that trade. The default is off,
# because silently sharing one API ID between every install is how you get
# throttled by a quota you didn't know you had.
#
# Your own, from https://my.telegram.org -> API development tools:
#   tools/fetch_api_credentials.py automates everything except the login.
ALLOW_SHARED_CREDENTIALS = get("ALLOW_SHARED_CREDENTIALS", "false").lower() == "true"

SHARED_API_ID = 2040
SHARED_API_HASH = "b18441a1ff607e10a989891a5462e627"

USING_SHARED_CREDENTIALS = not (API_ID and API_HASH)

if USING_SHARED_CREDENTIALS and ALLOW_SHARED_CREDENTIALS:
    API_ID = SHARED_API_ID
    API_HASH = SHARED_API_HASH

CREDENTIAL_HELP = (
    "XENO needs an API_ID and API_HASH before it can talk to Telegram.\n"
    "\n"
    "  Quickest:  python tools/fetch_api_credentials.py\n"
    "              (opens a browser, logs you in, writes .env for you)\n"
    "\n"
    "  By hand:   https://my.telegram.org -> API development tools\n"
    "              then set API_ID and API_HASH in .env\n"
    "\n"
    "  No account to spare? Set ALLOW_SHARED_CREDENTIALS=true in .env to\n"
    "              share Telegram Desktop's published credentials. They work,\n"
    "              but Telegram throttles them harder than your own and may\n"
    "              return API_ID_PUBLISHED_FLOOD. Fine for one person testing\n"
    "              it; a bad idea across many installs."
)

GEMINI_API_KEY = get("GEMINI_API_KEY", "")
OPENAI_API_KEY = get("OPENAI_API_KEY", "")
OPENAI_API_BASE = get("OPENAI_API_BASE", "https://api.openai.com/v1")
AI_MODEL = get("AI_MODEL", "gpt-4o")
AI_AUTO_REPLY = get("AI_AUTO_REPLY", "false").lower() == "true"
AI_ALLOWED_IDS = get("AI_ALLOWED_IDS", "")
ETHSCAN_API_KEY = get("ETHSCAN_API_KEY", "")

BOT_NAME = get("BOT_NAME", "xeno")
PERSONA = get("PERSONA", "")

# --- assistant / control-panel bot (second TelegramClient) -----------------
# The userbot client can only be driven by messages *you* send (every
# @command handler is outgoing=True). The assistant is a separate Telegram
# identity so the userbot can be driven out-of-band, by DMing a bot.
ASSISTANT_ENABLED = get("ASSISTANT_ENABLED", "true").lower() == "true"
# BOT_TOKEN is still honoured as an override — set it and BotFather is never
# touched. Left empty (the default), XENO creates the bot itself on first boot
# and writes the token back to .env, so this only ever happens once.
BOT_TOKEN = get("BOT_TOKEN", "")
AUTO_BOTFATHER = get("AUTO_BOTFATHER", "true").lower() == "true"
# Overrides for the auto-created bot. Defaults below.
ASSISTANT_NAME = get("ASSISTANT_NAME", "") or "Assistant Bot"
ASSISTANT_USERNAME = get("ASSISTANT_USERNAME", "")
ASSISTANT_PREFIX = get("ASSISTANT_PREFIX", "/")
# Set the new bot's bio + description via BotFather so it reads as an
# assistant rather than a bare handle. Runs once, at creation time.
ASSISTANT_DECORATE = get("ASSISTANT_DECORATE", "true").lower() == "true"

BOT_START_TIME = None
ASSISTANT_START_TIME = None


def credentials_missing() -> bool:
    """True when there's nothing Telethon can connect with."""
    return not (API_ID and API_HASH)
