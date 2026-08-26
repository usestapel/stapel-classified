"""Serializers for the stapel-classified API — envelopes and requests.

Every response shape is a dataclass in ``dto.py`` rendered through core's
``StapelDataclassSerializer``, so the emitted OpenAPI describes each card
field by field. The service layer answers with plain dicts whose keys are the
dataclass fields; DRF reads a mapping the same way it reads an object, and
the dataclass is what the contract is generated from.
"""
from __future__ import annotations

from rest_framework import serializers
from stapel_core.django.api.serializers import StapelDataclassSerializer

from .dto import (
    ConversationContextDTO,
    ConversationContextPageDTO,
)


class ConversationContextResponseSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = ConversationContextDTO


class ConversationContextPageResponseSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = ConversationContextPageDTO


class ConversationConfirmSerializer(serializers.Serializer):
    """Confirm that a contact about a listing is allowed, and read its header.

    ``conversation_id`` comes from stapel-chat, which the client has just
    called (``POST /chat/api/v1/conversations`` with ``subject_type:
    "listing"``). Both ids are VERIFIED against chat here — through 0.3.1 they
    were recorded as the caller said them.

    There is no ``scope_key``: chat stores the thread's scope and this module
    reads it back, so a client can no longer name a scope the thread is not in.
    """

    conversation_id = serializers.UUIDField()
    listing_id = serializers.CharField(max_length=255)


class ConversationContextQuerySerializer(serializers.Serializer):
    """A page of conversation ids to resolve headers for — the inbox call."""

    conversation_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=True
    )


__all__ = [
    "ConversationConfirmSerializer",
    "ConversationContextPageResponseSerializer",
    "ConversationContextQuerySerializer",
    "ConversationContextResponseSerializer",
]
