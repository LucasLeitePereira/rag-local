# Ingestão

## Como adicionar documentos

Copie (ou mova) os arquivos para `docs-fonte/`, em qualquer estrutura de
pastas — ela é espelhada em `docs-normalizado/`. Depois rode:

```bash
docserver ingest
```

O comando reindexa **tudo** do zero a cada execução: não existe indexação
incremental (ver `docs/ARQUITETURA.md`). Rode de novo sempre que adicionar,
editar ou remover arquivos em `docs-fonte/`.

**Remover um arquivo de `docs-fonte/` e rodar `docserver ingest` já basta** —
a ingestão apaga automaticamente o `.md` correspondente em
`docs-normalizado/` (e o retira do índice) quando a fonte original não existe
mais, listado como "Removidos" no relatório. Isso existe para não deixar
documentação obsoleta sendo servida por `ler_documento` ou aparecendo em
`listar_documentos` — foi exatamente um `.md` órfão desses (de um PDF já
apagado de `docs-fonte/`, indexado numa ingestão anterior) que causou uma
busca sobre um documento misturar trechos de outro completamente diferente.

Flags úteis:

```bash
docserver ingest --limpar           # apaga docs-normalizado/ e o índice antes de reingerir
docserver ingest --sem-embeddings   # pula a camada vetorial — ingestão bem mais rápida em dev
```

## Formatos suportados

| Extensão | Estratégia |
|---|---|
| `.md`, `.markdown`, `.txt` | cópia direta |
| `.docx`, `.pptx`, `.xlsx`, `.html` | `markitdown` |
| `.pdf` | `pymupdf4llm` (com limpeza de artefatos de formatação); se sair com menos de ~200 caracteres, cai para `markitdown` |
| `.csv` | vira tabela Markdown |

Qualquer outra extensão é ignorada (aparece em "Ignorados" no relatório, não
derruba a ingestão). Arquivos ocultos (começam com `.`) e temporários do
Office (`~$arquivo.docx`) também são ignorados silenciosamente.

## Lendo o relatório de ingestão

```
Ingestão concluída em 4.2s

  Arquivos processados:   38
  Chunks indexados:      412
  Ignorados (formato):     3
  Falhas de extração:      1
  Suspeitos (texto vazio): 2
  Removidos (órfãos):      1

Falhas:
  ✗ docs-fonte/antigo/manual.doc — formato .doc não suportado (converta para .docx)

Suspeitos (provável PDF escaneado, sem texto extraível):
  ? docs-fonte/legado/fluxo-2019.pdf

Removidos (fonte original não existe mais):
  - docs-normalizado/legado/contrato-antigo.md
```

- **Ignorados** — extensão sem extrator registrado. Converta o arquivo para
  um formato suportado, ou registre um extrator novo (veja abaixo).
- **Falhas** — o extrator foi chamado mas levantou uma exceção (arquivo
  corrompido, senha protegendo o arquivo, etc.). O restante do lote continua
  normalmente.
- **Suspeitos** — a extração rodou sem erro, mas o resultado ficou vazio ou
  quase vazio. O caso mais comum é PDF escaneado sem OCR (fora de escopo
  desta versão — veja `docs/ARQUITETURA.md`).
- **Removidos** — o `.md` normalizado existia de uma ingestão anterior, mas a
  fonte em `docs-fonte/` não existe mais (foi apagada, renomeada, ou passou a
  falhar na extração). O arquivo é apagado de `docs-normalizado/` e sai do
  índice na mesma ingestão.

## Quando a extração sai ruim

1. Abra o arquivo correspondente em `docs-normalizado/` e compare com o
   original — o Markdown intermediário existe justamente para essa inspeção.
2. Para PDFs com texto embaralhado ou incompleto, o front matter do arquivo
   normalizado registra qual extrator foi usado (`pymupdf4llm` ou
   `markitdown`); no atual não há como forçar manualmente um extrator por
   arquivo — ajuste `_extrair_pdf` em `src/docserver/extract.py` se um dos
   dois for consistentemente melhor para o seu tipo de PDF. `pymupdf4llm` às
   vezes fragmenta palavras em runs de 1-3 caracteres por variação de fonte
   no PDF original (ex.: PDFs com kerning por caractere) — `_limpar_markdown_pdf`
   tira o negrito/tachado espúrio ao redor dessas runs, mas não reconstrói a
   palavra partida; isso fica visível comparando o `.md` normalizado com o
   PDF original.
3. Para planilhas grandes ou complexas, `markitdown` extrai uma
   representação em texto/tabela — formatação, fórmulas e gráficos não são
   preservados.

## Adicionando um extrator novo

A arquitetura é plugável: um extrator é uma função `Path -> str` registrada
no dicionário `EXTRATORES`, em `src/docserver/extract.py`.

```python
def _extrair_rtf(caminho: Path) -> str:
    # sua lógica de conversão para Markdown aqui
    ...
    return texto_em_markdown

EXTRATORES[".rtf"] = _extrair_rtf
```

Se a extração puder falhar, deixe a exceção propagar normalmente —
`extrair_texto` a envolve em `ErroDeExtracao`, e a ingestão já sabe
registrar isso no relatório sem derrubar o processo.
