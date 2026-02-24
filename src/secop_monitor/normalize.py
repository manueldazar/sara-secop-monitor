import hashlib
import re
import unicodedata

from src.secop_monitor.schemas import RawItem, NormalizedItem

def normalize_text(text: str | None) -> str:
    """
    Normaliza el texto: lowercase, quita acentos, colapsa espacios
    y remueve puntuación simple.
    """
    if not text:
        return ""
    
    # Lowercase
    text = text.lower()
    
    # Quitar acentos (NFD separa los caracteres de sus diacríticos)
    text = ''.join(
        c for c in unicodedata.normalize('NFD', text) 
        if unicodedata.category(c) != 'Mn'
    )
    
    # Quitar puntuación simple (reemplazar no-alfanuméricos por espacios)
    # Dejamos letras, números y espacios en blanco.
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Colapsar múltiples espacios en uno solo
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def generate_fingerprint(title_norm: str, entity_norm: str) -> str:
    """
    Genera un fingerprint determinista mediante SHA-256 usando el
    título y la entidad normalizados.
    """
    base_string = f"{title_norm}|{entity_norm}"
    return hashlib.sha256(base_string.encode('utf-8')).hexdigest()

def normalize_item(raw_item: RawItem) -> NormalizedItem:
    """
    Convierte un RawItem en NormalizedItem aplicando las
    transformaciones necesarias al texto.
    """
    title_norm = normalize_text(raw_item.title)
    description_norm = normalize_text(raw_item.description)
    entity_norm = normalize_text(raw_item.entity_name)
    
    fingerprint = generate_fingerprint(title_norm, entity_norm)
    
    return NormalizedItem(
        raw=raw_item,
        title_norm=title_norm,
        description_norm=description_norm,
        entity_norm=entity_norm,
        fingerprint=fingerprint
    )
