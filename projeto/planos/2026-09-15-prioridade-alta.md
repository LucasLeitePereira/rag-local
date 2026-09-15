# Plano: tarefas de prioridade alta (TASK-001 a TASK-009) + extras

## Contexto
O `tasks.md` reúne o backlog tirado do `diagnostico.md` e dos testes do `docserver watch`. As tarefas 001–009 são as de prioridade alta:
- **Agentes:** o `ler_documento` estoura o contexto e a busca quebra sem vetores.
- **Operação:** ~35 min por reingestão; o banco trava durante a gravação.
- **Qualidade de busca:** faltam páginas, pesos BM25, avaliação e reranker.

Decisões do usuário:
- **Reranker:** suportar dois modelos e escolher o padrão pela avaliação.
- **Perguntas de avaliação dos PDFs:** eu escrevo a partir do corpus local.
- **Extras incluídos:** laço do watcher (eventos de último acesso) e TASK-012 (Tesseract).
- **Git:** commitar o que está pendente e criar branch nova, com um commit por tarefa.

## Fase 0 — Git
1. Commit na `fix/achados-criticos` do trabalho pendente: `docserver watch`, docs e `tasks.md`.
2. `git checkout -b feat/prioridade-alta`. Ao concluir cada tarefa, commit próprio e atualização do status no `tasks.md`.

## Fase 1 — Fundação (rápidas, sem mudar esquema)

### TASK-003 · WAL (`src/docserver/index.py`)
- `criar_indice`: `sqlite3.connect(caminho, timeout=30, check_same_thread=...)` e, se não for `:memory:`, `PRAGMA journal_mode=WAL`.
- Documentar em `ARQUITETURA.md` os arquivos `-wal`/`-shm` e a limitação de volumes de rede. Adicionar `data/*.db-wal` e `data/*.db-shm` ao `.gitignore`, se `data/` ainda não estiver ignorado.
- **Teste:** conexão A abre transação e insere sem commit; conexão B lê o estado antigo sem erro.

### TASK-004 · Embeddings em lote (`src/docserver/embed.py`, `cli.py`)
- `embed.embeddar_passagens(chunks, batch_size=32) -> list[list[float]]`: `modelo.encode([...], batch_size=..., normalize_embeddings=True)`.
- `executar_ingestao`: sem `embeddar_passagem_fn` injetada, usa o lote; com ela, mantém o caminho item a item (testes existentes).
- **Testes:** modelo falso (monkeypatch em `embed.obter_modelo`) verifica uma chamada com lista; teste `lento` compara lote × individual (tolerância 1e-5).

### TASK-002 · Fallback léxico (`index.py`, `server.py`, `cli.py`)
- **Sem vetores:** reindexação sem embeddings passa a fazer `DROP TABLE chunks_vec` e apagar `modelo`/`dimensao` de `metadados_indice`, e o relatório avisa "camada vetorial removida".
- **Avisos:** `buscar_hibrido(..., avisos: list[str] | None = None)` envolve `buscar_vetorial` em `try/except (ImportError, ErroModeloDivergente, sqlite3.OperationalError)`. Na falha, registra `logger.warning`, acrescenta o aviso e segue só léxico com `_filtrar(lexico)`.
- **Exibição:** `server._buscar_texto` e `cli._comando_search` mostram os avisos antes dos resultados ("Aviso: busca semântica indisponível (motivo); resultados apenas léxicos.").
- **Testes:**
  - `ingest --sem-embeddings` sobre índice vetorial: a busca híbrida não chama o embedder.
  - Embedder que lança `ImportError`: resultados léxicos com aviso.
  - Modelo divergente: resultados léxicos com aviso, sem exceção crua na tool.

### Extra · TASK-012 (Tesseract)
Resolvido dentro da TASK-006: a chamada a `pymupdf4llm.to_markdown` recebe `use_ocr=False`. O parâmetro existe em `pymupdf4llm/__init__.py:_layout_to_markdown`; com ele, `select_ocr_function`/`get_tessdata` não rodam.
- **Critério:** a suíte perde os 8 warnings e a ingestão de PDF não imprime tracebacks.

