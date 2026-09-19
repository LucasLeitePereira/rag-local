"""`docserver watch`: observa docs-fonte e reingere sozinho quando algo muda."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from docserver import cli, extract

ESPERA_PADRAO = 2.0
INTERVALO_VERIFICACAO = 0.5


def _log(mensagem: str) -> None:
    print(f"docserver: {mensagem}", flush=True)


class Agrupador:
    """Debounce: copiar uma pasta ou salvar um .docx gera dezenas de eventos; só
    vale reingerir quando passam `espera` segundos sem nenhum evento novo."""

    def __init__(self, espera: float, relogio=time.monotonic) -> None:
        self.espera = espera
        self._relogio = relogio
        self._lock = threading.Lock()
        self._pendente = False
        self._ultima_mudanca = 0.0
        self.eventos = 0

    def registrar(self) -> None:
        with self._lock:
            self._pendente = True
            self._ultima_mudanca = self._relogio()
            self.eventos += 1

    def pronto(self) -> bool:
        with self._lock:
            return self._pendente and self._relogio() - self._ultima_mudanca >= self.espera

    def consumir(self) -> int:
        """Zera a pendência e devolve quantos eventos ela acumulou. Eventos que chegarem
        depois (inclusive durante a ingestão) abrem uma pendência nova."""
        with self._lock:
            eventos = self.eventos
            self._pendente = False
            self.eventos = 0
            return eventos


def arquivo_relevante(caminho: str | bytes) -> bool:
    """Só interessam arquivos que a ingestão de fato leria: descarta ocultos, os
    temporários `~$` do Office e formatos sem extrator (inclusive `.tmp` de editores)."""
    arquivo = Path(os.fsdecode(caminho))
    return not cli._deve_ignorar(arquivo) and arquivo.suffix.lower() in extract.EXTRATORES


def _chave(caminho: str | bytes) -> str:
    return os.path.normcase(os.path.abspath(os.fsdecode(caminho)))


def _estado(caminho: str) -> tuple[int, int] | None:
    """(tamanho, mtime_ns) do arquivo, ou None se ele não existe."""
    try:
        info = os.stat(caminho)
    except OSError:
        return None
    return info.st_size, info.st_mtime_ns


class _Manipulador(FileSystemEventHandler):
    """Registra no agrupador as mudanças em arquivos que a ingestão leria.

    No Windows, só ler um arquivo (o que a própria ingestão faz) atualiza o último
    acesso e gera um evento `modified` — sem filtro, cada ingestão disparava a
    próxima. Por isso `modified` só conta se tamanho ou mtime mudaram em relação ao
    último estado visto; `docs_fonte` pré-carrega esse estado na partida."""

    def __init__(self, agrupador: Agrupador, docs_fonte: Path | None = None) -> None:
        self._agrupador = agrupador
        self._estados: dict[str, tuple[int, int] | None] = {}
        if docs_fonte is not None:
            for arquivo in Path(docs_fonte).rglob("*"):
                if arquivo.is_file() and arquivo_relevante(str(arquivo)):
                    self._estados[_chave(str(arquivo))] = _estado(str(arquivo))

    def _atualizar(self, caminho: str | bytes) -> bool:
        """Grava o estado atual e diz se ele difere do anterior (ou se é desconhecido)."""
        chave = _chave(caminho)
        atual = _estado(chave)
        mudou = chave not in self._estados or self._estados[chave] != atual
        self._estados[chave] = atual
        return mudou

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory or event.event_type in ("opened", "closed_no_write"):
            return
        if event.event_type == "modified":
            if arquivo_relevante(event.src_path) and self._atualizar(event.src_path):
                self._agrupador.registrar()
            return
        caminhos = [c for c in (event.src_path, getattr(event, "dest_path", "")) if c]
        for caminho in caminhos:
            self._atualizar(caminho)
        # renomear `rascunho.tmp` para `guia.md` só é relevante pelo destino, e
        # `guia.md` para `guia.bak` só pela origem — por isso vale qualquer um dos dois.
        if any(arquivo_relevante(c) for c in caminhos):
            self._agrupador.registrar()


def _ingerir_e_relatar(docs_fonte: Path, docs_normalizado: Path, indice: str, sem_embeddings: bool) -> None:
    relatorio = cli.executar_ingestao(
        docs_fonte,
        docs_normalizado,
        indice,
        sem_embeddings=sem_embeddings,
        # uma reingestão pode levar minutos: sem progresso, o watcher fica mudo o tempo todo
        progresso_fn=_log,
        # se um `docserver ingest` manual estiver rodando, o watcher espera em vez de
        # desistir — a mudança que o acordou continuaria pendente de qualquer forma
        esperar_lock=cli.ESPERA_LOCK_WATCHER,
    )
    print(cli.formatar_relatorio(relatorio), flush=True)


def _rodar_com_seguranca(ingerir_fn) -> None:
    """Uma ingestão que falha não pode derrubar o watcher: a próxima mudança (por
    exemplo, o arquivo terminar de ser copiado) tenta de novo."""
    try:
        ingerir_fn()
    except cli.ErroIngestao as erro:
        _log(f"ingestão abortada: {erro}")
    except Exception as erro:  # noqa: BLE001 — qualquer falha é registrada e o laço segue
        _log(f"erro inesperado na ingestão: {erro!r}")


def observar(
    docs_fonte: Path,
    docs_normalizado: Path,
    indice: str,
    sem_embeddings: bool = False,
    espera: float = ESPERA_PADRAO,
    ingerir_fn=None,
    parar: threading.Event | None = None,
    relogio=time.monotonic,
) -> None:
    """Faz uma ingestão inicial (pega o que mudou com o watcher desligado) e depois
    reingere a cada lote de mudanças em `docs_fonte`, até `parar` ser acionado."""
    if ingerir_fn is None:
        def ingerir_fn():
            _ingerir_e_relatar(docs_fonte, docs_normalizado, indice, sem_embeddings)
    parar = parar or threading.Event()
    agrupador = Agrupador(espera, relogio=relogio)

    # o observador sobe antes da ingestão inicial: o que mudar enquanto ela roda
    # vira uma pendência, em vez de se perder
    observador = Observer()
    observador.schedule(_Manipulador(agrupador, docs_fonte), str(docs_fonte), recursive=True)
    observador.start()
    try:
        _log("ingestão inicial")
        _rodar_com_seguranca(ingerir_fn)
        _log(f"observando {Path(docs_fonte).resolve()} (Ctrl+C para sair)")
        while not parar.wait(INTERVALO_VERIFICACAO):
            if agrupador.pronto():
                eventos = agrupador.consumir()
                _log(f"{eventos} mudança(s) detectada(s), reingerindo")
                _rodar_com_seguranca(ingerir_fn)
    finally:
        observador.stop()
        observador.join()
