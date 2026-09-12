# PLAN.md — Servidor de Documentação para Agentes (RAG local via MCP)

> Documento de especificação para implementação. Leia por inteiro antes de começar a codar.

---

## 1. Objetivo

Construir um sistema que centraliza a documentação de um projeto e a expõe de duas formas:

- **Para agentes de IA** (Claude, Copilot, Cursor) através de um servidor **MCP**.
- **Para pessoas**, através dos arquivos Markdown normalizados, legíveis diretamente.

O usuário joga arquivos numa pasta (`docs-fonte/`), roda um comando de ingestão, e a partir daí qualquer agente conectado ao servidor MCP consegue buscar e ler essa documentação.

**Esta é a base do projeto, não o produto final.** Priorize simplicidade, poucas dependências e código legível sobre completude de funcionalidades.

---

## 2. Princípios de design (respeite estes)

1. **Busca híbrida: BM25 + vetorial.** O público é misto — pessoas técnicas buscam por termo exato (nome de variável, endpoint, tabela), pessoas de negócio buscam por linguagem natural com vocabulário diferente do documento. Nenhuma das duas técnicas cobre os dois casos sozinha. A implementação é faseada (ver seção 5.6): BM25 funcionando e validado primeiro, camada vetorial depois, fusão por último.
2. **Uma dependência a menos é melhor que uma funcionalidade a mais.** Prefira a biblioteca padrão do Python quando ela resolver.
3. **Etapas intermediárias visíveis.** O Markdown normalizado fica em disco para inspeção humana. Nada de pipeline caixa-preta.
4. **Reindexação completa, não incremental.** Com centenas de arquivos leva segundos. Incremental é otimização prematura aqui.
5. **Tudo roda local.** Sem chamadas de rede, sem API key, sem serviço externo. O LLM é o cliente, não faz parte deste sistema.
6. **Docker desde o início**, para rodar igual na máquina do dev e numa VM/Codespace.
7. **TDD, sem exceção.** Nenhuma linha de código de produção é escrita antes de um teste que falhe e justifique essa linha. **Leia a seção 10 antes de começar a implementar.**

---

## 3. Stack

| Camada | Tecnologia | Motivo |
|---|---|---|
| Linguagem | Python 3.11+ | ecossistema de extração de documentos |
| Servidor MCP | `fastmcp` | implementação MCP mais direta em Python |
| Índice léxico | SQLite + FTS5 (stdlib `sqlite3`) | zero serviço para subir, BM25 embutido |
| Índice vetorial | `sqlite-vec` | extensão do MESMO SQLite — sem segundo banco, sem serviço extra |
| Embeddings | `sentence-transformers` + `intfloat/multilingual-e5-small` | ~470 MB, roda em CPU, bom em português |
| Extração | `markitdown` | cobre docx, pptx, xlsx, pdf, html numa dependência só |
| Extração PDF (opcional) | `pymupdf4llm` | fallback quando o markitdown sair ruim em PDF |
| CLI | `argparse` (stdlib) | não instale Typer/Click para 3 comandos |
| Gerenciador | `uv` (ou `pip` + `requirements.txt`) | sua escolha; documente a que usar |
| Testes | `pytest` | único dev-dependency obrigatório |
| Container | Docker + docker-compose | portabilidade para VM/Codespace |

**Não use:** LangChain, LlamaIndex, Chroma, Qdrant, FAISS, Postgres, Redis, Ollama. A camada vetorial é `sqlite-vec` dentro do mesmo arquivo SQLite — não introduza um segundo banco nem um serviço separado. Não use modelo de embeddings via API: ele roda local, sem rede.

---

## 4. Estrutura de diretórios

```
.
├── docs-fonte/              # ENTRADA MANUAL — o usuário larga arquivos aqui
│   └── .gitkeep
├── docs-normalizado/        # GERADO — tudo convertido para .md
│   └── .gitkeep
├── data/
│   └── indice.db            # GERADO — índice SQLite FTS5
├── src/
│   └── docserver/
│       ├── __init__.py
│       ├── cli.py           # ponto de entrada: ingest, search, stats, serve
│       ├── extract.py       # arquivo original -> Markdown
│       ├── chunk.py         # Markdown -> lista de chunks
│       ├── index.py         # chunks -> SQLite FTS5 + funções de busca
│       └── server.py        # servidor MCP (as tools)
├── tests/
│   ├── fixtures/            # arquivos de exemplo (md, docx, pdf pequenos)
│   └── test_*.py
├── docs/                    # documentação DESTE sistema (ver seção 9)
│   ├── ARQUITETURA.md
│   ├── INGESTAO.md
│   ├── AGENTES.md
│   ├── DEPLOY.md
│   └── TROUBLESHOOTING.md
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .gitignore
├── pyproject.toml
└── README.md
```

