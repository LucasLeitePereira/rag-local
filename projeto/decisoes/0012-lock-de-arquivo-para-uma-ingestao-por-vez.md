# 0012 · Lock de arquivo do sistema operacional para uma ingestão por vez

- **Data:** 2026-09-19 · **Status:** Aceita
- **Tarefa:** TASK-016 · **Commit:** `_a preencher_`

## Contexto
Nada impedia que `docserver watch` e `docserver ingest` rodassem ao mesmo
tempo sobre o mesmo índice — só uma frase em `docs/INGESTAO.md` pedindo para
não fazer isso. Duas ingestões simultâneas reescrevem `docs-normalizado/` e o
índice em paralelo, e o `ingest --limpar` chega a esvaziar o índice debaixo de
uma ingestão do watcher já em andamento.

## Alternativas consideradas
- **Arquivo de lock com PID, criado com `O_EXCL`** — é o padrão clássico, mas
  exige detectar o lock órfão de um processo morto. A checagem de "o PID ainda
  vive" não é portável: no Windows, `os.kill(pid, 0)` chama `TerminateProcess`
  e **mataria** o processo consultado. Restaria expirar o lock por tempo, o que
  erra nos dois sentidos (uma ingestão de 20 min parece órfã; um lock órfão
  bloqueia até o prazo).
- **Uma tabela de lock no próprio SQLite** — o índice pode não existir ainda, e
  um `BEGIN EXCLUSIVE` seguraria o banco durante os minutos de extração e
  embeddings, justamente o que a decisão [0001](0001-indice-em-modo-wal.md)
  evita para não travar o servidor.
- **Lock de byte do sistema operacional sobre um arquivo ao lado do índice.**

## Decisão
`cli.travar_ingestao(caminho_indice)` trava o primeiro byte de
`data/indice.db.lock` — `fcntl.flock` no Linux e no macOS, `msvcrt.locking` no
Windows. `executar_ingestao` roda inteira dentro desse contexto, e
`_comando_ingest` o estende para cobrir também o `--limpar`.

- **`docserver ingest`** não espera: aborta com `ErroIngestao`, código de saída
  1 e o PID de quem segura o lock.
- **`docserver watch`** espera até 5 minutos (`ESPERA_LOCK_WATCHER`): a mudança
  que o acordou continuaria pendente de qualquer forma.
- **Reentrância por thread:** um contador em memória permite que a mesma thread
  peça o lock de novo (`--limpar` seguido da ingestão). A chave inclui a thread
  de propósito — duas threads ingerindo ao mesmo tempo é exatamente o que o
  lock existe para impedir.
- **PID a partir do byte 1:** o byte 0 é o travado, e no Windows ler um trecho
  travado por outro processo falha. Gravar o PID depois dele deixa a mensagem
  de erro nomear o dono.

## Consequências
- **Lock órfão:** deixa de existir como problema. Quem mantém o lock é o SO; se
  o processo morre, o lock cai junto. Um `data/indice.db.lock` esquecido no
  disco não bloqueia nada, e a documentação diz explicitamente para **não**
  apagá-lo à mão.
- **Arquivo novo no disco:** `data/indice.db.lock` fica ao lado do índice.
  Entra no `.gitignore` junto com `data/*`, que já era ignorado.
- **Escopo:** o lock protege a escrita, não a leitura. O servidor MCP continua
  lendo o índice sem pedir nada, como antes.
- **A vigiar:** o watcher espera no máximo 5 minutos. Uma reingestão manual de
  corpus grande pode passar disso; nesse caso o watcher registra o erro e
  tenta de novo na próxima mudança, sem morrer.
