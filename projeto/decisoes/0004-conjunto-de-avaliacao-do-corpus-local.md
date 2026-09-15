# 0004 · Avaliação com conjunto próprio do corpus local, negativas e trecho

- **Data:** 2026-09-15 · **Status:** Aceita
- **Tarefa:** TASK-007, TASK-049 · **Commit:** `933bc39`

## Contexto
O `avaliar` tinha poucas perguntas sobre os documentos de demonstração e só
media se o documento certo aparecia. Mudanças de busca (pesos BM25, reranker)
seriam feitas às cegas.

## Alternativas consideradas
- **Pedir ao usuário que escrevesse as perguntas** — mais fiel ao uso real, mas
  lento.
- **Gerar perguntas automaticamente** — rápido, mas tende a copiar o texto e
  inflar o léxico.
- **O assistente escreve lendo o corpus**, misturando perguntas técnicas
  (termos exatos) e naturais (paráfrases, metade em português sobre documentos
  em inglês). Foi a escolha do usuário.

## Decisão
- **Formato YAML:** `pergunta`, `perfil` (`tecnico`/`natural`), `esperado`
  (`null` para pergunta sem resposta) e `trecho` opcional.
- **Métricas:** hit@1, hit@5, MRR@5, trecho@5, negativas vazias e ms por
  consulta.
- **Flags:** `--validar` confere documentos e trechos contra o índice;
  `--min-hit5` serve de meta para CI.
- **Conjuntos:** `avaliacao/perguntas-corpus-local.yaml` (62 positivas e 11
  negativas) sobre os PDFs locais, além do demo versionado.
- **Linha de base:** registrada antes de mexer na busca.

## Consequências
- **trecho@5:** mostrou que acertar o documento com o chunk errado é comum.
- **Negativas:** mostraram que o corte só esvaziava 27% das perguntas sem
  resposta.
- **Portabilidade:** o conjunto do corpus local depende dos PDFs, que não
  estão no Git; em outra máquina o `--validar` aponta o que falta.
- **Viés:** as perguntas foram escritas por quem conhece o corpus, e o número
  de negativas é pequeno.
