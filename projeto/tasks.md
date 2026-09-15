# Backlog de tarefas — docserver

Tarefas para implementar no futuro, no estilo de um board do Jira. A fonte
principal é o `diagnostico.md` (IDs originais C/A/M/I entre parênteses),
somada aos ajustes encontrados ao testar o `docserver watch`.

> Última revisão: 2026-09-15 · Tarefas de prioridade alta 001–009 concluídas na branch
> `feat/prioridade-alta`.
> Os achados C1–C6 do diagnóstico já foram
> resolvidos (commit `6cdb0aa`) e não aparecem aqui, exceto a parte pendente do C3.

## Como usar este arquivo

- **Nova tarefa:** use o próximo ID livre (`TASK-NNN`), preencha os campos e
  adicione uma linha no quadro-resumo.
- **Mudança de status:** atualize o campo na tarefa e no quadro.
- **Tarefa concluída:** mova para "Concluídas", com data e commit.
- Os IDs nunca são reaproveitados.

### Legenda

| Campo | Valores |
|---|---|
| **Prioridade** | 🔴 Alta: afeta a confiabilidade para agentes, dados ou segurança · 🟡 Média: qualidade ou operação perceptível · 🟢 Baixa: melhoria, limpeza ou escala futura |
| **Esforço** | P: até meio dia · M: 1–2 dias · G: 3 dias ou mais |
| **Tipo** | bug · melhoria · débito técnico · infra · docs · teste |
| **Status** | Backlog · A fazer · Em andamento · Bloqueada · Concluída |

---

## Quadro-resumo

| ID | Título | Épico | Prioridade | Esforço | Status |
|---|---|---|---|---|---|
| TASK-001 | Paginar `ler_documento` e criar leitura por trecho com vizinhos | Servidor MCP | 🔴 Alta | M | Concluída |
| TASK-002 | Fallback para busca léxica quando não há vetores ou o modelo falha | Servidor MCP | 🔴 Alta | P | Concluída |
| TASK-003 | Ativar `journal_mode=WAL` no índice SQLite | Ingestão | 🔴 Alta | P | Concluída |
| TASK-004 | Embeddings em lote | Ingestão | 🔴 Alta | P | Concluída |
| TASK-005 | Ingestão incremental por hash de arquivo | Ingestão | 🔴 Alta | G | Concluída |
| TASK-006 | Números de página nos chunks de PDF | Extração | 🔴 Alta | M | Concluída |
| TASK-007 | Ampliar o conjunto de avaliação e as métricas | Busca | 🔴 Alta | M | Concluída |
| TASK-008 | Pesos BM25 por coluna e caminhos `UNINDEXED` | Busca | 🔴 Alta | P | Concluída |
| TASK-009 | Reranker cross-encoder sobre os candidatos fundidos | Busca | 🔴 Alta | G | Concluída |
| TASK-010 | Autenticação por token no modo HTTP | Segurança | 🔴 Alta | M | Backlog |
| TASK-011 | `docker-compose.yml` sem TTY e `DEPLOY.md` atualizado sobre HTTP | Infra | 🔴 Alta | P | Backlog |
| TASK-012 | Eliminar o `UnicodeDecodeError` da verificação do Tesseract | Extração | 🟡 Média | P | Concluída |
| TASK-013 | Troca atômica do índice e de `docs-normalizado` | Ingestão | 🟡 Média | M | Backlog |
| TASK-014 | Servidor abre o índice somente leitura e sem escrita em consultas | Servidor MCP | 🟡 Média | P | Backlog |
| TASK-015 | Watcher garantido em Linux: modo polling e execução como serviço | Ingestão | 🟡 Média | M | Backlog |
| TASK-016 | Impedir ingestões simultâneas (watcher + `ingest` manual) | Ingestão | 🟡 Média | P | Backlog |
| TASK-051 | Progresso por arquivo e por etapa durante a ingestão | Ingestão | 🟡 Média | P | Backlog |
| TASK-017 | OCR seletivo por página em PDFs escaneados | Extração | 🟡 Média | G | Backlog |
| TASK-018 | Estrutura de cabeçalhos e artefatos de acentuação em PDFs | Extração | 🟡 Média | M | Backlog |
| TASK-019 | Detectar a codificação de `.txt`, `.md` e `.csv` | Extração | 🟡 Média | P | Backlog |
| TASK-020 | `origem` respeita o `--docs-fonte` informado | Extração | 🟡 Média | P | Backlog |
| TASK-021 | Ignorar cabeçalhos dentro de blocos de código | Chunking | 🟡 Média | P | Backlog |
| TASK-022 | Tabelas e blocos de código como unidades atômicas | Chunking | 🟡 Média | M | Backlog |
| TASK-023 | Breadcrumb de seções (`H1 › H2 › H3`) | Chunking | 🟡 Média | M | Backlog |
| TASK-024 | Limiar vetorial relativo ou calibrado | Busca | 🟡 Média | M | Backlog |
| TASK-025 | Validar `limite` e tornar o nº de candidatos proporcional | Busca | 🟡 Média | P | Backlog |
| TASK-026 | Diversidade nos resultados (MMR ou colapso de adjacentes) | Busca | 🟡 Média | M | Backlog |
| TASK-027 | Paginação e filtro em `listar_documentos` | Servidor MCP | 🟡 Média | P | Backlog |
| TASK-028 | Resultados estruturados (JSON) nas tools | Servidor MCP | 🟡 Média | M | Backlog |
| TASK-029 | Logging estruturado de consultas | Servidor MCP | 🟡 Média | P | Backlog |
| TASK-030 | Lockfile e limites superiores de versão nas dependências | Infra | 🟡 Média | P | Backlog |
| TASK-031 | Versão de Python de referência e CI no GitHub Actions | Infra | 🟡 Média | M | Backlog |
| TASK-032 | Revisão fixa do modelo de embeddings | Infra | 🟡 Média | P | Backlog |
| TASK-033 | Teste E2E do servidor com cliente MCP e cwds diferentes | Testes | 🟡 Média | M | Backlog |
| TASK-034 | Overlap de chunks por frase | Chunking | 🟢 Baixa | P | Backlog |
| TASK-035 | Remover o custo quadrático da tokenização no chunking | Chunking | 🟢 Baixa | M | Backlog |
| TASK-036 | Registrar qual contagem de tokens foi usada na ingestão | Chunking | 🟢 Baixa | P | Backlog |
| TASK-037 | Stopwords em inglês e stemming em português | Busca | 🟢 Baixa | M | Backlog |
| TASK-038 | Partition key por documento no `vec0` | Busca | 🟢 Baixa | M | Backlog |
| TASK-039 | Ignorar pastas ocultas em `docs-fonte` | Extração | 🟢 Baixa | P | Backlog |
| TASK-040 | Extrator de PDF devolve `(texto, extrator)` sem estado global | Extração | 🟢 Baixa | P | Backlog |
| TASK-041 | Front matter robusto (CRLF, bloco não fechado, front matter de origem) | Extração | 🟢 Baixa | P | Backlog |
| TASK-042 | CSV com escape de `\|` e divisão de tabelas grandes | Extração | 🟢 Baixa | P | Backlog |
| TASK-043 | Expor documentos como resources MCP | Servidor MCP | 🟢 Baixa | M | Backlog |
| TASK-044 | Enxugar a docstring de `buscar` e usar `instructions` do servidor | Servidor MCP | 🟢 Baixa | P | Backlog |
| TASK-045 | Revisar a necessidade de `libgl1` no Dockerfile | Infra | 🟢 Baixa | P | Backlog |
| TASK-046 | Healthcheck e warm-up na imagem Docker | Infra | 🟢 Baixa | P | Backlog |
| TASK-047 | Aviso sobre não publicar índices com conteúdo licenciado | Docs | 🟢 Baixa | P | Backlog |
| TASK-048 | Reduzir o tempo da suíte de testes rápida | Testes | 🟢 Baixa | P | Backlog |
| TASK-049 | Remover código morto em `formatar_tabela_avaliacao` | CLI | 🟢 Baixa | P | Concluída |
| TASK-050 | `docserver stats` mostrar a data da ingestão | CLI | 🟢 Baixa | P | Backlog |

