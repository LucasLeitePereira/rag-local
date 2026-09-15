# 0002 · Embeddings em lote com tamanho padrão 1

- **Data:** 2026-09-15 · **Status:** Aceita
- **Tarefa:** TASK-004 · **Commit:** `124a2da`

## Contexto
A ingestão calculava um embedding por chamada. A expectativa (registrada na
TASK-004) era que `encode` em lote fosse de 5 a 20 vezes mais rápido em CPU.

## Alternativas consideradas
- **Lote fixo de 32** — o valor típico para GPU.
- **Lote configurável, padrão escolhido por medição.**

## Decisão
`embed.embeddar_passagens` aceita vários chunks numa chamada, com tamanho de
lote em `EMBEDDINGS_TAMANHO_LOTE`. A medição em CPU com chunks reais (~400
tokens) mostrou lotes maiores que 1 **mais lentos** que a chamada individual,
então o padrão ficou 1.

## Consequências
- A reingestão completa do corpus local continua em ~36 min (quase todo o
  tempo em embeddings); o ganho real de tempo veio da ingestão incremental
  ([0007](0007-ingestao-incremental-por-sha256.md)).
- Em GPU ou com chunks curtos, vale medir de novo e aumentar o lote.
- Os números exatos da medição não foram guardados; se a questão voltar,
  registre-os em `testes/`.
