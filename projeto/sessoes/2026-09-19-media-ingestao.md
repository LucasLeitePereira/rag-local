# Sessão 2026-09-19 · Prioridade média, épico Ingestão

Branch `feat/prioridade-alta`. Fechadas TASK-013, TASK-016 e TASK-051 — todas
as de prioridade média do épico Ingestão, exceto a TASK-015 (watcher em Linux),
deixada de fora por decisão do usuário: ela exige validar em Linux nativo,
Docker e WSL2, o que não dá para fazer desta máquina.

## O que foi feito

**TASK-013 · troca atômica.** A ingestão escrevia os `.md` direto em
`docs-normalizado/` durante a extração, antes dos embeddings. Agora eles vão
para uma pasta temporária irmã e são movidos com `os.replace` só depois do
commit do índice. Decisão [0011](../decisoes/0011-troca-atomica-por-pasta-temporaria.md).

**TASK-016 · lock.** `cli.travar_ingestao` trava um byte de
`data/indice.db.lock` com `fcntl.flock`/`msvcrt.locking`. `ingest` aborta na
hora nomeando o PID do dono; o watcher espera. Decisão
[0012](../decisoes/0012-lock-de-arquivo-para-uma-ingestao-por-vez.md).

**TASK-051 · progresso.** `progresso_fn` injetável em `executar_ingestao` e em
`embed.embeddar_passagens`, mais tempo por etapa e arquivo mais lento no
relatório. Decisão [0013](../decisoes/0013-progresso-da-ingestao-por-callback.md).

Arquivos tocados: `src/docserver/cli.py`, `src/docserver/embed.py`,
`src/docserver/watch.py`, `tests/test_ingestao_atomica.py` (novo),
`docs/INGESTAO.md`, `docs/TROUBLESHOOTING.md`, `.gitignore`.

Suíte: 197 → **212 testes**, todos passando. Verificação real registrada em
[`testes/2026-09-19-ingestao-atomica-e-lock.md`](../testes/2026-09-19-ingestao-atomica-e-lock.md).

## O que apareceu no caminho

- **A extração de PDF é o gargalo, não os embeddings.** 43,0 s contra 20,1 s
  num PDF de 266 KB. A suposição até aqui era a inversa. Isso muda a leitura de
  TASK-004 (lotes de embeddings, já concluída com ganho nulo — coerente com o
  achado) e sobe a importância de TASK-017 (OCR seletivo) e TASK-018.
- **`os.kill(pid, 0)` não serve como "o processo está vivo?" no Windows** — ele
  chama `TerminateProcess` e mataria o processo consultado. Foi o que levou ao
  lock de byte do SO em vez de um arquivo de PID com expiração.
- **No Windows não se lê um trecho travado do arquivo.** O PID do dono do lock
  é gravado a partir do byte 1 por isso; a primeira versão saía com a mensagem
  sem o PID.
- **Reentrância do lock tem de ser por thread, não por processo.** A primeira
  versão contava por processo, e o teste de duas ingestões concorrentes em
  threads passava por engano.
- **`kill -9` deixa a pasta temporária para trás.** A ingestão seguinte limpa as
  órfãs, já com o lock na mão — o que garante que nenhuma esteja em uso.

## Pendente

- **TASK-015** segue aberta: é a única de Ingestão que resta e depende de uma
  máquina Linux / Docker / WSL2 para validar.
- Próximas de prioridade média sugeridas pelo backlog: TASK-053 (chamadas de
  rede no startup do servidor) e TASK-014 (índice somente leitura no servidor).
