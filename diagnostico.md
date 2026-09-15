# Diagnóstico técnico — docserver (RAG local via MCP)

> Data: 2026-09-14 · Commit analisado: `98c0832` (branch `master`)
> Método: leitura integral de `src/`, `tests/`, configuração e docs; inspeção do índice real (`data/indice.db`); execução da suíte de testes; chamadas ao vivo às três tools do servidor MCP conectado.

---

## 1. Resumo executivo

O projeto tem uma base sólida e bem pensada para o tamanho: pipeline de ingestão plugável (markitdown + pymupdf4llm), chunking por tokens reais com sobreposição, índice único em SQLite (FTS5 + sqlite-vec), fusão híbrida por RRF, validação de modelo divergente, proteção contra path traversal, docstrings de tools orientadas a agentes e 91 testes passando. A documentação é acima da média.

Porém, **como produto para agentes de IA ele ainda não está confiável**. Três achados comprometem o uso real hoje:

1. **`ler_documento` não funciona no servidor em execução** — retorna "Documento não encontrado" para qualquer caminho (confirmado ao vivo). Causa: o índice grava `caminho_normalizado` relativo e com `\`, e o servidor compara com o caminho absoluto resolvido.
2. **O agente nunca vê o chunk inteiro** — `formatar_resultados` corta cada trecho em 300 caracteres, enquanto os chunks têm em média ~1.500 caracteres (livro). Combinado com o item 1, o agente fica sem caminho para obter o contexto.
3. **O filtro de relevância é assimétrico**: qualquer chunk que case *um único termo* no BM25 (query com `OR`) passa, sem corte algum. Na prática, "rate limit da API" devolve 2 acertos corretos e 3 trechos irrelevantes do livro só por conterem "API" (confirmado ao vivo).

Há ainda riscos operacionais sérios (perda de dados por `--docs-fonte` errado, colisão de nomes, primeira consulta levando >120 s) e lacunas de escala (embeddings um a um, reingestão total, `ler_documento` sem paginação para documentos de 1 MB).

### Placar geral

| Dimensão | Nota | Comentário curto |
|---|---|---|
| Arquitetura | 7/10 | Simples, local, coesa. Falta camada de serviço e estado persistente de conexão. |
| Ingestão / extração | 5/10 | Boa escolha de libs; sem OCR, sem páginas, colisões de nome, só UTF-8. |
| Chunking | 6/10 | Tokens reais e hierarquia de fallback; ignora code fences, tabelas e hierarquia de seções. |
| Recuperação (retrieval) | 5/10 | Híbrido + RRF corretos; filtro de relevância falho, sem reranker, pesos BM25 não ajustados. |
| Interface MCP p/ agentes | 3/10 | `ler_documento` quebrado, snippet truncado, sem paginação, sem citação de página. |
| Robustez / operação | 4/10 | Deleções agressivas, reindex não incremental, latência de cold start. |
| Segurança | 6/10 | Path traversal tratado; HTTP sem autenticação. |
| Testes | 6/10 | Boa cobertura unitária; não pegaram o bug de caminho do servidor real. |
| Avaliação de qualidade | 3/10 | 19 perguntas só sobre os docs de exemplo, métrica única (hit@5 por documento). |
| Documentação | 8/10 | Rica; alguns trechos desatualizados (ex.: HTTP "fora de escopo"). |

---

## 2. Visão geral da arquitetura

```
docs-fonte/ ──extract.py──▶ docs-normalizado/*.md (front matter)
                                   │
                              chunk.py (seções H1–H3 → blocos ≤400 tokens, overlap 50)
                                   │
                              embed.py (multilingual-e5-small, 384d, normalizado)
                                   │
                              index.py ──▶ data/indice.db
                                            ├─ chunks      (FTS5, unicode61 remove_diacritics)
                                            ├─ chunks_vec  (vec0, FLOAT[384])
                                            └─ metadados_indice (modelo, dimensão)
                                   │
server.py (FastMCP: listar_documentos · buscar · ler_documento) ◀── agente
cli.py (ingest · search · avaliar · stats · serve [--http])
```

**Estado do índice real inspecionado:** 9 documentos, 964 chunks. O livro *Fundamentals of Data Engineering* gera 795 chunks (82% do índice); o relatório de Niterói (PDF de 32 MB) gera apenas 127 chunks / 110 KB de Markdown — forte indício de páginas-imagem sem texto extraível.

**Ambiente:** venv com Python 3.14, fastmcp 4.0.3, sentence-transformers 6.0.1, transformers 5.17, torch 2.14, sqlite-vec 0.1.9. O `pyproject.toml` declara `requires-python >=3.11` e o Dockerfile usa 3.11 — ou seja, dev e container rodam versões bem diferentes de tudo.

---

## 3. Achados críticos (corrigir antes de qualquer uso real)

> **Status (2026-09-14): C1–C6 resolvidos** (pendente de commit), com testes de regressão em `tests/`.
> - **C1:** índice grava `caminho_normalizado` relativo a `docs-normalizado` em POSIX; `ler_documento` resolve pelo índice (`index.resolver_documento`).
> - **C2:** `server._formatar_resultados_mcp` devolve o chunk inteiro com id, posição e similaridade.
> - **C3 (parcial):** corte por cobertura léxica ponderada por IDF (`COBERTURA_LEXICA_MINIMA`, padrão 0.5), também no fallback BM25; corrigido também o bug em que um item presente nas duas listas perdia a `similaridade` na fusão. No índice real, "rate limit da API" agora traz `api/contratos.md › Limites de requisição` em 1º, mas ainda vêm trechos do livro que contêm "limit" + "API" em outro sentido — o corte léxico não resolve isso; é trabalho para o reranker (Fase 2).
> - **C4:** `ErroIngestao` para fonte inexistente/vazia e para esvaziar índice com conteúdo (`--forcar`); órfãos e `--limpar` só apagam `.md` com `origem:` no front matter; `--limpar` esvazia o índice por DROP em vez de apagar o arquivo.
> - **C5:** nomes normalizados preservam a extensão (`manual.pdf.md`) + detecção de colisão case-insensitive.
> - **C6:** `serve` pré-carrega o modelo (`--sem-aquecimento` desliga), carrega do cache local sem consultar o Hub e mantém uma conexão SQLite por processo. ONNX/fastembed e `mode=ro` ficam para A4/Fase 3.

### C1. `ler_documento` sempre falha no servidor real
- **Onde:** `chunk.py:221` grava `str(caminho_normalizado)` (relativo ao cwd da ingestão, ex.: `docs-normalizado\api\contratos.md`); `server.py:22-24` resolve `docs_normalizado` para absoluto; `server.py:141` filtra com `str(c) in indexados`.
- **Evidência:** no índice, `caminho_normalizado = 'docs-normalizado\\api\\contratos.md'`. Chamadas ao vivo `ler_documento("api/contratos.md")` e `ler_documento("docs-fonte/api/contratos.md")` retornam "Documento não encontrado".
- **Por que os testes não pegaram:** os testes usam `tmp_path` absoluto tanto na ingestão quanto na leitura, então as strings coincidem.
- **Efeito colateral:** o índice também não é portável entre SO (separador `\` gravado no Windows, `/` no container Linux).
- **Correção:** gravar no índice o caminho **relativo a `docs-normalizado` em formato POSIX** (`api/contratos.md`) e resolver contra a base configurada no servidor. Idealmente o índice guarda só `caminho_origem` e o servidor deriva o resto. Adicionar teste que ingere com caminhos relativos e serve com absolutos (e vice-versa).

### C2. Trechos truncados em 300 caracteres
- **Onde:** `cli.py:144` — `r['texto'][:300]`, reutilizado pelo servidor.
- **Efeito:** chunks médios de 840–1.480 caracteres chegam ao agente cortados no meio da frase (visível nos resultados ao vivo: "...there is", "...now suppo"). O corte de 300 faz sentido na CLI, não no MCP. Sem C1 funcionando, o agente não tem como recuperar o restante.
- **Correção:** formatação separada para MCP com o chunk completo (o custo já está limitado a `limite × 400 tokens`), mais metadados úteis: id do chunk, `ordem`, score/similaridade e, se possível, página.

### C3. Filtro de relevância permissivo no lado léxico
- **Onde:** `index.py:195` monta a query com `OR` entre todos os termos; `index.py:324-333` considera relevante **qualquer** item que apareceu na lista léxica.
- **Evidência ao vivo:** `buscar("rate limit da API")` → [1] e [2] corretos; [3], [4], [5] são trechos do livro sobre REST/serialização que só contêm "API".
- **Assimetria:** o lado vetorial exige similaridade ≥ 0.85, o léxico não exige nada. Em corpus grande, termos comuns em inglês/português ("dados", "API", "sistema") contaminam quase toda consulta.
- **Correção (em ordem de custo):**
  1. Exigir cobertura mínima de termos para aceitar resultado só-léxico (ex.: ≥50% dos termos úteis, ou todos quando a consulta tem ≤2 termos), ou usar corte relativo ao melhor BM25.
  2. Descartar do resultado final itens cujo score RRF fique abaixo de uma fração do topo.
  3. Adicionar um **reranker cross-encoder** multilíngue (ex.: `BAAI/bge-reranker-v2-m3` ou equivalente leve) sobre os ~20 candidatos fundidos — é o ganho de qualidade mais consistente para RAG híbrido.

### C4. `--docs-fonte` inexistente apaga tudo silenciosamente
- **Onde:** `cli.py:43` (`rglob` num diretório inexistente devolve lista vazia — verificado), depois `cli.py:67-70` remove todos os `.md` "órfãos" e `index.reindexar` grava um índice vazio.
- **Cenário:** um erro de digitação ou rodar `docserver ingest` a partir do diretório errado zera `docs-normalizado/` e o índice, sem erro.
- **Agravantes:** a remoção de órfãos e o `--limpar` (`shutil.rmtree`) atuam sobre qualquer pasta passada em `--docs-normalizado`, inclusive uma que contenha `.md` que não foram gerados pelo docserver.
- **Correção:** abortar se `docs_fonte` não existir ou não tiver nenhum arquivo suportado; só remover arquivos cujo front matter contenha `origem:` gerado pelo docserver; recusar reindexar para 0 chunks quando o índice anterior não estava vazio, a menos que haja `--forcar`.

### C5. Colisão de nomes na normalização
- **Onde:** `extract.py:170` — `with_suffix(".md")`.
- **Cenário:** `manual.pdf` e `manual.docx` (ou `README.md` e `README.txt`) na mesma pasta geram o mesmo `manual.md`. O segundo sobrescreve o primeiro, mas os chunks do primeiro já foram adicionados; o índice passa a ter duas origens apontando para o mesmo arquivo normalizado, e `ler_documento` devolve o conteúdo errado.
- **Correção:** preservar a extensão original no nome (`manual.pdf.md`) ou detectar colisão e reportar como falha.

### C6. Latência de cold start e bloqueio do servidor
- **Evidência:** a primeira chamada de `buscar` ao vivo levou **mais de 120 s** e foi movida para background pelo cliente; chamadas subsequentes foram rápidas.
- **Causas:** o modelo (torch + sentence-transformers) é carregado preguiçosamente na primeira consulta (`embed.py:17-22`); tools são síncronas e cada chamada abre nova conexão, recarrega a extensão sqlite-vec e revalida metadados. Enquanto o modelo carrega, outras chamadas ficam enfileiradas.
- **Correção:** pré-carregar o modelo (e o tokenizer) no startup do `serve`, antes de aceitar requisições; manter uma conexão SQLite por processo (ou pool, somente leitura com `mode=ro`); considerar ONNX/`optimum` ou `fastembed` para reduzir o tempo de import e memória.

---

## 4. Achados de alta severidade

### A1. `ler_documento` devolve documentos inteiros sem paginação
O livro normalizado tem ~1 MB (~250 mil tokens). Quando C1 for corrigido, uma chamada a `ler_documento` estoura a janela de contexto de praticamente qualquer agente — e a docstring de `buscar` *incentiva* essa chamada. Necessário: parâmetros `secao`, `inicio`/`fim` (por chunk `ordem` ou por caracteres), limite padrão de tamanho com aviso de continuação, e/ou uma tool `ler_trecho(id, vizinhos=1)` que devolva o chunk com os adjacentes (padrão *small-to-big*).

### A2. Busca híbrida quebra ao reingerir `--sem-embeddings` sobre índice existente
`reindexar` apaga as linhas de `chunks_vec`, mas a tabela e `metadados_indice` continuam existindo. `_tabela_vetorial_existe` segue retornando `True`, então `buscar_hibrido` tenta carregar o modelo mesmo sem vetores. Numa instalação sem a extra `embeddings`, isso gera `ImportError` em vez do *fallback* para BM25 anunciado na documentação. Da mesma forma, `ErroModeloDivergente` não é tratado no servidor e vira erro cru para o agente. Correção: dropar `chunks_vec`/metadados quando não há embeddings; checar se há linhas, não só a tabela; capturar `ImportError`/`ErroModeloDivergente` e degradar para léxico com aviso no resultado.

### A3. Ingestão não incremental e embeddings um a um
- `cli.py:80` calcula embeddings com `[calcular(c) for c in todos_chunks]` — uma chamada ao modelo por chunk, sem batch. `SentenceTransformer.encode` com listas e `batch_size=32/64` é tipicamente 5–20× mais rápido em CPU.
- Toda ingestão reextrai todos os PDFs (incluindo o de 32 MB) e reembedda os 964 chunks, mesmo que nada tenha mudado. Além disso `ingerido_em` muda sempre, poluindo diffs.
- Correção: guardar hash (sha256 + mtime) por arquivo de origem; reextrair/reembeddar apenas o que mudou; apagar só os chunks da origem alterada; embeddings em lote.

### A4. Leitura com efeito colateral e reindex não atômico entre processos
- `buscar_vetorial` chama `_validar_ou_registrar_modelo`, que pode **escrever** em `metadados_indice` durante uma consulta.
- `criar_indice` executa `CREATE VIRTUAL TABLE IF NOT EXISTS` em toda tool call.
- A ingestão reescreve `docs-normalizado/` antes de atualizar o índice; se o processo cair durante os embeddings (a etapa mais longa), servidor e disco ficam dessincronizados.
- Correção: abrir o índice em modo somente leitura no servidor; construir o índice novo em arquivo temporário e fazer *swap* atômico (`os.replace`) ao final; habilitar `PRAGMA journal_mode=WAL`.

### A5. Extração de PDF perde informação essencial para RAG
- **Sem números de página:** `pymupdf4llm.to_markdown` é chamado sem `page_chunks=True`, então o agente não consegue citar "p. 123". Para relatórios e livros, isso é o principal requisito de citação.
- **Sem OCR:** o relatório de Niterói (32 MB → 110 KB de texto) sugere muitas páginas como imagem. O heurístico `MIN_CARACTERES_PDF_VALIDO = 200` é absoluto por arquivo, não por página — um PDF com 1 página de texto e 80 escaneadas passa como "válido".
- **Estrutura fraca:** o livro tem 706 cabeçalhos no Markdown, mas só 15 viram seção (H1–H3); o "CHAPTER 6 Storage" saiu como linha comum, então todos os chunks do capítulo 6 ficam atribuídos à seção "CHAPTER 5". Artefatos de extração aparecem nas seções ("Indicadores-chave de An á lise", "Á reas-alvo").
- Correção: extrair por página e gravar `pagina` no chunk; detectar páginas com pouco texto e aplicar OCR (`pymupdf` + Tesseract, ou `docling`); considerar `docling`/`marker` para PDFs estruturados; pós-processar espaços dentro de palavras acentuadas.

### A6. HTTP sem autenticação
`serve --http --host 0.0.0.0` expõe toda a documentação e o índice sem nenhum controle de acesso. O padrão `127.0.0.1` é seguro, mas não há alerta ao usar outro host. Adicionar token (header `Authorization: Bearer`) via middleware/auth do FastMCP, e emitir aviso explícito quando o bind não for loopback.

---

## 5. Achados de média severidade

### Chunking (`chunk.py`)
- **M1. Cabeçalhos dentro de blocos de código** (`# comentário` em bash/Python dentro de ```` ``` ````) são tratados como seções (`_CABECALHO_SECAO`), fragmentando o documento. Ignorar regiões dentro de fences.
- **M2. Tabelas e código são quebrados** por `\n` e reunidos com `\n\n` (`_unidades_atomicas` + `_blocos_por_tamanho`), desfazendo tabelas Markdown e fences. Tratar tabelas/fences como unidades atômicas (ou dividi-las repetindo o cabeçalho da tabela).
- **M3. Sem hierarquia de seção:** um H3 "Visão geral" perde o H1/H2 pai. No relatório de Niterói há "1. Visão geral" em várias partes diferentes, impossíveis de distinguir. Guardar o *breadcrumb* (`H1 › H2 › H3`) em `secao` e usá-lo no texto embeddado.
- **M4. Overlap entre seções inexistente e overlap cortando por palavra** (`_cauda_por_tokens`), o que pode começar o chunk no meio de uma frase. Preferir cauda por frase.
- **M5. Custo quadrático** em `_dividir_por_palavras` e `_cauda_por_tokens` (retokenizam a string acumulada a cada palavra). Aceitável hoje; ruim para textos sem pontuação/quebras (tabelas extraídas de PDF). Tokenizar uma vez e cortar por offsets (`return_offsets_mapping`).
- **M6.** O tokenizer depende de `transformers` presente e do modelo em cache; sem isso cai para `len/3` em silêncio — chunks de tamanhos diferentes conforme o ambiente de ingestão. Logar qual contagem foi usada e gravar nos metadados do índice.

### Recuperação (`index.py`)
- **M7. BM25 sem pesos por coluna:** `bm25(chunks)` pondera igualmente `caminho_origem`, `caminho_normalizado`, `titulo_doc`, `secao` e `texto`. Os caminhos (com palavras como "api", "arquitetura", "Data Engineering") inflam o score de todos os chunks daquele arquivo. Marcar os caminhos como `UNINDEXED` e usar `bm25(chunks, 0,0, 2.0, 3.0, 1.0)` ou similar.
- **M8. Limiar vetorial 0.85 calibrado num único corpus** (comentário em `index.py:42-50`). O e5-small comprime similaridades em 0.7–0.9; um corte absoluto é frágil e muda com o domínio/idioma. Preferir corte relativo (diferença para o top-1), reranker (C3) ou calibrar com o conjunto de avaliação.
- **M9. Stopwords:** lista curta, com duplicatas ("e", "esta", "as"), sem stopwords em inglês — relevante porque o corpus tem um livro em inglês. Sem stemming em português ("pagamento" ≠ "pagar"); o FTS5 não tem stemmer PT nativo, mas é possível pré-processar com um stemmer (ex.: RSLP/Snowball) numa coluna auxiliar.
- **M10. Candidatos fixos em 20** por ramo, independentes de `limite`; `limite` sem validação (valores ≤0 ou muito altos). Normalizar para `1 ≤ limite ≤ 20` e usar `k = max(20, 4×limite)`.
- **M11. Filtro por documento no KNN** faz varredura exata — correto e documentado, mas passa a ser caro com o livro (795 vetores ok; 50 livros não). sqlite-vec suporta *metadata columns*/*partition keys* no `vec0`; usar `caminho_origem` como partition key.
- **M12. Sem deduplicação/diversidade:** o top-5 pode trazer 5 chunks consecutivos do mesmo trecho (overlap de 50 tokens favorece isso). Aplicar MMR ou colapsar chunks adjacentes.

