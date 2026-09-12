# Ambiente local

Como configurar o ambiente de desenvolvimento deste projeto.

## Variáveis de ambiente

`AUTH_TOKEN_TTL` define o tempo de vida do access token em segundos. O padrão é 900 (15 minutos).

`DATABASE_URL` aponta para o banco Postgres local, no formato `postgres://usuario:senha@host:porta/banco`.

`LOG_LEVEL` controla a verbosidade dos logs (`debug`, `info`, `warning`, `error`). Em desenvolvimento, use `debug`.

## Subindo o projeto

Rode `docker compose up` na raiz do repositório. O serviço de API sobe na porta 8000 e o banco na 5432.

## Rodando os testes

`pytest` roda a suíte inteira. Testes marcados como lentos são pulados por padrão; para incluí-los, use `pytest -m lento`.
