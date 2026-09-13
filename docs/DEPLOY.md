# Deploy

## Local

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[embeddings,dev]"
docserver ingest
docserver serve
```

Sem a extra `embeddings` (`pip install -e .`), a busca funciona em modo
léxico puro — útil para desenvolvimento rápido sem baixar `sentence-transformers`/`torch`.

## Docker

```bash
docker compose build
docker compose run --rm docserver docserver ingest
docker compose run --rm docserver docserver search "sua pergunta"
```

O `docker-compose.yml` faz bind mount de `docs-fonte/`, `docs-normalizado/`
e `data/` — edite os arquivos fonte do lado de fora do container
normalmente, e rode `ingest` de novo dentro dele.

Para uma imagem mais leve, sem a camada vetorial (só BM25):

```bash
docker compose build --build-arg COM_EMBEDDINGS=false
```

**Limitação conhecida:** o transporte MCP usado aqui é stdio, e stdio
dentro de um container tem atrito em alguns clientes MCP (o cliente precisa
saber rodar `docker compose run` como se fosse o comando do servidor, o que
nem todo cliente suporta configurar facilmente). O transporte HTTP resolveria
isso, mas está fora de escopo desta versão (ver `docs/ARQUITETURA.md`). Para
uso com um cliente MCP local, a instalação direta (sem Docker) tende a ser
mais simples; Docker é mais adequado para ingestão/validação em CI ou numa
VM/Codespace compartilhada.

## Codespaces / VM

Este repositório inclui um `.devcontainer/devcontainer.json` mínimo. Ao abrir
o projeto num GitHub Codespace, o ambiente já sobe com o Dockerfile deste
projeto — rode `docserver ingest` e `docserver serve` normalmente de dentro
do Codespace.

Numa VM comum, os passos são os mesmos da seção "Local" acima — só garanta
Python 3.11+ disponível.

## Roteiro de demonstração

1. `docker compose build` (ou `pip install -e ".[embeddings,dev]"` local).
2. `docserver ingest` — mostre o relatório (contagens, sem falhas).
3. `docserver search "um termo técnico exato"` — mostre que o resultado
   vem com arquivo de origem e seção.
4. `docserver search "a mesma pergunta em linguagem natural"` — mostre que
   a busca híbrida encontra o mesmo documento por um caminho diferente.
5. `docserver avaliar avaliacao/perguntas.yaml` — mostre a tabela
   comparativa léxico / vetorial / híbrido.
6. Conecte um cliente MCP (`docs/AGENTES.md`) e faça a mesma pergunta ao
   agente — mostre que ele cita o arquivo de origem em vez de responder de
   memória.
