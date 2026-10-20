"""XENO mini-tools module: QR codes, text sharing (telegra.ph / paste.rs), one-offs."""
import io
import shutil
import tempfile

import aiohttp

from core.command import command
from core.http import get_json, post_form


async def create_telegraph(title, content):
    """Create a Telegraph page and return its URL. Anonymous account per call."""
    nodes = [{"tag": "p", "children": [ln]} for ln in content.split("\n")]
    async with aiohttp.ClientSession() as s:
        async with s.post(
            "https://api.telegra.ph/createAccount",
            json={"short_name": "Xeno", "author_name": "Xeno"},
            timeout=20,
        ) as r:
            acc = await r.json()
        if not acc.get("ok"):
            raise RuntimeError(acc.get("error", "telegraph account failed"))
        token = acc["result"]["access_token"]
        async with s.post(
            "https://api.telegra.ph/createPage",
            json={
                "access_token": token,
                "title": (title or "Xeno")[:64],
                "content": nodes,
                "author_name": "Xeno",
            },
            timeout=20,
        ) as r:
            page = await r.json()
    if not page.get("ok"):
        raise RuntimeError(page.get("error", "createPage failed"))
    return page["result"]["url"]


@command("qrcode")
async def qrcode_cmd(event):
    """Generate QR code from text. Usage: `.qrcode <text>`"""
    a = event.text.split(maxsplit=1)
    txt = a[1].strip() if len(a) > 1 else ""
    if not txt:
        return await event.eor("Give text/link to encode.")
    import qrcode
    try:
        img = qrcode.make(txt)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        await event.eor("**QR generated**", file=buf)
    except Exception as e:
        await event.eor(f"Error: `{e}`")




@command("telegraph")
async def telegraph_cmd(event):
    """Upload text to Telegraph. Usage: `.telegraph <text>` or reply to a message."""
    # Previously this posted access_token="" (always rejected), threw the
    # response away, and replied with an echo of the input instead of a link.
    try:
        if event.reply_to:
            r = await event.get_reply_message()
            txt = r.text or r.raw_text or ""
        else:
            a = event.text.split(maxsplit=1)
            txt = a[1].strip() if len(a) > 1 else ""
        if not txt:
            return await event.eor("Give text or reply to a text message.")
        url = await create_telegraph(txt.split("\n", 1)[0].strip()[:64] or "XENO", txt)
        return await event.eor(f"**Telegraph:**\n{url}")
    except Exception as e:
        return await event.eor(f"Error: `{e}`")


@command("cpaste")
async def paste_cmd(event):
    """Alternative paste (Paste.rs). Usage: `.cpaste <text>` or reply to file/text."""
    try:
        if event.reply_to:
            r = await event.get_reply_message()
            txt = r.text or r.raw_text or ""
            if r.media and not txt:
                path = await r.download_media(file=tempfile.mkdtemp(prefix="xeno_paste_"))
                if path:
                    txt = open(path, "r", errors="replace").read()
        else:
            a = event.text.split(maxsplit=1)
            txt = a[1].strip() if len(a) > 1 else ""
        if not txt:
            return await event.eor("Give text or reply to a message or file.")
        res = await post_form("https://paste.rs", data=txt, headers={"Content-Type": "text/plain"})
        url = (res or "").strip()
        if url.startswith("http"):
            return await event.eor(f"**Paste.rs:** {url}")
        return await event.eor(f"Paste failed: `{res[:200]}`")
    except Exception as e:
        return await event.eor(f"Error: `{e}`")


@command("trans")
async def trans_cmd(event):
    """Quick translate (MyMemory free API). Usage: `.trans <langcode> <text>`"""
    a = event.text.split(maxsplit=2)
    if len(a) < 3:
        return await event.eor("Usage: `.trans <target-lang> <text>` e.g. `.trans hi hello`")
    target, text = a[1], a[2]
    try:
        data = await get_json(
            "https://api.mymemory.translated.net/get",
            {"q": text, "langpair": f"en|{target}"})
        translated = data.get("responseData", {}).get("translatedText", "")
        if translated:
            if translated.startswith("MYMEMORY WARNING"):
                translated = translated.split(":", 1)[-1].strip()
            return await event.eor(f"**{target}:** `{translated}`")
        return await event.eor("No translation available.")
    except Exception as e:
        return await event.eor(f"Error: `{e}`")


