import pytest

from docserver import embed


def test_texto_de_passagem_recebe_o_prefixo_passage():
    resultado = embed.preparar_passagem("conteúdo qualquer")

    assert resultado == "passage: conteúdo qualquer"


def test_texto_de_consulta_recebe_o_prefixo_query():
    resultado = embed.preparar_consulta("pergunta qualquer")

    assert resultado == "query: pergunta qualquer"


def test_texto_embeddado_concatena_titulo_secao_e_corpo():
    chunk = {
        "titulo_doc": "Contrato de API v2",
        "secao": "Limites de requisição",
        "texto": "O cliente pode fazer até 100 requisições por minuto.",
    }

    resultado = embed.texto_para_embeddar(chunk)

    assert resultado == (
        "Contrato de API v2 — Limites de requisição — "
        "O cliente pode fazer até 100 requisições por minuto."
    )


def test_modelo_e_carregado_uma_unica_vez(monkeypatch):
    chamadas = []

    def _carregador_falso():
        chamadas.append(1)
        return "modelo-falso"

    monkeypatch.setattr(embed, "_carregar_modelo", _carregador_falso)
    monkeypatch.setattr(embed, "_modelo_cache", None)

    embed.obter_modelo()
    embed.obter_modelo()

    assert len(chamadas) == 1


class _ModeloFalso:
    def __init__(self):
        self.chamadas = []

    def encode(self, textos, batch_size=None, normalize_embeddings=False):
        import numpy as np

        self.chamadas.append((textos, batch_size, normalize_embeddings))
        return np.array([[float(len(t)), 0.0] for t in textos])


def test_embeddar_passagens_chama_o_modelo_uma_vez_com_todos_os_textos(monkeypatch):
    modelo = _ModeloFalso()
    monkeypatch.setattr(embed, "obter_modelo", lambda: modelo)
    chunks = [{"titulo_doc": "Doc", "secao": "S", "texto": f"texto {i}"} for i in range(5)]

    vetores = embed.embeddar_passagens(chunks, tamanho_lote=2)

    assert len(modelo.chamadas) == 1
    textos, lote, normalizado = modelo.chamadas[0]
    assert textos == [embed.preparar_passagem(embed.texto_para_embeddar(c)) for c in chunks]
    assert lote == 2 and normalizado
    assert len(vetores) == 5 and all(isinstance(v, list) for v in vetores)


def test_embeddar_passagens_sem_chunks_nao_carrega_o_modelo(monkeypatch):
    def _falhar():
        raise AssertionError("não deveria carregar o modelo")

    monkeypatch.setattr(embed, "obter_modelo", _falhar)
    assert embed.embeddar_passagens([]) == []


@pytest.mark.lento
def test_embeddings_em_lote_iguais_aos_individuais():
    chunks = [
        {"titulo_doc": "Guia", "secao": "Instalação", "texto": "Rode o comando de setup."},
        {"titulo_doc": "Auth", "secao": "Tokens", "texto": "O refresh token dura trinta dias e é rotacionado."},
        {"titulo_doc": "API", "secao": "Limites", "texto": "Até 100 requisições por minuto."},
    ]

    em_lote = embed.embeddar_passagens(chunks)
    individuais = [embed.embeddar_passagem(c) for c in chunks]

    for vetor_lote, vetor_individual in zip(em_lote, individuais):
        assert vetor_lote == pytest.approx(vetor_individual, abs=1e-5)


@pytest.mark.lento
def test_vetor_retornado_tem_a_dimensao_esperada_do_modelo():
    vetor = embed.embeddar_passagem({"titulo_doc": "Doc", "secao": "Sec", "texto": "Texto curto."})

    assert len(vetor) == embed.DIMENSAO
