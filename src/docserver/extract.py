"""Extração de arquivos originais para Markdown.

Arquitetura plugável: adicionar um formato novo é adicionar uma função
e uma entrada no dicionário EXTRATORES, nada mais.
"""

from __future__ import annotations

import csv as _csv
import datetime as _dt
from pathlib import Path
from typing import Callable

MIN_CARACTERES_PDF_VALIDO = 200


class ErroDeExtracao(Exception):
    """Falha ao converter um arquivo original para Markdown."""


def _extrair_texto_puro(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8")


def _extrair_com_markitdown(caminho: Path) -> str:
    from markitdown import MarkItDown

    return MarkItDown().convert(str(caminho)).text_content


def _extrair_pdf(caminho: Path) -> str:
    texto = _extrair_com_markitdown(caminho)
    if len(texto.strip()) >= MIN_CARACTERES_PDF_VALIDO:
        return texto

    try:
        import pymupdf4llm

        texto_alternativo = pymupdf4llm.to_markdown(str(caminho))
    except Exception:
        return texto

    return texto_alternativo if len(texto_alternativo.strip()) > len(texto.strip()) else texto


def _extrair_csv(caminho: Path) -> str:
    with caminho.open(newline="", encoding="utf-8") as arquivo:
        linhas = list(_csv.reader(arquivo))
    if not linhas:
        return ""

    cabecalho, *resto = linhas
    tabela = [
        "| " + " | ".join(cabecalho) + " |",
        "| " + " | ".join("---" for _ in cabecalho) + " |",
    ]
    tabela.extend("| " + " | ".join(linha) + " |" for linha in resto)
    return "\n".join(tabela)


EXTRATORES: dict[str, Callable[[Path], str]] = {
    ".md": _extrair_texto_puro,
    ".markdown": _extrair_texto_puro,
    ".txt": _extrair_texto_puro,
    ".docx": _extrair_com_markitdown,
    ".pptx": _extrair_com_markitdown,
    ".xlsx": _extrair_com_markitdown,
    ".html": _extrair_com_markitdown,
    ".pdf": _extrair_pdf,
    ".csv": _extrair_csv,
}


def extrair_texto(caminho: Path) -> str | None:
    """Converte um arquivo original para Markdown, ou None se o formato não é suportado."""
    funcao = EXTRATORES.get(caminho.suffix.lower())
    if funcao is None:
        return None
    try:
        return funcao(caminho)
    except Exception as erro:
        raise ErroDeExtracao(f"falha ao extrair {caminho}: {erro}") from erro


def ler_front_matter(conteudo: str) -> tuple[dict[str, str], str]:
    """Separa o front matter YAML (formato chave: valor simples) do corpo Markdown."""
    if not conteudo.startswith("---\n"):
        return {}, conteudo

    fim = conteudo.index("\n---\n", 4)
    bloco = conteudo[4:fim]
    corpo = conteudo[fim + len("\n---\n") :]
    if corpo.startswith("\n"):
        corpo = corpo[1:]

    meta: dict[str, str] = {}
    for linha in bloco.splitlines():
        if ":" not in linha:
            continue
        chave, _, valor = linha.partition(":")
        meta[chave.strip()] = valor.strip()
    return meta, corpo


def normalizar(caminho_origem: Path, docs_fonte: Path, docs_normalizado: Path) -> Path:
    """Extrai `caminho_origem` e grava o Markdown normalizado com front matter.

    Espelha a estrutura de pastas de docs_fonte dentro de docs_normalizado,
    trocando a extensão por .md.
    """
    texto = extrair_texto(caminho_origem)
    if texto is None:
        raise ValueError(f"formato não suportado: {caminho_origem.suffix}")

    caminho_relativo = caminho_origem.relative_to(docs_fonte)
    caminho_saida = (docs_normalizado / caminho_relativo).with_suffix(".md")
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    origem_str = f"docs-fonte/{caminho_relativo.as_posix()}"
    extrator = EXTRATORES[caminho_origem.suffix.lower()].__name__
    ingerido_em = _dt.datetime.now().isoformat(timespec="seconds")

    front_matter = (
        "---\n"
        f"origem: {origem_str}\n"
        f"extrator: {extrator}\n"
        f"ingerido_em: {ingerido_em}\n"
        "---\n\n"
    )
    caminho_saida.write_text(front_matter + texto, encoding="utf-8")
    return caminho_saida
