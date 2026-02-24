from src.secop_monitor.config import Config
from src.secop_monitor.notifier.base import Notifier
from src.secop_monitor.notifier.stdout import StdoutNotifier
from src.secop_monitor.notifier.slack import SlackNotifier

def get_notifier(config: Config) -> Notifier:
    """Fábrica de Notifiers basándose en la configuración principal."""
    if config.app.notifier == "slack":
        return SlackNotifier(config.notifications.slack)
    return StdoutNotifier()
