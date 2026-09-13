# docserver

Servidor de documentação para agentes de IA: centraliza os documentos de um
projeto (Markdown, Word, PDF, planilhas, ...) e os expõe por **busca híbrida
(BM25 + vetorial)** a qualquer cliente MCP (Claude, Copilot, Cursor), além de
deixar tudo legível como Markdown normalizado para humanos.

Esta é a base do projeto, não o produto final — veja
[`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) para as decisões e o que fica
para uma fase futura.

## Quickstart

```bash
pip install -e ".[embeddings,dev]"          # ou: docker compose build
cp seus-documentos/* docs-fonte/            # jogue seus arquivos aqui
docserver ingest                            # extrai, normaliza e indexa
docserver search "sua pergunta"             # valida a busca pelo terminal
docserver serve                             # sobe o servidor MCP (stdio)
```

Aponte seu cliente MCP para `docserver serve` — veja
[`docs/AGENTES.md`](docs/AGENTES.md) para exemplos de configuração.

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