### Ordem sugerida

1. **Rápidas e de alto impacto:** TASK-002, TASK-003, TASK-004, TASK-011, TASK-012.
2. **Uso por agentes:** TASK-001, TASK-006.
3. **Base para mexer na busca:** TASK-007 (sem avaliação ampla, as mudanças de busca são às cegas), depois TASK-008 e TASK-009.
4. **Operação com o watcher:** TASK-005, TASK-013, TASK-016.

---

## Épico: Ingestão

### TASK-003 · Ativar `journal_mode=WAL` no índice SQLite
- **Prioridade:** 🔴 Alta · **Esforço:** P · **Tipo:** melhoria · **Status:** Concluída (334a281)
- **Origem:** teste do `docserver watch` + diagnóstico (A4, parte)
- **Contexto:** o índice usa o journal padrão do SQLite e nenhum `timeout` é configurado. Enquanto a ingestão confirma a transação final, as leituras do servidor ficam bloqueadas, e uma busca que espere mais de 5 s falha com `database is locked`. Com o watcher, reingestões acontecem com o servidor no ar.
- **O que fazer:** em `index.criar_indice`, executar `PRAGMA journal_mode=WAL` e definir um `timeout` explícito na conexão. Documentar em `docs/ARQUITETURA.md` os arquivos `-wal`/`-shm` gerados.
- **Critérios de aceite:** uma busca durante a gravação final de uma reingestão responde com o índice antigo, sem erro; há teste com duas conexões (uma escrevendo em transação aberta e outra lendo).

### TASK-004 · Embeddings em lote
- **Prioridade:** 🔴 Alta · **Esforço:** P · **Tipo:** melhoria · **Status:** Concluída (124a2da)
- **Origem:** diagnóstico (A3)
- **Contexto:** `cli.executar_ingestao` calcula um embedding por chamada (`[calcular(c) for c in todos_chunks]`). A reingestão de 10 arquivos levou 480 s, e em CPU o `encode` em lote costuma ser de 5 a 20 vezes mais rápido.
- **O que fazer:** função `embed.embeddar_passagens(chunks, batch_size=32)` usando `SentenceTransformer.encode` com lista; manter a injeção para testes.
- **Critérios de aceite:** vetores idênticos (tolerância numérica) aos da versão atual; tempo de ingestão do corpus real medido antes e depois e registrado no PR.

### TASK-005 · Ingestão incremental por hash de arquivo
- **Prioridade:** 🔴 Alta · **Esforço:** G · **Tipo:** melhoria · **Status:** Concluída (a8b7737)
- **Origem:** diagnóstico (A3); ficou mais urgente com o watcher
- **Contexto:** hoje, qualquer mudança reextrai todos os PDFs e recalcula todos os embeddings. Adicionar um PDF custou ~8 min de reingestão. Além disso, `ingerido_em` muda sempre, poluindo diffs. Isto revê a decisão "Reindexação completa, não incremental" de `docs/ARQUITETURA.md`.
- **O que fazer:** tabela `arquivos` no índice (origem, sha256, mtime, tamanho, extrator); reextrair e recalcular embeddings só das origens novas ou alteradas; apagar só os chunks das origens alteradas ou removidas; manter `ingest --limpar` como reconstrução completa.
- **Critérios de aceite:** reingerir sem mudanças não chama extrator nem modelo; alterar um arquivo só reprocessa aquele arquivo; as proteções de `ErroIngestao` e a remoção de órfãos continuam valendo; ADR atualizado em `ARQUITETURA.md`.
- **Dependências:** TASK-004 (recomendado antes).

