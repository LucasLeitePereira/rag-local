"""Índice léxico (SQLite FTS5 / BM25) e vetorial (sqlite-vec) dos chunks de documentação,
com fusão híbrida por Reciprocal Rank Fusion (RRF)."""

from __future__ import annotations

import logging
import os
import re
import sqlite3

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

_TOKEN = re.compile(r"\w+", re.UNICODE)

K_RRF_PADRAO = 60


class ErroModeloDivergente(Exception):
    """O índice vetorial foi construído com um modelo/dimensão diferente do atual."""


def criar_indice(caminho: str) -> sqlite3.Connection:
    """Abre (ou cria) o banco de índice em `caminho` (use ':memory:' para testes)."""
    conexao = sqlite3.connect(caminho)
    conexao.execute(_ESQUEMA)
    conexao.commit()
    return conexao


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


def _query_fts(consulta: str) -> str:
    """Converte a consulta livre do usuário numa query FTS5 segura (nunca quebra a sintaxe)."""
    termos = _TOKEN.findall(consulta)
    if not termos:
        return '""'
    return " OR ".join('"' + termo.replace('"', '""') + '"' for termo in termos)


def buscar(conexao: sqlite3.Connection, consulta: str, limite: int = 5) -> list[dict]:
    cursor = conexao.execute(
        f"""
        SELECT rowid AS id, {", ".join(_CAMPOS)}, bm25(chunks) AS score
        FROM chunks
        WHERE chunks MATCH ?
        ORDER BY score
        LIMIT ?
        """,
        (_query_fts(consulta), limite),
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

    cursor = conexao.execute(
        f"""
        SELECT c.rowid AS id, {", ".join("c." + campo for campo in _CAMPOS)}, v.distance AS distancia
        FROM chunks_vec v
        JOIN chunks c ON c.rowid = v.chunk_id
        WHERE v.embedding MATCH ? AND k = ?
        ORDER BY v.distance
        """,
        (sqlite_vec.serialize_float32(vetor), limite),
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


def buscar_hibrido(
    conexao: sqlite3.Connection,
    consulta: str,
    limite: int = 5,
    k_rrf: int = K_RRF_PADRAO,
    embeddar_consulta_fn=None,
    nome_modelo: str | None = None,
    dimensao: int | None = None,
) -> list[dict]:
    peso_lexico = float(os.environ.get("PESO_LEXICO", 1.0))
    peso_vetorial = float(os.environ.get("PESO_VETORIAL", 1.0))

    lexico = buscar(conexao, consulta, limite=20)

    if not _tabela_vetorial_existe(conexao):
        logger.warning(
            "índice vetorial ausente — busca híbrida caindo para busca léxica (BM25) pura"
        )
        return lexico[:limite]

    if peso_vetorial == 0:
        return lexico[:limite]

    vetorial = buscar_vetorial(
        conexao,
        consulta,
        limite=20,
        embeddar_consulta_fn=embeddar_consulta_fn,
        nome_modelo=nome_modelo,
        dimensao=dimensao,
    )
    fundido = fundir_rrf(lexico, vetorial, peso_lexico=peso_lexico, peso_vetorial=peso_vetorial, k=k_rrf)
    return fundido[:limite]
