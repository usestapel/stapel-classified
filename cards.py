"""The short listing card and the public seller card — cross-domain reads.

Both are assembled from comm Functions the members already serve. Nothing
here queries a member's ORM and nothing here imports one: the composite is
allowed to know that listings and profiles exist, not to reach into them.

Three properties are load-bearing and easy to lose:

1. **A card answers for a listing that is gone.** ``listings.search_documents``
   serves every status, and a key it does not serve is a listing that was
   deleted. The public read path (``Listing.visible_to``) 404s anything that
   is not published — which is correct for a stranger and useless for the
   person standing in the conversation about it, who is *most* confused
   exactly when the thing is sold or withdrawn. So the card has a
   ``state`` of its own: ``available`` / ``unavailable`` / ``gone``.
2. **Degradation is data.** Every enrichment (CDN render metadata, rating,
   public profile fields) may be unreachable; each card then carries
   ``meta_status`` (``ok`` / ``partial``) and ``meta_reason`` naming what is
   missing. A conversation must never fail to open because a rating service
   blinked — the stapel-chat attachment rule, applied to the same class of
   problem.
3. **One definition of "the card".** ``search_sources`` stores a card with
   every search document; this module builds the chat card. They come from
   the same ``_base_card`` so a price formatted one way in a search hit and
   another way in a chat header is impossible.
"""
from __future__ import annotations

import logging
from typing import Iterable

logger = logging.getLogger(__name__)

#: Statuses in which a listing is live. Read from stapel-listings rather than
#: copied, for the same reason ``search_sources.listing_source`` reads it: a
#: lifecycle state added upstream must not leave this module's idea of "live"
#: behind. Imported lazily — the app registry has to be up.
def _indexed_statuses() -> frozenset:
    from stapel_listings.models import INDEXED_STATUSES

    return frozenset(str(status) for status in INDEXED_STATUSES)


#: The listing states a card names. `gone` is the absence of a document.
STATE_AVAILABLE = "available"
STATE_UNAVAILABLE = "unavailable"
STATE_GONE = "gone"

META_OK = "ok"
META_PARTIAL = "partial"


def _card_images(payload: dict) -> list:
    """The listing's gallery as the card carries it: refs, in the owner's order.

    ``listings.search_documents`` serves the whole gallery and this projection
    used to take element zero of it — so a result row could never show more
    than one photo whatever the client was able to draw, and the swipeable
    strip a phone SERP is made of had exactly one slide. The gallery is the
    owner's; the only thing decided here is how much of it a CARD is worth,
    which is ``CARD_IMAGES_LIMIT``: a result row is a glance, and a person who
    wants photo eleven opens the listing.

    Deduplicated, because two identical refs are two identical slides and a
    carousel that repeats a picture reads as a broken carousel.
    """
    from .conf import classified_settings

    limit = max(1, int(classified_settings.CARD_IMAGES_LIMIT))
    refs = [str(ref) for ref in (payload.get("images") or []) if ref]
    return list(dict.fromkeys(refs))[:limit]


def _base_card(payload: dict) -> dict:
    """The fields every classified card shows, whatever renders it.

    Shared with ``search_sources._card`` so a result row and a chat header
    cannot disagree about what a listing looks like. The display price rides
    along with nothing derived: the written price is what a human reads and
    formatting it is the frontend's job, not a server's guess at a locale.

    ``images`` is the gallery and ``image`` is its first element. Both, not one
    of them: every reader in and out of this fleet was written against
    ``image``, the card travels through stores that never validate it
    (stapel-search keeps it in a JSONField, stapel-chat re-declares it as
    opaque JSON), and a key removed on the server is a client that renders
    nothing until it is redeployed. So the singular stays, and it is always
    ``images[0]`` — never a second answer to the same question.
    """
    images = _card_images(payload)
    return {
        "title": payload.get("title") or "",
        "price": payload.get("price"),
        "currency": payload.get("currency") or "",
        "location_label": payload.get("location_label") or "",
        "image": images[0] if images else None,
        "images": images,
        "published_at": payload.get("published_at"),
    }


def _call(name: str, payload: dict, *, what: str):
    """One guarded comm read. Returns ``None`` when the answer is unavailable.

    Unavailable is not an error here: it is the ``partial`` branch of a card.
    The exception is deliberately swallowed and logged, because the caller is
    a person opening a chat.
    """
    if not name:
        return None
    from stapel_core.comm import call

    from .conf import classified_settings

    try:
        return call(name, payload, timeout=float(classified_settings.CALL_TIMEOUT_SECONDS))
    except Exception:  # noqa: BLE001 — degradation is data, see the docstring
        logger.info("classified: %s unavailable via %r", what, name, exc_info=True)
        return None


# ── The listing card ─────────────────────────────────────────────────


