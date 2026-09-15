# 0007 · Ingestão incremental por sha256 numa transação única

- **Data:** 2026-09-15 · **Status:** Aceita (substitui a decisão original de reindexar tudo)
- **Tarefa:** TASK-005 · **Commit:** `a8b7737`

## Contexto
Toda ingestão reprocessava o corpus inteiro: ~35 min para 11 documentos
(~6 mil chunks) com embeddings em CPU. O `docserver watch` repetia isso a
cada arquivo copiado.

## Alternativas consideradas
- **Detectar mudança por `mtime`** — barato, mas a cópia no Windows preserva o
  `mtime`, e restaurar um backup antigo não o avança.
- **sha256 de todo arquivo a cada ingestão** — dezenas de ms para um PDF de
  16 MB; mais robusto.
- **Troca de modelo de embeddings:** manter o erro `ErroModeloDivergente`
  exigindo `--limpar`, ou reconstruir sozinho.

## Decisão
- **Registro:** a tabela `arquivos` (esquema v4) guarda sha256, tamanho,
  chunks, extrator e data.
- **O que é reprocessado:** só arquivos novos ou alterados são extraídos e
  embeddados. Os que sumiram, ou passaram a falhar, saem do índice.
- **Reconstrução automática:** acontece com índice antigo, modelo trocado ou
  chunks sem vetor.
- **Gravação:** um único `BEGIN IMMEDIATE` com rollback; `.md` órfãos só são
  apagados depois do commit.

## Consequências
- **Tempo:** a reingestão sem mudanças caiu de 36,5 min para 2,4 s (medido,
  ver `testes/2026-09-15-reingestao-corpus-real.md`).
- **Falha no meio:** não deixa índice parcial. A reingestão interrompida em
  2026-09-15 deixou o índice v1 intacto.
- **Reconstrução completa:** continua levando o tempo cheio; parar a
  ingestão no meio perde todo o trabalho feito.
