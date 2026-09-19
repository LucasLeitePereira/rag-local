"""Troca atômica (TASK-013), lock de ingestão (TASK-016) e progresso (TASK-051)."""

import subprocess
import sys
import threading

import numpy as np
import pytest

from docserver import cli, embed, index


def _corpus(tmp_path, quantidade=3):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    docs_normalizado.mkdir()
    for i in range(1, quantidade + 1):
        (docs_fonte / f"doc{i}.md").write_text(
            f"# Documento {i}\n\n## Seção\n\nConteúdo do documento {i} com texto suficiente, assunto{i}.\n",
            encoding="utf-8",
        )
    return docs_fonte, docs_normalizado, str(tmp_path / "indice.db")


def _ingerir(docs_fonte, docs_normalizado, caminho_indice, **kwargs):
    kwargs.setdefault("embeddar_passagem_fn", lambda chunk: [1.0, 0.0, 0.0])
    kwargs.setdefault("nome_modelo", "fake")
    return cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice, **kwargs)


def _md_de(docs_normalizado):
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(docs_normalizado.rglob("*.md"))}


# --------------------------------------------------------------------------- TASK-013


def test_falha_nos_embeddings_nao_altera_docs_normalizado_nem_o_indice(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    _ingerir(docs_fonte, docs_normalizado, caminho_indice)
    antes_md = _md_de(docs_normalizado)
    antes_chunks = cli.executar_stats(caminho_indice)["chunks"]

    (docs_fonte / "doc2.md").write_text(
        "# Documento 2 revisado\n\n## Nova seção\n\nTexto completamente novo do documento dois.\n",
        encoding="utf-8",
    )
    (docs_fonte / "doc4.md").write_text(
        "# Documento 4\n\n## Seção\n\nDocumento que ainda não existia no índice anterior.\n",
        encoding="utf-8",
    )

    def _explodir(chunk):
        raise RuntimeError("falha injetada durante os embeddings")

    with pytest.raises(RuntimeError, match="falha injetada"):
        _ingerir(docs_fonte, docs_normalizado, caminho_indice, embeddar_passagem_fn=_explodir)

    assert _md_de(docs_normalizado) == antes_md
    assert not (docs_normalizado / "doc4.md").exists()
    assert cli.executar_stats(caminho_indice)["chunks"] == antes_chunks


def test_a_pasta_temporaria_da_ingestao_nao_sobrevive_a_uma_falha(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)

    def _explodir(chunk):
        raise RuntimeError("falha injetada")

    with pytest.raises(RuntimeError):
        _ingerir(docs_fonte, docs_normalizado, caminho_indice, embeddar_passagem_fn=_explodir)

    assert [p for p in tmp_path.iterdir() if p.name.startswith(".docs-normalizado.tmp")] == []


def test_temporaria_deixada_por_um_processo_morto_e_limpa_na_proxima_ingestao(tmp_path):
    """Um `kill -9` não roda o `finally` que apaga a pasta temporária; a ingestão
    seguinte varre o que sobrou, já com o lock na mão."""
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path, quantidade=1)
    orfa = tmp_path / ".docs-normalizado.tmp-9999-deadbeef"
    orfa.mkdir()
    (orfa / "lixo.md").write_text("sobra de uma ingestão morta", encoding="utf-8")

    _ingerir(docs_fonte, docs_normalizado, caminho_indice)

    assert not orfa.exists()
    assert (docs_normalizado / "doc1.md").is_file()


def test_ingestao_bem_sucedida_grava_os_md_com_os_mesmos_caminhos_de_antes(tmp_path):
    """A pasta temporária é detalhe interno: o resultado em disco e no índice tem de ser
    idêntico ao de escrever direto em docs-normalizado, inclusive em subpastas."""
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path, quantidade=1)
    (docs_fonte / "manuais").mkdir()
    (docs_fonte / "manuais" / "guia.md").write_text(
        "# Guia\n\n## Uso\n\nTexto do guia dentro de uma subpasta para testar o espelhamento.\n",
        encoding="utf-8",
    )

    _ingerir(docs_fonte, docs_normalizado, caminho_indice)

    assert (docs_normalizado / "doc1.md").is_file()
    assert (docs_normalizado / "manuais" / "guia.md").is_file()
    conexao = index.criar_indice(caminho_indice)
    try:
        normalizados = {
            linha[0] for linha in conexao.execute("SELECT caminho_normalizado FROM chunks")
        }
    finally:
        conexao.close()
    assert normalizados == {"doc1.md", "manuais/guia.md"}