`docs-normalizado/` e `data/` entram no `.gitignore` (são gerados). `docs-fonte/` é versionado, mas com `.gitkeep` — o conteúdo real depende do projeto.

---

## 5. Pipeline de ingestão

Comando: `docserver ingest`

### 5.1 Varredura

Percorre `docs-fonte/` recursivamente. Ignora arquivos ocultos, `~$*` (temporários do Office) e extensões não suportadas (registra um aviso, não quebra).

### 5.2 Extração (`extract.py`)

Dicionário de extensão → função extratora. Cada extratora recebe um `Path` e devolve uma string Markdown.

| Extensão | Estratégia |
|---|---|
| `.md`, `.markdown`, `.txt` | cópia direta, sem conversão |
| `.docx`, `.pptx`, `.xlsx`, `.html` | `markitdown` |
| `.pdf` | `markitdown`; se o resultado tiver menos de ~200 caracteres, tenta `pymupdf4llm` e registra o fallback |
| `.csv` | ler e renderizar como tabela Markdown |
| outros | pular com aviso |

Regras:
- A arquitetura precisa ser **plugável**: adicionar um formato novo é adicionar uma função e uma entrada no dicionário, nada mais.
- Falha na extração de um arquivo **não derruba a ingestão**. Registre o erro, some ao relatório final e siga.
- Se a extração devolver texto vazio ou quase vazio, marque o arquivo como suspeito no relatório (provável PDF escaneado sem OCR).

### 5.3 Normalização

Grava o resultado em `docs-normalizado/`, espelhando a estrutura de pastas de `docs-fonte/` e trocando a extensão por `.md`.

No topo de cada arquivo gerado, escreva um front matter YAML:

```yaml
---
origem: docs-fonte/contratos/api-v2.pdf
extrator: markitdown
ingerido_em: 2026-09-12T10:30:00
---
```

Arquivos que já eram `.md` na origem: copie preservando o front matter que já existir e acrescente os campos acima se faltarem.

### 5.4 Chunking (`chunk.py`)

Para cada `.md` normalizado:

1. **Se o arquivo tiver cabeçalhos `##`**: quebre por seção. Cada seção vira um chunk, carregando junto o título `#` do documento.
2. **Se não tiver cabeçalhos** (comum em PDF convertido): caia para blocos de aproximadamente 800 tokens com ~100 de sobreposição, quebrando preferencialmente em fim de parágrafo.
3. Seções muito grandes (> ~1500 tokens) são subdivididas pela regra 2, mantendo o nome da seção.
4. Seções vazias ou com menos de ~30 caracteres são descartadas.

Para contagem de tokens, uma aproximação por caracteres (`len(texto) / 4`) é suficiente. Não instale `tiktoken` para isso.

Cada chunk carrega:

```python
{
  "caminho_origem":      "docs-fonte/contratos/api-v2.pdf",   # nome que as pessoas conhecem
  "caminho_normalizado": "docs-normalizado/contratos/api-v2.md",
  "titulo_doc":          "Contrato de API v2",
  "secao":               "Limites de requisição",
  "texto":               "...",
  "ordem":               3
}
```

O `caminho_origem` é obrigatório em todo retorno de busca — é o que o agente cita para o usuário.

### 5.5 Indexação léxica (`index.py`)

```sql
CREATE VIRTUAL TABLE chunks USING fts5(
    caminho_origem,
    caminho_normalizado,
    titulo_doc,
    secao,
    texto,
    ordem UNINDEXED,
    tokenize = "unicode61 remove_diacritics 2"
);
```

O `remove_diacritics 2` importa: a documentação está em português, e sem isso "configuração" e "configuracao" não casam.

Reindexação: apaga a tabela e reconstrói do zero. A busca usa `bm25()` para ordenar e `snippet()` para destacar o trecho relevante.

