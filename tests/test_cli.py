from docserver import cli


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

    relatorio = cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice)

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

    relatorio = cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice)

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

    relatorio = cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice)

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
    cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice)

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
    cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice)

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


def test_formatar_tabela_avaliacao_mostra_colunas_por_modo():
    resultado = {"lexico": {"tecnico": [9, 10], "natural": [3, 10]}}

    tabela = cli.formatar_tabela_avaliacao(resultado)

    assert "lexico" in tabela
    assert "9/10" in tabela
    assert "3/10" in tabela
