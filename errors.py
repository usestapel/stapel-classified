"""i18n error keys of stapel-classified.

Only ``error.<status>.classified_<slug>`` keys leave this package — human
strings are translations, never literals in a response. The English registry
below is the source; ``translations/errors.<lang>.json`` ships the localized
catalogues in the same release, because owning a key means shipping its
catalogue.
"""
from stapel_core.django.api.errors import ErrorKeysView, register_service_errors

# ── Conversation subjects ────────────────────────────────────────────
ERR_404_LISTING_NOT_FOUND = "error.404.classified_listing_not_found"
ERR_404_CONVERSATION_NOT_FOUND = "error.404.classified_conversation_not_found"
ERR_400_OWN_LISTING = "error.400.classified_own_listing"

# ── Contact ──────────────────────────────────────────────────────────
# No block key here since 0.4.0. A blocked pair is refused by stapel-chat, at
# the door it owns (`create_direct` -> `error.403.chat_send_refused`, and
# `error.503.chat_blocks_unavailable` when the provider is present and
# failing). Two keys for one refusal would let a client tell "refused to open"
# from "refused to send", which is itself the disclosure non-disclosure exists
# to prevent.

# ── The conversation itself ──────────────────────────────────────────
#: Chat owns both halves of a conversation header's provenance (who is in the
#: thread, what it is about) since 0.3.2, so a chat outage is a 503 here and
#: never an empty page: an empty page reads as "you are not a party to any of
#: these", which is a permission answer, not an outage.
ERR_503_CHAT_UNAVAILABLE = "error.503.classified_chat_unavailable"

STAPEL_CLASSIFIED_ERRORS = {
    ERR_404_LISTING_NOT_FOUND: "This listing no longer exists",
    ERR_404_CONVERSATION_NOT_FOUND: "Conversation not found",
    ERR_400_OWN_LISTING: "You cannot start a buyer conversation on your own listing",
    ERR_503_CHAT_UNAVAILABLE: "Conversations are temporarily unavailable, try again shortly",
}

#: What a client can actually DO about each refusal (core's REMEDIATION_VOCAB).
STAPEL_CLASSIFIED_REMEDIATION = {
    ERR_404_LISTING_NOT_FOUND: "verify",
    ERR_404_CONVERSATION_NOT_FOUND: "verify",
    ERR_400_OWN_LISTING: "fix_input",
    ERR_503_CHAT_UNAVAILABLE: "wait_and_retry",
}

register_service_errors(
    STAPEL_CLASSIFIED_ERRORS, remediation=STAPEL_CLASSIFIED_REMEDIATION
)


class ClassifiedErrorKeysView(ErrorKeysView):
    """The error-key listing the stapel-translate collector reads."""

    def get_service_errors(self):
        return STAPEL_CLASSIFIED_ERRORS


__all__ = (
    [name for name in dir() if name.startswith("ERR_")]
    + [
        "STAPEL_CLASSIFIED_ERRORS",
        "STAPEL_CLASSIFIED_REMEDIATION",
        "ClassifiedErrorKeysView",
    ]
)
