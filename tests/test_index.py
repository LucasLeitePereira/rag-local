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


def test_limite_restringe_a_quantidade_de_resultados(conn):
    chunks = [_chunk(ordem=i, texto=f"Chunk número {i} fala sobre relatórios.") for i in range(10)]
    index.indexar_chunks(conn, chunks)

    resultados = index.buscar(conn, "relatórios", limite=3)

    assert len(resultados) == 3


def test_termo_com_aspas_ou_caractere_especial_nao_quebra_a_query_fts(conn):
    index.indexar_chunks(conn, [_chunk(texto="A variável AUTH_TOKEN_TTL define o tempo de vida.")])

    resultados = index.buscar(conn, 'AUTH_TOKEN_TTL "não fechada')

    assert isinstance(resultados, list)
