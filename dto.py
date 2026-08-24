"""Dataclass DTOs — the API models of stapel-classified.

Envelopes, not ORM rows. The cards themselves are plain dicts assembled in
``cards.py`` from other modules' answers, and they are typed here so the
emitted OpenAPI contract describes them field by field instead of shrugging
at a free-form object (contract-pipeline.md A1: typed where typeable).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CardImageDTO:
    """The card's primary image: an opaque CDN ref plus what a UI needs to
    reserve its box before the bytes arrive. Same fields, same meanings and
    same source (``cdn.describe_many``) as a stapel-chat attachment."""

    ref: str = ""
    mime: Optional[str] = None
    ext: Optional[str] = None
    bytes: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    aspect: Optional[float] = None
    square: Optional[bool] = None
    animated: Optional[bool] = None
    preview_b64: Optional[str] = None
    preview_kind: Optional[str] = None
    variants: List[Dict[str, Any]] = field(default_factory=list)
    meta_status: str = "ok"
    meta_reason: Optional[str] = None


@dataclass
class ListingCardDTO:
    """The short listing card a conversation header shows.

    ``state`` is the field this whole wave exists for: ``available``,
    ``unavailable`` (paused, expired, sold, blocked — it exists and is not
    live) and ``gone`` (deleted). A buyer is most confused exactly when the
    thing is no longer on sale, and that is the case a public 404 cannot
    express.
    """

    listing_id: str = ""
    title: str = ""
    price: Optional[str] = None
    currency: str = ""
    location_label: str = ""
    published_at: Optional[str] = None
    image: Optional[CardImageDTO] = None
    status: str = ""
    moderation_status: str = ""
    state: str = "available"
    owner_id: str = ""
    url: str = ""
    meta_status: str = "ok"
    meta_reason: Optional[str] = None


@dataclass
class RatingDTO:
    """An aggregate, or nothing at all. Never a fabricated zero."""

    avg: Optional[float] = None
    count: int = 0


@dataclass
class SellerCardDTO:
    """The counterparty, as the marketplace shows them in public.

    Never more than the public profile: display name, avatar ref,
    member-since, seller type, rating. A conversation is not a lookup tool.
    """

    user_id: str = ""
    display_name: str = ""
    avatar: Optional[str] = None
    member_since: Optional[str] = None
    seller_type: str = ""
    rating: Optional[RatingDTO] = None
    url: str = ""
    meta_status: str = "ok"
    meta_reason: Optional[str] = None


@dataclass
class SubjectDTO:
    """What a conversation is about, and since when."""

    type: str = "listing"
    key: str = ""
    listing: Optional[ListingCardDTO] = None
    bound_at: Optional[str] = None


@dataclass
class ConversationContextDTO:
    """One conversation's header: the subject, the counterparty, my role."""

    conversation_id: str = ""
    scope_key: str = ""
    subject: Optional[SubjectDTO] = None
    counterparty: Optional[SellerCardDTO] = None
    viewer_role: str = ""
    previous_subjects: List[SubjectDTO] = field(default_factory=list)


@dataclass
class ConversationContextPageDTO:
    """A batch answer, keyed by conversation id.

    Ids the caller is not a party of are simply ABSENT — a 403 per row would
    confirm that an id names a real thread, and the id is the only thing
    protecting a stranger's conversation from being probed.
    """

    items: Dict[str, ConversationContextDTO] = field(default_factory=dict)
    missing: List[str] = field(default_factory=list)
