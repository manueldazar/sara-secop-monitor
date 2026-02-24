from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class RawItem:
    """Item raw extraído directo del Collector, sin procesar ni normalizar."""
    process_id: str
    title: str
    description: str
    entity_name: str
    published_at: datetime | None
    closing_at: datetime | None
    budget: float | None
    location: str | None
    url: str

@dataclass
class NormalizedItem:
    """Item procesado con el texto listo para mathing y deduplicación."""
    raw: RawItem
    title_norm: str
    description_norm: str
    entity_norm: str
    fingerprint: str
    
    @property
    def full_text(self) -> str:
        """Combine campos relevantes para la búsqueda en un solo bloque."""
        return f"{self.title_norm} {self.description_norm}".strip()

@dataclass
class MatchResult:
    """Resultado de evaluar un QueryConfig sobre un NormalizedItem."""
    score: float
    matched: bool
    explain: dict[str, Any] = field(default_factory=dict)
