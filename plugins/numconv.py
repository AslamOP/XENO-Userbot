"""XENO numeric & unit series: number-system conversions, unit conversions,
math helpers. Loop-registered original code."""
import math
import random

from core.command import command

# Longest factorial we can print before Python's int->str digit limit (4300) bites.
MAX_FACTORIAL = 1000


# ---- number-system conversions ----
_CONV = {
    "bin2dec": lambda s: str(int(s, 2)),
    "bin2hex": lambda s: hex(int(s, 2)),
    "bin2oct": lambda s: oct(int(s, 2)),
    "dec2bin": lambda s: bin(int(s))[2:],
    "dec2hex": lambda s: hex(int(s))[2:].upper(),
    "dec2oct": lambda s: oct(int(s))[2:],
    "hex2dec": lambda s: str(int(s, 16)),
    "hex2bin": lambda s: bin(int(s, 16))[2:],
    "hex2oct": lambda s: oct(int(s, 16))[2:],
    "oct2dec": lambda s: str(int(s, 8)),
    "oct2bin": lambda s: bin(int(s, 8))[2:],
    "oct2hex": lambda s: hex(int(s, 8))[2:].upper(),
}

for _name, _fn in _CONV.items():
    def _make(name, fn):
        async def _handler(event):
            a = event.text.split(maxsplit=1)
            arg = a[1].strip() if len(a) > 1 else ""
            if not arg:
                return await event.reply(f"Give a value. Usage: `.{name} <value>`")
            try:
                val = fn(arg)
                return await event.reply(f"**{name}:** `{val}`")
            except Exception:
                return await event.reply(f"Invalid input for `.{name}`")
        _handler.__name__ = f"conv_{name}"
        _handler.__doc__ = f"Convert using {name}."
        return _handler
    command(_name)(_make(_name, _fn))


# ---- math helpers ----
@command("math")
async def math_cmd(event):
    """Simple math formatting helpers menu. Run sub-commands: prim, fib, factorial, etc."""
    return await event.reply(
        "**🔢 math helpers:**\n"
        "`prim <n>` prime?  `fib <n>`  `factorial <n>`  `gcd a b`  `lcm a b`\n"
        "`sqrt <n>`  `cbrt <n>`  `powc a b`  `logc <n>`\n"
        "`avg nums...`  `sumc numbers...`  `datastats nums...`  `pct part whole`")


@command("prim")
async def prim_cmd(event):
    a = event.text.split(maxsplit=1)
    arg = a[1] if len(a) > 1 else ""
    try:
        n = int(arg)
    except ValueError:
        return await event.reply("Give an integer.")
    if n < 2:
        return await event.reply(f"`{n}` is not prime.")
    # Trial division is O(sqrt(n)); without a ceiling a big input pins this
    # handler (and its task) indefinitely.
    if n > 10 ** 14:
        return await event.reply(
            f"`{n}` is too large for trial division (limit 10^14). "
            "Use a primality library for numbers this big."
        )
    for i in range(2, int(math.isqrt(n)) + 1):
        if n % i == 0:
            return await event.reply(f"`{n}` is **not** prime (divisible by {i}).")
    return await event.reply(f"`{n}` is **prime** ✅")


@command("fib")
async def fib_cmd(event):
    a = event.text.split(maxsplit=1)
    arg = a[1] if len(a) > 1 else ""
    try:
        n = int(arg)
    except ValueError:
        return await event.reply("Give a count. Usage: `.fib <n>`")
    if n < 1 or n > 1000:
        return await event.reply("n between 1 and 1000.")
    x, y = 0, 1
    seq = []
    for _ in range(n):
        seq.append(x)
        x, y = y, x + y
    return await event.reply(f"**Fibonacci ({n}):**\n{', '.join(map(str, seq))}")


