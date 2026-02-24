import os
import requests
import logging
from typing import Sequence

from src.secop_monitor.notifier.base import Notifier
from src.secop_monitor.models import Opportunity
from src.secop_monitor.config import SlackConfig

logger = logging.getLogger(__name__)

class SlackNotifier(Notifier):
    """Envía notificaciones vía webhook de Slack."""
    
    def __init__(self, config: SlackConfig):
        self.webhook_url = os.environ.get(config.webhook_env_var)
        self.username = config.username
        
    def notify(self, items: Sequence[Opportunity]) -> None:
        if not items or not self.webhook_url:
            return
            
        for opp in items:
            text_blocks = [
                f"*Nueva Oportunidad ({opp.score:.2f})*: <{opp.url}|{opp.title}>\n",
                f"*Query Matched*: {opp.query_match}",
                f"*Entidad*: {opp.entity_name}",
                f"*Explains*: `{opp.match_explain}`"
            ]
            
            payload = {
                "username": self.username,
                "text": "\n".join(text_blocks)
            }
            try:
                # Usamos requests para lanzar en caso de fallo red 
                res = requests.post(self.webhook_url, json=payload, timeout=5)
                res.raise_for_status()
            except requests.RequestException as e:
                logger.error(f"Falla notificando a Slack: {e}")
                # No interrumpe sino que loggea el error de timeout/falla de conectividad