### Extração (`extract.py`)
- **M13. Somente UTF-8** para `.txt`, `.md` e `.csv`; arquivos em cp1252/latin-1 (comuns no Windows/Brasil) viram falha. Usar detecção (`charset-normalizer`, já dependência transitiva) com fallback.
- **M14. CSV sem escape de `|`** e sem limite de linhas — um CSV grande vira uma "tabela" gigante sem cabeçalho repetido nos chunks.
- **M15. `ler_front_matter`** lança `ValueError` se o front matter não fechar, não trata CRLF, e um `.md` de origem que já tenha front matter próprio fica com dois blocos (o original vira texto indexado).
- **M16. `_deve_ignorar`** olha só o nome do arquivo; pastas ocultas (`.git/`, `.obsidian/`) dentro de `docs-fonte` são ingeridas.
- **M17. `origem`** é sempre prefixado com `docs-fonte/`, mesmo quando `--docs-fonte` aponta para outra pasta — caminhos citados ao agente ficam incorretos.
- **M18. Estado global `_ultimo_extrator_pdf`:** frágil (não thread-safe, acoplamento oculto). Fazer o extrator retornar `(texto, nome_extrator)`.

### Servidor MCP (`server.py`)
- **M19. `listar_documentos` sem limite:** hoje devolve ~90 linhas; com dezenas de livros vira milhares. Adicionar paginação, filtro por prefixo e opção de omitir seções.
- **M20. Resultados em texto livre**, sem estrutura. O MCP suporta *structured output*; retornar JSON (origem, seção, página, ordem, id, score, texto) facilita citação e encadeamento pelo agente.
- **M21. Sem resources/prompts MCP:** documentos poderiam ser expostos como `resources` (`doc://api/contratos.md`), deixando o cliente anexá-los diretamente.
- **M22. Sem logging/observabilidade:** nenhuma métrica de latência, consultas vazias ou erros. Log estruturado em stderr (nunca stdout no stdio) com consulta, nº de resultados e tempo ajudaria a calibrar o retrieval com uso real.
- **M23. Docstring de `buscar` muito longa** (~200 palavras), consumida em toda conversa. Enxugar e mover a orientação de fluxo para `instructions` do servidor FastMCP.

