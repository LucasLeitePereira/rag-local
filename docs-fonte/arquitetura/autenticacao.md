# Autenticação

Como o sistema autentica usuários e serviços.

## Renovação de token

O refresh token tem validade de 30 dias e é rotacionado a cada uso: cada renovação invalida o refresh token anterior e emite um novo. O access token de curta duração (ver `AUTH_TOKEN_TTL`) é o que efetivamente autoriza cada requisição.

## Login

O login aceita e-mail e senha, ou OAuth2 via Google. Após três tentativas com senha incorreta, a conta é bloqueada por 15 minutos.

## Logout

O logout revoga o refresh token atual no servidor. Tokens de acesso já emitidos continuam válidos até expirar naturalmente — não há revogação de access token.
