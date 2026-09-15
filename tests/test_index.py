import pytest

from docserver import index


@pytest.fixture
def conn():
    conexao = index.criar_indice(":memory:")
    yield conexao
    conexao.close()


def _chunk(**kwargs):
    base = {
        "caminho_origem": "docs-fonte/doc.md",
        "caminho_normalizado": "docs-normalizado/doc.md",
        "titulo_doc": "Doc",
        "secao": "Seção",
        "texto": "texto padrão",
        "ordem": 0,
    }
    base.update(kwargs)
    return base


def test_chunk_indexado_e_recuperavel_por_um_termo_do_seu_texto(conn):
    index.indexar_chunks(conn, [_chunk(texto="O prazo de entrega é de 30 dias úteis.")])

    resultados = index.buscar(conn, "entrega")

    assert len(resultados) == 1
    assert "entrega" in resultados[0]["texto"]


def test_busca_ignora_acentuacao(conn):
    index.indexar_chunks(conn, [_chunk(texto="A configuração do sistema fica em config.yaml.")])

    com_acento = index.buscar(conn, "configuração")
    sem_acento = index.buscar(conn, "configuracao")

    assert len(com_acento) == 1
    assert len(sem_acento) == 1


def test_resultado_mais_relevante_vem_primeiro(conn):
    index.indexar_chunks(
        conn,
        [
            _chunk(ordem=0, texto="Este documento menciona token de autenticação uma vez."),
            _chunk(
                ordem=1,
                texto="Token token token: autenticação, renovação de token e expiração de token.",
            ),
        ],
    )

    resultados = index.buscar(conn, "token")

    assert resultados[0]["ordem"] == 1


def test_busca_sem_resultado_retorna_lista_vazia_nao_erro(conn):
    index.indexar_chunks(conn, [_chunk(texto="Conteúdo qualquer.")])

    resultados = index.buscar(conn, "termo-que-nao-existe-em-lugar-nenhum")

    assert resultados == []


def test_reindexar_nao_duplica_chunks(conn):
    chunks = [_chunk(texto="Conteúdo único sobre faturamento.")]
    index.indexar_chunks(conn, chunks)
    index.reindexar(conn, chunks)

    resultados = index.buscar(conn, "faturamento")

    assert len(resultados) == 1


def test_reindexar_com_vetores_em_conexao_nova_nao_falha(tmp_path):
    caminho = str(tmp_path / "indice.db")
    chunks = [_chunk(texto="Conteúdo único sobre faturamento.")]
    embeddings = [[0.1, 0.2, 0.3]]

    primeira = index.criar_indice(caminho)
    index.indexar_chunks(primeira, chunks, embeddings=embeddings, nome_modelo="modelo-teste")
    primeira.close()

    segunda = index.criar_indice(caminho)
    index.reindexar(segunda, chunks, embeddings=embeddings, nome_modelo="modelo-teste")

    assert len(index.buscar(segunda, "faturamento")) == 1
    segunda.close()


def test_indice_em_arquivo_usa_wal_e_leitor_nao_bloqueia_durante_gravacao(tmp_path):
    caminho = str(tmp_path / "indice.db")
    escritor = index.criar_indice(caminho)
    index.indexar_chunks(escritor, [_chunk(texto="Conteúdo antigo sobre faturamento.")])
    assert escritor.execute("PRAGMA journal_mode").fetchone()[0] == "wal"

    leitor = index.criar_indice(caminho)
    try:
        # gravação em andamento (transação aberta, como o reindexar da ingestão)
        escritor.execute("DELETE FROM chunks")
        escritor.execute(
            "INSERT INTO chunks (caminho_origem, texto) VALUES ('docs-fonte/novo.md', 'Conteúdo novo sobre cobrança.')"
        )
        assert escritor.in_transaction

        assert len(index.buscar(leitor, "faturamento")) == 1
        assert index.buscar(leitor, "cobrança") == []

        escritor.commit()
        assert index.buscar(leitor, "faturamento") == []
        assert len(index.buscar(leitor, "cobrança")) == 1
    finally:
        leitor.close()
        escritor.close()


def test_limite_restringe_a_quantidade_de_resultados(conn):
    chunks = [_chunk(ordem=i, texto=f"Chunk número {i} fala sobre relatórios.") for i in range(10)]
    index.indexar_chunks(conn, chunks)

    resultados = index.buscar(conn, "relatórios", limite=3)

    assert len(resultados) == 3


def test_termo_com_aspas_ou_caractere_especial_nao_quebra_a_query_fts(conn):
    index.indexar_chunks(conn, [_chunk(texto="A variável AUTH_TOKEN_TTL define o tempo de vida.")])

    resultados = index.buscar(conn, 'AUTH_TOKEN_TTL "não fechada')

    assert isinstance(resultados, list)