### CLI e avaliação
- **M24. Avaliação insuficiente:** 19 perguntas, todas sobre os 6 Markdown de exemplo (nenhuma sobre os PDFs, que são 97% dos chunks); métrica única hit@5 por documento; sem MRR, nDCG, recall por chunk, nem casos negativos (perguntas sem resposta, que testariam o corte de relevância). Os limiares do sistema foram calibrados à mão fora desse conjunto.
- **M25. `formatar_tabela_avaliacao`** tem função `_somar` nunca usada e reserva largura para uma linha "geral" que nunca é impressa.
- **M26. `docserver stats`** promete "data da ingestão" no help, mas não mostra.

---

## 6. Infraestrutura, dependências e empacotamento

- **I1. Dependências sem lock e com versões muito abertas** (`fastmcp>=2.0` instalou 4.0.3; `markitdown>=0.0.1a2` instalou beta 0.1.8b1; `transformers` 5.x). Major versions quebram API sem aviso. Adicionar `uv.lock`/`requirements.lock` e limites superiores de major.
- **I2. Python divergente:** venv em 3.14, Docker em 3.11, CI inexistente. Fixar uma versão de referência e testar a matriz mínima em CI (GitHub Actions).
- **I3. Modelo baixado sem revisão fixa** no Dockerfile; builds diferentes podem gerar vetores diferentes com o mesmo nome de modelo, e `metadados_indice` não detecta. Fixar `revision=` e gravar no índice.
- **I4. `docker-compose.yml` com `tty: true`:** para MCP via stdio, TTY converte `\n` em `\r\n` e mistura streams, corrompendo o protocolo JSON-RPC. Para servir via container, usar `stdin_open` sem TTY (`docker run -i`) ou o modo `--http` com porta publicada — que já existe, mas `DEPLOY.md` ainda diz que HTTP "está fora de escopo".
- **I5. `libgl1`** no Dockerfile provavelmente é desnecessário (pymupdf não precisa); aumenta a imagem.
- **I6. Sem healthcheck** nem comando de warm-up na imagem.
- **I7. Aviso no pytest:** `UnicodeDecodeError` numa thread de `subprocess` (saída do processo filho em cp1252 lida como UTF-8, provavelmente em `test_cli.py`). Passar `encoding="utf-8", errors="replace"` ou `PYTHONIOENCODING=utf-8`.
- **I8. Conteúdo sob direitos autorais no corpus local:** `docs-fonte/` contém um livro comercial em PDF. Os PDFs estão no `.gitignore`, mas o `data/indice.db` e `docs-normalizado/` contêm o texto integral; ao compartilhar imagem Docker, índice ou expor via HTTP, isso também é distribuído. Vale uma nota no README sobre não publicar índices de conteúdo licenciado.

