"""Embeddings de texto via sentence-transformers, com os prefixos exigidos pelo modelo e5."""

from __future__ import annotations

import os

NOME_MODELO = "intfloat/multilingual-e5-small"
DIMENSAO = 384

_modelo_cache = None


def _carregar_modelo():
    from sentence_transformers import SentenceTransformer

    # com o modelo já em cache, não consultar o Hugging Face Hub: a checagem de rede
    # soma segundos (ou trava sem rede) ao startup do servidor.
    try:
        return SentenceTransformer(NOME_MODELO, local_files_only=True)
    except Exception:
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


# Medido em CPU (4 threads do torch) com 200 chunks reais do livro, ~400 tokens cada:
# lote 1 = 33,6 s; lotes 4/8/16/32 = 39-43 s; chamada individual = 34,1 s. Com
# sequências longas o custo é dominado pela atenção, e o padding dentro do lote só
# acrescenta trabalho — por isso o padrão é 1. Em GPU, ou com chunks curtos, lotes
# maiores tendem a compensar: ajuste por EMBEDDINGS_TAMANHO_LOTE.
TAMANHO_LOTE_PADRAO = 1


def embeddar_passagens(chunks: list[dict], tamanho_lote: int | None = None) -> list[list[float]]:
    """Embeddings de vários chunks numa única chamada ao modelo (`encode` com lista),
    que distribui os textos em lotes de `tamanho_lote`."""
    if not chunks:
        return []
    if tamanho_lote is None:
        tamanho_lote = int(os.environ.get("EMBEDDINGS_TAMANHO_LOTE", TAMANHO_LOTE_PADRAO))
    modelo = obter_modelo()
    textos = [preparar_passagem(texto_para_embeddar(chunk)) for chunk in chunks]
    vetores = modelo.encode(textos, batch_size=tamanho_lote, normalize_embeddings=True)
    return [vetor.tolist() for vetor in vetores]


def embeddar_consulta(consulta: str) -> list[float]:
    modelo = obter_modelo()
    texto = preparar_consulta(consulta)
    return modelo.encode(texto, normalize_embeddings=True).tolist()
