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

## PDF virou texto embaralhado

Alguns PDFs (principalmente com layout em colunas, tabelas complexas, ou
fontes incomuns) confundem o extrator de texto. Abra o arquivo correspondente
em `docs-normalizado/` para confirmar o problema, e veja no front matter qual
extrator foi usado (`markitdown` ou `pymupdf4llm`). Se um dos dois for
consistentemente pior para o seu tipo de PDF, ajuste a lógica de fallback em
`_extrair_pdf` (`src/docserver/extract.py`) — por exemplo, invertendo a
ordem de tentativa para esse tipo de documento.

## PDF escaneado sem texto (aparece como "suspeito")

O relatório de ingestão marca como suspeito qualquer arquivo cuja extração
resultou em texto vazio ou quase vazio — o caso mais comum é um PDF
escaneado (imagem, sem camada de texto). OCR está fora de escopo desta
versão (ver `docs/ARQUITETURA.md`, seção "Fase futura"). Solução prática
hoje: rode o PDF por uma ferramenta de OCR externa antes de colocá-lo em
`docs-fonte/`.

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
