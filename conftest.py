def pytest_configure(config):
    from django.conf import settings

    if not settings.configured:
        # stapel_geo is deliberately NOT installed here: its models need
        # the GDAL C stack (same policy as stapel-geo's own non-spatial
        # test mode). The preset still lists it; e2e coverage is the
        # assembled project, not this unit harness.
        settings.configure(
            SECRET_KEY="test-secret-key-not-for-production",
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
                "django.contrib.sessions",
                "django.contrib.admin",
                "django.contrib.messages",
                "stapel_core.django.apps.CommonDjangoConfig",
                "stapel_core.django.users",
                "stapel_core.django.projections",
                "stapel_categories",
                "stapel_listings",
                "stapel_reviews",
                "stapel_shop",
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
            CACHES={
                "default": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                }
            },
            STAPEL_COMM={
                "OUTBOX_ENABLED": False,
                "ACTION_TRANSPORT": "inprocess",
            },
        )
        import django

        django.setup()
