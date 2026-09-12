from docserver import chunk


def test_documento_com_cabecalho_e_dividido_em_um_chunk_por_secao(com_cabecalhos_md):
    chunks = chunk.chunkar_arquivo(com_cabecalhos_md)

    secoes = [c["secao"] for c in chunks]
    assert secoes == ["Instalação", "Configuração", "Solução de problemas"]


def test_cada_chunk_carrega_o_titulo_do_documento(com_cabecalhos_md):
    chunks = chunk.chunkar_arquivo(com_cabecalhos_md)

    assert all(c["titulo_doc"] == "Manual do Sistema" for c in chunks)


def test_documento_sem_cabecalho_cai_para_blocos_por_tamanho(sem_cabecalhos_md):
    chunks = chunk.chunkar_arquivo(sem_cabecalhos_md)

    assert len(chunks) > 1


def test_blocos_do_fallback_tem_sobreposicao_entre_si(sem_cabecalhos_md):
    chunks = chunk.chunkar_arquivo(sem_cabecalhos_md)

    primeiro_fim = chunks[0]["texto"][-50:]
    segundo_inicio = chunks[1]["texto"][:200]
    assert any(trecho in segundo_inicio for trecho in [primeiro_fim[-20:]])


def test_secao_acima_do_limite_e_subdividida_mantendo_o_nome_da_secao(secao_gigante_md):
    chunks = chunk.chunkar_arquivo(secao_gigante_md)

    chunks_referencia = [c for c in chunks if c["secao"] == "Referência completa"]
    assert len(chunks_referencia) > 1


def test_secao_com_menos_de_30_caracteres_e_descartada(criar_normalizado):
    corpo = (
        "# Doc\n\n"
        "## Vazia\n\ncurto\n\n"
        "## Cheia\n\nEsta seção tem bastante conteúdo textual para não ser descartada.\n"
    )
    caminho = criar_normalizado(corpo, origem="docs-fonte/doc.md", nome="doc.md")

    chunks = chunk.chunkar_arquivo(caminho)

    secoes = [c["secao"] for c in chunks]
    assert "Vazia" not in secoes
    assert "Cheia" in secoes


def test_ordem_original_das_secoes_e_preservada_no_campo_ordem(com_cabecalhos_md):
    chunks = chunk.chunkar_arquivo(com_cabecalhos_md)

    assert [c["ordem"] for c in chunks] == list(range(len(chunks)))


def test_caminho_origem_aponta_para_o_arquivo_original_nao_para_o_normalizado(com_cabecalhos_md):
    chunks = chunk.chunkar_arquivo(com_cabecalhos_md)

    assert all(c["caminho_origem"] == "docs-fonte/manual.md" for c in chunks)
    assert all(c["caminho_normalizado"] == str(com_cabecalhos_md) for c in chunks)