## Fase 2 — Esquema v2 e ingestão incremental
Os itens 008, 006 e 005 mudam o esquema e são implementados em sequência, com **uma única versão de esquema**.

### Versionamento de esquema (base comum)
- **Criação:** `metadados_indice` passa a ser criada sempre, com `versao_esquema = 2`.
- **Verificação:** `index.verificar_esquema(conexao) -> str | None` devolve uma mensagem se existe tabela `chunks` sem versão ou com versão diferente.
- **Na ingestão:** esquema antigo gera **reconstrução completa automática**. As tabelas são recriadas dentro da transação final (`BEGIN IMMEDIATE` … `commit`, com `rollback` em erro), e o relatório mostra "índice recriado: formato antigo".
- **No servidor e na CLI de busca:** a mensagem orienta "índice em formato antigo — rode `docserver ingest`", no mesmo padrão de `server._mensagem_indice_ausente`.

### TASK-008 · BM25 por coluna (`index.py`)
- **Esquema:** `caminho_origem` e `caminho_normalizado` como `UNINDEXED`, o que mantém o filtro `caminho_origem = ?`.
- **Pesos:** `PESOS_BM25` na ordem das colunas, inicialmente `(0, 0, 1.0, 2.0, 1.0, 0, 0, 0)`, e `bm25(chunks, *PESOS_BM25)` em `buscar`. Título com peso 1, porque é igual em todos os chunks do documento e inflaria como os caminhos. Ajustável via env `PESOS_BM25`; valores finais escolhidos com a TASK-007.
- **Cobertura:** tirar os caminhos de `_CAMPOS_TEXTO` (cobertura léxica).
- **Teste:** documento cujo caminho contém "api" e texto sem "api" não aparece na busca por "api".

### TASK-006 · Páginas (`extract.py`, `chunk.py`, `index.py`, `server.py`, `cli.py`)
- **Extração:** `_extrair_pdf` chama `pymupdf4llm.to_markdown(caminho, page_chunks=True, use_ocr=False)`. Aplica `_limpar_markdown_pdf` por página e junta as páginas com o marcador `<!--pagina:N-->` numa linha própria, sem espaços, para sobreviver ao split por palavra.
  - O fallback markitdown fica sem marcadores (página nula).
  - A regra de `MIN_CARACTERES_PDF_VALIDO` continua valendo sobre o texto total.
- **Chunking:**
  - Em `chunkar_arquivo`, percorre os blocos em ordem mantendo `pagina_corrente`. Para cada bloco: `pagina_inicio` é o primeiro marcador do bloco, se ele abre com um, ou a corrente; `pagina_fim` é o último marcador do bloco, ou o início.
  - Atualiza a corrente **antes** do descarte por `MIN_CARACTERES`, depois remove os marcadores do texto.
  - `_titulo_documento` ignora linhas de marcador.
- **Índice:** colunas `pagina_inicio UNINDEXED` e `pagina_fim UNINDEXED` em `_ESQUEMA`/`_CAMPOS`.
- **Saída:**
  - `server._formatar_resultados_mcp` e `cli.formatar_resultados` mostram `p. N` ou `pp. N–M`.
  - `ler_documento` remove os marcadores do corpo.
- **Testes:**
  - PDF de 3 páginas (fixture com `pymupdf`, como `exemplo_pdf` em `tests/conftest.py`): chunks com páginas corretas.
  - Marcador cai numa cauda de overlap.
  - Fallback sem marcador resulta em página `None`.

### TASK-005 · Ingestão incremental (`cli.py`, `index.py`)
- **Tabela nova** `arquivos(caminho_origem PK, caminho_normalizado, sha256, tamanho, chunks, extrator, ingerido_em)`.
- **Classificação:** `executar_ingestao` passa a comparar o sha256 de cada arquivo suportado com `arquivos` (sempre hash: ~50 ms para 16 MB; mais robusto que mtime, que a cópia do Windows preserva).
  - **Inalterado:** hash igual e `.md` normalizado existente. Não extrai nem calcula embedding.
  - **Novo ou alterado:** extrai, gera chunks e embeddings (em lote, TASK-004).
  - **Removido:** está em `arquivos` e sumiu da fonte, ou passou a falhar na extração (mantém a semântica atual).
