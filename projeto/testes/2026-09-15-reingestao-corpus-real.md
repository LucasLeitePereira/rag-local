# Reingestão do corpus real e verificação final da prioridade alta

- **Data:** 2026-09-15 · **Branch:** `feat/prioridade-alta` · **Commit:** `d736053` (ingestão) / `a23f5b6` (verificação)
- **Máquina:** Windows 11 Pro, CPU com 4 threads, 7,9 GB de RAM (~3 GB livres com o resto aberto), sem GPU, Python 3.14.
- **Corpus:** 11 documentos em `docs-fonte/`: 6 Markdown de demonstração e 5 PDFs locais, fora do Git (livro *Fundamentals of Data Engineering*, relatório de Niterói, manuais PeopleTools 8.57 `pt857tape` e `pt857tpcr`, calendário `f39476…`).

## 1. Reconstrução do índice (esquema v1 → v4)

Comando: `docserver ingest`, com o índice anterior no esquema v1 (6 029 chunks).

```text
Ingestão concluída em 2188.6s
  Novos:                   11
  Alterados:               0
  Inalterados (pulados):   0
  Removidos do índice:     0
  Chunks indexados:        6109 (6109 novos)
  Ignorados (formato):     0
  Falhas de extração:      0
  Suspeitos (texto vazio): 0
  Removidos (órfãos):      0
Índice reconstruído do zero: índice em formato antigo (versão 1).
Novos:
  + docs-fonte\(PO) Niteroi_Final_Report_v1.51-all.pdf
  + docs-fonte\api\contratos.md
  + docs-fonte\arquitetura\autenticacao.md
  + docs-fonte\arquitetura\visao-geral.md
  + docs-fonte\f39476e4f7addfe77e1d5d41f4c16eef.pdf
  + docs-fonte\Fundamentals of Data Engineering (Reis, JoeHousley, Matt) (Z-Library).pdf
  + docs-fonte\guias\ambiente-local.md
  + docs-fonte\processos\inadimplencia.md
  + docs-fonte\processos\onboarding.md
  + docs-fonte\pt857tape-b022020.pdf
  + docs-fonte\pt857tpcr-b022020.pdf
```

- **Tempo:** 2 188,6 s (36,5 min), na mesma faixa dos ~35 min da ingestão completa antiga. A reconstrução refaz todos os embeddings.
- **Chunks:** 6 109 no v4, contra 6 029 no v1. A diferença provavelmente vem da extração por página, que mudou a divisão dos PDFs (não investigado).
- **Tentativa anterior:** uma reingestão interrompida no dia anterior, no meio dos embeddings, não gravou nada. O índice v1 continuou íntegro, como esperado da transação única.
- **Tropeço:** `python -m docserver.cli ingest` sai em 1 s sem fazer nada, porque o módulo não tem `__main__`. Use o executável `venv/Scripts/docserver.exe`.

## 2. Reingestão sem mudanças

```text
Ingestão concluída em 2.4s

  Novos:                   0
  Alterados:               0
  Inalterados (pulados):   11
  Removidos do índice:     0
  Chunks indexados:        6109 (0 novos)
```

De 36,5 min para 2,4 s: só o sha256 dos 11 arquivos é calculado.

## 3. Verificação no índice real

| Item | Resultado |
|---|---|
| `pytest -q` | 194 passed, 3 deselected (85 s) |
| `pytest -m lento` | 3 passed (21 s): embeddings em lote reais, mMiniLM real |
| `docserver search "Application Engine" --documento pt857tape-b022020.pdf` | resultados com `(p. 19)`, `(pp. 15–16)`, `(pp. 155–156)`; 61 s no total, quase todo em carregar torch e os dois modelos numa CLI fria |
| `ler_documento` do livro | `[… — parte 1 de 52]`, 19 980 caracteres, rodapé `[Continua: ler_documento(caminho="…", parte=2)]` |
| `buscar` pelo servidor, após `_aquecer` | 7,2 s na 1ª chamada, 3,1 s na 2ª; resultado com `chunk 315 · posição 155 · p. 92` |
| `ler_trecho(315, vizinhos=1)` | posições 154 a 156 de 0–804, com seção e páginas |
| Busca durante ingestão sem `database is locked` | **só por teste automatizado** (duas conexões, WAL); não reproduzido com processos reais |
| Watcher parado por mais de 1 h não se redispara | **só por teste automatizado** (filtro por `stat`); não observado em execução real |
