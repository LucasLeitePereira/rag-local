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
    cli.executar_ingestao(docs_fonte, docs_normalizado, caminho_indice)
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
    docs_normalizado, _ = _preparar_corpus(tmp_path)

    texto = server._listar_documentos_texto(docs_normalizado)

    assert "docs-fonte/autenticacao.md" in texto
    assert "Autenticação" in texto
    assert "Renovação de token" in texto
    assert "Login" in texto


def test_ler_documento_aceita_caminho_parcial_e_resolve_para_o_arquivo_certo(tmp_path):
    docs_normalizado, _ = _preparar_corpus(tmp_path)

    texto = server._ler_documento_texto("autenticacao.md", docs_normalizado)

    assert "Renovação de token" in texto


def test_ler_documento_com_caminho_ambiguo_lista_as_opcoes(tmp_path):
    docs_normalizado, _ = _preparar_corpus(tmp_path)
    outra_pasta = docs_normalizado / "outra"
    outra_pasta.mkdir()
    (outra_pasta / "autenticacao.md").write_text(
        "---\norigem: docs-fonte/outra/autenticacao.md\nextrator: x\ningerido_em: y\n---\n\n"
        "# Outra Autenticação\n\nConteúdo.\n",
        encoding="utf-8",
    )

    texto = server._ler_documento_texto("autenticacao.md", docs_normalizado)

    assert "ambígu" in texto.lower()
    assert "outra/autenticacao.md" in texto


def test_ler_documento_rejeita_path_traversal(tmp_path):
    docs_normalizado, _ = _preparar_corpus(tmp_path)

    texto = server._ler_documento_texto("../../../etc/passwd", docs_normalizado)

    assert "inválido" in texto.lower() or "não encontrado" in texto.lower()


def test_ler_documento_com_caminho_inexistente_retorna_mensagem_util(tmp_path):
    docs_normalizado, _ = _preparar_corpus(tmp_path)

    texto = server._ler_documento_texto("nao-existe.md", docs_normalizado)

    assert "não encontrado" in texto.lower()