### 5.6 Indexação vetorial e busca híbrida (`embed.py` + `index.py`)

**Implemente esta subseção somente depois que a busca BM25 estiver funcionando, testada e validada com documentos reais.** Ver seção 13.

#### Embeddings

Modelo: `intfloat/multilingual-e5-small` via `sentence-transformers`, rodando em CPU.

Atenção ao detalhe que mais causa resultado ruim com essa família de modelos: **ela exige prefixos**. Texto indexado leva `passage: ` na frente; texto de consulta leva `query: `. Sem isso a qualidade cai visivelmente. Encapsule isso em `embed.py` para que o resto do código não precise saber.

O texto embeddado de cada chunk não é só o corpo — concatene título do documento, seção e corpo:

```
passage: Contrato de API v2 — Limites de requisição — O cliente pode fazer até...
```

Isso dá contexto ao vetor e melhora muito a recuperação de chunks curtos.

#### Armazenamento

`sqlite-vec`, no **mesmo arquivo** `indice.db`:

```sql
CREATE VIRTUAL TABLE chunks_vec USING vec0(
    chunk_id INTEGER PRIMARY KEY,
    embedding FLOAT[384]
);
```

384 é a dimensão do `multilingual-e5-small`. Guarde a dimensão e o nome do modelo numa tabela de metadados e valide na abertura do índice — se o modelo mudou, o índice precisa ser reconstruído, e o sistema deve avisar isso claramente em vez de devolver resultado errado em silêncio.

#### Fusão dos resultados (RRF)

Rode as duas buscas em paralelo, pegando os ~20 melhores de cada, e funda com **Reciprocal Rank Fusion**:

```
score(doc) = Σ  peso_da_lista / (k + posição_na_lista)
```

com `k = 60`. Use RRF, não soma ponderada de scores — BM25 e similaridade de cosseno vivem em escalas diferentes e normalizá-las é uma fonte constante de bugs. RRF só usa a posição, então o problema desaparece.

Pesos iniciais: 1.0 para ambas as listas. Deixe configuráveis por variável de ambiente (`PESO_LEXICO`, `PESO_VETORIAL`) para permitir ajuste sem mexer no código durante a validação.

#### Degradação graciosa

Se o índice vetorial não existir (ingestão rodada sem embeddings, ou modelo indisponível), a busca **cai para BM25 puro e avisa no log**. O sistema nunca fica inutilizável por causa da camada vetorial.

Ofereça `docserver ingest --sem-embeddings` para uma ingestão rápida durante o desenvolvimento.

### 5.7 Relatório

Ao fim, imprima um resumo legível:

```
Ingestão concluída em 4.2s

  Arquivos processados:   38
  Chunks indexados:      412
  Ignorados (formato):     3
  Falhas de extração:      1
  Suspeitos (texto vazio): 2

Falhas:
  ✗ docs-fonte/antigo/manual.doc — formato .doc não suportado (converta para .docx)

Suspeitos (provável PDF escaneado, sem texto extraível):
  ? docs-fonte/legado/fluxo-2019.pdf
  ? docs-fonte/legado/ata-reuniao.pdf
```

---

## 6. Servidor MCP (`server.py`)

Transporte **stdio** nesta fase (o cliente inicia o processo). HTTP é fase futura.

Exponha exatamente três tools. **As descrições abaixo são parte da especificação — elas são o prompt que faz o agente usar a ferramenta na hora certa. Não as encurte.**

### `listar_documentos()`

> Lista toda a documentação disponível deste projeto, em árvore, com o título e as seções de cada documento. Use esta ferramenta primeiro quando não souber o que existe na documentação, ou quando a busca por termos não retornar nada útil. Barata de chamar — prefira listar e ler o documento certo a fazer várias buscas às cegas.

Retorno: árvore em texto, com caminho de origem, título e as seções de cada documento.

### `buscar(consulta: str, limite: int = 5)`