def test_stopwords_da_consulta_nao_geram_falso_match(conn):
    index.indexar_chunks(conn, [_chunk(texto="Conteúdo qualquer que não fala sobre o assunto perguntado.")])

    resultados = index.buscar(conn, "qual é o")

    assert resultados == []


def test_consulta_so_com_stopwords_nao_quebra_a_busca(conn):
    index.indexar_chunks(conn, [_chunk(texto="Conteúdo qualquer.")])

    resultados = index.buscar(conn, "o a de")

    assert isinstance(resultados, list)


def test_busca_com_origem_so_retorna_chunks_daquele_documento(conn):
    index.indexar_chunks(
        conn,
        [
            _chunk(caminho_origem="docs-fonte/a.md", texto="Prazo de entrega do documento A."),
            _chunk(caminho_origem="docs-fonte/b.md", texto="Prazo de entrega do documento B."),
        ],
    )

    resultados = index.buscar(conn, "entrega", origem="docs-fonte/b.md")

    assert len(resultados) == 1
    assert resultados[0]["caminho_origem"] == "docs-fonte/b.md"


def test_resolver_origem_por_nome_de_arquivo_sem_caminho(conn):
    index.indexar_chunks(conn, [_chunk(caminho_origem="docs-fonte/arquitetura/visao-geral.md")])

    candidatos = index.resolver_origem(conn, "visao-geral.md")

    assert candidatos == ["docs-fonte/arquitetura/visao-geral.md"]


def test_palavras_do_caminho_nao_casam_a_busca(conn):
    index.indexar_chunks(
        conn,
        [
            _chunk(
                caminho_origem="docs-fonte/api/contratos.md",
                caminho_normalizado="api/contratos.md",
                texto="Limites de requisição por minuto.",
            )
        ],
    )

    assert index.buscar(conn, "api") == []
    assert index.buscar(conn, "contratos") == []
    assert len(index.buscar(conn, "requisição", origem="docs-fonte/api/contratos.md")) == 1


def test_termo_na_secao_pesa_mais_que_no_texto(conn):
    index.indexar_chunks(
        conn,
        [
            _chunk(ordem=0, secao="Introdução", texto="Aqui se fala de faturamento de passagem, entre outros temas."),
            _chunk(ordem=1, secao="Faturamento", texto="Detalhes do processo mensal, entre outros temas."),
        ],
    )

    assert index.buscar(conn, "faturamento")[0]["ordem"] == 1


def test_pesos_bm25_configuraveis_por_env(conn, monkeypatch):
    index.indexar_chunks(
        conn,
        [
            _chunk(ordem=0, secao="Introdução", texto="Aqui se fala de faturamento de passagem, entre outros temas."),
            _chunk(ordem=1, secao="Faturamento", texto="Detalhes do processo mensal, entre outros temas."),
        ],
    )
    monkeypatch.setenv("PESOS_BM25", "secao=0,texto=1")

    assert index.buscar(conn, "faturamento")[0]["ordem"] == 0


def _criar_indice_v1(caminho):
    import sqlite3

    conexao = sqlite3.connect(caminho)
    conexao.execute(
        "CREATE VIRTUAL TABLE chunks USING fts5(caminho_origem, caminho_normalizado, titulo_doc, "
        'secao, texto, ordem UNINDEXED, tokenize = "unicode61 remove_diacritics 2")'
    )
    conexao.execute(
        "INSERT INTO chunks VALUES ('docs-fonte/velho.md', 'velho.md', 'Velho', 'S', 'conteúdo antigo', 0)"
    )
    conexao.commit()
    conexao.close()


def test_indice_novo_grava_a_versao_atual_do_esquema(conn):
    assert index.versao_esquema(conn) == index.VERSAO_ESQUEMA
    assert index.verificar_esquema(conn) is None


def test_indice_sem_versao_e_reconhecido_como_antigo_e_reindexar_o_recria(tmp_path):
    caminho = str(tmp_path / "indice.db")
    _criar_indice_v1(caminho)

    conexao = index.criar_indice(caminho)
    try:
        assert index.versao_esquema(conexao) == 1
        assert "docserver ingest" in index.verificar_esquema(conexao)
        with pytest.raises(index.ErroEsquemaAntigo):
            index.exigir_esquema_atual(conexao)

        index.reindexar(conexao, [_chunk(texto="Conteúdo novo sobre faturamento.")])

        assert index.verificar_esquema(conexao) is None
        assert [r["texto"] for r in index.buscar(conexao, "faturamento")] == ["Conteúdo novo sobre faturamento."]
        assert index.buscar(conexao, "antigo") == []
    finally:
        conexao.close()


def test_resolver_origem_documento_inexistente_nao_encontra_nada(conn):
    index.indexar_chunks(conn, [_chunk(caminho_origem="docs-fonte/a.md")])

    assert index.resolver_origem(conn, "nao-existe.md") == []
