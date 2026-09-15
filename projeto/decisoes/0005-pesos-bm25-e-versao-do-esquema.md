# 0005 · Pesos BM25 por coluna, caminhos fora do FTS e esquema versionado

- **Data:** 2026-09-15 · **Status:** Aceita
- **Tarefa:** TASK-008 · **Commit:** `78cbd4c`

## Contexto
Os caminhos eram colunas indexadas do FTS5 com o mesmo peso do texto:
- **Pasta no caminho:** "api" na pasta `api/` fazia todos os chunks do arquivo
  pontuarem para "api".
- **Nome do arquivo:** "Data Engineering" no nome do PDF inflava o livro
  inteiro.

Mudar colunas do FTS exige recriar a tabela, e não havia como detectar um
índice de formato antigo.

## Alternativas consideradas
- **Tirar os caminhos da tabela** — perde o filtro por documento.
- **Caminhos `UNINDEXED` + pesos por coluna** — filtro preservado.
- **Para índice antigo:** exigir `--limpar` manual, ou reconstruir sozinho na
  próxima ingestão.

## Decisão
- **Caminhos:** `UNINDEXED`.
- **Pesos BM25:** `secao` 2, `titulo_doc` 1, `texto` 1, ajustáveis por
  `PESOS_BM25` sem reindexar.
- **Versão do esquema:** fica em `metadados_indice.versao_esquema`. Índice
  antigo é reconstruído na próxima `docserver ingest`; até lá, as tools
  orientam a rodá-la.

## Consequências
- O trecho@5 técnico do híbrido subiu de 88% para 94%, sem mexer no resto.
- Toda mudança de colunas depois disso (TASK-006 → v3, TASK-005 → v4) só
  incrementa a versão.
- Os pesos não foram retocados depois do reranker
  ([0010](0010-reranker-mminilm-padrao.md)).
