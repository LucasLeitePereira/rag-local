import pytest

from docserver import cli


def _ingerir_um_documento(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    (docs_fonte / "guia.md").write_text(
        "# Guia\n\n## Instalação\n\nRode o comando de setup para instalar o sistema.\n",
        encoding="utf-8",
    )
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)
    return docs_fonte, docs_normalizado, caminho_indice


def test_ingestao_com_docs_fonte_inexistente_aborta_sem_apagar_nada(tmp_path):
    _, docs_normalizado, caminho_indice = _ingerir_um_documento(tmp_path)

    with pytest.raises(cli.ErroIngestao):
        cli.executar_ingestao(tmp_path / "docs-fnote", docs_normalizado, caminho_indice, sem_embeddings=True)

    assert (docs_normalizado / "guia.md").exists()
    assert cli.executar_stats(caminho_indice)["chunks"] == 1


def test_ingestao_com_fonte_sem_arquivos_suportados_aborta_a_menos_que_forcar(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _ingerir_um_documento(tmp_path)
    (docs_fonte / "guia.md").unlink()

    with pytest.raises(cli.ErroIngestao):
        cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)
    assert (docs_normalizado / "guia.md").exists()
    assert cli.executar_stats(caminho_indice)["chunks"] == 1

    cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True, forcar=True)
    assert not (docs_normalizado / "guia.md").exists()
    assert cli.executar_stats(caminho_indice)["chunks"] == 0


