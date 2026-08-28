## Assemble (one line)

```bash
pip install stapel-tools
stapel-assemble myads --libs classified
cd myads && make test
```

That expands `classified` through the STAPEL_LIBS `requires`
closure and wires every member module into INSTALLED_APPS,
requirements.txt, urls.py and CONFIG.MD, then runs the verify gates.

## Manual wiring (no scaffold)

```python
# settings.py
from stapel_classified import preset

INSTALLED_APPS = [
    # ... django/stapel-core baseline (incl. stapel_core.django.projections)
    *preset.INSTALLED_APPS,
]
for _k, _v in preset.SETTINGS_DEFAULTS.items():
    globals().setdefault(_k, _v)

# urls.py
from django.urls import include, path

from stapel_classified import preset

urlpatterns = [
    path(prefix, include(module)) for prefix, module in preset.URL_INCLUDES
]
```

Mount from `preset.URL_INCLUDES` rather than by hand: `stapel-classified`
(its own conversation surface), `stapel-categories` and `stapel-listings`
contribute only the `v1/` segment and belong under `<mod>/api/`, while
`reviews`, `geo`, `search` and `moderation` bake `api/v1/` in themselves. Both end at `/<mod>/api/v1/...`, and getting it wrong is a
`stapel_core.mounts.E004` refusal to boot, not a cosmetic difference.

## Config checklist (fill these, in the generated project's CONFIG.MD too)

| Key | Note |
|-----|------|
| `STAPEL_REVIEWS["TARGET_TYPES"]` | prefilled by the preset (targets `listing`) |
| `STAPEL_SEARCH["SOURCES"]` | prefilled by the preset (the `listing` source) |
| `STAPEL_MODERATION["TARGET_TYPES"]` | prefilled by the preset (`listing` pre-publication, `review`/`seller`/`chat_message` post) |
| `STAPEL_CHAT["BLOCK_ENFORCEMENT"]` | prefilled `required` by the preset — the ONE block switch, and it is stapel-chat's. Chat holds both doors (opening a direct thread, sending into one) and says at every boot which state you are in. A key of this name under `STAPEL_CLASSIFIED` moved here in 0.4.0 and is a boot error (`stapel_classified.E003`). |
| `STAPEL_ACCESS["ROLES"]` | **yours** — the moderation console is staff-only; `preset.RECOMMENDED_ACCESS_ROLES` shows the shape |
| `STAPEL_GDPR["DATA_OWNERS"]` | **yours** — must list `"moderation"`, or erasure never closes over complaint data |
| `STAPEL_MODERATION["APPEAL_URL_TEMPLATE"]` | **yours** — an empty appeal link is what DSA Art. 17 notices |
| `STAPEL_SEARCH["BACKEND"]` | defaults to Postgres; name `naive` or `meili` if that is not your engine |
| `STAPEL_LISTINGS["BASE_CURRENCY"]` | default `USD` — set your currency |
| `STAPEL_GEO[...]` | geocoder provider/keys — see stapel-geo CONFIG.MD |
| listing coordinates | lat/lon are LISTING fields (no projection needed) — see stapel-listings |

## Glue

Two members ship deliberately empty registries, because neither may know what
a listing is. This package is the one place that knows both sides:

- **`STAPEL_SEARCH["SOURCES"]["listing"]`** →
  `stapel_classified.search_sources.listing_source`. Pulls documents through
  `listings.search_documents` / `listings.search_export`, invalidated by
  `listing.published` / `listing.updated` / `listing.removed`. Registering it
  is also what wires the subscribers — you write no signal handler. Facets are
  built from listings' `features_search` (stapel-search's declared lossy
  fallback: attribute *range* filters do not work until listings serves DAOs).
- **`STAPEL_MODERATION["TARGET_TYPES"]`** → `listing` (pre-publication:
  `listing.submitted` opens the case and nothing is public until the verdict)
  and `review` (post: live on arrival, a verdict is a takedown).

Coordinates need no glue at all: they are the listing's OWN fields (lat/lon on
the listing), not a foreign aggregate.

## The conversation header (0.2.0)

A chat in a classified marketplace is always ABOUT something and BETWEEN two
identified people. Neither fact belongs to the messaging engine, so this
composite owns the join and serves the header:

```
POST /classified/api/v1/conversations           bind a chat thread to a listing
GET  /classified/api/v1/conversations/{id}      one header
POST /classified/api/v1/conversations/contexts  a page of them, for the inbox
```

A header carries the **short listing card** — title, price, primary image
with CDN render metadata, and a `state` of `available` / `unavailable`
(sold, paused, expired) / `gone`, which is the answer a public listing read
cannot give and exactly the case a buyer is most confused by — plus the
**counterparty's public seller card**. Never more of a person than their
public profile.

`docs/frontend-contract.md` is the document the default skins build against:
every payload, every refusal, and the six things the fleet does not serve yet
with what the UI does about each in the meantime.
