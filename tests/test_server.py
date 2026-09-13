from pathlib import Path

from docserver import cli, server


def _preparar_corpus(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    docs_normalizado.mkdir()
    (docs_fonte / "autenticacao.md").write_text(
        "# Autenticação\n\n"
        "## Renovação de token\n\n"
        "O refresh token tem validade de 30 dias e é rotacionado a cada uso.\n\n"
        "## Login\n\nO login aceita e-mail e senha.\n",
        encoding="utf-8",
    )
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)
    return docs_normalizado, caminho_indice


def test_buscar_retorna_texto_formatado_com_origem_e_secao(tmp_path):
    _, caminho_indice = _preparar_corpus(tmp_path)

    texto = server._buscar_texto(caminho_indice, "refresh token")

    assert "docs-fonte/autenticacao.md" in texto
    assert "Renovação de token" in texto


def test_buscar_sem_resultado_retorna_mensagem_orientando_proximo_passo(tmp_path):
    _, caminho_indice = _preparar_corpus(tmp_path)

    texto = server._buscar_texto(caminho_indice, "termo-inexistente-em-lugar-nenhum-xyz")

    assert "listar_documentos" in texto or "reformular" in texto.lower()


def test_listar_documentos_retorna_arvore_com_titulos_e_secoes(tmp_path):
    _, caminho_indice = _preparar_corpus(tmp_path)

    texto = server._listar_documentos_texto(caminho_indice)

    assert "docs-fonte/autenticacao.md" in texto
    assert "Autenticação" in texto
    assert "Renovação de token" in texto
    assert "Login" in texto


def test_listar_documentos_nao_mostra_md_orfao_que_ficou_de_fora_do_indice(tmp_path):
    docs_normalizado, caminho_indice = _preparar_corpus(tmp_path)
    (docs_normalizado / "orfao.md").write_text(
        "---\norigem: docs-fonte/orfao.md\nextrator: x\ningerido_em: y\n---\n\n"
        "# Órfão\n\nConteúdo que não faz mais parte do índice.\n",
        encoding="utf-8",
    )

    texto = server._listar_documentos_texto(caminho_indice)

    assert "orfao" not in texto.lower()


def test_ler_documento_aceita_caminho_parcial_e_resolve_para_o_arquivo_certo(tmp_path):
    docs_normalizado, caminho_indice = _preparar_corpus(tmp_path)

    texto = server._ler_documento_texto("autenticacao.md", docs_normalizado, caminho_indice)

    assert "Renovação de token" in texto


