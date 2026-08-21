from django.apps import AppConfig

# The app slot carries the composite's cross-domain glue
# (projections-and-composition §3). It stays mounted even though the module
# serves no HTTP of its own (STAPEL_LIBS: django_app=True, http=False), which
# is what let `search_sources` land here without a breaking change to
# consumers' INSTALLED_APPS.
#
# ready() deliberately imports nothing. `search_sources` is resolved by dotted
# path out of STAPEL_SEARCH["SOURCES"] when stapel-search wires its registry,
# and importing it here would only make the composite's app order matter.


class ClassifiedConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "stapel_classified"
    label = "classified"
    verbose_name = "Stapel Classified (composite)"