---

## 7. Testes

**Situação:** `91 passed, 1 deselected (lento), 8 warnings` em ~94 s.

**Pontos fortes:** boa granularidade por módulo; injeção de `embeddar_*_fn` permite testar o híbrido sem o modelo; testes de path traversal, órfãos e caminhos ambíguos.

**Lacunas:**
- Nenhum teste de ponta a ponta do servidor como o cliente o usa (subprocesso `docserver serve` + cliente MCP, ou `fastmcp.Client` in-memory) com **ingestão e serviço em cwds/caminhos diferentes** — exatamente o cenário de C1.
- Sem testes para: `--docs-fonte` inexistente (C4), colisão `x.pdf`/`x.docx` (C5), reingestão `--sem-embeddings` sobre índice vetorial (A2), cabeçalho dentro de code fence (M1), arquivo não UTF-8 (M13).
- Sem teste de regressão de qualidade de retrieval integrado ao CI (o `avaliar` existe, mas não tem meta mínima nem roda automaticamente).
- 94 s para testes "rápidos" é alto; provavelmente há carga do tokenizer real ou de extração de PDF em testes não marcados como `lento`.

---

## 8. Plano de ação recomendado

### Fase 1 — Tornar utilizável (1–2 dias)
1. Corrigir caminhos no índice (C1) + teste E2E com cwd diferente.
2. Devolver chunk completo e metadados no MCP (C2).
3. Paginar/limitar `ler_documento` e adicionar leitura por chunk com vizinhos (A1).
4. Guardas contra deleção acidental e colisão de nomes (C4, C5).
5. Pré-carregar modelo e conexão no `serve` (C6).

