# CONFIG.MD — stapel-classified

Config registry ({static-scaffold-and-config.md} §2). Almost every key here
belongs to a member module (shop (categories, attributes, listings,
reviews), geo, search, moderation); see each member's CONFIG.MD (the
scaffold aggregates them all into the generated project's CONFIG.MD
automatically).

Scenario defaults live in `stapel_classified.preset.SETTINGS_DEFAULTS` — they are
settings-dict PRESETS for member keys, not new keys.

Since 0.2.0 the composite has a namespace of its OWN, because it owns one
cross-domain JOIN (a chat conversation ↔ the listing it is about) and the
reads off it. Every key in it is either an axis or a comm Function NAME:
point one at your own provider and the answer changes with no fork.

## stapel-classified — `STAPEL_CLASSIFIED`

| Key | Source | Purpose | Required | Default |
|-----|--------|---------|----------|---------|
| BLOCK_ENFORCEMENT | env | `auto` (enforce where a block provider answers; announce at boot where none does) / `required` (a missing provider is a boot ERROR, `classified.E002`) / `off` (a disclosed statement, `classified.W002`). In every state a provider that is present and FAILS answers 503 — an outage is not consent. | no | `required` |
| BLOCK_FUNCTION | env | comm Function answering "is there a block between these two". `{"pairs": [[a,b],…]} -> {"blocked": [[a,b],…]}`, either direction. stapel-profiles owns the relationship and does not publish this yet. | no | `profiles.relationships` |
| LISTING_DOCUMENTS_FUNCTION | env | Where every listing card comes from. Serves ALL statuses, which is why a card can say "sold" and "gone" where a public read 404s. | no | `listings.search_documents` |
| DISPLAY_NAMES_FUNCTION | env | The counterparty's name. | no | `profiles.display_names` |
| PUBLIC_PROFILE_FUNCTION | env | Avatar (fleet image object), member-since (date), seller type — served by stapel-profiles >= 0.16.0 as `profiles.public_cards`. Set `""` on a deployment without profiles: the counterparty card then answers `meta_status: partial`. | no | `profiles.public_cards` |
| SELLER_RATING_FUNCTION | env | The rating aggregate for a seller card. | no | `reviews.aggregate` |
| SELLER_RATING_TARGET_TYPE | env | The reviews target type a seller's rating is keyed under. Empty = this deployment has no seller reviews, and the card says `rating: null` rather than inventing a zero. | no | `""` |
| MEDIA_DESCRIBE_FUNCTION | env | CDN render metadata for the card's primary image — the same contract stapel-chat uses for an attachment. | no | `cdn.describe_many` |
| CARD_IMAGE_TIER | env | Widest CDN variant a card asks about. | no | `480` |
| LISTING_URL_TEMPLATE | env | `{listing_id}` template for the card's public link. Empty = no link rather than an invented one. | no | `""` |
| SELLER_URL_TEMPLATE | env | `{user_id}` template for the seller card's public link. | no | `""` |
| CONTEXT_BATCH_LIMIT | env | Conversations resolved in one batch call (the inbox page). Kept at stapel-cdn's own describe_many ceiling. | no | `50` |
| CALL_TIMEOUT_SECONDS | env | Per comm read, before a card degrades to its partial form. A chat that will not open because a rating service is slow is worse than a chat with no stars. | no | `5` |

## Member keys this preset fills in

Presets, not new keys — each one belongs to the member named in the header.

| Member key | Preset value | Why the composite is the one that can set it |
|---|---|---|
| `STAPEL_SEARCH["SOURCES"]["listing"]` | `stapel_classified.search_sources.listing_source` | stapel-search ships an empty source registry: it knows nothing about listings, and listings knows nothing about an index. |
| `STAPEL_MODERATION["TARGET_TYPES"]["listing"]` | pre-publication gate, `listings.moderation_content`, `listing_blocked` letter | stapel-moderation is target-generic and ships an empty registry. |
| `STAPEL_MODERATION["TARGET_TYPES"]["review"]` | post-publication gate, `reviews.moderation_content`, no letter, narrowed reason list | same, for the other target. |
| `STAPEL_MODERATION["TARGET_TYPES"]["seller"]` | post gate, `classified.seller_content` (served HERE), no verdict topic | a marketplace can be asked to act against a seller, and the fleet serves no `profiles.moderation_content` — so the composite serves the marketplace-shaped answer itself. |
| `STAPEL_MODERATION["TARGET_TYPES"]["chat_message"]` | post gate, `chat.moderation_content` keyed `message_id`, `can_report` = `classified.can_report_message` | the key is this composite's `<conversation_id>:<message_id>`: chat reads the message half, and only this package can answer off the conversation half whether the reporter was in the thread at all. Evidence-based until 0.3.0, when stapel-chat 0.5.0 started serving the content. |
| `STAPEL_MODERATION["REASONS"]` | `prohibited_item`, `misleading_price`, `already_sold`, `impersonation` | the complaint taxonomy is universal and moderation ships one; these are the codes a MARKETPLACE needs on top, merged over the built-ins. |
| `STAPEL_REVIEWS["TARGET_TYPES"]["listing"]` | post-moderated, one per author, responses allowed | stapel-reviews is target-generic and ships an empty registry. |

## Keys a host must still decide

Nothing below has a safe default a composite could invent.

| Key | Why | Consequence of leaving it |
|---|---|---|
| `STAPEL_ACCESS["ROLES"]` | The moderation console is staff-only. `preset.RECOMMENDED_ACCESS_ROLES` shows the shape and is deliberately not merged. | Nobody can open the queue. |
| `STAPEL_GDPR["DATA_OWNERS"]` | Must list `"moderation"` (and bump `DATA_OWNERS_VERSION`). | `moderation.W005` here, `gdpr.E002` there; erasure never closes over complaint data. |
| `STAPEL_MODERATION["APPEAL_URL_TEMPLATE"]` | Empty yields an empty link rather than an invented one. | Statements of reasons carry no appeal address (DSA Art. 17). |
| `STAPEL_LISTINGS["LISTING_URL_TEMPLATE"]` | Same policy on the listings side. | A moderator's card cannot link to the listing. |
| `STAPEL_SEARCH["BACKEND"]` | Defaults to Postgres. | A non-Postgres deployment must name `naive` or `meili` explicitly. |
| `STAPEL_COMM["TASK_DISPATCH"]` | Screening is a comm Task. `"inline"` runs it in the web process — a test setting. | On a real stand it must be `"action"` or `"bus"`, or screening blocks the request. |
| An `llm.complete` provider | `SCREEN_ENABLED` is on and `ON_SCREENING_FAILURE="hold"`. | Every submission queues for a human. That is the safe direction, not a silent one. |
