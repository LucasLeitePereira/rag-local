from pathlib import Path

import pytest

from docserver import cli, embed, index, server

_aquecer_real = server._aquecer


@pytest.fixture(autouse=True)
def _sem_aquecimento_real(monkeypatch):
    # `server.main()` sem argumentos aponta para o data/indice.db real do repositório:
    # sem isto, os testes carregariam o modelo de embeddings de verdade.
    monkeypatch.setattr(server, "_aquecer", lambda caminho_indice: None)


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
            "aquecer": True,
        }
    ]


def _preparar_server_mcp(tmp_path, monkeypatch):
    docs_normalizado, caminho_indice = _preparar_corpus(tmp_path)
    monkeypatch.setattr(cli, "INDICE_FIXO", Path(caminho_indice))
    monkeypatch.setattr(cli, "DOCS_NORMALIZADO_FIXO", Path(docs_normalizado))
    monkeypatch.setattr(cli, "_ip_rede_local", lambda: "192.168.0.10")
    chamadas = []
    monkeypatch.setattr("docserver.server.main", lambda **kwargs: chamadas.append(kwargs))
    return docs_normalizado, caminho_indice, chamadas


def test_server_mcp_local_sobe_http_na_rede_com_caminhos_fixos(tmp_path, monkeypatch, capsys):
    docs_normalizado, caminho_indice, chamadas = _preparar_server_mcp(tmp_path, monkeypatch)
    outro_dir = tmp_path / "outro-cwd"
    outro_dir.mkdir()
    monkeypatch.chdir(outro_dir)

    cli.main(["server-mcp", "--local"])

    assert chamadas == [
        {
            "docs_normalizado": Path(docs_normalizado),
            "indice": caminho_indice,
            "transporte": "http",
            "host": "0.0.0.0",
            "porta": 8765,
            "aquecer": True,
        }
    ]
    assert "http://192.168.0.10:8765/mcp" in capsys.readouterr().err


def test_server_mcp_sem_local_fica_restrito_a_esta_maquina(tmp_path, monkeypatch):
    _, _, chamadas = _preparar_server_mcp(tmp_path, monkeypatch)

    cli.main(["server-mcp"])

    assert chamadas[0]["host"] == "127.0.0.1"
    assert chamadas[0]["transporte"] == "http"


def test_server_mcp_aborta_sem_indice(tmp_path, monkeypatch):
    _, _, chamadas = _preparar_server_mcp(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "INDICE_FIXO", tmp_path / "nao-existe.db")

    with pytest.raises(SystemExit):
        cli.main(["server-mcp", "--local"])

    assert chamadas == []


def test_raiz_do_projeto_contem_o_pyproject():
    assert (cli.RAIZ_PROJETO / "pyproject.toml").is_file()


def test_ler_documento_funciona_quando_ingestao_e_servidor_usam_cwds_e_caminhos_diferentes(tmp_path, monkeypatch):
    # regressão C1: a ingestão rodava com caminhos relativos ao cwd e o servidor,
    # com caminhos absolutos — `ler_documento` nunca achava nada no servidor real.
    projeto = tmp_path / "projeto"
    (projeto / "docs-fonte" / "api").mkdir(parents=True)
    (projeto / "docs-fonte" / "api" / "contratos.md").write_text(
        "# Contratos\n\n## Rate limit\n\nCada cliente pode fazer 100 requisições por minuto.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(projeto)
    cli.main(["ingest", "--sem-embeddings"])

    outro_dir = tmp_path / "outro-cwd"
    outro_dir.mkdir()
    monkeypatch.chdir(outro_dir)
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: None)
    cli.main(
        [
            "--docs-normalizado",
            str(projeto / "docs-normalizado"),
            "--indice",
            str(projeto / "data" / "indice.db"),
            "serve",
        ]
    )

    for caminho in ("docs-fonte/api/contratos.md", "api/contratos.md", "contratos.md", "contratos"):
        assert "100 requisições por minuto" in server.ler_documento(caminho), caminho