def test_ingestao_que_nao_gera_chunks_nao_esvazia_indice_com_conteudo(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _ingerir_um_documento(tmp_path)
    (docs_fonte / "guia.md").write_text("curto", encoding="utf-8")  # abaixo do mínimo de um chunk

    with pytest.raises(cli.ErroIngestao):
        cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    assert cli.executar_stats(caminho_indice)["chunks"] == 1


def test_limpeza_de_orfaos_preserva_md_que_nao_foi_gerado_pelo_docserver(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _ingerir_um_documento(tmp_path)
    alheio = docs_normalizado / "anotacoes-pessoais.md"
    alheio.write_text("# Minhas anotações\n\nNão apague.\n", encoding="utf-8")

    relatorio = cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    assert alheio.exists()
    assert relatorio["preservados"] == [str(alheio)]
    assert relatorio["removidos"] == []


def test_comando_ingest_com_fonte_inexistente_e_limpar_sai_com_erro_sem_apagar(tmp_path, monkeypatch, capsys):
    _, docs_normalizado, caminho_indice = _ingerir_um_documento(tmp_path)

    with pytest.raises(SystemExit) as saida:
        cli.main(
            [
                "--docs-fonte",
                str(tmp_path / "nao-existe"),
                "--docs-normalizado",
                str(docs_normalizado),
                "--indice",
                caminho_indice,
                "ingest",
                "--limpar",
            ]
        )

    assert saida.value.code == 1
    assert "abortada" in capsys.readouterr().err.lower()
    assert (docs_normalizado / "guia.md").exists()
    assert cli.executar_stats(caminho_indice)["chunks"] == 1


def test_comando_ingest_limpar_so_remove_arquivos_gerados_pelo_docserver(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _ingerir_um_documento(tmp_path)
    alheio = docs_normalizado / "anotacoes-pessoais.md"
    alheio.write_text("# Minhas anotações\n\nNão apague.\n", encoding="utf-8")

    cli.main(
        [
            "--docs-fonte",
            str(docs_fonte),
            "--docs-normalizado",
            str(docs_normalizado),
            "--indice",
            caminho_indice,
            "ingest",
            "--limpar",
            "--sem-embeddings",
        ]
    )

    assert alheio.exists()
    assert (docs_normalizado / "guia.md").exists()
    assert cli.executar_stats(caminho_indice)["chunks"] == 1


def test_fontes_com_mesmo_nome_e_extensoes_diferentes_nao_colidem(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    (docs_fonte / "manual.md").write_text(
        "# Manual MD\n\nConteúdo exclusivo da versão markdown do manual.\n", encoding="utf-8"
    )
    (docs_fonte / "manual.txt").write_text(
        "# Manual TXT\n\nConteúdo exclusivo da versão em texto puro do manual.\n", encoding="utf-8"
    )
    (docs_fonte / "manual.csv").write_text("coluna,valor\nversao,planilha\n", encoding="utf-8")
    caminho_indice = str(tmp_path / "indice.db")

    relatorio = cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    assert relatorio["processados"] == 3
    assert relatorio["falhas"] == []
    assert sorted(p.name for p in docs_normalizado.iterdir()) == ["manual.csv.md", "manual.md", "manual.txt.md"]
    assert cli.executar_stats(caminho_indice)["documentos"] == 3


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
    (docs_fonte / "visivel.md").write_text("# Visível\n\nConteúdo com texto suficiente.\n", encoding="utf-8")
    caminho_indice = str(tmp_path / "indice.db")

    relatorio = cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    assert relatorio["processados"] == 1
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

    tecnico = resultado["lexico"]["tecnico"]
    natural = resultado["lexico"]["natural"]
    assert (tecnico["hit1"], tecnico["hit5"], tecnico["positivas"]) == (1, 1, 1)
    assert tecnico["rr"] == 1.0
    assert (natural["hit5"], natural["positivas"]) == (0, 1)
    assert tecnico["consultas"] == 1 and tecnico["tempo_s"] >= 0


def _indice_com_dois_documentos(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_fonte.mkdir()
    (docs_fonte / "auth.md").write_text(
        "# Auth\n\n## Renovação\n\nO refresh token dura 30 dias e é rotacionado a cada uso.\n",
        encoding="utf-8",
    )
    (docs_fonte / "cobranca.md").write_text(
        "# Cobrança\n\n## Suspensão\n\nA conta é suspensa após 15 dias de atraso no pagamento do token.\n",
        encoding="utf-8",
    )
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(docs_fonte, tmp_path / "docs-normalizado", caminho_indice, sem_embeddings=True)
    return caminho_indice


def test_avaliar_mede_trecho_e_perguntas_negativas(tmp_path):
    caminho_indice = _indice_com_dois_documentos(tmp_path)
    caminho_perguntas = tmp_path / "perguntas.yaml"
    caminho_perguntas.write_text(
        "- pergunta: \"refresh token\"\n"
        "  esperado: docs-fonte/auth.md\n"
        "  perfil: tecnico\n"
        "  trecho: \"dura 30 DIAS e e rotacionado\"\n"
        "- pergunta: \"refresh token\"\n"
        "  esperado: docs-fonte/auth.md\n"
        "  perfil: tecnico\n"
        "  trecho: \"frase que não está no chunk\"\n"
        "- pergunta: \"orçamento trimestral de marketing\"\n"
        "  esperado: null\n"
        "  perfil: natural\n",
        encoding="utf-8",
    )

    resultado = cli.executar_avaliacao(caminho_perguntas, caminho_indice, modos=("hibrido",))

    tecnico = resultado["hibrido"]["tecnico"]
    assert (tecnico["com_trecho"], tecnico["trecho5"]) == (2, 1)
    natural = resultado["hibrido"]["natural"]
    assert (natural["positivas"], natural["negativas"], natural["negativas_vazias"]) == (0, 1, 1)
    assert cli.taxas_avaliacao(natural)["hit5"] is None


def test_mrr_usa_a_posicao_do_primeiro_acerto():
    metricas = cli._metricas_vazias()
    topo = [{"caminho_origem": "outro.md", "texto": ""}, {"caminho_origem": "certo.md", "texto": ""}]

    cli._pontuar_resposta(metricas, {"esperado": "certo.md"}, topo)

    assert (metricas["hit1"], metricas["hit5"], metricas["rr"]) == (0, 1, 0.5)


def test_validar_perguntas_aponta_documento_e_trecho_inexistentes(tmp_path):
    caminho_indice = _indice_com_dois_documentos(tmp_path)
    caminho_perguntas = tmp_path / "perguntas.yaml"
    caminho_perguntas.write_text(
        "- pergunta: \"ok\"\n"
        "  esperado: docs-fonte/auth.md\n"
        "  perfil: tecnico\n"
        "  trecho: \"rotacionado a cada uso\"\n"
        "- pergunta: \"doc sumiu\"\n"
        "  esperado: docs-fonte/nao-existe.md\n"
        "  perfil: tecnico\n"
        "- pergunta: \"trecho errado\"\n"
        "  esperado: docs-fonte/auth.md\n"
        "  perfil: natural\n"
        "  trecho: \"dura 60 dias\"\n"
        "- pergunta: \"negativa com trecho\"\n"
        "  esperado: null\n"
        "  perfil: natural\n"
        "  trecho: \"qualquer\"\n",
        encoding="utf-8",
    )

    problemas = cli.validar_perguntas(caminho_perguntas, caminho_indice)

    assert len(problemas) == 3
    assert "nao-existe.md" in problemas[0]
    assert "dura 60 dias" in problemas[1]
    assert "negativa" in problemas[2]


def test_comando_avaliar_sai_com_erro_abaixo_da_meta_de_hit5(tmp_path, capsys):
    caminho_indice = _indice_com_dois_documentos(tmp_path)
    caminho_perguntas = tmp_path / "perguntas.yaml"
    caminho_perguntas.write_text(
        "- pergunta: \"refresh rotacionado\"\n"
        "  esperado: docs-fonte/cobranca.md\n"
        "  perfil: tecnico\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as saida:
        cli.main(["--indice", caminho_indice, "avaliar", str(caminho_perguntas), "--min-hit5", "0.9"])

    assert saida.value.code == 1
    assert "abaixo da meta" in capsys.readouterr().out


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
    assert resultado["lexico"]["tecnico"]["hit5"] == 1


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
    (docs_fonte / "permanente.md").write_text(
        "# Permanente\n\n## Seção\n\nDocumento que continua na fonte depois da remoção.\n",
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
    tecnico = cli._metricas_vazias() | {"positivas": 10, "hit1": 7, "hit5": 9, "rr": 8.0, "consultas": 10}
    natural = cli._metricas_vazias() | {"positivas": 10, "hit1": 1, "hit5": 3, "rr": 2.0, "consultas": 12}
    natural |= {"negativas": 2, "negativas_vazias": 1}
    resultado = {"lexico": {"tecnico": tecnico, "natural": natural}}

    tabela = cli.formatar_tabela_avaliacao(resultado)

    assert "lexico" in tabela
    assert "9/10" in tabela
    assert "3/10" in tabela
    assert "12/20" in tabela  # linha geral
    assert "90%" in tabela and "50%" in tabela
    assert "geral" in tabela
