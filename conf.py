"""Settings namespace for stapel-classified.

Read through ``classified_settings`` (lazily, at call time) — never via a
module-level ``os.getenv``, whose value would freeze at import. Resolution
order per key: ``settings.STAPEL_CLASSIFIED`` dict -> flat Django setting of
the same name -> environment variable -> default below.

Every key here is either an **axis** (it changes what the module does) or a
**comm Function name** (it changes WHOM the module asks) — and a fact another
module owns gets neither: block enforcement is stapel-chat's axis and this
namespace stopped carrying a copy of it in 0.4.0. There is no
registry in this namespace on purpose: the composite has exactly one subject
type today (``listing``) and one consumer of it, and a merge-registry built
before its second entry exists is a seam that documents itself and nothing
else. The names below are the seam — point one at your own provider and the
answer changes with no fork.

Why a composite has a settings namespace at all
-----------------------------------------------
Because it makes the cross-domain JOIN — the conversation header no member
can build alone — and every module it asks is named here rather than
imported. It owns no table any more: ``ConversationSubject`` was deleted in
0.3.2 once stapel-chat 0.6.0 grew subjects of its own, and a composite that
kept a second copy of somebody else's fact would be the thing §7 of the v2
verdicts forbids.
"""
from stapel_core.conf import AppSettings

#: AppSettings-shaped literal dict (capability-config.md §2): a top-level
#: DEFAULTS lets the capabilities emitter introspect axis keys/kinds without
#: re-parsing the AppSettings() call.
DEFAULTS = {
    # ── Blocking is NOT an axis here ──────────────────────────────────
    # There is deliberately no BLOCK_* key in this namespace. stapel-chat
    # owns both write doors a block has to hold — opening a direct thread
    # (0.6.1) and sending into one (0.6.0) — and reads them from
    # STAPEL_CHAT. This composite states its product knowledge as a VALUE on
    # that axis (`preset.SETTINGS_DEFAULTS["STAPEL_CHAT"]["BLOCK_ENFORCEMENT"]
    # = "required"`), never as a second axis: two switches for one fact means
    # an operator turns one and behaviour is decided by the other.
    # `checks.E003` catches a deployment that still sets the old keys here.

    # ── The conversation ─────────────────────────────────────────────
    # Who is in a thread, and what it is about. stapel-chat >= 0.6.0 serves
    # it; this is the read that replaced the composite's own binding table,
    # and it is the one seam that has no degraded form — see
    # services.ChatUnavailable for why an empty answer would be a lie.
    "CONVERSATION_PARTICIPANTS_FUNCTION": "chat.conversation_participants",

    # ── The cards ────────────────────────────────────────────────────
    # Listing documents. `listings.search_documents` serves every status
    # (only an unknown or soft-deleted key is absent), which is precisely why
    # the card can answer "sold" and "gone" instead of 404 — the state a
    # buyer is most confused by is the one a public read hides.
    "LISTING_DOCUMENTS_FUNCTION": "listings.search_documents",
    # Display names for the counterparty card. Names only — everything richer
    # waits for the function below.
    "DISPLAY_NAMES_FUNCTION": "profiles.display_names",
    # Public profile cards (avatar as the fleet image object, member-since as
    # a date, seller type). stapel-profiles >= 0.16.0 serves it; a deployment
    # without profiles sets "" and the counterparty card answers "partial".
    "PUBLIC_PROFILE_FUNCTION": "profiles.public_cards",
    # Rating aggregate for the counterparty card.
    "SELLER_RATING_FUNCTION": "reviews.aggregate",
    # The reviews target type a seller's rating is keyed under. Empty = this
    # deployment has no seller reviews, and the card says `rating: null`
    # rather than inventing a zero.
    "SELLER_RATING_TARGET_TYPE": "",
    # CDN render metadata for the card's primary image — the same contract
    # stapel-chat uses for attachments, so one picture has one answer.
    "MEDIA_DESCRIBE_FUNCTION": "cdn.describe_many",
    # Widest CDN variant a card asks about. A card is a thumbnail; a client
    # that wants the gallery opens the listing.
    "CARD_IMAGE_TIER": 480,
    # How many of a listing's photos a CARD carries. The gallery belongs to
    # the listing and this is the only thing decided here: a result row is a
    # glance, and the person who wants photo eleven opens the listing. Ten is
    # what a swipeable SERP strip is worth — below that a phone card runs out
    # of photos mid-swipe, above it the stored card grows for slides nobody
    # reaches. Tuning, deliberately not an axis.
    "CARD_IMAGES_LIMIT": 10,
    # Template for the public listing URL a moderator's card links to.
    "LISTING_URL_TEMPLATE": "",
    # Template for the public seller URL a moderator's card links to.
    "SELLER_URL_TEMPLATE": "",

    # ── Bounds ───────────────────────────────────────────────────────
    # Conversations resolved in one batch call. The chat inbox is the caller
    # and it pages; this is the ceiling on one page. Kept at stapel-cdn's own
    # describe_many limit, because that call is the widest thing a batch of
    # cards fans out into.
    "CONTEXT_BATCH_LIMIT": 50,
    # Seconds any single comm read above may take before the card degrades to
    # its partial form. A chat that will not open because a rating service is
    # slow is worse than a chat with no stars in it.
    "CALL_TIMEOUT_SECONDS": 5,
}

classified_settings = AppSettings(
    "STAPEL_CLASSIFIED",
    defaults=DEFAULTS,
    import_strings=(),
)

__all__ = ["DEFAULTS", "classified_settings"]