def listing_cards(keys: Iterable) -> dict:
    """``{listing_key: card}`` for every key asked about, including the gone.

    A key the document function does not serve is not dropped: it comes back
    as a ``gone`` card. Dropping it would hand the caller a conversation with
    no header, which is the state the owner opened the product and found.
    """
    from .conf import classified_settings

    wanted = [str(key) for key in keys if str(key)]
    if not wanted:
        return {}

    answer = _call(
        classified_settings.LISTING_DOCUMENTS_FUNCTION,
        {"keys": wanted},
        what="listing documents",
    )
    documents = answer if isinstance(answer, dict) else {}
    reachable = answer is not None

    cards = {}
    for key in wanted:
        document = documents.get(key) or documents.get(str(key))
        if document is None:
            cards[key] = _gone_card(key, reachable=reachable)
            continue
        cards[key] = _live_card(key, document)

    _describe_images(cards)
    return cards


def _gone_card(key: str, *, reachable: bool) -> dict:
    """A card for a listing nobody serves any more — or for a read that failed.

    The two are told apart, because they are different truths: the listing
    was deleted, versus the catalogue could not be asked. A client renders
    "listing removed" for one and "temporarily unavailable" for the other.
    """
    return {
        "listing_id": key,
        "title": "",
        "price": None,
        "currency": "",
        "location_label": "",
        "published_at": None,
        "image": None,
        "images": [],
        "status": "",
        "moderation_status": "",
        "state": STATE_GONE if reachable else STATE_UNAVAILABLE,
        "owner_id": "",
        "url": "",
        "meta_status": META_PARTIAL,
        "meta_reason": "listing_deleted" if reachable else "catalogue_unavailable",
    }


def _live_card(key: str, document: dict) -> dict:
    from .conf import classified_settings

    status = str(document.get("status") or "")
    template = classified_settings.LISTING_URL_TEMPLATE or ""
    card = {
        "listing_id": key,
        **_base_card(document),
        "status": status,
        "moderation_status": str(document.get("moderation_status") or ""),
        "state": STATE_AVAILABLE if status in _indexed_statuses() else STATE_UNAVAILABLE,
        "owner_id": str(document.get("owner_id") or ""),
        "url": template.format(listing_id=key) if template else "",
        "meta_status": META_OK,
        "meta_reason": None,
    }
    return card


def _refs_to_describe(cards: dict, budget: int) -> list:
    """Every card's gallery, flattened PRIMARIES FIRST and capped at *budget*.

    Column-major on purpose. ``cdn.describe_many`` takes a bounded batch, and
    a batch of fifty conversations each carrying ten photos is five hundred
    refs — so something has to be left out, and the honest order to leave it
    out in is "everybody's first photo before anybody's second". Row-major
    would spend the whole budget on the first five cards' galleries and leave
    the forty-fifth chat header with no thumbnail at all, which is the surface
    that only ever shows a thumbnail.

    What falls off the end is not dropped: it stays a ref and says
    ``not_described`` (see :func:`_describe_images`), which is the same
    sentence this module already used for a ref the CDN answered nothing about.
    """
    galleries = [list(card.get("images") or []) for card in cards.values()]
    depth = max((len(gallery) for gallery in galleries), default=0)
    ordered: list = []
    seen: set = set()
    for position in range(depth):
        for gallery in galleries:
            if position >= len(gallery):
                continue
            ref = gallery[position]
            if ref in seen:
                continue
            seen.add(ref)
            ordered.append(ref)
    return ordered[:budget]


def _set_images(card: dict, described: list) -> None:
    """Both keys, one answer: ``image`` IS ``images[0]``, described the same."""
    card["images"] = described
    card["image"] = described[0] if described else None


def _describe_images(cards: dict) -> None:
    """Merge CDN render metadata over each card's images, in one call.

    Every image stays an opaque ref plus the numbers a UI needs to reserve its
    box before the bytes land — ``aspect``, ``preview_b64``, ``variants`` —
    exactly the shape stapel-chat gives an attachment, because it is the same
    CDN answering about the same kind of thing. A card whose CDN read failed
    keeps the refs and says so; a ref the CDN does not know says that
    differently, and neither is a broken conversation.

    One call for the whole batch, as before: the gallery grew, the fan-out did
    not. What the batch could not fit is named by :func:`_refs_to_describe`.
    """
    from .conf import classified_settings

    budget = int(classified_settings.CONTEXT_BATCH_LIMIT)
    refs = _refs_to_describe(cards, budget)
    if not refs:
        return

    answer = _call(
        classified_settings.MEDIA_DESCRIBE_FUNCTION,
        {"refs": refs},
        what="cdn.describe_many",
    )
    if answer is None:
        for card in cards.values():
            gallery = list(card.get("images") or [])
            if not gallery:
                continue
            _set_images(
                card,
                [_image(ref, None, reason="cdn_unavailable") for ref in gallery],
            )
            card["meta_status"] = META_PARTIAL
            card["meta_reason"] = card["meta_reason"] or "cdn_unavailable"
        return

    snapshots = (answer.get("items") if isinstance(answer, dict) else None) or {}
    missing = set((answer.get("missing") if isinstance(answer, dict) else None) or [])
    for card in cards.values():
        gallery = list(card.get("images") or [])
        if not gallery:
            continue
        described = []
        for ref in gallery:
            if ref in snapshots:
                described.append(_image(ref, snapshots[ref]))
            elif ref in missing:
                described.append(_image(ref, None, reason="unknown_ref"))
                card["meta_status"] = META_PARTIAL
                card["meta_reason"] = card["meta_reason"] or "image_unknown_ref"
            else:
                described.append(_image(ref, None, reason="not_described"))
        _set_images(card, described)


