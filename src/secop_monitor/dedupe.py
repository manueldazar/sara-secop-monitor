import difflib
from typing import Sequence

from src.secop_monitor.models import Opportunity
from src.secop_monitor.normalize import normalize_text
from src.secop_monitor.schemas import NormalizedItem

def is_secondary_duplicate(
    item: NormalizedItem,
    recent_opportunities: Sequence[Opportunity],
    similarity_threshold: float = 0.90
) -> bool:
    """
    Comprueba si existe un posible duplicado secundario comparando:
    1) Fingerprint exacto (por si cambian de process_id pero es mismo título y entidad).
    2) Similitud algorítmica alta (Fuzzy Matching > threshold) entre el título normalizado
       del `item` y el título normalizado de las oportunidades recientes.
    """
    if not recent_opportunities:
        return False

    for opp in recent_opportunities:
        # 1. Exact fingerprint
        if item.fingerprint == opp.fingerprint:
            return True
            
        # 2. Heuristic similarity over normalized titles
        opp_title_norm = normalize_text(opp.title)
        
        ratio = difflib.SequenceMatcher(None, item.title_norm, opp_title_norm).ratio()
        if ratio >= similarity_threshold:
            return True
            
    return False
