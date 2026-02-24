import logging
from typing import Sequence

from src.secop_monitor.notifier.base import Notifier
from src.secop_monitor.models import Opportunity

logger = logging.getLogger(__name__)

class StdoutNotifier(Notifier):
    """Notifier que imprime cada alerta a consola, útil para desarrollo."""
    
    def notify(self, items: Sequence[Opportunity]) -> None:
        if not items:
            return
            
        logger.info(f" --- [STDOUT NOTIFIER] {len(items)} NUEVAS ALERTAS --- ")
        
        for opp in items:
            msg = (
                f"\n[{opp.score:.2f}] {opp.title}"
                f"\n  Query: {opp.query_match}"
                f"\n  Entidad: {opp.entity_name}"
                f"\n  URL: {opp.url}"
                f"\n  Explain: {opp.match_explain}\n"
            )
            print(msg)
