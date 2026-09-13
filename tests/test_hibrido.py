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


def test_hibrido_com_origem_so_retorna_chunks_daquele_documento():
    conexao = conn()
    chunks = [
        _chunk(caminho_origem="docs-fonte/a.md", ordem=0, texto="Prazo de entrega do contrato A."),
        _chunk(caminho_origem="docs-fonte/b.md", ordem=0, texto="Prazo de entrega do contrato B."),
    ]
    embeddings = [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
    index.indexar_chunks(conexao, chunks, embeddings=embeddings, nome_modelo="fake")

    resultados = index.buscar_hibrido(
        conexao,
        "prazo de entrega",
        origem="docs-fonte/b.md",
        embeddar_consulta_fn=_embeddar_consulta_fixa([1.0, 0.0, 0.0]),
        nome_modelo="fake",
        dimensao=3,
    )

    assert resultados
    assert all(r["caminho_origem"] == "docs-fonte/b.md" for r in resultados)


def test_chunk_sem_relacao_com_a_consulta_e_descartado_do_hibrido():
    conexao = conn()
    chunks = [
        _chunk(ordem=0, texto="Calendário de feriados e datas letivas da faculdade."),
        _chunk(ordem=1, texto="Explica o objetivo do projeto de segurança urbana da prefeitura."),
    ]
    # embedding do chunk 0 ortogonal à consulta (similaridade baixa); chunk 1 idêntico.
    embeddings = [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]
    index.indexar_chunks(conexao, chunks, embeddings=embeddings, nome_modelo="fake")

    resultados = index.buscar_hibrido(
        conexao,
        "objetivo do projeto de segurança urbana",
        embeddar_consulta_fn=_embeddar_consulta_fixa([1.0, 0.0, 0.0]),
        nome_modelo="fake",
        dimensao=3,
    )

    textos = [r["texto"] for r in resultados]
    assert any("segurança urbana" in t for t in textos)
    assert not any("Calendário" in t for t in textos)


def test_hibrido_sem_nenhum_resultado_relevante_devolve_lista_vazia():
    conexao = conn()
    chunks = [_chunk(ordem=0, texto="Um assunto qualquer, completamente sem relação com a busca.")]
    embeddings = [[0.0, 1.0, 0.0]]
    index.indexar_chunks(conexao, chunks, embeddings=embeddings, nome_modelo="fake")

    resultados = index.buscar_hibrido(
        conexao,
        "receita de bolo de cenoura",
        embeddar_consulta_fn=_embeddar_consulta_fixa([1.0, 0.0, 0.0]),
        nome_modelo="fake",
        dimensao=3,
    )

    assert resultados == []


def test_acerto_lexico_em_apenas_um_termo_raro_nao_e_descartado_pelo_corte_de_relevancia():
    # regressão: um corte de relevância que exige cobertura de >=50% dos termos da
    # consulta é mais rígido que o próprio BM25 que gerou a lista léxica — um chunk
    # pode ser o melhor resultado léxico contendo só um dos termos (ex.: "paginação"
    # sem "endpoints") e ainda assim era descartado antes desta correção.
    conexao = conn()
    chunks = [
        _chunk(ordem=0, texto="Listagens usam paginação por cursor, sem número de página."),
        _chunk(ordem=1, texto="Um chunk qualquer, sem relação nenhuma com a consulta."),
    ]
    # embeddings ortogonais à consulta nos dois chunks: só o léxico deveria salvar o acerto.
    embeddings = [[0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    index.indexar_chunks(conexao, chunks, embeddings=embeddings, nome_modelo="fake")

    resultados = index.buscar_hibrido(
        conexao,
        "como funciona a paginação dos endpoints",
        embeddar_consulta_fn=_embeddar_consulta_fixa([1.0, 0.0, 0.0]),
        nome_modelo="fake",
        dimensao=3,
    )

    assert any("paginação" in r["texto"] for r in resultados)


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
