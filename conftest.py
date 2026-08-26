# The block harness this module SHIPS (`stapel_classified.testing`) is loaded
# by its `pytest11` entry point — the same way a consumer gets it, so this
# suite exercises the real delivery mechanism rather than a private import.
#
# Do NOT also name it in `pytest_plugins`: pytest registers an entry-point
# plugin under its entry-point name and a `pytest_plugins` entry under its
# module name, and the second registration of the same module is
# `ValueError: Plugin already registered under a different name`. It passed
# here and died on the runner for one release, because a stale editable
# install had not yet recorded the entry point — the same "green in my venv"
# shape `tests/test_test_dependencies.py` exists for.


def pytest_configure(config):
    from django.conf import settings

    if not settings.configured:
        # stapel_geo is deliberately NOT installed here: its models need
        # the GDAL C stack (same policy as stapel-geo's own non-spatial
        # test mode). The preset still lists it; e2e coverage is the
        # assembled project, not this unit harness.
        #
        # stapel_search and stapel_moderation ARE installed, and the preset's
        # own SETTINGS_DEFAULTS are the settings under test — the point of
        # this harness is that the composite's declarations actually wire up
        # against the real member modules, not that they parse.
        #
        # stapel_chat (+ stapel_realtime, its WebSocket substrate) is NOT a
        # member of this composite: it owns no part of the preset, and this
        # module is not allowed to know what a message is. It is mounted HERE
        # because the composite now READS chat — the `chat_message` target
        # type names `chat.moderation_content`, and the conversation header is
        # built on `chat.conversation_participants` — and this file's own rule
        # is that a double on either side of a seam is the one thing that
        # cannot prove it. Mounting chat brings its deployment checks
        # (E010-E014) with it, which is why the realtime settings below are
        # real — the mirror of stapel-chat's own harness, which mounts
        # stapel_moderation for exactly this reason.
        #
        # stapel_profiles is mounted for the same reason and it is the newer
        # one: BLOCK_ENFORCEMENT defaults to "required", so every test in this
        # suite runs against a REGISTERED `profiles.relationships` provider or
        # it is not running against this module's default posture at all. A
        # fixture that registered a block double would have been a suite
        # asserting its own idea of profiles; the block a test sets up here is
        # a real `UserRelationship` row read by profiles' real provider. The
        # three tests that assert the no-provider posture unregister it
        # explicitly (`no_block_provider`) — that state is a deployment
        # WITHOUT profiles, which is a thing to construct, not to inherit.
        from stapel_classified import preset

        settings.configure(
            SECRET_KEY="test-secret-key-not-for-production-and-long-enough-for-prodguard",
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
                "django.contrib.sessions",
                "django.contrib.admin",
                "django.contrib.messages",
                "rest_framework",
                "stapel_core.django.apps.CommonDjangoConfig",
                "stapel_core.django.users",
                "stapel_core.django.projections",
                "stapel_categories",
                "stapel_listings",
                "stapel_reviews",
                "stapel_shop",
                "stapel_search",
                "stapel_moderation",
                # In INSTALLED_APPS because it carries the system checks and
                # registers the "channels" signal transport from its
                # AppConfig.ready() — the two lines a host with chat writes.
                "stapel_realtime",
                "stapel_chat",
                # Serves profiles.relationships / .display_names /
                # .public_cards — the three reads the header and the block
                # check make. See the note above.
                "stapel_profiles",
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
            ROOT_URLCONF="stapel_classified.tests.urls",
            # A *realistic* host, not the smallest one that imports: this is
            # what `manage.py check` is run against in
            # tests/test_composite.py, and a check run against a settings
            # stub proves nothing about a deployment.
            # stapel_core.django.settings.COMMON_MIDDLEWARE verbatim —
            # spelled out because importing stapel_core.django pulls DRF in
            # before settings.configure() has run. BootGateMiddleware first
            # is the point: without it the E-gates never reach a gunicorn
            # worker (stapel_core.boot.W002).
            MIDDLEWARE=[
                "stapel_core.django.boot.BootGateMiddleware",
                "django.middleware.security.SecurityMiddleware",
                "corsheaders.middleware.CorsMiddleware",
                "django.contrib.sessions.middleware.SessionMiddleware",
                "django.middleware.common.CommonMiddleware",
                "stapel_core.django.jwt.middleware.CsrfExemptAPIMiddleware",
                "django.middleware.csrf.CsrfViewMiddleware",
                "django.contrib.auth.middleware.AuthenticationMiddleware",
                "stapel_core.django.jwt.middleware.JWTAuthMiddleware",
                "stapel_core.django.admin.redirect.AdminLoginRedirectMiddleware",
                "stapel_core.django.jwt.middleware.ServiceAPIKeyMiddleware",
                "django.contrib.messages.middleware.MessageMiddleware",
                "django.middleware.clickjacking.XFrameOptionsMiddleware",
            ],
            TEMPLATES=[
                {
                    "BACKEND": "django.template.backends.django.DjangoTemplates",
                    "APP_DIRS": True,
                    "OPTIONS": {
                        "context_processors": [
                            "django.template.context_processors.request",
                            "django.contrib.auth.context_processors.auth",
                            "django.contrib.messages.context_processors.messages",
                        ]
                    },
                }
            ],
            STATIC_URL="/static/",
            # URL *names*, not root-relative paths: a mount prefix must not
            # be able to 404 the login redirect (stapel_core.mounts.W001).
            LOGIN_URL="admin:login",
            LOGIN_REDIRECT_URL="admin:index",
            CACHES={
                "default": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                }
            },
            STAPEL_COMM={
                "OUTBOX_ENABLED": False,
                "ACTION_TRANSPORT": "inprocess",
                # Screening runs in the web process here; a real deployment
                # uses "action"/"bus" so task.requested leaves it.
                "TASK_DISPATCH": "inline",
                "TASK_EXECUTOR": "inline",
                # stapel-chat's ephemeral frames (typing, receipts, the inbox
                # stream) ride this one; without it they are dropped silently
                # and chat says so as E013.
                "SIGNAL_TRANSPORT": "channels",
            },
            # In-memory layer: enough for a single-process run, and what
            # stapel-chat's own harness uses (E011 wants a 'default').
            CHANNEL_LAYERS={
                "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
            },
            STAPEL_REALTIME={
                # Exact origins, ports included — an entry without the port
                # is an allowlist that silently never matches (realtime.E003),
                # and an empty one is cross-site WebSocket hijacking of a live
                # conversation where the socket authenticates by cookie
                # (stapel_chat.E014).
                "ALLOWED_ORIGINS": ["http://testserver"],
            },
            # The Postgres backend is the module default and needs Postgres;
            # this harness runs the naive engine on SQLite. The seam is
            # stapel-search's to prove across engines (its own e2e runs both),
            # not the composite's — what the composite must prove is that its
            # source declaration round-trips through whichever engine is on.
            STAPEL_SEARCH={
                **preset.SETTINGS_DEFAULTS["STAPEL_SEARCH"],
                "BACKEND": "stapel_search.backends.naive.NaiveSearchBackend",
            },
            STAPEL_MODERATION={
                **preset.SETTINGS_DEFAULTS["STAPEL_MODERATION"],
                # No LLM provider in a unit harness: screening is off, so a
                # submitted listing waits for a human instead of hanging on a
                # retry ladder against nothing.
                "SCREEN_ENABLED": False,
            },
            # The preset's own chat declaration, under test: the `listing`
            # subject type chat refuses to store without, and the "required"
            # block posture this composite sets over chat's "auto". A harness
            # that spelled its own would prove nothing about the preset.
            STAPEL_CHAT=preset.SETTINGS_DEFAULTS["STAPEL_CHAT"],
            STAPEL_REVIEWS=preset.SETTINGS_DEFAULTS["STAPEL_REVIEWS"],
            STAPEL_LISTINGS={"REQUIRE_IMAGE_ON_PUBLISH": False},
        )
        import django

        django.setup()

        from stapel_core.comm.schemas import autoload_schemas

        autoload_schemas()
