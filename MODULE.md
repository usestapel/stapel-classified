# MODULE.md — stapel-classified (agent-facing extension map)

A composite: INSTALLED_APPS/urls/config preset over existing Stapel modules,
plus the cross-domain declarations that no member is allowed to write.
It writes NO business logic and mounts NO urls of its own (`http=False`,
`django_app=True` in STAPEL_LIBS — the app slot exists for glue).

Members: **shop** (categories + attributes + listings + reviews) + **geo** +
**search** + **moderation**.

## What the composite declares

Two members ship deliberately EMPTY registries, because neither is allowed to
know what a listing or a review is. This package is the one place that knows
both sides, so it is where they meet:

| Registry | Owner | Entry declared here |
|---|---|---|
| `STAPEL_SEARCH["SOURCES"]` | stapel-search (`BUILTIN_SOURCES = {}`) | `listing` -> `stapel_classified.search_sources.listing_source` |
| `STAPEL_MODERATION["TARGET_TYPES"]` | stapel-moderation (`BUILTIN_TARGET_TYPES = {}`) | `listing`, `review` |
| `STAPEL_REVIEWS["TARGET_TYPES"]` | stapel-reviews (`BUILTIN_TARGET_TYPES = {}`) | `listing` |
| `shop.listing_review_summary` | stapel-shop | the reviews->listings rating projection |

### The `listing` search source

`stapel_classified/search_sources.py` is the only executable glue in this
package: `listings.search_documents` / `listings.search_export` in,
`SearchDocumentInput` out, invalidated by `listing.published` /
`listing.updated` / `listing.removed`. Registering it is also what wires the
subscribers — a host writes no signal handler.

Two properties worth knowing before you extend it:

- **`visible_statuses` is read from `stapel_listings.models.INDEXED_STATUSES`**,
  not copied. A lifecycle state added upstream cannot leave the index's idea
  of "live" behind.
- **Facets come from `features_search`, not from stapel-attributes DAOs.**
  `listings.search_documents` does not serve the DAO list, so the mapper takes
  stapel-search's declared fallback (`ACCEPT_FEATURES_SEARCH`). The loss is
  real: every attribute lands as a *term*, so `r.<slug>` range filters over
  listing attributes do not work and `hex_color`'s `simple` axis and unit
  context are gone. Closing it is one field in listings' document builder plus
  dropping `features_search=` for `features=` here.

### The two moderation target types

`listing` is **pre**-publication (`listing.submitted` opens the case, nothing
is public until the verdict) and `review` is **post** (published on arrival, a
verdict is a takedown). Both name their owner's `*.moderation_content` under
that owner's own id spelling (`listing_id` / `review_id`).

`profile` is deliberately absent: stapel-profiles is not a member, so a policy
for it would point at a content function nobody serves.

`preset.RECOMMENDED_ACCESS_ROLES` names the moderator clearances the module
documents. It is NOT merged into `SETTINGS_DEFAULTS` — a role table is a host's
org chart, and a composite that installed one would hand out staff mandates a
deployment never asked for.

## Seams

- `preset.INSTALLED_APPS` / `preset.URL_INCLUDES` / `preset.SETTINGS_DEFAULTS`
  — plain data; a project copies or references them. Override per-project by
  editing the project's own settings, not this package.
- `search_sources.map_listing` / `listing_source` — replace either in your own
  `STAPEL_SEARCH["SOURCES"]["listing"]` if your product's card or text arm
  differs; the rest of the wiring is unchanged.
- Member modules keep ALL their own seams (each module's MODULE.md).
- Composition changes (add/remove a member) = a MINOR bump of this package
  (pre-1.0 house semver: minor = breaking).

## Mount canon

`stapel-categories` and `stapel-listings` contribute only the `v1/` segment
and are mounted under `<mod>/api/`; `stapel-reviews`, `geo`, `search` and
`moderation` bake `api/v1/` in themselves and are mounted at `<mod>/`. Both
shapes end at `/<mod>/api/v1/...`, which is what `stapel_core.mounts.E004`
requires. `tests/test_composite.py` runs the whole system-check suite against
the preset's own URLconf, so a mount that drifts fails here.

## Host actions this composite does not take

- **`STAPEL_ACCESS["ROLES"]`** — see `RECOMMENDED_ACCESS_ROLES` above.
- **`STAPEL_GDPR["DATA_OWNERS"]`** — add `"moderation"` (and bump
  `DATA_OWNERS_VERSION`) if you run stapel-gdpr; moderation stores complaint
  text and complainant identities, and the erasure closure never completes
  without the declaration (`moderation.W005` / `gdpr.E002`).
- **`STAPEL_MODERATION["APPEAL_URL_TEMPLATE"]`** — empty by default, and an
  empty appeal link is what DSA Art. 17 notices.
- **A screener** — `SCREEN_ENABLED` is on by default and
  `ON_SCREENING_FAILURE="hold"`, so with no LLM provider configured every
  submission queues for a human rather than publishing unscreened.
