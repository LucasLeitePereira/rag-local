# 0008 · Watcher ignora `modified` sem mudança de tamanho ou mtime

- **Data:** 2026-09-15 · **Status:** Aceita
- **Tarefa:** — (achado ao testar o `docserver watch`) · **Commit:** `c5aa97c`

## Contexto
No Windows, a leitura feita pela própria ingestão atualiza o "último acesso"
dos arquivos e gera eventos `modified` no `watchdog`. Cada ingestão
disparava a próxima, sem fim.

## Alternativas consideradas
- **Ignorar eventos durante a ingestão e por alguns segundos depois** —
  depende de tempo; perde mudanças reais feitas nesse intervalo.
- **Comparar o sha256 a cada evento** — correto, mas lê o arquivo inteiro a
  cada evento.
- **Comparar `(tamanho, mtime_ns)` com o último estado conhecido.**

## Decisão
- **Estado inicial:** `_Manipulador` guarda `(st_size, st_mtime_ns)` por
  arquivo, preenchido na partida.
- **`modified`:** só conta se o estado mudou ou era desconhecido.
- **`created`, `deleted` e `moved`:** sempre contam.

## Consequências
- **Laço:** o watcher parado depois de uma ingestão não se redispara (coberto
  por teste; ainda não observado por mais de 1 h numa execução real).
- **Detecção de mudança:** uma alteração que preserve tamanho e `mtime` não é
  detectada pelo watcher, mas a próxima `docserver ingest` a pega pelo sha256.
