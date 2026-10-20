"""XENO crypto module — live prices & market data via CoinGecko (free, no key)."""
from core.command import command
from core.http import get_json

SYMS = {
    "btc": "bitcoin", "eth": "ethereum", "doge": "dogecoin",
    "ltc": "litecoin", "xrp": "ripple", "sol": "solana",
    "ada": "cardano", "bnb": "binancecoin", "dot": "polkadot",
    "matic": "matic-network", "avax": "avalanche-2", "ton": "the-open-network",
    "trx": "tron", "xmr": "monero", "shib": "shiba-inu",
    "link": "chainlink", "atom": "cosmos", "uni": "uniswap",
    "aave": "aave", "near": "near",
}


async def _price(event, slug, sym):
    try:
        d = await get_json(f"https://api.coingecko.com/api/v3/coins/{slug}")
        if not d or "market_data" not in d:
            return await event.eor(f"`{sym}` not found.")
        p = d["market_data"]["current_price"]["usd"]
        ch = d["market_data"].get("price_change_percentage_24h", 0)
        cap = d["market_data"].get("market_cap", {}).get("usd")
        sym = d["symbol"].upper()
        rank = d.get("market_cap_rank", "?")
        arrow = "▲" if ch >= 0 else "▼"
        lines = [
            f"**{d['name']} ({sym})**",
            f"💰 `${p:,.6f}`" if p < 1 else f"💰 `${p:,.2f}`",
            f"📈 24h: {arrow} `{ch:.2f}%`",
            f"🏦 Market cap: `${cap:,.0f}`",
            f"#️⃣ Rank: `#{rank}`",
        ]
        await event.eor("\n".join(lines))
    except Exception as e:
        await event.eor(f"Error: `{e}`")


for _sym, _slug in SYMS.items():
    def _mk(sym, slug):
        async def _handler(event):
            await _price(event, slug, sym)
        _handler.__name__ = f"crypto_{sym}"
        return _handler
    command(_sym)(_mk(_sym, _slug))


@command("price")
async def price_cmd(event):
    """Price of any coin by name. Usage: `.price <coin-slug>` e.g. .price bitcoin"""
    a = event.text.split(maxsplit=1)
    q = a[1].strip().lower() if len(a) > 1 else "bitcoin"
    await _price(event, q, q)


@command("topcoins")
async def topcoins_cmd(event):
    """Top 10 crypto by market cap."""
    try:
        d = await get_json("https://api.coingecko.com/api/v3/coins/markets",
                           {"vs_currency": "usd", "order": "market_cap_desc",
                            "per_page": 10, "page": 1})
        lines = ["**🏆 Top 10 Crypto:**"]
        for i, c in enumerate(d, 1):
            lines.append(f"{i}. **{c['symbol'].upper()}** `${c['current_price']:,.2f}` "
                         f"(24h `{c.get('price_change_percentage_24h', 0):.1f}%`)")
        await event.eor("\n".join(lines))
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("feargreed")
async def feargreed_cmd(event):
    """Crypto Fear & Greed index."""
    try:
        d = await get_json("https://api.alternative.me/fng/")
        data = d["data"][0]
        val = int(data["value"])
        label = data["value_classification"]
        bar = "🟢" * (val // 10) + "🔴" * (10 - val // 10)
        await event.eor(f"**😨 Fear & Greed Index:**\n`{val}/100` — *{label}*\n{bar}")
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("ethgas")
async def ethgas_cmd(event):
    """Current Ethereum gas price (Gwei). Needs ETHSCAN_API_KEY in .env."""
    import config

    key = config.get("ETHSCAN_API_KEY", "")
    if not key:
        return await event.eor(
            "⚠️ `ethgas` needs an Etherscan key: set `ETHSCAN_API_KEY=` in .env "
            "(free tier at etherscan.io)."
        )
    try:
        d = await get_json(
            "https://api.etherscan.io/v2/api",
            {
                "chainid": "1",
                "module": "gastracker",
                "action": "gasoracle",
                "apikey": key,
            },
        )
        # V2 returns result as a dict on success and as a string on error.
        r = d.get("result")
        if not isinstance(r, dict):
            return await event.eor(f"Etherscan: `{d.get('message', r)}`")
        await event.eor(
            "**⛽ Ethereum Gas:**\n"
            f"Safe: `{r.get('SafeGasPrice')} Gwei`\n"
            f"Proposed: `{r.get('ProposeGasPrice')} Gwei`\n"
            f"Fast: `{r.get('FastGasPrice')} Gwei`\n"
            f"Base fee: `{r.get('suggestBaseFee')} Gwei`"
        )
    except Exception as e:
        await event.eor(f"Error: `{e}`")