import logging
import os
import qrcode
import time
from logging.handlers import RotatingFileHandler

from telethon import TelegramClient
from telethon.errors import AccessTokenInvalidError
from telethon.sessions import StringSession

import config

LOG_FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt="%H:%M:%S",
)
log = logging.getLogger("userbot")

# Panel `/logs` needs a real file to read. Without this, logging went to stderr
# only, so the command could never work under the documented Docker deploy
# (keepalive.sh's redirect aside).
LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
LOG_FILE = os.path.join(LOG_DIR, "xeno.log")
try:
    os.makedirs(LOG_DIR, exist_ok=True)
    _fh = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    _fh.setFormatter(logging.Formatter(LOG_FORMAT, datefmt="%H:%M:%S"))
    logging.getLogger().addHandler(_fh)
    log.info(f"Logging to {LOG_FILE}")
except OSError as e:  # read-only volume, permissions, ...
    log.warning(f"File logging disabled: {e}")

_session = StringSession(config.SESSION) if config.SESSION else config.SESSION_NAME

bot = TelegramClient(
    _session,
    config.API_ID,
    config.API_HASH,
    retry_delay=1,
    auto_reconnect=True,
    connection_retries=3,
    timeout=20,
    request_retries=3,
)


async def _qr_login(quiet=False):
    """Headless QR login: renders the code to the log + keeps refreshing until scanned."""
    await bot.connect()
    # If no saved session or session appears invalid, do QR login
    if not config.SESSION:
        qr = await bot.qr_login()
        log.info("=== XENO QR LOGIN ===")
        log.info("Scan with the OWNER account: Telegram > Settings > Devices > Link a Desktop Device")
        while True:
            if not quiet:
                try:
                    q = qrcode.QRCode(border=1)
                    q.add_data(qr.url)
                    q.make(fit=True)
                    q.print_ascii(invert=True)
                    out_path = getattr(config, "SESSION_FILE", "/tmp/xeno_qr.png")
                    q.make_image().save(out_path)
                except Exception:
                    pass
            try:
                if await qr.wait(timeout=30):
                    break
                try:
                    img = qrcode.make(qr.url)
                    img.save("/tmp/xeno_qr.png")
                    log.info("QR refreshed -> /tmp/xeno_qr.png")
                except Exception:
                    pass
            except Exception:
                continue
    else:
        raise RuntimeError("SESSION string is not valid Telethon session")


async def start_bot():
    config.BOT_START_TIME = time.time()
    await bot.connect()
    if not await bot.is_user_authorized():
        log.warning("No valid session found. Starting QR login flow...")
        await _qr_login()
    me = await bot.get_me()
    log.info(f"Logged in as {me.first_name} (@{me.username}) [ID: {me.id}]")
    return me
