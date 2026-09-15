"""Leitura para agentes (TASK-001): `ler_documento` em partes/por seção e `ler_trecho`."""

import pytest

from docserver import cli, index, server


@pytest.fixture(autouse=True)
def _sem_aquecimento_real(monkeypatch):
    monkeypatch.setattr(server, "_aquecer", lambda caminho_indice: None)


def _corpus(tmp_path, conteudo):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    (docs_fonte / "manual.md").write_text(conteudo, encoding="utf-8")
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, sem_embeddings=True)
    return docs_normalizado, caminho_indice


def _documento_grande(paragrafos=40):
    linhas = ["# Manual", "", "## Instalação", ""]
    for i in range(paragrafos):
        linhas += [f"Parágrafo {i:02d} da instalação com texto de preenchimento suficiente.", ""]
    linhas += ["## Configuração", "", "Ajuste a variável TIMEOUT para 30 segundos.", ""]
    linhas += ["### Configuração avançada", "", "O modo turbo usa cache em disco.", ""]
    linhas += ["## Backup", "", "Faça backup diário do banco.", ""]
    return "\n".join(linhas)


def test_documento_pequeno_sai_inteiro_sem_cabecalho_de_parte(tmp_path):
    docs_normalizado, caminho_indice = _corpus(tmp_path, "# Guia\n\n## Uso\n\nRode o comando de setup para instalar.\n")

    texto = server._ler_documento_texto("manual.md", docs_normalizado, caminho_indice)

    assert texto.startswith("# Guia")
    assert "parte" not in texto.lower()


