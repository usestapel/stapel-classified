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

The one place DAOs *are* read is ``_title_text``, and since 0.5.0 it reads
one field off them: a code-valued attribute's ``labels`` snapshot. That is not
the DAO path reopened — ``features_title`` is served, it is a DAO list by
contract, and the display half of a code exists nowhere else.
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


#: Attribute types whose stored ``value`` is a list of CODES and whose display
#: half is a separate ``labels`` snapshot on the same DAO.
#:
#: Named here for the same reason listings names them in ``_LIST_VALUE_TYPES``
#: rather than letting them fall through a generic branch — a code is not a
#: word a human ever typed, so a code in the text arm is a chip nobody can
#: read and a query nobody can match.
#:
#: ``ref_select`` / ``ref_hierarchical_select`` have carried the snapshot since
#: stapel-attributes 0.5; ``select`` joins them at 0.7.0, which is the release
#: that stopped a plain select from throwing its option copy away. The set is a
#: statement about the DAO shape, not about where the copy came from: a
#: vocabulary term and an inline option are the same problem for a reader, and
#: on a live board they produced the same symptom — a search whose only match
#: for «б/у» was the two listings that happened to type it in the description,
#: because the index held ``b-u``.
LABEL_SNAPSHOT_TYPES = frozenset({"ref_select", "ref_hierarchical_select", "select"})


def _title_text(payload: dict) -> tuple[str, ...]:
    """Attribute values shown as title chips — weight-B text in the index.

    ``features_title`` is a list of DAOs and ``features_search`` is the
    module's own extraction of the searchable values out of those same DAOs.
    Taking the values from ``features_search`` keeps ONE definition of "what
    is searchable about an attribute" (listings'), instead of re-deriving
    values from DAOs here and letting the two drift.

    **Except for the code-valued types, where the two halves are different
    things on purpose.** A DAO in :data:`LABEL_SNAPSHOT_TYPES` carries
    ``value`` (the codes, which are the filter axis and what
    ``features_search`` serves) AND ``labels`` (the display snapshot taken at
    write time). The chip a person reads on a result row is "iPhone 10", not
    ``iphone-10``, and «Б/у», not ``b-u`` — and the query a person types is the
    label too — so for those types the text arm takes ``labels``. Nothing is
    re-derived: the label snapshot is the owner's, stored beside the codes at
    publish time, and ``features_search`` below still carries the codes
    untouched. Absent ``labels`` — a DAO written before the vocabulary
    answered, or before stapel-attributes 0.7.0 taught ``select`` to snapshot
    at all — falls back to the codes rather than dropping the attribute out of
    the text arm.

    DAO order is the category's own feature order, and it is preserved:
    ``text_extra`` is compared field-by-field in the rebuild-vs-live gate, and
    an order that came out of a set would make that comparison flap.
    """
    daos = [
        dao
        for dao in (payload.get("features_title") or [])
        if isinstance(dao, dict) and dao.get("slug")
    ]
    if not daos:
        return ()
    searchable = payload.get("features_search") or {}

    text: list[str] = []
    for dao in daos:
        values = None
        if str(dao.get("type") or "") in LABEL_SNAPSHOT_TYPES:
            labels = dao.get("labels")
            if isinstance(labels, list) and labels:
                values = labels
        if values is None:
            values = searchable.get(str(dao["slug"])) or []
        text.extend(str(value) for value in values if value not in (None, ""))
    return tuple(text)


def _card(payload: dict) -> dict:
    """What a result row shows, stored with the document.

    A card is not an index axis — it is here so a page of hits costs one
    query and no hydration hop back into listings (search verdict §18.4).
    The display price rides along with ``price_base``: the base value is what
    sorts and filters across currencies, the written price is what a human
    reads.

    The shape comes from ``cards._base_card``, which the conversation header
    also builds on: a search hit and a chat header showing the same listing
    differently would be two answers to one question, and one of them would
    be wrong on the day somebody edited only one of the two builders.
    """
    from .cards import _base_card

    return _base_card(payload)


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
    "LABEL_SNAPSHOT_TYPES",
    "REMOVAL_SIGNALS",
    "SIGNALS",
    "listing_source",
    "map_listing",
]