# --------------------------------------------------------------------------- TASK-016


def test_segunda_ingestao_simultanea_aborta_com_mensagem_sobre_o_lock(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    segurando = threading.Event()
    liberar = threading.Event()
    erro: list[BaseException] = []

    def _dono():
        with cli.travar_ingestao(caminho_indice):
            segurando.set()
            liberar.wait(10)

    thread = threading.Thread(target=_dono)
    thread.start()
    try:
        assert segurando.wait(10)
        with pytest.raises(cli.ErroIngestao) as capturado:
            _ingerir(docs_fonte, docs_normalizado, caminho_indice)
        erro.append(capturado.value)
    finally:
        liberar.set()
        thread.join(10)

    mensagem = str(erro[0])
    assert "outra ingestão já está em andamento" in mensagem
    assert "indice.db.lock" in mensagem
    # abortou antes de tocar em qualquer coisa
    assert list(docs_normalizado.rglob("*.md")) == []


def test_ingestao_abortada_pelo_lock_nao_deixa_o_indice_pela_metade(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    _ingerir(docs_fonte, docs_normalizado, caminho_indice)
    chunks_antes = cli.executar_stats(caminho_indice)["chunks"]
    (docs_fonte / "doc9.md").write_text(
        "# Documento 9\n\n## Seção\n\nArquivo novo que não deve entrar enquanto o lock existir.\n",
        encoding="utf-8",
    )

    # a segunda tentativa vem de outro processo, como no uso real (watcher + ingest)
    with cli.travar_ingestao(caminho_indice):
        resultado = subprocess.run(
            [
                sys.executable,
                "-c",
                "from docserver import cli; cli.main()",
                "--docs-fonte",
                str(docs_fonte),
                "--docs-normalizado",
                str(docs_normalizado),
                "--indice",
                caminho_indice,
                "ingest",
                "--sem-embeddings",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    assert resultado.returncode == 1
    assert "outra ingestão já está em andamento" in resultado.stderr
    assert cli.executar_stats(caminho_indice)["chunks"] == chunks_antes
    assert not (docs_normalizado / "doc9.md").exists()


def test_lock_orfao_de_processo_morto_nao_bloqueia_a_proxima_ingestao(tmp_path):
    """O lock é mantido pelo SO, não pelo conteúdo do arquivo: um `.lock` deixado para
    trás por um processo que morreu (com PID de outro processo dentro) não trava nada."""
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    caminho_lock = cli.caminho_do_lock(caminho_indice)
    caminho_lock.parent.mkdir(parents=True, exist_ok=True)
    caminho_lock.write_text("999999", encoding="utf-8")

    relatorio = _ingerir(docs_fonte, docs_normalizado, caminho_indice)

    assert relatorio["processados"] == 3
    assert (docs_normalizado / "doc1.md").is_file()


def test_lock_e_reentrante_na_mesma_thread(tmp_path):
    """`ingest --limpar` segura o lock e `executar_ingestao` volta a pedi-lo."""
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    with cli.travar_ingestao(caminho_indice):
        relatorio = _ingerir(docs_fonte, docs_normalizado, caminho_indice)
    assert relatorio["processados"] == 3


def test_ingestao_que_espera_pelo_lock_entra_quando_ele_e_liberado(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    # um subprocesso segura o lock por 1 s, como faria um `docserver ingest` manual
    script = (
        "import time, sys; "
        "from docserver import cli; "
        "ctx = cli.travar_ingestao(sys.argv[1]); "
        "ctx.__enter__(); "
        "print('ok', flush=True); "
        "time.sleep(1.0); "
        "ctx.__exit__(None, None, None)"
    )
    processo = subprocess.Popen(
        [sys.executable, "-c", script, caminho_indice], stdout=subprocess.PIPE, text=True
    )
    try:
        assert processo.stdout.readline().strip() == "ok"
        relatorio = _ingerir(docs_fonte, docs_normalizado, caminho_indice, esperar_lock=20.0)
    finally:
        processo.wait(20)

    assert relatorio["processados"] == 3


# --------------------------------------------------------------------------- TASK-051


def test_progresso_reporta_etapas_e_cada_arquivo(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    linhas: list[str] = []

    relatorio = _ingerir(docs_fonte, docs_normalizado, caminho_indice, progresso_fn=linhas.append)

    texto = "\n".join(linhas)
    assert "extração: 3 arquivo(s) a processar" in texto
    for numero in (1, 2, 3):
        assert f"[{numero}/3] extraindo doc{numero}.md" in texto
        assert f"[{numero}/3] doc{numero}.md: " in texto and "chunks em" in texto
    assert "gravando o índice" in texto
    assert "ingestão concluída em" in texto
    assert relatorio["processados"] == 3


def test_progresso_numera_apenas_o_que_sera_reprocessado(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    _ingerir(docs_fonte, docs_normalizado, caminho_indice)
    (docs_fonte / "doc2.md").write_text(
        "# Documento 2 revisado\n\n## Seção\n\nTexto novo o bastante para mudar o sha256.\n",
        encoding="utf-8",
    )
    linhas: list[str] = []

    _ingerir(docs_fonte, docs_normalizado, caminho_indice, progresso_fn=linhas.append)

    texto = "\n".join(linhas)
    assert "extração: 1 arquivo(s) a processar, 2 inalterado(s)" in texto
    assert "[1/1] extraindo doc2.md" in texto


def test_sem_progresso_fn_a_ingestao_nao_escreve_nada(tmp_path, capsys):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)
    _ingerir(docs_fonte, docs_normalizado, caminho_indice)
    capturado = capsys.readouterr()
    assert capturado.out == ""
    assert capturado.err == ""


def test_relatorio_traz_tempo_por_etapa_e_o_arquivo_mais_lento(tmp_path):
    docs_fonte, docs_normalizado, caminho_indice = _corpus(tmp_path)

    relatorio = _ingerir(docs_fonte, docs_normalizado, caminho_indice)

    assert set(relatorio["tempos"]) == {"extracao", "embeddings", "indice", "troca"}
    assert all(valor >= 0 for valor in relatorio["tempos"].values())
    caminho_lento, segundos = relatorio["mais_lento"]
    assert caminho_lento.endswith(".md") and segundos >= 0

    texto = cli.formatar_relatorio(relatorio)
    assert "Tempo por etapa:" in texto
    assert "Extração:" in texto
    assert "Arquivo mais lento:" in texto


def test_embeddar_passagens_informa_o_avanco_em_blocos(monkeypatch):
    class _ModeloFalso:
        def encode(self, textos, batch_size=None, normalize_embeddings=None):
            return np.array([[0.1, 0.2] for _ in textos])

    monkeypatch.setattr(embed, "obter_modelo", lambda: _ModeloFalso())
    chunks = [{"texto": f"trecho {i}"} for i in range(60)]
    avancos: list[tuple[int, int]] = []

    vetores = embed.embeddar_passagens(chunks, progresso_fn=lambda f, t: avancos.append((f, t)))

    assert len(vetores) == 60
    assert avancos == [(25, 60), (50, 60), (60, 60)]


def test_embeddar_passagens_em_blocos_da_o_mesmo_resultado_de_uma_chamada_so(monkeypatch):
    class _ModeloFalso:
        def encode(self, textos, batch_size=None, normalize_embeddings=None):
            return np.array([[float(len(texto)), 1.0] for texto in textos])

    monkeypatch.setattr(embed, "obter_modelo", lambda: _ModeloFalso())
    chunks = [{"texto": "x" * i} for i in range(40)]

    de_uma_vez = embed.embeddar_passagens(chunks)
    em_blocos = embed.embeddar_passagens(chunks, progresso_fn=lambda f, t: None)

    assert de_uma_vez == em_blocos
