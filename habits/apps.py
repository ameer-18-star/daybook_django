from django.apps import AppConfig


class HabitsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'habits'

    def ready(self):
        # No-op unless DAYBOOK_ENABLE_SCHEDULER=1 — see scheduler.py's
        # docstring for why this is opt-in rather than automatic.
        from . import scheduler
        scheduler.start()