@command("factorial")
async def fact_cmd(event):
    a = event.text.split(maxsplit=1)
    arg = a[1] if len(a) > 1 else ""
    try:
        n = int(arg)
    except ValueError:
        return await event.reply(f"Give an integer. Usage: `.factorial <n>` (0-{MAX_FACTORIAL})")
    if n < 0 or n > MAX_FACTORIAL:
        return await event.reply(f"n between 0 and {MAX_FACTORIAL}.")
    r = math.factorial(n)
    if len(str(r)) > 3500:
        return await event.reply(f"`{n}!` has {len(str(r))} digits — too long to send.")
    return await event.reply(f"**{n}!** = `{r}`")


def _two_ints(event):
    """Return (x, y) on success or (None, None) on bad input."""
    a = event.text.split()
    try:
        return int(a[1]), int(a[2])
    except (IndexError, ValueError):
        return None, None


@command("gcd")
async def gcd_cmd(event):
    x, y = _two_ints(event)
    if x is None:
        return await event.reply("Give two integers. Usage: `.gcd 12 18`")
    return await event.reply(f"**gcd({x},{y})** = `{math.gcd(x, y)}`")


@command("lcm")
async def lcm_cmd(event):
    a, b = _two_ints(event)
    if a is None:
        return await event.reply("Give two integers. Usage: `.lcm 4 6`")
    if a == 0 or b == 0:
        return await event.reply("lcm is 0 when either value is 0.")
    return await event.reply(f"**lcm({a},{b})** = `{abs(a * b) // math.gcd(a, b)}`")


@command("sqrt")
async def sqrt_cmd(event):
    a = event.text.split(maxsplit=1)
    arg = a[1] if len(a) > 1 else ""
    try:
        n = float(arg)
    except ValueError:
        return await event.reply("Give a number.")
    if n < 0:
        return await event.reply("sqrt requires a non-negative number.")
    return await event.reply(f"√{n} = `{math.sqrt(n):.6f}`")


@command("cbrt")
async def cbrt_cmd(event):
    a = event.text.split(maxsplit=1)
    arg = a[1] if len(a) > 1 else ""
    try:
        n = float(arg)
    except ValueError:
        return await event.reply("Give a number.")
    r = math.copysign(abs(n) ** (1 / 3), n)
    return await event.reply(f"∛{n} = `{r:.6f}`")


@command("powc")
async def powc_cmd(event):
    a = event.text.split()
    try:
        x, y = float(a[1]), float(a[2])
    except Exception:
        return await event.reply("Usage: `.powc <base> <exp>`")
    return await event.reply(f"`{x}^{y}` = `{x ** y:g}`")


@command("logc")
async def logc_cmd(event):
    a = event.text.split(maxsplit=1)
    arg = a[1] if len(a) > 1 else ""
    try:
        n = float(arg)
    except ValueError:
        return await event.reply("Give a number > 0.")
    if n <= 0:
        return await event.reply("log requires positive number.")
    return await event.reply(f"ln({n}) = `{math.log(n):.6f}`\nlog10({n}) = `{math.log10(n):.6f}`")


@command("avg")
async def avg_cmd(event):
    a = event.text.split()
    try:
        nums = [float(x) for x in a[1:]]
    except Exception:
        return await event.reply("Give numbers: `.avg 1 2 3 4`")
    if not nums:
        return await event.reply("Give numbers: `.avg 1 2 3`")
    return await event.reply(f"**Average** of `{', '.join(map(str, nums))}` = `{sum(nums)/len(nums):.4f}`")


@command("sumc")
async def sumc_cmd(event):
    a = event.text.split()
    try:
        nums = [float(x) for x in a[1:]]
    except Exception:
        return await event.reply("Give numbers: `.sumc 1 2 3`")
    if not nums:
        return await event.reply("Give numbers.")
    return await event.reply(f"**Sum** = `{sum(nums):g}`")


@command("pct")
async def pct_cmd(event):
    a = event.text.split()
    try:
        part, whole = float(a[1]), float(a[2])
    except Exception:
        return await event.reply("Usage: `.pct <part> <whole>`")
    if whole == 0:
        return await event.reply("Whole can't be 0.")
    return await event.reply(f"`{part}` is **{part/whole*100:.2f}%** of `{whole}`")