#: Keys a card's image always carries — present, ``null`` where unknown, so a
#: client never tests for a field's existence (the chat attachment rule).
IMAGE_KEYS = (
    "mime",
    "ext",
    "bytes",
    "width",
    "height",
    "aspect",
    "square",
    "animated",
    "preview_b64",
    "preview_kind",
    "variants",
)


def _image(ref: str, snapshot: dict | None, *, reason: str | None = None) -> dict:
    image = {"ref": str(ref), **{key: None for key in IMAGE_KEYS}}
    image["variants"] = []
    if not snapshot:
        image["meta_status"] = "missing" if reason == "unknown_ref" else META_PARTIAL
        image["meta_reason"] = reason
        return image
    for key in IMAGE_KEYS:
        if key in snapshot:
            image[key] = snapshot[key]
    image["variants"] = list(snapshot.get("variants") or [])
    image["meta_status"] = str(snapshot.get("meta_status") or META_OK)
    image["meta_reason"] = snapshot.get("meta_reason")
    return image


# ── The seller card ──────────────────────────────────────────────────


def seller_cards(user_ids: Iterable) -> dict:
    """``{user_id: card}`` — the counterparty as the marketplace shows them.

    **Never more than the public profile.** A conversation partner sees the
    display name, the avatar ref, the member-since date and the rating: the
    same facts a stranger reads off the seller's public page. Nothing about
    the account, no email, no phone — a chat is not a lookup tool.

    Today only the display name and the rating have comm Functions in the
    fleet, so the card comes back ``partial`` with ``profile_unavailable``
    naming what is missing, and the frontend renders initials. That closes
    the day stapel-profiles ships ``profiles.public_cards`` and a deployment
    sets PUBLIC_PROFILE_FUNCTION — with no release here.
    """
    from .conf import classified_settings

    wanted = [str(uid) for uid in user_ids if str(uid)]
    if not wanted:
        return {}
    wanted = list(dict.fromkeys(wanted))

    public = _call(
        classified_settings.PUBLIC_PROFILE_FUNCTION,
        {"user_ids": wanted},
        what="public profiles",
    )
    profiles = {}
    if isinstance(public, dict):
        profiles = public.get("profiles") or public.get("items") or {}

    names = {}
    if not profiles:
        answer = _call(
            classified_settings.DISPLAY_NAMES_FUNCTION,
            {"user_ids": wanted},
            what="display names",
        )
        if isinstance(answer, dict):
            names = answer.get("display_names") or {}

    template = classified_settings.SELLER_URL_TEMPLATE or ""
    cards = {}
    for user_id in wanted:
        profile = profiles.get(user_id) if isinstance(profiles, dict) else None
        card = {
            "user_id": user_id,
            "display_name": "",
            "avatar": None,
            "member_since": None,
            "seller_type": "",
            "rating": None,
            "url": template.format(user_id=user_id) if template else "",
            "meta_status": META_OK,
            "meta_reason": None,
        }
        if isinstance(profile, dict):
            card["display_name"] = str(profile.get("display_name") or "")
            card["avatar"] = profile.get("avatar") or profile.get("avatar_url") or None
            card["member_since"] = profile.get("member_since") or profile.get("created_at")
            card["seller_type"] = str(profile.get("seller_type") or "")
        else:
            card["display_name"] = str(names.get(user_id) or "")
            card["meta_status"] = META_PARTIAL
            # Names the ONE thing missing and why, so the gap is a routed ask
            # rather than a blank the frontend has to guess about.
            card["meta_reason"] = "profile_unavailable"
        card["rating"] = _rating(user_id)
        cards[user_id] = card
    return cards


def _rating(user_id: str):
    """The seller's aggregate, or ``None`` — never a fabricated zero.

    "No reviews yet" and "0.0 stars" are different sentences and a client
    draws them differently; stapel-reviews itself omits a key with no
    published review rather than answering zeros, and that distinction is
    carried through here rather than flattened.
    """
    from .conf import classified_settings

    target_type = classified_settings.SELLER_RATING_TARGET_TYPE or ""
    if not target_type:
        return None
    answer = _call(
        classified_settings.SELLER_RATING_FUNCTION,
        {"target_type": target_type, "target_key": str(user_id)},
        what="seller rating",
    )
    if not isinstance(answer, dict):
        return None
    count = answer.get("count")
    if not count:
        return None
    return {"avg": answer.get("avg"), "count": count}


__all__ = [
    "IMAGE_KEYS",
    "META_OK",
    "META_PARTIAL",
    "STATE_AVAILABLE",
    "STATE_GONE",
    "STATE_UNAVAILABLE",
    "listing_cards",
    "seller_cards",
]
