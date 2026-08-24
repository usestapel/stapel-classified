"""Single-module Django settings for stapel-classified's own contract.

One ``settings.configure(...)`` block for the emission harness and the
capabilities emitter, so the two cannot drift. The TEST suite deliberately
does NOT use it: a composite's tests must boot every member (that is the only
claim a composite makes), while the contract is emitted from this package's
own surface alone — mixing the two would put stapel-listings' endpoints in
stapel-classified's schema.json.

``SPECTACULAR_SETTINGS`` is not set here for the reason every sibling harness
states: drf-spectacular builds its settings singleton at import time, before a
``configure()``-based harness can populate it. The one knob that must be
forced, ``SCHEMA_PATH_PREFIX``, is patched on the singleton by ``_codegen``.
"""
from __future__ import annotations


def settings_kwargs(*, root_urlconf: str = "stapel_classified.codegen_urls") -> dict:
    """The ``settings.configure(**kwargs)`` for a single-module instance."""
    return dict(
        SECRET_KEY="test-secret-key-not-for-production",
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            "django.contrib.sessions",
            "django.contrib.messages",
            "stapel_core.django.apps.CommonDjangoConfig",
            "stapel_core.django.users",
            "rest_framework",
            "drf_spectacular",
            "stapel_classified",
        ],
        AUTH_USER_MODEL="users.User",
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        USE_TZ=True,
        ROOT_URLCONF=root_urlconf,
        CACHES={
            "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
        },
        # Mirror stapel_core.django.settings.REST_FRAMEWORK exactly (the
        # config a real deployment emits under). Inlined, not imported, to
        # dodge the import-time settings read.
        REST_FRAMEWORK={
            "DEFAULT_AUTHENTICATION_CLASSES": [
                "stapel_core.django.jwt.authentication.JWTCookieAuthentication",
            ],
            "DEFAULT_PERMISSION_CLASSES": [
                "stapel_core.django.api.permissions.IsServiceRequest",
                "stapel_core.django.api.permissions.IsSuperUser",
            ],
            "DEFAULT_RENDERER_CLASSES": [
                "rest_framework.renderers.JSONRenderer",
                "rest_framework.renderers.BrowsableAPIRenderer",
            ],
            "DEFAULT_SCHEMA_CLASS": "stapel_core.django.openapi.schemas.PermissionAwareAutoSchema",
            "EXCEPTION_HANDLER": "stapel_core.django.api.errors.stapel_exception_handler",
        },
        STAPEL_COMM={
            "OUTBOX_ENABLED": False,
            "ACTION_TRANSPORT": "inprocess",
            "VALIDATE_SCHEMAS": True,
        },
        MIGRATION_MODULES={"users": None},
    )


# The multi-module common path prefix drf-spectacular auto-detects inside an
# all-modules aggregate. Forced on the singleton by the harness so a
# single-module instance derives the same operationIds.
CODEGEN_SCHEMA_PATH_PREFIX = "/"
