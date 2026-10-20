"""In-chat update with changelog and rollback wrapper around update.sh."""
import asyncio
import os
import subprocess

from core.auth import is_owner
from core.command import command


@command("update")
async def update_cmd(event):
    """Update from git with verification + rollback. Usage: `.update`"""
    if not await is_owner(event):
        return await event.eor("🔒 Owner only.")
    
    await event.eor("🔄 Starting update... (this may take a minute)")
    
    update_script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "update.sh")
    if not os.path.exists(update_script):
        return await event.eor("❌ update.sh not found")
    
    try:
        proc = await asyncio.create_subprocess_exec(
            "bash", update_script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=os.path.dirname(update_script)
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=600)
        output = stdout.decode()[-2000:] if stdout else "(no output)"
        if proc.returncode == 0:
            await event.eor(f"✅ Update complete\n\n{output}")
        else:
            await event.eor(f"⚠️ Update finished with exit code {proc.returncode}\n\n{output}")
    except asyncio.TimeoutError:
        await event.eor("❌ Update timed out after 10 minutes")
    except Exception as e:
        await event.eor(f"❌ Update failed: {e}")


@command("upcheck")
async def upcheck_cmd(event):
    """Check for updates without applying. Usage: `.upcheck`"""
    if not await is_owner(event):
        return await event.eor("🔒 Owner only.")
    
    update_script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "update.sh")
    if not os.path.exists(update_script):
        return await event.eor("❌ update.sh not found")
    
    try:
        proc = await asyncio.create_subprocess_exec(
            "bash", update_script, "--check",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=os.path.dirname(update_script)
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        output = stdout.decode()[-1500:] if stdout else "(no output)"
        await event.eor(f"📊 Update check\n\n{output}")
    except Exception as e:
        await event.eor(f"❌ Check failed: {e}")


@command("rollback")
async def rollback_cmd(event):
    """Rollback to last known good commit. Usage: `.rollback`"""
    if not await is_owner(event):
        return await event.eor("🔒 Owner only.")
    
    update_script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "update.sh")
    if not os.path.exists(update_script):
        return await event.eor("❌ update.sh not found")
    
    try:
        proc = await asyncio.create_subprocess_exec(
            "bash", update_script, "--rollback",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=os.path.dirname(update_script)
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        output = stdout.decode()[-1500:] if stdout else "(no output)"
        await event.eor(f"⏪ Rollback\n\n{output}")
    except Exception as e:
        await event.eor(f"❌ Rollback failed: {e}")
