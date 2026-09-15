"""Reranker (TASK-009): reordenação dos candidatos híbridos por cross-encoder."""

import pytest

from docserver import cli, index, rerank


_AUTH = "# Auth\n\n## Tokens\n\nO refresh token dura 30 dias e é rotacionado a cada uso.\n"


def _chunk(ordem, texto):
    return {
        "caminho_origem": f"docs-fonte/doc{ordem}.md",
        "caminho_normalizado": f"doc{ordem}.md",
        "titulo_doc": "Doc",
        "secao": "Seção",
        "texto": texto,
        "ordem": 0,
    }


def _indice():
    conexao = index.criar_indice(":memory:")
    chunks = [
        _chunk(0, "O prazo de entrega padrão é de 30 dias úteis para pedidos nacionais."),
        _chunk(1, "Prazo de entrega internacional: 60 dias, sujeito à alfândega."),
        _chunk(2, "O prazo para devolução é de 7 dias após a entrega."),
    ]
    index.indexar_chunks(conexao, chunks, embeddings=[[1.0, 0.0, 0.0]] * 3, nome_modelo="fake")
    return conexao


def _buscar(conexao, **kwargs):
    return index.buscar_hibrido(
        conexao,
        "prazo de entrega",
        embeddar_consulta_fn=lambda consulta: [1.0, 0.0, 0.0],
        nome_modelo="fake",
        dimensao=3,
        **kwargs,
    )


def test_reranker_reordena_e_corta_abaixo_do_minimo(monkeypatch):
    monkeypatch.setenv("RERANK_MINIMO", "0.5")
    conexao = _indice()
    notas = {"docs-fonte/doc0.md": 0.2, "docs-fonte/doc1.md": 0.6, "docs-fonte/doc2.md": 0.9}
    chamadas = []

    def reranquear(consulta, itens):
        chamadas.append((consulta, [i["id"] for i in itens]))
        return [notas[i["caminho_origem"]] for i in itens]

    resultados = _buscar(conexao, reranquear_fn=reranquear)

    assert [r["caminho_origem"] for r in resultados] == ["docs-fonte/doc2.md", "docs-fonte/doc1.md"]
    assert [r["rerank"] for r in resultados] == [0.9, 0.6]
    assert len(chamadas) == 1 and len(chamadas[0][1]) == 3


def test_reranker_recebe_no_maximo_n_candidatos(monkeypatch):
    monkeypatch.setattr(index, "N_CANDIDATOS_RERANK", 2)
    conexao = _indice()
    recebidos = []

    def reranquear(consulta, itens):
        recebidos.append(len(itens))
        return [1.0] * len(itens)

    resultados = _buscar(conexao, reranquear_fn=reranquear)

    assert recebidos == [2] and len(resultados) == 2


def test_falha_no_reranker_cai_no_corte_normal_com_aviso():
    conexao = _indice()
    sem_rerank = _buscar(conexao, reranquear_fn=False)

    def quebrado(consulta, itens):
        raise OSError("modelo não baixado")

    avisos = []
    resultados = _buscar(conexao, reranquear_fn=quebrado, avisos=avisos)

    assert [r["id"] for r in resultados] == [r["id"] for r in sem_rerank]
    assert avisos == ["reranker indisponível (modelo não baixado); resultados na ordem da busca híbrida."]


def test_reranker_vem_da_env_e_desligado_nao_chama(monkeypatch):
    chamadas = []
    monkeypatch.setattr(rerank, "pontuar", lambda consulta, itens, chave=None: chamadas.append(chave) or [1.0] * len(itens))
    conexao = _indice()

    monkeypatch.setenv("RERANKER", "desligado")
    _buscar(conexao)
    assert chamadas == []

    monkeypatch.setenv("RERANKER", "bge-m3")
    _buscar(conexao)
    assert chamadas == ["bge-m3"]


def test_reranker_tambem_reordena_indice_sem_vetores(monkeypatch):
    conexao = index.criar_indice(":memory:")
    index.indexar_chunks(conexao, [_chunk(0, "prazo de entrega curto"), _chunk(1, "prazo de entrega longo")])

    resultados = index.buscar_hibrido(
        conexao, "prazo de entrega", reranquear_fn=lambda c, itens: [0.3 if "curto" in i["texto"] else 0.8 for i in itens]
    )

    assert [r["texto"] for r in resultados] == ["prazo de entrega longo", "prazo de entrega curto"]