### TASK-013 · Troca atômica do índice e de `docs-normalizado`
- **Prioridade:** 🟡 Média · **Esforço:** M · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** diagnóstico (A4)
- **Contexto:** a ingestão reescreve `docs-normalizado/` antes de atualizar o índice. Se o processo cair durante os embeddings (a etapa mais longa), disco e índice ficam dessincronizados. Enquanto a ingestão roda, `ler_documento` pode servir texto mais novo que os chunks da `buscar`.
- **O que fazer:** gerar os `.md` numa pasta temporária e o índice em arquivo temporário (ou transação única), e trocar tudo ao final (`os.replace`).
- **Critérios de aceite:** matar a ingestão no meio (teste com exceção injetada durante os embeddings) deixa índice e `docs-normalizado` no estado anterior.
- **Dependências:** avaliar junto com TASK-005, que muda o fluxo de gravação.

### TASK-015 · Watcher garantido em Linux: modo polling e execução como serviço
- **Prioridade:** 🟡 Média · **Esforço:** M · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** implementação do `docserver watch` (ver `docs/INGESTAO.md`)
- **Contexto:** em Linux o watchdog usa `inotify`, que não recebe eventos em volumes Docker montados de hosts Windows/macOS, em `/mnt/c` do WSL2 e em NFS/SMB. Há também o limite `fs.inotify.max_user_watches`. O watcher só foi validado no Windows.
- **O que fazer:** validar em Linux nativo, Docker e WSL2; flag `docserver watch --polling` usando `watchdog.observers.polling.PollingObserver` (com intervalo configurável); unit systemd de exemplo e/ou serviço `watch` no `docker-compose.yml`.
- **Critérios de aceite:** com `--polling`, o watcher detecta a criação de um arquivo num volume montado no Docker; documentação atualizada em `INGESTAO.md`, `DEPLOY.md` e `TROUBLESHOOTING.md`.

### TASK-016 · Impedir ingestões simultâneas (watcher + `ingest` manual)
- **Prioridade:** 🟡 Média · **Esforço:** P · **Tipo:** bug · **Status:** Backlog
- **Origem:** implementação do `docserver watch`
- **Contexto:** hoje só a documentação pede para não rodar `docserver ingest` com o watcher ativo. Duas ingestões simultâneas reescrevem `docs-normalizado/` e o índice ao mesmo tempo.
- **O que fazer:** lock de arquivo ao lado do índice (ex.: `data/indice.db.lock`) adquirido por `executar_ingestao`; a segunda ingestão aborta com mensagem clara (ou espera, no caso do watcher).
- **Critérios de aceite:** teste com duas ingestões concorrentes: uma conclui e a outra recebe `ErroIngestao` explicando o lock; lock órfão (processo morto) não bloqueia para sempre.

### TASK-051 · Progresso por arquivo e por etapa durante a ingestão
- **Prioridade:** 🟡 Média · **Esforço:** P · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** teste do `docserver watch` (2026-09-15)
- **Contexto:** a ingestão só imprime o relatório no fim. Ao adicionar um PDF de 16 MB, a reingestão passou mais de 18 minutos sem nenhuma saída. Só dava para saber em que etapa ela estava olhando os horários dos `.md` em `docs-normalizado/` e o uso de CPU do processo.
- **O que fazer:** em `cli.executar_ingestao`, emitir uma linha por arquivo (`[3/11] extraindo pt857tpcr-b022020.pdf (16 MB)… 412 chunks em 95.2s`), uma linha ao iniciar cada etapa (extração, embeddings, gravação do índice) e progresso periódico dos embeddings (`embeddings 400/1351`). A saída vai por um callback injetável (`progresso_fn`), para os testes não poluírem a saída e o watcher prefixar com `docserver:`. O tempo de cada etapa entra no relatório final, o que mostra se o gargalo é a extração ou os embeddings (útil para priorizar TASK-004 e TASK-005). No modo stdio do servidor, nada disso pode ir para o stdout.
- **Critérios de aceite:** `docserver ingest` e `docserver watch` mostram o arquivo em processamento e o avanço dos embeddings; o relatório final traz o tempo por etapa e o arquivo mais lento; teste verifica as chamadas do callback.

---

## Épico: Extração

### TASK-012 · Eliminar o `UnicodeDecodeError` da verificação do Tesseract
- **Prioridade:** 🟡 Média · **Esforço:** P · **Tipo:** bug · **Status:** Concluída (84e63ab)
- **Origem:** teste do `docserver watch` + diagnóstico (I7, com a causa corrigida)
- **Contexto:** a cada PDF, `pymupdf4llm.to_markdown` chama `pymupdf.get_tessdata()`, que roda `tesseract --list-langs` e `where tesseract` via shell com `text=True`. Sem o Tesseract instalado, o Windows responde em português na codificação do console (cp850), e a leitura como UTF-8 lança `UnicodeDecodeError` numa thread do `subprocess`. A extração continua, mas o traceback aparece no terminal e parece falha. O diagnóstico atribuía o aviso ao `test_cli.py`; a causa real é essa verificação.
- **O que fazer:** investigar a opção do `pymupdf4llm` para desligar o OCR (ou definir `TESSDATA_PREFIX`), para que a verificação não rode quando não há OCR; se não houver opção, isolar a chamada. Não mascarar erros reais de extração.
- **Critérios de aceite:** `docserver ingest` com PDFs não imprime tracebacks; os 8 warnings da suíte de testes desaparecem; o texto extraído é idêntico ao atual.
- **Relacionada:** TASK-017 (se o OCR for adotado, a verificação passa a ser desejada).

