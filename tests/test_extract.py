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
