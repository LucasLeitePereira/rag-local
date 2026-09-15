# Sessão 2026-09-15 · Tarefas de prioridade alta (TASK-001 a TASK-009)

- **Branch:** `feat/prioridade-alta` (a partir de `fix/achados-criticos`)
- **Plano:** [`planos/2026-09-15-prioridade-alta.md`](../planos/2026-09-15-prioridade-alta.md)
- **Duração:** duas partes: madrugada (implementação) e dia seguinte
  (reingestão real, avaliação, calibração)

## Pedido

Resolver as tarefas de prioridade alta do backlog (TASK-001 a TASK-009) mais
dois extras: o laço do watcher e a TASK-012 (Tesseract).

### Decisões do usuário no início
- **Reranker:** suportar dois modelos e escolher o padrão pela avaliação.
- **Perguntas de avaliação dos PDFs:** escritas pelo assistente, lendo o corpus.
- **Extras:** laço do watcher e TASK-012 incluídos.
- **Git:** commitar o pendente, criar branch nova e fazer um commit por tarefa.

## Parte 1 · Implementação

| Ordem | Tarefa | Commit | Decisão |
|---|---|---|---|
| 1 | TASK-003 · WAL | `334a281` | [0001](../decisoes/0001-indice-em-modo-wal.md) |
| 2 | TASK-004 · embeddings em lote | `124a2da` | [0002](../decisoes/0002-embeddings-lote-padrao-1.md) |
| 3 | TASK-002 · fallback léxico | `5079369` | [0003](../decisoes/0003-fallback-lexico-com-aviso.md) |
| 4 | TASK-007 + TASK-049 · avaliação | `933bc39` | [0004](../decisoes/0004-conjunto-de-avaliacao-do-corpus-local.md) |
| 5 | TASK-008 · pesos BM25, esquema versionado | `78cbd4c` | [0005](../decisoes/0005-pesos-bm25-e-versao-do-esquema.md) |
| 6 | TASK-006 + TASK-012 · páginas, sem OCR | `84e63ab` | [0006](../decisoes/0006-pagina-por-marcador-e-pdf-sem-ocr.md) |
| 7 | TASK-005 · ingestão incremental | `a8b7737` | [0007](../decisoes/0007-ingestao-incremental-por-sha256.md) |
| 8 | Watcher · eventos de último acesso | `c5aa97c` | [0008](../decisoes/0008-watcher-filtra-eventos-por-stat.md) |
| 9 | TASK-001 · leitura em partes, `ler_trecho` | `a8ffaac` | [0009](../decisoes/0009-leitura-em-partes-e-ler-trecho.md) |
| 10 | TASK-009 · reranker (código, desligado) | `d736053` | [0010](../decisoes/0010-reranker-mminilm-padrao.md) |

### Problemas encontrados
- **Scores fora de 0–1:** o mMiniLM devolvia logits crus (a ativação do modelo
  é identidade). Correção: pedir sempre os logits e aplicar a sigmoide no
  `rerank.pontuar`.
- **Ordem de apagar os `.md` órfãos:** eram removidos antes da gravação do
  índice; uma falha na gravação deixaria índice e disco divergentes. Passaram
  a ser removidos depois do commit, com teste.
- **Fixture de teste curta demais:** o texto tinha menos de `MIN_CARACTERES` e
  não gerava chunk.
- **Heredocs no Git Bash:** corrompiam aspas e barras invertidas ao escrever
  arquivos. Passamos a usar scripts Python ou edição direta.

### Encerramento da parte 1
O usuário pediu para parar. A reingestão real (em andamento) e o download do
bge-m3 foram interrompidos; o índice v1 ficou intacto. O reranker ficou
desligado por padrão, e os passos para retomar foram anotados no `tasks.md`.

## Parte 2 · Reingestão, avaliação e calibração

1. **Reingestão do corpus real:** 36,5 min (v1 → v4, 6 109 chunks). A segunda
   rodada levou 2,4 s. Ver
   [`testes/2026-09-15-reingestao-corpus-real.md`](../testes/2026-09-15-reingestao-corpus-real.md).
2. **Download do bge-m3:** concluído (~2,3 GB). O disco C: ficou com 7,2 GB
   livres.
3. **Avaliação com os dois rerankers juntos:** morta por falta de memória.
   Rodamos um modelo por vez.
4. **mMiniLM com corte 0.1:** ganha nas negativas, mas perde acertos.
   Calibramos o corte a partir das notas coletadas uma única vez. Ver
   [`testes/2026-09-15-avaliacao-reranker.md`](../testes/2026-09-15-avaliacao-reranker.md).
5. **bge-m3 sozinho:** ~35 s por busca, e o processo foi morto por memória
   após 46 perguntas. Descartado como padrão.
6. **Decisão:** mMiniLM ligado por padrão, `RERANK_MINIMO` 0.01, lotes de 8
   pares. Instalação só léxica não liga o reranker. Commit `a23f5b6`.
7. **Verificação final no índice real:** página na busca, "parte 1 de 52",
   `ler_trecho`, `pytest -m lento`.
8. **`tasks.md`:** TASK-009 concluída (`5b92286`).
9. **Registro do projeto:** criada a pasta `projeto/` (este registro), com
   `tasks.md`, `diagnostico.md` e `PLAN.md` movidos para dentro.

### Outros acontecimentos
- **Remote Control:** o usuário quis acompanhar pelo celular. `! claude rc` no
  prompt abre um **segundo** Claude Code, que trava esperando confirmação; o
  certo é digitar `/remote-control` direto no prompt da sessão.
- **Timeout de busca no repositório:** um `grep -r` na raiz passou de 120 s
  porque entrou em `venv/` e `docs-normalizado/`. Use a busca com filtro de
  pastas.

## Pendências

- **PR de `feat/prioridade-alta` contra `master`:** aguardando confirmação do
  usuário para o push. A branch também carrega `6cdb0aa` (achados críticos) e
  `88cffa4` (watcher), que não estão no `master`.
- **Verificações sem teste real:** busca concorrente com ingestão em processos
  reais e watcher parado por mais de 1 h.
- **Negativas:** só 27% das perguntas sem resposta voltam vazias com o
  reranker (TASK-024).
- **Latência:** ~3 s por busca com reranker; `N_CANDIDATOS_RERANK` não é
  configurável.
- **bge-m3:** medir em máquina com GPU ou mais RAM, se houver interesse.
