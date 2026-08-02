# stapel-classified

[![license](https://img.shields.io/github/license/usestapel/stapel-classified)](https://github.com/usestapel/stapel-classified/blob/main/LICENSE)
[![status](https://img.shields.io/badge/status-unreleased-orange)](https://github.com/usestapel/stapel-classified)

Не опубликовано на PyPI. Установка из исходников: `pip install git+https://github.com/usestapel/stapel-classified`
Composite: classified ads — the shop composite + geo (location-bound listings).

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
    "stapel_categories",
    "stapel_listings",
    "stapel_reviews",
    "stapel_shop",
    "stapel_geo",
    "stapel_classified",
]
for _k, _v in preset.SETTINGS_DEFAULTS.items():
    globals().setdefault(_k, _v)

# urls.py
from django.urls import include, path

urlpatterns = [
    path("categories/", include("stapel_categories.urls")),
    path("listings/", include("stapel_listings.urls")),
    path("reviews/", include("stapel_reviews.urls")),
    path("geo/", include("stapel_geo.urls")),
]
```

## Config checklist (fill these, in the generated project's CONFIG.MD too)

| Key | Note |
|-----|------|
| `STAPEL_REVIEWS["TARGET_TYPES"]` | prefilled by `stapel_classified.preset.SETTINGS_DEFAULTS` (targets `listing`) |
| `STAPEL_LISTINGS["BASE_CURRENCY"]` | default `USD` — set your currency |
| `STAPEL_GEO[...]` | geocoder provider/keys — see stapel-geo CONFIG.MD |
| listing coordinates | lat/lon are LISTING fields (no projection needed) — see stapel-listings |

## Glue

None of its own beyond what stapel-shop already carries: coordinates are the
listing's OWN fields (lat/lon on the listing), not a foreign aggregate — no
projection needed for geo.
