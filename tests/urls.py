"""URLconf for the composite's unit harness — a realistic host, not a stub.

It mounts the preset's own ``URL_INCLUDES`` verbatim, which is the point: a
prefix that produces a non-canonical path, or a module that cannot be
imported, fails ``manage.py check`` here instead of in a generated project.
``stapel_geo`` is skipped for the same reason it is absent from
``INSTALLED_APPS`` in ``conftest.py`` — its models need the GDAL C stack.

The admin is a host's, not the composite's; it is mounted here because
``LOGIN_URL``/``LOGIN_REDIRECT_URL`` must resolve (stapel_core.mounts.E001/
E002) and a host that installs ``django.contrib.admin`` and serves it nowhere
is not a configuration anybody deploys.
"""
from django.contrib import admin
from django.urls import include, path

from stapel_classified import preset

urlpatterns = [
    path(prefix, include(module))
    for prefix, module in preset.URL_INCLUDES
    if not module.startswith("stapel_geo")
] + [path("admin/", admin.site.urls)]
