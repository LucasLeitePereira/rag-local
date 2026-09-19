# 0011 · `docs-normalizado` trocado por pasta temporária, depois do commit do índice

- **Data:** 2026-09-19 · **Status:** Aceita
- **Tarefa:** TASK-013 · **Commit:** `_a preencher_`

## Contexto
A ingestão escrevia cada `.md` normalizado direto em `docs-normalizado/`
durante a extração — ou seja, **antes** dos embeddings, que é a etapa longa
(20 s para 29 chunks, mais de 15 min para um PDF de 16 MB no corpus real).

Duas consequências:

- Matar a ingestão no meio deixava o disco com o texto novo e o índice com os
  chunks antigos, permanentemente dessincronizados até a próxima ingestão.
- Durante os minutos de uma reingestão, `ler_documento` servia o texto novo
  enquanto `buscar` devolvia trechos do texto velho.

A TASK-005 já havia posto a gravação do índice numa transação única
(decisão [0007](0007-ingestao-incremental-por-sha256.md)); faltava o lado do
sistema de arquivos.

## Alternativas consideradas
- **Escrever num arquivo temporário por `.md` e trocar um a um durante a
  extração** — cada arquivo fica atômico, mas o conjunto não: a queda no meio
  continua deixando metade nova e metade velha.
- **Gerar `docs-normalizado` inteiro numa pasta nova e trocar as duas pastas
  com um `os.replace` só** — a troca é de fato única, mas obriga a copiar
  também os arquivos inalterados (o caso comum: 11 de 12 numa reingestão) e
  destrói os `.md` que o usuário deixou na pasta e que a ingestão preserva.
- **Escrever só os arquivos reprocessados numa pasta temporária e movê-los
  depois do commit do índice.**

## Decisão
Os `.md` desta ingestão vão para `.docs-normalizado.tmp-<pid>-<id>/`, pasta
irmã de `docs-normalizado/` (mesmo sistema de arquivos, requisito do
`os.replace`). Depois que `index.atualizar_indice` dá commit, cada arquivo é
movido para o lugar definitivo, e só então os órfãos são removidos. Um
`finally` apaga a pasta temporária em qualquer saída.

A pasta é irmã, e não interna a `docs-normalizado/`, para não aparecer no
`rglob("*.md")` que remove os órfãos.

## Consequências
- **Queda no meio:** disco e índice ficam no estado anterior, verificado com um
  `kill` real durante os embeddings (ver
  [`testes/2026-09-19-ingestao-atomica-e-lock.md`](../testes/2026-09-19-ingestao-atomica-e-lock.md)).
- **Janela remanescente:** a promoção em si não é atômica como conjunto. Se o
  processo morrer entre o commit e o último `os.replace`, alguns `.md` ficam
  novos e outros velhos. A janela caiu de "minutos de embeddings" para
  "milissegundos de move" (0,0 s no corpus real), e a próxima ingestão
  reescreve tudo pelo sha256.
- **Custo:** nenhum arquivo a mais é escrito — os inalterados nunca entram na
  pasta temporária.
- **Resto de `kill -9`:** o `finally` não roda num `kill -9`, então a pasta
  temporária pode sobrar. A ingestão seguinte apaga as que encontrar, já com o
  lock na mão (decisão [0012](0012-lock-de-arquivo-para-uma-ingestao-por-vez.md)),
  o que garante que nenhuma esteja em uso.