> Busca na documentação técnica deste projeto e retorna os trechos mais relevantes, cada um com o arquivo de origem e a seção. Use SEMPRE antes de responder qualquer pergunta sobre este projeto — arquitetura, endpoints, variáveis de ambiente, decisões de projeto, processos internos — em vez de responder de memória. A busca é híbrida: funciona tanto com termos técnicos exatos (nomes de função, tabela, variável) quanto com perguntas em linguagem natural. Se a primeira busca não trouxer o que você precisa, tente reformular com o outro estilo — uma pergunta natural se você buscou por termo exato, ou o termo técnico provável se você buscou por descrição. Se o trecho retornado não for suficiente, chame `ler_documento` com o caminho indicado para ver o documento inteiro.

Retorno em texto legível, nunca JSON cru:

```
[1] docs-fonte/arquitetura/autenticacao.md › Renovação de token
O refresh token tem validade de 30 dias e é rotacionado a cada uso...

[2] docs-fonte/guias/ambiente-local.md › Variáveis de ambiente
AUTH_TOKEN_TTL define o tempo de vida do access token em segundos...
```

Se não houver resultado, devolva uma mensagem que oriente o próximo passo: sugerir termos alternativos e sugerir `listar_documentos`.

### `ler_documento(caminho: str)`

> Devolve o conteúdo completo de um documento da documentação do projeto. Use depois de `buscar` ou `listar_documentos`, quando o trecho retornado não trouxer contexto suficiente. Aceita tanto o caminho de origem quanto o normalizado.

Precisa aceitar caminho parcial ou aproximado (por exemplo só `autenticacao.md`) e resolver para o arquivo certo; se houver ambiguidade, liste as opções em vez de escolher sozinho.

**Segurança:** valide que o caminho resolvido está dentro de `docs-normalizado/`. Nada de path traversal.

---

## 7. CLI

```
docserver ingest                    # roda o pipeline completo de ingestão
docserver ingest --limpar           # apaga docs-normalizado/ e o índice antes
docserver ingest --sem-embeddings   # ingestão rápida, só índice léxico
docserver search "termo"            # busca híbrida pelo terminal
docserver search "termo" --modo lexico|vetorial|hibrido   # para comparar as três
docserver avaliar perguntas.yaml    # roda o conjunto de avaliação (ver 7.1)
docserver stats                     # documentos, chunks, modelo, data da ingestão
docserver serve                     # sobe o servidor MCP em stdio
```

O `search` pelo terminal é importante: permite validar a qualidade da busca sem depender de nenhum cliente de IA configurado. O `--modo` é o que torna visível se a camada vetorial está agregando ou atrapalhando.

### 7.1 Conjunto de avaliação

Crie `avaliacao/perguntas.yaml` com o formato:

```yaml
- pergunta: "o que acontece quando o cliente não paga"
  esperado: docs-fonte/processos/inadimplencia.md
  perfil: natural
- pergunta: "AUTH_TOKEN_TTL"
  esperado: docs-fonte/guias/ambiente-local.md
  perfil: tecnico
```

`docserver avaliar` roda cada pergunta nos três modos e imprime uma tabela de acerto (o documento esperado apareceu no top-5?), quebrada por perfil:

```
             léxico   vetorial   híbrido
técnico       9/10      5/10      10/10
natural       3/10      8/10       9/10
geral        12/20     13/20      19/20
```

Essa tabela é a evidência de que a busca híbrida vale a complexidade — e é exatamente o que mostrar numa demonstração. Comece com 15–20 perguntas, metade de cada perfil.

---

## 8. Docker

### Dockerfile

- Base `python:3.11-slim`.
- Build em múltiplos estágios se ajudar no tamanho, mas priorize simplicidade.
- Instale só as dependências de runtime.
- **Baixe o modelo de embeddings durante o build**, não no primeiro uso. Uma linha `RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"` deixa o modelo dentro da imagem. Sem isso, o container precisa de rede na primeira execução — péssimo numa demonstração.
- Defina `HF_HUB_OFFLINE=1` no runtime para garantir que nada tenta baixar nada em produção.
- A imagem vai ficar em torno de 1,5–2 GB por causa do PyTorch. Isso é esperado. Se ficar inviável para o ambiente de demo, o `Dockerfile` deve permitir build sem a camada vetorial via `ARG COM_EMBEDDINGS=true`.
- `WORKDIR /app`, código em `/app/src`.
- Usuário não-root.
- `CMD` padrão: `docserver serve`.

### docker-compose.yml

Um serviço só, com bind mounts para os três diretórios que precisam persistir e ser editáveis de fora:

