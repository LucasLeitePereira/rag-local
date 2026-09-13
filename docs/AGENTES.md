# Conectando um agente de IA

Por padrão o `docserver` fala [MCP](https://modelcontextprotocol.io) via
**stdio**: o cliente sobe o processo `docserver serve` diretamente, sem
porta nem rede. Isso significa que o cliente precisa rodar na mesma máquina
(ou container) onde `docs-fonte/`, `docs-normalizado/` e `data/indice.db`
existem — e também que não existe um link para "abrir" ou compartilhar: o
processo só fala pelos streams padrão de entrada/saída de quem o subiu.

Se você precisa de um link (para um cliente MCP remoto, para testar com
`curl`/[MCP Inspector](https://github.com/modelcontextprotocol/inspector),
ou para servir mais de um cliente ao mesmo tempo), suba com `--http`:

```bash
docserver --indice /caminho/absoluto/data/indice.db \
  --docs-normalizado /caminho/absoluto/docs-normalizado \
  serve --http --host 127.0.0.1 --porta 8765
```

O endpoint fica em `http://127.0.0.1:8765/mcp`. Por padrão o bind é em
`127.0.0.1` (só a própria máquina acessa) — mude `--host` para `0.0.0.0`
apenas se precisar expor para a rede, e nesse caso considere colocar atrás
de um proxy com autenticação, já que o `docserver` não implementa nenhuma
(ver "Fase futura" em `docs/ARQUITETURA.md`). Use `--http` só quando
precisar de fato de rede; para o caso comum (um cliente MCP local) stdio
continua mais simples e não exige gerenciar porta nem processo em segundo
plano.

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

## Conectando de outra máquina na rede

Os exemplos acima sobem o servidor via stdio, na mesma máquina do cliente.
Para consumir de outro PC (mesma rede local), suba com `--http --host
0.0.0.0` na máquina que tem `docs-fonte/`, `docs-normalizado/` e
`data/indice.db`:

```bash
docserver --indice /caminho/absoluto/data/indice.db \
  --docs-normalizado /caminho/absoluto/docs-normalizado \
  serve --http --host 0.0.0.0 --porta 8765
```

`--host 0.0.0.0` é o que aceita conexões de outras máquinas — com o padrão
(`127.0.0.1`) só o próprio PC acessa, mesmo com a porta liberada no
firewall.

1. **Descubra o IP dessa máquina na rede** (Windows: `ipconfig`; Linux/macOS:
   `ip addr` ou `ifconfig`) — algo como `192.168.x.x`.
2. **Libere a porta no firewall**, como administrador. No Windows:
   ```powershell
   New-NetFirewallRule -DisplayName "docserver MCP (8765)" -Direction Inbound `
     -Protocol TCP -LocalPort 8765 -Action Allow -Profile Private
   ```
   `-Profile Private` restringe a liberação a redes marcadas como
   privadas (doméstica/trabalho) no Windows — não libera em redes públicas.
3. **No outro PC**, teste que a rede enxerga antes de configurar o cliente:
   ```bash
   curl http://192.168.x.x:8765/mcp
   ```
4. **Configure o cliente com a URL** em vez de um comando local:

   VS Code / Copilot (`.vscode/mcp.json`):
   ```json
   {
     "servers": {
       "docserver": {
         "type": "http",
         "url": "http://192.168.x.x:8765/mcp"
       }
     }
   }
   ```

   Claude Code:
   ```bash
   claude mcp add --transport http docserver http://192.168.x.x:8765/mcp
   ```

   Claude Desktop: hoje servidor remoto se adiciona pela UI (Settings →
   Connectors), não editando `claude_desktop_config.json` diretamente.

**Sem autenticação nenhuma** — qualquer dispositivo que alcance
`IP:porta` nessa rede consegue ler e buscar toda a documentação indexada.
Aceitável numa rede doméstica ou de escritório confiável; nunca exponha isso
direto na internet (nada de port-forward no roteador) sem colocar atrás de
um proxy com autenticação antes (ver "Fase futura" em
`docs/ARQUITETURA.md`). Se a máquina usa IP dinâmico (DHCP), o endereço pode
mudar a cada reinício — configure IP fixo se isso incomodar.

## As três ferramentas (tools)

| Tool | Quando o agente deve chamar |
|---|---|
| `listar_documentos()` | Não sabe o que existe na documentação, ou uma busca não retornou nada útil. |
| `buscar(consulta, limite=5, documento=None)` | Antes de responder qualquer pergunta sobre o projeto — sempre, em vez de responder de memória. |
| `ler_documento(caminho)` | O trecho de `buscar` não trouxe contexto suficiente. |

Todas retornam **texto legível**, nunca JSON cru — pensado para ser lido
diretamente pelo agente e citado ao usuário, sempre com o caminho de origem.

**`documento`** restringe a busca a um único arquivo (caminho completo, parcial
ou só o nome) — use quando já se sabe, por `listar_documentos` ou por uma
busca anterior, qual documento tem a resposta. Evita que trechos de *outros*
documentos indexados se misturem no resultado só porque bateram bem no termo
buscado; é a defesa direta contra o índice ter mais de um documento com
vocabulário parecido (dois PDFs institucionais, por exemplo).

`buscar` também aplica um corte mínimo de relevância antes de devolver
resultados: um trecho só entra na resposta se a similaridade vetorial da
consulta com ele for alta o bastante, ou se ele casou de fato na busca por
termo exato (BM25) com algum termo relevante da pergunta. Uma resposta vazia
é intencional — significa que
nada no índice passou nesse corte — e não deve ser preenchida com uma
resposta "de memória"; oriente o usuário a reformular a pergunta, restringir
por `documento`, ou confirmar se o assunto está mesmo na documentação
indexada.

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
