"""Reranker (cross-encoder) que reordena os candidatos da busca híbrida."""

from __future__ import annotations

import math
import os

from docserver import embed

# Candidatos avaliados em docs/ARQUITETURA.md ("Reranker"). Ambos multilíngues.
MODELOS_RERANKER = {
    "mminilm": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
    "bge-m3": "BAAI/bge-reranker-v2-m3",
}
RERANKER_PADRAO = "mminilm"
# Desligado até a avaliação no corpus local escolher o modelo e calibrar
# RERANK_MINIMO (TASK-009, pendente); ligue com RERANKER=mminilm ou RERANKER=bge-m3.
RERANKER_ENV_PADRAO = "desligado"
DESLIGADO = ("desligado", "nenhum", "0", "false", "")

# Os dois modelos leem até 512 tokens por par (consulta + trecho); cortar o texto
# antes evita tokenizar à toa a cauda que seria truncada de qualquer forma.
MAX_CARACTERES_TRECHO = 2000

_cache: dict[str, object] = {}


def reranker_configurado() -> str | None:
    """Chave (ou id do Hugging Face) do reranker da env `RERANKER`, ou None se desligado."""
    valor = os.environ.get("RERANKER", RERANKER_ENV_PADRAO).strip()
    if valor.lower() in DESLIGADO:
        return None
    return valor


def _carregar(nome: str):
    from sentence_transformers import CrossEncoder

    try:
        return CrossEncoder(nome, max_length=512, local_files_only=True)
    except Exception:
        return CrossEncoder(nome, max_length=512)


def obter_modelo(chave: str):
    """Carrega o modelo uma vez por processo. Uma falha também fica em cache: sem isso,
    cada busca repetiria segundos de tentativa (e de acesso à rede) antes do fallback."""
    nome = MODELOS_RERANKER.get(chave, chave)
    if nome not in _cache:
        try:
            _cache[nome] = _carregar(nome)
        except Exception as erro:  # noqa: BLE001 — quem chama decide o fallback
            _cache[nome] = erro
    modelo = _cache[nome]
    if isinstance(modelo, Exception):
        raise modelo
    return modelo


def pontuar(consulta: str, itens: list[dict], chave: str | None = None) -> list[float]:
    """Pontuação de relevância (0–1, maior é melhor) de cada chunk para a consulta."""
    chave = chave or reranker_configurado() or RERANKER_PADRAO
    if not itens:
        return []
    modelo = obter_modelo(chave)
    pares = [(consulta, embed.texto_para_embeddar(item)[:MAX_CARACTERES_TRECHO]) for item in itens]
    # cada modelo traz sua ativação (o mMiniLM devolve logits crus; outros, sigmoide):
    # pedir sempre os logits e aplicar a sigmoide aqui deixa todos na mesma escala 0–1,
    # que é a do RERANK_MINIMO
    import torch

    logits = modelo.predict(pares, show_progress_bar=False, activation_fn=torch.nn.Identity())
    return [1.0 / (1.0 + math.exp(-float(logit))) for logit in logits]