def test_indice_grava_caminho_normalizado_relativo_e_posix(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    (docs_fonte / "api").mkdir(parents=True)
    (docs_fonte / "api" / "contratos.md").write_text(
        "# Contratos\n\n## Seção\n\nTexto suficiente para virar um chunk indexado.\n", encoding="utf-8"
    )
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    conexao = index.criar_indice(caminho_indice)
    try:
        valores = {linha[0] for linha in conexao.execute("SELECT caminho_normalizado FROM chunks")}
    finally:
        conexao.close()

    assert valores == {"api/contratos.md"}


def test_ler_documento_distingue_fontes_com_mesmo_nome_e_extensoes_diferentes(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    (docs_fonte / "manual.md").write_text(
        "# Manual MD\n\n## Seção\n\nConteúdo exclusivo da versão em markdown do manual.\n", encoding="utf-8"
    )
    (docs_fonte / "manual.txt").write_text(
        "# Manual TXT\n\n## Seção\n\nConteúdo exclusivo da versão em texto puro do manual.\n", encoding="utf-8"
    )
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    texto_txt = server._ler_documento_texto("manual.txt", docs_normalizado, caminho_indice)
    texto_md = server._ler_documento_texto("docs-fonte/manual.md", docs_normalizado, caminho_indice)
    ambiguo = server._ler_documento_texto("manual", docs_normalizado, caminho_indice)

    assert "texto puro" in texto_txt and "markdown" not in texto_txt
    assert "markdown" in texto_md and "texto puro" not in texto_md
    assert "ambígu" in ambiguo.lower()


def test_buscar_devolve_o_chunk_inteiro_com_metadados(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    frase_final = "E esta é a frase final que fica depois do corte de trezentos caracteres."
    corpo = " ".join(["O refresh token é renovado automaticamente pelo cliente."] * 10) + " " + frase_final
    (docs_fonte / "auth.md").write_text(f"# Auth\n\n## Renovação\n\n{corpo}\n", encoding="utf-8")
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    texto = server._buscar_texto(caminho_indice, "refresh token")

    assert len(corpo) > 300
    assert frase_final in texto
    assert "chunk " in texto
    assert "posição 0 no documento" in texto


def test_main_aquece_o_modelo_antes_de_aceitar_requisicoes(monkeypatch):
    eventos = []
    monkeypatch.setattr(server, "_aquecer", lambda caminho_indice: eventos.append("aquecer"))
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: eventos.append("run"))

    server.main()

    assert eventos == ["aquecer", "run"]


def test_main_sem_aquecimento_nao_carrega_modelo(monkeypatch):
    eventos = []
    monkeypatch.setattr(server, "_aquecer", lambda caminho_indice: eventos.append("aquecer"))
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: eventos.append("run"))

    server.main(aquecer=False)

    assert eventos == ["run"]


def _indice_vetorial(tmp_path):
    caminho_indice = str(tmp_path / "indice.db")
    conexao = index.criar_indice(caminho_indice)
    chunk = {
        "caminho_origem": "docs-fonte/a.md",
        "caminho_normalizado": "a.md",
        "titulo_doc": "A",
        "secao": "S",
        "texto": "texto qualquer",
        "ordem": 0,
    }
    index.indexar_chunks(conexao, [chunk], embeddings=[[1.0, 0.0, 0.0]], nome_modelo="fake")
    conexao.close()
    return caminho_indice


def test_aquecer_com_indice_vetorial_carrega_o_modelo(tmp_path, monkeypatch):
    caminho_indice = _indice_vetorial(tmp_path)
    chamadas = []
    monkeypatch.setattr(embed, "embeddar_consulta", lambda consulta: chamadas.append(consulta))

    _aquecer_real(caminho_indice)

    assert len(chamadas) == 1


def test_aquecer_nao_derruba_o_servidor_se_o_modelo_nao_carrega(tmp_path, monkeypatch):
    caminho_indice = _indice_vetorial(tmp_path)

    def _falhar(consulta):
        raise ImportError("sentence-transformers não instalado")

    monkeypatch.setattr(embed, "embeddar_consulta", _falhar)

    _aquecer_real(caminho_indice)  # não deve levantar


def test_aquecer_sem_indice_vetorial_nao_carrega_modelo(tmp_path, monkeypatch):
    _, caminho_indice = _preparar_corpus(tmp_path)
    chamadas = []
    monkeypatch.setattr(embed, "embeddar_consulta", lambda consulta: chamadas.append(consulta))

    _aquecer_real(caminho_indice)

    assert chamadas == []


def test_conexao_persistente_e_reutilizada_enquanto_o_servidor_esta_ativo(tmp_path, monkeypatch):
    docs_normalizado, caminho_indice = _preparar_corpus(tmp_path)
    aberturas = []
    criar_original = index.criar_indice

    def _contar(caminho, compartilhada=False):
        aberturas.append(caminho)
        return criar_original(caminho, compartilhada=compartilhada)

    def _servir(**kwargs):
        monkeypatch.setattr(index, "criar_indice", _contar)
        server.listar_documentos()
        server.buscar("refresh token")
        server.ler_documento("autenticacao.md")

    monkeypatch.setattr(server.mcp, "run", _servir)

    server.main(docs_normalizado=docs_normalizado, indice=caminho_indice, aquecer=False)

    assert len(aberturas) == 1
    assert server._persistente["conexao"] is None


def test_configurar_resolve_caminhos_relativos_para_absolutos(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    server.configurar(Path("docs-normalizado"), "data/indice.db")

    assert server._config["docs_normalizado"] == (tmp_path / "docs-normalizado").resolve()
    assert Path(server._config["indice"]) == (tmp_path / "data" / "indice.db").resolve()
