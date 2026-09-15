# 0001 · Índice SQLite em modo WAL com timeout de 30 s

- **Data:** 2026-09-15 · **Status:** Aceita
- **Tarefa:** TASK-003 · **Commit:** `334a281`

## Contexto
Com o `docserver watch`, a ingestão roda em outro processo com o servidor MCP
no ar. No journal padrão do SQLite, enquanto a ingestão confirmava a transação
final, as leituras do servidor ficavam bloqueadas, e uma busca que esperasse
mais de 5 s (timeout padrão) falhava com `database is locked`.

## Alternativas consideradas
- **Só aumentar o timeout** — a busca espera a gravação inteira em vez de
  falhar; não resolve a espera.
- **Trocar o índice por cópia atômica** (gravar num arquivo novo e renomear) —
  resolve também falhas no meio, mas é maior; ficou como TASK-013.
- **WAL** — leitores continuam vendo a versão anterior até o commit.

## Decisão
`index.criar_indice` liga `PRAGMA journal_mode=WAL` (exceto `:memory:`) e abre
a conexão com `timeout=30`.

## Consequências
- Buscas durante a ingestão respondem com o índice anterior, sem erro (teste
  com duas conexões).
- Aparecem `indice.db-wal` e `indice.db-shm` ao lado do índice; para copiar o
  índice, copie os três ou pare os processos antes.
- WAL não é confiável em pasta de rede (NFS/SMB).
