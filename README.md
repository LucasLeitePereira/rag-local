# docserver

Servidor de documentação para agentes de IA: centraliza os documentos de um
projeto (Markdown, Word, PDF, planilhas, ...) e os expõe por **busca híbrida
(BM25 + vetorial)** a qualquer cliente MCP (Claude, Copilot, Cursor), além de
deixar tudo legível como Markdown normalizado para humanos.

Esta é a base do projeto, não o produto final — veja
[`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) para as decisões e o que fica
para uma fase futura.

- [Requisitos mínimos](#requisitos-mínimos)
- [Instalação para pessoas](#instalação-para-pessoas) — passo a passo no Windows ou Linux
- [Instalação para agentes de IA](#instalação-para-agentes-de-ia) — instruções para um agente instalar sozinho
- [Documentação](#documentação)
- [Desenvolvimento](#desenvolvimento)

## Requisitos mínimos

| | Só busca léxica (BM25) | Busca híbrida (BM25 + vetorial) |
|---|---|---|
| Sistema operacional | Windows 10/11, Linux (x86_64 ou ARM64) ou macOS | igual |
| Python | 3.11 ou superior | igual |
| CPU | 2 núcleos | 2 núcleos (4 recomendado para ingerir muitos PDFs) |
| RAM | 2 GB | 4 GB (8 GB recomendado) |
| Disco livre | ~500 MB + seus documentos | ~2,5 GB + seus documentos |
| GPU | não usa | não precisa — roda em CPU |
| Internet | só durante a instalação | instalação + primeiro `ingest` (baixa o modelo, ~470 MB) |

O disco extra da busca híbrida vem do PyTorch (versão CPU) e do modelo de
embeddings `intfloat/multilingual-e5-small`. Os valores são estimativas —
PDFs grandes aumentam o uso de memória durante a ingestão.

Também é preciso um **cliente MCP** para usar o servidor com uma IA (Claude
Code, Claude Desktop, VS Code com Copilot, Cursor, ...). Sem ele, a busca
funciona pelo terminal (`docserver search`).

## Instalação para pessoas

Os comandos devem ser rodados **na ordem**, a partir da pasta do projeto.

### Windows (PowerShell)

**1. Instale o Python 3.11+ e o Git**, se ainda não tiver:

```powershell
winget install Python.Python.3.12
winget install Git.Git
```

Feche e reabra o terminal depois de instalar, e confira:

```powershell
py --version        # deve mostrar 3.11 ou superior
git --version
```

**2. Baixe o projeto:**

```powershell
git clone https://github.com/LucasLeitePereira/rag-local.git
cd rag-local
```

**3. Crie e ative o ambiente virtual:**

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
```

Se aparecer erro de "execução de scripts desabilitada", libere uma vez para o
seu usuário e tente ativar de novo:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**4. Instale o projeto:**

```powershell
python -m pip install --upgrade pip
pip install -e ".[embeddings]" --extra-index-url https://download.pytorch.org/whl/cpu
```

Para instalar só a busca léxica (bem mais leve, sem PyTorch):
`pip install -e .`

**5. Coloque seus documentos em `docs-fonte\`** (pode usar subpastas):

```powershell
Copy-Item -Recurse C:\caminho\dos\seus\documentos\* docs-fonte\
```

Formatos suportados: `.md`, `.txt`, `.docx`, `.pptx`, `.xlsx`, `.html`,
`.pdf`, `.csv` — detalhes em [`docs/INGESTAO.md`](docs/INGESTAO.md).

**6. Ingira e indexe:**

```powershell
docserver ingest
```

Se instalou só a busca léxica, use `docserver ingest --sem-embeddings`.

O relatório final deve mostrar `Falhas de extração: 0`. Rode de novo sempre
que adicionar, editar ou remover arquivos em `docs-fonte\`. O aviso sobre
`HF_TOKEN` pode ser ignorado.

**7. Teste a busca pelo terminal:**

```powershell
docserver stats
docserver search "sua pergunta"
```

**8. Anote o caminho absoluto do projeto** — ele vai na configuração do MCP:

```powershell
(Get-Location).Path          # ex.: D:\projetos\rag-local
```

Siga para [Configurar o MCP na sua IA](#configurar-o-mcp-na-sua-ia).

### Linux (Debian/Ubuntu)

**1. Instale o Python 3.11+, o venv e o Git:**

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
python3 --version    # deve mostrar 3.11 ou superior
```

Em Fedora: `sudo dnf install -y python3 python3-pip git`. Se a versão da sua
distribuição for menor que 3.11, instale uma mais nova (ex.: `pyenv` ou o
PPA `deadsnakes` no Ubuntu).

**2. Baixe o projeto:**

```bash
git clone https://github.com/LucasLeitePereira/rag-local.git
cd rag-local
```

**3. Crie e ative o ambiente virtual:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**4. Instale o projeto:**

```bash
python -m pip install --upgrade pip
pip install -e ".[embeddings]" --extra-index-url https://download.pytorch.org/whl/cpu
```

O `--extra-index-url` é importante no Linux: sem ele, o pip baixa o PyTorch
com CUDA (vários GB a mais) mesmo sem GPU. Para instalar só a busca léxica:
`pip install -e .`

**5. Coloque seus documentos em `docs-fonte/`:**

```bash
cp -r /caminho/dos/seus/documentos/* docs-fonte/
```

**6. Ingira e indexe:**

```bash
docserver ingest
```

Se instalou só a busca léxica, use `docserver ingest --sem-embeddings`. Se
aparecer `ImportError: libGL.so.1`, instale `sudo apt install -y libgl1` e
rode de novo.

**7. Teste a busca pelo terminal:**

```bash
docserver stats
docserver search "sua pergunta"
```

**8. Anote o caminho absoluto do projeto:**

```bash
pwd                          # ex.: /home/voce/rag-local
```

### Configurar o MCP na sua IA

O cliente MCP inicia o `docserver serve` sozinho — **não** deixe esse comando
rodando num terminal. Duas regras valem para todos os clientes:

1. **Use caminhos absolutos** para o executável, para `docs-normalizado` e
   para `data/indice.db`. O cliente inicia o processo numa pasta qualquer, e
   com caminhos relativos o servidor não encontra o índice.
2. **As opções vêm antes de `serve`.**

Nos exemplos, troque `CAMINHO` pelo caminho anotado no passo 8.

| | Executável | Separador |
|---|---|---|
| Windows | `CAMINHO\.venv\Scripts\docserver.exe` | `\` (em JSON, escreva `\\`) |
| Linux/macOS | `CAMINHO/.venv/bin/docserver` | `/` |

#### Claude Code

Windows:

```powershell
claude mcp add docserver --scope user -- CAMINHO\.venv\Scripts\docserver.exe --docs-normalizado CAMINHO\docs-normalizado --indice CAMINHO\data\indice.db serve
```

Linux:

```bash
claude mcp add docserver --scope user -- CAMINHO/.venv/bin/docserver --docs-normalizado CAMINHO/docs-normalizado --indice CAMINHO/data/indice.db serve
```

Confira com `claude mcp list` no terminal, ou `/mcp` dentro do Claude Code.
Sem `--scope user`, o servidor fica disponível só na pasta atual.

#### Claude Desktop

Abra *Settings → Developer → Edit Config* (ou edite
`%APPDATA%\Claude\claude_desktop_config.json` no Windows,
`~/Library/Application Support/Claude/claude_desktop_config.json` no macOS) e
adicione:

```json
{
  "mcpServers": {
    "docserver": {
      "command": "D:\\projetos\\rag-local\\.venv\\Scripts\\docserver.exe",
      "args": [
        "--docs-normalizado", "D:\\projetos\\rag-local\\docs-normalizado",
        "--indice", "D:\\projetos\\rag-local\\data\\indice.db",
        "serve"
      ]
    }
  }
}
```

Feche o Claude Desktop por completo (inclusive da bandeja do sistema) e abra
de novo.

#### VS Code (GitHub Copilot)

Crie `.vscode/mcp.json` no workspace (ou rode *MCP: Add Server* na paleta de
comandos):

```json
{
  "servers": {
    "docserver": {
      "type": "stdio",
      "command": "/home/voce/rag-local/.venv/bin/docserver",
      "args": [
        "--docs-normalizado", "/home/voce/rag-local/docs-normalizado",
        "--indice", "/home/voce/rag-local/data/indice.db",
        "serve"
      ]
    }
  }
}
```

Use o Copilot Chat no modo **Agent** para que ele possa chamar as ferramentas.

#### Cursor

Crie `.cursor/mcp.json` no projeto, ou `~/.cursor/mcp.json` para todos os
projetos, com o mesmo bloco do Claude Desktop (chave `mcpServers`). Depois
confira em *Settings → MCP* se o servidor aparece ativo.

#### Outros clientes

Qualquer cliente compatível com MCP via **stdio** funciona: configure o
comando como o executável do venv e os argumentos
`--docs-normalizado <abs> --indice <abs> serve`. Mais detalhes e um exemplo
de `CLAUDE.md` em [`docs/AGENTES.md`](docs/AGENTES.md).

#### Testando

Pergunte à IA algo que só está nos seus documentos. Ela deve chamar a
ferramenta `buscar` e citar o arquivo de origem na resposta. Se não aparecer
nada, veja [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

## Instalação para agentes de IA

> **Para a pessoa:** cole no seu agente (Claude Code, Cursor, Copilot Agent,
> ...) o prompt abaixo, aberto numa pasta onde ele possa trabalhar:
>
> ```text
> Instale localmente o docserver seguindo a seção "Instalação para agentes de IA"
> do README em https://github.com/LucasLeitePereira/rag-local e depois configure
> o MCP no cliente que você é. Meus documentos estão em: <caminho ou "ainda não tenho">.
> ```

**Agente: siga as etapas abaixo em ordem.** Cada etapa tem uma verificação;
não avance se ela falhar — corrija ou pare e relate o erro exato ao usuário.

### Regras

- Não peça confirmação para os comandos desta seção: eles só criam arquivos
  dentro da pasta do projeto e instalam pacotes num venv local. **Peça
  confirmação** antes de instalar software no sistema (Python, Git, pacotes
  `apt`/`winget`) ou de alterar a configuração do cliente MCP do usuário.
- Descubra o sistema operacional antes de começar e use os comandos
  correspondentes. Chame o venv sempre pelo caminho explícito do executável
  (tabela abaixo) — não dependa de `activate`, porque o estado do shell pode
  não persistir entre os seus comandos.
- Não rode `docserver serve` diretamente: ele fica aguardando entrada via
  stdio e trava o seu terminal. Quem o inicia é o cliente MCP.
- Nunca use caminhos relativos na configuração do MCP.

| Variável | Windows | Linux/macOS |
|---|---|---|
| `PY` (sistema) | `py -3` | `python3` |
| `VENV_PY` | `<RAIZ>\.venv\Scripts\python.exe` | `<RAIZ>/.venv/bin/python` |
| `DOCSERVER` | `<RAIZ>\.venv\Scripts\docserver.exe` | `<RAIZ>/.venv/bin/docserver` |

`<RAIZ>` é o caminho **absoluto** da pasta do repositório clonado.

### Etapa 1 — pré-requisitos

Rode `PY --version` e `git --version`.

- **Verificação:** Python ≥ 3.11 e Git presentes.
- Se faltar algo: peça autorização ao usuário e instale (Windows:
  `winget install Python.Python.3.12` / `winget install Git.Git`; Debian/Ubuntu:
  `sudo apt install -y python3 python3-venv python3-pip git`).
- Confira os [requisitos mínimos](#requisitos-mínimos). Se houver menos de
  4 GB de RAM ou 2,5 GB de disco livre, instale sem embeddings (etapa 3,
  variante léxica) e avise o usuário.

### Etapa 2 — clonar e criar o venv

```text
git clone https://github.com/LucasLeitePereira/rag-local.git
cd rag-local
PY -m venv .venv
```

Se você já está dentro de um clone deste repositório (existe `pyproject.toml`
com `name = "docserver"`), não clone de novo — use a pasta atual.

- **Verificação:** o arquivo `VENV_PY` existe. Guarde `<RAIZ>` (Windows:
  `(Get-Location).Path`; Linux: `pwd`).

### Etapa 3 — instalar

```text
VENV_PY -m pip install --upgrade pip
VENV_PY -m pip install -e ".[embeddings]" --extra-index-url https://download.pytorch.org/whl/cpu
```

Variante léxica (máquina fraca ou pedido do usuário): `VENV_PY -m pip install -e .`

A instalação com embeddings pode levar vários minutos; use um timeout longo.

- **Verificação:** `DOCSERVER --help` lista os subcomandos `ingest`, `search`,
  `avaliar`, `serve` e `stats`.

### Etapa 4 — documentos

Se o usuário informou uma pasta de documentos, copie o conteúdo dela para
`<RAIZ>/docs-fonte/` (preservando subpastas). Se não informou, mantenha os
documentos de exemplo que já vêm no repositório e avise que ele pode
adicionar os dele depois.

- **Verificação:** `docs-fonte/` contém ao menos um arquivo `.md`, `.txt`,
  `.docx`, `.pptx`, `.xlsx`, `.html`, `.pdf` ou `.csv`.

### Etapa 5 — ingestão

Rode a partir de `<RAIZ>`:

```text
DOCSERVER ingest
```

Na instalação léxica, use `DOCSERVER ingest --sem-embeddings`. Na primeira
execução com embeddings, o modelo (~470 MB) é baixado — use timeout longo.
Avisos sobre `HF_TOKEN` e barras de progresso `Loading weights` são normais.

- **Verificação:** a saída termina com `Ingestão concluída` e
  `Chunks indexados` maior que 0. Se `Falhas de extração` for maior que 0,
  informe ao usuário quais arquivos falharam, mas continue.
- `ImportError: libGL.so.1` no Linux: com autorização, `sudo apt install -y libgl1`
  e repita a etapa.

### Etapa 6 — validar a busca

```text
DOCSERVER stats
DOCSERVER search "<um termo que aparece nos documentos>"
```

- **Verificação:** `search` retorna ao menos um resultado com caminho de
  origem em `docs-fonte/`.

### Etapa 7 — configurar o MCP

Identifique em qual cliente você está rodando e, **com autorização do
usuário**, registre o servidor com estes valores (substitua `<RAIZ>`):

- comando: `DOCSERVER` (caminho absoluto)
- argumentos, nesta ordem: `--docs-normalizado`, `<RAIZ>/docs-normalizado`,
  `--indice`, `<RAIZ>/data/indice.db`, `serve`
- transporte: `stdio`
- nome do servidor: `docserver`

Como registrar em cada cliente:

| Cliente | Onde |
|---|---|
| Claude Code | `claude mcp add docserver --scope user -- DOCSERVER --docs-normalizado <RAIZ>/docs-normalizado --indice <RAIZ>/data/indice.db serve` |
| Claude Desktop | chave `mcpServers` em `claude_desktop_config.json` |
| VS Code / Copilot | chave `servers` em `.vscode/mcp.json`, com `"type": "stdio"` |
| Cursor | chave `mcpServers` em `.cursor/mcp.json` ou `~/.cursor/mcp.json` |

Os blocos JSON completos estão em
[Configurar o MCP na sua IA](#configurar-o-mcp-na-sua-ia). Em JSON no
Windows, escape as barras invertidas (`\\`). Edite o arquivo existente
mesclando a chave nova — não sobrescreva outros servidores já configurados.
Se não conseguir identificar o cliente, mostre ao usuário os valores acima e
peça que ele configure.

- **Verificação:** Claude Code → `claude mcp list` mostra `docserver` como
  conectado. Nos demais, peça ao usuário que reinicie o cliente e confirme
  que as ferramentas `buscar`, `listar_documentos` e `ler_documento`
  aparecem.

### Etapa 8 — relatório final

Informe ao usuário:

1. `<RAIZ>` e o modo instalado (híbrido ou só léxico);
2. o resumo do `ingest` (arquivos, chunks, falhas);
3. onde o MCP foi configurado e se precisa reiniciar o cliente;
4. que, ao mudar os documentos, basta rodar `DOCSERVER ingest` de novo.

## Documentação

- [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) — decisões de design e o porquê de cada uma
- [`docs/INGESTAO.md`](docs/INGESTAO.md) — como adicionar documentos e formatos suportados
- [`docs/AGENTES.md`](docs/AGENTES.md) — como conectar um cliente MCP
- [`docs/DEPLOY.md`](docs/DEPLOY.md) — rodar local, Docker, Codespaces, roteiro de demonstração
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) — problemas comuns e como resolvê-los

## Desenvolvimento

```bash
pip install -e ".[embeddings,dev]" --extra-index-url https://download.pytorch.org/whl/cpu
pytest              # suíte rápida (~20s, sem carregar o modelo real)
pytest -m lento      # inclui os testes que carregam o modelo de embeddings
```

Este projeto foi construído por TDD — veja o histórico do Git para a ordem
em que cada comportamento foi implementado.
