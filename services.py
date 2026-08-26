"""Service layer: read what a conversation is about, and who is in it.

Both facts now live in stapel-chat. Through 0.3.1 the first of them lived
HERE, in a ``ConversationSubject`` table, because chat keyed a direct thread
by the participant pair alone and one buyer and one seller could therefore
hold exactly one thread whatever they discussed. chat 0.6.0 put the subject
into ``direct_key``, so each listing gets its own thread, and shipped
``chat.conversation_participants`` so a server can ask who is in one. The
table was marked for deletion the day both landed and this is that day: it is
gone, not shadowed, and nothing here keeps a second copy of either fact.

What is left is the composite's actual job — the JOIN. Chat holds an opaque
``(subject_type, subject_key)`` it may never parse; listings holds a listing
that knows nothing about conversations; profiles holds a person. The header a
buyer and a seller both need is assembled here, from three modules' answers,
in the one package allowed to know all three exist.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: The only subject type this composite serves. A string rather than an enum:
#: it travels to stapel-chat as an opaque name (``STAPEL_CHAT["SUBJECT_TYPES"]``
#: — see preset.py) and an enum here would be a second vocabulary to keep in
#: step with that one.
SUBJECT_TYPE_LISTING = "listing"

#: What chat calls a two-party thread. A group room can carry a subject too,
#: and the header renders one; the block check below is about opening a
#: DIRECT conversation with a seller, which is the only contact this module
#: knows how to refuse.
KIND_DIRECT = "direct"

#: Why a header is degraded. The subject's key names a listing whose owner is
#: not in the thread — nothing in the fleet can refuse that at creation time
#: (chat may not know what a listing is), so it is rendered rather than
#: hidden: the badge is the closure, not a 404 that would also hide honest
#: threads.
REASON_OWNER_NOT_A_PARTY = "subject_owner_not_a_party"


class ClassifiedError(Exception):
    """Base of every refusal this layer raises."""


class SubjectNotFound(ClassifiedError):
    """The listing named by the request does not exist (404)."""


class ConversationNotBound(ClassifiedError):
    """Chat has no such thread, or it is not about that listing (404)."""


class NotAParty(ClassifiedError):
    """The caller is not a party to the conversation (404-shaped)."""


class OwnListing(ClassifiedError):
    """A seller cannot open a buyer conversation with themselves (400)."""


class ContactRefused(ClassifiedError):
    """A block stands between the two parties (403)."""


class ChatUnavailable(ClassifiedError):
    """Chat is the source of both facts and could not be asked (503).

    Never an empty answer. An empty answer is indistinguishable from "you are
    not a party to any of these", which is a 404 — and a reader would take a
    chat outage for a permission boundary.
    """


# ── The one read this module makes of chat ───────────────────────────


def chat_threads(conversation_ids) -> dict:
    """``[id, …] -> {id: {exists, kind, scope_key, subject_*, participants}}``.

    ``chat.conversation_participants`` (stapel-chat 0.6.0), by NAME — this
    package imports no chat module and mounts none of it, so a deployment
    that runs chat in another process changes nothing here.
    """
    from stapel_core.comm import call

    from .conf import classified_settings

    wanted = [str(cid) for cid in conversation_ids if str(cid or "").strip()]
    if not wanted:
        return {}

    name = classified_settings.CONVERSATION_PARTICIPANTS_FUNCTION or ""
    if not name:
        raise ChatUnavailable("no CONVERSATION_PARTICIPANTS_FUNCTION configured")
    try:
        answer = call(
            name,
            {"conversation_ids": wanted},
            timeout=float(classified_settings.CALL_TIMEOUT_SECONDS),
        )
    except Exception as exc:  # noqa: BLE001 — see ChatUnavailable
        logger.warning("classified: participants read via %r failed: %s", name, exc)
        raise ChatUnavailable(
            f"{exc} — if the chat service answered 'no such function', it is "
            f"older than stapel-chat 0.6.0, which is the first release "
            f"serving {name!r}"
        ) from exc
    return (answer or {}).get("conversations") or {}


def party_ids(thread: dict) -> list:
    return [
        str(p.get("user_id") or "")
        for p in (thread.get("participants") or [])
        if str(p.get("user_id") or "")
    ]


# ── Contact ──────────────────────────────────────────────────────────


def confirm_listing_conversation(
    *,
    conversation_id,
    listing_key,
    actor_id,
) -> dict:
    """Check that this contact is allowed, and answer the header for it.

    This used to WRITE the binding (``bind_listing_conversation``): the client
    created a thread in chat, then told this module what it was about, and
    every later read was authorized against that claim. Chat owns the subject
    now, so there is nothing to record — what is left is the half a claim
    could never be, a **verification**:

    - the listing exists (a 404 nobody else in the fleet can produce, because
      chat may not know what a listing is);
    - the caller is not its seller (contacting yourself is not contact);
    - chat agrees the thread exists, that the caller is in it, and that its
      subject really is that listing — the "a binding is a claim by the person
      who makes it" limitation of 0.3.x, closed;
    - and no block stands between the two parties.

    Order is deliberate and unchanged: the listing first (it produces the 404
    and names the seller), self-contact next (cheap, and a block check against
    yourself is meaningless), then chat, then the block — the two that can be
    remote calls and the two that can answer 503, last.
    """
    from . import blocks
    from .cards import STATE_GONE, listing_cards

    key = str(listing_key)
    card = listing_cards([key]).get(key) or {}
    if card.get("state") == STATE_GONE or not card.get("owner_id"):
        # A listing nobody serves has no seller to introduce. A thread already
        # about it keeps working — see conversation_contexts, which renders
        # the gone card rather than refusing the read.
        raise SubjectNotFound(key)

    seller_id = str(card["owner_id"])
    if str(actor_id) == seller_id:
        raise OwnListing(key)

    cid = str(conversation_id)
    thread = chat_threads([cid]).get(cid) or {}
    if not thread.get("exists"):
        raise ConversationNotBound(cid)
    if str(actor_id) not in party_ids(thread):
        # 404-shaped, like every other refusal on this surface: a 403 would
        # confirm the id names a real thread, and the id is the only thing
        # keeping a stranger's conversation unprobed.
        raise NotAParty(cid)
    if (
        thread.get("subject_type") != SUBJECT_TYPE_LISTING
        or str(thread.get("subject_key") or "") != key
    ):
        raise ConversationNotBound(cid)

    if blocks.is_blocked(actor_id, seller_id):
        raise ContactRefused(key)

    return conversation_context(cid, viewer_id=actor_id)


# ── Reading ──────────────────────────────────────────────────────────


def conversation_context(conversation_id, *, viewer_id) -> dict:
    """The header of one conversation: what it is about, and with whom."""
    contexts = conversation_contexts([conversation_id], viewer_id=viewer_id)
    if not contexts:
        raise ConversationNotBound(str(conversation_id))
    return contexts[str(conversation_id)]


def conversation_contexts(conversation_ids, *, viewer_id) -> dict:
    """``{conversation_id: context}`` for a page of the inbox, in one pass.

    One participants read for the whole page, then two comm reads for the
    cards (documents, then their images) plus one per distinct counterparty
    rating — never one round trip per row, which is what makes a conversation
    list openable at all.

    A conversation the viewer is not a party of is simply ABSENT from the
    answer, and so is one chat says is about nothing (or about something this
    composite does not serve). Not a 403: a 403 would confirm that the id
    names a real thread.
    """
    from .cards import STATE_GONE, listing_cards, seller_cards
    from .conf import classified_settings

    wanted = [str(cid) for cid in conversation_ids if str(cid)]
    if not wanted:
        return {}
    limit = int(classified_settings.CONTEXT_BATCH_LIMIT)
    wanted = list(dict.fromkeys(wanted))[:limit]

    viewer = str(viewer_id)
    threads = chat_threads(wanted)
    mine = {
        cid: thread
        for cid, thread in threads.items()
        if thread.get("exists")
        and thread.get("subject_type") == SUBJECT_TYPE_LISTING
        and str(thread.get("subject_key") or "")
        and viewer in party_ids(thread)
    }
    if not mine:
        return {}

    cards = listing_cards({str(t["subject_key"]) for t in mine.values()})

    counterparties: dict[str, str] = {}
    for cid, thread in mine.items():
        card = cards.get(str(thread["subject_key"])) or {}
        owner = str(card.get("owner_id") or "")
        others = [p for p in party_ids(thread) if p != viewer]
        if owner and owner in others:
            counterparties[cid] = owner
        elif len(others) == 1:
            counterparties[cid] = others[0]
        else:
            # A group room about a listing: several other people and no single
            # "the other party". The header still renders its subject.
            counterparties[cid] = ""
    parties = seller_cards({uid for uid in counterparties.values() if uid})

    contexts = {}
    for cid, thread in mine.items():
        key = str(thread["subject_key"])
        card = cards.get(key) or {}
        owner = str(card.get("owner_id") or "")
        parties_here = party_ids(thread)
        # A gone listing has no owner to be a party — its card already says
        # `gone`, and flagging that as a mismatched owner would name the same
        # fact twice, in a field that means something else.
        owner_is_known = bool(owner) and card.get("state") != STATE_GONE
        degraded = owner_is_known and owner not in parties_here
        contexts[cid] = {
            "conversation_id": cid,
            "scope_key": str(thread.get("scope_key") or ""),
            "subject": {
                "type": SUBJECT_TYPE_LISTING,
                "key": key,
                "listing": card or None,
                "meta_status": "partial" if degraded else "ok",
                "meta_reason": REASON_OWNER_NOT_A_PARTY if degraded else None,
            },
            "counterparty": parties.get(counterparties[cid]),
            "viewer_role": "seller" if owner_is_known and viewer == owner else "buyer",
        }
    return contexts


__all__ = [
    "KIND_DIRECT",
    "REASON_OWNER_NOT_A_PARTY",
    "SUBJECT_TYPE_LISTING",
    "ChatUnavailable",
    "ClassifiedError",
    "ContactRefused",
    "ConversationNotBound",
    "NotAParty",
    "OwnListing",
    "SubjectNotFound",
    "chat_threads",
    "party_ids",
    "confirm_listing_conversation",
    "conversation_context",
    "conversation_contexts",
]
