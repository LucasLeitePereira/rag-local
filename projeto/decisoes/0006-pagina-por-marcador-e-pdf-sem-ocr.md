# 0006 · Página de PDF por marcador no Markdown; extração sem OCR

- **Data:** 2026-09-15 · **Status:** Aceita
- **Tarefa:** TASK-006, TASK-012 · **Commit:** `84e63ab`

## Contexto
- **Página:** o agente não conseguia citar a página de um trecho de PDF.
- **Tesseract:** a cada PDF, o `pymupdf4llm` procurava o Tesseract e
  imprimia um `UnicodeDecodeError` (saída em cp850 no Windows). Isso gerava
  8 warnings na suíte e tracebacks na ingestão.

## Alternativas consideradas
- **Página só no índice**, calculada na extração — o `docs-normalizado/`
  deixaria de bastar para reindexar sem reextrair.
- **Marcador no Markdown normalizado** — o chunking deduz a página.
- **Para o Tesseract:** instalar e configurar, ou desligar o OCR. OCR de
  verdade para PDF escaneado ficou como TASK-017.

## Decisão
- **Extração:** `pymupdf4llm.to_markdown(page_chunks=True, use_ocr=False)`,
  com um `<!--pagina:N-->` numa linha própria antes de **toda** página, mesmo
  vazia.
- **Chunking:** cada chunk recebe `pagina_inicio` e `pagina_fim`, e o texto
  antes do marcador N é da página N-1.
- **Leitura:** os marcadores saem do texto dos chunks e do `ler_documento`.

## Consequências
- **Saída da busca:** mostra `p. N` ou `pp. N–M`, e as páginas continuam
  certas na cauda de sobreposição entre chunks.
- **Fallback:** o `markitdown` não tem marcadores e deixa a página nula.
- **PDF escaneado:** continua sem texto e só aparece como "suspeito".