```yaml
services:
  docserver:
    build: .
    volumes:
      - ./docs-fonte:/app/docs-fonte
      - ./docs-normalizado:/app/docs-normalizado
      - ./data:/app/data
    stdin_open: true
    tty: true
```

Precisa funcionar este fluxo:

```bash
docker compose build
docker compose run --rm docserver docserver ingest
docker compose run --rm docserver docserver search "autenticação"
```

Documente no `DEPLOY.md` que, com transporte stdio, o cliente MCP roda o container via `docker compose run`. E registre a limitação conhecida: **stdio dentro de container tem atrito em alguns clientes** — o transporte HTTP resolve isso e está na fase futura.

### Codespaces

Inclua um `.devcontainer/devcontainer.json` mínimo apontando para o Dockerfile, para o projeto abrir pronto num GitHub Codespace.

---

## 9. Documentação a ser escrita

Esta parte é entregável, não opcional. O objetivo é que uma pessoa que nunca viu o projeto consiga rodá-lo e entender as decisões.

### `README.md`
O que é, o problema que resolve, quickstart em até 5 comandos, link para os demais documentos. Curto.

### `docs/ARQUITETURA.md`
As decisões e o porquê de cada uma: por que SQLite FTS5 e não banco vetorial; por que normalizar tudo para Markdown; por que reindexação completa; por que stdio primeiro. Inclua um diagrama Mermaid do fluxo (ingestão e consulta). Inclua uma seção **"Fase futura"** listando, sem implementar: busca híbrida com embeddings, transporte HTTP com OAuth, permissão por documento, reindexação automática via CI.

### `docs/INGESTAO.md`
Como adicionar documentos, formatos suportados, o que fazer quando a extração sair ruim, como ler o relatório de ingestão, como adicionar um extrator novo (com exemplo de código).

### `docs/AGENTES.md`
Como conectar um cliente MCP. Exemplos de configuração para Claude Desktop, Claude Code, VS Code/Copilot e Cursor — deixe claro que os caminhos dos arquivos de configuração devem ser conferidos na documentação de cada cliente, porque mudam. Explique as três tools, o formato de retorno, e inclua um `CLAUDE.md` de exemplo instruindo o agente a consultar a documentação antes de responder.

### `docs/DEPLOY.md`
Rodar local, rodar via Docker, rodar em Codespaces/VM. Inclua um roteiro de demonstração passo a passo (útil para apresentar a terceiros).

### `docs/TROUBLESHOOTING.md`
Os problemas previsíveis, com diagnóstico e solução: busca não encontra nada; PDF virou texto embaralhado; PDF escaneado sem texto; agente ignora as ferramentas e responde de memória; container não enxerga os arquivos.

---

## 10. TDD — como este projeto deve ser construído

**Este projeto é desenvolvido por TDD. Isso não é uma preferência de estilo, é parte da especificação.**

### 10.1 O ciclo

Para cada comportamento, nesta ordem, sem pular etapa:

1. **Vermelho** — escreva um teste que descreva o comportamento desejado. Rode e confirme que ele falha, e que falha **pelo motivo certo** (não por erro de import ou de sintaxe).
2. **Verde** — escreva a menor quantidade de código de produção que faça o teste passar. Feio é aceitável aqui. Não antecipe o próximo teste.
3. **Refatorar** — limpe o código com os testes passando. Se algum quebrar, o refactor está errado, não o teste.

Repita. Um comportamento por ciclo.

### 10.2 Regras

- **Nunca escreva código de produção sem um teste vermelho que o exija.** Se você se pegar escrevendo uma função "porque vai precisar", pare e escreva o teste antes.
- **Um teste por comportamento**, não por função. O nome do teste descreve o comportamento em português: `test_chunk_divide_por_cabecalho_de_nivel_2`, `test_busca_ignora_acentuacao`, `test_ler_documento_rejeita_path_traversal`.
- **Não teste implementação.** Teste a interface pública de cada módulo. Se um refactor interno quebra o teste sem mudar comportamento, o teste está errado.
- **Testes rápidos.** A suíte inteira roda em segundos. Nos testes de `embed.py` e `test_hibrido.py`, use um embedder falso (função determinística que devolve vetores fixos por texto) para a lógica de fusão e de armazenamento. Reserve o modelo real para um punhado de testes marcados `@pytest.mark.lento`, excluídos da execução padrão.
- **Commit a cada ciclo verde-refactor**, com a mensagem descrevendo o comportamento adicionado. O histórico do Git deve contar a ordem em que o sistema foi construído.
- **Bug encontrado = teste antes da correção.** Reproduza o bug num teste que falha, depois corrija.

