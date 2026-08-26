"""The gate that stops a green suite here from being a red one on a runner.

A fix for a defect class, not for one import. 0.3.1 was tagged, its suite was
green in the shared development virtualenv, and the publish job died: the
harness mounts ``stapel_chat``, chat's deployment checks import
``stapel_chat.consumers``, that needs ``channels``, and no file in this repo
said so. Same night, same shape as stapel-core 0.44.0, stapel-chat 0.5.0 and a
stapel-tools nav-manifest test. The mechanism is stapel-chat 0.5.1's, ported.

**With one thing added, because a composite is the worst case for this.** The
chat gate collects what the suite IMPORTS. A composite's suite mostly does not
import its siblings — it MOUNTS them, as strings in ``INSTALLED_APPS``, and a
string is invisible to an import scan. ``stapel_profiles`` and
``stapel_realtime`` are in this harness exactly that way. So string constants
naming a ``stapel_*`` package count too: it is the same declaration and the
same failure on a clean runner.
"""
from __future__ import annotations

import ast
import pathlib
import re
import tomllib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_PYPROJECT = _ROOT / "pyproject.toml"

#: This package itself.
_SELF_MODULE = "stapel_classified"


def _suite_files() -> list[pathlib.Path]:
    """The suite is these files. ``conftest.py`` sits outside ``tests/`` and is
    where every mount lives, so it is very much in scope."""
    files = sorted((_ROOT / "tests").glob("*.py"))
    files.append(_ROOT / "conftest.py")
    # This file and its helper TALK about sibling packages; scanning their own
    # string constants would make the gate report itself.
    skip = {"test_test_dependencies.py", "siblings.py"}
    return [f for f in files if f.exists() and f.name not in skip]


def _dist_name(module: str) -> str:
    """``stapel_moderation`` -> ``stapel-moderation``."""
    return module.replace("_", "-")


def _needed_stapel_modules() -> dict[str, set[str]]:
    """``{top-level stapel module: {files that need it}}``.

    Imports at any depth — inside functions, fixtures and ``try`` blocks,
    which is where the ones that bit the fleet were hiding — plus string
    constants naming a package, which is how a Django app is mounted.
    """
    found: dict[str, set[str]] = {}

    def _note(name: str, path: pathlib.Path) -> None:
        top = name.split(".")[0]
        if top.startswith("stapel_") and top != _SELF_MODULE and top.isidentifier():
            found.setdefault(top, set()).add(path.name)

    for path in _suite_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _note(alias.name, path)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                _note(node.module, path)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                # "stapel_realtime", "stapel_core.django.users" — a mount is a
                # dependency that no import scan can see.
                _note(node.value, path)
    return found


def _declared() -> tuple[set[str], set[str]]:
    """``(runtime distributions, test-extra distributions)``, names only."""
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    project = data["project"]

    def _names(specs) -> set[str]:
        out = set()
        for spec in specs or []:
            name = re.split(r"[\[<>=!~;\s]", spec, maxsplit=1)[0].strip()
            if name:
                out.add(name)
        return out

    runtime = _names(project.get("dependencies"))
    extras = project.get("optional-dependencies") or {}
    return runtime, _names(extras.get("test"))


def test_every_sibling_the_suite_needs_is_declared():
    """The gate. A test may mount or import any sibling it likes — and must
    say so. "It works in my venv" is not a dependency declaration, and the
    shared development virtualenv of this fleet has every module installed,
    so it can never be the thing that tells us. ``pyproject.toml`` is."""
    runtime, test_extra = _declared()
    declared = runtime | test_extra

    undeclared = {
        module: sorted(files)
        for module, files in _needed_stapel_modules().items()
        if _dist_name(module) not in declared
    }

    assert not undeclared, (
        "These sibling packages are needed by the test suite and declared "
        "nowhere, so CI installs a runner without them and the suite errors "
        "at setup: "
        + "; ".join(
            f"{_dist_name(m)} (needed by {', '.join(f)})"
            for m, f in sorted(undeclared.items())
        )
        + ". Add each to [project.optional-dependencies].test in "
        "pyproject.toml — or stop needing it."
    )


def test_the_test_extra_declares_nothing_the_suite_does_not_use():
    """The other direction, so the extra cannot rot into a wish list.

    Only siblings are checked: pytest, channels and daphne are the harness,
    not modules under contract with this one.
    """
    runtime, test_extra = _declared()
    needed = {_dist_name(m) for m in _needed_stapel_modules()}

    stale = {
        dist
        for dist in test_extra
        if dist.startswith("stapel-") and dist not in needed and dist not in runtime
    }

    assert not stale, (
        "The `test` extra declares sibling packages nothing in the suite "
        f"needs: {sorted(stale)}. Remove them, or the extra stops describing "
        "anything."
    )


@pytest.mark.parametrize("module", sorted(_needed_stapel_modules()))
def test_a_declared_sibling_is_actually_importable_here(module):
    """Locally a reminder; on CI (``STAPEL_TEST_STRICT_SIBLINGS=1``) the
    assertion that the workflow installed what it claims to.

    Without it the ``test`` extra could go missing from the CI step and the
    only symptom would be a handful of quiet skips in a green run — the second
    face of this same defect class.
    """
    from .siblings import STRICT, installed

    if installed(module):
        return
    if STRICT:
        pytest.fail(
            f"{_dist_name(module)} is declared and not installed, with "
            "STAPEL_TEST_STRICT_SIBLINGS=1 set. The CI step that installs "
            "the `test` extra did not do what the workflow says it does."
        )
    pytest.skip(f"{_dist_name(module)} not installed: `pip install -e '.[test]'`")
