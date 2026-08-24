"""Canonical-prefix URLconf for contract emission (contract-pipeline.md §2).

Mounts the module root at ``classified/api/`` — this module contributes only
the ``v1/`` segment (api-versioning.md §2, §6), so the resulting public prefix
is ``/classified/api/v1/…``, exactly the mount recipe ``urls.py`` documents
and ``preset.URL_INCLUDES`` performs.

Declared separately from the test urlconf (which mounts the WHOLE composite)
so the emission mount can never silently drift from the documented one.
"""
from django.urls import include, path

urlpatterns = [
    path("classified/api/", include("stapel_classified.urls")),
]
