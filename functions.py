"""comm Functions this composite PROVIDES.

Two of them, and both exist because a domain-blind engine needs an answer
only a composite can give:

``classified.subject_cards``
    Keyed batch of short listing cards. Since stapel-chat 0.6.0 this is the
    ``card_function`` chat calls for a ``listing`` subject — the shape was
    designed against that ask before chat had a registry to name it in, and
    the preset declares the binding (``STAPEL_CHAT["SUBJECT_TYPES"]``). It is
    also what this module's own header views use, so one listing has exactly
    one card wherever it is rendered.

``classified.seller_content``
    The moderation content function for the ``seller`` target type. A
    marketplace can be asked to act against a *seller*, not only against one
    listing, and stapel-moderation requires a content function per target
    type. stapel-profiles serves no ``profiles.moderation_content``, which is
    exactly why the composite's MODULE.md refused to register a ``profile``
    target — so this composite serves the marketplace-shaped answer itself:
    who the seller is in public, and their rating. ``author_id`` is the
    seller's own id, which is what makes "you cannot report yourself" work
    without trusting anything a client sent.
"""
from __future__ import annotations

import json
from pathlib import Path

from stapel_core.comm import function

_SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas" / "functions"

SUBJECT_CARDS = "classified.subject_cards"
SELLER_CONTENT = "classified.seller_content"
CAN_REPORT_MESSAGE = "classified.can_report_message"

#: How a chat message is named to stapel-moderation:
#: ``<conversation_id>:<message_id>``. The composite key is not decoration —
#: a bare message id would be unauthorizable, because nobody in the fleet can
#: say who was in a conversation from a message id alone. With the
#: conversation in the key, this package can ask chat who is in that thread,
#: which is what makes "only the two people in the thread may report what was
#: said in it" a server rule instead of a client's good manners.
MESSAGE_KEY_SEPARATOR = ":"


def _schema(name: str) -> dict:
    return json.loads((_SCHEMAS_DIR / f"{name}.json").read_text(encoding="utf-8"))


@function(SUBJECT_CARDS, schema=_schema(SUBJECT_CARDS))
def subject_cards_function(payload: dict) -> dict:
    """``{keys: [...]} -> {cards: {key: card}}`` — short cards, gone included.

    A key whose listing was deleted comes back as a ``gone`` card rather than
    being dropped: the caller is rendering a conversation that exists, and a
    header with nothing in it is the defect this whole surface closes.
    """
    from .cards import listing_cards

    return {"cards": listing_cards(payload.get("keys") or [])}


@function(SELLER_CONTENT, schema=_schema(SELLER_CONTENT))
def seller_content_function(payload: dict) -> dict:
    """One seller's public identity, in the ``*.moderation_content`` shape."""
    from .cards import seller_cards

    user_id = str(payload.get("seller_id") or "")
    card = seller_cards([user_id]).get(user_id) or {}
    rating = card.get("rating") or {}
    return {
        "seller_id": user_id,
        "title": card.get("display_name") or "",
        "text": "",
        "language": "",
        "media": [],
        # The seller IS the author of their own storefront: this is what makes
        # OwnContent (you cannot report yourself) answerable without trusting
        # a client-supplied name.
        "author_id": user_id,
        "url": card.get("url") or "",
        "rating": rating or None,
        "seller_type": card.get("seller_type") or "",
    }


@function(CAN_REPORT_MESSAGE, schema=_schema(CAN_REPORT_MESSAGE))
def can_report_message_function(payload: dict) -> dict:
    """May this user complain about that message? — the type's ``can_report``.

    The target key carries the conversation, which is what makes "only the two
    people in a thread may report what was said in it" a server rule instead
    of a client's good manners. Until 0.3.2 the parties were read off this
    package's own binding row — a copy of chat's membership that nothing could
    refresh, so it was as stale as the last time somebody bound a subject.
    They are read from chat itself now (``chat.conversation_participants``).

    Fail-CLOSED — an unparseable key, an unknown conversation, an outsider, or
    a chat that cannot be asked all answer no. moderation's default for a
    missing callback is fail-open, which is right for a public listing and
    wrong for a private thread; an unreachable chat is the same shape as an
    unreachable block store, and an outage is not consent.
    """
    from . import services

    target_key = str(payload.get("target_key") or "")
    conversation_id, _, message_id = target_key.partition(MESSAGE_KEY_SEPARATOR)
    if not conversation_id or not message_id:
        return {"allowed": False, "reason": "malformed_key"}

    try:
        thread = services.chat_threads([conversation_id]).get(conversation_id) or {}
    except services.ChatUnavailable:
        return {"allowed": False, "reason": "chat_unavailable"}
    if not thread.get("exists"):
        return {"allowed": False, "reason": "unknown_conversation"}
    return {
        "allowed": str(payload.get("reporter_id") or "")
        in services.party_ids(thread)
    }


__all__ = [
    "CAN_REPORT_MESSAGE",
    "MESSAGE_KEY_SEPARATOR",
    "SELLER_CONTENT",
    "SUBJECT_CARDS",
    "can_report_message_function",
    "seller_content_function",
    "subject_cards_function",
]
