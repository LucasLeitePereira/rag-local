"""Índice léxico (SQLite FTS5 / BM25) dos chunks de documentação."""

from __future__ import annotations

import re
import sqlite3

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

_CAMPOS = ["caminho_origem", "caminho_normalizado", "titulo_doc", "secao", "texto", "ordem"]

_TOKEN = re.compile(r"\w+", re.UNICODE)


def criar_indice(caminho: str) -> sqlite3.Connection:
    """Abre (ou cria) o banco de índice em `caminho` (use ':memory:' para testes)."""
    conexao = sqlite3.connect(caminho)
    conexao.execute(_ESQUEMA)
    conexao.commit()
    return conexao


def indexar_chunks(conexao: sqlite3.Connection, chunks: list[dict]) -> None:
    conexao.executemany(
        f"""
        INSERT INTO chunks ({", ".join(_CAMPOS)})
        VALUES ({", ".join(":" + c for c in _CAMPOS)})
        """,
        chunks,
    )
    conexao.commit()


def reindexar(conexao: sqlite3.Connection, chunks: list[dict]) -> None:
    conexao.execute("DELETE FROM chunks")
    indexar_chunks(conexao, chunks)


def _query_fts(consulta: str) -> str:
    """Converte a consulta livre do usuário numa query FTS5 segura (nunca quebra a sintaxe)."""
    termos = _TOKEN.findall(consulta)
    if not termos:
        return '""'
    return " OR ".join('"' + termo.replace('"', '""') + '"' for termo in termos)


def buscar(conexao: sqlite3.Connection, consulta: str, limite: int = 5) -> list[dict]:
    cursor = conexao.execute(
        f"""
        SELECT {", ".join(_CAMPOS)}, bm25(chunks) AS score
        FROM chunks
        WHERE chunks MATCH ?
        ORDER BY score
        LIMIT ?
        """,
        (_query_fts(consulta), limite),
    )
    colunas = [descricao[0] for descricao in cursor.description]
    return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
