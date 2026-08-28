"""The conversation-context surface: what a chat is about, and with whom.

Three endpoints, one purpose — the owner opened the live product's chat and
found it "unclear with whom and about what". A messaging engine may not know
what a listing is and a catalogue may not know what a conversation is, so the
answer is assembled here, in the one package allowed to know both.

Every view is core's ``StapelAPIView`` (the hoisted serializer seam, core
0.37.0): a host swaps a request or response shape by subclassing and setting
one attribute, and never by copying a method body.
"""
from __future__ import annotations

import functools

from drf_spectacular.utils import extend_schema
from stapel_core.django.api.errors import StapelErrorResponse, StapelResponse
from stapel_core.django.api.permissions import ANONYMOUS_DENIED, IsNotAnonymousUser
from stapel_core.django.api.views import StapelAPIView

from . import services
from .errors import (
    ERR_400_OWN_LISTING,
    ERR_404_CONVERSATION_NOT_FOUND,
    ERR_404_LISTING_NOT_FOUND,
    ERR_503_CHAT_UNAVAILABLE,
)
from .serializers import (
    ConversationConfirmSerializer,
    ConversationContextPageResponseSerializer,
    ConversationContextQuerySerializer,
    ConversationContextResponseSerializer,
)


def _maps_errors(handler):
    """One translation table from service refusals to the error catalogue."""

    @functools.wraps(handler)
    def wrapper(self, request, *args, **kwargs):
        try:
            return handler(self, request, *args, **kwargs)
        except services.SubjectNotFound:
            return StapelErrorResponse(404, ERR_404_LISTING_NOT_FOUND)
        except (services.ConversationNotBound, services.NotAParty):
            # The same 404 for both: a distinct answer for "that thread exists
            # and is not yours" would confirm the id names a real thread.
            return StapelErrorResponse(404, ERR_404_CONVERSATION_NOT_FOUND)
        except services.ChatUnavailable:
            return StapelErrorResponse(503, ERR_503_CHAT_UNAVAILABLE)
        except services.OwnListing:
            return StapelErrorResponse(400, ERR_400_OWN_LISTING)

    return wrapper


@extend_schema(tags=["Classified / conversations"])
class ConversationConfirmView(StapelAPIView):
    """Confirm a contact about a listing, and answer the header to render.

    **200, not 201**: since 0.3.2 this creates nothing. The thread is chat's
    and carries its own subject; what happens here is the check no other
    module in the fleet can make — the listing exists, the caller is not its
    seller, and chat agrees the caller is in that thread and that it really is
    about that listing.

    A blocked pair never reaches this endpoint: chat refuses them the thread
    at `create_direct` (0.6.1). A pair that already HAS a thread is confirmed
    here even while the block provider is down — that is a read of history,
    and the composite stopped putting an outage in front of one in 0.4.0.
    """

    permission_classes = [IsNotAnonymousUser]
    stapel_anonymous_access = ANONYMOUS_DENIED
    request_serializer_class = ConversationConfirmSerializer
    response_serializer_class = ConversationContextResponseSerializer

    @extend_schema(
        request=ConversationConfirmSerializer,
        responses={200: ConversationContextResponseSerializer},
    )
    @_maps_errors
    def post(self, request):
        payload = self.get_request_serializer_class()(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        context = services.confirm_listing_conversation(
            conversation_id=data["conversation_id"],
            listing_key=data["listing_id"],
            actor_id=request.user.pk,
        )
        return StapelResponse(self.get_response_serializer_class()(context).data)


@extend_schema(tags=["Classified / conversations"])
class ConversationContextView(StapelAPIView):
    """The header of one conversation.

    A conversation the caller is not a party of answers 404, exactly like one
    that does not exist. A 403 would confirm the id names a real thread, and
    the id is the only thing keeping a stranger's conversation unprobed.
    """

    permission_classes = [IsNotAnonymousUser]
    stapel_anonymous_access = ANONYMOUS_DENIED
    response_serializer_class = ConversationContextResponseSerializer

    @extend_schema(responses={200: ConversationContextResponseSerializer})
    @_maps_errors
    def get(self, request, conversation_id):
        context = services.conversation_context(
            conversation_id, viewer_id=request.user.pk
        )
        return StapelResponse(self.get_response_serializer_class()(context).data)


@extend_schema(tags=["Classified / conversations"])
class ConversationContextBatchView(StapelAPIView):
    """Headers for a page of the inbox, in one call.

    A conversation list that resolves its cards one request per row is a list
    that does not open. The page is bounded by ``CONTEXT_BATCH_LIMIT`` and
    costs two comm reads plus one rating read per distinct counterparty,
    whatever the page size.

    POST rather than GET because the body is a list of ids: a query string of
    fifty UUIDs is a proxy limit waiting to be discovered in production.
    """

    permission_classes = [IsNotAnonymousUser]
    stapel_anonymous_access = ANONYMOUS_DENIED
    request_serializer_class = ConversationContextQuerySerializer
    response_serializer_class = ConversationContextPageResponseSerializer

    @extend_schema(
        request=ConversationContextQuerySerializer,
        responses={200: ConversationContextPageResponseSerializer},
    )
    @_maps_errors
    def post(self, request):
        payload = self.get_request_serializer_class()(data=request.data)
        payload.is_valid(raise_exception=True)
        asked = [str(cid) for cid in payload.validated_data["conversation_ids"]]

        items = services.conversation_contexts(asked, viewer_id=request.user.pk)
        return StapelResponse(
            self.get_response_serializer_class()(
                {
                    "items": items,
                    "missing": [cid for cid in asked if cid not in items],
                }
            ).data
        )


__all__ = [
    "ConversationConfirmView",
    "ConversationContextBatchView",
    "ConversationContextView",
]
