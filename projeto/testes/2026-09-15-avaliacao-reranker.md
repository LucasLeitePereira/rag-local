# Avaliação dos rerankers e calibração do `RERANK_MINIMO`

- **Data:** 2026-09-15 · **Índice:** v4, 11 documentos, 6 109 chunks, `multilingual-e5-small`
- **Máquina:** Windows 11 Pro, CPU com 4 threads, 7,9 GB de RAM (~3 GB livres com o resto aberto), sem GPU, Python 3.14.
- **Conjuntos:** `avaliacao/perguntas-corpus-local.yaml` (62 positivas + 11 negativas) e `avaliacao/perguntas.yaml` (21 + 4)
- **Decisão resultante:** [`decisoes/0010`](../decisoes/0010-reranker-mminilm-padrao.md)

## 1. Tentativa com os dois modelos juntos: falhou por memória

`docserver avaliar … --rerankers mminilm,bge-m3` pré-carrega o e5, o mMiniLM e o bge-m3 no mesmo processo. O sistema matou o processo por falta de memória antes da primeira linha de resultado.

## 2. `avaliar` com o mMiniLM e `RERANK_MINIMO=0.1` (valor provisório)

Comando: `docserver avaliar avaliacao/perguntas-corpus-local.yaml --rerankers mminilm`

```text
modo             perfil   acertos  hit@1  hit@5  MRR@5  trecho@5  neg vazio  ms/cons
lexico           natural    22/29    72%    76%   0.74       69%        12%        7
lexico           tecnico    33/33   100%   100%   1.00       91%         0%       25
lexico           geral      55/62    87%    89%   0.88       81%         9%       16
vetorial         natural    24/29    83%    83%   0.83       76%         0%       42
vetorial         tecnico    33/33    97%   100%   0.98       88%         0%       87
vetorial         geral      57/62    90%    92%   0.91       82%         0%       64
hibrido          natural    24/29    79%    83%   0.81       76%        25%       67
hibrido          tecnico    33/33   100%   100%   1.00       94%        33%       66
hibrido          geral      57/62    90%    92%   0.91       85%        27%       67
hibrido+mminilm  natural    24/29    83%    83%   0.83       79%        88%     3485
hibrido+mminilm  tecnico    32/33    97%    97%   0.97       88%        67%     3421
hibrido+mminilm  geral      56/62    90%    90%   0.90       84%        82%     3453
```

Comando: `docserver avaliar avaliacao/perguntas.yaml --rerankers mminilm`

```text
modo             perfil   acertos  hit@1  hit@5  MRR@5  trecho@5  neg vazio  ms/cons
lexico           natural    10/10    90%   100%   0.95      100%         0%       44
lexico           tecnico    10/11    82%    91%   0.86       91%        50%       57
lexico           geral      20/21    86%    95%   0.90       95%        25%       51
vetorial         natural    10/10   100%   100%   1.00      100%         0%       44
vetorial         tecnico     7/11    64%    64%   0.64       64%         0%       43
vetorial         geral      17/21    81%    81%   0.81       79%         0%       43
hibrido          natural    10/10   100%   100%   1.00      100%         0%       72
hibrido          tecnico    11/11    82%   100%   0.89      100%         0%       66
hibrido          geral      21/21    90%   100%   0.94      100%         0%       69
hibrido+mminilm  natural     7/10    70%    70%   0.70       75%       100%     2755
hibrido+mminilm  tecnico    11/11    91%   100%   0.95      100%        50%     3058
hibrido+mminilm  geral      18/21    81%    86%   0.83       89%        75%     2913
```

Com o corte 0.1, o reranker esvazia muito mais negativas, mas perde acertos, principalmente nas perguntas naturais do demo (70%). O que perde acertos é o corte, e não a ordenação: veja a seção 3.

## 3. Calibração do corte (mMiniLM)

Para não repetir ~5 min de avaliação a cada limite, o script de coleta rodou cada pergunta uma vez com `RERANK_MINIMO=0` e guardou o top-5 reranqueado com a nota de cada item. As métricas de cada limite vêm de filtrar esse top-5, com as funções `_pontuar_resposta` e `taxas_avaliacao` do `cli`. Como o filtro é monotônico, o resultado é igual ao de rodar a busca com aquele corte. O JSON coletado não está no Git porque contém trechos dos PDFs.