### TASK-006 · Números de página nos chunks de PDF
- **Prioridade:** 🔴 Alta · **Esforço:** M · **Tipo:** melhoria · **Status:** Concluída (84e63ab)
- **Origem:** diagnóstico (A5)
- **Contexto:** `pymupdf4llm.to_markdown` é chamado sem `page_chunks=True`; o agente não consegue citar "p. 123", o principal requisito de citação em livros e relatórios.
- **O que fazer:** extrair por página, preservar marcadores de página no Markdown normalizado, gravar `pagina_inicio`/`pagina_fim` no chunk e devolvê-los em `buscar`.
- **Critérios de aceite:** resultados de busca em PDFs mostram a página; teste com PDF de 3 páginas verifica a atribuição.

### TASK-017 · OCR seletivo por página em PDFs escaneados
- **Prioridade:** 🟡 Média · **Esforço:** G · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** diagnóstico (A5); fase futura em `ARQUITETURA.md`
- **Contexto:** o relatório de Niterói (32 MB → 110 KB de texto) indica muitas páginas-imagem. `MIN_CARACTERES_PDF_VALIDO` é avaliado por arquivo, não por página.
- **O que fazer:** detectar páginas com pouco texto e aplicar OCR só nelas (pymupdf + Tesseract, ou `docling`); tornar o OCR opcional (extra de instalação) e marcar no relatório quais páginas passaram por OCR.
- **Critérios de aceite:** PDF misto (texto + página escaneada) tem as duas partes indexadas; sem Tesseract instalado, a ingestão segue como hoje, sem ruído.
- **Dependências:** TASK-006, TASK-012.

### TASK-018 · Estrutura de cabeçalhos e artefatos de acentuação em PDFs
- **Prioridade:** 🟡 Média · **Esforço:** M · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** diagnóstico (A5)
- **Contexto:** o livro tem 706 cabeçalhos, mas só 15 viram seção; "CHAPTER 6 Storage" saiu como texto comum, então o capítulo 6 fica atribuído ao 5. Há artefatos como "An á lise" e "Á reas-alvo".
- **O que fazer:** avaliar `docling`/`marker` para PDFs estruturados; promover linhas de capítulo a cabeçalho; pós-processar espaços dentro de palavras acentuadas.
- **Critérios de aceite:** no livro, chunks do capítulo 6 são atribuídos ao capítulo 6; os artefatos citados somem.

### TASK-019 · Detectar a codificação de `.txt`, `.md` e `.csv`
- **Prioridade:** 🟡 Média · **Esforço:** P · **Tipo:** bug · **Status:** Backlog
- **Origem:** diagnóstico (M13)
- **Contexto:** `_extrair_texto_puro` e `_extrair_csv` só aceitam UTF-8; arquivos cp1252/latin-1, comuns no Windows, viram falha.
- **O que fazer:** tentar UTF-8 e, se falhar, usar `charset-normalizer` (já dependência transitiva); registrar a codificação detectada no front matter.
- **Critérios de aceite:** teste com `.txt` em cp1252 contendo acentos é extraído corretamente.

### TASK-020 · `origem` respeita o `--docs-fonte` informado
- **Prioridade:** 🟡 Média · **Esforço:** P · **Tipo:** bug · **Status:** Backlog
- **Origem:** diagnóstico (M17)
- **Contexto:** `extract.normalizar` sempre prefixa `docs-fonte/`, mesmo com `--docs-fonte outra/pasta`; o caminho citado ao agente fica errado.
- **O que fazer:** usar o nome da pasta de origem real (ou caminho relativo a ela) e documentar a compatibilidade com índices existentes.
- **Critérios de aceite:** ingestão com `--docs-fonte manuais` grava `origem: manuais/...`.

### TASK-039 · Ignorar pastas ocultas em `docs-fonte`
- **Prioridade:** 🟢 Baixa · **Esforço:** P · **Tipo:** bug · **Status:** Backlog
- **Origem:** diagnóstico (M16)
- **Contexto:** `cli._deve_ignorar` olha só o nome do arquivo; `.git/` e `.obsidian/` dentro de `docs-fonte` são ingeridas. O filtro do watcher (`watch.arquivo_relevante`) herda o mesmo comportamento.
- **O que fazer:** ignorar se qualquer parte do caminho relativo começar com `.`.
- **Critérios de aceite:** teste com `docs-fonte/.obsidian/nota.md` não indexado e mudanças nela não disparam o watcher.

### TASK-040 · Extrator de PDF devolve `(texto, extrator)` sem estado global
- **Prioridade:** 🟢 Baixa · **Esforço:** P · **Tipo:** débito técnico · **Status:** Backlog
- **Origem:** diagnóstico (M18)
- **O que fazer:** remover `_ultimo_extrator_pdf`; os extratores retornam o nome do extrator usado junto com o texto.
- **Critérios de aceite:** front matter continua registrando `pymupdf4llm`/`markitdown` corretamente; testes atuais passam.

### TASK-041 · Front matter robusto
- **Prioridade:** 🟢 Baixa · **Esforço:** P · **Tipo:** bug · **Status:** Backlog
- **Origem:** diagnóstico (M15)
- **Contexto:** `ler_front_matter` lança `ValueError` com bloco não fechado, não trata CRLF, e um `.md` de origem com front matter próprio fica com dois blocos.
- **Critérios de aceite:** testes para CRLF, bloco não fechado e `.md` de origem com front matter (os metadados originais não viram texto indexado).

### TASK-042 · CSV com escape de `|` e divisão de tabelas grandes
- **Prioridade:** 🟢 Baixa · **Esforço:** P · **Tipo:** bug · **Status:** Backlog
- **Origem:** diagnóstico (M14)
- **Critérios de aceite:** células com `|` não quebram a tabela; CSV grande gera chunks que repetem o cabeçalho.
- **Relacionada:** TASK-022.

