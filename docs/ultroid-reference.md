# Ultroid Source Reference

Verbatim study of [TeamUltroid/Ultroid](https://github.com/TeamUltroid/Ultroid) (`main`), extracted for XENO development. Every section below is sourced from the actual files; paths are given relative to the repo root. Truncated snippets were re-fetched where necessary — nothing here is paraphrased from memory.

---

## 1. Repository layout

```
pyUltroid/
  __init__.py            # package init: DB, clients, globals (sync module-level)
  __main__.py            # entry point: python -m pyUltroid
  configs.py             # Var class — env/CLI config
  version.py             # __version__, ultroid_version
  loader.py              # generic Loader class
  telethonpatch.py       # monkey-patches Telethon (imported FIRST, everywhere)
  startup/
    __init__.py          # logger/host detection (sync)
    BaseClient.py        # UltroidClient(TelegramClient)
    _database.py         # UltroidDB factory + backends
    connections.py       # validate_session, vc_connection
    funcs.py             # autobot, autopilot, customize, plug, ready, WasItRestart
    loader.py            # load_other_plugins() orchestration
    utils.py             # load_addons() — addon namespace injection
  _misc/
    __init__.py          # _SudoManager, owner_and_sudos, helpers
    _decorators.py       # ultroid_cmd, compile_pattern
    _assistant.py        # asst_cmd, callback, in_pattern
    _wrappers.py         # eor, eod, _try_delete
    _supporter.py        # admin_cmd, sudo_cmd compat shims
  fns/                   # helper utilities (bash, admin_check, tools…)
  dB/                    # typed DB wrappers over udB
  assistant/             # assistant-side plugins (start.py, manager/, pmbot.py)
  plugins/               # userbot plugins (__init__.py re-exports everything)
  addons/                # git-cloned third-party plugins
  strings/               # i18n get_string/get_help
```

Entry point is `python -m pyUltroid`. There is no repo-root `__init__.py`.

---

## 2. Boot sequence (exact order)

Source: `pyUltroid/__init__.py` + `pyUltroid/__main__.py`.

### Phase A — `import pyUltroid` (sync module-level)

```python
run_as_module = __package__ in sys.argv or sys.argv[0] == "-m"

if run_as_module:
    start_time = time.time()
    udB = UltroidDB()          # Redis > Mongo > SQL > LocalDB.json
    update_envs()               # mirror env/.env into udB (DB wins at runtime)
    udB.ping()

    BOT_MODE  = udB.get_key("BOTMODE")
    DUAL_MODE = udB.get_key("DUAL_MODE")
    USER_MODE = udB.get_key("USER_MODE")
    if USER_MODE:
        DUAL_MODE = False

    if BOT_MODE:
        ultroid_bot = None      # missing BOT_TOKEN → sys.exit()
    else:
        ultroid_bot = UltroidClient(
            validate_session(Var.SESSION, LOGS),
            udB=udB, app_version=ultroid_version, device_model="Ultroid",
        )
        ultroid_bot.run_in_loop(autobot())   # auto-create bot via BotFather if no token

    if USER_MODE:
        asst = ultroid_bot                  # single client
    else:
        asst = UltroidClient("asst", bot_token=udB.get_key("BOT_TOKEN"), udB=udB)

    # BOT_MODE: ultroid_bot = asst
    # else if assistant lacks inline placeholder → run_in_loop(enable_inline(...))
    vcClient = vc_connection(udB, ultroid_bot)
    _version_changes(udB)

    HNDLR      = udB.get_key("HNDLR") or "."
    DUAL_HNDLR = udB.get_key("DUAL_HNDLR") or "/"
    SUDO_HNDLR = udB.get_key("SUDO_HNDLR") or HNDLR
```

**Critical detail:** clients are *started inside their constructor* — `UltroidClient.__init__` calls `self.run_in_loop(self.start_client(bot_token=bot_token))`, i.e. `loop.run_until_complete(await self.start(...))`. Everything at import time is sync; async work is driven via repeated `run_until_complete`.

### Phase B — `main()` (sync chain of `run_until_complete`)

```python
def main():
    # optional self-update → os.execl(...) restart
    ultroid_bot.run_in_loop(startup_stuff())     # dirs, thumbnail, gdrive, TZ
    ultroid_bot.me.phone = None
    if not ultroid_bot.me.bot:
        udB.set_key("OWNER_ID", ultroid_bot.uid)
    ultroid_bot.run_in_loop(autopilot())         # ensure LOG_CHANNEL, invite/promote asst
    ultroid_bot.loop.create_task(keep_redis_alive())   # only fire-and-forget task
    load_other_plugins(addons=..., pmbot=..., manager=..., vcbot=...)  # SYNC imports
    ultroid_bot.run_in_loop(customize())         # BotFather profile pic for assistant
    if plugin_channels:
        ultroid_bot.run_in_loop(plug(plugin_channels))
    if not udB.get_key("LOG_OFF"):
        ultroid_bot.run_in_loop(ready())         # deploy message to LOG_CHANNEL
    ultroid_bot.run_in_loop(WasItRestart(udB))   # edit "_RESTART" message
    udB.re_cache()

if __name__ == "__main__":
    main()
    asst.run()          # ← THE ONLY BLOCKING CALL
```

**Boot one-liner:** `import pyUltroid` (DB → clients started in-ctor → `autobot` → `asst` → `vcClient`) → `main()` (sync chain of `run_until_complete` for startup/autopilot/customize/plug/ready; **sync** `Loader` imports; `create_task(keep_redis_alive)`) → `asst.run()` → `run_until_disconnected()` blocks.

Only **one** client ever calls `run_until_disconnected()` — the assistant. Both clients share the same event loop, so the main bot's handlers fire on it too.

### Shutdown

No `signal`, `atexit`, or cleanup code exists. Behavior comes from Telethon's `run_until_disconnected()`, `sys.exit()` on fatal errors, and `os.execl` for self-update. FloodWait handling inside the decorator does `disconnect → sleep → connect`.

---

## 3. `UltroidClient` — Telethon subclass

Source: `pyUltroid/startup/BaseClient.py`.

```python
class UltroidClient(TelegramClient):
    def __init__(self, session, api_id=None, api_hash=None, bot_token=None,
                 udB=None, logger=LOGS, log_attempt=True, exit_on_error=True,
                 *args, **kwargs):
        self._cache = {}
        self._dialogs = []
        self._handle_error = exit_on_error
        self._log_at = log_attempt
        self.logger = logger
        self.udB = udB
        kwargs["api_id"] = api_id or Var.API_ID
        kwargs["api_hash"] = api_hash or Var.API_HASH
        kwargs["base_logger"] = TelethonLogger
        super().__init__(session, **kwargs)
        self.run_in_loop(self.start_client(bot_token=bot_token))   # START IN CTOR
        self.dc_id = self.session.dc_id

    async def start_client(self, **kwargs):
        if self._log_at:
            self.logger.info("Trying to login.")
        try:
            await self.start(**kwargs)
        except ApiIdInvalidError:
            self.logger.critical("API ID and API_HASH combination does not match!")
            sys.exit()
        except (AuthKeyDuplicatedError, EOFError) as er:
            if self._handle_error:
                self.logger.critical("String session expired. Create new!")
                return sys.exit()
        except (AccessTokenExpiredError, AccessTokenInvalidError):
            self.udB.del_key("BOT_TOKEN")
            self.logger.critical("Bot token is expired or invalid...")
            sys.exit()
        self.me = await self.get_me()
        if self.me.bot:
            me = f"@{self.me.username}"
        else:
            setattr(self.me, "phone", None)
            me = self.full_name
        if self._log_at:
            self.logger.info(f"Logged in as {me}")
        self._bot = await self.is_bot()

    def run_in_loop(self, function):
        """run inside asyncio loop"""
        return self.loop.run_until_complete(function)

    def run(self):
        """run asyncio loop"""
        self.run_until_disconnected()

    def add_handler(self, func, *args, **kwargs):
        """Add new event handler, ignoring if exists"""
        if func in [_[0] for _ in self.list_event_handlers()]:
            return
        self.add_event_handler(func, *args, **kwargs)
```

Also: `fast_uploader`/`fast_downloader` (FastTelethon parallel transfer, cache in `self._cache`), `full_name`, `uid`, `parse_id(text)`.

### Session validation — `startup/connections.py`

`validate_session()` accepts Telethon `StringSession` (exactly 353 chars, current version prefix) or Pyrogram sessions of length 351/356/362 (struct-unpacked, DC IP looked up in `DC_IPV4`, repacked into Telethon format).

---

## 4. Database layer (`udB`)

Source: `pyUltroid/startup/_database.py`.

Backend chosen at import time:
1. `REDIS_URI`/`REDISHOST` → `RedisDB` (pip-installs `redis hiredis` if missing)
2. `MONGO_URI` → `MongoDB`
3. `DATABASE_URL` → `SqlDB`
4. else → `LocalDB` (`localdb.json`)

```python
def UltroidDB():
    try:
        if Redis:    return RedisDB(host=..., password=..., port=..., decode_responses=True, ...)
        elif MongoClient: return MongoDB(Var.MONGO_URI)
        elif psycopg2:    return SqlDB(Var.DATABASE_URL)
        else:             return LocalDB()
    except BaseException as err:
        LOGS.exception(err)
    exit()
```

**Key-value API** (all backends):

| Method | Behavior |
|---|---|
| `get_key(key)` | cache-first (`self._cache`), falls to `_get_data()` with `ast.literal_eval` deserialization |
| `set_key(key, value, cache_only=False)` | normalize → update cache → `set(str(key), str(value))` |
| `del_key(key)` | cache eviction + `delete(key)` |
| `re_cache()` | clear + rebuild whole cache |
| `rename(a, b)`, `ping()`, `keys()`, `usage` | |

`RedisDB` binds `self.set = self.db.set` etc. directly. `MongoDB` uses one collection per key (`{_id, value}`). `SqlDB` uses **one column per key** in table `Ultroid` (ALTER TABLE per set). `LocalDB` wraps JSON.

**Redis keepalive:** `keep_redis_alive()` task writes `KEEP_ACTIVE` every `max(interval, 60)` seconds.

**Config precedence:** CLI argv positions 1–5 > `.env` (dotenv+decouple) > defaults. `update_envs()` then mirrors env values into udB — **DB overrides env at runtime**.

---

## 5. `ultroid_cmd` — the command decorator

Source: `pyUltroid/_misc/_decorators.py`. Registration is via `client.add_event_handler(...)`, **not** `@client.on`.

### Pattern compilation

```python
def compile_pattern(data, hndlr):
    if data.startswith("^"):
        data = data[1:]
    if data.startswith("."):
        data = data[1:]
    if hndlr in [" ", "NO_HNDLR"]:
        return re.compile("^" + data)
    return re.compile("\\" + hndlr + data)
```

Prefix is regex-escaped (`.` → `\.`). Matched with Telethon's `re.match` semantics (anchored only at string start by the literal prefix).

### Registration matrix

| Registration | Client | Event | Pattern built with | Direction |
|---|---|---|---|---|
| Sudo dup (if `allow_sudo and HNDLR != SUDO_HNDLR`) | `ultroid_bot` | `NewMessage` | `SUDO_HNDLR` | `incoming=True` |
| Main command | `ultroid_bot` | `NewMessage` | `HNDLR` | `outgoing=True` **iff** sudo-dup registered, else `None` (= no filter) |
| Edits (if `TAKE_EDITS`) | `ultroid_bot` | `MessageEdited` | `HNDLR` | — |
| Manager (if `manager=True and MANAGER`) | `asst` | `NewMessage` | `"/"` | `incoming=True` |
| Dual-mode (if `DUAL_MODE`) | `asst` | `NewMessage` | `DUAL_HNDLR` | `incoming=True` |

All registrations set `forwards=False` and `func=lambda e: not e.via_bot_id` (default), plus `chats`/`blacklist_chats` from `BLACKLIST_CHATS`.

**Key semantic:** when no sudo dup is registered, the main handler has `outgoing=None, incoming=None` → **no direction filter** → incoming messages also reach `wrapp`, where `if not ult.out:` performs the owner/sudo gate. So a command can be executed *by the owner typing in a group* (incoming, owner authorized) or by the account itself (outgoing).

### Wrapper flow (inside `wrapp(ult)`)

1. `COMMAND_LOGGER` DB key → log + optional LOG_CHANNEL echo.
2. `if not ult.out:` gates — `owner_only` → reject; `sender_id not in owner_and_sudos()` → reject; `_ignore_eval` → `eod(py_d1)`; `fullsudo` → require `SUDO_M.fullsudos`.
3. `#noub` chat-title block (bypass = `DEVLIST`).
4. `groups_only`/`admins_only` → `eod(py_d3/py_d5)`; `only_devs` → requires `I_DEV`.
5. `await dec(ult)` with a **giant exception ladder**: `FloodWaitError` (disconnect/sleep/reconnect), `ChatSendInlineForbiddenError`, media-forbidden, `BotMethodInvalidError`, `AuthKeyDuplicatedError` (send session-generator buttons, `sys.exit()`), `StopPropagation` re-raise, catch-all → build crash log (versions, traceback, last 5 git commits) → send to LOG_CHANNEL via `asst` → edit original into a link to the log.
6. Bookkeeping: `LIST[file.stem] += [pattern]`; for `addons/`, `LOADED[file.stem].append(wrapp)` (used by `un_plug`).

### Kwarg flags

`owner_only`, `groups_only`, `admins_only`, `fullsudo`, `only_devs`, `manager` (+ `allow_all`, `allow_pm`, `require`), `func`, `ultroid_bot=`, `asst=`.

---

## 6. Assistant decorators

Source: `pyUltroid/_misc/_assistant.py`.

```python
def asst_cmd(pattern=None, load=None, owner=False, **kwargs):
    name = inspect.stack()[1].filename.split("/")[-1].replace(".py", "")
    kwargs["forwards"] = False
    def ult(func):
        if pattern:
            kwargs["pattern"] = re.compile(f"^/{pattern}")   # hard-anchored to "/"
        async def handler(event):
            if owner and event.sender_id not in owner_and_sudos():
                return
            try:
                await func(event)
            except Exception as er:
                LOGS.exception(er)
        asst.add_event_handler(handler, NewMessage(**kwargs))
        ...
    return ult

def callback(data=None, from_users=None, admins=False, owner=False, **kwargs):
    ...  # CallbackQuery handler; "me" in from_users → owner id
    asst.add_event_handler(wrapper, CallbackQuery(data=data, **kwargs))

def in_pattern(pattern=None, owner=False, **kwargs):
    ...  # InlineQuery handler
    asst.add_event_handler(wrapper, InlineQuery(pattern=pattern, **kwargs))
```

Facts:
- Assistant command prefix is **hard-coded `/`** — no configurable prefix.
- No direction filter by default (works for `/start` from anyone).
- `owner=` check is **opt-in**; without it, anyone can invoke.
- Exceptions inside `asst_cmd` are swallowed with `LOGS.exception` (no crash-log message, unlike `ultroid_cmd`).
- `load=` kwarg registers into `AST_PLUGINS` registry via `append_or_update`.

### Assistant `/start` — `assistant/start.py`

```python
@asst_cmd(pattern="start( (.*)|$)", forwards=False, func=lambda x: not x.is_group)
async def ultroid(event):
    args = event.pattern_match.group(1).strip()
    # logs first-time start to LOG_CHANNEL (BOT_USERS KeyManager)
    if event.sender_id not in SUDO_M.fullsudos:
        # normal user: STARTMSG/STARTMEDIA + "Info." button (data="ownerinfo")
    else:
        # owner: args=="set" → _settings buttons; else → _start buttons
        #   _start: Language / Settings / Stats / Broadcast / TimeZone
        #   _settings: API Keys / PM Bot / Alive / PMPermit / Features / VC Song
```

Menu state is held in `KeyManager` DB keys (`BOT_USERS`, `STARTMSG`, `STARTMEDIA`, `BOT_INFO_START`).

---

## 7. `eor` / `eod` — response helpers

Source: `pyUltroid/_misc/_wrappers.py`.

```python
async def eor(event, text=None, time=None, link_preview=False, edit_time=None, **args):
    reply_to = event.reply_to_msg_id or event
    if event.out and not isinstance(event, MessageService):
        if edit_time:
            await sleep(edit_time)
        if args.get("file") and not event.media:
            await event.delete()
            ok = await event.client.send_message(event.chat_id, text,
                link_preview=link_preview, reply_to=reply_to, **args)
        else:
            try:
                ok = await event.edit(text, link_preview=link_preview, **args)
            except MessageNotModifiedError:
                ok = event
    else:
        ok = await event.client.send_message(event.chat_id, text,
            link_preview=link_preview, reply_to=reply_to, **args)
    if time:
        await sleep(time)
        return await ok.delete()
    return ok

async def eod(event, text=None, **kwargs):
    kwargs["time"] = kwargs.get("time", 8)
    return await eor(event, text, **kwargs)

setattr(Message, "eor", eor)          # every Message gets .eor()
setattr(Message, "try_delete", _try_delete)
```

Semantics: **outgoing → edit; incoming → send new message** (can't edit someone else's). `eod` = `eor` + auto-delete after 8s.

---

## 8. Permission system

Source: `pyUltroid/_misc/__init__.py`.

```python
class _SudoManager:
    def get_sudos(self):        return self.db.get_key("SUDOS") or []
    @property
    def should_allow_sudo(self): return self.db.get_key("SUDO")   # master switch
    def owner_and_sudos(self):   return [self.owner, *self.get_sudos()]
    @property
    def fullsudos(self):
        fsudos = self.db.get("FULLSUDO")      # space-separated string
        ... return [int(_), ...] + [owner]
    def is_sudo(self, id_):      return bool(id_ in self.get_sudos())

SUDO_M = _SudoManager()
owner_and_sudos = SUDO_M.owner_and_sudos
```

- `SUDO` key = master switch; `SUDOS` = list of sudo IDs; `FULLSUDO` = space-separated full-sudo IDs.
- `fullsudo=True` commands require `SUDO_M.fullsudos`; normal commands accept `owner_and_sudos()`.
- `DEVLIST` (hardcoded IDs) bypasses only `#noub` chat blocking.
- Dev mode = `I_DEV` DB key, checked by `only_devs=True`.
- `admin_check(event, require=None)` (in `fns/admins.py`): owner/sudos → `True` immediately; anonymous admins proven via inline callback; else `get_permissions()` → require `is_admin` + specific right.

---

## 9. Plugin loading

### Generic `Loader` — `pyUltroid/loader.py`

```python
class Loader:
    def __init__(self, path="plugins", key="Official", logger=LOGS): ...
    def load(self, log=True, func=import_module, include=None, exclude=None,
             after_load=None, load_all=False):
        _single = os.path.isfile(self.path)
        if include:
            files = glob.glob(f"{self.path}/_*.py")   # underscore files always
            files += [existing paths for each include entry]
        elif _single:
            files = [self.path]
        else:
            files = get_all_files(...) if load_all else glob.glob(f"{self.path}/*.py")
            # exclude entries starting "_" are NEVER excludable
        for plugin in sorted(files):
            if func == import_module:
                plugin = plugin.replace(".py", "").replace("/", ".").replace("\\", ".")
            try:
                modl = func(plugin)
            except ModuleNotFoundError as er:
                self._logger.error(f"{plugin}: '{er.name}' not installed!"); continue
            except Exception as exc:
                self._logger.error(...); self._logger.exception(exc); continue
            if callable(after_load):
                after_load(self, modl, plugin_name=...)
```

**A broken plugin never aborts the load.**

### Orchestrator — `pyUltroid/startup/loader.py::load_other_plugins`

Load order: **`plugins/` → `assistant/` → `addons/` (git-cloned) → `assistant/manager/` → `assistant/pmbot.py` → `vcbot/`**.

- `EXCLUDE_OFFICIAL` / `INCLUDE_ONLY` DB keys filter official plugins.
- `assistant/` excluded if `USER_MODE` or `DISABLE_AST_PLUGINS`; always excludes `pmbot`, and `games` unless included.
- `addons/`: git-clone `TeamUltroid/UltroidAddons` if missing, `git pull` if present, `pip install -r addons/addons.txt`, recursive load with `func=load_addons`.
- `_after_load` populates `HELP[loader.key][plugin_name]` from `strings.get_help()` or `module.__doc__` (`.format(i=HNDLR)`).

### Addon namespace injection — `startup/utils.py::load_addons`

Third-party plugins written for other userbots import cleanly because these module attributes are injected **before** `exec_module`:

```python
name = plugin_name.replace("/", ".").replace("\\", ".").replace(".py", "")
spec = util.spec_from_file_location(name, plugin_name)
mod = util.module_from_spec(spec)
for path in configPaths:            # "ub", "userbot", "telebot", "fridaybot", ...
    modules[path] = config          # legacy names aliased to _supporter
mod.udB = udB; mod.asst = asst; mod.tgbot = asst
mod.ultroid_bot = ultroid_bot; mod.ub = mod.bot = mod.ultroid = mod.borg = mod.telebot = ...
mod.eod = eod; mod.eor = eor; mod.hndlr = mod.HNDLR = mod.CMD_HNDLR = HNDLR
mod.ultroid_cmd = mod.on_cmd = ultroid_cmd
mod.asst_cmd = asst_cmd; mod.callback = callback
mod.admin_cmd = admin_cmd; mod.sudo_cmd = sudo_cmd
mod.Config = Config; mod.Var = Var; mod.HELP = HELP.get("Addons", {})
spec.loader.exec_module(mod)
modules[name] = mod
```

### Plugin-channel loader — `startup/funcs.py::plug`

```python
async def plug(plugin_channels):
    # creates addons/ + __init__.py ("from plugins import *\n\nbot = ultroid_bot")
    for chat in plugin_channels:
        async for x in ultroid_bot.iter_messages(
            chat, search=".py", filter=InputMessagesFilterDocument, wait_time=10):
            plugin = "addons/" + x.file.name.replace("_", "-").replace("|", "-")
            if not os.path.exists(plugin):
                if x.text == "#IGNORE": continue
                plugin = await x.download_media(plugin)
                try:    load_addons(plugin)
                except Exception as e: ...; os.remove(plugin)
```

---

## 10. `.install` / `.unload` / `.uninstall` / `.load`

Source: `plugins/core.py` + `pyUltroid/fns/helper.py`.

```python
class KEEP_SAFE:
    All = [
        r"os\.system", r"subprocess\.(run|call|Popen|check_output)",
        r"exec\s*\(", r"eval\s*\(", r"__import__\s*\(",
        r"open\s*\(.*['\"]w['\"]", r"shutil\.(rmtree|move|copy)",
        r"session\.string", r"get_me\(\)", r"api_id", r"api_hash",
    ]
```

| Command | Semantics |
|---|---|
| `.install` | reply-to-`.py` → regex safety scan (`KEEP_SAFE.All`) → `load_addons`. `.install f` bypasses scan. `fullsudo=True`. |
| `.unload <name>` | `un_plug(name)` — removes handlers only. **Addons only** — refuses for `plugins/`. |
| `.uninstall <name>` | `un_plug` + `os.remove(addons/<name>.py)` |
| `.load <name>` | best-effort `un_plug` then re-`load_addons` from `addons/<name>.py` (hot reload). `fullsudo=True`. |
| `.getaddons <raw-url>` | download raw `.py` into `addons/`, then load. `fullsudo=True`. |

`un_plug(shortname)` removal: primary path removes exact wrapper functions tracked in `LOADED[shortname]` from both clients; fallback scans `client._event_builders` deleting any builder whose callback `__module__ == f"addons.{shortname}"`.

---

## 11. `autopilot()` — log channel provisioning

Source: `pyUltroid/startup/funcs.py`.

```python
async def autopilot():
    channel = udB.get_key("LOG_CHANNEL")
    if channel:
        try: chat = await ultroid_bot.get_entity(channel)
        except: udB.del_key("LOG_CHANNEL"); channel = None
    if not channel:
        # CreateChannelRequest(title="My Ultroid Logs", megagroup=True)
        #   ChannelsTooMuchError → save error, return
        channel = get_peer_id(chat); udB.set_key("LOG_CHANNEL", channel)
    # ensure assistant is PARTICIPANT (InviteToChannelRequest if not)
    # if newly created and assistant has no admin_rights:
    #   EditAdminRequest(channel, asst.me.username,
    #       ChatAdminRights(add_admins, invite_users, change_info, ban_users,
    #                       delete_messages, pin_messages, anonymous=False,
    #                       manage_call=True), "Assistant")
    # if chat.photo is ChatPhotoEmpty → download default photo, EditPhotoRequest
```

This is why the assistant can `send_message` to LOG_CHANNEL in Ultroid — it's always invited + promoted first. XENO's `personal` group fallback exists precisely because this step doesn't run for an arbitrary group.

---

## 12. `customize()` — assistant profile via BotFather

Source: `pyUltroid/startup/funcs.py` (verbatim core).

```python
async def customize():
    chat_id = udB.get_key("LOG_CHANNEL")
    if asst.me.photo:                    # ← runs at most once
        return
    LOGS.info("Customising Your Assistant Bot in @BOTFATHER")
    UL = f"@{asst.me.username}"
    sir = f"@{ultroid_bot.me.username}" if ultroid_bot.me.username else ultroid_bot.me.first_name
    file = random.choice(["https://graph.org/file/...jpg", ..., "resources/extras/ultroid_assistant.jpg"])
    if not os.path.exists(file):
        file, _ = await download_file(file, "profile.jpg"); rem = True
    msg = await asst.send_message(chat_id, "**Auto Customisation** Started on @Botfather")
    await asyncio.sleep(1)
    await ultroid_bot.send_message("botfather", "/cancel");      await asyncio.sleep(1)
    await ultroid_bot.send_message("botfather", "/setuserpic");  await asyncio.sleep(1)
    isdone = (await ultroid_bot.get_messages("botfather", limit=1))[0].text
    if isdone.startswith("Invalid bot"): return
    await ultroid_bot.send_message("botfather", UL);             await asyncio.sleep(1)
    await ultroid_bot.send_file("botfather", file);              await asyncio.sleep(2)
    # then /setabouttext + /setdescription with same UL/payload pattern
    await msg.edit("Completed **Auto Customisation** at @BotFather.")
```

**Why BotFather:** bots cannot call `UploadProfilePhotoRequest` — it only works on user accounts. The user client drives the BotFather conversation.

---

## 13. `ready()` — startup banner to log channel

Source: `pyUltroid/startup/funcs.py`.

```python
async def ready():
    chat_id = udB.get_key("LOG_CHANNEL")
    if not udB.get_key("INIT_DEPLOY"):          # FIRST DEPLOY
        MSG = "🎇 **Thanks for Deploying Ultroid Userbot!**\n• ..."
        PHOTO = "https://graph.org/file/54a917cc9dbb94733ea5f.jpg"
        BTTS = Button.inline("• Click to Start •", "initft_2")
        udB.set_key("INIT_DEPLOY", "Done")
    else:                                       # SUBSEQUENT
        MSG = f"**Ultroid has been deployed!**\n...UserMode/Assistant/Support..."
        BTTS, PHOTO = None, None
        prev_spam = udB.get_key("LAST_UPDATE_LOG_SPAM")
        if prev_spam: await ultroid_bot.delete_messages(chat_id, int(prev_spam))
        if await updater(): BTTS = Button.inline("Update Available", "updtavail")
    try:
        spam_sent = await asst.send_message(chat_id, MSG, file=PHOTO, buttons=BTTS)
    except ValueError as e:                     # ← bot not in chat → fall back
        await (await ultroid_bot.send_message(chat_id, str(e))).delete()
        spam_sent = await asst.send_message(chat_id, MSG, file=PHOTO, buttons=BTTS)
    except Exception as el:
        try: spam_sent = await ultroid_bot.send_message(chat_id, MSG)
        except Exception as ef: LOGS.exception(ef)
```

**Pattern:** assistant delivers first; on failure fall back to user client. Banner image (`file=PHOTO`) attached on first deploy; subsequent deploys send text-only (or delete previous spam).

---

## 14. `autobot()` — auto-provision bot via BotFather

Source: `pyUltroid/startup/funcs.py`. Runs only if `BOT_TOKEN` missing.

```python
async def autobot():
    # await ultroid_bot.start()
    # BotFather: /cancel → /newbot → name (from owner) → username candidates
    #   parse token from reply: isdone.split("`")[1]
    # udB.set_key("BOT_TOKEN", token)
    # enable_inline(...)  → /setinline
    # ANY failure → sys.exit(1)
```

XENO's equivalent lives in `core/assistant.py::autobot()` but is **non-fatal** (deliberate divergence: XENO boots as userbot-only if bot creation fails).

---

## 15. Alive / ping

Source: `plugins/bot.py`.

```python
@ultroid_cmd(pattern="alive( (.*)|$)")
async def lol(ult):
    # "alive inline" / "alive i" → inline query on assistant
    pic = udB.get_key("ALIVE_PIC")             # optional image (list → random choice)
    header = udB.get_key("ALIVE_TEXT") or default
    # git branch + repo URL from Repo().remotes[0]
    # formats markdown or html variant with versions/uptime/branch
    if pic:
        try:
            await ult.reply(als, file=pic, ...); await ult.try_delete()
        except ChatSendMediaForbiddenError: pass   # fall through to text
    await eor(ult, als, ...)

@ultroid_cmd(pattern="ping$", chats=[], type=["official", "assistant"])
async def _(event):
    start = time.time()
    x = await event.eor("Pong !")
    end = round((time.time() - start) * 1000)
    await x.edit(get_string("ping").format(end, uptime))
```

Customizable keys: `ALIVE_PIC`, `ALIVE_TEXT`, `ALIVE_EMOJI`.

---

## 16. Inline system

Sources: `pyUltroid/_misc/_assistant.py` (`in_pattern`) + `plugins/_inline.py`.

- `@in_pattern("ultd", owner=True)` — main inline help portal; `@in_pattern(owner=True, func=...)` with empty text = default result.
- `@in_pattern("stf(.*)", owner=True)` — generic send-via-inline: results stored in `STUFF` dict keyed by incrementing int; `something(e, msg, media, button)` queries `asst.me.username f"stf{num}"` and clicks. Used so **userbot can send media/buttons in chats where it lacks rights** (via the bot's inline identity).
- `@callback(data, owner=True)` — inline button callbacks; `callback(re.compile("uh_(.*)"))` for paginated help.
- `page_num(index, key)` builds paged `Button.inline` grids from `HELP[key]` with `HELP_ROWS`/`HELP_COLUMNS` keys.

---

## 17. Config (`Var`)

Source: `pyUltroid/configs.py`.

```python
class Var:
    API_ID     = int(sys.argv[1]) if len(sys.argv) > 1 else config("API_ID", default=6, cast=int)
    API_HASH   = sys.argv[2] if len(sys.argv) > 2 else config("API_HASH", default="...")
    SESSION    = sys.argv[3] if len(sys.argv) > 3 else config("SESSION", default=None)
    REDIS_URI  = sys.argv[4] ...   REDIS_PASSWORD = sys.argv[5] ...
    BOT_TOKEN  = config("BOT_TOKEN", default=None)
    LOG_CHANNEL = config("LOG_CHANNEL", default=0, cast=int)
    HEROKU_APP_NAME, HEROKU_API, VC_SESSION, ADDONS, VCBOT, DATABASE_URL, MONGO_URI, TGDB_URL ...
```

CLI argv positions 1–5 override env. `decouple` reads `.env`; `update_envs()` mirrors into udB.

---

## 18. Divergence notes for XENO

| Concern | Ultroid | XENO |
|---|---|---|
| Entry | `python -m pyUltroid`, sync module-level init | `main.py` async `asyncio.run(main())` |
| Client start | inside `UltroidClient.__init__` via `run_until_complete` | `await client.start(...)` in `start_bot()` / `start_assistant()` |
| Blocking call | `asst.run()` only | `asst.run_until_disconnected()` only (same pattern) |
| DB | Redis/Mongo/SQL/LocalJSON, pip auto-install | single `data/xeno_db.json`, debounced flush |
| Command decorator | `ultroid_cmd` — registers 1–5 handlers, giant exception ladder, sudo/manager/dual | `core/command.py::command()` — `outgoing=True`, single handler, thin wrapper |
| Assistant prefix | hard-coded `/` | `config.ASSISTANT_PREFIX` |
| Response helpers | `eor`/`eod` monkey-patched onto `Message` | plugins call `event.reply` / `event.edit` directly |
| Sudo system | `SUDO_M` with `SUDOS`/`FULLSUDO` keys | none (alpha) |
| Plugin loader | `Loader` class + `_after_load` → `HELP` registry; `_*.py` always included; excludes non-excludable if underscore | `core/plugin_loader.py`, flat |
| Addons | `load_addons` namespace shims for cross-userbot compat | `importlib.spec_from_file_location` under `addons.<name>` |
| `.install` | `KEEP_SAFE` regex scan, `.install f` force | `core/safety.py` scan, `.install f` force |
| Log channel | `autopilot()` auto-creates + invites + promotes assistant | `LOG_CHAT_ID` env; assistant may not be member → user-client fallback |
| Assistant pic | `customize()` via BotFather, once (`if asst.me.photo: return`) | same — implemented in `core/assistant.py::customize()` |
| Startup banner | `ready()` — assistant-first, fallback user client; `INIT_DEPLOY` one-shot | `core/assistant.py::ready()` — same try/fallback loop, every boot |
| Profile bio/desc | `/setabouttext` + `/setdescription` in `customize()` | `_decorate()` (only when AUTO_BOTFATHER created the bot) |
| Self-update | `.update` → `git pull` + `os.execl` | `update.sh` pull → verify → restart → rollback |
| Shutdown | no handlers; Telethon default | `finally: await db_flush()` |
| Crash reporting | decorator catches all → crash log to LOG_CHANNEL via `asst` | journalctl; no in-handler crash log (gap) |
| `alive` | customizable `ALIVE_PIC`/`ALIVE_TEXT`/`ALIVE_EMOJI`, inline variant, buttons | plain text reply (gap: no pic/buttons) |
| Inline system | full (`in_pattern`, `STUFF` send-via-inline, paged help) | none (gap) |
