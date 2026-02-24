import re
from typing import Any

from src.secop_monitor.config import QueryConfig
from src.secop_monitor.schemas import NormalizedItem, MatchResult
from src.secop_monitor.normalize import normalize_text

class Matcher:
    """Implementa las reglas de evaluación y scoring para un QueryConfig."""
    
    WEIGHT_PHRASES = 0.35
    WEIGHT_ALL = 0.35
    WEIGHT_ANY = 0.30

    def __init__(self, query_config: QueryConfig):
        self.query_config = query_config
        
        # Normalizar los términos de configuración para el matcheo
        self.phrases = [self._norm(p) for p in query_config.phrases if p.strip()]
        self.keywords_all = [self._norm(k) for k in query_config.keywords_all if k.strip()]
        self.keywords_any = [self._norm(k) for k in query_config.keywords_any if k.strip()]
        self.keywords_not = [self._norm(k) for k in query_config.keywords_not if k.strip()]
        
        # 1) Expansión de sinónimos: diccionario simétrico
        self.synonyms_map: dict[str, set[str]] = {}
        for key, variants in query_config.synonyms.items():
            norm_k = self._norm(key)
            norm_variants = [self._norm(v) for v in variants if v.strip()]
            
            # Formar el grupo completo incluyendo la llave
            group = {norm_k} | set(norm_variants)
            
            for term in group:
                if term not in self.synonyms_map:
                    self.synonyms_map[term] = set()
                self.synonyms_map[term].update(group)
            
    def _norm(self, text: str) -> str:
        return normalize_text(text)
        
    def _get_expanded_term(self, term: str) -> list[str]:
        """Devuelve el término original y todos sus sinónimos vinculados."""
        if term in self.synonyms_map:
            return list(self.synonyms_map[term])
        return [term]

    def _check_term(self, term: str, text: str) -> bool:
        """Verifica si un término o alguno de sus sinónimos está como palabra completa en el texto."""
        variants = self._get_expanded_term(term)
        for variant in variants:
            # \b garantiza saltos de palabra en regex. re.escape protege caracteres si sobrevivieron.
            pattern = r'\b' + re.escape(variant) + r'\b'
            if re.search(pattern, text):
                return True
        return False
        
    def match(self, item: NormalizedItem, threshold: float) -> MatchResult:
        full_text = item.full_text
        
        explain: dict[str, Any] = {
            "query_name": self.query_config.name,
            "phrases_hit": [],
            "keywords_all_hit": [],
            "keywords_all_miss": [],
            "keywords_any_hit": [],
            "excluded_by": [],
            "component_scores": {}
        }
        
        # 2) Exclusión (hard exclude)
        not_hits = [k for k in self.keywords_not if self._check_term(k, full_text)]
        if not_hits:
            explain["excluded_by"] = not_hits
            return MatchResult(score=0.0, matched=False, explain=explain)
            
        # 3) Puntaje ponderado
        
        # 3.1 Phrases
        phrases_hit = [p for p in self.phrases if self._check_term(p, full_text)]
        phrase_score = len(phrases_hit) / max(1, len(self.phrases)) if self.phrases else 0.0
        phrases_part = self.WEIGHT_PHRASES * phrase_score
        
        # 3.2 Keywords All
        all_hits = [k for k in self.keywords_all if self._check_term(k, full_text)]
        all_misses = [k for k in self.keywords_all if k not in all_hits]
        
        if not self.keywords_all:
            all_score = 1.0 # Si no hay 'all', no penaliza
        else:
            all_score = 1.0 if len(all_hits) == len(self.keywords_all) else (len(all_hits) / len(self.keywords_all))
        all_part = self.WEIGHT_ALL * all_score
        
        # 3.3 Keywords Any
        any_hits = [k for k in self.keywords_any if self._check_term(k, full_text)]
        if not self.keywords_any:
            any_score = 0.0
        else:
            any_score = min(1.0, len(any_hits) / min(3, len(self.keywords_any))) # Cap en 3 hits
        any_part = self.WEIGHT_ANY * any_score
        
        # Score Final
        final_score = min(1.0, phrases_part + all_part + any_part)
        matched = final_score >= threshold
        
        # Explainability
        explain["phrases_hit"] = phrases_hit
        explain["keywords_all_hit"] = all_hits
        explain["keywords_all_miss"] = all_misses
        explain["keywords_any_hit"] = any_hits
        explain["component_scores"] = {
            "phrases": round(phrases_part, 3),
            "all": round(all_part, 3),
            "any": round(any_part, 3)
        }
        
        return MatchResult(score=final_score, matched=matched, explain=explain)

def evaluate_best_match(item: NormalizedItem, queries: list[QueryConfig], threshold: float) -> tuple[str, MatchResult]:
    """Evalúa el item contra todas las queries y devuelve la iteración de mejor puntaje."""
    best_name = "NONE"
    best_res = MatchResult(0.0, False, {})
    
    for q in queries:
        matcher = Matcher(q)
        res = matcher.match(item, threshold)
        if res.score > best_res.score:
            best_res = res
            best_name = q.name
            
    return best_name, best_res
