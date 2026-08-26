"""v1 URL set — paths are relative to the ``api/v1/`` mount the host makes.

One audience only: the two people in a conversation. There is no staff
surface here — a moderator reads a listing in the moderation console, which
is the module that owns queues.
"""
from typing import NamedTuple

from django.urls import path

from .errors import ClassifiedErrorKeysView
from .views import (
    ConversationConfirmView,
    ConversationContextBatchView,
    ConversationContextView,
)

conversation_patterns = [
    # Confirm that a contact about a listing is allowed, and read the header
    # back. POST is the "I am writing to this seller" moment; it records
    # nothing (chat holds the thread and its subject since 0.3.2).
    path("conversations", ConversationConfirmView.as_view(), name="classified-conversations"),
    # Headers for a page of the inbox, one call.
    path(
        "conversations/contexts",
        ConversationContextBatchView.as_view(),
        name="classified-conversation-contexts",
    ),
    # One conversation's header.
    path(
        "conversations/<uuid:conversation_id>",
        ConversationContextView.as_view(),
        name="classified-conversation",
    ),
]

urlpatterns = [
    *conversation_patterns,
    # The listing the stapel-translate error collector reads.
    path("error-keys/", ClassifiedErrorKeysView.as_view(), name="classified-error-keys"),
]


class GateEntry(NamedTuple):
    """One gated URL block (capability-config.md §2 p.2). ``flags`` compose
    with OR; empty flags = always on."""

    name: str
    flags: tuple
    patterns: tuple


#: One block, always mounted. It is declared rather than assumed because the
#: capabilities emitter reads it: a product asking "what does installing this
#: composite ADD to my API" gets the answer from the contract instead of from
#: somebody's memory. There is no switch to turn it off — a classified
#: deployment whose conversations have no subject is the product the owner
#: opened and could not use.
GATE_REGISTRY: dict = {
    "classified.conversations": GateEntry(
        "classified.conversations", (), tuple(conversation_patterns)
    ),
}
