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

# Versão do formato do índice, gravada em `metadados_indice`. Mudou o esquema (colunas,
# tabelas, o que vai em cada uma)? Incremente: a próxima ingestão reconstrói o índice
# sozinha, e o servidor avisa em vez de falhar com "no such column".
#   1 — sem versão gravada; caminhos indexados no FTS
#   2 — caminhos UNINDEXED e pesos BM25 por coluna (TASK-008)
#   3 — pagina_inicio / pagina_fim (TASK-006)
#   4 — tabela `arquivos` para a ingestão incremental (TASK-005)
VERSAO_ESQUEMA = 4

# Os caminhos ficam UNINDEXED: continuam filtráveis (`caminho_origem = ?`) e
# devolvidos na busca, mas as palavras deles não casam consultas — "api" no nome da
# pasta fazia todo chunk do arquivo pontuar para "api".
_ESQUEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
    caminho_origem UNINDEXED,
    caminho_normalizado UNINDEXED,
    titulo_doc,
    secao,
    texto,
    ordem UNINDEXED,
    pagina_inicio UNINDEXED,
    pagina_fim UNINDEXED,
    tokenize = "unicode61 remove_diacritics 2"
);
"""

_ESQUEMA_METADADOS = """
CREATE TABLE IF NOT EXISTS metadados_indice (
    chave TEXT PRIMARY KEY,
    valor TEXT
);
"""

# Um registro por arquivo de origem indexado: o sha256 decide, na próxima ingestão,
# se o arquivo pode ser pulado (sem extrair nem gerar embeddings).
_ESQUEMA_ARQUIVOS = """
CREATE TABLE IF NOT EXISTS arquivos (
    caminho_origem TEXT PRIMARY KEY,
    caminho_normalizado TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    tamanho INTEGER NOT NULL,
    chunks INTEGER NOT NULL,
    extrator TEXT,
    ingerido_em TEXT
);
"""

_CAMPOS_ARQUIVO = ["caminho_origem", "caminho_normalizado", "sha256", "tamanho", "chunks", "extrator", "ingerido_em"]

_CAMPOS = [
    "caminho_origem",
    "caminho_normalizado",
    "titulo_doc",
    "secao",
    "texto",
    "ordem",
    "pagina_inicio",
    "pagina_fim",
]

# Campos cujos termos contam para a cobertura léxica (ver `_cobertura_lexica`): os
# mesmos que o FTS indexa.
_CAMPOS_TEXTO = ["titulo_doc", "secao", "texto"]

# Peso de cada coluna indexada no BM25. A seção pesa o dobro: um termo no nome da
# seção indica o assunto do trecho inteiro. O título fica em 1 porque é igual em
# todos os chunks do documento — pesá-lo mais faria o documento todo empatar no topo.
# Colunas ausentes pesam 0. Ajustável sem reindexar: PESOS_BM25="secao=3,texto=1".
PESOS_BM25_PADRAO = {"titulo_doc": 1.0, "secao": 2.0, "texto": 1.0}


class ErroEsquemaAntigo(Exception):
    """O índice foi gravado num formato anterior ao atual; precisa de nova ingestão."""


def _pesos_bm25() -> list[float]:
    pesos = dict(PESOS_BM25_PADRAO)
    configurado = os.environ.get("PESOS_BM25")
    if configurado:
        pesos = {}
        for par in configurado.split(","):
            coluna, _, valor = par.partition("=")
            pesos[coluna.strip()] = float(valor)
    return [pesos.get(campo, 0.0) for campo in _CAMPOS]

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
    if not _tabela_existe(conexao, "chunks"):
        _criar_esquema(conexao)
        conexao.commit()
    return conexao


def _tabela_existe(conexao: sqlite3.Connection, nome: str) -> bool:
    linha = conexao.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (nome,)
    ).fetchone()
    return linha is not None


def _criar_esquema(conexao: sqlite3.Connection) -> None:
    conexao.execute(_ESQUEMA)
    conexao.execute(_ESQUEMA_METADADOS)
    conexao.execute(_ESQUEMA_ARQUIVOS)
    conexao.execute(
        "INSERT OR REPLACE INTO metadados_indice (chave, valor) VALUES ('versao_esquema', ?)",
        (str(VERSAO_ESQUEMA),),
    )


def versao_esquema(conexao: sqlite3.Connection) -> int:
    """Versão gravada no índice; 1 para índices anteriores ao versionamento."""
    if not _tabela_existe(conexao, "metadados_indice"):
        return 1
    linha = conexao.execute(
        "SELECT valor FROM metadados_indice WHERE chave = 'versao_esquema'"
    ).fetchone()
    return int(linha[0]) if linha else 1


def verificar_esquema(conexao: sqlite3.Connection) -> str | None:
    """Mensagem para o usuário se o índice está num formato diferente do atual, ou None."""
    versao = versao_esquema(conexao)
    if versao == VERSAO_ESQUEMA:
        return None
    return (
        f"o índice está num formato antigo (versão {versao}; a atual é {VERSAO_ESQUEMA}). "
        "Rode 'docserver ingest' para reconstruí-lo."
    )


def exigir_esquema_atual(conexao: sqlite3.Connection) -> None:
    mensagem = verificar_esquema(conexao)
    if mensagem:
        raise ErroEsquemaAntigo(mensagem)


def recriar_esquema(conexao: sqlite3.Connection) -> None:
    """Apaga todas as tabelas do índice e cria as do formato atual, sem commit — quem
    chama decide se isso entra numa transação maior (ver `reindexar`)."""
    if _tabela_vetorial_existe(conexao):
        _carregar_extensao_vec(conexao)
        conexao.execute("DROP TABLE chunks_vec")
    conexao.execute("DROP TABLE IF EXISTS metadados_indice")
    conexao.execute("DROP TABLE IF EXISTS arquivos")
    conexao.execute("DROP TABLE IF EXISTS chunks")
    _criar_esquema(conexao)


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
    recriar_esquema(conexao)
    conexao.commit()


def _carregar_extensao_vec(conexao: sqlite3.Connection) -> None:
    import sqlite_vec

    conexao.enable_load_extension(True)
    sqlite_vec.load(conexao)
    conexao.enable_load_extension(False)


def _tabela_vetorial_existe(conexao: sqlite3.Connection) -> bool:
    return _tabela_existe(conexao, "chunks_vec")


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
            "Rode 'docserver ingest': ele reconstrói o índice com o modelo atual."
        )


def indexar_chunks(
    conexao: sqlite3.Connection,
    chunks: list[dict],
    embeddings: list[list[float]] | None = None,
    nome_modelo: str | None = None,
    commit: bool = True,
) -> None:
    """Insere chunks (e vetores). `commit=False` deixa a gravação dentro da transação
    de quem chama (ver `atualizar_indice`)."""
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
        cursor = conexao.execute(insercao, {campo: chunk.get(campo) for campo in _CAMPOS})
        if embeddings:
            import sqlite_vec

            conexao.execute(
                "INSERT INTO chunks_vec (chunk_id, embedding) VALUES (?, ?)",
                (cursor.lastrowid, sqlite_vec.serialize_float32(embeddings[i])),
            )

    if commit:
        conexao.commit()


def remover_camada_vetorial(conexao: sqlite3.Connection) -> bool:
    """Apaga a tabela vetorial e o modelo registrado. Devolve True se havia camada.

    Esvaziar só as linhas de `chunks_vec` não basta: com a tabela e o modelo ainda
    registrados, a busca híbrida continuava achando que havia vetores e tentava
    carregar o modelo — numa instalação sem a extra `embeddings`, ImportError em vez
    do fallback para BM25."""
    if not _tabela_vetorial_existe(conexao):
        return False
    _carregar_extensao_vec(conexao)
    conexao.execute("DROP TABLE chunks_vec")
    conexao.execute(_ESQUEMA_METADADOS)
    conexao.execute("DELETE FROM metadados_indice WHERE chave IN ('modelo', 'dimensao')")
    return True


def reindexar(
    conexao: sqlite3.Connection,
    chunks: list[dict],
    embeddings: list[list[float]] | None = None,
    nome_modelo: str | None = None,
) -> bool:
    """Substitui todo o conteúdo do índice. Sem embeddings, a camada vetorial é
    removida (ver `remover_camada_vetorial`). Devolve True se isso aconteceu.
    Um índice em formato antigo é recriado no formato atual antes de gravar."""
    if verificar_esquema(conexao):
        recriar_esquema(conexao)
    conexao.execute("DELETE FROM chunks")
    camada_removida = False
    if not embeddings:
        camada_removida = remover_camada_vetorial(conexao)
    elif _tabela_vetorial_existe(conexao):
        # conexão nova não conhece o módulo vec0 até a extensão ser carregada
        _carregar_extensao_vec(conexao)
        conexao.execute("DELETE FROM chunks_vec")
    indexar_chunks(conexao, chunks, embeddings=embeddings, nome_modelo=nome_modelo)
    return camada_removida


def modelo_registrado(conexao: sqlite3.Connection) -> str | None:
    """Nome do modelo de embeddings gravado no índice, ou None sem camada vetorial."""
    if not _tabela_existe(conexao, "metadados_indice"):
        return None
    linha = conexao.execute("SELECT valor FROM metadados_indice WHERE chave = 'modelo'").fetchone()
    return linha[0] if linha else None


def chunks_sem_vetor(conexao: sqlite3.Connection) -> int:
    """Quantos chunks não têm vetor (todos, se não há camada vetorial)."""
    total = conexao.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    if not _tabela_vetorial_existe(conexao):
        return total
    _carregar_extensao_vec(conexao)
    return total - conexao.execute("SELECT COUNT(*) FROM chunks_vec").fetchone()[0]


def arquivos_registrados(conexao: sqlite3.Connection) -> dict[str, dict]:
    """{caminho_origem: registro} dos arquivos indexados; vazio em índice de formato antigo."""
    if verificar_esquema(conexao) or not _tabela_existe(conexao, "arquivos"):
        return {}
    cursor = conexao.execute(f"SELECT {', '.join(_CAMPOS_ARQUIVO)} FROM arquivos")
    return {linha[0]: dict(zip(_CAMPOS_ARQUIVO, linha)) for linha in cursor.fetchall()}


def origens_indexadas(conexao: sqlite3.Connection) -> set[str]:
    """Origens com chunks no índice ou registradas em `arquivos` (inclui as sem chunks)."""
    origens = {linha[0] for linha in conexao.execute("SELECT DISTINCT caminho_origem FROM chunks")}
    if _tabela_existe(conexao, "arquivos"):
        origens |= {linha[0] for linha in conexao.execute("SELECT caminho_origem FROM arquivos")}
    return origens


def atualizar_indice(
    conexao: sqlite3.Connection,
    chunks: list[dict],
    registros: list[dict],
    remover_origens: list[str],
    embeddings: list[list[float]] | None = None,
    nome_modelo: str | None = None,
    reconstruir: bool = False,
) -> bool:
    """Gravação da ingestão incremental numa única transação: apaga chunks, vetores e
    registros das origens em `remover_origens` e das reprocessadas (as de `registros`),
    insere os chunks novos e grava os registros. Um erro no meio desfaz tudo — leitores
    (WAL) continuam vendo o índice anterior.

    `embeddings=None` significa ingestão sem embeddings: a camada vetorial é removida
    (devolve True se havia uma). Com `reconstruir` (ou índice em formato antigo), o
    esquema é recriado do zero antes da gravação."""
    if conexao.in_transaction:
        conexao.commit()
    conexao.execute("BEGIN IMMEDIATE")
    try:
        if reconstruir or verificar_esquema(conexao):
            recriar_esquema(conexao)

        vetorial = _tabela_vetorial_existe(conexao)
        if vetorial:
            _carregar_extensao_vec(conexao)
        origens = set(remover_origens) | {r["caminho_origem"] for r in registros}
        for origem in sorted(origens):
            ids = [
                linha[0]
                for linha in conexao.execute("SELECT rowid FROM chunks WHERE caminho_origem = ?", (origem,))
            ]
            if vetorial:
                conexao.executemany("DELETE FROM chunks_vec WHERE chunk_id = ?", [(i,) for i in ids])
            conexao.execute("DELETE FROM chunks WHERE caminho_origem = ?", (origem,))
            conexao.execute("DELETE FROM arquivos WHERE caminho_origem = ?", (origem,))

        camada_removida = remover_camada_vetorial(conexao) if embeddings is None else False
        indexar_chunks(conexao, chunks, embeddings=embeddings or None, nome_modelo=nome_modelo, commit=False)
        conexao.executemany(
            f"INSERT INTO arquivos ({', '.join(_CAMPOS_ARQUIVO)}) "
            f"VALUES ({', '.join(':' + c for c in _CAMPOS_ARQUIVO)})",
            registros,
        )
        conexao.commit()
    except BaseException:
        conexao.rollback()
        raise
    return camada_removida


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
        SELECT rowid AS id, {", ".join(_CAMPOS)}, bm25(chunks, {", ".join("?" * len(_CAMPOS))}) AS score
        FROM chunks
        WHERE {condicao}
        ORDER BY score
        LIMIT ?
        """,
        [*_pesos_bm25(), *parametros],
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
    avisos: list[str] | None = None,
) -> list[dict]:
    """Busca híbrida (BM25 + vetorial, fundidas por RRF) com corte de relevância.

    Se a via vetorial falhar — extra `embeddings` não instalada, modelo divergente do
    índice, extensão sqlite-vec indisponível —, a busca segue só com o léxico em vez
    de devolver o erro cru: o motivo é registrado no log e acrescentado a `avisos`
    (quando informado) para quem chama mostrar ao usuário ou ao agente."""
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

    try:
        vetorial = buscar_vetorial(
            conexao,
            consulta,
            limite=20,
            embeddar_consulta_fn=embeddar_consulta_fn,
            nome_modelo=nome_modelo,
            dimensao=dimensao,
            origem=origem,
        )
    except (ImportError, ErroModeloDivergente, sqlite3.OperationalError) as erro:
        motivo = str(erro) or type(erro).__name__
        logger.warning("busca vetorial indisponível (%s) — caindo para busca léxica (BM25) pura", motivo)
        if avisos is not None:
            avisos.append(
                f"busca semântica indisponível ({motivo}); os resultados vêm apenas da busca léxica."
            )
        return _filtrar(lexico)[:limite]
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
