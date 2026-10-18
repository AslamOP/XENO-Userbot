#!/usr/bin/env python3
"""XENO test runner — no pytest, no network.

    python tests/run.py            # everything
    python tests/run.py panel      # one module
"""
import importlib
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.chdir(os.path.dirname(HERE))

from fakes import _RESULTS, check  # noqa: E402

MODULES = ["test_botfather", "test_panel", "test_custom_plugins",
           "test_temp_and_files", "test_files", "test_plugins"]


def main():
    wanted = sys.argv[1:] or MODULES
    tests = []
    for name in wanted:
        try:
            mod = importlib.import_module(name)
        except Exception:
            print(f"\n!! could not import {name}")
            traceback.print_exc()
            _RESULTS.append((f"import {name}", False, "import error"))
            continue
        for attr in sorted(vars(mod)):
            fn = getattr(mod, attr)
            if callable(fn) and getattr(fn, "_is_test", False):
                tests.append((name, attr, fn))

    print(f"running {len(tests)} tests from {len(wanted)} module(s)\n")
    failed_mods = []
    for modname, tname, fn in tests:
        before = len(_RESULTS)
        try:
            fn()
        except Exception as e:
            check(f"{modname}.{tname} (crashed)", False,
                  f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}")
        new = _RESULTS[before:]
        bad = [r for r in new if not r[1]]
        status = "FAIL" if bad else "ok"
        print(f"  {status:4s} {modname}.{tname}  ({len(new)} checks)")
        if bad:
            failed_mods.append(f"{modname}.{tname}")

    passed = sum(1 for r in _RESULTS if r[1])
    failed = [r for r in _RESULTS if not r[1]]

    print(f"\n{'=' * 62}")
    if failed:
        print(f"{passed} passed, {len(failed)} FAILED\n")
        for name, _, detail in failed:
            print(f"  FAIL  {name}")
            if detail:
                print(f"        {detail}")
    else:
        print(f"all {passed} checks passed")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
