"""Service layer: bind a conversation to its subject, and read the context.

Two operations, and both exist because of one sentence from the owner after
opening the live product's chat: it was "unclear with whom, and unclear about
what". A messaging engine cannot fix that — it is not allowed to know what a
listing is. A catalogue cannot fix it either. The join is the fix, and this
is where it is made and read.
"""
from __future__ import annotations

import logging

from django.db import IntegrityError, transaction

from .models import SUBJECT_TYPE_LISTING, ConversationSubject

logger = logging.getLogger(__name__)


class ClassifiedError(Exception):
    """Base of every refusal this layer raises."""


class SubjectNotFound(ClassifiedError):
    """The listing named by a binding request does not exist (404)."""


class ConversationNotBound(ClassifiedError):
    """No subject has ever been recorded for this conversation (404)."""


class NotAParty(ClassifiedError):
    """The caller is neither party of the bound conversation (404-shaped)."""


class OwnListing(ClassifiedError):
    """A seller cannot open a buyer conversation with themselves (400)."""


class ContactRefused(ClassifiedError):
    """A block stands between the two parties (403)."""


# ── Binding ──────────────────────────────────────────────────────────


def bind_listing_conversation(
    *,
    conversation_id,
    listing_key,
    actor_id,
    scope_key: str = "",
) -> ConversationSubject:
    """Record that ``conversation_id`` is about ``listing_key``.

    Called by the buyer's client immediately after chat has created (or
    returned) the direct conversation — chat 0.4.0 publishes no
    ``conversation.created`` event and no comm Function to create one from a
    server, both of which are routed upstream. Until then the client holds
    the handle and this is where it lands.

    Order of checks is deliberate: the listing first (it produces the 404 and
    tells us who the seller is), self-contact next (cheap, and a block check
    against yourself is meaningless), the block last (it is the only one that
    can be a remote call and the only one that can answer 503).
    """
    from . import blocks
    from .cards import STATE_GONE, listing_cards

    key = str(listing_key)
    card = listing_cards([key]).get(key) or {}
    if card.get("state") == STATE_GONE or not card.get("owner_id"):
        # A listing nobody serves has no seller to introduce, so there is no
        # conversation to open ABOUT it. A conversation already bound to it
        # keeps working — see conversation_context, which renders the gone
        # card rather than refusing the read.
        raise SubjectNotFound(key)

    seller_id = str(card["owner_id"])
    if str(actor_id) == seller_id:
        raise OwnListing(key)

    if blocks.is_blocked(actor_id, seller_id):
        raise ContactRefused(key)

    row = ConversationSubject(
        scope_key=scope_key or "",
        conversation_id=conversation_id,
        subject_type=SUBJECT_TYPE_LISTING,
        subject_key=key,
        initiator_id=actor_id,
        counterparty_id=seller_id,
    )
    try:
        with transaction.atomic():
            row.save()
    except IntegrityError:
        # Idempotent: the same (conversation, subject) pair is one fact,
        # however many times a retried request or a second tab reports it.
        # The FIRST writer's parties stand — a later caller cannot rewrite
        # who the two sides of a thread are.
        return ConversationSubject.objects.get(
            conversation_id=conversation_id,
            subject_type=SUBJECT_TYPE_LISTING,
            subject_key=key,
        )
    return row


# ── Reading ──────────────────────────────────────────────────────────


def current_subject(conversation_id) -> ConversationSubject:
    """The newest subject recorded for a conversation.

    Newest rather than only: chat 0.4.0 gives one buyer and one seller a
    single direct thread whatever they discuss, so a thread genuinely can be
    about a second listing. The header shows the latest and the history is
    the rest of the rows — see models.py for why that is honesty rather than
    laxity.
    """
    row = (
        ConversationSubject.objects.filter(conversation_id=conversation_id)
        .order_by("-created_at")
        .first()
    )
    if row is None:
        raise ConversationNotBound(str(conversation_id))
    return row


def conversation_context(conversation_id, *, viewer_id) -> dict:
    """The header of one conversation: what it is about, and with whom."""
    contexts = conversation_contexts([conversation_id], viewer_id=viewer_id)
    if not contexts:
        raise ConversationNotBound(str(conversation_id))
    return contexts[str(conversation_id)]


def conversation_contexts(conversation_ids, *, viewer_id) -> dict:
    """``{conversation_id: context}`` for a page of the inbox, in one pass.

    Two comm reads for the whole page (documents, then their images) plus one
    per distinct counterparty rating — never one round trip per row, which is
    what makes a conversation list openable at all.

    A conversation the viewer is not a party of is simply ABSENT from the
    answer. Not a 403: a 403 would confirm that the id names a real thread,
    and the ids are the only thing protecting a stranger's conversation from
    being probed.
    """
    from .cards import listing_cards, seller_cards
    from .conf import classified_settings

    wanted = [str(cid) for cid in conversation_ids if str(cid)]
    if not wanted:
        return {}
    limit = int(classified_settings.CONTEXT_BATCH_LIMIT)
    wanted = list(dict.fromkeys(wanted))[:limit]

    rows = ConversationSubject.objects.filter(conversation_id__in=wanted).order_by(
        "-created_at"
    )
    current: dict[str, ConversationSubject] = {}
    history: dict[str, list] = {}
    for row in rows:
        cid = str(row.conversation_id)
        if cid not in current:
            current[cid] = row
        else:
            history.setdefault(cid, []).append(row)

    mine = {
        cid: row for cid, row in current.items() if row.involves(viewer_id)
    }
    if not mine:
        return {}

    keys = {row.subject_key for row in mine.values()}
    for extra in history.values():
        keys.update(row.subject_key for row in extra)
    cards = listing_cards(keys)
    parties = seller_cards({row.other_party(viewer_id) for row in mine.values()})

    contexts = {}
    for cid, row in mine.items():
        contexts[cid] = {
            "conversation_id": cid,
            "scope_key": row.scope_key,
            "subject": {
                "type": row.subject_type,
                "key": row.subject_key,
                "listing": cards.get(row.subject_key),
                "bound_at": row.created_at.isoformat(),
            },
            "counterparty": parties.get(row.other_party(viewer_id)),
            "viewer_role": (
                "buyer" if str(viewer_id) == str(row.initiator_id) else "seller"
            ),
            # Every subject this thread has carried, newest first, minus the
            # current one. Empty in a deployment whose chat keys threads by
            # subject; non-empty on chat 0.4.0, where it is the only way to
            # see that "that other listing" was discussed here too.
            "previous_subjects": [
                {
                    "type": other.subject_type,
                    "key": other.subject_key,
                    "listing": cards.get(other.subject_key),
                    "bound_at": other.created_at.isoformat(),
                }
                for other in history.get(cid, [])
            ],
        }
    return contexts


__all__ = [
    "ClassifiedError",
    "ContactRefused",
    "ConversationNotBound",
    "NotAParty",
    "OwnListing",
    "SubjectNotFound",
    "bind_listing_conversation",
    "conversation_context",
    "conversation_contexts",
    "current_subject",
]
