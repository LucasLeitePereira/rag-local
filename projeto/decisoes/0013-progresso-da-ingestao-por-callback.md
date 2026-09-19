# 0013 · Progresso da ingestão por callback injetável, não por `print`

- **Data:** 2026-09-19 · **Status:** Aceita
- **Tarefa:** TASK-051 · **Commit:** `_a preencher_`

## Contexto
A ingestão só falava no fim. Ao adicionar um PDF de 16 MB ao corpus real, a
reingestão passou mais de 18 minutos muda: a única forma de saber em que etapa
ela estava era olhar os horários dos `.md` em `docs-normalizado/` e o uso de
CPU do processo.

A restrição que decide o desenho: no modo stdio do servidor MCP, **nada** pode
ir para o stdout — é por onde trafega o protocolo. A suíte de testes tem a
mesma exigência prática de não poluir a saída.

## Alternativas consideradas
- **`print` direto em `executar_ingestao`** — resolve o `ingest`, mas quebra o
  stdio e polui os testes.
- **`logging`** — configurável e silenciável, mas exige configuração de
  handlers para uma saída que é de interface, não de diagnóstico, e o watcher
  teria de reconstruir o prefixo `docserver:` num formatter.
- **Callback `progresso_fn` que recebe uma linha pronta.**

## Decisão
`executar_ingestao(..., progresso_fn=None)`. Sem a função, a ingestão é
silenciosa (o padrão, e o que o stdio exige). `_comando_ingest` passa um
`print`, desligável com `--silencioso`; o watcher passa o próprio `_log`, que
prefixa com `docserver:`.

O que é informado:

- uma linha por etapa (extração, embeddings, gravação do índice);
- uma linha ao começar e outra ao terminar cada arquivo, numeradas `[3/11]`;
- o avanço dos embeddings a cada 25 chunks (`embeddings 400/1351`).

Duas mudanças de apoio:

- **Duas passadas sobre `docs-fonte`.** A primeira calcula os sha256 e decide o
  que reprocessar; a segunda extrai. Sem isso o denominador do `[3/11]`
  contaria também os arquivos inalterados, que são a maioria numa reingestão.
- **`embed.embeddar_passagens(..., progresso_fn=...)`** divide os textos em
  blocos de 25 para poder informar o avanço. Sem a função, segue mandando tudo
  numa chamada só — o caminho antigo, intocado.

O relatório final ganhou o tempo de cada etapa e o arquivo mais lento, que
mostra na hora se o gargalo é a extração ou os embeddings.

## Consequências
- **Diagnóstico:** no teste real, 43,0 s de extração contra 20,1 s de
  embeddings para um PDF de 266 KB — a extração de PDF é o gargalo, não os
  embeddings, o que muda a prioridade de TASK-004 e TASK-017.
- **Equivalência dos embeddings:** com `progresso_fn`, os textos vão em blocos
  de 25 em vez de todos de uma vez. Com o lote padrão 1 (decisão
  [0002](0002-embeddings-lote-padrao-1.md)) cada texto é codificado sozinho de
  qualquer jeito, então o resultado é idêntico — há teste para isso. Com
  `EMBEDDINGS_TAMANHO_LOTE` maior, o bloco é `max(lote, 25)`, e a diferença
  ficaria no padding dentro do lote.
- **Tempo do primeiro arquivo:** ele paga a carga do tokenizador (12,5 s para
  um `.md` de 1 KB no teste do watcher). "Arquivo mais lento" precisa ser lido
  com isso em mente numa ingestão de poucos arquivos.
