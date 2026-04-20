from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'

    def ready(self):
        from .signals import inventory_event_signal  # noqa: F401
