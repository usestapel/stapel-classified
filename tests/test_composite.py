"""Minimal composite checks: the package imports, the preset is coherent,
the Django app mounts.
"""
from stapel_classified import preset


def test_preset_is_coherent():
    # The composite's own app slot is present (glue must live in
    # INSTALLED_APPS — STAPEL_LIBS grabli 5.8) and prefixes are unique.
    assert "stapel_classified" in preset.INSTALLED_APPS
    prefixes = [p for p, _ in preset.URL_INCLUDES]
    assert len(prefixes) == len(set(prefixes))
    # The composite mounts no urls of its own (http=False — glue only).
    assert not any(m.startswith("stapel_classified") for _, m in preset.URL_INCLUDES)


def test_app_config_mounts():
    from django.apps import apps

    cfg = apps.get_app_config("classified")
    assert cfg.name == "stapel_classified"
