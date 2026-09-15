# 0003 · Busca cai para o léxico com aviso quando a camada vetorial falha

- **Data:** 2026-09-15 · **Status:** Aceita
- **Tarefa:** TASK-002 · **Commit:** `5079369`

## Contexto
Havia dois defeitos:
- **Tabela vetorial vazia:** uma ingestão `--sem-embeddings` só esvaziava as
  linhas de `chunks_vec`, então a busca continuava achando que havia vetores.
- **Falha exposta ao agente:** sem `sentence_transformers`, com modelo
  divergente ou com o sqlite-vec quebrado, a tool `buscar` devolvia uma
  exceção crua.

## Alternativas consideradas
- **Falhar com mensagem clara** — honesto, mas deixa o agente sem resposta
  mesmo com o índice léxico funcionando.
- **Cair para o léxico em silêncio** — o agente não sabe que a qualidade caiu.
- **Cair para o léxico com aviso.**

## Decisão
- **Ingestão sem embeddings:** remove a tabela `chunks_vec` e o modelo
  registrado.
- **Falha na via vetorial:** `buscar_hibrido` captura `ImportError`,
  `ErroModeloDivergente` e erros do sqlite-vec e segue só com o léxico. O motivo
  volta em `avisos`, e a tool e o `docserver search` o mostram antes dos
  resultados.

## Consequências
- A busca nunca quebra por causa da camada vetorial.
- O mesmo mecanismo de aviso foi reaproveitado para o reranker indisponível
  ([0010](0010-reranker-mminilm-padrao.md)).
