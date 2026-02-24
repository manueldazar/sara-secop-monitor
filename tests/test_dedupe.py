import datetime
from src.secop_monitor.models import Opportunity
from src.secop_monitor.schemas import RawItem
from src.secop_monitor.normalize import normalize_item
from src.secop_monitor.dedupe import is_secondary_duplicate

def test_dedupe_secondary_exact_fingerprint():
    # Item A
    itemA = normalize_item(RawItem("1", "Mismo Titulo", "", "Misma Entidad", datetime.datetime.now(), None, 0, "", ""))
    # Opp ya insertada, distinto process_id (2) pero misma data
    oppA = Opportunity(
        process_id="2",
        title="Mismo Titulo", 
        entity_name="Misma Entidad",
        fingerprint=itemA.fingerprint
    )
    assert is_secondary_duplicate(itemA, [oppA]) == True

def test_dedupe_secondary_heuristic():
    # item original
    item = normalize_item(RawItem("1", "Consultoría en analitica de datos", "", "DANE", datetime.datetime.now(), None, 0, "", ""))
    
    # Republicación con variaciones sutiles sintacticas
    republished_opp = Opportunity(
        process_id="2",
        title="Consultoría en analítica de datos republicado", 
        entity_name="DANE",
        # Fingerprint no coincidirá puesto que varia titulo
        fingerprint="abcdh", 
    )
    
    # Evaluar fuzzy > 0.8
    assert is_secondary_duplicate(item, [republished_opp], similarity_threshold=0.80) == True
    # Evaluar fuzzy muy estricto > 0.99
    assert is_secondary_duplicate(item, [republished_opp], similarity_threshold=0.99) == False
