from abc import ABC, abstractmethod
import datetime

from src.secop_monitor.schemas import RawItem

class Collector(ABC):
    """Interfaz base para todos los recolectores de datos (SECOP, Fixture, etc.)."""
    
    @abstractmethod
    def collect(self, since: datetime.datetime, limit: int) -> list[RawItem]:
        """
        Recolecta items publicados a partir de la fecha `since`.
        
        Args:
            since: Fecha y hora en UTC desde la que se desea buscar.
            limit: Límite de items a retornar. Max_items_per_run.
            
        Returns:
            Lista de objetos RawItem listos para el pipeline, ordenados de
            forma que no superen el límite configurado.
        """
        pass