### Fase 2 — Qualidade de recuperação (3–5 dias)
6. Ampliar o conjunto de avaliação: ≥60 perguntas cobrindo PDFs, casos sem resposta, métricas hit@k, MRR e recall por chunk; rodar em CI com meta mínima.
7. Pesos BM25 por coluna, caminhos `UNINDEXED` (M7), corte léxico por cobertura (C3.1).
8. Reranker cross-encoder sobre os candidatos fundidos (C3.3) e MMR/colapso de adjacentes (M12).
9. Breadcrumb de seções e respeito a code fences/tabelas no chunking (M1–M3).
10. Números de página e OCR seletivo em PDFs (A5).

### Fase 3 — Operação e escala (contínuo)
11. Ingestão incremental por hash + embeddings em lote + swap atômico do índice (A3, A4).
12. Resultados estruturados (JSON), resources MCP e `instructions` do servidor (M20, M21, M23).
13. Auth no modo HTTP, compose sem TTY, lockfile e revisão fixa do modelo (A6, I1, I3, I4).
14. Logging estruturado de consultas para calibrar limiares com uso real (M22).

---

## 9. O que está bem feito (manter)

- Índice único em SQLite com FTS5 e sqlite-vec: zero infraestrutura, fácil de copiar e inspecionar.
- RRF por posição (não por score bruto) — escolha correta para fundir BM25 e cosseno.
- Prefixos `query:`/`passage:` do e5 e embeddings normalizados, com a conversão L2→cosseno documentada.
- Título + seção concatenados ao texto embeddado, dando contexto a chunks curtos.
- Detecção de modelo/dimensão divergente com mensagem acionável.
- Extrator plugável por extensão, com fallback pymupdf4llm → markitdown e limpeza de artefatos.
- `listar_documentos` e `ler_documento` baseados no índice, não no disco (evita servir órfãos).
- Mensagens de erro das tools escritas para orientar o agente ("use listar_documentos...").
- Documentação extensa (arquitetura, ingestão, agentes, deploy, troubleshooting) e comentários que explicam o *porquê* das decisões.
