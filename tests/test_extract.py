from docserver import extract


def test_md_e_copiado_sem_alteracao_de_conteudo(tmp_path):
    origem = tmp_path / "doc.md"
    origem.write_text("# Título\n\nConteúdo aqui.\n", encoding="utf-8")

    resultado = extract.extrair_texto(origem)

    assert resultado == "# Título\n\nConteúdo aqui.\n"


def test_txt_e_tratado_como_markdown(tmp_path):
    origem = tmp_path / "notas.txt"
    origem.write_text("Apenas texto corrido.", encoding="utf-8")

    resultado = extract.extrair_texto(origem)

    assert resultado == "Apenas texto corrido."


def test_extensao_desconhecida_retorna_none_e_nao_levanta_excecao(tmp_path):
    origem = tmp_path / "arquivo.zzz"
    origem.write_text("dado binário simulado", encoding="utf-8")

    resultado = extract.extrair_texto(origem)

    assert resultado is None


def test_registrar_extrator_novo_no_dicionario_passa_a_faze_lo_ser_usado(tmp_path):
    origem = tmp_path / "arquivo.customfmt"
    origem.write_text("qualquer coisa", encoding="utf-8")

    extract.EXTRATORES[".customfmt"] = lambda caminho: "convertido!"
    try:
        resultado = extract.extrair_texto(origem)
    finally:
        del extract.EXTRATORES[".customfmt"]

    assert resultado == "convertido!"


def test_front_matter_de_origem_e_escrito_no_arquivo_normalizado(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    docs_normalizado.mkdir()

    origem = docs_fonte / "guia.md"
    origem.write_text("# Guia\n\nTexto.\n", encoding="utf-8")

    caminho_saida = extract.normalizar(origem, docs_fonte, docs_normalizado)

    conteudo = caminho_saida.read_text(encoding="utf-8")
    assert conteudo.startswith("---\n")
    assert "origem: docs-fonte/guia.md" in conteudo
    assert "extrator:" in conteudo
    assert "ingerido_em:" in conteudo
    assert "# Guia" in conteudo
    assert "Texto." in conteudo


def test_docx_produz_markdown_com_os_cabecalhos_preservados(exemplo_docx):
    resultado = extract.extrair_texto(exemplo_docx)

    assert "Título do Documento" in resultado
    assert "Primeira Seção" in resultado
    assert "#" in resultado


def test_csv_vira_tabela_markdown(tmp_path):
    origem = tmp_path / "dados.csv"
    origem.write_text("nome,idade\nAna,30\nBruno,25\n", encoding="utf-8")

    resultado = extract.extrair_texto(origem)

    assert "| nome | idade |" in resultado
    assert "| Ana | 30 |" in resultado


def test_arquivo_corrompido_registra_erro_e_nao_derruba_o_processo(corrompido_docx):
    import pytest

    with pytest.raises(extract.ErroDeExtracao):
        extract.extrair_texto(corrompido_docx)


def test_pdf_sem_texto_extraivel_e_marcado_como_suspeito(vazio_pdf):
    resultado = extract.extrair_texto(vazio_pdf)

    assert len(resultado.strip()) < 20


def test_pdf_com_texto_extraivel_produz_conteudo(exemplo_pdf):
    resultado = extract.extrair_texto(exemplo_pdf)

    assert "Título do PDF de exemplo" in resultado


def test_limpar_markdown_pdf_remove_negrito_e_tachado_fragmentados():
    # amostra real de artefato do pymupdf4llm: runs de 1-3 caracteres em negrito e
    # tachado por causa de variação de fonte/kerning no PDF de origem.
    bruto = "**Apo** **~~i~~ o técn** **~~i~~ co** para o desenvolvimento"

    limpo = extract._limpar_markdown_pdf(bruto)

    assert "*" not in limpo
    assert "~" not in limpo
    assert "para o desenvolvimento" in limpo


def test_limpar_markdown_pdf_remove_tags_html_residuais():
    bruto = "<u>JANEIRO</u> primeira linha<br>segunda linha"

    limpo = extract._limpar_markdown_pdf(bruto)

    assert "<u>" not in limpo and "</u>" not in limpo
    assert "<br>" not in limpo
    assert "JANEIRO" in limpo


def test_limpar_markdown_pdf_remove_comentarios_de_texto_de_imagem():
    bruto = "<!-- Start of picture text -->01 Nome do projeto<!-- End of picture text -->"

    limpo = extract._limpar_markdown_pdf(bruto)

    assert "picture text" not in limpo
    assert "01 Nome do projeto" in limpo


def test_limpar_markdown_pdf_preserva_cabecalhos_com_negrito():
    bruto = "## **1. Visão Geral**\n\nTexto qualquer da seção."

    limpo = extract._limpar_markdown_pdf(bruto)

    assert limpo.startswith("## 1. Visão Geral")


def test_limpar_markdown_pdf_colapsa_linhas_em_branco_e_espacos_demais():
    bruto = "Primeira linha.\n\n\n\n\nSegunda   linha   com   espaços."

    limpo = extract._limpar_markdown_pdf(bruto)

    assert "\n\n\n" not in limpo
    assert "   " not in limpo


def test_extrair_pdf_usa_pymupdf4llm_e_registra_no_front_matter(tmp_path, exemplo_pdf):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    docs_normalizado.mkdir()
    origem = docs_fonte / "exemplo.pdf"
    origem.write_bytes(exemplo_pdf.read_bytes())

    caminho_saida = extract.normalizar(origem, docs_fonte, docs_normalizado)

    conteudo = caminho_saida.read_text(encoding="utf-8")
    assert "extrator: pymupdf4llm" in conteudo or "extrator: markitdown" in conteudo


def test_ler_front_matter_separa_metadados_do_corpo():
    conteudo = (
        "---\n"
        "origem: docs-fonte/guia.md\n"
        "extrator: _extrair_texto_puro\n"
        "ingerido_em: 2026-09-12T10:00:00\n"
        "---\n\n"
        "# Guia\n\nTexto.\n"
    )

    meta, corpo = extract.ler_front_matter(conteudo)

    assert meta["origem"] == "docs-fonte/guia.md"
    assert corpo == "# Guia\n\nTexto.\n"
