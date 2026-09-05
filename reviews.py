"""The `listing` owner resolver — cross-domain glue (projections-and-composition
§3), the reviews half of what ``search_sources.py`` already is for search.

stapel-reviews is target-generic: it does not know a "listing" has an owner.
This composite is the one place allowed to know both sides, so the
``owner_key_for`` resolver stapel-reviews' registry calls for the ``listing``
target type — ``STAPEL_REVIEWS["TARGET_TYPES"]["listing"]["owner_key_for"]``
in ``preset.py`` — lives HERE, one function, one call to
``listings.status``.
"""
from __future__ import annotations


def listing_owner_key(target_key: str) -> str | None:
    """Who owns listing ``target_key``, or ``None`` — never raises.

    Called by stapel-reviews' ``registry.resolve_owner_key`` with the
    target key as a STRING (the storefront's stringified listing pk, e.g.
    ``"610"``); ``listings.status`` wants an int. ``None`` is a legitimate
    answer there ("no owner"/registry treats it as ``""``), so both a
    non-numeric key and an unknown listing collapse to it rather than
    propagating — ``resolve_owner_key`` does NOT swallow a raise, and a
    listing that is merely gone (deleted between the review and the
    backfill, say) must not abort a caller that only wants a best-effort
    owner key.
    """
    try:
        listing_id = int(target_key)
    except (TypeError, ValueError):
        return None

    from stapel_core.comm import call

    try:
        result = call("listings.status", {"listing_id": listing_id})
    except LookupError:
        return None

    if not isinstance(result, dict):
        return None
    owner_id = result.get("owner_id")
    return str(owner_id) if owner_id is not None else None