---

## Épico: Chunking

### TASK-021 · Ignorar cabeçalhos dentro de blocos de código
- **Prioridade:** 🟡 Média · **Esforço:** P · **Tipo:** bug · **Status:** Backlog
- **Origem:** diagnóstico (M1)
- **Contexto:** `# comentário` dentro de ```` ``` ```` é tratado como seção por `_CABECALHO_SECAO`, fragmentando o documento.
- **Critérios de aceite:** teste com bloco bash contendo `# comentário` gera uma única seção.

### TASK-022 · Tabelas e blocos de código como unidades atômicas
- **Prioridade:** 🟡 Média · **Esforço:** M · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** diagnóstico (M2)
- **Contexto:** `_unidades_atomicas` + `_blocos_por_tamanho` quebram por `\n` e reúnem com `\n\n`, desfazendo tabelas e fences.
- **Critérios de aceite:** tabela que cabe num chunk fica intacta; tabela maior é dividida repetindo o cabeçalho; fence nunca é aberta num chunk e fechada em outro sem marcação.

### TASK-023 · Breadcrumb de seções (`H1 › H2 › H3`)
- **Prioridade:** 🟡 Média · **Esforço:** M · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** diagnóstico (M3)
- **Contexto:** um H3 "Visão geral" perde os pais; no relatório de Niterói há várias "1. Visão geral" indistinguíveis.
- **O que fazer:** gravar o breadcrumb em `secao` e usá-lo no texto usado para o embedding.
- **Critérios de aceite:** resultados mostram o caminho completo da seção; requer reingestão (documentar).

### TASK-034 · Overlap de chunks por frase
- **Prioridade:** 🟢 Baixa · **Esforço:** P · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** diagnóstico (M4)
- **Critérios de aceite:** chunks com overlap começam no início de uma frase quando houver pontuação disponível.

### TASK-035 · Remover o custo quadrático da tokenização no chunking
- **Prioridade:** 🟢 Baixa · **Esforço:** M · **Tipo:** débito técnico · **Status:** Backlog
- **Origem:** diagnóstico (M5)
- **O que fazer:** em `_dividir_por_palavras` e `_cauda_por_tokens`, tokenizar uma vez e cortar por offsets (`return_offsets_mapping`).
- **Critérios de aceite:** chunks idênticos aos atuais; texto longo sem pontuação processado em tempo linear (teste de tempo com margem).

### TASK-036 · Registrar qual contagem de tokens foi usada na ingestão
- **Prioridade:** 🟢 Baixa · **Esforço:** P · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** diagnóstico (M6)
- **Contexto:** sem `transformers` ou sem o modelo em cache, o chunking cai em silêncio para `len/3`.
- **Critérios de aceite:** relatório de ingestão e `metadados_indice` informam "tokenizer real" ou "estimativa".

---

## Épico: Busca

### TASK-007 · Ampliar o conjunto de avaliação e as métricas
- **Prioridade:** 🔴 Alta · **Esforço:** M · **Tipo:** teste · **Status:** Concluída (933bc39)
- **Origem:** diagnóstico (M24)
- **Contexto:** hoje são 19 perguntas, só sobre os 6 Markdown de exemplo (os PDFs são 97% dos chunks), com métrica única hit@5 por documento e nenhum caso sem resposta.
- **O que fazer:** 60 ou mais perguntas cobrindo os PDFs, casos negativos (devem voltar vazios) e métricas hit@k, MRR e recall por chunk; meta mínima configurável.
- **Critérios de aceite:** `docserver avaliar` imprime as novas métricas por modo; a meta mínima pode ser checada em CI (TASK-031).
- **Bloqueia:** TASK-009, TASK-024 (calibração).

### TASK-008 · Pesos BM25 por coluna e caminhos `UNINDEXED`
- **Prioridade:** 🔴 Alta · **Esforço:** P · **Tipo:** melhoria · **Status:** Concluída (78cbd4c)
- **Origem:** diagnóstico (M7)
- **Contexto:** `bm25(chunks)` pondera igualmente caminhos, título, seção e texto; palavras nos caminhos ("api", "Data Engineering") inflam todos os chunks do arquivo.
- **O que fazer:** marcar `caminho_origem`/`caminho_normalizado` como `UNINDEXED` e usar `bm25(chunks, 0, 0, 2.0, 3.0, 1.0)` ou similar; migrar índices existentes (exige reingestão).
- **Critérios de aceite:** avaliação (TASK-007) não piora; consulta "api" deixa de favorecer chunks só pelo caminho.

