import logging

from docserver import index


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


def conn():
    return index.criar_indice(":memory:")


def _embeddar_consulta_fixa(vetor):
    return lambda consulta: vetor


def test_chunk_recuperavel_por_termo_exato_aparece_no_resultado_hibrido():
    conexao = conn()
    chunks = [_chunk(ordem=0, texto="O prazo de entrega padrão é de 30 dias úteis.")]
    embeddings = [[1.0, 0.0, 0.0]]
    index.indexar_chunks(conexao, chunks, embeddings=embeddings, nome_modelo="fake")

    resultados = index.buscar_hibrido(
        conexao,
        "entrega",
        embeddar_consulta_fn=_embeddar_consulta_fixa([1.0, 0.0, 0.0]),
        nome_modelo="fake",
        dimensao=3,
    )

    assert any("entrega" in r["texto"] for r in resultados)


def test_chunk_com_vocabulario_diferente_e_recuperado_pela_via_vetorial():
    conexao = conn()
    chunks = [
        _chunk(ordem=0, texto="Explica o que fazer quando um cliente atrasa o pagamento da fatura."),
        _chunk(ordem=1, texto="Este outro chunk fala sobre um assunto qualquer sem relação nenhuma."),
    ]
    # o chunk 0 não compartilha vocabulário com a consulta em linguagem natural,
    # mas seu embedding é idêntico ao vetor da consulta.
    embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    index.indexar_chunks(conexao, chunks, embeddings=embeddings, nome_modelo="fake")

    resultados = index.buscar_hibrido(
        conexao,
        "inadimplência do consumidor",
        embeddar_consulta_fn=_embeddar_consulta_fixa([1.0, 0.0, 0.0]),
        nome_modelo="fake",
        dimensao=3,
    )

    assert any("atrasa o pagamento" in r["texto"] for r in resultados)


def test_rrf_documento_bem_posicionado_nas_duas_listas_fica_acima_de_um_que_so_aparece_numa():
    lexico = [{"id": 1}, {"id": 2}]
    vetorial = [{"id": 1}, {"id": 3}]

    fundido = index.fundir_rrf(lexico, vetorial, peso_lexico=1.0, peso_vetorial=1.0, k=60)

    posicoes = [item["id"] for item in fundido]
    assert posicoes.index(1) < posicoes.index(2)
    assert posicoes.index(1) < posicoes.index(3)


def test_rrf_usa_posicao_nao_score_alterar_escala_nao_muda_ordem():
    lexico_a = [{"id": 1, "score": 5.0}, {"id": 2, "score": 4.9}]
    lexico_b = [{"id": 1, "score": 500.0}, {"id": 2, "score": 0.001}]
    vetorial = [{"id": 2}, {"id": 1}]

    fundido_a = index.fundir_rrf(lexico_a, vetorial, k=60)
    fundido_b = index.fundir_rrf(lexico_b, vetorial, k=60)

    assert [i["id"] for i in fundido_a] == [i["id"] for i in fundido_b]


def test_peso_vetorial_zero_reproduz_exatamente_a_busca_lexica_pura():
    conexao = conn()
    chunks = [
        _chunk(ordem=0, texto="Configuração de ambiente e variáveis do sistema."),
        _chunk(ordem=1, texto="Outro chunk qualquer sem relação com configuração nenhuma."),
    ]
    embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    index.indexar_chunks(conexao, chunks, embeddings=embeddings, nome_modelo="fake")

    puro = index.buscar(conexao, "configuração", limite=5)

    import os

    os.environ["PESO_VETORIAL"] = "0"
    try:
        hibrido = index.buscar_hibrido(conexao, "configuração", limite=5)
    finally:
        del os.environ["PESO_VETORIAL"]

    assert [r["texto"] for r in hibrido] == [r["texto"] for r in puro]


def test_indice_vetorial_ausente_cai_para_bm25_e_registra_aviso(caplog):
    conexao = conn()
    index.indexar_chunks(conexao, [_chunk(texto="Conteúdo sobre faturamento mensal.")])

    with caplog.at_level(logging.WARNING):
        resultados = index.buscar_hibrido(conexao, "faturamento")

    assert len(resultados) == 1
    assert any("léxic" in registro.message.lower() or "bm25" in registro.message.lower() for registro in caplog.records)


def test_modelo_divergente_gera_erro_explicito_na_abertura_do_indice():
    conexao = conn()
    chunks = [_chunk(texto="Conteúdo qualquer para indexar com o modelo A.")]
    index.indexar_chunks(conexao, chunks, embeddings=[[1.0, 0.0, 0.0]], nome_modelo="modelo-a")

    try:
        index.buscar_vetorial(
            conexao,
            "consulta",
            embeddar_consulta_fn=_embeddar_consulta_fixa([1.0, 0.0]),
            nome_modelo="modelo-b",
            dimensao=2,
        )
        assert False, "deveria ter levantado ErroModeloDivergente"
    except index.ErroModeloDivergente:
        pass