### 10.3 Fixtures

Em `tests/fixtures/`, geradas programaticamente no `conftest.py` sempre que possível (evita binários no repositório):

- `com_cabecalhos.md` — três seções `##` com conteúdo distinto
- `sem_cabecalhos.md` — texto corrido longo, para exercitar o fallback de chunking
- `secao_gigante.md` — uma seção acima do limite, para exercitar a subdivisão
- `exemplo.docx` e `exemplo.pdf` — pequenos, gerados no setup
- `vazio.pdf` — sem texto extraível, simulando PDF escaneado
- `corrompido.docx` — bytes inválidos com extensão válida

Fixtures compartilhadas de `tmp_path` para as pastas `docs-fonte/`, `docs-normalizado/` e para um índice SQLite em memória.

### 10.4 A lista de testes, na ordem de escrita

Escreva nesta ordem. Cada item é um ciclo vermelho-verde-refactor.

**`test_extract.py`**
- `.md` é copiado sem alteração de conteúdo
- `.txt` é tratado como Markdown
- `.docx` produz Markdown com os cabeçalhos preservados
- `.csv` vira tabela Markdown
- extensão desconhecida retorna `None` e não levanta exceção
- arquivo corrompido registra erro e não derruba o processo
- PDF sem texto extraível é marcado como suspeito
- front matter de origem é escrito no arquivo normalizado
- registrar um extrator novo no dicionário passa a fazê-lo ser usado

**`test_chunk.py`**
- documento com `##` é dividido em um chunk por seção
- cada chunk carrega o título `#` do documento
- documento sem cabeçalho cai para blocos por tamanho
- blocos do fallback têm sobreposição entre si
- seção acima do limite é subdividida mantendo o nome da seção
- seção com menos de 30 caracteres é descartada
- a ordem original das seções é preservada no campo `ordem`
- `caminho_origem` aponta para o arquivo original, não para o normalizado

**`test_index.py`**
- chunk indexado é recuperável por um termo do seu texto
- busca por "configuracao" encontra "configuração" (e vice-versa)
- resultado mais relevante vem primeiro
- busca sem resultado retorna lista vazia, não erro
- reindexar não duplica chunks
- `limite` restringe a quantidade de resultados
- termo com aspas ou caractere especial não quebra a query FTS

**`test_embed.py`**
- texto de passagem recebe o prefixo `passage: `
- texto de consulta recebe o prefixo `query: `
- o texto embeddado concatena título, seção e corpo
- o vetor retornado tem a dimensão esperada do modelo
- o modelo é carregado uma única vez (não a cada chamada)

**`test_hibrido.py`**
- chunk recuperável por termo exato aparece no resultado híbrido
- chunk com vocabulário diferente da consulta é recuperado pela via vetorial
- RRF: documento bem posicionado nas duas listas fica acima de um que só aparece numa
- RRF usa posição, não score — alterar a escala dos scores não muda a ordem final
- `PESO_VETORIAL=0` reproduz exatamente o resultado da busca léxica pura
- índice vetorial ausente faz a busca cair para BM25 e registrar aviso, sem erro
- modelo divergente do registrado nos metadados gera erro explícito na abertura do índice

**`test_server.py`**
- `buscar` retorna texto formatado com caminho de origem e seção
- `buscar` sem resultado retorna mensagem orientando o próximo passo
- `listar_documentos` retorna a árvore com títulos e seções
- `ler_documento` aceita caminho parcial e resolve para o arquivo certo
- `ler_documento` com caminho ambíguo lista as opções em vez de escolher
- `ler_documento` rejeita `../` e caminho fora de `docs-normalizado/`
- `ler_documento` com caminho inexistente retorna mensagem útil, não stack trace

**`test_pipeline.py`** (integração, por último)
- ingestão ponta a ponta: três formatos em `docs-fonte/` → busca encontra conteúdo dos três
- arquivo problemático no meio do lote não impede os demais de serem indexados
- relatório final traz as contagens corretas

