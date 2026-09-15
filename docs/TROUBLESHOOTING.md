# Troubleshooting

## A busca não encontra nada

1. Rode `docserver stats` — se `Chunks indexados: 0`, a ingestão não rodou
   ou não encontrou nenhum arquivo suportado em `docs-fonte/`.
2. Rode `docserver ingest` de novo e confira o relatório: os arquivos que
   você espera aparecem em "Novos", "Alterados" ou "Inalterados", não em
   "Ignorados" ou "Falhas"?
3. Tente `docserver search "termo" --modo lexico` e depois `--modo vetorial`
   separadamente — se um dos dois encontra e o outro não, o problema está
   isolado a uma das duas camadas.
4. Peça ao agente para chamar `listar_documentos` — se o documento nem
   aparece na árvore, ele não foi indexado (volte ao passo 1).

## A busca mistura trechos de documentos diferentes

Se `buscar` devolve trechos que claramente não têm nada a ver com a
pergunta, ou de um documento diferente do que se esperava:

1. Passe `documento` (caminho, parcial ou só o nome do arquivo) para
   restringir a busca a um único documento — é a forma mais direta de
   confirmar se o problema é o índice ter mais de um documento com
   vocabulário parecido.
2. Rode `docserver ingest` de novo e confira "Removidos" no relatório — um
   `.md` de uma ingestão anterior cuja fonte em `docs-fonte/` foi apagada ou
   renomeada fica órfão em `docs-normalizado/` até a próxima ingestão limpar
   isso (ver `docs/INGESTAO.md`). Foi exatamente esse cenário — um PDF
   apagado da fonte mas ainda indexado — que originalmente causava esse tipo
   de mistura.
3. Se mesmo assim um resultado claramente irrelevante aparecer, é o corte de
   relevância que precisa de ajuste (ver `docs/ARQUITETURA.md`) — aumente
   `COBERTURA_LEXICA_MINIMA` se o ruído vem de termos comuns da consulta, ou
   `SIMILARIDADE_MINIMA` se vem da via vetorial. Se, ao contrário, acertos
   legítimos somem, reduza-os.

## `docserver ingest` abortou ("Ingestão abortada: ...")

A ingestão se recusa a apagar dados por engano e, nesses casos, não altera
nem `docs-normalizado/` nem o índice (ver "Proteções contra perda de dados"
em `docs/INGESTAO.md`):

- **"pasta de documentos de origem não encontrada"** — confira o
  `--docs-fonte` e o diretório de onde o comando foi executado.
- **"nenhum arquivo em formato suportado"** ou **"não gerou nenhum chunk"** —
  se a intenção é mesmo esvaziar o índice, repita com `--forcar`.

## "Aviso: busca semântica indisponível (...)"

`buscar` (e `docserver search`) não conseguiu usar a camada vetorial e devolveu
só os resultados da busca léxica (BM25). O motivo vem entre parênteses:

- **`No module named 'sentence_transformers'`**: a extra `embeddings` não está
  instalada. Instale-a (ver README) ou reingira com `--sem-embeddings` para
  remover a camada vetorial de vez.
- **"o índice foi construído com o modelo ..."**: o índice foi gerado com
  outro modelo de embeddings. Rode `docserver ingest`: ao notar o modelo
  diferente, a ingestão reconstrói o índice inteiro.
- **Erro do sqlite-vec**: a extensão não carregou nesta máquina; reinstale as
  dependências.

Uma ingestão com `--sem-embeddings` sobre um índice que tinha vetores remove a
camada vetorial (o relatório avisa "Camada vetorial removida"); a busca fica
só léxica, sem aviso, até uma ingestão com embeddings.

## "Índice indisponível: o índice está num formato antigo"

O índice foi gravado por uma versão anterior do docserver, com outras colunas. Rode
`docserver ingest`: a ingestão detecta o formato e reconstrói o índice inteiro (o
relatório avisa). Enquanto isso não acontece, as tools respondem com essa mensagem
em vez de resultados.

## `docserver watch` não reagiu a uma mudança

1. Confira se a mudança foi num arquivo que a ingestão leria: formatos não
   suportados, arquivos ocultos (`.algo`), temporários do Office (`~$algo`) e
   pastas vazias são ignorados de propósito.
2. Espere o `--espera` (2 s por padrão) **sem novas mudanças**: enquanto um
   editor ou uma cópia continuam gravando, a contagem recomeça.
3. Se aparece `docserver: ingestão abortada: ...`, a mudança foi detectada, mas
   a ingestão se recusou a rodar (ver a seção anterior). O watcher não aceita
   `--forcar`; para esvaziar o índice de propósito, use `docserver ingest --forcar`.
