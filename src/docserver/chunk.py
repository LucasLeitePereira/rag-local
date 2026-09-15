"""Divide Markdown normalizado em chunks para indexação."""

from __future__ import annotations

import re
from pathlib import Path

from docserver import embed
from docserver.extract import ler_front_matter

MAX_TOKENS_CHUNK = 400
SOBREPOSICAO_TOKENS = 50
MIN_CARACTERES = 30

# Cabeçalhos de nível 1 a 3 delimitam seções. Extratores de PDF (pymupdf4llm) geram
# níveis mais profundos (####, #####...) para subtítulos internos — ficam dentro do
# texto da seção que os contém e são subdivididos por tamanho, não por nome.
_CABECALHO_H1 = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_CABECALHO_QUALQUER = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
_CABECALHO_SECAO = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)

_QUEBRA_FRASE = re.compile(r"(?<=[.!?;])\s+")

_tokenizer_cache = None


def _obter_tokenizer():
    """Tokenizer real do modelo de embeddings, carregado uma única vez. Usa
    `local_files_only` para nunca tentar baixar nada nem travar sem rede — sem o
    modelo em cache local, cai silenciosamente para a estimativa por caracteres."""
    global _tokenizer_cache
    if _tokenizer_cache is None:
        try:
            from transformers import AutoTokenizer

            _tokenizer_cache = AutoTokenizer.from_pretrained(embed.NOME_MODELO, local_files_only=True)
        except Exception:
            _tokenizer_cache = False
    return _tokenizer_cache