- **Reconstrução completa:** quando o esquema é antigo, o modelo gravado difere do atual (troca a atual `ErroModeloDivergente` na ingestão por reconstrução automática, informada no relatório), ou há embeddings ligados e o índice ainda não tem vetores. O `--limpar` continua como está.
- **Proteções:** "nenhum arquivo suportado" continua igual. A checagem de "índice ficaria vazio" usa o total final (chunks inalterados + novos).
- **Gravação:** transação única que apaga os chunks e vetores das origens alteradas ou removidas (`rowid`s via `caminho_origem`), insere os novos e faz upsert/delete em `arquivos`.
- **Órfãos:** `_remover_gerados` recebe em `manter` também os normalizados dos inalterados.
- **Relatório:** `formatar_relatorio` ganha novos / alterados / inalterados / removidos. `ingerido_em` só muda nos reprocessados.
- **`ARQUITETURA.md`:** reescrever a decisão "Reindexação completa, não incremental".
- **Testes** (em `tests/test_cli.py`/`test_pipeline.py`):
  - Reingerir sem mudanças não chama extrator nem embedder (espiões).
  - Alterar 1 de 3 arquivos reprocessa só ele.
  - Apagar um arquivo remove chunks, vetores e `.md`.
  - Troca de modelo força reconstrução.
  - Esquema v1 é recriado.
  - `--forcar` e proteções continuam passando.

### Extra · Laço do watcher (`src/docserver/watch.py`)
- `_Manipulador` guarda `(tamanho, mtime_ns)` por caminho, preenchido na partida com os arquivos relevantes.
- Evento `modified` só registra se o `stat` atual difere do guardado; `created`/`deleted`/`moved` sempre registram e atualizam o mapa.
- **Teste:** `FileModifiedEvent` sobre um arquivo sem mudança real não registra pendência; após escrever conteúdo novo, registra.

## Fase 3 — Leitura para agentes

### TASK-001 · `ler_documento` paginado + `ler_trecho` (`server.py`, `index.py`)
- **`ler_documento(caminho, parte=1, secao=None)`:**
  - Corpo sem marcadores. Com `secao`, recorta a seção por nome, casando sem acento e sem caixa; se houver ambiguidade, lista as opções.
  - Divide em partes de até `LIMITE_CARACTERES_LEITURA` (env, padrão 20 000), cortando em parágrafo.
  - Com mais de uma parte: cabeçalho "Parte X de N" e rodapé "continue com `ler_documento(caminho, parte=X+1)`". Parte inexistente gera mensagem clara.
  - Documento pequeno continua idêntico ao atual.
- **Nova tool `ler_trecho(id, vizinhos=1)`:**
  - `vizinhos` limitado a 0–5.
  - Busca o chunk por `rowid` e os de mesma `caminho_origem` com `ordem` na janela, em ordem.
  - Cada bloco sai com seção e página; um id inexistente gera mensagem clara.
  - Helper `index.obter_trechos(conexao, id, vizinhos)`.
- **Docstrings:** `buscar` passa a indicar `ler_trecho` com o id do resultado e `ler_documento` por partes. Atualizar a tabela de tools em `docs/AGENTES.md`.
- **Testes:**
  - Documento grande devolve a parte 1 com rodapé e a última parte sem rodapé.
  - `secao` existente, inexistente e ambígua.
  - `ler_trecho` no início e no fim do documento (janela truncada).
  - id inválido.

## Fase 4 — Qualidade de busca

### TASK-007 · Avaliação ampliada (`cli.py`, `avaliacao/`)
- **Formato YAML:** `pergunta`, `perfil` (tecnico/natural), `esperado` (origem ou `null` para pergunta sem resposta) e `trecho` opcional (substring normalizada sem acento e sem caixa que deve estar num chunk do top-k).
- **Métricas por modo e perfil:** hit@1, hit@5, MRR@5, recall de trecho@5 e, para negativos, taxa de resultado vazio (só no `hibrido`, que tem corte).
- **Tabela:** reescrever `formatar_tabela_avaliacao`, removendo o `_somar` morto (M25).
- **Flags:**
  - `--min-hit5 X`: sai com código 1 abaixo da meta.
  - `--validar`: confere que cada `trecho` existe no `.md` normalizado do `esperado` e aborta listando as inválidas.
