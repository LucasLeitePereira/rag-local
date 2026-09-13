from docserver import chunk


def _contar_tokens_falso(texto: str) -> int:
    """Estimativa barata (sem carregar o tokenizer real) usada nos testes — mantém
    a suíte rápida e hermética, independente do modelo estar em cache localmente."""
    return len(texto) // 4


def test_documento_com_cabecalho_e_dividido_em_um_chunk_por_secao(com_cabecalhos_md):
    chunks = chunk.chunkar_arquivo(com_cabecalhos_md, contar_tokens_fn=_contar_tokens_falso)

    secoes = [c["secao"] for c in chunks]
    assert secoes == ["Instalação", "Configuração", "Solução de problemas"]


def test_cada_chunk_carrega_o_titulo_do_documento(com_cabecalhos_md):
    chunks = chunk.chunkar_arquivo(com_cabecalhos_md, contar_tokens_fn=_contar_tokens_falso)

    assert all(c["titulo_doc"] == "Manual do Sistema" for c in chunks)


def test_documento_sem_cabecalho_cai_para_blocos_por_tamanho(sem_cabecalhos_md):
    chunks = chunk.chunkar_arquivo(sem_cabecalhos_md, contar_tokens_fn=_contar_tokens_falso)

    assert len(chunks) > 1


def test_blocos_do_fallback_tem_sobreposicao_entre_si(sem_cabecalhos_md):
    chunks = chunk.chunkar_arquivo(sem_cabecalhos_md, contar_tokens_fn=_contar_tokens_falso)

    primeiro_fim = chunks[0]["texto"][-50:]
    segundo_inicio = chunks[1]["texto"][:200]
    assert any(trecho in segundo_inicio for trecho in [primeiro_fim[-20:]])


def test_secao_acima_do_limite_e_subdividida_mantendo_o_nome_da_secao(secao_gigante_md):
    chunks = chunk.chunkar_arquivo(secao_gigante_md, contar_tokens_fn=_contar_tokens_falso)

    chunks_referencia = [c for c in chunks if c["secao"] == "Referência completa"]
    assert len(chunks_referencia) > 1


def test_secao_com_menos_de_30_caracteres_e_descartada(criar_normalizado):
    corpo = (
        "# Doc\n\n"
        "## Vazia\n\ncurto\n\n"
        "## Cheia\n\nEsta seção tem bastante conteúdo textual para não ser descartada.\n"
    )
    caminho = criar_normalizado(corpo, origem="docs-fonte/doc.md", nome="doc.md")

    chunks = chunk.chunkar_arquivo(caminho, contar_tokens_fn=_contar_tokens_falso)

    secoes = [c["secao"] for c in chunks]
    assert "Vazia" not in secoes
    assert "Cheia" in secoes


def test_ordem_original_das_secoes_e_preservada_no_campo_ordem(com_cabecalhos_md):
    chunks = chunk.chunkar_arquivo(com_cabecalhos_md, contar_tokens_fn=_contar_tokens_falso)

    assert [c["ordem"] for c in chunks] == list(range(len(chunks)))


def test_caminho_origem_aponta_para_o_arquivo_original_nao_para_o_normalizado(com_cabecalhos_md):
    chunks = chunk.chunkar_arquivo(com_cabecalhos_md, contar_tokens_fn=_contar_tokens_falso)

    assert all(c["caminho_origem"] == "docs-fonte/manual.md" for c in chunks)
    assert all(c["caminho_normalizado"] == str(com_cabecalhos_md) for c in chunks)


def test_nenhum_chunk_ultrapassa_max_tokens_mesmo_com_paragrafo_unico_gigante(criar_normalizado):
    paragrafo_gigante = " ".join(f"palavra{i}" for i in range(2000))  # um só parágrafo, sem \n\n nem pontuação
    corpo = f"# Doc\n\n## Seção única\n\n{paragrafo_gigante}\n"
    caminho = criar_normalizado(corpo, origem="docs-fonte/doc.md", nome="doc.md")

    chunks = chunk.chunkar_arquivo(caminho, contar_tokens_fn=_contar_tokens_falso)

    assert len(chunks) > 1
    assert all(_contar_tokens_falso(c["texto"]) <= chunk.MAX_TOKENS_CHUNK for c in chunks)


def test_texto_antes_do_primeiro_cabecalho_de_secao_nao_e_perdido(criar_normalizado):
    corpo = (
        "Texto de abertura do documento, fora de qualquer cabeçalho, mas com "
        "conteúdo relevante que precisa continuar pesquisável no índice.\n\n"
        "## Primeira seção\n\n"
        "Conteúdo da primeira seção, com bastante texto para não ser descartado.\n"
    )
    caminho = criar_normalizado(corpo, origem="docs-fonte/sem-h1.md", nome="sem-h1.md")

    chunks = chunk.chunkar_arquivo(caminho, contar_tokens_fn=_contar_tokens_falso)

    textos = [c["texto"] for c in chunks]
    assert any("Texto de abertura do documento" in t for t in textos)


def test_titulo_cai_para_primeira_linha_quando_nao_ha_cabecalho(criar_normalizado):
    corpo = "Texto corrido sem nenhum cabeçalho, só parágrafos soltos.\n\nSegundo parágrafo qualquer.\n"
    caminho = criar_normalizado(corpo, origem="docs-fonte/sem-titulo.md", nome="sem-titulo.md")

    chunks = chunk.chunkar_arquivo(caminho, contar_tokens_fn=_contar_tokens_falso)

    assert chunks[0]["titulo_doc"] == "Texto corrido sem nenhum cabeçalho, só parágrafos soltos."
