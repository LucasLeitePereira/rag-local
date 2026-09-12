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


@pytest.mark.lento
def test_vetor_retornado_tem_a_dimensao_esperada_do_modelo():
    vetor = embed.embeddar_passagem({"titulo_doc": "Doc", "secao": "Sec", "texto": "Texto curto."})

    assert len(vetor) == embed.DIMENSAO
