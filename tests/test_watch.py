import threading
import time

import pytest
from watchdog.events import DirCreatedEvent, FileCreatedEvent, FileModifiedEvent, FileMovedEvent

from docserver import cli, index, watch


class RelogioFalso:
    def __init__(self):
        self.agora = 0.0

    def __call__(self):
        return self.agora


def test_agrupador_so_dispara_depois_da_espera_sem_eventos_novos():
    relogio = RelogioFalso()
    agrupador = watch.Agrupador(espera=2.0, relogio=relogio)
    assert not agrupador.pronto()

    agrupador.registrar()
    relogio.agora = 1.5
    assert not agrupador.pronto()

    agrupador.registrar()  # evento durante a espera reinicia a contagem
    relogio.agora = 3.0
    assert not agrupador.pronto()

    relogio.agora = 3.5
    assert agrupador.pronto()


def test_agrupador_rajada_de_eventos_vira_um_unico_disparo():
    relogio = RelogioFalso()
    agrupador = watch.Agrupador(espera=1.0, relogio=relogio)
    for _ in range(20):
        agrupador.registrar()

    relogio.agora = 1.0
    assert agrupador.pronto()
    assert agrupador.consumir() == 20
    assert not agrupador.pronto()


@pytest.mark.parametrize(
    "evento, relevante",
    [
        (FileModifiedEvent("docs-fonte/guia.md"), True),
        (FileCreatedEvent("docs-fonte/api/contrato.PDF"), True),
        (FileModifiedEvent("docs-fonte/~$relatorio.docx"), False),
        (FileModifiedEvent("docs-fonte/.oculto.md"), False),
        (FileCreatedEvent("docs-fonte/foto.png"), False),
        (DirCreatedEvent("docs-fonte/nova-pasta"), False),
        (FileMovedEvent("docs-fonte/rascunho.tmp", "docs-fonte/guia.md"), True),
        (FileMovedEvent("docs-fonte/guia.md", "docs-fonte/guia.bak"), True),
    ],
)
def test_manipulador_so_registra_arquivos_que_a_ingestao_leria(evento, relevante):
    agrupador = watch.Agrupador(espera=0)
    watch._Manipulador(agrupador).dispatch(evento)
    assert agrupador.pronto() is relevante


def _rodar_em_thread(**kwargs):
    parar = threading.Event()
    thread = threading.Thread(target=watch.observar, kwargs={**kwargs, "parar": parar}, daemon=True)
    thread.start()
    return parar, thread


def _aguardar(condicao, prazo=10.0):
    limite = time.monotonic() + prazo
    while time.monotonic() < limite:
        if condicao():
            return True
        time.sleep(0.1)
    return False


def test_observar_faz_ingestao_inicial_e_segue_vivo_apos_erro(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_fonte.mkdir()
    chamadas = []

    def ingerir_falhando():
        chamadas.append(1)
        raise cli.ErroIngestao("simulado")

    parar, thread = _rodar_em_thread(
        docs_fonte=docs_fonte,
        docs_normalizado=tmp_path / "docs-normalizado",
        indice=str(tmp_path / "indice.db"),
        espera=0.1,
        ingerir_fn=ingerir_falhando,
    )
    try:
        assert _aguardar(lambda: len(chamadas) == 1)
        (docs_fonte / "guia.md").write_text("# Guia\n", encoding="utf-8")
        assert _aguardar(lambda: len(chamadas) >= 2)
        assert thread.is_alive()
    finally:
        parar.set()
        thread.join(timeout=5)
    assert not thread.is_alive()


def test_observar_indexa_arquivo_criado_depois_de_iniciado(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_normalizado = tmp_path / "docs-normalizado"
    docs_fonte.mkdir()
    docs_normalizado.mkdir()
    caminho_indice = str(tmp_path / "indice.db")

    parar, thread = _rodar_em_thread(
        docs_fonte=docs_fonte,
        docs_normalizado=docs_normalizado,
        indice=caminho_indice,
        sem_embeddings=True,
        espera=0.2,
    )
    try:
        time.sleep(0.5)  # deixa a ingestão inicial (vazia, abortada) passar
        (docs_fonte / "guia.md").write_text(
            "# Guia\n\n## Instalação\n\nRode o comando de setup para instalar o sistema.\n",
            encoding="utf-8",
        )
        # prazo folgado: a primeira ingestão do processo carrega o tokenizador do chunking
        assert _aguardar(lambda: index.contar_chunks(caminho_indice) > 0, prazo=60.0)
    finally:
        parar.set()
        thread.join(timeout=5)

    assert "instalar" in cli.formatar_resultados(cli.executar_busca(caminho_indice, "setup", modo="lexico"))


def test_parser_aceita_comando_watch():
    args = cli.construir_parser().parse_args(["watch", "--espera", "1", "--sem-embeddings"])
    assert args.func is cli._comando_watch
    assert args.espera == 1.0
    assert args.sem_embeddings


def test_comando_watch_com_fonte_inexistente_sai_com_erro(tmp_path, capsys):
    with pytest.raises(SystemExit) as saida:
        cli.main(["--docs-fonte", str(tmp_path / "nao-existe"), "--indice", str(tmp_path / "i.db"), "watch"])
    assert saida.value.code == 1
    assert "abortada" in capsys.readouterr().err.lower()


def test_modified_sem_mudanca_real_nao_registra_mas_conteudo_novo_sim(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_fonte.mkdir()
    guia = docs_fonte / "guia.md"
    guia.write_text("# Guia\n\nconteúdo inicial\n", encoding="utf-8")
    agrupador = watch.Agrupador(espera=0)
    manipulador = watch._Manipulador(agrupador, docs_fonte)

    guia.read_text(encoding="utf-8")  # leitura (último acesso) gera `modified` no Windows
    manipulador.dispatch(FileModifiedEvent(str(guia)))
    assert not agrupador.pronto()

    guia.write_text("# Guia\n\nconteúdo inicial, agora bem maior que antes\n", encoding="utf-8")
    manipulador.dispatch(FileModifiedEvent(str(guia)))
    assert agrupador.pronto()

    agrupador.consumir()
    manipulador.dispatch(FileModifiedEvent(str(guia)))  # mesmo estado já visto
    assert not agrupador.pronto()


def test_modified_de_arquivo_criado_depois_da_partida_registra(tmp_path):
    docs_fonte = tmp_path / "docs-fonte"
    docs_fonte.mkdir()
    agrupador = watch.Agrupador(espera=0)
    manipulador = watch._Manipulador(agrupador, docs_fonte)
    novo = docs_fonte / "novo.md"
    novo.write_text("# Novo\n", encoding="utf-8")

    manipulador.dispatch(FileModifiedEvent(str(novo)))

    assert agrupador.pronto()
