from docserver import cli


def _embeddar_falso(chunk):
    texto = chunk["texto"]
    return [float(len(texto) % 7), float(len(texto) % 5), float(len(texto) % 3)]


def _embeddar_consulta_falso(consulta):
    return [float(len(consulta) % 7), float(len(consulta) % 5), float(len(consulta) % 3)]


def test_ingestao_processa_md_e_indexa_chunks(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    docs_normalizado.mkdir()
    (docs_fonte / "guia.md").write_text(
        "# Guia\n\n## Instalação\n\nRode o comando de setup para instalar o sistema.\n",
        encoding="utf-8",
    )
    caminho_indice = str(tmp_path / "indice.db")

    relatorio = cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    assert relatorio["processados"] == 1
    assert relatorio["chunks"] == 1
    assert (docs_normalizado / "guia.md").exists()


def test_ingestao_relatorio_conta_ignorados_e_falhas(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    docs_normalizado.mkdir()
    (docs_fonte / "guia.md").write_text("# Guia\n\nConteúdo.\n", encoding="utf-8")
    (docs_fonte / "planilha.xyz").write_text("formato não suportado", encoding="utf-8")
    caminho_indice = str(tmp_path / "indice.db")

    relatorio = cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    assert relatorio["processados"] == 1
    assert len(relatorio["ignorados"]) == 1


def test_ingestao_ignora_arquivos_ocultos_e_temporarios_do_office(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    docs_normalizado.mkdir()
    (docs_fonte / ".oculto.md").write_text("# Oculto\n\nConteúdo.\n", encoding="utf-8")
    (docs_fonte / "~$rascunho.docx").write_text("temporário do office", encoding="utf-8")
    caminho_indice = str(tmp_path / "indice.db")

    relatorio = cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    assert relatorio["processados"] == 0
    assert relatorio["ignorados"] == []


def test_busca_formata_resultado_com_origem_e_secao(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    docs_normalizado.mkdir()
    (docs_fonte / "guia.md").write_text(
        "# Guia\n\n## Instalação\n\nRode o comando de setup para instalar o sistema.\n",
        encoding="utf-8",
    )
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    resultados = cli.executar_busca(caminho_indice, "instalar")
    texto = cli.formatar_resultados(resultados)

    assert "docs-fonte/guia.md" in texto
    assert "Instalação" in texto


def test_busca_sem_resultado_orienta_proximo_passo():
    texto = cli.formatar_resultados([])

    assert "listar_documentos" in texto or "reformular" in texto.lower()


def test_avaliar_calcula_taxa_de_acerto_por_perfil_no_modo_lexico(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    docs_normalizado.mkdir()
    (docs_fonte / "auth.md").write_text(
        "# Auth\n\n## Renovação\n\nO refresh token dura 30 dias e é rotacionado a cada uso.\n",
        encoding="utf-8",
    )
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    caminho_perguntas = tmp_path / "perguntas.yaml"
    caminho_perguntas.write_text(
        "- pergunta: \"refresh token\"\n"
        "  esperado: docs-fonte/auth.md\n"
        "  perfil: tecnico\n"
        "- pergunta: \"algo que não existe em lugar nenhum\"\n"
        "  esperado: docs-fonte/auth.md\n"
        "  perfil: natural\n",
        encoding="utf-8",
    )

    resultado = cli.executar_avaliacao(caminho_perguntas, caminho_indice)

    assert resultado["lexico"]["tecnico"] == [1, 1]
    assert resultado["lexico"]["natural"] == [0, 1]


def test_ingestao_com_embeddings_grava_modelo_no_indice(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    docs_normalizado.mkdir()
    (docs_fonte / "guia.md").write_text(
        "# Guia\n\n## Seção\n\nConteúdo com bastante texto para não ser descartado.\n",
        encoding="utf-8",
    )
    caminho_indice = str(tmp_path / "indice.db")

    cli.executar_ingestao(
        docs_fonte,
        docs_normalizado,
        caminho_indice,
        embeddar_passagem_fn=_embeddar_falso,
        nome_modelo="fake",
    )

    stats = cli.executar_stats(caminho_indice)
    assert stats["modelo"] == "fake"


def test_ingestao_com_sem_embeddings_nao_grava_modelo(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    docs_normalizado.mkdir()
    (docs_fonte / "guia.md").write_text(
        "# Guia\n\n## Seção\n\nConteúdo com bastante texto para não ser descartado.\n",
        encoding="utf-8",
    )
    caminho_indice = str(tmp_path / "indice.db")

    cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    stats = cli.executar_stats(caminho_indice)
    assert stats["modelo"] is None


def test_busca_com_modo_lexico_nao_usa_vetorial(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    docs_normalizado.mkdir()
    (docs_fonte / "guia.md").write_text(
        "# Guia\n\n## Seção\n\nConteúdo com bastante texto sobre faturamento mensal.\n",
        encoding="utf-8",
    )
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(
        docs_fonte,
        docs_normalizado,
        caminho_indice,
        embeddar_passagem_fn=_embeddar_falso,
        nome_modelo="fake",
    )

    resultados = cli.executar_busca(caminho_indice, "faturamento", modo="lexico")

    assert len(resultados) == 1


def test_avaliar_roda_nos_tres_modos_quando_indice_vetorial_existe(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    docs_normalizado.mkdir()
    (docs_fonte / "auth.md").write_text(
        "# Auth\n\n## Renovação\n\nO refresh token dura 30 dias e é rotacionado a cada uso.\n",
        encoding="utf-8",
    )
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(
        docs_fonte,
        docs_normalizado,
        caminho_indice,
        embeddar_passagem_fn=_embeddar_falso,
        nome_modelo="fake",
    )

    caminho_perguntas = tmp_path / "perguntas.yaml"
    caminho_perguntas.write_text(
        "- pergunta: \"refresh token\"\n"
        "  esperado: docs-fonte/auth.md\n"
        "  perfil: tecnico\n",
        encoding="utf-8",
    )

    resultado = cli.executar_avaliacao(
        caminho_perguntas,
        caminho_indice,
        modos=("lexico", "vetorial", "hibrido"),
        embeddar_consulta_fn=_embeddar_consulta_falso,
        nome_modelo="fake",
        dimensao=3,
    )

    assert set(resultado.keys()) == {"lexico", "vetorial", "hibrido"}
    assert resultado["lexico"]["tecnico"] == [1, 1]


def test_stats_reporta_documentos_e_chunks_indexados(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    docs_normalizado.mkdir()
    (docs_fonte / "guia.md").write_text(
        "# Guia\n\n## Seção\n\nConteúdo com bastante texto para não ser descartado.\n",
        encoding="utf-8",
    )
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    stats = cli.executar_stats(caminho_indice)

    assert stats["documentos"] == 1
    assert stats["chunks"] == 1
    assert stats["modelo"] is None


def test_ingestao_remove_normalizado_orfao_quando_fonte_e_apagada(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    docs_normalizado.mkdir()
    origem = docs_fonte / "temporario.md"
    origem.write_text(
        "# Temporário\n\n## Seção\n\nConteúdo qualquer com texto suficiente para não ser descartado.\n",
        encoding="utf-8",
    )
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)
    assert (docs_normalizado / "temporario.md").exists()

    origem.unlink()
    relatorio = cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    assert not (docs_normalizado / "temporario.md").exists()
    assert relatorio["removidos"] == [str(docs_normalizado / "temporario.md")]
    assert cli.executar_busca(caminho_indice, "temporário") == []


def test_busca_com_documento_restringe_ao_arquivo_indicado(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    docs_normalizado.mkdir()
    (docs_fonte / "a.md").write_text(
        "# Doc A\n\n## Prazo\n\nO prazo de entrega do documento A é de 10 dias.\n", encoding="utf-8"
    )
    (docs_fonte / "b.md").write_text(
        "# Doc B\n\n## Prazo\n\nO prazo de entrega do documento B é de 20 dias.\n", encoding="utf-8"
    )
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    resultados = cli.executar_busca(caminho_indice, "prazo de entrega", origem="docs-fonte/b.md")

    assert len(resultados) == 1
    assert resultados[0]["caminho_origem"] == "docs-fonte/b.md"


def test_formatar_tabela_avaliacao_mostra_colunas_por_modo():
    resultado = {"lexico": {"tecnico": [9, 10], "natural": [3, 10]}}

    tabela = cli.formatar_tabela_avaliacao(resultado)

    assert "lexico" in tabela
    assert "9/10" in tabela
    assert "3/10" in tabela
