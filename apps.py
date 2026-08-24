from django.apps import AppConfig

# The app slot carries the composite's cross-domain glue
# (projections-and-composition §3). Until 0.2.0 it carried only declarations
# (`search_sources`, and the registry entries in `preset`) and served no HTTP.
# It now also owns ONE table — the conversation↔listing join — and the reads
# that hang off it, because no member is allowed to hold that join: chat may
# not know what a listing is, listings may not know what a conversation is.
# See MODULE.md, "What a composite may own".
#
# ready() imports only side-effect modules (comm functions, checks, error
# keys). `search_sources` is still resolved by dotted path out of
# STAPEL_SEARCH["SOURCES"] and importing it here would make app order matter.


class ClassifiedConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "stapel_classified"
    label = "classified"
    verbose_name = "Stapel Classified (composite)"

    def ready(self):
        # Import-time side effects only; no database access (a composite that
        # queried at ready() would break `migrate` on an empty database).
        from . import checks  # noqa: F401
        from . import errors  # noqa: F401
        from . import functions  # noqa: F401
