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
