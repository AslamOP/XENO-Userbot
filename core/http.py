"""Shared async HTTP helpers. No external deps beyond aiohttp (already required)."""
import aiohttp


async def get_json(url, params=None, headers=None, timeout=20):
    async with aiohttp.ClientSession() as s:
        async with s.get(url, params=params, headers=headers, timeout=timeout) as r:
            return await r.json(content_type=None)


async def get_text(url, params=None, headers=None, timeout=20):
    async with aiohttp.ClientSession() as s:
        async with s.get(url, params=params, headers=headers, timeout=timeout) as r:
            return await r.text()


async def get_bytes(url, params=None, headers=None, timeout=30):
    async with aiohttp.ClientSession() as s:
        async with s.get(url, params=params, headers=headers, timeout=timeout) as r:
            return await r.read()


async def post_form(url, data=None, headers=None, timeout=20):
    async with aiohttp.ClientSession() as s:
        async with s.post(url, data=data, headers=headers, timeout=timeout) as r:
            return await r.text()