### 10.5 Meta de cobertura

Não persiga percentual. A meta é que **todo comportamento descrito na seção 10.4 tenha um teste**, e que os critérios da seção 11 sejam verificáveis rodando `pytest`. Código gerado sem teste correspondente é código a remover, não a cobrir depois.

---

## 11. Critérios de aceitação

O projeto está pronto quando tudo abaixo for verdade:

- [ ] Largar um `.md`, um `.docx` e um `.pdf` em `docs-fonte/`, rodar `docserver ingest`, e os três aparecerem em `docs-normalizado/` como Markdown legível.
- [ ] O relatório de ingestão mostra contagens e lista falhas e suspeitos.
- [ ] `docserver search "termo"` devolve trechos relevantes com arquivo de origem e seção.
- [ ] Busca com e sem acento devolve o mesmo resultado.
- [ ] Uma consulta em linguagem natural, com vocabulário diferente do documento, encontra o documento certo.
- [ ] Uma consulta por identificador técnico exato encontra o documento certo.
- [ ] `docserver avaliar` roda e imprime a tabela comparativa dos três modos.
- [ ] Com o índice vetorial ausente, a busca continua funcionando em modo léxico.
- [ ] Um cliente MCP conectado consegue chamar as três tools e responder uma pergunta citando o arquivo de origem.
- [ ] `docker compose build` e `docker compose run --rm docserver docserver ingest` funcionam do zero.
- [ ] Um arquivo com extensão não suportada não derruba a ingestão.
- [ ] Os cinco documentos da seção 9 existem e estão preenchidos.
- [ ] `pytest` passa, e todo comportamento listado na seção 10.4 tem um teste correspondente.
- [ ] O histórico do Git mostra testes sendo commitados junto ou antes do código que os satisfaz.

---

## 12. Fora de escopo (não implemente)

Registre como fase futura no `ARQUITETURA.md`, mas **não construa agora**:

- Reranking com cross-encoder (o próximo upgrade de qualidade, depois do híbrido)
- Expansão de consulta / geração de perguntas sintéticas
- Transporte HTTP, OAuth, autenticação, multiusuário
- Permissão por documento
- Interface web
- Reindexação automática / watcher de arquivos
- OCR para PDF escaneado
- Integração com Confluence, Drive, Notion

---

## 13. Ordem de implementação

Cada etapa abaixo é uma sequência de ciclos vermelho-verde-refactor, seguindo a lista da seção 10.4. **Não existe uma etapa "escrever os testes"** — os testes vêm antes do código em todas elas.

1. **Esqueleto** — `pyproject.toml`, estrutura de pastas, `pytest` rodando com um teste trivial passando, `conftest.py` com as fixtures básicas.
2. **`extract.py`, só `.md` e `.txt`** — o caso mais simples, ponta a ponta.
3. **`chunk.py`** — quebra por cabeçalho primeiro, fallback depois.
4. **`index.py` léxico** — indexação FTS5 e busca BM25.
5. **CLI `ingest` + `search`** — primeiro momento demonstrável.
6. **Conjunto de avaliação + `docserver avaliar`** — escreva as 15–20 perguntas com os documentos reais do projeto. **Pare aqui.** Rode a avaliação em modo léxico e registre o resultado. Esse número é a linha de base contra a qual a camada vetorial será julgada.
7. **`embed.py`** — embeddings com prefixos, isolado e testado com embedder falso.
8. **`index.py` vetorial + fusão RRF** — e rode a avaliação de novo nos três modos. A tabela comparativa é entregável desta etapa.
9. **`server.py`** — as três tools MCP.
10. **Demais extratores** — docx, pdf, xlsx, csv, pptx, um ciclo por formato.
11. **`test_pipeline.py`** — os testes de integração.
12. **Docker + devcontainer.**
13. **Documentação** (seção 9).

A etapa 6 existe para não construir a camada vetorial no escuro: se a avaliação mostrar que o híbrido não melhora o perfil "natural", há um problema no chunking ou nos próprios documentos, e adicionar mais busca não vai resolver.

Commit a cada ciclo verde. Ao fim de cada etapa numerada, a suíte inteira deve estar verde antes de seguir para a próxima.
