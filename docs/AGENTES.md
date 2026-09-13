# Conectando um agente de IA

O `docserver` fala [MCP](https://modelcontextprotocol.io) via **stdio**: o
cliente sobe o processo `docserver serve` diretamente, sem porta nem rede.
Isso significa que o cliente precisa rodar na mesma máquina (ou container)
onde `docs-fonte/`, `docs-normalizado/` e `data/indice.db` existem.

> Os caminhos exatos dos arquivos de configuração de cada cliente mudam com
> frequência — confira sempre a documentação oficial do cliente que você
> está usando. Os exemplos abaixo mostram o formato do bloco de configuração,
> não necessariamente o arquivo/local mais atual.

> **Sempre passe caminhos absolutos.** O cliente MCP sobe o processo no
> diretório que ele escolher (o Claude Desktop, por exemplo, não usa a pasta
> do projeto e ignora uma chave `cwd`). Sem `--indice` e `--docs-normalizado`
> absolutos, o servidor procura `data/indice.db` e `docs-normalizado/`
> relativos a esse diretório e não encontra nada. As opções globais vêm
> **antes** do subcomando `serve`.

## Claude Desktop

Em `claude_desktop_config.json` (Windows: `%APPDATA%\Claude\`; macOS:
`~/Library/Application Support/Claude/`):

```json
{
  "mcpServers": {
    "docserver": {
      "command": "/caminho/absoluto/para/o/projeto/.venv/bin/docserver",
      "args": [
        "--docs-normalizado", "/caminho/absoluto/para/o/projeto/docs-normalizado",
        "--indice", "/caminho/absoluto/para/o/projeto/data/indice.db",
        "serve"
      ]
    }
  }
}
```

No Windows, o binário do venv é `.venv\Scripts\docserver.exe` (escape as
barras no JSON: `"D:\\projeto\\.venv\\Scripts\\docserver.exe"`). Reinicie o
Claude Desktop depois de editar o arquivo.

## Claude Code

```bash
claude mcp add docserver -- /caminho/absoluto/.venv/bin/docserver   --docs-normalizado /caminho/absoluto/docs-normalizado   --indice /caminho/absoluto/data/indice.db   serve
```

Use o binário do venv: `docserver` só está no `PATH` com o venv ativado, e o
Claude Code não o ativa. Depois, confira com `/mcp` dentro do Claude Code.

## VS Code / GitHub Copilot

No `.vscode/mcp.json` do workspace:

```json
{
  "servers": {
    "docserver": {
      "command": "docserver",
      "args": ["serve"]
    }
  }
}
```

## Cursor

No `.cursor/mcp.json` (ou na configuração global de MCP do Cursor):

```json
{
  "mcpServers": {
    "docserver": {
      "command": "docserver",
      "args": ["serve"]
    }
  }
}
```

## As três ferramentas (tools)

| Tool | Quando o agente deve chamar |
|---|---|
| `listar_documentos()` | Não sabe o que existe na documentação, ou uma busca não retornou nada útil. |
| `buscar(consulta, limite=5)` | Antes de responder qualquer pergunta sobre o projeto — sempre, em vez de responder de memória. |
| `ler_documento(caminho)` | O trecho de `buscar` não trouxe contexto suficiente. |

Todas retornam **texto legível**, nunca JSON cru — pensado para ser lido
diretamente pelo agente e citado ao usuário, sempre com o caminho de origem.

## Exemplo de `CLAUDE.md`

Adicione ao `CLAUDE.md` (ou equivalente) do projeto que está sendo
documentado, para reforçar o hábito de consultar antes de responder:

```markdown
## Documentação do projeto

Este projeto tem um servidor MCP de documentação (`docserver`) conectado.
Antes de responder qualquer pergunta sobre arquitetura, endpoints, variáveis
de ambiente, processos internos ou decisões de projeto, use a ferramenta
`buscar` para consultar a documentação real — não responda de memória.
Se a busca não trouxer nada útil, tente `listar_documentos` para ver o que
existe, ou reformule a consulta (termo técnico exato vs. linguagem natural).
```
