# 0010 · Reranker mMiniLM ligado por padrão, `RERANK_MINIMO` 0.01

- **Data:** 2026-09-15 · **Status:** Aceita
- **Tarefa:** TASK-009 · **Commits:** `d736053`, `a23f5b6`

## Contexto
A linha de base mostrou três fraquezas do híbrido:
- **Perfil natural:** abaixo do vetorial puro (83% × 86% de hit@5).
- **Trecho:** o chunk certo muitas vezes fora do top-5.
- **Negativas:** só 27% voltavam vazias.

O usuário pediu suporte a dois modelos e a escolha do padrão pela avaliação.

## Alternativas consideradas
- **`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (mMiniLM)** — multilíngue,
  ~470 MB.
- **`BAAI/bge-reranker-v2-m3` (bge-m3)** — multilíngue, ~2,3 GB, em geral
  mais preciso.
- **Manter desligado.**
- **Para o corte:** 0 (sem corte), 0.01, 0.1 (valor provisório) e outros
  valores entre 0.01 e 0.5.

## Decisão
- **Modelo:** mMiniLM ligado por padrão (env `RERANKER`), repontuando os 20
  primeiros da fusão.
- **Corte:** `RERANK_MINIMO` = 0.01.
- **Memória:** `predict` em lotes de 8 pares.
- **Instalação só léxica:** não liga o reranker por padrão.

Números em `testes/2026-09-15-avaliacao-reranker.md`:
- **mMiniLM, qualidade:** no corpus local, hit@1 foi de 90% a 97%, hit@5 de
  92% a 97% e trecho@5 de 85% a 92%.
- **mMiniLM, custo:** ~3,3 s por busca em CPU.
- **bge-m3:** ~35 s por busca. Estourou a RAM de 8 GB duas vezes: primeiro
  carregado junto com o mMiniLM e o e5; depois sozinho, com lotes de 8 pares,
  após 46 perguntas. Nunca completou o conjunto, então **não há números de
  qualidade dele**.
- **Corte:** acertos reais têm notas de 0,02 a 0,05, e negativas chegam a
  0,12 (0,47 no demo). 0.01 é o maior corte sem perder acerto; 0.1 esvazia
  82% das negativas, mas derruba o hit@5 para 90% (86% no demo).

## Consequências
- **Latência:** cada busca passa de ~70 ms para ~3 s em CPU. `RERANKER=desligado`
  e `search --sem-rerank` são as saídas.
- **Negativas:** continuam o ponto fraco (27% vazias no corpus local).
- **Download:** a primeira busca baixa mais ~470 MB.
- **bge-m3 em GPU:** pode valer medir numa máquina com GPU ou mais RAM.
- **Latência configurável:** `N_CANDIDATOS_RERANK` não é configurável por
  env; repontuar menos candidatos reduziria a latência, sem medição ainda.
