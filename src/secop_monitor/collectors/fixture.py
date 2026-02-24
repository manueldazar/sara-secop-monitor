import datetime
import json
import logging
from typing import Any
import pytz

from src.secop_monitor.collectors.base import Collector
from src.secop_monitor.schemas import RawItem

logger = logging.getLogger(__name__)

class FixtureCollector(Collector):
    """
    Collector que lee datos de un JSON local e imita ser SECOP.
    Ideal para testing y pruebas offline.
    """
    
    def __init__(self, fixture_path: str, app_timezone: pytz.BaseTzInfo):
        self.fixture_path = fixture_path
        self.app_timezone = app_timezone
        
    def _parse_datetime(self, date_str: str | None) -> datetime.datetime | None:
        """Convierte un string en ISO a UTC asumiendo ingenuamente la timezone de la app."""
        if not date_str:
            return None
            
        try:
            # Parse naive
            dt = datetime.datetime.fromisoformat(date_str)
            if dt.tzinfo is None:
                # Localizar primero a la timezone de la app, luego llevar a UTC
                dt = self.app_timezone.localize(dt)
            return dt.astimezone(datetime.timezone.utc)
        except ValueError as e:
            logger.warning(f"Error parseando datetime '{date_str}': {e}")
            return None

    def collect(self, since: datetime.datetime, limit: int) -> list[RawItem]:
        logger.info(f"Recolectando datos del fixture {self.fixture_path} desde {since} (límite: {limit})")
        try:
            with open(self.fixture_path, "r", encoding="utf-8") as f:
                data: list[dict[str, Any]] = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error cargando el fixture {self.fixture_path}: {e}")
            return []
            
        return self._build_items(data, since, limit)
        
    def _build_items(
        self, 
        data: list[dict[str, Any]], 
        since: datetime.datetime, 
        limit: int
    ) -> list[RawItem]:
        items = []
        
        for record in data:
            if len(items) >= limit:
                break
                
            published_at = self._parse_datetime(record.get("published_at"))
            
            # Sólo retornar items publicados igual o después de la fecha `since` en UTC
            if published_at and published_at < since:
                continue
                
            closing_at = self._parse_datetime(record.get("closing_at"))
            budget = record.get("budget")
            if budget is not None:
                try:
                    budget = float(budget)
                except ValueError:
                    budget = None
                    
            item = RawItem(
                process_id=str(record.get("process_id", "")),
                title=str(record.get("title", "")),
                description=str(record.get("description", "")),
                entity_name=str(record.get("entity_name", "")),
                published_at=published_at,
                closing_at=closing_at,
                budget=budget,
                location=str(record.get("location", "")) if record.get("location") else None,
                url=str(record.get("url", ""))
            )
            
            # Validación de campos mínimos obligatorios
            if not item.process_id or not item.title:
                logger.debug(f"Row {item.process_id} malformada. Se descarta.")
                continue
                
            items.append(item)
            
        return items
