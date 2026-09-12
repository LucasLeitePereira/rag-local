# Contratos de API

Endpoints principais expostos pela API v2.

## Limites de requisição

O cliente pode fazer até 100 requisições por minuto por chave de API. Ao ultrapassar o limite, a API responde com status 429 e um cabeçalho `Retry-After` indicando quantos segundos esperar.

## Paginação

Listagens usam paginação por cursor: o parâmetro `cursor` na resposta aponta para a próxima página. Não existe paginação por número de página.

## Versionamento

A versão da API vai na URL (`/v2/...`). Versões antigas são mantidas por 12 meses após o lançamento de uma nova versão, com aviso de descontinuação no cabeçalho `Deprecation`.
