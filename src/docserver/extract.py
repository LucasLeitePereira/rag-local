"""Extração de arquivos originais para Markdown.

Arquitetura plugável: adicionar um formato novo é adicionar uma função
e uma entrada no dicionário EXTRATORES, nada mais.
"""

from __future__ import annotations

import csv as _csv
import datetime as _dt
import re
from pathlib import Path
from typing import Callable

MIN_CARACTERES_PDF_VALIDO = 200

# Nome do extrator de PDF efetivamente usado na última chamada a `_extrair_pdf` —
# `normalizar()` lê essa variável logo em seguida para gravar no front matter qual
# das duas bibliotecas produziu o texto (o dicionário EXTRATORES só sabe o nome da
# função `_extrair_pdf`, não qual lib ela escolheu internamente). Não é thread-safe,
# mas a ingestão processa um arquivo de cada vez.
_ultimo_extrator_pdf = "pymupdf4llm"

_STRIKETHROUGH = re.compile(r"~~([^\n~]+?)~~")
_NEGRITO = re.compile(r"\*\*([^\n*]+?)\*\*")
_TAG_QUEBRA_LINHA = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG_SUBLINHADO = re.compile(r"</?u>", re.IGNORECASE)
_COMENTARIO_HTML = re.compile(r"<!--.*?-->")
_CABECALHO_VAZIO = re.compile(r"^#+[ \t]*$", re.MULTILINE)
_LINHAS_EM_BRANCO_DEMAIS = re.compile(r"\n{3,}")
_ESPACOS_REPETIDOS = re.compile(r"[ \t]{2,}")


def _limpar_markdown_pdf(texto: str) -> str:
    """Remove artefatos de formatação típicos do pymupdf4llm: negrito/tachado que a
    biblioteca aplica a runs de 1-3 caracteres por variação de fonte no PDF original
    (`**Apo** **~~i~~ o técn**...`), comentários `<!-- Start/End of picture text -->`
    ao redor de texto extraído de imagens, tags HTML residuais de tabelas/sublinhado
    e espaçamento excessivo.

    Isso NÃO reconstrói palavras eventualmente fragmentadas pelo PDF de origem —
    corrigir esse tipo de fragmentação exigiria heurística lexical bem mais pesada
    e específica do documento; aqui só se tira o ruído de marcação em torno delas."""
    texto = _STRIKETHROUGH.sub(r"\1", texto)
    texto = _TAG_QUEBRA_LINHA.sub(" ", texto)
    texto = _TAG_SUBLINHADO.sub("", texto)
    texto = _COMENTARIO_HTML.sub("", texto)
    texto = _NEGRITO.sub(r"\1", texto)
    texto = _CABECALHO_VAZIO.sub("", texto)
    texto = _LINHAS_EM_BRANCO_DEMAIS.sub("\n\n", texto)
    texto = _ESPACOS_REPETIDOS.sub(" ", texto)
    return texto.strip()


class ErroDeExtracao(Exception):
    """Falha ao converter um arquivo original para Markdown."""


def _extrair_texto_puro(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8")


def _extrair_com_markitdown(caminho: Path) -> str:
    from markitdown import MarkItDown

    return MarkItDown().convert(str(caminho)).text_content


def _extrair_pdf(caminho: Path) -> str:
    """pymupdf4llm é o extrator principal: preserva cabeçalhos (o markitdown não gera
    nenhum) e não gruda palavras entre si como o markitdown costuma fazer. Cai para
    o markitdown só quando o pymupdf4llm falha ou devolve pouco texto (PDF escaneado,
    por exemplo) — nesse caso fica o que vier mais longo dos dois."""
    global _ultimo_extrator_pdf

    try:
        import pymupdf4llm

        texto = _limpar_markdown_pdf(pymupdf4llm.to_markdown(str(caminho)))
    except Exception:
        texto = ""

    if len(texto.strip()) >= MIN_CARACTERES_PDF_VALIDO:
        _ultimo_extrator_pdf = "pymupdf4llm"
        return texto

    try:
        texto_alternativo = _extrair_com_markitdown(caminho)
    except Exception:
        _ultimo_extrator_pdf = "pymupdf4llm"
        return texto

    if len(texto_alternativo.strip()) > len(texto.strip()):
        _ultimo_extrator_pdf = "markitdown"
        return texto_alternativo
    _ultimo_extrator_pdf = "pymupdf4llm"
    return texto


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
    if caminho_origem.suffix.lower() == ".pdf":
        extrator = _ultimo_extrator_pdf
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