4. Em **Linux**, o watcher depende de `inotify`, que não recebe eventos em
   volumes do Docker montados a partir de Windows/macOS, em `/mnt/c` do WSL2 e
   em compartilhamentos NFS/SMB. Nesses ambientes, rode `docserver ingest`
   manualmente (o modo polling é trabalho futuro, ver `docs/INGESTAO.md`). Em
   árvores muito grandes, aumente `fs.inotify.max_user_watches`.

## `ler_documento` responde "Documento não encontrado" para tudo

Índices criados antes da versão que passou a gravar o caminho normalizado
relativo (`api/contratos.md`) não são compatíveis: rode `docserver ingest` uma
vez. Se a mensagem for "está no índice, mas o arquivo normalizado não foi
encontrado", o `--docs-normalizado` passado ao `serve` não é a pasta usada na
ingestão.

## PDF virou texto embaralhado

Alguns PDFs (principalmente com layout em colunas, tabelas complexas, ou
fontes incomuns) confundem o extrator de texto. Abra o arquivo correspondente
em `docs-normalizado/` para confirmar o problema, e veja no front matter qual
extrator foi usado (`pymupdf4llm` ou `markitdown`). Se um dos dois for
consistentemente pior para o seu tipo de PDF, ajuste a lógica de fallback em
`_extrair_pdf` (`src/docserver/extract.py`) — por exemplo, invertendo a
ordem de tentativa para esse tipo de documento. Um sintoma específico do
`pymupdf4llm` é palavra fragmentada em runs de 1-3 caracteres (efeito de
kerning por caractere em alguns PDFs) — `_limpar_markdown_pdf` já remove o
negrito/tachado espúrio ao redor dessas runs, mas não reconstrói a palavra;
se isso for frequente no seu corpus, vale investir numa heurística de
remontagem específica.

## PDF escaneado sem texto (aparece como "suspeito")

O relatório de ingestão marca como suspeito qualquer arquivo cuja extração
resultou em texto vazio ou quase vazio — o caso mais comum é um PDF
escaneado (imagem, sem camada de texto). OCR está fora de escopo desta
versão (ver `docs/ARQUITETURA.md`, seção "Fase futura"). Solução prática
hoje: rode o PDF por uma ferramenta de OCR externa antes de colocá-lo em
`docs-fonte/`.

## O cliente MCP não conecta, ou conecta mas não acha nenhum documento

- O cliente sobe `docserver serve` num diretório que ele escolhe, não
  necessariamente o do projeto. Passe `--docs-normalizado` e `--indice` com
  caminhos **absolutos**, antes do `serve` (exemplos em `docs/AGENTES.md`).
  Sem isso, `listar_documentos` responde "Nenhum documento indexado" e
  `buscar` responde "Índice não encontrado em ...".
- Use o caminho absoluto do binário do venv como `command`: o cliente não
  ativa o venv, então `docserver` sozinho não está no `PATH`.
- Teste o comando exato da configuração a partir de outro diretório
  (ex.: `cd ~ && /caminho/.venv/bin/docserver --indice ... serve`). Ele deve
  ficar parado esperando entrada — se sair com erro, o cliente também falha.

## O agente ignora as ferramentas e responde de memória

- Confirme que o cliente MCP está de fato conectado ao `docserver` (veja
  `docs/AGENTES.md`) — muitos clientes mostram os servidores conectados e
  suas tools disponíveis numa tela de configuração.
- Reforce explicitamente no `CLAUDE.md` (ou equivalente) do projeto que o
  agente deve consultar `buscar` antes de responder — veja o exemplo em
  `docs/AGENTES.md`. A descrição da tool já orienta isso, mas instruções no
  system prompt do projeto ajudam a tornar o comportamento consistente.
- Alguns agentes só chamam ferramentas quando a pergunta menciona
  explicitamente o projeto ("de acordo com a documentação...") — vale testar
  reformular a pergunta do usuário dessa forma.

## O container não enxerga os arquivos

- Confirme que `docs-fonte/`, `docs-normalizado/` e `data/` existem na raiz
  do projeto **antes** de rodar `docker compose run` — os bind mounts do
  `docker-compose.yml` não criam a pasta do lado do host automaticamente em
  todas as versões do Docker.
- Edições em `docs-fonte/` feitas fora do container aparecem dentro dele
  imediatamente (bind mount), mas você ainda precisa rodar
  `docker compose run --rm docserver docserver ingest` para reindexar — o
  container não observa mudanças automaticamente (ver "Fase futura").
- Se o container foi construído com `--build-arg COM_EMBEDDINGS=false`, o
  índice vetorial nunca é criado — isso é esperado, não um bug; a busca cai
  para BM25 puro e registra um aviso no log.
