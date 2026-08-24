"""Block enforcement, at the one place a classified conversation begins.

A user-to-user block is **not** a classified concept and this module does not
own one. stapel-profiles has owned it since 0.4.x — ``UserRelationship`` with
a ``blocked`` status, ``POST /profiles/api/v1/<user_id>/block``, and a
``me/blocked`` list. What the fleet has never had is a way for a *server* to
consult it: profiles publishes four comm Functions and none of them answers
"is there a block between these two", so every block in the fleet is enforced
by a client hiding a button. That is the routed upstream ask (MODULE.md), and
this file is the classified half of it.

The posture, and why it is an axis rather than a constant
--------------------------------------------------------
stapel-chat's founding lesson is that a *silent* fallback is the defect: a
product polled for months because a socket seam failed quietly into its
degraded half. The answer is not "never degrade" — it is "never degrade
silently". So:

- the provider is registered → every contact is checked, and a check that
  RAISES answers 503. An outage is not consent;
- the provider is not registered at all → this deployment has no block
  store, and ``manage.py check`` says so at every boot (W001). Refusing every
  contact instead would take a marketplace offline over a function nobody in
  the fleet has written yet;
- a deployment that runs stapel-profiles sets ``BLOCK_ENFORCEMENT`` to
  ``"required"`` and the missing provider becomes a boot ERROR (E002).

The default flips to ``"required"`` in the first release after profiles ships
the function — recorded in MODULE.md as a follow-up, not left to memory.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

ENFORCEMENT_AUTO = "auto"
ENFORCEMENT_REQUIRED = "required"
ENFORCEMENT_OFF = "off"
ENFORCEMENT_MODES = (ENFORCEMENT_AUTO, ENFORCEMENT_REQUIRED, ENFORCEMENT_OFF)


class BlockCheckUnavailable(Exception):
    """The block store is configured and could not be asked (→ 503)."""


def provider_unreachable_reason() -> str:
    """Why the configured block Function cannot be called here, or ``""``.

    Delegates to core's own probe, which is honest about what it cannot
    prove: over a bus transport nothing at boot can establish that a remote
    provider is up, and it says so instead of asserting.
    """
    from stapel_core.comm import function_unreachable_reason

    from .conf import classified_settings

    name = classified_settings.BLOCK_FUNCTION or ""
    if not name:
        return "no BLOCK_FUNCTION configured"
    return function_unreachable_reason(name) or ""


def blocked_pairs(pairs) -> set:
    """Ask the provider which of ``pairs`` are blocked in EITHER direction.

    Returns a set of frozensets, so a caller never has to remember which way
    round it asked. Raises :class:`BlockCheckUnavailable` when the provider
    is configured, registered and then fails — the one case that must not
    read as "allowed".
    """
    from stapel_core.comm import call

    from .conf import classified_settings

    mode = str(classified_settings.BLOCK_ENFORCEMENT or ENFORCEMENT_AUTO)
    if mode == ENFORCEMENT_OFF:
        return set()

    wanted = [
        [str(a), str(b)]
        for a, b in pairs
        if str(a) and str(b) and str(a) != str(b)
    ]
    if not wanted:
        return set()

    name = classified_settings.BLOCK_FUNCTION or ""
    unreachable = provider_unreachable_reason()
    if unreachable:
        if mode == ENFORCEMENT_REQUIRED:
            # Declared required and not there: the deployment is broken and
            # says so, rather than letting a blocked stranger through.
            raise BlockCheckUnavailable(unreachable)
        # "auto": no block store in this deployment. Announced at boot by
        # checks.W001 — this is never the first time anyone hears it.
        return set()

    try:
        answer = call(
            name,
            {"pairs": wanted},
            timeout=float(classified_settings.CALL_TIMEOUT_SECONDS),
        )
    except Exception as exc:  # noqa: BLE001 — an outage is not consent
        logger.warning("classified: block check via %r failed: %s", name, exc)
        raise BlockCheckUnavailable(str(exc)) from exc

    blocked = (answer or {}).get("blocked") or []
    return {frozenset((str(a), str(b))) for a, b in blocked if a and b}


def is_blocked(user_a, user_b) -> bool:
    """Whether a block exists between two users, in either direction.

    Direction is deliberately not reported to the caller and never to the
    client: telling the blocked party "they blocked you" turns a quiet
    boundary into a notification. The refusal a user sees is the same one
    they would see if the listing had been withdrawn.
    """
    return frozenset((str(user_a), str(user_b))) in blocked_pairs([(user_a, user_b)])


__all__ = [
    "ENFORCEMENT_AUTO",
    "ENFORCEMENT_MODES",
    "ENFORCEMENT_OFF",
    "ENFORCEMENT_REQUIRED",
    "BlockCheckUnavailable",
    "blocked_pairs",
    "is_blocked",
    "provider_unreachable_reason",
]