@command("datastats")
async def stats_cmd(event):
    a = event.text.split()
    try:
        nums = [float(x) for x in a[1:]]
    except Exception:
        return await event.reply("Give numbers: `.stats 1 2 3`")
    if not nums:
        return await event.reply("Give numbers.")
    mean = sum(nums) / len(nums)
    srt = sorted(nums)
    if len(nums) % 2 == 0:
        med = (srt[len(nums)//2-1] + srt[len(nums)//2]) / 2
    else:
        med = srt[len(nums)//2]
    vari = sum((x - mean) ** 2 for x in nums) / len(nums)
    return await event.reply(
        f"**Stats:**\nCount: `{len(nums)}`\nSum: `{sum(nums):g}`\n"
        f"Mean: `{mean:.4f}`\nMedian: `{med:.4f}`\n"
        f"Min: `{min(nums):g}`  Max: `{max(nums):g}`\n"
        f"Variance: `{vari:.4f}`")


# ---- unit conversions ----
_UNITS = {
    "km2miles": lambda v: v * 0.621371,
    "miles2km": lambda v: v * 1.609344,
    "m2feet": lambda v: v * 3.28084,
    "feet2m": lambda v: v / 3.28084,
    "cm2inch": lambda v: v / 2.54,
    "inch2cm": lambda v: v * 2.54,
    "kg2lb": lambda v: v * 2.204623,
    "lb2kg": lambda v: v / 2.204623,
    "g2oz": lambda v: v / 28.349523,
    "oz2g": lambda v: v * 28.349523,
    "c2f": lambda v: v * 9 / 5 + 32,
    "f2c": lambda v: (v - 32) * 5 / 9,
    "c2k": lambda v: v + 273.15,
    "k2c": lambda v: v - 273.15,
    "l2gal": lambda v: v / 3.785411784,
    "gal2l": lambda v: v * 3.785411784,
    "l2ml": lambda v: v * 1000,
    "ml2l": lambda v: v / 1000,
    "kmh2mph": lambda v: v / 1.609344,
    "mph2kmh": lambda v: v * 1.609344,
    "ms2kmh": lambda v: v * 3.6,
    "kmh2ms": lambda v: v / 3.6,
    "ha2acre": lambda v: v * 2.471054,
    "acre2ha": lambda v: v / 2.471054,
    "pa2bar": lambda v: v / 100000,
    "bar2pa": lambda v: v * 100000,
    "kw2hp": lambda v: v * 1.341022,
    "hp2kw": lambda v: v / 1.341022,
    "j2cal": lambda v: v / 4.184,
    "cal2j": lambda v: v * 4.184,
}

for _uname, _ufn in _UNITS.items():
    def _umake(name, fn):
        async def _uhandler(event):
            a = event.text.split(maxsplit=1)
            arg = a[1].strip() if len(a) > 1 else ""
            if not arg:
                return await event.reply(f"Give a value. Usage: `.{name} <value>`")
            try:
                v = float(arg)
                return await event.reply(f"**{name}:** `{v}` → `{fn(v):g}`")
            except ValueError:
                return await event.reply("Give a numeric value.")
        _uhandler.__name__ = f"unit_{name}"
        _uhandler.__doc__ = f"Convert value via {name}."
        return _uhandler
    command(_uname)(_umake(_uname, _ufn))


@command("units")
async def units_cmd(event):
    """List unit converters. Usage: `.units`"""
    names = ", ".join(sorted(_UNITS.keys()))
    return await event.reply(f"**📐 Unit converters:**\n`{names}`")


@command("conv")
async def conv_cmd(event):
    """Generic quick converter menu. Usage: `.conv`"""
    return await event.reply(
        "**🔁 Converters:**\n"
        "`km2miles miles2km m2feet feet2m cm2inch inch2cm`\n"
        "`kg2lb lb2kg g2oz oz2g c2f f2c c2k k2c l2gal gal2l`\n"
        "`kmh2mph mph2kmh ms2kmh kmh2ms ha2acre acre2ha`\n"
        "`pa2bar bar2pa kw2hp hp2kw j2cal cal2j`")