"""XENO sys module — host telemetry. Owner-only: these leak the VPS's details."""
import os
import platform
import shutil
import time

from core.auth import is_owner
from core.command import command


async def _deny(event):
    if not await is_owner(event):
        await event.reply("🔒 Owner only — this reports host internals.")
        return True
    return False


@command("uptime")
async def uptime_cmd(event):
    """Host uptime. Usage: `.uptime`"""
    if await _deny(event):
        return
    try:
        with open("/proc/uptime") as f:
            up = float(f.read().split()[0])
        days, rem = divmod(int(up), 86400)
        hrs, rem = divmod(rem, 3600)
        mins, secs = divmod(rem, 60)
        await event.reply(
            f"**💻 Uptime:** `{days}d {hrs}h {mins}m {secs}s`\n"
            f"🈶 Since: `{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() - up))}`"
        )
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("sysinfo")
async def sysinfo_cmd(event):
    """System info: hostname, arch, OS, python."""
    if await _deny(event):
        return
    await event.reply(
        f"**🖥 System info:**\n"
        f"Host: `{platform.node()}`\n"
        f"OS: `{platform.platform()}`\n"
        f"Arch: `{platform.machine()}`\n"
        f"Python: `{platform.python_version()}`\n"
        f"Release: `{platform.release()}`"
    )


@command("mem")
async def mem_cmd(event):
    """Memory usage. Usage: `.mem`"""
    if await _deny(event):
        return
    try:
        with open("/proc/meminfo") as f:
            raw = [l for l in f if ":" in l]
        data = {k: int(v.split()[0]) for k, v in (l.split(":", 1) for l in raw)}
        total = data["MemTotal"] // 1024
        avail = data.get("MemAvailable", data["MemFree"]) // 1024
        await event.reply(
            f"**🧠 Memory:**\n"
            f"Total: `{total} MB`\n"
            f"Used: `{total - avail} MB`\n"
            f"Available: `{avail} MB`\n"
            f"Swap: `{data.get('SwapTotal', 0) // 1024} MB`"
        )
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("cpu")
async def cpu_cmd(event):
    """CPU load (loadavg). Usage: `.cpu`"""
    if await _deny(event):
        return
    try:
        with open("/proc/loadavg") as f:
            p = f.read().split()
        await event.reply(
            f"**🎛 CPU load:**\n"
            f"1m: `{p[0]}`\n5m: `{p[1]}`\n15m: `{p[2]}`\n"
            f"Runnable: `{p[3]}`\nTotal procs: `{p[4]}`"
        )
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("diskspace")
async def diskspace_cmd(event):
    """Disk usage of /. Usage: `.diskspace`"""
    if await _deny(event):
        return
    try:
        u = shutil.disk_usage("/")
    except Exception as e:
        return await event.reply(f"Error: `{e}`")
    await event.reply(
        f"**💾 Disk (/):**\n"
        f"Total: `{u.total / 2**30:.1f} GB`\nUsed: `{u.used / 2**30:.1f} GB`\n"
        f"Free: `{u.free / 2**30:.1f} GB`\nUsage: `{u.used / u.total * 100:.1f}%`"
    )


@command("whoami")
async def whoami_cmd(event):
    """Your own Telegram identity. Usage: `.whoami`"""
    # This used to report the *userbot account*, which printed its ID, username
    # and premium status into whatever chat it was typed in.
    u = await event.get_sender()
    me = await event.client.get_me()
    await event.reply(
        f"**👤 You:**\n"
        f"ID: `{u.id}`\nName: `{u.first_name}`\n"
        f"Username: `@{u.username if getattr(u, 'username', None) else '—'}`\n"
        f"Premium: `{bool(getattr(u, 'premium', False))}`\n"
        f"\n_(this account is id `{me.id}`)_"
    )