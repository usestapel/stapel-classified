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


@checks.register(checks.Tags.compatibility)
def check_moderation_gate_agreement(app_configs, **kwargs):
    """E004 — the two halves of the moderation-gate policy must agree.

    The policy is spelled twice because each module owns its own half:
    stapel-moderation's per-target ``gate`` says what the QUEUE believes
    ("pre": nothing is public before my verdict), stapel-listings'
    ``MODERATION_GATE`` says what publish actually DOES. Two settings that
    can disagree is how one half publishes immediately while the other half
    still gates: listings post / moderation pre puts live content in front
    of a queue that believes it is screening drafts; listings pre /
    moderation post holds every first publication in ``pending`` for a
    verdict the policy says nothing should wait for — on a moderator-less
    stand, forever. An ERROR because both directions are silent at runtime:
    every component is green in isolation, and only the seam is wrong.

    This check is also what makes moderation's ``gate`` key non-inert for
    the listing target: until it, nothing consumed the declaration at all.
    """
    from stapel_listings.conf import listings_settings
    from stapel_moderation.registry import UnknownTargetType, resolve_policy

    target_type = listings_settings.MODERATION_TARGET_TYPE
    try:
        moderation_gate = resolve_policy(target_type)["gate"]
    except UnknownTargetType:
        # No policy registered for the listing target at all — that is the
        # three-name alignment defect, owned elsewhere (a consumer whose
        # name is absent from the registry never gets a verdict); a gate
        # comparison against a missing policy would only shout twice.
        return []

    # An installed stapel-listings older than 0.13.3 has no MODERATION_GATE
    # default and consumes no such key: whatever the host declares, that lib
    # gates "pre". Reading the declared value through AppSettings would
    # report the value nothing is reading, so the DEFAULTS table — what the
    # installed code actually consults — is the authority on whether the
    # knob exists.
    if "MODERATION_GATE" in listings_settings.defaults:
        listings_gate = listings_settings.MODERATION_GATE
    else:
        listings_gate = "pre"

    # A value outside {pre, post} is its owner's enum check
    # (stapel_listings.E001 / stapel_moderation.E003); comparing garbage
    # here would report the same mistake twice under a misleading name.
    valid = ("pre", "post")
    if moderation_gate not in valid or listings_gate not in valid:
        return []
    if moderation_gate == listings_gate:
        return []
    if listings_gate == "post":
        doing = "publishes first publications immediately"
    else:
        doing = "holds every first publication in pending for a verdict"
    return [
        checks.Error(
            f"Moderation-gate policy disagrees with itself: "
            f"STAPEL_MODERATION's policy for target type {target_type!r} "
            f"declares gate={moderation_gate!r} while "
            f"STAPEL_LISTINGS['MODERATION_GATE'] is {listings_gate!r}. "
            f"Listings {doing} while the queue believes the "
            f"{moderation_gate!r} model — a seam defect that is invisible "
            f"in either module alone.",
            hint="Set both to the same value: 'pre' (nothing public before "
                 "the verdict) or 'post' (publish first, review after; a "
                 "rejecting verdict takes the listing down). The preset "
                 "ships pre/pre.",
            id="stapel_classified.E004",
        )
    ]


__all__ = [
    "MOVED_KEYS",
    "check_block_keys_moved",
    "check_card_providers",
    "check_moderation_gate_agreement",
]
