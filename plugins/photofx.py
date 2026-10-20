"""XENO photo module: Pillow-based image effects, captions, image search.

Requires Pillow. It's an optional dependency (see requirements.txt), so if the
import fails the whole module skips itself rather than taking the plugin loader
down with it.
"""
import io
import os
import re
import shutil
import tempfile
import urllib.parse

from core.command import command
from core.http import get_text

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

    # Pillow's own bomb guard is off by default; a 200MP PNG would OOM the host.
    Image.MAX_IMAGE_PIXELS = 50_000_000
    HAVE_PIL = True
except ImportError as _e:  # pragma: no cover
    HAVE_PIL = False
    _PIL_ERROR = _e

MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024


if HAVE_PIL:

    async def _run_effect(event, label, fn, fmt="JPEG"):
        """Download the replied media to a private temp dir, apply fn, send, clean up."""
        if not event.reply_to:
            return await event.eor("Reply to an image.")
        tmpdir = tempfile.mkdtemp(prefix="xeno_fx_")
        try:
            r = await event.get_reply_message()
            path = await r.download_media(file=tmpdir)
            if not path:
                return await event.eor("Media not downloaded.")
            size = os.path.getsize(path)
            if size > MAX_DOWNLOAD_BYTES:
                return await event.eor(f"Image too large ({size // 1048576}MB). Max 20MB.")
            img = Image.open(path)
            img.load()
            out = fn(img)
            buf = io.BytesIO()
            out.save(buf, format=fmt)
            buf.seek(0)
            await event.eor(f"**{label}:**", file=buf)
        except Exception as e:
            await event.eor(f"Error: `{e}`")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _register():
        """Wire up every Pillow-dependent command."""
        from core.command import command as _c

        @_c("caption")
        async def caption_cmd(event):
            """Add a caption line to a replied image. Usage: `.caption <text>`"""
            if not event.reply_to:
                return await event.eor("Reply to an image.")
            txt = event.text.split(maxsplit=1)
            text = txt[1].strip() if len(txt) > 1 else "XENO"

            def _caption(img):
                out = img.convert("RGB")
                W, H = out.size
                draw = ImageDraw.Draw(out)
                try:
                    font = ImageFont.truetype(
                        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                        max(28, W // 20),
                    )
                except Exception:
                    font = ImageFont.load_default()
                box = draw.textbbox((0, 0), text, font=font)
                tw, th = box[2] - box[0], box[3] - box[1]
                banner = Image.new("RGB", (W, th + 40), "black")
                ImageDraw.Draw(banner).text(
                    ((W - tw) // 2, 20 - box[1]), text, fill="white", font=font
                )
                merged = Image.new("RGB", (W, H + banner.height))
                merged.paste(out, (0, 0))
                merged.paste(banner, (0, H))
                return merged

            return await _run_effect(event, "✍️ Captioned", _caption)

        @_c("grayscale")
        async def grayscale_cmd(event):
            """Convert replied image to grayscale."""
            return await _run_effect(
                event, "⬜ Grayscale", lambda i: i.convert("L").convert("RGB")
            )

        @_c("invert")
        async def invert_cmd(event):
            """Invert colors of replied image."""
            # ImageOps.invert returns a NEW image; the original is untouched.
            return await _run_effect(
                event, "🌀 Inverted", lambda i: ImageOps.invert(i.convert("RGB"))
            )

        @_c("blur")
        async def blur_cmd(event):
            """Blur replied image."""
            return await _run_effect(
                event, "🌫 Blurred",
                lambda i: i.convert("RGB").filter(ImageFilter.GaussianBlur(6)),
            )

        @_c("brighten")
        async def brighten_cmd(event):
            """Brighten replied image."""
            return await _run_effect(
                event, "✨ Brightened",
                lambda i: ImageEnhance.Brightness(i.convert("RGB")).enhance(1.4),
            )

        @_c("contrast")
        async def contrast_cmd(event):
            """Increase contrast of replied image."""
            return await _run_effect(
                event, "🎚 Contrast",
                lambda i: ImageEnhance.Contrast(i.convert("RGB")).enhance(1.5),
            )

        @_c("crop")
        async def crop_cmd(event):
            """Crop replied image to center square."""

            def _crop(img):
                out = img.convert("RGB")
                W, H = out.size
                s = min(W, H)
                return out.crop(
                    ((W - s) // 2, (H - s) // 2, (W - s) // 2 + s, (H - s) // 2 + s)
                )

            return await _run_effect(event, "✂️ Cropped", _crop)

        @_c("rotate90")
        async def rotate90_cmd(event):
            """Rotate replied image 90° clockwise."""
            return await _run_effect(
                event, "🔄 Rotated", lambda i: i.convert("RGB").rotate(-90, expand=True)
            )

        @_c("circle")
        async def circle_cmd(event):
            """Circle-mask replied image."""

            def _circle(img):
                out = img.convert("RGB")
                s = min(out.size)
                out = out.crop((0, 0, s, s)).resize((512, 512))
                mask = Image.new("L", (512, 512), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, 512, 512), fill=255)
                canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
                canvas.paste(out, (0, 0), mask)
                return canvas

            return await _run_effect(event, "⭕ Circular", _circle, fmt="PNG")

    _register()


@command("color")
async def color_cmd(event):
    """Generate a solid color image. Usage: `.color <hex>` e.g. `.color ff0000`"""
    if not HAVE_PIL:
        return await event.eor("Pillow isn't installed, so image tools are off.")
    a = event.text.split(maxsplit=1)
    hx = a[1].strip().lstrip("#") if len(a) > 1 else "5a9cff"
    if len(hx) != 6:
        return await event.eor("Give a 6-digit hex: `.color ff0000`")
    try:
        r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
    except ValueError:
        return await event.eor("Invalid hex.")
    img = Image.new("RGB", (512, 512), (r, g, b))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    await event.eor(f"**🎨 #{hx.upper()}**", file=buf)


@command("img")
async def img_cmd(event):
    """Image search via Bing (free endpoint). Usage: `.img <query>`"""
    a = event.text.split(maxsplit=1)
    q = a[1].strip() if len(a) > 1 else ""
    if not q:
        return await event.eor("Give a query. Usage: `.img <query>`")
    url = f"https://www.bing.com/images/search?q={urllib.parse.quote(q)}&format=rss"
    try:
        txt = await get_text(url)
    except Exception as e:
        return await event.eor(f"Error: `{e}`")
    # Bing's RSS <link> is a result page, not the image file. Prefer the
    # media:content url when present; otherwise just list the pages.
    direct = re.findall(r'<media:content[^>]+url="([^"]+)"', txt)[:3]
    pages = [u.replace("&amp;", "&") for u in re.findall(r"<link>(.*?)</link>", txt)[1:4]]
    if direct:
        return await event.eor(f"**🖼 {q}:**", file=direct[0])
    if pages:
        body = "\n".join(f"• {p}" for p in pages)
        return await event.eor(f"**🖼 {q}:**\n{body}")
    return await event.eor("No images found.")