- **Arquivos:**
  - `avaliacao/perguntas.yaml` (demo, no Git) ganha negativos e trechos.
  - Novo `avaliacao/perguntas-corpus-local.yaml` com 60+ perguntas que eu escrevo lendo `docs-normalizado/`: livro, Niterói, PeopleTools AE/PCR e o PDF `f39476…`, mistura de técnico/natural e ~10 negativos. Documentar em `docs/ARQUITETURA.md` (seção de avaliação) que ele depende dos PDFs locais.
- **Linha de base:** rodar a avaliação antes das mudanças de busca, fixando o commit da Fase 1, e registrar os números no `docs/ARQUITETURA.md` para comparar com TASK-008/009.

### TASK-009 · Reranker (`src/docserver/rerank.py` novo, `index.py`, `server.py`, `cli.py`)
- **Módulo `rerank.py`:**
  - Modelos candidatos em `MODELOS_RERANKER = {"mminilm": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", "bge-m3": "BAAI/bge-reranker-v2-m3"}`, escolhido por env `RERANKER` (`mminilm` | `bge-m3` | `desligado`).
  - Usa `sentence_transformers.CrossEncoder`, que já vem na extra `embeddings`, com cache e `local_files_only` com fallback, igual a `embed._carregar_modelo`.
  - `pontuar(consulta, itens) -> list[float]`.
- **Integração em `buscar_hibrido`:** recebe `reranquear_fn` injetável.
  - Com reranker disponível: pontua os `N_CANDIDATOS_RERANK` (20) melhores da fusão RRF; o texto é `embed.texto_para_embeddar` truncado.
  - Ordena pela pontuação e filtra por `RERANK_MINIMO`; o filtro `_relevante` atual deixa de ser o corte.
  - Sem reranker, ou com falha: comportamento atual + aviso (mecanismo da TASK-002).
- **Pontos de uso:** `server._aquecer` pré-carrega o reranker; CLI `search --sem-rerank`; `avaliar` ganha os modos `hibrido+mminilm` e `hibrido+bge-m3`.
- **Decisão pela avaliação:** rodar os dois no corpus local e medir métricas e latência média por busca (CPU). Escolher o padrão e calibrar `RERANK_MINIMO` pelos negativos. Registrar números e decisão em `ARQUITETURA.md`, tirando o reranker da "Fase futura". Ajustar também os pesos da TASK-008.
- **Testes:** `reranquear_fn` falsa inverte a ordem e corta abaixo do mínimo; falha no reranker cai no fluxo atual com aviso; teste `lento` carrega o mMiniLM real.

## Encerramento
- Atualizar `tasks.md`: 001–009 e 012 para "Concluídas", com commit, e registrar o extra do watcher.
- Revisar `README.md`, `docs/INGESTAO.md` (incremental, páginas), `docs/AGENTES.md` (tools novas), `docs/TROUBLESHOOTING.md` (aviso de busca semântica, índice em formato antigo).

## Verificação
1. `venv/Scripts/python -m pytest -q` verde a cada tarefa, sem os 8 warnings após a TASK-006; `pytest -m lento` no fim (embeddings em lote e reranker reais).
2. Ingestão real:
   - `docserver ingest` no corpus atual reconstrói do esquema v1. Medir o tempo contra os ~35 min atuais.
   - Rodar de novo sem mudanças deve levar segundos ("inalterados: 11").
   - Copiar um PDF novo reprocessa só ele.
3. `docserver search "Application Engine" --documento pt857tape-b022020.pdf` mostra a página. `docserver avaliar avaliacao/perguntas-corpus-local.yaml --validar` passa, e a tabela mostra o ganho do reranker frente à linha de base.
4. Servidor MCP (`docserver server-mcp`):
   - `ler_documento` do livro devolve "Parte 1 de N".
   - `ler_trecho(id)` com um id vindo de `buscar`.
   - Busca durante uma ingestão responde sem `database is locked`.
5. Watcher: `docserver watch` parado por mais de 1 h após uma ingestão não dispara reingestão sozinho; um arquivo novo dispara processamento só dele.