def test_ler_documento_com_caminho_ambiguo_lista_as_opcoes(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    docs_normalizado.mkdir()
    (docs_fonte / "autenticacao.md").write_text(
        "# Autenticação\n\n## Renovação\n\nO refresh token dura 30 dias e é rotacionado a cada uso.\n",
        encoding="utf-8",
    )
    (docs_fonte / "outra").mkdir()
    (docs_fonte / "outra" / "autenticacao.md").write_text(
        "# Outra Autenticação\n\n## Conteúdo\n\nTexto de exemplo com conteúdo suficiente para o chunk.\n",
        encoding="utf-8",
    )
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    texto = server._ler_documento_texto("autenticacao.md", docs_normalizado, caminho_indice)

    assert "ambígu" in texto.lower()
    assert "outra/autenticacao.md" in texto


def test_ler_documento_rejeita_path_traversal(tmp_path):
    docs_normalizado, caminho_indice = _preparar_corpus(tmp_path)

    texto = server._ler_documento_texto("../../../etc/passwd", docs_normalizado, caminho_indice)

    assert "inválido" in texto.lower() or "não encontrado" in texto.lower()


def test_ler_documento_com_caminho_inexistente_retorna_mensagem_util(tmp_path):
    docs_normalizado, caminho_indice = _preparar_corpus(tmp_path)

    texto = server._ler_documento_texto("nao-existe.md", docs_normalizado, caminho_indice)

    assert "não encontrado" in texto.lower()


def test_ler_documento_nao_serve_md_orfao_que_ficou_de_fora_do_indice(tmp_path):
    docs_normalizado, caminho_indice = _preparar_corpus(tmp_path)
    (docs_normalizado / "orfao.md").write_text(
        "---\norigem: docs-fonte/orfao.md\nextrator: x\ningerido_em: y\n---\n\n"
        "# Órfão\n\nConteúdo que não faz mais parte do índice.\n",
        encoding="utf-8",
    )

    texto = server._ler_documento_texto("orfao.md", docs_normalizado, caminho_indice)

    assert "não encontrado" in texto.lower()


def test_buscar_com_documento_restringe_resultado_aquele_arquivo(tmp_path):
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

    texto = server._buscar_texto(caminho_indice, "prazo de entrega", documento="b.md")

    assert "docs-fonte/b.md" in texto
    assert "docs-fonte/a.md" not in texto


def test_buscar_com_documento_inexistente_orienta_a_listar_documentos(tmp_path):
    _, caminho_indice = _preparar_corpus(tmp_path)

    texto = server._buscar_texto(caminho_indice, "token", documento="nao-existe.md")

    assert "não encontrado" in texto.lower()
    assert "listar_documentos" in texto


def test_buscar_com_indice_inexistente_orienta_a_rodar_ingest_sem_criar_arquivo(tmp_path):
    caminho_indice = tmp_path / "nao-existe" / "indice.db"

    texto = server._buscar_texto(str(caminho_indice), "token")

    assert "docserver ingest" in texto
    assert str(caminho_indice) in texto
    assert not caminho_indice.exists()


def test_serve_usa_caminhos_passados_na_cli_independente_do_diretorio_atual(tmp_path, monkeypatch):
    docs_normalizado, caminho_indice = _preparar_corpus(tmp_path)
    outro_dir = tmp_path / "outro-cwd"
    outro_dir.mkdir()
    monkeypatch.chdir(outro_dir)
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: None)

    cli.main(["--docs-normalizado", str(docs_normalizado), "--indice", caminho_indice, "serve"])

    assert "Renovação de token" in server.listar_documentos()
    assert "docs-fonte/autenticacao.md" in server.buscar("refresh token")
    assert "Renovação de token" in server.ler_documento("autenticacao.md")


def test_serve_padrao_usa_transporte_stdio_sem_host_nem_porta(monkeypatch):
    chamadas = []
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: chamadas.append(kwargs))

    server.main()

    assert chamadas == [{"transport": "stdio"}]


def test_serve_com_http_repassa_transporte_host_e_porta(monkeypatch):
    chamadas = []
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: chamadas.append(kwargs))

    server.main(transporte="http", host="0.0.0.0", porta=9000)

    assert chamadas == [{"transport": "http", "host": "0.0.0.0", "port": 9000}]


def test_cli_serve_com_flag_http_repassa_host_e_porta_para_o_servidor(tmp_path, monkeypatch):
    docs_normalizado, caminho_indice = _preparar_corpus(tmp_path)
    chamadas = []
    monkeypatch.setattr(
        "docserver.server.main",
        lambda **kwargs: chamadas.append(kwargs),
    )

    cli.main(
        [
            "--docs-normalizado",
            str(docs_normalizado),
            "--indice",
            caminho_indice,
            "serve",
            "--http",
            "--host",
            "0.0.0.0",
            "--porta",
            "9001",
        ]
    )

    assert chamadas == [
        {
            "docs_normalizado": Path(docs_normalizado),
            "indice": caminho_indice,
            "transporte": "http",
            "host": "0.0.0.0",
            "porta": 9001,
        }
    ]


def test_configurar_resolve_caminhos_relativos_para_absolutos(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    server.configurar(Path("docs-normalizado"), "data/indice.db")

    assert server._config["docs_normalizado"] == (tmp_path / "docs-normalizado").resolve()
    assert Path(server._config["indice"]) == (tmp_path / "data" / "indice.db").resolve()
