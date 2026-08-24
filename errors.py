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
#: Deliberately unspecific. A blocked user is told the seller cannot be
#: contacted, never that they were blocked or by whom: naming the block turns
#: a quiet boundary into a notification, and a marketplace's block exists
#: precisely so the other person stops receiving anything.
ERR_403_CONTACT_REFUSED = "error.403.classified_contact_refused"
ERR_503_BLOCKS_UNAVAILABLE = "error.503.classified_blocks_unavailable"

STAPEL_CLASSIFIED_ERRORS = {
    ERR_404_LISTING_NOT_FOUND: "This listing no longer exists",
    ERR_404_CONVERSATION_NOT_FOUND: "Conversation not found",
    ERR_400_OWN_LISTING: "You cannot start a buyer conversation on your own listing",
    ERR_403_CONTACT_REFUSED: "This seller cannot be contacted",
    ERR_503_BLOCKS_UNAVAILABLE: "Contacts are temporarily unavailable, try again shortly",
}

#: What a client can actually DO about each refusal (core's REMEDIATION_VOCAB).
STAPEL_CLASSIFIED_REMEDIATION = {
    ERR_404_LISTING_NOT_FOUND: "verify",
    ERR_404_CONVERSATION_NOT_FOUND: "verify",
    ERR_400_OWN_LISTING: "fix_input",
    ERR_403_CONTACT_REFUSED: "contact_support",
    ERR_503_BLOCKS_UNAVAILABLE: "wait_and_retry",
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
