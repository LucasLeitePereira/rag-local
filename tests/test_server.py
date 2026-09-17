import threading
import time
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


def test_tools_em_indice_de_formato_antigo_orientam_a_reingerir(tmp_path):
    import sqlite3

    caminho_indice = str(tmp_path / "indice.db")
    conexao = sqlite3.connect(caminho_indice)
    conexao.execute("CREATE VIRTUAL TABLE chunks USING fts5(caminho_origem, caminho_normalizado, titulo_doc, secao, texto, ordem UNINDEXED)")
    conexao.commit()
    conexao.close()

    for texto in (
        server._buscar_texto(caminho_indice, "qualquer"),
        server._listar_documentos_texto(caminho_indice),
        server._ler_documento_texto("a.md", tmp_path, caminho_indice),
    ):
        assert "formato antigo" in texto and "docserver ingest" in texto


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


def test_buscar_mostra_aviso_quando_a_busca_semantica_falha(tmp_path, monkeypatch):
    caminho_indice = str(tmp_path / "indice.db")
    conexao = index.criar_indice(caminho_indice)
    chunk = {
        "caminho_origem": "docs-fonte/a.md",
        "caminho_normalizado": "a.md",
        "titulo_doc": "A",
        "secao": "Faturamento",
        "texto": "O faturamento mensal é consolidado no dia 5.",
        "ordem": 0,
    }
    index.indexar_chunks(conexao, [chunk], embeddings=[[1.0] + [0.0] * (embed.DIMENSAO - 1)])
    conexao.close()

    def _sem_extra(consulta):
        raise ImportError("sentence-transformers não instalado")

    monkeypatch.setattr(embed, "embeddar_consulta", _sem_extra)

    texto = server._buscar_texto(caminho_indice, "faturamento")

    assert texto.startswith("Aviso: busca semântica indisponível")
    assert "consolidado no dia 5" in texto


def test_ingestao_sem_embeddings_sobre_indice_vetorial_informa_remocao_da_camada(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    (docs_fonte / "guia.md").write_text(
        "# Guia\n\n## Seção\n\nConteúdo com bastante texto sobre faturamento mensal.\n", encoding="utf-8"
    )
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(
        docs_fonte, docs_normalizado, caminho_indice, embeddar_passagem_fn=lambda c: [1.0, 0.0, 0.0], nome_modelo="fake"
    )

    relatorio = cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    assert relatorio["camada_vetorial_removida"] is True
    assert "Camada vetorial removida" in cli.formatar_relatorio(relatorio)
    assert cli.executar_stats(caminho_indice)["modelo"] is None


def test_pdf_ingerido_mostra_pagina_na_busca_e_ler_documento_sem_marcadores(tmp_path, tres_paginas_pdf):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    (docs_fonte / "tres.pdf").write_bytes(tres_paginas_pdf.read_bytes())
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    with index.criar_indice(caminho_indice) as conexao:
        resultados = index.buscar(conexao, "backup", limite=5)
    # o PDF de exemplo é curto: um único chunk cobre as três páginas
    assert [(r["pagina_inicio"], r["pagina_fim"]) for r in resultados] == [(1, 3)]

    texto_busca = server._buscar_texto(caminho_indice, "backup")
    assert "pp. 1–3" in texto_busca
    assert "(pp. 1–3)" in cli.formatar_resultados(resultados)

    texto = server._ler_documento_texto("tres.pdf", docs_normalizado, caminho_indice)
    assert "backup" in texto
    assert "pagina:" not in texto


def test_formatar_paginas():
    assert cli.formatar_paginas({"pagina_inicio": None, "pagina_fim": None}) is None
    assert cli.formatar_paginas({}) is None
    assert cli.formatar_paginas({"pagina_inicio": 4, "pagina_fim": 4}) == "p. 4"
    assert cli.formatar_paginas({"pagina_inicio": 4, "pagina_fim": 6}) == "pp. 4–6"


def test_serve_stdio_nao_espera_o_aquecimento_para_falar_o_protocolo(monkeypatch):
    """O cliente MCP desiste do `initialize` em 30 s e o aquecimento leva minutos:
    em stdio ele tem que rodar em paralelo ao `mcp.run`, nunca antes dele."""
    liberar = threading.Event()
    aquecimento_comecou = threading.Event()
    aquecimento_terminou = threading.Event()
    chamadas = []

    def _aquecer_lento(caminho_indice):
        aquecimento_comecou.set()
        liberar.wait(5)
        aquecimento_terminou.set()

    monkeypatch.setattr(server, "_aquecer", _aquecer_lento)
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: chamadas.append(kwargs))

    try:
        server.main()

        # o `run` já rodou com o aquecimento ainda preso: é isso que salva o handshake
        assert chamadas == [{"transport": "stdio"}]
        assert not aquecimento_terminou.is_set(), "o `run` esperou o aquecimento terminar"
        assert aquecimento_comecou.wait(5), "o aquecimento nem chegou a começar"
    finally:
        liberar.set()


def test_serve_http_aquece_antes_de_anunciar_o_link(monkeypatch):
    """Em HTTP o link só aparece depois do `run`: dá para aquecer antes, e quem
    conectar já encontra o modelo pronto."""
    eventos = []

    monkeypatch.setattr(server, "_aquecer", lambda caminho_indice: eventos.append("aquecer"))
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: eventos.append("run"))

    server.main(transporte="http")

    assert eventos == ["aquecer", "run"]


def test_serve_sem_aquecimento_nao_dispara_a_thread(monkeypatch):
    eventos = []

    monkeypatch.setattr(server, "_aquecer", lambda caminho_indice: eventos.append("aquecer"))
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: eventos.append("run"))

    server.main(aquecer=False)

    assert eventos == ["run"]


def test_modelo_de_embeddings_carrega_uma_vez_so_com_threads_concorrentes(monkeypatch):
    """Aquecimento e buscas rodam em threads diferentes: sem o lock, cada uma
    construiria sua própria cópia dos pesos."""
    carregamentos = []

    def _carregar_devagar():
        carregamentos.append(1)
        time.sleep(0.05)
        return object()

    monkeypatch.setattr(embed, "_carregar_modelo", _carregar_devagar)
    monkeypatch.setattr(embed, "_modelo_cache", None)

    obtidos = []
    threads = [
        threading.Thread(target=lambda: obtidos.append(embed.obter_modelo())) for _ in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)

    assert len(carregamentos) == 1
    assert len({id(m) for m in obtidos}) == 1
