"""Divide Markdown normalizado em chunks para indexação."""

from __future__ import annotations

import re
from pathlib import Path

from docserver.extract import ler_front_matter

TAMANHO_BLOCO_TOKENS = 800
SOBREPOSICAO_TOKENS = 100
LIMITE_SECAO_TOKENS = 1500
MIN_CARACTERES = 30

_CABECALHO_H1 = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_CABECALHO_H2 = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def _tokens_aprox(texto: str) -> float:
    return len(texto) / 4


def _titulo_documento(corpo: str) -> str:
    m = _CABECALHO_H1.search(corpo)
    return m.group(1).strip() if m else ""


def _dividir_por_secoes(corpo: str) -> list[tuple[str, str]]:
    """Retorna [(nome_secao, texto_secao), ...] a partir dos cabeçalhos ##."""
    marcadores = list(_CABECALHO_H2.finditer(corpo))
    if not marcadores:
        return []

    secoes = []
    for i, marcador in enumerate(marcadores):
        nome = marcador.group(1).strip()
        inicio = marcador.end()
        fim = marcadores[i + 1].start() if i + 1 < len(marcadores) else len(corpo)
        texto = corpo[inicio:fim].strip()
        secoes.append((nome, texto))
    return secoes


def _blocos_por_tamanho(
    texto: str,
    tamanho_tokens: int = TAMANHO_BLOCO_TOKENS,
    sobreposicao_tokens: int = SOBREPOSICAO_TOKENS,
) -> list[str]:
    """Quebra texto em blocos de ~tamanho_tokens, com sobreposição, preferindo fim de parágrafo."""
    tamanho_chars = tamanho_tokens * 4
    sobreposicao_chars = sobreposicao_tokens * 4

    if len(texto) <= tamanho_chars:
        return [texto]

    paragrafos = texto.split("\n\n")
    blocos: list[str] = []
    atual = ""
    for paragrafo in paragrafos:
        candidato = f"{atual}\n\n{paragrafo}" if atual else paragrafo
        if len(candidato) > tamanho_chars and atual:
            blocos.append(atual)
            cauda = atual[-sobreposicao_chars:] if sobreposicao_chars else ""
            atual = f"{cauda}\n\n{paragrafo}" if cauda else paragrafo
        else:
            atual = candidato
    if atual:
        blocos.append(atual)
    return blocos


def chunkar_arquivo(caminho_normalizado: Path) -> list[dict]:
    """Lê um arquivo Markdown normalizado e devolve a lista de chunks para indexação."""
    conteudo = caminho_normalizado.read_text(encoding="utf-8")
    meta, corpo = ler_front_matter(conteudo)
    caminho_origem = meta.get("origem", "")
    titulo_doc = _titulo_documento(corpo)

    secoes = _dividir_por_secoes(corpo)
    if not secoes:
        secoes = [(titulo_doc, corpo)]

    chunks: list[dict] = []
    ordem = 0
    for nome_secao, texto_secao in secoes:
        if _tokens_aprox(texto_secao) > LIMITE_SECAO_TOKENS:
            blocos = _blocos_por_tamanho(texto_secao)
        else:
            blocos = [texto_secao]

        for bloco in blocos:
            bloco = bloco.strip()
            if len(bloco) < MIN_CARACTERES:
                continue
            chunks.append(
                {
                    "caminho_origem": caminho_origem,
                    "caminho_normalizado": str(caminho_normalizado),
                    "titulo_doc": titulo_doc,
                    "secao": nome_secao,
                    "texto": bloco,
                    "ordem": ordem,
                }
            )
            ordem += 1

    return chunks