```text
### notas-mminilm
perguntas-corpus-local (ms/cons médio 3293)
limite  perfil   hit@1  hit@5  MRR@5  trecho@5  neg vazio
0.0     natural    93%    93%   0.93       90%         0%
0.0     tecnico   100%   100%   1.00       94%         0%
0.0     geral      97%    97%   0.97       92%         0%
0.01    natural    93%    93%   0.93       90%        38%
0.01    tecnico   100%   100%   1.00       94%         0%
0.01    geral      97%    97%   0.97       92%        27%
0.02    natural    93%    93%   0.93       90%        62%
0.02    tecnico   100%   100%   1.00       91%        33%
0.02    geral      97%    97%   0.97       90%        55%
0.05    natural    90%    90%   0.90       83%        75%
0.05    tecnico    97%    97%   0.97       88%        67%
0.05    geral      94%    94%   0.94       85%        73%
0.1     natural    83%    83%   0.83       79%        88%
0.1     tecnico    97%    97%   0.97       88%        67%
0.1     geral      90%    90%   0.90       84%        82%
0.15    natural    79%    79%   0.79       76%       100%
0.15    tecnico    97%    97%   0.97       88%       100%
0.15    geral      89%    89%   0.89       82%       100%
0.2     natural    79%    79%   0.79       76%       100%
0.2     tecnico    94%    94%   0.94       88%       100%
0.2     geral      87%    87%   0.87       82%       100%
0.3     natural    79%    79%   0.79       76%       100%
0.3     tecnico    91%    91%   0.91       85%       100%
0.3     geral      85%    85%   0.85       81%       100%
0.5     natural    72%    72%   0.72       66%       100%
0.5     tecnico    88%    88%   0.88       82%       100%
0.5     geral      81%    81%   0.81       74%       100%
nota do acerto (positivas): [-1, -1, 0.03, 0.044, 0.078, 0.088, 0.107, 0.176, 0.264, 0.362, 0.377, 0.481, 0.714, 0.773, 0.795, 0.811, 0.827, 0.836, 0.845, 0.912, 0.946, 0.957, 0.966, 0.98, 0.983, 0.983, 0.992, 0.992, 0.992, 0.993, 0.996, 0.996, 0.996, 0.997, 0.997, 0.997, 0.997, 0.998, 0.998, 0.998, 0.999, 0.999, 0.999, 0.999, 0.999, 0.999, 0.999, 0.999, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
nota máxima (negativas):   [0.002, 0.003, 0.009, 0.01, 0.011, 0.014, 0.035, 0.047, 0.07, 0.103, 0.116]
perguntas (ms/cons médio 2996)
limite  perfil   hit@1  hit@5  MRR@5  trecho@5  neg vazio
0.0     natural   100%   100%   1.00      100%         0%
0.0     tecnico    91%   100%   0.95      100%         0%
0.0     geral      95%   100%   0.98      100%         0%
0.01    natural   100%   100%   1.00      100%        50%
0.01    tecnico    91%   100%   0.95      100%        50%
0.01    geral      95%   100%   0.98      100%        50%
0.02    natural    90%    90%   0.90       88%        50%
0.02    tecnico    91%   100%   0.95      100%        50%
0.02    geral      90%    95%   0.93       95%        50%
0.05    natural    70%    70%   0.70       75%       100%
0.05    tecnico    91%   100%   0.95      100%        50%
0.05    geral      81%    86%   0.83       89%        75%
0.1     natural    70%    70%   0.70       75%       100%
0.1     tecnico    91%   100%   0.95      100%        50%
0.1     geral      81%    86%   0.83       89%        75%
0.15    natural    70%    70%   0.70       75%       100%
0.15    tecnico    91%   100%   0.95      100%        50%
0.15    geral      81%    86%   0.83       89%        75%
0.2     natural    70%    70%   0.70       75%       100%
0.2     tecnico    91%   100%   0.95      100%        50%
0.2     geral      81%    86%   0.83       89%        75%
0.3     natural    70%    70%   0.70       75%       100%
0.3     tecnico    91%   100%   0.95      100%        50%
0.3     geral      81%    86%   0.83       89%        75%
0.5     natural    70%    70%   0.70       75%       100%
0.5     tecnico    91%   100%   0.95      100%       100%
0.5     geral      81%    86%   0.83       89%       100%
nota do acerto (positivas): [0.019, 0.033, 0.048, 0.578, 0.616, 0.788, 0.859, 0.881, 0.976, 0.982, 0.984, 0.993, 0.994, 0.997, 0.998, 0.998, 0.999, 1.0, 1.0, 1.0, 1.0]
nota máxima (negativas):   [0.003, 0.009, 0.021, 0.471]
```

As listas finais trazem, para as positivas, a nota do primeiro acerto (-1 = fora do top-5) e, para as negativas, a maior nota devolvida. Há sobreposição: acertos em 0,019 a 0,048 e negativas em 0,07 a 0,116 (0,471 no demo). Nenhum limite separa as duas coisas.

**Escolha: 0.01.** É o maior corte que não perde acerto nos dois conjuntos (0.02 já perde uma pergunta natural do demo).

## 4. bge-m3: interrompido por memória

A coleta com `bge-m3` (lotes de 8 pares) passou por 46 perguntas, com média de **34.7 s por consulta** (mín. 26.7 s, máx. 43.4 s). Em seguida o sistema matou o processo por falta de memória. O JSON só seria gravado no fim, então **não há métricas de qualidade do bge-m3**. Com ~35 s por busca ele é inviável para uso interativo nesta máquina, de qualquer forma.

## 5. Resumo

| conjunto | modo | hit@1 | hit@5 | MRR@5 | trecho@5 | neg vazio | ms/cons |
|---|---|---|---|---|---|---|---|
| corpus local | hibrido | 90% | 92% | 0.91 | 85% | 27% | 67 |
| corpus local | **+mminilm, corte 0.01** | **97%** | **97%** | **0.97** | **92%** | **27%** | ~3 300 |
| demo | hibrido | 90% | 100% | 0.94 | 100% | 0% | 69 |
| demo | **+mminilm, corte 0.01** | **95%** | **100%** | **0.98** | **100%** | **50%** | ~3 000 |

## Como repetir

1. `docserver avaliar <conjunto> --rerankers mminilm` (um modelo por vez em máquinas de 8 GB).
2. Para calibrar, colete o top-5 com `RERANK_MINIMO=0` e `index.buscar_hibrido(..., reranquear_fn=lambda t, itens: rerank.pontuar(t, itens, "mminilm"))`, guarde `caminho_origem`, `texto` e `rerank` de cada resultado, e aplique os limites sobre esse top-5.
