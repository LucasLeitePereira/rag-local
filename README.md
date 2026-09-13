# docserver

Servidor de documentação para agentes de IA: centraliza os documentos de um
projeto (Markdown, Word, PDF, planilhas, ...) e os expõe por **busca híbrida
(BM25 + vetorial)** a qualquer cliente MCP (Claude, Copilot, Cursor), além de
deixar tudo legível como Markdown normalizado para humanos.

Esta é a base do projeto, não o produto final — veja
[`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) para as decisões e o que fica
para uma fase futura.

## Quickstart

### 1. Criar e ativar o ambiente virtual

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 2. Instalar o projeto

```bash
pip install -e ".[embeddings,dev]"
```

Sem a extra `embeddings` (`pip install -e .`), a busca funciona em modo
léxico puro (BM25) — mais rápido de instalar, sem baixar
`sentence-transformers`/`torch`. Veja [`docs/DEPLOY.md`](docs/DEPLOY.md) para
a alternativa via Docker.

### 3. Adicionar seus documentos

```bash
cp seus-documentos/* docs-fonte/            # em qualquer estrutura de pastas, tanto faz
```

Formatos suportados: `.md`, `.txt`, `.docx`, `.pptx`, `.xlsx`, `.html`,
`.pdf`, `.csv` — detalhes em [`docs/INGESTAO.md`](docs/INGESTAO.md).

### 4. Ingerir e indexar

```bash
docserver ingest
```

Extrai cada arquivo, normaliza em Markdown (`docs-normalizado/`) e indexa
para busca léxica + vetorial. Rode de novo sempre que adicionar, editar ou
remover arquivos em `docs-fonte/`.

### 5. Validar a busca pelo terminal

```bash
docserver search "sua pergunta"
docserver stats                             # confere quantos chunks foram indexados
```

### 6. Subir o servidor MCP

```bash
docserver serve
```

Isso sobe o servidor via stdio — não é para rodar solto no terminal e deixar
aberto, é o comando que o **cliente MCP** (Claude Desktop, Claude Code,
Cursor, VS Code) invoca sozinho quando você o configura apontando para
`docserver serve`. Veja [`docs/AGENTES.md`](docs/AGENTES.md) para o passo a
passo de configuração de cada cliente.

## Documentação

- [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) — decisões de design e o porquê de cada uma
- [`docs/INGESTAO.md`](docs/INGESTAO.md) — como adicionar documentos e formatos suportados
- [`docs/AGENTES.md`](docs/AGENTES.md) — como conectar um cliente MCP
- [`docs/DEPLOY.md`](docs/DEPLOY.md) — rodar local, Docker, Codespaces, roteiro de demonstração
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) — problemas comuns e como resolvê-los

## Desenvolvimento

```bash
pytest              # suíte rápida (~20s, sem carregar o modelo real)
pytest -m lento      # inclui os testes que carregam o modelo de embeddings
```

Este projeto foi construído por TDD — veja o histórico do Git para a ordem
em que cada comportamento foi implementado.
