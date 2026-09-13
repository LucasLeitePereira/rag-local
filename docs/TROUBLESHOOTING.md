# Troubleshooting

## A busca não encontra nada

1. Rode `docserver stats` — se `Chunks indexados: 0`, a ingestão não rodou
   ou não encontrou nenhum arquivo suportado em `docs-fonte/`.
2. Rode `docserver ingest` de novo e confira o relatório: os arquivos que
   você espera aparecem em "Arquivos processados", não em "Ignorados"?
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
   relevância (`SIMILARIDADE_MINIMA`, ver `docs/ARQUITETURA.md`) que precisa
   de ajuste — aumente o valor via variável de ambiente se estiver frouxo
   demais para o seu corpus.

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