### TASK-009 · Reranker cross-encoder sobre os candidatos fundidos
- **Prioridade:** 🔴 Alta · **Esforço:** G · **Tipo:** melhoria · **Status:** Concluída (`d736053`, `a23f5b6`)
- **Origem:** diagnóstico (C3, parte pendente); fase futura em `ARQUITETURA.md`
- **Contexto:** o corte por cobertura léxica melhorou "rate limit da API", mas ainda vêm trechos do livro com "limit" e "API" em outro sentido.
- **O que fazer:** cross-encoder multilíngue leve (ex.: `BAAI/bge-reranker-v2-m3` ou menor) sobre ~20 candidatos; opcional por extra de instalação; pré-carregado no aquecimento.
- **Critérios de aceite:** ganho mensurável na avaliação; latência por consulta em CPU medida e documentada; sem a extra, a busca funciona como hoje.
- **Dependências:** TASK-007.
- **Feito:** `src/docserver/rerank.py` com `mminilm` (`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, padrão) e `bge-m3` (`BAAI/bge-reranker-v2-m3`), escolhidos pela env `RERANKER`; nota 0–1 por sigmoide dos logits; `buscar_hibrido` repontua os 20 primeiros da fusão e corta abaixo de `RERANK_MINIMO` (padrão 0.01); falha no reranker cai na ordem híbrida com aviso; instalação só léxica não liga o reranker. `search --sem-rerank`, `avaliar --rerankers`, aquecimento no servidor.
- **Resultado (números em `docs/ARQUITETURA.md`):** corpus local hit@1 90% → 97%, hit@5 92% → 97%, trecho@5 85% → 92%; demo hit@1 90% → 95%. Custo: ~3 s por busca em CPU (contra ~70 ms). O `bge-m3` levou ~35 s por busca e estourou a RAM de 8 GB. Pesos BM25 da TASK-008 mantidos.
- **Verificação real (2026-09-15):** reingestão do corpus do esquema v1 → v4 em 36,5 min (6 109 chunks); segunda rodada em 2,4 s ("Inalterados: 11"); `search` mostra a página; `ler_documento` do livro devolve "parte 1 de 52"; `ler_trecho` com id de `buscar`; `pytest -m lento` verde. Busca concorrente com ingestão e watcher parado por mais de 1 h ficaram cobertos só pelos testes automatizados (WAL e filtro por `stat`).
- **Ficou para depois:** as negativas ainda são o ponto fraco (só 27% voltam vazias no corpus local; um corte maior derruba acertos); a latência de ~3 s poderia cair repontuando menos candidatos (`N_CANDIDATOS_RERANK` não é configurável por env). Ver TASK-024.

### TASK-024 · Limiar vetorial relativo ou calibrado
- **Prioridade:** 🟡 Média · **Esforço:** M · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** diagnóstico (M8)
- **Contexto:** o corte absoluto de 0.85 foi calibrado num único corpus; o e5-small comprime similaridades entre 0.7 e 0.9.
- **Critérios de aceite:** limiar definido a partir da avaliação (incluindo casos negativos) ou relativo ao top-1, com justificativa em `ARQUITETURA.md`.
- **Dependências:** TASK-007.

### TASK-025 · Validar `limite` e tornar o nº de candidatos proporcional
- **Prioridade:** 🟡 Média · **Esforço:** P · **Tipo:** bug · **Status:** Backlog
- **Origem:** diagnóstico (M10)
- **O que fazer:** normalizar `1 ≤ limite ≤ 20` na CLI e nas tools; candidatos por ramo `k = max(20, 4 × limite)`.
- **Critérios de aceite:** `limite=0`, negativo ou 1000 não quebram nem devolvem volume excessivo; testes cobrindo os limites.

### TASK-026 · Diversidade nos resultados (MMR ou colapso de adjacentes)
- **Prioridade:** 🟡 Média · **Esforço:** M · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** diagnóstico (M12)
- **Contexto:** o top-5 pode trazer chunks consecutivos do mesmo trecho, reforçados pelo overlap de 50 tokens.
- **Critérios de aceite:** chunks adjacentes do mesmo documento são colapsados ou penalizados; avaliação não piora.

### TASK-037 · Stopwords em inglês e stemming em português
- **Prioridade:** 🟢 Baixa · **Esforço:** M · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** diagnóstico (M9)
- **Contexto:** a lista de stopwords é curta, tem duplicatas ("e", "esta", "as") e não inclui inglês; "pagamento" ≠ "pagar".
- **Critérios de aceite:** lista deduplicada com PT + EN; stemming (RSLP/Snowball) numa coluna auxiliar, avaliado pela TASK-007.

### TASK-038 · Partition key por documento no `vec0`
- **Prioridade:** 🟢 Baixa · **Esforço:** M · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** diagnóstico (M11)
- **Contexto:** o filtro por documento no KNN faz varredura exata; aceitável hoje, caro com dezenas de livros.
- **Critérios de aceite:** `caminho_origem` como partition key; busca com `documento` mantém os mesmos resultados.

---

## Épico: Servidor MCP

### TASK-001 · Paginar `ler_documento` e criar leitura por trecho com vizinhos
- **Prioridade:** 🔴 Alta · **Esforço:** M · **Tipo:** melhoria · **Status:** Concluída (a8ffaac)
- **Origem:** diagnóstico (A1)
- **Contexto:** o livro normalizado tem ~1 MB (~250 mil tokens). Uma chamada a `ler_documento` estoura a janela de contexto de praticamente qualquer agente, e a docstring de `buscar` incentiva essa chamada.
- **O que fazer:** parâmetros `secao` e `inicio`/`fim` (por `ordem` de chunk), limite padrão de tamanho com aviso de continuação; nova tool `ler_trecho(id, vizinhos=1)` (padrão *small-to-big*); ajustar as docstrings.
- **Critérios de aceite:** `ler_documento` do livro devolve no máximo o limite configurado, com instrução de como continuar; `ler_trecho` devolve o chunk e os adjacentes; testes para os dois.

### TASK-002 · Fallback para busca léxica quando não há vetores ou o modelo falha
- **Prioridade:** 🔴 Alta · **Esforço:** P · **Tipo:** bug · **Status:** Concluída (5079369)
- **Origem:** diagnóstico (A2)
- **Contexto:** `reindexar` apaga as linhas de `chunks_vec`, mas a tabela e `metadados_indice` continuam, e `_tabela_vetorial_existe` segue `True`. Após `ingest --sem-embeddings` sobre um índice vetorial, `buscar_hibrido` tenta carregar o modelo; sem a extra `embeddings`, isso gera `ImportError` em vez do fallback prometido. `ErroModeloDivergente` também chega cru ao agente.
- **O que fazer:** dropar `chunks_vec`/metadados quando não houver embeddings; checar se há linhas, não só a tabela; capturar `ImportError`/`ErroModeloDivergente` e degradar para léxico com aviso no resultado.
- **Critérios de aceite:** testes para reingestão `--sem-embeddings` sobre índice vetorial e para modelo divergente, ambos devolvendo resultados léxicos com aviso.

### TASK-014 · Servidor abre o índice somente leitura e sem escrita em consultas
- **Prioridade:** 🟡 Média · **Esforço:** P · **Tipo:** débito técnico · **Status:** Backlog
- **Origem:** diagnóstico (A4)
- **Contexto:** `buscar_vetorial` chama `_validar_ou_registrar_modelo`, que pode escrever em `metadados_indice` durante uma consulta; `criar_indice` executa `CREATE ... IF NOT EXISTS` ao abrir.
- **O que fazer:** conexão do servidor com `mode=ro` (URI), separando "abrir para consulta" de "criar/registrar" (usado só na ingestão).
- **Critérios de aceite:** nenhuma escrita no índice durante `buscar`/`listar_documentos`/`ler_documento` (teste com arquivo somente leitura).
- **Relacionada:** TASK-003 (WAL e `mode=ro` precisam ser testados juntos).

### TASK-027 · Paginação e filtro em `listar_documentos`
- **Prioridade:** 🟡 Média · **Esforço:** P · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** diagnóstico (M19)
- **Critérios de aceite:** parâmetros `prefixo`, `com_secoes` e paginação; a listagem padrão fica limitada, com instrução de como ver mais.

### TASK-028 · Resultados estruturados (JSON) nas tools
- **Prioridade:** 🟡 Média · **Esforço:** M · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** diagnóstico (M20)
- **O que fazer:** usar *structured output* do MCP com origem, seção, página, ordem, id, score e texto.
- **Critérios de aceite:** clientes com suporte recebem estrutura; clientes sem suporte continuam recebendo texto legível.
- **Relacionada:** TASK-006 (página).

### TASK-029 · Logging estruturado de consultas
- **Prioridade:** 🟡 Média · **Esforço:** P · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** diagnóstico (M22)
- **O que fazer:** log em stderr (nunca stdout no stdio) com consulta, modo, nº de resultados, resultados vazios, erros e latência.
- **Critérios de aceite:** logs presentes nos transportes stdio e HTTP sem quebrar o protocolo; opção para desligar ou anonimizar as consultas.

### TASK-043 · Expor documentos como resources MCP
- **Prioridade:** 🟢 Baixa · **Esforço:** M · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** diagnóstico (M21)
- **Critérios de aceite:** documentos listados como `doc://<origem>` e anexáveis pelo cliente; respeita a mesma resolução pelo índice de `ler_documento`.

### TASK-044 · Enxugar a docstring de `buscar` e usar `instructions` do servidor
- **Prioridade:** 🟢 Baixa · **Esforço:** P · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** diagnóstico (M23)
- **Contexto:** a docstring tem ~200 palavras e é consumida em toda conversa.
- **Critérios de aceite:** docstring curta; a orientação de fluxo fica em `FastMCP(instructions=...)`; `docs/AGENTES.md` atualizado.

---

## Épico: Segurança e infraestrutura

### TASK-010 · Autenticação por token no modo HTTP
- **Prioridade:** 🔴 Alta · **Esforço:** M · **Tipo:** melhoria · **Status:** Backlog
- **Origem:** diagnóstico (A6)
- **Contexto:** `serve --http` e `server-mcp --local` expõem toda a documentação sem controle de acesso (o `server-mcp --local` já avisa, mas não protege).
- **O que fazer:** `Authorization: Bearer <token>` via auth do FastMCP, com token por variável de ambiente; aviso quando o bind não for loopback e não houver token.
- **Critérios de aceite:** requisição sem token recebe 401; `docs/AGENTES.md` explica como configurar o token nos clientes.

### TASK-011 · `docker-compose.yml` sem TTY e `DEPLOY.md` atualizado sobre HTTP
- **Prioridade:** 🔴 Alta · **Esforço:** P · **Tipo:** bug · **Status:** Backlog
- **Origem:** diagnóstico (I4)
- **Contexto:** `tty: true` converte `\n` em `\r\n` e corrompe o JSON-RPC via stdio. `docs/DEPLOY.md` ainda diz que HTTP "está fora de escopo", mas o modo HTTP já existe.
- **Critérios de aceite:** compose com `stdin_open: true` sem TTY (ou serviço HTTP com porta publicada); cliente MCP conecta ao container; `DEPLOY.md` corrigido.

### TASK-030 · Lockfile e limites superiores de versão nas dependências
- **Prioridade:** 🟡 Média · **Esforço:** P · **Tipo:** infra · **Status:** Backlog
- **Origem:** diagnóstico (I1)
- **Contexto:** `fastmcp>=2.0` instalou 4.0.3, `markitdown` veio em beta, `transformers` 5.x; `watchdog>=4.0` também está aberto.
- **Critérios de aceite:** lockfile versionado (`uv.lock` ou `requirements.lock`) e limites de major no `pyproject.toml`; instalação reprodutível documentada no README.

### TASK-031 · Versão de Python de referência e CI no GitHub Actions
- **Prioridade:** 🟡 Média · **Esforço:** M · **Tipo:** infra · **Status:** Backlog
- **Origem:** diagnóstico (I2)
- **Contexto:** venv em Python 3.14, Docker em 3.11, sem CI.
- **Critérios de aceite:** workflow rodando `pytest` em Windows e Linux na versão mínima e na de referência; opcionalmente a avaliação da TASK-007 com meta mínima.

### TASK-032 · Revisão fixa do modelo de embeddings
- **Prioridade:** 🟡 Média · **Esforço:** P · **Tipo:** infra · **Status:** Backlog
- **Origem:** diagnóstico (I3)
- **Critérios de aceite:** `revision=` fixo no código e no Dockerfile; revisão gravada em `metadados_indice` e verificada como o nome do modelo.

### TASK-045 · Revisar a necessidade de `libgl1` no Dockerfile
- **Prioridade:** 🟢 Baixa · **Esforço:** P · **Tipo:** infra · **Status:** Backlog
- **Origem:** diagnóstico (I5)
- **Atenção:** o README (instalação Linux) orienta instalar `libgl1` quando aparece `ImportError: libGL.so.1`, então alguma dependência precisa dela. Confirmar qual antes de remover.
- **Critérios de aceite:** decisão documentada; se removida, imagem menor e ingestão de PDF/DOCX funcionando no container.

### TASK-046 · Healthcheck e warm-up na imagem Docker
- **Prioridade:** 🟢 Baixa · **Esforço:** P · **Tipo:** infra · **Status:** Backlog
- **Origem:** diagnóstico (I6)
- **Critérios de aceite:** `HEALTHCHECK` no modo HTTP; modelo pré-carregado na subida do container.

### TASK-047 · Aviso sobre não publicar índices com conteúdo licenciado
- **Prioridade:** 🟢 Baixa · **Esforço:** P · **Tipo:** docs · **Status:** Backlog
- **Origem:** diagnóstico (I8)
- **Contexto:** `data/indice.db` e `docs-normalizado/` contêm o texto integral dos PDFs (inclusive um livro comercial), mesmo com os PDFs no `.gitignore`.
- **Critérios de aceite:** nota no README e em `DEPLOY.md`; conferir que `data/` e `docs-normalizado/` não vão para a imagem Docker nem para o Git por padrão.

---

## Épico: Testes e CLI

### TASK-033 · Teste E2E do servidor com cliente MCP e cwds diferentes
- **Prioridade:** 🟡 Média · **Esforço:** M · **Tipo:** teste · **Status:** Backlog
- **Origem:** diagnóstico (seção 7)
- **Contexto:** o bug C1 passou pelos testes porque ingestão e leitura usavam os mesmos caminhos absolutos.
- **Critérios de aceite:** teste com `fastmcp.Client` (in-memory ou subprocesso) ingerindo com caminhos relativos em um cwd e servindo com absolutos em outro, chamando as três tools.

### TASK-048 · Reduzir o tempo da suíte de testes rápida
- **Prioridade:** 🟢 Baixa · **Esforço:** P · **Tipo:** teste · **Status:** Backlog
- **Origem:** diagnóstico (seção 7)
- **Contexto:** a suíte "rápida" leva de 25 a 95 s, provavelmente pela carga do tokenizer real e pela extração de PDF em testes não marcados como `lento`.
- **Critérios de aceite:** `pytest --durations=15` analisado; testes pesados marcados ou com fixtures em escopo de sessão; suíte padrão abaixo de 20 s.

### TASK-049 · Remover código morto em `formatar_tabela_avaliacao`
- **Prioridade:** 🟢 Baixa · **Esforço:** P · **Tipo:** débito técnico · **Status:** Concluída (933bc39)
- **Origem:** diagnóstico (M25)
- **Contexto:** a função `_somar` nunca é usada e a largura reservada para a linha "geral" nunca é impressa.
- **Critérios de aceite:** ou a linha "geral" passa a ser impressa, ou o código morto é removido.
- **Relacionada:** TASK-007 (a tabela vai mudar).

### TASK-050 · `docserver stats` mostrar a data da ingestão
- **Prioridade:** 🟢 Baixa · **Esforço:** P · **Tipo:** bug · **Status:** Backlog
- **Origem:** diagnóstico (M26)
- **Contexto:** o help promete "data da ingestão", mas o comando não mostra.
- **Critérios de aceite:** data da última ingestão gravada em `metadados_indice` e exibida em `stats`.

---

## Concluídas

| ID | Título | Concluída em | Commit |
|---|---|---|---|
| — | C1–C6 do diagnóstico (caminhos no índice, chunk completo no MCP, corte léxico, proteções de ingestão, colisão de nomes, cold start) | 2026-09-14 | `6cdb0aa` |
| — | Ingestão automática com `docserver watch` | 2026-09-14 | `88cffa4` |
| TASK-003 | Ativar `journal_mode=WAL` no índice SQLite | 2026-09-15 | `334a281` |
| TASK-004 | Embeddings em lote (medição em CPU não mostrou ganho com lotes > 1; padrão ficou 1, ajustável por `EMBEDDINGS_TAMANHO_LOTE`) | 2026-09-15 | `124a2da` |
| TASK-002 | Fallback para busca léxica quando não há vetores ou o modelo falha | 2026-09-15 | `5079369` |
| TASK-007 | Ampliar o conjunto de avaliação e as métricas (73 perguntas no corpus local, linha de base registrada) | 2026-09-15 | `933bc39` |
| TASK-049 | Remover código morto em `formatar_tabela_avaliacao` (junto com a TASK-007) | 2026-09-15 | `933bc39` |
| TASK-008 | Pesos BM25 por coluna e caminhos `UNINDEXED` (+ versão do esquema do índice) | 2026-09-15 | `78cbd4c` |
| TASK-006 | Números de página nos chunks de PDF | 2026-09-15 | `84e63ab` |
| TASK-012 | Eliminar o `UnicodeDecodeError` do Tesseract (`use_ocr=False`) | 2026-09-15 | `84e63ab` |
| TASK-005 | Ingestão incremental por sha256, numa transação única | 2026-09-15 | `a8b7737` |
| — | Watcher ignora eventos de último acesso (cada ingestão disparava a próxima) | 2026-09-15 | `c5aa97c` |
| TASK-001 | `ler_documento` em partes e por seção + tool `ler_trecho` | 2026-09-15 | `a8ffaac` |
| TASK-009 | Reranker cross-encoder (mMiniLM por padrão, calibrado pela avaliação) | 2026-09-15 | `d736053`, `a23f5b6` |
