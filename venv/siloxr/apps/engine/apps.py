# backend/apps/engine/apps.py

from django.apps import AppConfig


class EngineConfig(AppConfig):
    name         = "apps.engine"
    verbose_name = "SiloXR Engine"

    def ready(self):
        import apps.engine.signals  # noqa: F401