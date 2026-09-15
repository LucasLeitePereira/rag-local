# 0009 · `ler_documento` em partes e por seção; nova tool `ler_trecho`

- **Data:** 2026-09-15 · **Status:** Aceita
- **Tarefa:** TASK-001 · **Commit:** `a8ffaac`

## Contexto
`ler_documento` devolvia o arquivo inteiro. O livro do corpus local tem mais
de 1 milhão de caracteres e estourava o contexto do agente numa chamada só.
Quando um trecho da busca vinha cortado, a única saída era ler o documento
todo.

## Alternativas consideradas
- **Truncar em N caracteres** — o agente perde o resto sem saber como chegar lá.
- **Paginação por partes com a chamada seguinte explícita.**
- **Leitura por seção** — traz exatamente o assunto, se o agente souber o nome.
- **Leitura por vizinhança de chunk** — continua um resultado de busca de
  forma barata.

## Decisão
- **`ler_documento(caminho, parte=1, secao=None)`:**
  - partes de até `LIMITE_CARACTERES_LEITURA` (20 000), cortadas entre
    parágrafos;
  - cabeçalho "parte X de N" e rodapé com a chamada exata da parte seguinte;
  - documento pequeno sai igual a antes;
  - `secao` casa sem acento e sem caixa, inclui as subseções e lista as
    opções quando ambígua ou inexistente.
- **`ler_trecho(chunk, vizinhos=1)`:** devolve o chunk da busca com até 5
  vizinhos de cada lado, com seção e página.

## Consequências
- **Livro:** sai em 52 partes (verificado no índice real).
- **Agente:** precisa seguir o rodapé; as docstrings e o `docs/AGENTES.md`
  orientam isso.
- **Limite em caracteres:** o limite não é em tokens; ≈ 5 000 tokens é uma
  estimativa.
