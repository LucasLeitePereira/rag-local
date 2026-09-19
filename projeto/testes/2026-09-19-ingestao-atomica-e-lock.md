# Verificação real: troca atômica, lock e progresso da ingestão

- **Data:** 2026-09-19
- **Tarefas:** TASK-013, TASK-016, TASK-051
- **Máquina:** Windows 11 Pro 10.0.26200, Python 3.14, CPU
- **Corpus:** `docs-fonte/` do projeto — 11 documentos, 3378 chunks,
  `intfloat/multilingual-e5-small`
- **Comandos:** `docserver ingest` e `docserver watch` da instalação editável
  em `venv/`

Não são medições de desempenho: são as verificações de que os critérios de
aceite valem fora dos testes automatizados.

## Suíte automatizada

```
pytest tests/ -q     →  212 passed, 3 deselected em 41,5 s
```

Antes das mudanças eram 197. Os 15 novos estão em
`tests/test_ingestao_atomica.py`.

## 1. Ingestão incremental, nada mudou

```
extração: 0 arquivo(s) a processar, 11 inalterado(s)
gravando o índice
ingestão concluída em 1.9s
```

Tempo total 2,2 s. O progresso não custa nada quando não há trabalho.

## 2. Arquivo novo: progresso e tempo por etapa

Cópia do `2020-Scrum-Guide-PortugueseBR-3.0.pdf` (266 KB) sob outro nome:

```
extração: 1 arquivo(s) a processar, 11 inalterado(s)
[1/1] extraindo teste-task-051.pdf (266 KB)…
[1/1] teste-task-051.pdf: 29 chunks em 43.0s
embeddings: 29 chunk(s)
embeddings 25/29
embeddings 29/29
gravando o índice
ingestão concluída em 64.7s
```

Relatório final:

| Etapa | Tempo |
|---|---|
| Extração | 43,0 s |
| Embeddings | 20,1 s |
| Índice | 1,3 s |
| Troca (`os.replace`) | 0,0 s |

**Achado:** a extração do PDF custa mais do que o dobro dos embeddings. Até
aqui a suposição era a inversa — foi o que motivou a nota em
[`decisoes/0013`](../decisoes/0013-progresso-da-ingestao-por-callback.md) sobre
a prioridade de TASK-004 e TASK-017.

O custo da troca atômica é 0,0 s: mover os `.md` prontos é ruído perto de
qualquer outra etapa.

## 3. Lock: segunda ingestão simultânea (TASK-016)

Um processo segura o lock; um `docserver ingest` real tenta entrar:

```
dono real: 11408
stderr: Ingestão abortada: outra ingestão já está em andamento (PID 11408) e
segura o lock data\indice.db.lock. Nada foi alterado. Espere ela terminar, ou
pare o `docserver watch` antes de rodar `docserver ingest`.
```

Código de saída 1. Liberado o lock, a ingestão seguinte roda normalmente
(código 0).

O PID só aparece porque ele é gravado a partir do **byte 1**: no Windows, ler
o byte 0 — o travado — falha com violação de lock, e a mensagem saía sem o
dono. Foi corrigido depois desta primeira execução.

## 4. Troca atômica: `kill` durante os embeddings (TASK-013)

Fonte trocada por um PDF de 5,5 MB (508 chunks), ingestão morta com `kill` no
meio da etapa de embeddings:

```
antes:  .md 35961 bytes sha 962d05afefaf, 3407 chunks
matando durante: embeddings 25/508
depois: .md 35961 bytes sha 962d05afefaf, 3407 chunks

docs-normalizado intacto: True
indice intacto: True
```

É o critério de aceite da TASK-013, com um `kill` de verdade em vez de exceção
injetada.

O `kill` deixou para trás `.docs-normalizado.tmp-9200-362c54fc/` (o `finally`
não roda num `kill`) e o `data/indice.db.lock` (inofensivo: o lock do SO caiu
com o processo). A limpeza de pastas temporárias órfãs na partida da ingestão
foi acrescentada por causa disso.

## 5. Watcher (`docserver watch`)

Em pasta temporária, com `--sem-embeddings --espera 1`:

```
docserver: ingestão inicial
docserver: extração: 1 arquivo(s) a processar, 0 inalterado(s)
docserver: [1/1] extraindo inicial.md (1 KB)…
docserver: [1/1] inicial.md: 1 chunks em 12.5s
docserver: gravando o índice
docserver: observando ...\docs-fonte (Ctrl+C para sair)
docserver: 1 mudança(s) detectada(s), reingerindo
docserver: extração: 1 arquivo(s) a processar, 1 inalterado(s)
docserver: [1/1] extraindo novo.md (1 KB)…
docserver: [1/1] novo.md: 1 chunks em 0.0s
```

Os 12,5 s do primeiro arquivo são a carga do tokenizador, não o `.md` de 1 KB:
o mesmo arquivo na segunda ingestão leva 0,0 s. "Arquivo mais lento" precisa
ser lido com isso em mente quando há poucos arquivos.

## 6. Corpus restaurado

Arquivo de teste removido e `docserver ingest` rodado de novo: 11 documentos,
3378 chunks, nenhuma pasta `.docs-normalizado.tmp-*` — exatamente o estado
anterior à verificação.
