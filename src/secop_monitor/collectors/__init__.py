import pytz

from src.secop_monitor.config import Config
from src.secop_monitor.collectors.base import Collector
from src.secop_monitor.collectors.fixture import FixtureCollector
from src.secop_monitor.collectors.secop_api import SecopApiCollector

def get_collector(config: Config) -> Collector:
    """Fábrica de collectors basada en la configuración."""
    app_timezone = config.get_timezone()
    
    if config.source.collector == "fixture":
        return FixtureCollector(
            fixture_path=config.source.fixture_path,
            app_timezone=app_timezone
        )
    elif config.source.collector == "secop_api":
        if not config.source.secop_api:
            raise ValueError("Configuración de SECOP API faltante.")
        return SecopApiCollector(
            base_url=config.source.secop_api.base_url,
            auth=config.source.secop_api.auth,
            app_timezone=app_timezone
        )
    raise ValueError(f"Collector desconocido: {config.source.collector}")
