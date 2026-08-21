"""The `listing` search source — cross-domain glue, the one thing a composite
is allowed to write (projections-and-composition §3).

stapel-search ships ``BUILTIN_SOURCES = {}`` on purpose: it knows nothing
about listings, and stapel-listings knows nothing about an index. The pair
meets here, in the composite that is allowed to know both sides, exactly the
way ``stapel_shop.projections`` joins listings to reviews.

What the seam is made of:

- ``listings.search_documents`` — keyed batch pull, the live read behind a
  ``listing.*`` signal;
- ``listings.search_export`` — the cursor snapshot behind
  ``manage.py search_rebuild`` / ``search_drift_check``;
- ``listing.published`` / ``listing.updated`` / ``listing.removed`` — the
  invalidation signals. They are *signals*, never documents: their payloads
  are ``additionalProperties: false`` and carry identity only, and the
  document that decides visibility is the one the pull returns.

Both Functions answer from the same builder in listings, so a rebuilt index
and a live-updated one cannot disagree about what a listing looks like. Both
calls are ``call()`` — in-process in this monolith, a bus round trip in a
split deployment, with no change here.

**Declared loss: facets come from ``features_search``, not from DAOs.**
The search spec (§5.3) wants the mapper to hand over full stapel-attributes
DAOs, because ``features_search`` flattens every value to a term: it loses
``hex_color``'s ``simple`` axis, loses unit context, and cannot tell a range
from a term — so ``r.<slug>`` range filters over listing attributes do not
work and every attribute facet counts as a term. ``listings.search_documents``
does not serve the DAO list (``Listing.features`` exists but is not in
``build_search_document``), and inventing a second read path here would be
the "declared but not connected" defect in the seam that exists to prevent
it. The honest wiring is the declared fallback (``ACCEPT_FEATURES_SEARCH``,
on by default); closing it is one field in listings' document builder, and it
is named as such in this composite's CHANGELOG.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

#: comm names, spelled once. The composite never imports the owner module to
#: reach them — a split deployment resolves the same strings over the bus.
CONTENT_FUNCTION = "listings.search_documents"
EXPORT_FUNCTION = "listings.search_export"

#: Identity-only facts that invalidate one key.
SIGNALS = ("listing.published", "listing.updated", "listing.removed")

#: The subset whose meaning is "this key is gone". Still verified by the
#: pull: a key the source no longer serves is the source saying "deleted",
#: and a key it still serves with a non-indexed status is a tombstone.
REMOVAL_SIGNALS = ("listing.removed",)


def _decimal(value: Any) -> Decimal | None:
    """Prices and coordinates ride the wire as strings, never as floats."""
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _datetime(value: Any):
    """ISO 8601 -> aware datetime; anything unparseable is simply absent."""
    if not value:
        return None
    if not isinstance(value, str):
        return value
    from django.utils.dateparse import parse_datetime

    return parse_datetime(value)


def _title_text(payload: dict) -> tuple[str, ...]:
    """Attribute values shown as title chips — weight-B text in the index.

    ``features_title`` is a list of DAOs and ``features_search`` is the
    module's own extraction of the searchable values out of those same DAOs.
    Intersecting them keeps ONE definition of "what is searchable about an
    attribute" (listings'), instead of re-deriving values from DAOs here and
    letting the two drift.
    """
    flagged = {
        str(dao.get("slug"))
        for dao in (payload.get("features_title") or [])
        if isinstance(dao, dict) and dao.get("slug")
    }
    if not flagged:
        return ()
    searchable = payload.get("features_search") or {}
    return tuple(
        str(value)
        for slug in flagged
        for value in (searchable.get(slug) or [])
        if value not in (None, "")
    )


def _card(payload: dict) -> dict:
    """What a result row shows, stored with the document.

    A card is not an index axis — it is here so a page of hits costs one
    query and no hydration hop back into listings (search verdict §18.4).
    The display price rides along with ``price_base``: the base value is what
    sorts and filters across currencies, the written price is what a human
    reads.
    """
    images = payload.get("images") or []
    return {
        "title": payload.get("title") or "",
        "price": payload.get("price"),
        "currency": payload.get("currency") or "",
        "location_label": payload.get("location_label") or "",
        "image": images[0] if images else None,
        "published_at": payload.get("published_at"),
    }


def map_listing(payload: dict):
    """``listings.search_documents`` row -> ``SearchDocumentInput``.

    The payload is whatever the owner serves plus ``key`` (and ``seq`` on a
    snapshot row), which is the contract stapel-search calls the mapper with
    for both the live pull and the rebuild.

    ``category_path`` is deliberately NOT set: stapel-search fills it from
    ``categories.path`` (stapel-categories 0.5.6), and a path guessed here
    would be a second ancestry model living next to the real tree.
    """
    from stapel_search.dto import SearchDocumentInput

    updated_at = _datetime(payload.get("updated_at"))
    seq = payload.get("seq")
    if seq in (None, ""):
        seq = int(updated_at.timestamp() * 1000) if updated_at else 0

    return SearchDocumentInput(
        doc_type="listing",
        doc_key=str(payload.get("key") or ""),
        # Raw, never a boolean baked in here: index membership is the
        # indexer's predicate over `visible_statuses` below.
        status=str(payload.get("status") or ""),
        language=str(payload.get("language") or ""),
        owner_key=str(payload.get("owner_id") or ""),
        category_id=str(payload.get("category_id") or ""),
        title=str(payload.get("title") or ""),
        body=str(payload.get("description") or ""),
        text_extra=_title_text(payload),
        # See the module docstring: the DAO path is not served, so this is
        # the declared lossy fallback and not an oversight.
        features_search=dict(payload.get("features_search") or {}),
        price_base=_decimal(payload.get("price_base")),
        price=_decimal(payload.get("price")),
        currency=str(payload.get("currency") or ""),
        published_at=_datetime(payload.get("published_at")),
        source_updated_at=updated_at,
        lat=_decimal(payload.get("lat")),
        lon=_decimal(payload.get("lon")),
        geohash=str(payload.get("geohash") or ""),
        location_id=str(payload.get("location_id") or ""),
        location_label=str(payload.get("location_label") or ""),
        card=_card(payload),
        seq=int(seq or 0),
    )


def listing_source():
    """The ``SourceSpec`` named by ``STAPEL_SEARCH["SOURCES"]["listing"]``.

    A factory rather than a module-level instance: the settings overlay
    resolves the dotted path and calls it, and ``visible_statuses`` is read
    from stapel-listings so that a lifecycle state added there cannot leave
    the index's idea of "live" behind. That single import is the whole reason
    this glue belongs to a composite and not to either module.
    """
    from stapel_listings.models import INDEXED_STATUSES
    from stapel_search.registry import SourceSpec

    return SourceSpec(
        doc_type="listing",
        mapper=map_listing,
        content_function=CONTENT_FUNCTION,
        export_function=EXPORT_FUNCTION,
        signals=SIGNALS,
        removal_signals=REMOVAL_SIGNALS,
        key_fields=("listing_id", "key"),
        visible_statuses=frozenset(str(status) for status in INDEXED_STATUSES),
    )


__all__ = [
    "CONTENT_FUNCTION",
    "EXPORT_FUNCTION",
    "REMOVAL_SIGNALS",
    "SIGNALS",
    "listing_source",
    "map_listing",
]
