import os
import sys
from contextlib import contextmanager
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python load_fixture_without_signals.py <fixture_path>")
        return 1

    fixture_path = Path(sys.argv[1]).resolve()
    if not fixture_path.exists():
        print(f"Fixture not found: {fixture_path}")
        return 1

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "siloxr.settings.production")
    os.environ.setdefault("DB_BACKEND", "postgres")

    import django

    django.setup()

    from django.core.serializers import deserialize
    from django.db import transaction
    from django.db.models.signals import post_save

    from apps.engine import signals as engine_signals
    from apps.inventory.models import BurnRate, ForecastSnapshot, InventoryEvent

    @contextmanager
    def suspended_engine_signals():
        post_save.disconnect(engine_signals.trigger_learning_on_event, sender=InventoryEvent)
        post_save.disconnect(engine_signals.trigger_forecast_on_burn_rate, sender=BurnRate)
        post_save.disconnect(engine_signals.trigger_decision_on_forecast, sender=ForecastSnapshot)
        try:
            yield
        finally:
            post_save.connect(engine_signals.trigger_learning_on_event, sender=InventoryEvent)
            post_save.connect(engine_signals.trigger_forecast_on_burn_rate, sender=BurnRate)
            post_save.connect(engine_signals.trigger_decision_on_forecast, sender=ForecastSnapshot)

    text = fixture_path.read_text(encoding="utf-8")
    count = 0

    with suspended_engine_signals():
        with transaction.atomic():
            for obj in deserialize("json", text, ignorenonexistent=True):
                obj.save()
                count += 1

    print(f"Imported {count} objects from {fixture_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
