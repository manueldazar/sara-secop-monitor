from abc import ABC, abstractmethod
from typing import Sequence
from src.secop_monitor.models import Opportunity

class Notifier(ABC):
    """Interfaz base para canales de notificación."""
    
    @abstractmethod
    def notify(self, items: Sequence[Opportunity]) -> None:
        """
        Envía notificaciones sobre una lista de oportunidades nuevas
        que cumplieron el umbral de score.
        """
        pass
