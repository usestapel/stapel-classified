"""System checks — the composite says at boot what it can and cannot enforce.

The rule these implement is stapel-chat's, learned the expensive way: a
degraded state a deployment can be in *silently* is the defect. So the
block-enforcement posture is printed at every ``manage.py check``, in all
three of its states, and the one that is genuinely broken is an ERROR.
"""
from __future__ import annotations

from django.core import checks


@checks.register(checks.Tags.compatibility)
def check_block_enforcement(app_configs, **kwargs):
    """E001/E002/W001/W002 — can this deployment actually enforce a block?"""
    from . import blocks
    from .conf import classified_settings

    mode = str(classified_settings.BLOCK_ENFORCEMENT or "")
    if mode not in blocks.ENFORCEMENT_MODES:
        return [checks.Error(
            f"STAPEL_CLASSIFIED['BLOCK_ENFORCEMENT'] is {mode!r}; only "
            f"{', '.join(blocks.ENFORCEMENT_MODES)} exist.",
            id="stapel_classified.E001",
        )]

    name = classified_settings.BLOCK_FUNCTION or ""
    if mode == blocks.ENFORCEMENT_OFF:
        return [checks.Warning(
            "STAPEL_CLASSIFIED['BLOCK_ENFORCEMENT'] is 'off': a user who "
            "blocked somebody can still be written to from a listing page. "
            "That is a statement this check exists to make out loud, not a "
            "default anyone drifted into.",
            hint="Set it to 'auto' or 'required' once a block provider is "
                 "reachable.",
            id="stapel_classified.W002",
        )]

    reason = blocks.provider_unreachable_reason()
    if not reason:
        return []
    if mode == blocks.ENFORCEMENT_REQUIRED:
        return [checks.Error(
            f"STAPEL_CLASSIFIED['BLOCK_ENFORCEMENT'] is 'required' and the "
            f"block provider {name!r} cannot be called here: {reason}. Every "
            f"attempt to contact a seller will answer 503.",
            hint="Install the owning module in this process, configure its "
                 "function route for the split topology, or drop the "
                 "posture to 'auto' knowingly.",
            id="stapel_classified.E002",
        )]
    return [checks.Warning(
        f"Blocks are NOT enforced in this deployment: {name!r} cannot be "
        f"called here ({reason}), and BLOCK_ENFORCEMENT is 'auto'. Contact "
        f"between any two users proceeds. stapel-profiles owns the block "
        f"relationship but publishes no comm Function to read it yet — this "
        f"is the state the fleet is in, printed rather than assumed.",
        hint="Set BLOCK_ENFORCEMENT='required' once a provider answers "
             "STAPEL_CLASSIFIED['BLOCK_FUNCTION'], so a missing one is a "
             "boot error instead of an open door.",
        id="stapel_classified.W001",
    )]


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


__all__ = ["check_block_enforcement", "check_card_providers"]
