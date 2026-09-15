"""Índice léxico (SQLite FTS5 / BM25) e vetorial (sqlite-vec) dos chunks de documentação,
com fusão híbrida por Reciprocal Rank Fusion (RRF)."""

from __future__ import annotations

import logging
import math
import os
import re
import sqlite3
import unicodedata
from pathlib import Path

from docserver import embed

logger = logging.getLogger(__name__)

_ESQUEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
    caminho_origem,
    caminho_normalizado,
    titulo_doc,
    secao,
    texto,
    ordem UNINDEXED,
    tokenize = "unicode61 remove_diacritics 2"
);
"""

_ESQUEMA_METADADOS = """
CREATE TABLE IF NOT EXISTS metadados_indice (
    chave TEXT PRIMARY KEY,
    valor TEXT
);
"""

_CAMPOS = ["caminho_origem", "caminho_normalizado", "titulo_doc", "secao", "texto", "ordem"]

_CAMPOS_TEXTO = ["caminho_origem", "caminho_normalizado", "titulo_doc", "secao", "texto"]

_TOKEN = re.compile(r"\w+", re.UNICODE)
_TOKEN_FTS = re.compile(r"[^\W_]+", re.UNICODE)

K_RRF_PADRAO = 60

TIMEOUT_CONEXAO_S = 30.0

# Fração mínima (0-1) do peso IDF dos termos da consulta que um resultado precisa
# cobrir para entrar na busca híbrida só pelo lado léxico (ver `_relevante`). Com
# 0.5, "rate limit da API" num corpus onde "API" é comum descarta chunks que só têm
# "API" (~20% do peso), mas aceita um único termo raro quando os demais nem existem
# no corpus. Ajustável via env sem reindexar.
COBERTURA_LEXICA_MINIMA_PADRAO = 0.5

# Similaridade de cosseno mínima (0-1) para um resultado vetorial ser considerado
# relevante o bastante para aparecer sozinho na busca híbrida. Calibrada empiricamente
# contra o corpus real (relatório de Niterói + calendário acadêmico + docs de exemplo):
# consultas sem nenhuma relação com o corpus (ex.: "receita de bolo") ainda alcançam
# 0.83-0.85 de similaridade com o multilingual-e5-small, que comprime a maioria das
# similaridades na faixa 0.7-0.9 — um corte em 0.80 deixava esse ruído passar. Consultas
# genuinamente respondidas pelo corpus ficaram em 0.87-0.90. Ajustável via env sem
# precisar reindexar.
SIMILARIDADE_MINIMA_PADRAO = 0.85

# Palavras vazias do português (já sem acento, minúsculas) removidas da consulta
# antes de montar a query FTS e de calcular a cobertura léxica — sem isso, uma
# pergunta em linguagem natural ("qual o objetivo do projeto...") faz "o", "do" e
# "projeto" contarem tanto quanto os termos que realmente importam.
STOPWORDS_PT = frozenset(
    """
    a as o os um uma uns umas de do da dos das em no na nos nas por para com sem
    sobre entre ao aos a as e ou que qual quais quando onde como se e foi ser sao
    esta estao seu sua seus suas este esta isso isto aquele aquela aquilo me te
    lhe lhes meu minha teu tua nosso nossa tem ha la ali aqui mas porque pois
    assim mais menos tambem ja so ate depois antes qualquer todo toda todos todas
    """.split()
)


class ErroModeloDivergente(Exception):
    """O índice vetorial foi construído com um modelo/dimensão diferente do atual."""


def criar_indice(caminho: str, compartilhada: bool = False) -> sqlite3.Connection:
    """Abre (ou cria) o banco de índice em `caminho` (use ':memory:' para testes).

    `compartilhada=True` libera o uso da conexão a partir de outras threads — o
    servidor mantém uma única conexão por processo e serializa o acesso com um lock.

    O journal fica em WAL: com o journal padrão, a gravação final de uma ingestão
    (feita por outro processo, como o `docserver watch`) bloqueava as leituras do
    servidor, e uma busca que esperasse mais que o timeout falhava com
    "database is locked". Em WAL, leitores continuam vendo o índice anterior até o
    commit. O modo é persistente no arquivo; o timeout cobre escritores concorrentes."""
    conexao = sqlite3.connect(caminho, timeout=TIMEOUT_CONEXAO_S, check_same_thread=not compartilhada)
    if caminho != ":memory:":
        conexao.execute("PRAGMA journal_mode=WAL")
    conexao.execute(_ESQUEMA)
    conexao.commit()
    return conexao


def contar_chunks(caminho: str) -> int:
    """Quantos chunks o índice em `caminho` tem hoje (0 se o arquivo nem existe)."""
    if caminho != ":memory:" and not Path(caminho).exists():
        return 0
    conexao = criar_indice(caminho)
    try:
        return conexao.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    finally:
        conexao.close()


def limpar_indice(conexao: sqlite3.Connection) -> None:
    """Esvazia o índice por dentro (DROP das tabelas) em vez de apagar o arquivo: no
    Windows o arquivo não pode ser removido enquanto o servidor o mantém aberto."""
    if _tabela_vetorial_existe(conexao):
        _carregar_extensao_vec(conexao)
        conexao.execute("DROP TABLE chunks_vec")
    conexao.execute("DROP TABLE IF EXISTS metadados_indice")
    conexao.execute("DROP TABLE IF EXISTS chunks")
    conexao.execute(_ESQUEMA)
    conexao.commit()


def _carregar_extensao_vec(conexao: sqlite3.Connection) -> None:
    import sqlite_vec

    conexao.enable_load_extension(True)
    sqlite_vec.load(conexao)
    conexao.enable_load_extension(False)


def _tabela_vetorial_existe(conexao: sqlite3.Connection) -> bool:
    linha = conexao.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_vec'"
    ).fetchone()
    return linha is not None


def _garantir_tabela_vetorial(conexao: sqlite3.Connection, dimensao: int) -> None:
    _carregar_extensao_vec(conexao)
    conexao.execute(_ESQUEMA_METADADOS)
    conexao.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0("
        f"chunk_id INTEGER PRIMARY KEY, embedding FLOAT[{dimensao}])"
    )


def _validar_ou_registrar_modelo(conexao: sqlite3.Connection, nome_modelo: str, dimensao: int) -> None:
    conexao.execute(_ESQUEMA_METADADOS)
    linha_modelo = conexao.execute(
        "SELECT valor FROM metadados_indice WHERE chave = 'modelo'"
    ).fetchone()
    if linha_modelo is None:
        conexao.execute(
            "INSERT INTO metadados_indice (chave, valor) VALUES ('modelo', ?)", (nome_modelo,)
        )
        conexao.execute(
            "INSERT INTO metadados_indice (chave, valor) VALUES ('dimensao', ?)", (str(dimensao),)
        )
        conexao.commit()
        return

    linha_dim = conexao.execute(
        "SELECT valor FROM metadados_indice WHERE chave = 'dimensao'"
    ).fetchone()
    modelo_salvo = linha_modelo[0]
    dimensao_salva = int(linha_dim[0]) if linha_dim else None
    if modelo_salvo != nome_modelo or dimensao_salva != dimensao:
        raise ErroModeloDivergente(
            f"o índice foi construído com o modelo '{modelo_salvo}' ({dimensao_salva}d), "
            f"mas o modelo atual é '{nome_modelo}' ({dimensao}d). "
            "Reconstrua o índice com: docserver ingest --limpar"
        )


def indexar_chunks(
    conexao: sqlite3.Connection,
    chunks: list[dict],
    embeddings: list[list[float]] | None = None,
    nome_modelo: str | None = None,
) -> None:
    if embeddings is not None and len(embeddings) != len(chunks):
        raise ValueError("embeddings deve ter o mesmo tamanho que chunks")

    if embeddings:
        dimensao = len(embeddings[0])
        _garantir_tabela_vetorial(conexao, dimensao)
        _validar_ou_registrar_modelo(conexao, nome_modelo or embed.NOME_MODELO, dimensao)

    insercao = f"""
        INSERT INTO chunks ({", ".join(_CAMPOS)})
        VALUES ({", ".join(":" + c for c in _CAMPOS)})
    """

    for i, chunk in enumerate(chunks):
        cursor = conexao.execute(insercao, chunk)
        if embeddings:
            import sqlite_vec

            conexao.execute(
                "INSERT INTO chunks_vec (chunk_id, embedding) VALUES (?, ?)",
                (cursor.lastrowid, sqlite_vec.serialize_float32(embeddings[i])),
            )

    conexao.commit()


def reindexar(
    conexao: sqlite3.Connection,
    chunks: list[dict],
    embeddings: list[list[float]] | None = None,
    nome_modelo: str | None = None,
) -> None:
    conexao.execute("DELETE FROM chunks")
    if _tabela_vetorial_existe(conexao):
        # conexão nova não conhece o módulo vec0 até a extensão ser carregada
        _carregar_extensao_vec(conexao)
        conexao.execute("DELETE FROM chunks_vec")
    indexar_chunks(conexao, chunks, embeddings=embeddings, nome_modelo=nome_modelo)


def _sem_acentos(texto: str) -> str:
    forma = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in forma if not unicodedata.combining(c)).lower()


def _termos_uteis(consulta: str) -> list[str]:
    """Termos da consulta sem stopwords. Uma consulta só com stopwords ("qual é o")
    fica sem termos úteis — melhor não achar nada do que casar qualquer chunk que
    contenha "o" ou "de"."""
    termos = _TOKEN.findall(consulta)
    return [t for t in termos if _sem_acentos(t) not in STOPWORDS_PT]


def _query_fts(consulta: str) -> str:
    """Converte a consulta livre do usuário numa query FTS5 segura (nunca quebra a sintaxe)."""
    termos = _termos_uteis(consulta)
    if not termos:
        return '""'
    return " OR ".join('"' + termo.replace('"', '""') + '"' for termo in termos)


def _sem_prefixo(caminho: str, prefixo: str) -> str:
    return caminho[len(prefixo) :] if caminho.startswith(prefixo) else caminho


def _casa_caminho(relativo: str, alvo: str) -> bool:
    nome = relativo.rsplit("/", 1)[-1]
    return relativo == alvo or relativo.endswith("/" + alvo) or nome == alvo or Path(nome).stem == alvo


def resolver_documento(conexao: sqlite3.Connection, documento: str) -> list[tuple[str, str]]:
    """Resolve um caminho (completo, parcial ou só o nome do arquivo, de origem ou
    normalizado) para os pares `(caminho_origem, caminho_normalizado)` do índice que
    ele identifica — casamento exato, por sufixo de caminho, pelo nome do arquivo ou
    pelo nome sem extensão. Pode devolver mais de um candidato."""
    alvo = documento.strip().replace("\\", "/")
    alvo = _sem_prefixo(_sem_prefixo(alvo, "./"), "docs-fonte/")
    alvo = _sem_prefixo(alvo, "docs-normalizado/")

    pares = conexao.execute(
        "SELECT DISTINCT caminho_origem, caminho_normalizado FROM chunks ORDER BY caminho_origem"
    ).fetchall()
    candidatos = []
    for origem, normalizado in pares:
        if _casa_caminho(_sem_prefixo(origem, "docs-fonte/"), alvo) or _casa_caminho(normalizado, alvo):
            candidatos.append((origem, normalizado))
    return candidatos


def resolver_origem(conexao: sqlite3.Connection, documento: str) -> list[str]:
    """Como `resolver_documento`, mas devolve só os `caminho_origem`."""
    return [origem for origem, _ in resolver_documento(conexao, documento)]


def buscar(conexao: sqlite3.Connection, consulta: str, limite: int = 5, origem: str | None = None) -> list[dict]:
    condicao = "chunks MATCH ?"
    parametros: list = [_query_fts(consulta)]
    if origem:
        condicao += " AND caminho_origem = ?"
        parametros.append(origem)
    parametros.append(limite)

    cursor = conexao.execute(
        f"""
        SELECT rowid AS id, {", ".join(_CAMPOS)}, bm25(chunks) AS score
        FROM chunks
        WHERE {condicao}
        ORDER BY score
        LIMIT ?
        """,
        parametros,
    )
    colunas = [descricao[0] for descricao in cursor.description]
    return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]


def buscar_vetorial(
    conexao: sqlite3.Connection,
    consulta: str,
    limite: int = 20,
    embeddar_consulta_fn=None,
    nome_modelo: str | None = None,
    dimensao: int | None = None,
    origem: str | None = None,
) -> list[dict]:
    if not _tabela_vetorial_existe(conexao):
        return []

    modelo = nome_modelo or embed.NOME_MODELO
    dim = dimensao or embed.DIMENSAO
    _validar_ou_registrar_modelo(conexao, modelo, dim)

    import sqlite_vec

    _carregar_extensao_vec(conexao)
    calcular = embeddar_consulta_fn or embed.embeddar_consulta
    vetor = calcular(consulta)
    vetor_serializado = sqlite_vec.serialize_float32(vetor)

    campos_c = ", ".join("c." + campo for campo in _CAMPOS)
    if origem:
        # o KNN do vec0 (MATCH ... AND k = ?) não filtra por outras colunas antes
        # de aplicar o k, então com filtro por documento faz-se uma varredura exata
        # restrita a ele — o corpus local é pequeno o bastante para isso ser barato.
        cursor = conexao.execute(
            f"""
            SELECT c.rowid AS id, {campos_c}, vec_distance_l2(v.embedding, ?) AS distancia
            FROM chunks_vec v
            JOIN chunks c ON c.rowid = v.chunk_id
            WHERE c.caminho_origem = ?
            ORDER BY distancia
            LIMIT ?
            """,
            (vetor_serializado, origem, limite),
        )
    else:
        cursor = conexao.execute(
            f"""
            SELECT c.rowid AS id, {campos_c}, v.distance AS distancia
            FROM chunks_vec v
            JOIN chunks c ON c.rowid = v.chunk_id
            WHERE v.embedding MATCH ? AND k = ?
            ORDER BY v.distance
            """,
            (vetor_serializado, limite),
        )
    colunas = [descricao[0] for descricao in cursor.description]
    return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]


def fundir_rrf(
    lexico: list[dict],
    vetorial: list[dict],
    peso_lexico: float = 1.0,
    peso_vetorial: float = 1.0,
    k: int = K_RRF_PADRAO,
) -> list[dict]:
    """Reciprocal Rank Fusion: usa apenas a posição em cada lista, nunca o score bruto."""
    pontuacoes: dict = {}
    dados: dict = {}

    for pos, item in enumerate(lexico):
        pontuacoes[item["id"]] = pontuacoes.get(item["id"], 0.0) + peso_lexico / (k + pos + 1)
        dados.setdefault(item["id"], item)

    for pos, item in enumerate(vetorial):
        pontuacoes[item["id"]] = pontuacoes.get(item["id"], 0.0) + peso_vetorial / (k + pos + 1)
        dados.setdefault(item["id"], item)

    ordenados = sorted(pontuacoes.items(), key=lambda par: par[1], reverse=True)
    return [dados[id_] for id_, _ in ordenados]


def _distancia_para_similaridade(distancia: float) -> float:
    """Converte distância L2 em similaridade de cosseno assumindo vetores normalizados
    (norm=1, como `embed.py` passa a gerar): para esses, sim = 1 - distância²/2."""
    return 1.0 - (distancia**2) / 2.0


def _tokens_fts(texto: str) -> set[str]:
    """Tokens como o `unicode61 remove_diacritics` do FTS5 os vê: sequências de letras
    e dígitos (sublinhado separa), minúsculas e sem acento."""
    return set(_TOKEN_FTS.findall(_sem_acentos(texto)))


def _pesos_idf(conexao: sqlite3.Connection, termos: list[str], origem: str | None) -> dict[str, float]:
    """IDF (fórmula do BM25) de cada termo útil, no mesmo escopo da busca. Termos que
    não aparecem em nenhum chunk do escopo ficam de fora: nenhum resultado poderia
    cobri-los, então não devem pesar contra quem cobre os demais."""
    filtro, parametros_origem = (" AND caminho_origem = ?", [origem]) if origem else ("", [])
    total = conexao.execute(
        f"SELECT COUNT(*) FROM chunks WHERE 1=1{filtro}", parametros_origem
    ).fetchone()[0]
    pesos: dict[str, float] = {}
    for termo in dict.fromkeys(termos):
        frequencia = conexao.execute(
            f"SELECT COUNT(*) FROM chunks WHERE chunks MATCH ?{filtro}",
            ['"' + termo.replace('"', '""') + '"', *parametros_origem],
        ).fetchone()[0]
        if frequencia:
            pesos[termo] = math.log((total - frequencia + 0.5) / (frequencia + 0.5) + 1)
    return pesos


def _cobertura_lexica(item: dict, pesos: dict[str, float]) -> float:
    """Fração (0-1) do peso IDF da consulta coberta pelos termos presentes no chunk."""
    total = sum(pesos.values())
    if not total:
        return 0.0
    presentes = _tokens_fts(" ".join(str(item.get(campo) or "") for campo in _CAMPOS_TEXTO))
    coberto = sum(
        peso for termo, peso in pesos.items() if _tokens_fts(termo) <= presentes
    )
    return coberto / total


def _relevante(
    item: dict, ids_lexicos: set, pesos: dict[str, float], cobertura_minima: float, similaridade_minima: float
) -> bool:
    """Um resultado é relevante se cobre boa parte do peso IDF da consulta, ou se a
    similaridade vetorial é alta o bastante para sustentar sozinha.

    Só ter aparecido na lista léxica não basta: a query FTS usa OR, então qualquer
    chunk com um único termo comum ("API", "dados") entrava — em corpus grande isso
    contamina quase toda consulta. Contar termos sem peso também falha no sentido
    oposto (descarta "paginação" sem "endpoints"): ponderar por IDF faz um termo raro
    valer mais que vários comuns, e termos ausentes do corpus não contam."""
    if item["id"] in ids_lexicos and _cobertura_lexica(item, pesos) >= cobertura_minima:
        return True
    similaridade = item.get("similaridade")
    return similaridade is not None and similaridade >= similaridade_minima


def buscar_hibrido(
    conexao: sqlite3.Connection,
    consulta: str,
    limite: int = 5,
    k_rrf: int = K_RRF_PADRAO,
    embeddar_consulta_fn=None,
    nome_modelo: str | None = None,
    dimensao: int | None = None,
    origem: str | None = None,
) -> list[dict]:
    peso_lexico = float(os.environ.get("PESO_LEXICO", 1.0))
    peso_vetorial = float(os.environ.get("PESO_VETORIAL", 1.0))
    cobertura_minima = float(os.environ.get("COBERTURA_LEXICA_MINIMA", COBERTURA_LEXICA_MINIMA_PADRAO))
    similaridade_minima = float(os.environ.get("SIMILARIDADE_MINIMA", SIMILARIDADE_MINIMA_PADRAO))

    lexico = buscar(conexao, consulta, limite=20, origem=origem)
    ids_lexicos = {item["id"] for item in lexico}
    pesos = _pesos_idf(conexao, _termos_uteis(consulta), origem) if lexico else {}

    def _filtrar(itens: list[dict]) -> list[dict]:
        return [
            item
            for item in itens
            if _relevante(item, ids_lexicos, pesos, cobertura_minima, similaridade_minima)
        ]

    if not _tabela_vetorial_existe(conexao):
        logger.warning(
            "índice vetorial ausente — busca híbrida caindo para busca léxica (BM25) pura"
        )
        return _filtrar(lexico)[:limite]

    if peso_vetorial == 0:
        return _filtrar(lexico)[:limite]

    vetorial = buscar_vetorial(
        conexao,
        consulta,
        limite=20,
        embeddar_consulta_fn=embeddar_consulta_fn,
        nome_modelo=nome_modelo,
        dimensao=dimensao,
        origem=origem,
    )
    similaridades = {item["id"]: _distancia_para_similaridade(item["distancia"]) for item in vetorial}
    for item in vetorial:
        item["similaridade"] = similaridades[item["id"]]

    fundido = fundir_rrf(lexico, vetorial, peso_lexico=peso_lexico, peso_vetorial=peso_vetorial, k=k_rrf)
    # um item presente nas duas listas chega da fusão com o dicionário da lista
    # léxica, que não tem similaridade — sem repor aqui, um chunk com cobertura
    # léxica baixa mas similaridade alta seria descartado pelo corte.
    for item in fundido:
        if item["id"] in similaridades:
            item["similaridade"] = similaridades[item["id"]]
    return _filtrar(fundido)[:limite]
