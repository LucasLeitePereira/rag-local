"""Extração de arquivos originais para Markdown.

Arquitetura plugável: adicionar um formato novo é adicionar uma função
e uma entrada no dicionário EXTRATORES, nada mais.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Callable


def _extrair_texto_puro(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8")


EXTRATORES: dict[str, Callable[[Path], str]] = {
    ".md": _extrair_texto_puro,
    ".markdown": _extrair_texto_puro,
    ".txt": _extrair_texto_puro,
}


def extrair_texto(caminho: Path) -> str | None:
    """Converte um arquivo original para Markdown, ou None se o formato não é suportado."""
    funcao = EXTRATORES.get(caminho.suffix.lower())
    if funcao is None:
        return None
    return funcao(caminho)


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
