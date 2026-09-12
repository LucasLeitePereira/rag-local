# Visão geral da arquitetura

Como as peças do sistema se encaixam.

## Componentes

A API é um serviço Python que fala com um banco Postgres e uma fila Redis para processamento assíncrono. Um worker separado consome a fila para enviar e-mails e gerar relatórios pesados.

## Banco de dados

O schema principal fica no Postgres. Migrações são versionadas e aplicadas automaticamente no deploy — nunca à mão em produção.

## Cache

Respostas de leitura frequente ficam em cache no Redis por 5 minutos. Escrever um recurso invalida o cache correspondente na hora.