def test_documento_grande_sai_em_partes_cortadas_entre_paragrafos(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMITE_CARACTERES_LEITURA", "1000")
    docs_normalizado, caminho_indice = _corpus(tmp_path, _documento_grande())

    primeira = server._ler_documento_texto("manual.md", docs_normalizado, caminho_indice)
    assert primeira.startswith("[docs-fonte/manual.md — parte 1 de ")
    total = int(primeira.split(" de ", 1)[1].split("]", 1)[0])
    assert total > 2
    assert primeira.rstrip().endswith('[Continua: ler_documento(caminho="docs-fonte/manual.md", parte=2)]')

    partes = [server._ler_documento_texto("manual.md", docs_normalizado, caminho_indice, parte=n) for n in range(1, total + 1)]
    ultima = partes[-1]
    assert "[Continua" not in ultima
    assert "Faça backup diário do banco." in ultima
    for n, parte in enumerate(partes, 1):
        corpo = parte.split("]\n\n", 1)[1].split("\n\n[Continua", 1)[0]
        assert len(corpo) <= 1000
    # nenhum parágrafo cortado ao meio, nenhum perdido
    todos = "\n\n".join(p.split("]\n\n", 1)[1].split("\n\n[Continua", 1)[0] for p in partes)
    for i in range(40):
        assert todos.count(f"Parágrafo {i:02d} da instalação com texto de preenchimento suficiente.") == 1


def test_parte_inexistente_responde_quantas_existem(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMITE_CARACTERES_LEITURA", "1000")
    docs_normalizado, caminho_indice = _corpus(tmp_path, _documento_grande())

    texto = server._ler_documento_texto("manual.md", docs_normalizado, caminho_indice, parte=99)

    assert texto.startswith("Parte 99 não existe: docs-fonte/manual.md tem ")


def test_paragrafo_maior_que_o_limite_e_cortado_em_espaco():
    paragrafo = " ".join(f"palavra{i}" for i in range(100))

    partes = server._dividir_em_partes(paragrafo, 100)

    assert all(len(p) <= 100 for p in partes)
    assert " ".join(partes).split() == paragrafo.split()


def test_secao_existente_inclui_subsecoes_e_para_na_seguinte(tmp_path):
    docs_normalizado, caminho_indice = _corpus(tmp_path, _documento_grande())

    texto = server._ler_documento_texto("manual.md", docs_normalizado, caminho_indice, secao="configuracao")

    assert texto.startswith("## Configuração")
    assert "TIMEOUT" in texto and "modo turbo" in texto
    assert "backup" not in texto.lower() and "Parágrafo" not in texto


def test_secao_inexistente_lista_as_disponiveis(tmp_path):
    docs_normalizado, caminho_indice = _corpus(tmp_path, _documento_grande())

    texto = server._ler_documento_texto("manual.md", docs_normalizado, caminho_indice, secao="Deploy")

    assert texto.startswith("Seção não encontrada: Deploy.")
    assert "- Instalação" in texto and "- Backup" in texto


def test_secao_ambigua_lista_as_opcoes(tmp_path):
    docs_normalizado, caminho_indice = _corpus(tmp_path, _documento_grande())

    texto = server._ler_documento_texto("manual.md", docs_normalizado, caminho_indice, secao="Config")

    assert texto.startswith("Seção ambígua")
    assert "- Configuração\n" in texto and "- Configuração avançada" in texto


def test_secao_grande_tambem_sai_em_partes_com_a_secao_na_continuacao(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMITE_CARACTERES_LEITURA", "1000")
    docs_normalizado, caminho_indice = _corpus(tmp_path, _documento_grande())

    texto = server._ler_documento_texto("manual.md", docs_normalizado, caminho_indice, secao="Instalação")

    assert texto.startswith("[docs-fonte/manual.md › Instalação — parte 1 de ")
    assert 'secao="Instalação", parte=2)]' in texto


def _ids_por_ordem(caminho_indice):
    conexao = index.criar_indice(caminho_indice)
    try:
        linhas = conexao.execute("SELECT rowid, ordem FROM chunks ORDER BY CAST(ordem AS INTEGER)").fetchall()
    finally:
        conexao.close()
    return [rowid for rowid, _ in linhas]


def _corpus_com_varios_chunks(tmp_path):
    secoes = "\n\n".join(f"## Seção {i}\n\nConteúdo exclusivo da seção número {i} do manual." for i in range(6))
    return _corpus(tmp_path, "# Manual\n\n" + secoes + "\n")


def test_ler_trecho_traz_vizinhos_em_ordem_e_marca_o_pedido(tmp_path):
    _, caminho_indice = _corpus_com_varios_chunks(tmp_path)
    ids = _ids_por_ordem(caminho_indice)
    assert len(ids) == 6

    texto = server._ler_trecho_texto(caminho_indice, ids[2], vizinhos=1)

    assert texto.startswith("docs-fonte/manual.md — posições 1 a 3 (o documento vai da posição 0 à 5)")
    assert texto.index("seção número 1") < texto.index("seção número 2") < texto.index("seção número 3")
    assert "seção número 0" not in texto and "seção número 4" not in texto
    assert f"chunk {ids[2]} · posição 2) ← pedido" in texto


def test_ler_trecho_no_inicio_e_no_fim_trunca_a_janela(tmp_path):
    _, caminho_indice = _corpus_com_varios_chunks(tmp_path)
    ids = _ids_por_ordem(caminho_indice)

    inicio = server._ler_trecho_texto(caminho_indice, ids[0], vizinhos=2)
    fim = server._ler_trecho_texto(caminho_indice, ids[-1], vizinhos=2)

    assert "posições 0 a 2" in inicio
    assert "posições 3 a 5" in fim


def test_ler_trecho_limita_vizinhos_entre_0_e_5(tmp_path):
    _, caminho_indice = _corpus_com_varios_chunks(tmp_path)
    ids = _ids_por_ordem(caminho_indice)

    assert "posições 2 a 2" in server._ler_trecho_texto(caminho_indice, ids[2], vizinhos=-3)
    assert "posições 0 a 5" in server._ler_trecho_texto(caminho_indice, ids[2], vizinhos=50)


def test_ler_trecho_com_id_inexistente_orienta(tmp_path):
    _, caminho_indice = _corpus_com_varios_chunks(tmp_path)

    texto = server._ler_trecho_texto(caminho_indice, 9999)

    assert texto.startswith("Trecho não encontrado: chunk 9999.")


def test_ler_trecho_com_indice_ausente(tmp_path):
    texto = server._ler_trecho_texto(str(tmp_path / "nao-existe.db"), 1)

    assert "Índice não encontrado" in texto