def test_falha_ao_carregar_fica_em_cache(monkeypatch):
    tentativas = []

    def carregar(nome):
        tentativas.append(nome)
        raise OSError("sem rede")

    monkeypatch.setattr(rerank, "_carregar", carregar)
    monkeypatch.setattr(rerank, "_cache", {})

    for _ in range(3):
        with pytest.raises(OSError):
            rerank.obter_modelo("mminilm")

    assert tentativas == [rerank.MODELOS_RERANKER["mminilm"]]


def test_reranker_configurado_le_a_env(monkeypatch):
    monkeypatch.delenv("RERANKER", raising=False)
    assert rerank.reranker_configurado() == "mminilm"  # padrão escolhido pela avaliação
    monkeypatch.setenv("RERANKER", "mminilm")
    assert rerank.reranker_configurado() == "mminilm"
    monkeypatch.setenv("RERANKER", "Desligado")
    assert rerank.reranker_configurado() is None
    monkeypatch.setenv("RERANKER", "bge-m3")
    assert rerank.reranker_configurado() == "bge-m3"


def test_instalacao_so_lexica_nao_liga_o_reranker_por_padrao(monkeypatch):
    monkeypatch.setattr(rerank.importlib.util, "find_spec", lambda nome: None)
    monkeypatch.delenv("RERANKER", raising=False)
    assert rerank.reranker_configurado() is None
    # pedido explícito continua valendo (e cai no aviso de indisponível na busca)
    monkeypatch.setenv("RERANKER", "mminilm")
    assert rerank.reranker_configurado() == "mminilm"


def test_avaliacao_com_modo_de_reranker_usa_a_chave_do_modo(tmp_path, monkeypatch):
    chaves = []
    monkeypatch.setattr(rerank, "pontuar", lambda consulta, itens, chave=None: chaves.append(chave) or [1.0] * len(itens))
    docs_fonte = tmp_path / "docs-fonte"
    docs_fonte.mkdir()
    (docs_fonte / "auth.md").write_text(_AUTH, encoding="utf-8")
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(docs_fonte, tmp_path / "docs-normalizado", caminho_indice, sem_embeddings=True)
    perguntas = tmp_path / "perguntas.yaml"
    perguntas.write_text('- pergunta: "refresh token"\n  esperado: docs-fonte/auth.md\n  perfil: tecnico\n', encoding="utf-8")

    resultado = cli.executar_avaliacao(perguntas, caminho_indice, modos=("hibrido", "hibrido+mminilm"))

    assert chaves == ["mminilm"]  # `hibrido` puro é a linha de base, sem reranker
    assert resultado["hibrido+mminilm"]["tecnico"]["hit5"] == 1


def test_search_sem_rerank_nao_chama_o_reranker(tmp_path, monkeypatch, capsys):
    chamadas = []
    monkeypatch.setattr(rerank, "pontuar", lambda consulta, itens, chave=None: chamadas.append(1) or [1.0] * len(itens))
    monkeypatch.setenv("RERANKER", "mminilm")
    docs_fonte = tmp_path / "docs-fonte"
    docs_fonte.mkdir()
    (docs_fonte / "auth.md").write_text(_AUTH, encoding="utf-8")
    caminho_indice = str(tmp_path / "indice.db")
    cli.executar_ingestao(docs_fonte, tmp_path / "docs-normalizado", caminho_indice, sem_embeddings=True)

    cli.main(["--indice", caminho_indice, "search", "refresh token", "--sem-rerank"])
    assert chamadas == []
    cli.main(["--indice", caminho_indice, "search", "refresh token"])
    assert chamadas == [1]
    assert "auth.md" in capsys.readouterr().out


@pytest.mark.lento
def test_mminilm_real_poe_o_trecho_relevante_na_frente(monkeypatch):
    itens = [
        {"titulo_doc": "Manual", "secao": "Cozinha", "texto": "Receita de bolo de cenoura com cobertura de chocolate."},
        {"titulo_doc": "Manual", "secao": "Autenticação", "texto": "O refresh token expira em 30 dias e é rotacionado a cada uso."},
    ]

    notas = rerank.pontuar("quanto tempo dura o refresh token?", itens, "mminilm")

    assert all(0.0 <= n <= 1.0 for n in notas)
    assert notas[1] > notas[0]
