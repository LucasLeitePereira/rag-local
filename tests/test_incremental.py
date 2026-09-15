"""Ingestão incremental (TASK-005): só o que mudou é extraído e embeddado."""

import sqlite3

import pytest

from docserver import cli, extract, index


def _embeddar_falso(chunk):
    return [1.0, 0.0, 0.0]


def _corpus(tmp_path, quantidade=3):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    for i in range(1, quantidade + 1):
        (docs_fonte / f"doc{i}.md").write_text(
            f"# Documento {i}\n\n## Seção\n\nConteúdo do documento {i} com texto suficiente, assunto{i}.\n",
            encoding="utf-8",
        )
    return docs_fonte, docs_normalizado, str(tmp_path / "indice.db")


class _Espiao:
    """Conta as chamadas a uma função, delegando para a original."""

    def __init__(self, funcao):
        self.funcao = funcao
        self.chamadas = []

    def __call__(self, *args, **kwargs):
        self.chamadas.append(args)
        return self.funcao(*args, **kwargs)


def _ingerir(docs_fonte, docs_normalizado, caminho_indice, **kwargs):
    kwargs.setdefault("embeddar_passagem_fn", _embeddar_falso)
    kwargs.setdefault("nome_modelo", "fake")
    return cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, **kwargs)


def _contar(caminho_indice, sql):
    conexao = index.criar_indice(caminho_indice)
    try:
        if "chunks_vec" in sql:
            index._carregar_extensao_vec(conexao)
        return conexao.execute(sql).fetchone()[0]
    finally:
        conexao.close()


def test_reingerir_sem_mudancas_nao_extrai_nem_embedda(tmp_path, monkeypatch):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    _ingerir(docs_fonte, docs_normalizado, caminho_indice)

    normalizar = _Espiao(extract.normalizar)
    monkeypatch.setattr(extract, "normalizar", normalizar)
    embeddar = _Espiao(_embeddar_falso)
    relatorio = _ingerir(docs_fonte, docs_normalizado, caminho_indice, embeddar_passagem_fn=embeddar)

    assert normalizar.chamadas == [] and embeddar.chamadas == []
    assert relatorio["inalterados"] == 3 and relatorio["processados"] == 0
    assert relatorio["chunks"] == 3 and relatorio["chunks_novos"] == 0
    assert relatorio["reconstrucao"] is None
    assert _contar(caminho_indice, "SELECT COUNT(*) FROM chunks") == 3
    assert _contar(caminho_indice, "SELECT COUNT(*) FROM chunks_vec") == 3
    assert (docs_normalizado / "doc1.md").exists()


def test_alterar_um_arquivo_reprocessa_so_ele(tmp_path, monkeypatch):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    _ingerir(docs_fonte, docs_normalizado, caminho_indice)
    (docs_fonte / "doc2.md").write_text(
        "# Documento 2\n\n## Seção\n\nTexto novo do documento dois sobre faturamento trimestral.\n",
        encoding="utf-8",
    )

    normalizar = _Espiao(extract.normalizar)
    monkeypatch.setattr(extract, "normalizar", normalizar)
    relatorio = _ingerir(docs_fonte, docs_normalizado, caminho_indice)

    assert [c[0].name for c in normalizar.chamadas] == ["doc2.md"]
    assert relatorio["alterados"] == [str(docs_fonte / "doc2.md")] and relatorio["inalterados"] == 2
    assert _contar(caminho_indice, "SELECT COUNT(*) FROM chunks") == 3
    assert _contar(caminho_indice, "SELECT COUNT(*) FROM chunks_vec") == 3
    assert cli.executar_busca(caminho_indice, "assunto2", modo="lexico") == []
    assert len(cli.executar_busca(caminho_indice, "faturamento", modo="lexico")) == 1


def test_arquivo_novo_entra_sem_reprocessar_os_demais(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path, quantidade=2)
    _ingerir(docs_fonte, docs_normalizado, caminho_indice)
    (docs_fonte / "novo.md").write_text("# Novo\n\n## Seção\n\nDocumento recém-chegado na pasta.\n", encoding="utf-8")

    relatorio = _ingerir(docs_fonte, docs_normalizado, caminho_indice)

    assert relatorio["novos"] == [str(docs_fonte / "novo.md")] and relatorio["inalterados"] == 2
    assert relatorio["chunks"] == 3 and relatorio["chunks_novos"] == 1
    assert "Novos:                   1" in cli.formatar_relatorio(relatorio)


