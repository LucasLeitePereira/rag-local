# Decisões

| Nº | Decisão | Data | Status | Tarefa |
|---|---|---|---|---|
| [0001](0001-indice-em-modo-wal.md) | Índice SQLite em modo WAL com timeout de 30 s | 2026-09-15 | Aceita | TASK-003 |
| [0002](0002-embeddings-lote-padrao-1.md) | Embeddings em lote com tamanho padrão 1 | 2026-09-15 | Aceita | TASK-004 |
| [0003](0003-fallback-lexico-com-aviso.md) | Busca cai para o léxico com aviso quando a camada vetorial falha | 2026-09-15 | Aceita | TASK-002 |
| [0004](0004-conjunto-de-avaliacao-do-corpus-local.md) | Avaliação com conjunto próprio do corpus local, negativas e trecho | 2026-09-15 | Aceita | TASK-007 |
| [0005](0005-pesos-bm25-e-versao-do-esquema.md) | Pesos BM25 por coluna, caminhos fora do FTS e esquema versionado | 2026-09-15 | Aceita | TASK-008 |
| [0006](0006-pagina-por-marcador-e-pdf-sem-ocr.md) | Página de PDF por marcador no Markdown; extração sem OCR | 2026-09-15 | Aceita | TASK-006, TASK-012 |
| [0007](0007-ingestao-incremental-por-sha256.md) | Ingestão incremental por sha256 numa transação única | 2026-09-15 | Aceita | TASK-005 |
| [0008](0008-watcher-filtra-eventos-por-stat.md) | Watcher ignora `modified` sem mudança de tamanho ou mtime | 2026-09-15 | Aceita | — |
| [0009](0009-leitura-em-partes-e-ler-trecho.md) | `ler_documento` em partes e por seção; nova tool `ler_trecho` | 2026-09-15 | Aceita | TASK-001 |
| [0010](0010-reranker-mminilm-padrao.md) | Reranker mMiniLM ligado por padrão, `RERANK_MINIMO` 0.01 | 2026-09-15 | Aceita | TASK-009 |
| [0011](0011-troca-atomica-por-pasta-temporaria.md) | `docs-normalizado` trocado por pasta temporária, depois do commit do índice | 2026-09-19 | Aceita | TASK-013 |
| [0012](0012-lock-de-arquivo-para-uma-ingestao-por-vez.md) | Lock de arquivo do SO para uma ingestão por vez | 2026-09-19 | Aceita | TASK-016 |
| [0013](0013-progresso-da-ingestao-por-callback.md) | Progresso da ingestão por callback injetável | 2026-09-19 | Aceita | TASK-051 |

Decisões anteriores a 2026-09-15 (SQLite único com FTS5 + sqlite-vec, fusão
RRF, stdio antes de HTTP, modelo local `multilingual-e5-small`, chunks por
tokens reais) estão descritas em `docs/ARQUITETURA.md` e ainda não têm
registro próprio aqui.

## Modelo

```markdown
# NNNN · Título da decisão

- **Data:** AAAA-MM-DD · **Status:** Proposta | Aceita | Substituída por NNNN
- **Tarefa:** TASK-NNN · **Commit:** `abc1234`

## Contexto
O problema e as restrições, com números se houver.

## Alternativas consideradas
- **A** — prós / contras.
- **B** — prós / contras.

## Decisão
O que foi escolhido, em uma ou duas frases.

## Consequências
O que fica melhor, o que fica pior, o que precisa ser vigiado.
```
