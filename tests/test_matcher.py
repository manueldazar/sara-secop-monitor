import datetime
from src.secop_monitor.config import QueryConfig
from src.secop_monitor.matcher import Matcher, evaluate_best_match
from src.secop_monitor.schemas import RawItem, NormalizedItem
from src.secop_monitor.normalize import normalize_item

def _get_dummy_item(title="Inteligencia Artificial para el chatbot", desc=""):
    return normalize_item(RawItem(
        process_id="1", title=title, description=desc, entity_name="Entidad",
        published_at=datetime.datetime.now(), closing_at=None, budget=0, location="N/A", url=""
    ))

def test_hard_exclude():
    q = QueryConfig(
        name="Test",
        keywords_any=["chatbot"],
        keywords_not=["aseo"]
    )
    m = Matcher(q)
    
    # Matches properly
    res1 = m.match(_get_dummy_item("Desarrollo de chatbot"), 0.1)
    assert res1.matched
    assert res1.score > 0
    
    # Excludes properly
    res2 = m.match(_get_dummy_item("Desarrollo de chatbot y aseo"), 0.1)
    assert not res2.matched
    assert res2.score == 0.0
    assert "aseo" in res2.explain["excluded_by"]

def test_synonyms_expansion_symmetric():
    """
    Testear que la expansión simétrica garantiza un hit sin importar
    la forma con la que definimos la query (si variant o key original).
    """
    q1 = QueryConfig(
        name="VarA",
        keywords_any=["inteligencia artificial"],
        synonyms={"ia": ["inteligencia artificial"]}
    )
    
    # El item texto literal dice "ia pero no inteligencia..."
    item = _get_dummy_item("Desarrollo de ia y bots")
    m1 = Matcher(q1)
    
    res1 = m1.match(item, 0.1)
    assert res1.matched
    # Incluso detecta ia y la asocia a su key "inteligencia artificial"
    assert "inteligencia artificial" in res1.explain["keywords_any_hit"]

def test_scoring_weights():
    # Solo matchea phrases
    q = QueryConfig(
        name="All Hits",
        keywords_all=["backend", "frontend"], # 0.35 max
        phrases=["react native"] # 0.35 max
        # any = vacío (0 max)
    )
    m = Matcher(q)
    
    res1 = m.match(_get_dummy_item("Necesitamos react native pero sin backend ni front"), 0.1)
    
    # Phrase score (1 hit, 1 total) => 1.0 * 0.35 = 0.35
    # All score (1 hits de all, array len 2) => 1/2 * 0.35 = 0.175
    # Total = 0.525
    assert round(res1.score, 3) == 0.525
    
    res2 = m.match(_get_dummy_item("Tenemos un proyecto en react native que requiere backend y frontend experto"), 0.1)
    # Phrase = 0.35 + All (2/2 = 1.0 ) * 0.35 = 0.35 => Total 0.70
    assert res2.score == 0.70
