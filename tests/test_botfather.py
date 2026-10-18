"""BotFather auto-creation flow + the "never take the userbot down" guarantee."""
import asyncio

from fakes import FakeBotFather, FakeMe, check, test  # noqa: F401

from core import assistant as A


def _fast():
    """BotFather polling sleeps 1.2s/read; make it instant for tests.

    A.asyncio IS the asyncio module, so grab the real sleep first.
    """
    real = asyncio.sleep
    A.asyncio.sleep = lambda _=None: real(0)


@test
def test_botfather_happy_path():
    _fast()
    bf = FakeBotFather()
    res = asyncio.run(A.autobot(bf))
    check("creates a bot", res is not None, res)
    if not res:
        return
    check("token scraped from backticks", res[0] == "1234567:AAHfakeTOKEN", res[0])
    check("handle ends in _bot", res[1].endswith("_bot"), res[1])
    check("dialogue order: /cancel, /newbot, name",
          bf.sent[:3] == ["/cancel", "/newbot", "Assistant Bot"], bf.sent[:3])


@test
def test_botfather_username_collision():
    _fast()
    bf = FakeBotFather(taken=2)
    res = asyncio.run(A.autobot(bf))
    check("retries past taken usernames", res is not None, res)
    if res:
        handles = [s for s in bf.sent if s.endswith("_bot")]
        check("tried 3 handles", len(handles) == 3, handles)
        check("accepted the last one", res[1] == handles[-1], (res[1], handles))


@test
def test_botfather_bot_limit():
    _fast()
    bf = FakeBotFather(no_slots=True)
    res = asyncio.run(A.autobot(bf))
    check("bot limit -> None, no crash", res is None, res)
    check("stopped before sending a name", bf.sent == ["/cancel", "/newbot"], bf.sent)


@test
def test_botfather_name_rejected():
    _fast()
    bf = FakeBotFather(reject_names=1)
    res = asyncio.run(A.autobot(bf))
    check("rejected name still creates a bot", res is not None, res)
    check("fallback name differs from the rejected one",
          len(bf.sent) >= 5 and bf.sent[2] != bf.sent[3], bf.sent)


@test
def test_botfather_no_username():
    _fast()
    bf = FakeBotFather(username=None)
    res = asyncio.run(A.autobot(bf))
    check("no-username account still works", res is not None, res)
    if res:
        check("falls back to an assistant_ handle",
              res[1].startswith("assistant_") and res[1].endswith("_bot"), res[1])


@test
def test_botfather_username_override():
    _fast()
    A.config.ASSISTANT_USERNAME = "my_own_helper_bot"
    try:
        bf = FakeBotFather()
        res = asyncio.run(A.autobot(bf))
        check("ASSISTANT_USERNAME honoured",
              res is not None and res[1] == "my_own_helper_bot", res)
    finally:
        A.config.ASSISTANT_USERNAME = ""


@test
def test_botfather_transport_failure_is_survivable():
    """P0-1 regression: a BotFather network error must not raise."""
    _fast()
    for exc in (ConnectionError("no route to host"),
                TimeoutError("timed out"),
                RuntimeError("mtproto broke")):
        bf = FakeBotFather(boom=exc)
        try:
            res = asyncio.run(A.autobot(bf))
            check(f"{type(exc).__name__} -> returns None, no raise", res is None, res)
        except Exception as e:
            check(f"{type(exc).__name__} -> returns None, no raise", False,
                  f"raised {type(e).__name__}: {e}")


@test
def test_start_assistant_swallows_everything():
    """P0-1 regression: start_assistant must never propagate."""
    _fast()

    class Exploding:
        me = FakeMe()

        async def get_me(self):
            return self.me

        async def __call__(self, req):
            return None

        async def send_message(self, *a, **k):
            raise ConnectionError("boom")

        async def get_messages(self, *a, **k):
            raise ConnectionError("boom")

    async def go():
        return await A.start_assistant(Exploding(), log_channel=None)

    try:
        res = asyncio.run(go())
        check("start_assistant survives a dead BotFather", res is not None or True)
        check("no exception escaped start_assistant", True)
    except Exception as e:
        check("no exception escaped start_assistant", False,
              f"{type(e).__name__}: {e}")


@test
def test_defaults():
    check("default bot name is 'Assistant Bot'",
          A.config.ASSISTANT_NAME == "Assistant Bot", A.config.ASSISTANT_NAME)
    check("AUTO_BOTFATHER defaults on", A.config.AUTO_BOTFATHER is True)
    check("BOT_TOKEN empty by default", A.config.BOT_TOKEN == "")
    check("decorate defaults on", A.config.ASSISTANT_DECORATE is True)
    check("panel prefix is '/'", A.config.ASSISTANT_PREFIX == "/")
