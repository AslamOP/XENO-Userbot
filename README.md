# XENO — Python Telegram userbot

> ## 🧪 ALPHA
> **Not production-ready, and not audited.** It boots, and 304 offline checks
> pass, but it has never been run against a live account by anyone but its
> author. `.install` executes arbitrary code as this process, and installed
> plugins can read `*.session` — that file *is* your account.
>
> **Run it on a spare Telegram account.** See [Status](#status) for what works,
> what doesn't, and what's missing versus the established userbots.

A modular Telethon userbot with ~470 commands across 36 plugin modules.
Everything is auto-discovered: drop a file in `plugins/` and its commands are live.

## Quick start

    cp .env.example .env      # then fill API_ID / API_HASH / OWNER_ID from my.telegram.org
    python main.py            # first run prints a QR — scan it with the owner account

Docker:

    docker compose up -d --build
    docker compose logs -f
    docker compose down

One-shot deploy to a VPS (installs Docker if missing, rsyncs, builds, starts):

    ./deploy.sh user@your-vps [~/.ssh/id_rsa]

- No ports are exposed — Telegram uses long-poll MTProto, not HTTP.
- `restart: unless-stopped` keeps it alive across reboots.
- Only `./data/` is persisted (session, notes, moderation state, scores).

## Commands

`.help` — full index (auto-generated from the live handler registry)
`.help <module>` — one module, e.g. `.help textify`
`.help <command>` — locate a command, e.g. `.help ban`

Prefixes are `.` `!` `#` `,` (see `PREFIXES` in `.env`).
Every `@command` handler is registered `outgoing=True`, so **only your own
account can invoke them**.

## Two identities: userbot + assistant bot

XENO runs up to two Telegram clients:

- **userbot** — your account. Every `.command` is `outgoing=True`, so only your
  own messages trigger it.
- **assistant** — a separate bot you DM to drive the userbot out-of-band. Prefix
  `/`, owner-only, deliberately does **not** expose `.evalx`/`.execx`.

    AUTO_BOTFATHER=true   # default — XENO creates "Assistant Bot" for you

Panel commands: `/start` `/status` `/config` `/get <key>` `/set <key> <value>`
`/ambient` `/setambient <feature> on|off [everywhere]` `/modules`
`/commands [module]` `/logs [n]` `/restart`

Only these config keys are writable from the panel (`PANEL_KEYS` in
`plugins/control.py`): `PREFIXES` `AI_MODEL` `AI_AUTO_REPLY` `AI_ALLOWED_IDS`
`BOT_NAME` `PERSONA` `THEME` `OWNER_ID`.

`AUTO_BOTFATHER` is **on by default**. On first boot XENO messages @BotFather and
creates a bot named **"Assistant Bot"** with a `<your username>_bot` handle
(retrying with `assistant_<id><n>_bot` if taken) — the same flow as Ultroid's
`autobot()`. The token is stored in `data/xeno_db.json` (and mirrored to `.env`),
so it only ever runs once.

Two deliberate divergences from Ultroid:

- **No `sys.exit()`.** Ultroid hard-exits when BotFather refuses, which leaves you
  with no userbot at all. Here, failure returns `None`, logs why, and XENO boots
  as a userbot regardless.
- **Token lives in the db first.** `.env` is often read-only in Docker; the db is
  authoritative and `.env` is best-effort.

Set `BOT_TOKEN` to skip BotFather entirely.

## Updates

`.update` — pull latest from git, verify imports/tests, restart with automatic rollback if verification fails.  
`.upcheck` — check for available updates without applying.  
`.rollback` — revert to last known good commit.  
Uses `update.sh` with built-in safety checks.

## Autonomous ("ambient") handlers are OFF by default

These react to *other people's* messages — auto-deleting them, muting them,
replying to them. Each one is disabled until you explicitly enable it:

    .ambient                     # show status
    .ambient antispam on         # global
    .ambient captcha on here     # this chat only

Registered features: `antispam`, `blacklist`, `filters`, `captcha`, `linklock`,
`gban`, `persona`, `ai_auto`.

## Owner / sudo

`OWNER_ID` in `.env` is the only fully trusted account. `.evalx` / `.execx` run
arbitrary Python as the process user and are available to sudo users too —
don't add anyone you wouldn't hand a shell.

Modules: admin · ai · animex · casex · commander · crypto · datetimex ·
extras · finishx · fun · game · games · generators · globals · group ·
hashx · langx · media · mediacli · minitools · misc · notesx · numconv ·
opsx · persona · photofx · profile · search · sysx · tagx · textify ·
textstyle · tools · warden · words · world · control

## Deploying

`./deploy.sh user@your-vps` rsyncs the code but excludes `data/` (live state) and
`.env`, then SCPs your `.env` separately. Docker compose mounts `./data` only.

## Tests

    python tests/run.py              # everything, offline
    python tests/run.py panel        # one module

No network, no Telegram session, no pytest. Covers the BotFather dialogue
(including transport failures), control-panel authorization, and the plugin
registry. `data/xeno.log` is a 5MB×3 rotating file — the panel's `/logs`
reads it.

## Adding your own scripts

`core/plugin_loader.py` imports every `.py` in `plugins/` whose name does not
start with `_`. Importing runs the `@command` decorators, so a dropped file's
commands go live on the next start. No manifest, no registry edit.

Copy `plugins/_template.py` — it has six worked examples: a plain command, one
using the db, an owner-only one, an HTTP one, a replied-message one, and an
ambient handler.

```bash
cp plugins/_template.py plugins/mytask.py
$EDITOR plugins/mytask.py

./addplugin.sh plugins/mytask.py                  # upload + restart + verify
./addplugin.sh --remove plugins/mytask.py
./addplugin.sh plugins/mytask.py --no-restart    # upload only
```

By hand:

```bash
scp plugins/mytask.py ubuntu@13.220.255.57:/home/ubuntu/xeno/plugins/
ssh -i ~/.pem ubuntu@13.220.255.57 'sudo systemctl restart xeno'
sudo journalctl -u xeno | grep "Loaded plugin"     # confirm it registered
```

A plugin that fails to import is logged and skipped — it cannot take the bot
down. But it also means a silent failure, so check the journal after adding one.

Things worth knowing:

- **A restart is required.** Nothing hot-reloads.
- `@command` is `outgoing=True` — it only fires for messages *you* send.
- For handlers that react to other people's messages use raw `@bot.on(...)`
  **and** an `ambient_enabled("yourfeature", chat_id)` gate, with the name
  added to `AMBIENT_FEATURES` in `core/auth.py`. Un-gated ambient handlers fire
  in every chat the account is in, forever.
- `.evalx` / `.execx` run Python live (owner **and** sudo), if you'd rather not
  touch the filesystem.

## Status

### Maturity

`2.1.0-alpha`. Alpha means: it works on the parts that have been exercised, and
nobody outside the author has run it. `.maturity` in Telegram reports the same
thing at runtime.

| | |
|---|---|
| Tested | 283 offline checks on the deployment target (Ubuntu 26.04 / Python 3.14) |
| Untested | live Telegram traffic, multi-day sessions, multi-account use, `.webshot` against real sites |
| Deploy target | 1 vCPU / 908 MB RAM — the swap file and `MemoryMax=450M` exist because of this |

### Where XENO sits against the established userbots

Researched against the current versions as of October 2026.

| Project | Licence | Base | Last push | Notes |
|---|---|---|---|---|
| **Uroboros** | AGPL-3.0 | Telethon + aiogram | Oct 2026 | Newest project. Four access tiers, stable/dev channels, update-with-rollback, backup/restore, Hikka+FTG module adapter |
| CatUserbot | AGPL-3.0 | Telethon | Mar 2026 | Largest community (~1.5k stars). Still Heroku-shaped |
| Ultroid | — | Telethon | Jul 2026 | Source of the `addons/` + pre-install code scan XENO copied |
| Dragon-Userbot | GPL-3.0 | Pyrogram | Apr 2025 | Requires MongoDB |
| Hikka | AGPL-3.0 | Telethon | Mar 2025 | **Dead.** Final changelog entry is "Grand finale" — archived, development stopped |
| Userge | GPL-3.0 | Pyrogram | May 2024 | Effectively unmaintained |
| Pyrobud | MIT | Telethon | — | Deliberately anti-spam; best deployment advice of the lot |

XENO's 346 commands are well ahead of most of these, but that is the easy axis.
The things that actually matter for safety are behind.

### What XENO has that they don't

- **Every handler is `outgoing=True`** and there's a separate assistant bot, so a
  hijacked plugin still can't be driven by someone else in a group. No other
  project here defaults to that shape.
- **Store-scoped file access.** `.get` resolves an exact filename inside
  `downloads/` and re-checks the result against the store root. Ultroid's `.ul`
  globs arbitrary paths and only blocks the literal string `.env`.
- **Pre-install scan** (`core/safety.py`, 10 rules) with `.install f` to override
  and report what tripped.
- **Two-tier plugin lifetimes** — `.addplugin` (session-only, swept at boot) vs
  `.install` → `addons/` (persistent), plus `.load`/`.unload` to disable without
  deleting.
- **278–283 offline checks** in CI-able form. Most of these projects ship a
  "known to work, probably" module loader and no test suite at all.

### Where XENO is behind

Ordered by how much they hurt.

1. **Plugins can read `*.session` at runtime. This is the serious one.**
   Uroboros blocks it. A Telethon session file is a complete account takeover —
   anyone holding it reads your chats with no code and no password. XENO's
   safety scan only inspects source at install time; it does nothing about what
   a *loaded* addon can do afterwards. Hikka shipped this class of bug as
   **CVE-2025-52571, CVSS 9.6 critical**, fixed only in 1.6.2.

2. **No update rollback.** Uroboros `.update` shows a changelog, installs, and
   reverts on failure. XENO's deploy is manual — a bad push is a `git`-less
   filesystem and a bad afternoon.

3. **No backup/restore.** No equivalent of Uroboros' `.backup`/`.restore`. A
   single `*.session` deletion means re-login on a headless box.

4. **One access tier.** Owner-only for everything. Ultroid allows sudo users to
   `.install`; Uroboros has `owner`/`sudo`/`support`/per-command. Owner-only is
   defensible but it means no delegated operation.

5. **No module ecosystem.** No `.addrepo`, no Hikka/FTG adapter. The 346
   commands are hand-written; nothing is importable from elsewhere.

6. **No LICENSE file.** Every comparable project is AGPL or GPL. XENO is
   currently unlicensed, which means nobody else may legally use it.

7. **Known command collisions.** Seven names are registered twice
   (`.b`, `.calc`, `.date`, `.g`, `.hex`, `.pin`, `.sha`) — two handlers fire per
   invocation.

### Deliberate differences

- **No `.eval`/`.exec` in the assistant panel.** Every other project here
  exposes code execution. XENO's panel is config-only; install-based execution
  still exists but is owner-gated and scanned.
- **No arbitrary-path upload.** See `.get` above.
- **No Redis, no MongoDB.** State is a JSON file. Fine at this scale, and it
  means the whole thing fits in 450 MB.

## Installing plugins and managing files from Telegram

    .addplugin         reply to a .py  →  ⚡ temporary, gone on restart
    .delplugin <name>                      remove a temporary one
    .install [f]       reply to a .py  →  💾 addons/, survives restarts
    .uninstall <name>                      delete an installed one
    .load <name>                           switch an installed one back on
    .unload <name>                         disable it, keep the file
    .plugins                              list all three groups

⚠️ `.addplugin` and `.install` run code as the XENO process. Whoever can send
them owns the VPS — treat any `.py` you receive like a shell script. Every
command on this page is **owner-only**.

### Three states, three directories

    plugins/            ships with XENO. Can't be replaced or removed from chat.
    addons/             `.install` writes here. Survives restarts. The
                        directory itself is the record of ownership.
    data/tmp_plugins/   `.addplugin` writes here as top-level modules.
                        `core/custom.sweep_tmp()` deletes it at boot.

A built-in module always wins a name collision with an addon, so an installed
script can't quietly replace core code.

### `.install` scans before it writes

`.install` reads the source and pattern-matches it against a blocklist before
anything touches the disk. If anything trips, the install is refused and the
file is never written:

    os.system / subprocess / shell=True   runs a process
    eval / exec / __import__              executes code at runtime
    os.remove / shutil.rmtree             deletes files
    open('/etc/...')                      touches system or credential paths
    hardcoded http://<ip>                 an unpinned network endpoint

Bare `import os` is fine — it's the *calls* that trip it. A plugin that only
uses the bot's own API passes clean.

This is a **static regex scan, not a sandbox**. It catches accidents, not
attackers, and nothing should. If you wrote the plugin and trust it, `.install f`
forces past the scan and tells you which rules it tripped on the way through.

### `.unload` is not `.uninstall`

`.unload <name>` strips the handlers and remembers the choice, so the addon stays
off across restarts — but the file is still in `addons/` to read, and
`.load <name>` brings it straight back. `.uninstall <name>` deletes the file for
good.

### Files

    .save [name]       reply to media   →  downloads/    (.download, .savefile)
    .get <name>        send a stored file back
    .ls                list the store                 (.files)
    .delfile <name> force   delete a stored file       (.rm)
    .fileinfo          metadata for replied media
    .sticker           reply to an image → post as a sticker
    .webshot <url>     screenshot a page  → post it
    .json              dump a message as JSON

`downloads/` persists and is reachable only by exact filename — never by path,
so there is no `../../etc/passwd`. Filenames are validated before the join and
the result is re-checked against the store root afterwards.

There's deliberately no `.del` here: `admin.py` already owns it, and it deletes
the replied *message*. Registering it twice would fire two handlers per command.

Ownership is tracked in `data/custom_plugins.json`. Anything in `plugins/` that
*isn't* in that registry is treated as built-in and cannot be removed or
overwritten through these commands. `manage` and `control` are always protected.

Installs are rejected if the file has a syntax error, is over 256KB, or has a
name that isn't a valid Python identifier (`my-plugin.py` won't import — use
`my_plugin.py`). If a plugin loads but raises at import time, it is rolled back
automatically: the file and the registry entry are both removed.

The remote-plugin installer Ultroid has (`PLUGIN_CHANNEL`, which pulls `.py`
files from a Telegram channel) is what `.addplugin` replaces.
