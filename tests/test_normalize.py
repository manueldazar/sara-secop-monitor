import datetime
from src.secop_monitor.normalize import normalize_text, generate_fingerprint, normalize_item
from src.secop_monitor.schemas import RawItem

def test_normalize_text():
    assert normalize_text("Inteligencia Artificial") == "inteligencia artificial"
    assert normalize_text("Árboles y camión") == "arboles y camion"
    assert normalize_text(" Esto   es  una \t prueba  ! ") == "esto es una prueba"
    assert normalize_text("") == ""
    assert normalize_text(None) == ""

def test_generate_fingerprint():
    # Fingerprints idénticos ante la misma data normalizada
    f1 = generate_fingerprint("software ai", "minsalud")
    f2 = generate_fingerprint("software ai", "minsalud")
    assert f1 == f2
    
def test_normalize_item():
    raw = RawItem(
        process_id="123",
        title="Consultoría en IA",
        description="Analítica avanzada.",
        entity_name="Ministerio TIC",
        published_at=datetime.datetime(2026, 1, 1),
        closing_at=None,
        budget=100.0,
        location="Bogotá",
        url="http://x.com"
    )
    norm = normalize_item(raw)
    
    assert norm.title_norm == "consultoria en ia"
    assert norm.description_norm == "analitica avanzada"
    assert norm.entity_norm == "ministerio tic"
    assert norm.fingerprint is not None
    assert type(norm.fingerprint) is str
    assert norm.full_text == "consultoria en ia analitica avanzada"
