from django.apps import AppConfig

# No glue projections yet — this app slot exists so that, when cross-domain
# glue appears (projections-and-composition §3), it lands here without a
# breaking change to consumers' INSTALLED_APPS (the composite is already
# mounted as a Django app; see the STAPEL_LIBS entry: django_app=True even
# though http=False).


class ClassifiedConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "stapel_classified"
    label = "classified"
    verbose_name = "Stapel Classified (composite)"
