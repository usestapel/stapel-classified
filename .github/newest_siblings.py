#!/usr/bin/env python3
"""Assert that every `stapel-*` sibling really is the newest one in range.

Half (a) of the sibling-range ruling (2026-09-11) says this composite's CI
must install the NEWEST sibling within the declared range. `pip install -U`
alone does not say that, and the first green run of the `newest-siblings` leg
proved it: the job reported success having installed stapel-reviews 0.6.1
while 0.7.0 was on the index and inside the declared `>=0.6,<1.0`. Nothing was
broken — pip had BACKTRACKED, because stapel-shop 0.2.35 (the newest shop on
the index at that minute) still capped `stapel-reviews<0.7`, and a resolver
answers a conflict by choosing an older version, silently, with exit code 0.

That is the whole defect class the ruling exists to close, wearing a green
badge. A gate that cannot tell "the newest sibling works" from "an older
sibling was quietly substituted" measures nothing.

So this script asks the index the question directly, one package at a time and
with `--no-deps`, so that no other package's cap can influence the answer:

    what is the newest version of X that satisfies the range this repo declares?

and compares it against what is actually installed. On a mismatch it hunts
through the installed distributions for the requirement that excludes the
newest version and names it, because "reviews is at 0.6.1, not 0.7.0" is a
symptom and "stapel-shop 0.2.35 requires stapel-reviews<0.7" is the finding.

Run from a repo root, after the environment is installed:

    python .github/newest_siblings.py            # check, exit 1 on a mismatch
    python .github/newest_siblings.py --list     # just print what it resolves
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import tomllib
from importlib.metadata import PackageNotFoundError, distributions
from importlib.metadata import version as installed_version
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version


def canon(name: str) -> str:
    return name.lower().replace("_", "-")


def declared_siblings() -> list[Requirement]:
    """Every `stapel-*` requirement in pyproject.toml, runtime and extras."""
    project = tomllib.loads(Path("pyproject.toml").read_text())["project"]
    groups = [project.get("dependencies") or []]
    groups += list((project.get("optional-dependencies") or {}).values())

    seen: dict[str, Requirement] = {}
    for group in groups:
        for spec in group:
            req = Requirement(spec)
            if canon(req.name).startswith("stapel-"):
                # An extra can repeat a runtime requirement; the ranges are
                # identical by test_sibling_ranges.py, so first wins.
                seen.setdefault(canon(req.name), req)
    return list(seen.values())


def newest_in_range(req: Requirement) -> str | None:
    """The newest version on the index satisfying `req`, ignoring everything else.

    `--no-deps` is the point: it asks pip to resolve exactly one requirement,
    so the answer is a property of the index and this repo's range alone. Any
    other package's cap is deliberately invisible here — comparing this number
    against what a full resolve actually installed is how a backtrack becomes
    visible at all.
    """
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        proc = subprocess.run(
            [
                sys.executable, "-m", "pip", "install",
                "--dry-run", "--no-deps", "--ignore-installed",
                "--quiet", "--disable-pip-version-check",
                "--report", str(report),
                str(req),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print(f"  ! could not resolve '{req}': {proc.stderr.strip()[:400]}")
            return None
        data = json.loads(report.read_text())
    for item in data.get("install", []):
        meta = item.get("metadata") or {}
        if canon(meta.get("name", "")) == canon(req.name):
            return meta.get("version")
    return None


def who_excludes(name: str, version: str) -> list[str]:
    """Installed distributions whose own requirement forbids `name==version`."""
    culprits = []
    for dist in distributions():
        dist_name = canon(dist.metadata["Name"] or "")
        if dist_name == canon(name):
            continue
        for raw in dist.requires or []:
            try:
                req = Requirement(raw)
            except Exception:  # pragma: no cover - malformed metadata
                continue
            if canon(req.name) != canon(name):
                continue
            if req.marker is not None and not req.marker.evaluate({"extra": ""}):
                continue
            if not req.specifier.contains(version, prereleases=True):
                culprits.append(f"{dist_name} {dist.version} requires '{req}'")
    return culprits


def main() -> int:
    list_only = "--list" in sys.argv
    problems: list[str] = []
    unknown: list[str] = []

    print(f"{'sibling':<20} {'declared range':<22} {'newest in range':<17} installed")
    print("-" * 80)
    for req in sorted(declared_siblings(), key=lambda r: canon(r.name)):
        name = canon(req.name)
        newest = newest_in_range(req)
        try:
            have = installed_version(name)
        except PackageNotFoundError:
            have = None

        print(f"{name:<20} {str(req.specifier):<22} {str(newest):<17} {have}")

        if list_only:
            continue
        if newest is None:
            unknown.append(name)
            continue
        if have is None:
            problems.append(f"{name} is declared but NOT INSTALLED")
            continue
        if Version(have) != Version(newest):
            detail = who_excludes(name, newest) or [
                "no installed distribution forbids it — pip chose an older "
                "version for another reason (a cached wheel, a yanked release, "
                "or a Python-version marker on the newest file)"
            ]
            problems.append(
                f"{name} {have} is installed, but {newest} is the newest inside "
                f"'{req.specifier}'. The resolver backtracked rather than "
                f"failing, so this job would have gone green without testing "
                f"the release it claims to test. Excluded by:\n    "
                + "\n    ".join(detail)
            )

    if list_only:
        return 0

    if unknown:
        print()
        print(
            "newest-siblings: could not ask the index about: "
            + ", ".join(sorted(unknown))
            + " — a check that cannot see the index proves nothing."
        )
        return 1

    if problems:
        print()
        print("newest-siblings: FAILED — not every sibling is the newest in range.")
        for problem in problems:
            print(f"  - {problem}")
        print()
        print(
            "This composite declares a floor and <1.0 on purpose (architect's "
            "ruling, 2026-09-11): the upper bound no longer asserts "
            "compatibility, so THIS JOB has to. Either the capping package "
            "above needs a release that widens it, or — if the cap is a real "
            "finding about a leaf library that genuinely calls the moved "
            "surface — that is the answer, and it belongs in that library."
        )
        return 1

    print()
    print("newest-siblings: every declared sibling is the newest release in range.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
