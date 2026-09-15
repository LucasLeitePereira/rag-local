# Registro do projeto

Memória de trabalho do docserver: o que planejamos, o que decidimos e por quê,
o que medimos e o que foi feito em cada sessão. A documentação de **uso**
(instalação, ingestão, agentes, arquitetura atual) continua em `docs/` e no
`README.md` da raiz.

| Pasta / arquivo | O que guarda |
|---|---|
| [`tasks.md`](tasks.md) | Backlog no estilo board: tarefas, status, commits |
| [`diagnostico.md`](diagnostico.md) | Diagnóstico técnico de 2026-09-14, origem das tarefas |
| [`planos/`](planos/) | Planos de implementação, datados |
| [`decisoes/`](decisoes/) | Um registro por decisão: contexto, alternativas, escolha, consequências |
| [`testes/`](testes/) | Medições, avaliações e verificações manuais, com os números brutos |
| [`sessoes/`](sessoes/) | Diário: o que foi feito em cada sessão de trabalho e o que ficou pendente |

## Convenções

- **Nomes de arquivo:** `AAAA-MM-DD-assunto.md` em `planos/`, `testes/` e
  `sessoes/`; `NNNN-assunto.md` em `decisoes/` (numeração sequencial, nunca
  reaproveitada).
- **Decisão nova:** copie o modelo de [`decisoes/README.md`](decisoes/README.md)
  e acrescente a linha no índice de lá. Decisão revista não é apagada: marque
  como "Substituída por NNNN" e crie a nova.
- **Números:** registre a máquina, o commit e o comando usado. Uma medição sem
  isso não dá para repetir.
- **Sem conteúdo licenciado:** trechos dos PDFs de `docs-fonte/` não entram
  aqui (eles não estão no Git). Guarde métricas e notas, não o texto.
- **`docs/ARQUITETURA.md` × `decisoes/`:** a arquitetura descreve como o sistema
  é hoje; a decisão conta como se chegou lá, inclusive o que foi descartado.
