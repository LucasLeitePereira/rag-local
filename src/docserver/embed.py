"""Embeddings de texto via sentence-transformers, com os prefixos exigidos pelo modelo e5."""

from __future__ import annotations

NOME_MODELO = "intfloat/multilingual-e5-small"
DIMENSAO = 384

_modelo_cache = None


def _carregar_modelo():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(NOME_MODELO)


def obter_modelo():
    """Carrega o modelo de embeddings uma única vez e reutiliza a instância."""
    global _modelo_cache
    if _modelo_cache is None:
        _modelo_cache = _carregar_modelo()
    return _modelo_cache


def preparar_passagem(texto: str) -> str:
    return f"passage: {texto}"


def preparar_consulta(texto: str) -> str:
    return f"query: {texto}"


def texto_para_embeddar(chunk: dict) -> str:
    """Concatena título, seção e corpo — dá contexto ao vetor de chunks curtos."""
    partes = [chunk.get("titulo_doc", ""), chunk.get("secao", ""), chunk.get("texto", "")]
    return " — ".join(parte for parte in partes if parte)


def embeddar_passagem(chunk: dict) -> list[float]:
    modelo = obter_modelo()
    texto = preparar_passagem(texto_para_embeddar(chunk))
    # normalizado para norma 1: permite converter a distância L2 do índice vetorial
    # em similaridade de cosseno com `sim = 1 - distancia**2 / 2` (ver index.py).
    return modelo.encode(texto, normalize_embeddings=True).tolist()


def embeddar_consulta(consulta: str) -> list[float]:
    modelo = obter_modelo()
    texto = preparar_consulta(consulta)
    return modelo.encode(texto, normalize_embeddings=True).tolist()