@command("embed2")
async def embed2_cmd(event):
    """Box style text: usage `.embed2 <text>`"""
    a = event.text.split(maxsplit=1)
    txt = a[1].strip() if len(a) > 1 else ""
    if not txt:
        return await event.eor("Give text.")
    w = len(txt) + 4
    return await event.eor(f"```┌{'─'*(w-2)}┐\n│ {txt} │\n└{'─'*(w-2)}┘```")


@command("pinall")
async def pinall_cmd(event):
    """Pin every message above in this chat up to limit. Usage: `.pinall <n>`"""
    from core.auth import is_admin

    if not await is_admin(event.client, event.chat_id, event.sender_id):
        return await event.eor("You need admin rights to pin.")
    a = event.text.split(maxsplit=1)
    n = min(int(a[1]), 50) if len(a) > 1 and a[1].isdigit() else 10
    n = min(n, 50)
    if n < 1:
        return await event.eor("Give a positive number.")
    count = 0
    try:
        msgs = await event.client.get_messages(event.chat_id, limit=n)
        for m in msgs:
            try:
                await event.client.pin_message(event.chat_id, m.id)
                count += 1
            except Exception:
                break
        await event.eor(f"**Pinned {count} messages.**")
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("tpaste")
async def tpaste_cmd(event):
    """Paste + link in one step. Usage: `.tpaste <text>` or reply."""
    try:
        if event.reply_to:
            r = await event.get_reply_message()
            txt = r.text or r.raw_text or ""
        else:
            a = event.text.split(maxsplit=1)
            txt = a[1].strip() if len(a) > 1 else ""
        if not txt:
            return await event.eor("Give text or reply.")
        res = await post_form("https://paste.rs", data=txt, headers={"Content-Type": "text/plain"})
        url = (res or "").strip()
        return await event.eor(f"```\n{txt[:1500]}\n```\n\n[Paste link]({url})" if url.startswith("http") else "Paste failed.")
    except Exception as e:
        return await event.eor(f"Error: `{e}`")


@command("calc2")
async def calc2_cmd(event):
    """Simple arithmetic with many ops. Usage: `.calc2 <expr>`"""
    a = event.text.split(maxsplit=1)
    expr = a[1].strip() if len(a) > 1 else ""
    if not expr:
        return await event.eor("Usage: `.calc2 6*7`")
    import ast
    import operator as op
    ops = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
           ast.Mod: op.mod, ast.Pow: op.pow, ast.FloorDiv: op.floordiv,
           ast.USub: op.neg, ast.UAdd: op.pos}
    MAX_POW = 64          # unbounded `**` could wedge the worker forever
    MAX_INT = 10 ** 400

    def _eval(node):
        if isinstance(node, ast.Constant):
            # node.n was a deprecated ast.Num alias and is GONE in Python 3.14.
            # .value is the canonical attribute.
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise TypeError("non-numeric constant")
            return node.value
        if isinstance(node, ast.BinOp):
            left, right = _eval(node.left), _eval(node.right)
            if isinstance(node.op, ast.Pow):
                if abs(right) > MAX_POW or (isinstance(left, int) and abs(left) > 10):
                    raise ValueError(f"exponent/operand too large (max {MAX_POW})")
            result = ops[type(node.op)](left, right)
            if isinstance(result, (int, float)) and abs(result) > MAX_INT:
                raise ValueError("result too large")
            return result
        if isinstance(node, ast.UnaryOp):
            return ops[type(node.op)](_eval(node.operand))
        raise TypeError("unsupported")
    try:
        result = _eval(ast.parse(expr, mode="eval").body)
        return await event.eor(f"`{expr} = {result}`")
    except Exception as e:
        return await event.eor(f"Could not evaluate: `{e}`\nNumbers + `- * / % ** //` only.")