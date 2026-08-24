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


class ConversationBindSerializer(serializers.Serializer):
    """Bind a chat conversation to the listing it is about.

    ``conversation_id`` comes from stapel-chat, which the client has just
    called (``POST /chat/api/v1/conversations``). It is not created here and
    could not be: chat 0.4.0 publishes no comm Function to create one and no
    event when one appears — both are routed upstream, and until they land
    the client is the only party holding both halves.
    """

    conversation_id = serializers.UUIDField()
    listing_id = serializers.CharField(max_length=255)
    scope_key = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=255
    )


class ConversationContextQuerySerializer(serializers.Serializer):
    """A page of conversation ids to resolve headers for — the inbox call."""

    conversation_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=True
    )


__all__ = [
    "ConversationBindSerializer",
    "ConversationContextPageResponseSerializer",
    "ConversationContextQuerySerializer",
    "ConversationContextResponseSerializer",
]
