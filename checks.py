"""System checks — the composite says at boot what it can and cannot enforce.

The rule these implement is stapel-chat's, learned the expensive way: a
degraded state a deployment can be in *silently* is the defect.

Block enforcement is no longer among them. Since 0.4.0 the posture lives on
stapel-chat's axis and nowhere else, and chat announces all three of its
states itself (``stapel_chat.W003`` / ``E017`` / ``W004``). What is left here
is the transitional check that keeps the move from being silent for anyone
who declared the old keys.
"""
from __future__ import annotations

from django.core import checks

#: Keys this namespace carried until 0.4.0, and where they went. AppSettings
#: cannot complain about a dead key inside a namespace dict — its own
#: conf_checks only see environment variables — so a deployment that declared
#: a posture here would go on declaring it into nothing.
MOVED_KEYS = {
    "BLOCK_ENFORCEMENT": "STAPEL_CHAT['BLOCK_ENFORCEMENT']",
    "BLOCK_FUNCTION": "STAPEL_CHAT['BLOCK_FUNCTION']",
}


@checks.register(checks.Tags.compatibility)
def check_block_keys_moved(app_configs, **kwargs):
    """E003 — a block key still declared here decides nothing any more.

    An ERROR rather than a warning because the failure mode is a *lowered*
    posture that silently stops applying: a deployment with
    ``STAPEL_CLASSIFIED = {"BLOCK_ENFORCEMENT": "off"}`` inherits chat's
    ``auto`` after the upgrade and nothing tells it.
    """
    from django.conf import settings

    namespace = getattr(settings, "STAPEL_CLASSIFIED", None)
    if not isinstance(namespace, dict):
        return []
    return [
        checks.Error(
            f"STAPEL_CLASSIFIED[{key!r}] moved to {new} in "
            f"stapel-classified 0.4.0 and nothing reads it here any more, so "
            f"the posture declared in it is NOT being applied. stapel-chat "
            f"owns both doors a block has to hold — opening a direct thread "
            f"and sending into one — and reads only its own namespace.",
            hint=f"Move the value to {new} and delete it here. This "
                 f"composite's preset already sets "
                 f"STAPEL_CHAT['BLOCK_ENFORCEMENT'] = 'required'; a "
                 f"deployment that knowingly lowered the posture must lower "
                 f"it there instead.",
            id="stapel_classified.E003",
        )
        for key, new in MOVED_KEYS.items()
        if key in namespace
    ]


@checks.register(checks.Tags.compatibility)
def check_card_providers(app_configs, **kwargs):
    """W003 — the listing document function is what every card is built on.

    Unlike the enrichments (CDN metadata, rating, public profile), which
    degrade a card, this one decides whether there is a card at all. Probed
    only where core can prove the answer; over a bus transport the check
    stays quiet rather than crying wolf.
    """
    from stapel_core.comm import function_unreachable_reason

    from .conf import classified_settings

    name = classified_settings.LISTING_DOCUMENTS_FUNCTION or ""
    if not name:
        return [checks.Warning(
            "STAPEL_CLASSIFIED['LISTING_DOCUMENTS_FUNCTION'] is empty: every "
            "conversation header will render as 'listing unavailable'.",
            id="stapel_classified.W003",
        )]
    reason = function_unreachable_reason(name)
    if not reason:
        return []
    return [checks.Warning(
        f"The listing document function {name!r} cannot be called here: "
        f"{reason}. Conversation headers will render as 'temporarily "
        f"unavailable' — the honest degradation, but not a working product.",
        hint="Install stapel-listings in this process, or configure the "
             "function route for the split topology.",
        id="stapel_classified.W003",
    )]


__all__ = ["MOVED_KEYS", "check_block_keys_moved", "check_card_providers"]
