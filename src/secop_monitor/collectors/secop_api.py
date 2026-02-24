import datetime
import pytz

from src.secop_monitor.collectors.base import Collector
from src.secop_monitor.schemas import RawItem

class SecopApiCollector(Collector):
    """
    Collector para la API de SECOP en datos.gov.co (Socrata).
    Pendiente de implementación para MVP 2+.
    """
    
    def __init__(self, base_url: str, auth: dict | None, app_timezone: pytz.BaseTzInfo):
        self.base_url = base_url
        self.auth = auth
        self.app_timezone = app_timezone
        
    def collect(self, since: datetime.datetime, limit: int) -> list[RawItem]:
        raise NotImplementedError("La integración real con SECOP API se hará en la iteración MVP 2.")
