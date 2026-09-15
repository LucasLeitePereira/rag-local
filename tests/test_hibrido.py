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


def test_chunk_que_so_casa_um_termo_comum_da_consulta_e_descartado():
    # regressão C3: a query FTS usa OR, então "rate limit da API" trazia qualquer
    # chunk que só mencionasse "API" — o termo mais comum do corpus.
    conexao = conn()
    chunks = [
        _chunk(ordem=0, texto="O rate limit da API é de 100 requisições por minuto por cliente."),
        *[
            _chunk(ordem=i, texto=f"Capítulo {i}: a API REST serializa os dados em JSON para o consumidor.")
            for i in range(1, 9)
        ],
    ]
    embeddings = [[0.0, 1.0, 0.0]] * len(chunks)  # vetorial não salva ninguém
    index.indexar_chunks(conexao, chunks, embeddings=embeddings, nome_modelo="fake")

    resultados = index.buscar_hibrido(
        conexao,
        "rate limit da API",
        embeddar_consulta_fn=_embeddar_consulta_fixa([1.0, 0.0, 0.0]),
        nome_modelo="fake",
        dimensao=3,
    )

    assert [r["ordem"] for r in resultados] == [0]


def test_chunk_nas_duas_listas_com_cobertura_baixa_mas_similaridade_alta_e_mantido():
    # regressão: a fusão mantinha o dicionário da lista léxica (sem similaridade),
    # então "rate limit da API" descartava a seção em português "Limites de
    # requisição" — que só casa "API" lexicalmente, mas é a mais similar no vetorial.
    conexao = conn()
    chunks = [
        _chunk(ordem=0, texto="O cliente pode fazer até 100 requisições por minuto por chave de API."),
        _chunk(ordem=1, texto="O rate limit do serializador de objetos limita o aninhamento."),
        *[_chunk(ordem=i, texto=f"Capítulo {i}: a API REST serializa dados em JSON.") for i in range(2, 9)],
    ]
    embeddings = [[1.0, 0.0, 0.0]] + [[0.0, 1.0, 0.0]] * (len(chunks) - 1)
    index.indexar_chunks(conexao, chunks, embeddings=embeddings, nome_modelo="fake")

    resultados = index.buscar_hibrido(
        conexao,
        "rate limit da API",
        embeddar_consulta_fn=_embeddar_consulta_fixa([1.0, 0.0, 0.0]),
        nome_modelo="fake",
        dimensao=3,
    )

    assert 0 in [r["ordem"] for r in resultados]


def test_corte_por_cobertura_tambem_vale_sem_indice_vetorial():
    conexao = conn()
    chunks = [
        _chunk(ordem=0, texto="O rate limit da API é de 100 requisições por minuto por cliente."),
        *[
            _chunk(ordem=i, texto=f"Capítulo {i}: a API REST serializa os dados em JSON para o consumidor.")
            for i in range(1, 9)
        ],
    ]
    index.indexar_chunks(conexao, chunks)

    resultados = index.buscar_hibrido(conexao, "rate limit da API")

    assert [r["ordem"] for r in resultados] == [0]


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


def test_reindexar_sem_embeddings_remove_a_camada_vetorial_e_a_busca_nao_chama_o_modelo():
    conexao = conn()
    chunks = [_chunk(texto="Conteúdo sobre faturamento mensal da empresa.")]
    index.indexar_chunks(conexao, chunks, embeddings=[[1.0, 0.0, 0.0]], nome_modelo="fake")

    removida = index.reindexar(conexao, chunks)

    def _nao_chamar(consulta):
        raise AssertionError("não deveria calcular embedding sem camada vetorial")

    assert removida is True
    assert not index._tabela_vetorial_existe(conexao)
    assert conexao.execute("SELECT COUNT(*) FROM metadados_indice WHERE chave = 'modelo'").fetchone()[0] == 0
    resultados = index.buscar_hibrido(conexao, "faturamento", embeddar_consulta_fn=_nao_chamar)
    assert len(resultados) == 1


def test_falha_ao_carregar_o_modelo_cai_para_lexico_com_aviso():
    conexao = conn()
    index.indexar_chunks(
        conexao, [_chunk(texto="Conteúdo sobre faturamento mensal.")], embeddings=[[1.0, 0.0, 0.0]], nome_modelo="fake"
    )

    def _sem_extra(consulta):
        raise ImportError("No module named 'sentence_transformers'")

    avisos = []
    resultados = index.buscar_hibrido(
        conexao, "faturamento", embeddar_consulta_fn=_sem_extra, nome_modelo="fake", dimensao=3, avisos=avisos
    )

    assert len(resultados) == 1
    assert len(avisos) == 1 and "sentence_transformers" in avisos[0] and "léxica" in avisos[0]


def test_modelo_divergente_na_busca_hibrida_cai_para_lexico_com_aviso():
    conexao = conn()
    index.indexar_chunks(
        conexao, [_chunk(texto="Conteúdo sobre faturamento mensal.")], embeddings=[[1.0, 0.0, 0.0]], nome_modelo="modelo-a"
    )

    avisos = []
    resultados = index.buscar_hibrido(
        conexao,
        "faturamento",
        embeddar_consulta_fn=_embeddar_consulta_fixa([1.0, 0.0]),
        nome_modelo="modelo-b",
        dimensao=2,
        avisos=avisos,
    )

    assert len(resultados) == 1
    assert avisos and "modelo-a" in avisos[0]