def test_apagar_um_arquivo_remove_chunks_vetores_registro_e_md(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    _ingerir(docs_fonte, docs_normalizado, caminho_indice)
    (docs_fonte / "doc3.md").unlink()

    relatorio = _ingerir(docs_fonte, docs_normalizado, caminho_indice)

    assert relatorio["documentos_removidos"] == ["docs-fonte/doc3.md"]
    assert not (docs_normalizado / "doc3.md").exists()
    assert _contar(caminho_indice, "SELECT COUNT(*) FROM chunks") == 2
    assert _contar(caminho_indice, "SELECT COUNT(*) FROM chunks_vec") == 2
    assert _contar(caminho_indice, "SELECT COUNT(*) FROM arquivos") == 2


def test_md_normalizado_apagado_a_mao_e_regerado(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    _ingerir(docs_fonte, docs_normalizado, caminho_indice)
    (docs_normalizado / "doc1.md").unlink()

    relatorio = _ingerir(docs_fonte, docs_normalizado, caminho_indice)

    assert relatorio["alterados"] == [str(docs_fonte / "doc1.md")]
    assert (docs_normalizado / "doc1.md").exists()
    assert _contar(caminho_indice, "SELECT COUNT(*) FROM chunks") == 3


def test_troca_de_modelo_forca_reconstrucao(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    _ingerir(docs_fonte, docs_normalizado, caminho_indice)

    embeddar = _Espiao(lambda chunk: [0.0, 1.0, 0.0, 0.0])
    relatorio = _ingerir(docs_fonte, docs_normalizado, caminho_indice, embeddar_passagem_fn=embeddar, nome_modelo="outro")

    assert "modelo de embeddings trocado" in relatorio["reconstrucao"]
    assert len(embeddar.chamadas) == 3
    assert cli.executar_stats(caminho_indice)["modelo"] == "outro"
    assert "Índice reconstruído do zero" in cli.formatar_relatorio(relatorio)


def test_ingestao_com_embeddings_depois_de_uma_sem_reprocessa_tudo(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    _ingerir(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    relatorio = _ingerir(docs_fonte, docs_normalizado, caminho_indice)

    assert relatorio["reconstrucao"] == "há chunks sem embeddings"
    assert _contar(caminho_indice, "SELECT COUNT(*) FROM chunks_vec") == 3


def test_sem_embeddings_sobre_indice_vetorial_mantem_inalterados_e_remove_a_camada(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    _ingerir(docs_fonte, docs_normalizado, caminho_indice)

    relatorio = _ingerir(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    assert relatorio["inalterados"] == 3 and relatorio["camada_vetorial_removida"]
    assert cli.executar_stats(caminho_indice)["modelo"] is None
    assert _contar(caminho_indice, "SELECT COUNT(*) FROM chunks") == 3


def test_indice_de_formato_antigo_e_reconstruido(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    _ingerir(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)
    conexao = sqlite3.connect(caminho_indice)
    conexao.execute("UPDATE metadados_indice SET valor = '3' WHERE chave = 'versao_esquema'")
    conexao.execute("DROP TABLE arquivos")
    conexao.commit()
    conexao.close()

    relatorio = _ingerir(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)

    assert "formato antigo" in relatorio["reconstrucao"]
    assert relatorio["processados"] == 3
    conexao = index.criar_indice(caminho_indice)
    assert index.verificar_esquema(conexao) is None
    assert len(index.arquivos_registrados(conexao)) == 3
    conexao.close()


def test_erro_na_gravacao_desfaz_a_transacao_inteira(tmp_path, monkeypatch):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    _ingerir(docs_fonte, docs_normalizado, caminho_indice)
    (docs_fonte / "doc1.md").write_text("# Documento 1\n\n## Seção\n\nVersão nova e diferente do texto.\n", encoding="utf-8")
    (docs_fonte / "doc3.md").unlink()

    def falha(*args, **kwargs):
        raise RuntimeError("disco cheio")

    monkeypatch.setattr(index, "indexar_chunks", falha)
    with pytest.raises(RuntimeError):
        _ingerir(docs_fonte, docs_normalizado, caminho_indice)

    assert _contar(caminho_indice, "SELECT COUNT(*) FROM chunks") == 3
    assert _contar(caminho_indice, "SELECT COUNT(*) FROM chunks_vec") == 3
    assert _contar(caminho_indice, "SELECT COUNT(*) FROM arquivos") == 3
    assert len(cli.executar_busca(caminho_indice, "assunto3", modo="lexico")) == 1
    assert (docs_normalizado / "doc3.md").exists()


def test_arquivo_que_passa_a_falhar_na_extracao_sai_do_indice(tmp_path, monkeypatch):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    _ingerir(docs_fonte, docs_normalizado, caminho_indice)
    (docs_fonte / "doc2.md").write_text("# Documento 2\n\nconteúdo que vai falhar ao extrair\n", encoding="utf-8")
    original = extract.normalizar

    def normalizar(caminho, *args):
        if caminho.name == "doc2.md":
            raise extract.ErroDeExtracao("arquivo corrompido")
        return original(caminho, *args)

    monkeypatch.setattr(extract, "normalizar", normalizar)
    relatorio = _ingerir(docs_fonte, docs_normalizado, caminho_indice)

    assert relatorio["documentos_removidos"] == ["docs-fonte/doc2.md"]
    assert len(relatorio["falhas"]) == 1
    assert _contar(caminho_indice, "SELECT COUNT(*) FROM chunks") == 2
