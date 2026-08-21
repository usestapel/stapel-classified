# CONFIG.MD — stapel-classified

Config registry ({static-scaffold-and-config.md} §2). This composite reads
NO configuration keys of its own — every key belongs to a member module
(shop (categories, attributes, listings, reviews), geo, search, moderation);
see each member's CONFIG.MD (the scaffold aggregates them all
into the generated project's CONFIG.MD automatically).

Scenario defaults live in `stapel_classified.preset.SETTINGS_DEFAULTS` — they are
settings-dict PRESETS for member keys, not new keys.

## stapel-classified

| Key | Source | Purpose | Required | Default |
|-----|--------|---------|----------|---------|

## Member keys this preset fills in

Presets, not new keys — each one belongs to the member named in the header.

| Member key | Preset value | Why the composite is the one that can set it |
|---|---|---|
| `STAPEL_SEARCH["SOURCES"]["listing"]` | `stapel_classified.search_sources.listing_source` | stapel-search ships an empty source registry: it knows nothing about listings, and listings knows nothing about an index. |
| `STAPEL_MODERATION["TARGET_TYPES"]["listing"]` | pre-publication gate, `listings.moderation_content`, `listing_blocked` letter | stapel-moderation is target-generic and ships an empty registry. |
| `STAPEL_MODERATION["TARGET_TYPES"]["review"]` | post-publication gate, `reviews.moderation_content`, no letter, narrowed reason list | same, for the other target. |
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