def contar_tokens(texto: str) -> int:
    """Conta tokens com o tokenizer real do modelo; sem ele, estima 1 token a cada
    3 caracteres (mais conservador que a média real do português, de propósito)."""
    tokenizer = _obter_tokenizer()
    if tokenizer:
        return len(tokenizer.encode(texto, add_special_tokens=False))
    return -(-len(texto) // 3)  # ceil sem importar math


def _titulo_documento(corpo: str) -> str:
    m = _CABECALHO_H1.search(corpo)
    if m:
        return m.group(1).strip()
    m = _CABECALHO_QUALQUER.search(corpo)
    if m:
        return m.group(1).strip()
    for linha in corpo.splitlines():
        linha = linha.strip()
        if linha:
            return linha[:80].strip("# ").strip()
    return ""


def _dividir_por_secoes(corpo: str, titulo_doc: str) -> list[tuple[str, str]]:
    """Retorna [(nome_secao, texto_secao), ...] a partir dos cabeçalhos de nível 1 a 3.

    Texto antes do primeiro cabeçalho (comum quando o H1 vira o próprio nome da
    primeira seção, ou quando o documento simplesmente não abre com um cabeçalho)
    vira uma seção própria batizada com o título do documento, em vez de ser
    descartado silenciosamente."""
    marcadores = list(_CABECALHO_SECAO.finditer(corpo))
    if not marcadores:
        return []

    secoes = []
    preambulo = corpo[: marcadores[0].start()].strip()
    if preambulo:
        secoes.append((titulo_doc, preambulo))

    for i, marcador in enumerate(marcadores):
        nome = marcador.group(1).strip()
        inicio = marcador.end()
        fim = marcadores[i + 1].start() if i + 1 < len(marcadores) else len(corpo)
        texto = corpo[inicio:fim].strip()
        secoes.append((nome, texto))
    return secoes


def _dividir_por_palavras(texto: str, contar_tokens_fn, max_tokens: int) -> list[str]:
    """Último recurso: corte duro palavra a palavra, sem se importar com pontuação."""
    palavras = texto.split(" ")
    if len(palavras) <= 1:
        return [texto]

    blocos: list[str] = []
    atual: list[str] = []
    for palavra in palavras:
        candidato = atual + [palavra]
        if atual and contar_tokens_fn(" ".join(candidato)) > max_tokens:
            blocos.append(" ".join(atual))
            atual = [palavra]
        else:
            atual = candidato
    if atual:
        blocos.append(" ".join(atual))
    return blocos


def _unidades_atomicas(texto: str, contar_tokens_fn, max_tokens: int) -> list[str]:
    """Divide `texto` em pedaços que cabem sozinhos em max_tokens, tentando nessa
    ordem: parágrafo, linha, frase e por fim corte duro por palavra. Só desce um
    nível quando o nível atual não separa nada (texto sem parágrafos, por exemplo)."""
    if contar_tokens_fn(texto) <= max_tokens:
        return [texto]

    for separador in ("\n\n", "\n"):
        partes = [p for p in texto.split(separador) if p.strip()]
        if len(partes) > 1:
            resultado = []
            for parte in partes:
                resultado.extend(_unidades_atomicas(parte, contar_tokens_fn, max_tokens))
            return resultado

    frases = [f for f in _QUEBRA_FRASE.split(texto) if f.strip()]
    if len(frases) > 1:
        resultado = []
        for frase in frases:
            resultado.extend(_unidades_atomicas(frase, contar_tokens_fn, max_tokens))
        return resultado

    return _dividir_por_palavras(texto, contar_tokens_fn, max_tokens)


def _cauda_por_tokens(texto: str, tokens_alvo: int, contar_tokens_fn) -> str:
    """Últimas ~tokens_alvo tokens de `texto`, para dar sobreposição entre blocos."""
    if tokens_alvo <= 0:
        return ""
    palavras = texto.split(" ")
    cauda: list[str] = []
    for palavra in reversed(palavras):
        candidato = [palavra] + cauda
        if contar_tokens_fn(" ".join(candidato)) > tokens_alvo:
            break
        cauda = candidato
    return " ".join(cauda)


def _blocos_por_tamanho(
    texto: str,
    contar_tokens_fn,
    max_tokens: int = MAX_TOKENS_CHUNK,
    sobreposicao_tokens: int = SOBREPOSICAO_TOKENS,
) -> list[str]:
    """Quebra texto em blocos de até max_tokens (contados de verdade, não estimados
    por caracteres), com sobreposição entre blocos consecutivos.

    A contagem por bloco é aditiva (soma dos tokens de cada unidade, em vez de
    retokenizar o bloco inteiro a cada unidade acrescentada) de propósito: com um
    tokenizer real, retokenizar a string acumulada a cada passo custa O(n²) num
    documento grande — a soma é uma aproximação de sobra (o tokenizer pode fundir
    um ou dois tokens na fronteira entre unidades), aceitável dado que já há uma
    margem de ~20% entre MAX_TOKENS_CHUNK e o limite real do modelo."""
    if contar_tokens_fn(texto) <= max_tokens:
        return [texto]

    unidades = _unidades_atomicas(texto, contar_tokens_fn, max_tokens)

    blocos: list[str] = []
    partes_atuais: list[str] = []
    tokens_atuais = 0
    for unidade in unidades:
        tokens_unidade = contar_tokens_fn(unidade)
        acrescimo = tokens_unidade + (1 if partes_atuais else 0)  # +1: folga do separador
        if partes_atuais and tokens_atuais + acrescimo > max_tokens:
            bloco = "\n\n".join(partes_atuais)
            blocos.append(bloco)
            cauda = _cauda_por_tokens(bloco, sobreposicao_tokens, contar_tokens_fn)
            tokens_cauda = contar_tokens_fn(cauda) if cauda else 0
            # a unidade que abre o próximo bloco pode já estar perto do limite (ela
            # própria já é ≤ max_tokens); só entra sobreposição se ainda couber —
            # nunca ultrapassar max_tokens importa mais que preservar a cauda.
            if cauda and tokens_cauda + tokens_unidade <= max_tokens:
                partes_atuais = [cauda, unidade]
                tokens_atuais = tokens_cauda + tokens_unidade
            else:
                partes_atuais = [unidade]
                tokens_atuais = tokens_unidade
        else:
            partes_atuais.append(unidade)
            tokens_atuais += acrescimo
    if partes_atuais:
        blocos.append("\n\n".join(partes_atuais))
    return blocos


def chunkar_arquivo(
    caminho_normalizado: Path, docs_normalizado: Path | None = None, contar_tokens_fn=None
) -> list[dict]:
    """Lê um arquivo Markdown normalizado e devolve a lista de chunks para indexação.

    `caminho_normalizado` vai para o índice relativo a `docs_normalizado` e em formato
    POSIX (`api/contratos.md`): gravar o caminho como veio (relativo ao cwd da
    ingestão, com `\\` no Windows) impedia o servidor — que roda de outro diretório,
    ou outro SO — de achar o arquivo."""
    conteudo = caminho_normalizado.read_text(encoding="utf-8")
    base = docs_normalizado if docs_normalizado is not None else caminho_normalizado.parent
    caminho_indexado = caminho_normalizado.resolve().relative_to(Path(base).resolve()).as_posix()
    meta, corpo = ler_front_matter(conteudo)
    caminho_origem = meta.get("origem", "")
    titulo_doc = _titulo_documento(corpo)
    contar = contar_tokens_fn or contar_tokens

    secoes = _dividir_por_secoes(corpo, titulo_doc)
    if not secoes:
        secoes = [(titulo_doc, corpo)]

    chunks: list[dict] = []
    ordem = 0
    for nome_secao, texto_secao in secoes:
        blocos = _blocos_por_tamanho(texto_secao, contar)

        for bloco in blocos:
            bloco = bloco.strip()
            if len(bloco) < MIN_CARACTERES:
                continue
            chunks.append(
                {
                    "caminho_origem": caminho_origem,
                    "caminho_normalizado": caminho_indexado,
                    "titulo_doc": titulo_doc,
                    "secao": nome_secao,
                    "texto": bloco,
                    "ordem": ordem,
                }
            )
            ordem += 1

    return chunks
