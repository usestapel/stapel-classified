"""Root URLconf for stapel-classified — v1 canon mount (api-versioning.md §2).

Canon: ``/<mod>/api/v1/...``. This module contributes ``v1/`` only, so a host
mounts it under ``classified/api/`` — the stapel-categories / stapel-listings
shape, and what ``preset.URL_INCLUDES`` does:

    path("classified/api/", include("stapel_classified.urls"))

The composite served no HTTP at all until 0.2.0; see MODULE.md for what
changed and why a composite is allowed to serve this particular surface.
"""
from django.urls import include, path

urlpatterns = [
    path("v1/", include("stapel_classified.urls_v1")),
]
