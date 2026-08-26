"""Sibling modules this suite reaches for, and the one rule about them.

Ported from stapel-chat 0.5.1, which is where the defect class was closed
with a mechanism. Three releases in one night died on the same shape: a test
touched a sibling package that the shared development virtualenv happened to
have installed and that nothing declared, so it passed locally and failed on
a clean runner. This composite is the worst possible place for that — it is
by definition a suite that mounts other people's modules — and 0.3.1's own
publish run proved it: `stapel_chat.consumers` needed `channels`, no file in
this repo said so, and the release died in the test job.

The rule:

1. Every sibling the suite touches — imported OR mounted in INSTALLED_APPS —
   is declared in the ``test`` extra of ``pyproject.toml``
   (``pip install -e ".[test]"``). ``tests/test_test_dependencies.py`` reads
   both and fails if they disagree.
2. Reaching for one in a single test goes through :func:`requires`, never a
   bare module-scope import, so a contributor without the extra gets a named
   skip instead of a collection error.
3. CI sets ``STAPEL_TEST_STRICT_SIBLINGS=1``. In strict mode a missing
   sibling FAILS instead of skipping — on CI the extra is installed, so a
   skip there means the install did not do what the workflow says it does.
"""
from __future__ import annotations

import os
from importlib.util import find_spec

import pytest

#: CI sets this. See rule 3 above.
STRICT = os.environ.get("STAPEL_TEST_STRICT_SIBLINGS", "") == "1"


def installed(module: str) -> bool:
    """Is ``module`` importable here? Never raises, never imports it."""
    try:
        return find_spec(module) is not None
    except (ImportError, ValueError):  # pragma: no cover - defensive
        return False


def requires(module: str, dist: str):
    """Decorator: this test needs the sibling ``module`` (package ``dist``)."""
    if installed(module):
        return lambda func: func

    message = (
        f"{dist} is not installed. It is declared in this package's `test` "
        f'extra — install it with `pip install -e ".[test]"`.'
    )

    if not STRICT:
        return pytest.mark.skip(reason=message)

    def _decorator(func):
        # Deliberately NOT functools.wraps: pytest reads the wrapped
        # signature and would try to build fixtures that themselves need the
        # missing module. A no-argument stub needs nothing.
        def _missing_sibling():
            pytest.fail(
                f"{message} STAPEL_TEST_STRICT_SIBLINGS=1 is set, so this is "
                f"a failure rather than a skip: on CI the extra is installed, "
                f"and a skip here would mean it silently was not."
            )

        _missing_sibling.__name__ = func.__name__
        _missing_sibling.__doc__ = func.__doc__
        return _missing_sibling

    return _decorator


__all__ = ["STRICT", "installed", "requires"]
