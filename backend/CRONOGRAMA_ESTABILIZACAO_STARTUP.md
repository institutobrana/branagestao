# Cronograma de Estabilizacao do Startup e Deploy

## Objetivo
Separar gradualmente bootstrap operacional, migracoes e seeds para reduzir risco de crash no startup, inconsistencias de dados e falhas de deploy.

## Fase 1 (executada) - Contencao imediata do startup
Status: CONCLUIDA em 2026-04-16

Escopo:
- Introduzir politica de bootstrap por ambiente via variaveis de ambiente.
- Permitir desativacao explicita do bootstrap de schema/dados no import.
- Permitir desativacao explicita da thread de bootstrap em runtime.
- Manter compatibilidade com a flag legada `BRANA_SKIP_BOOTSTRAP`.

Entregas:
- `BRANA_RUNTIME_PROFILE` (local/dev/development com comportamento padrao permissivo).
- `BRANA_ENABLE_SCHEMA_BOOTSTRAP` para controlar `create_all` + bloco de compatibilidade no import.
- `BRANA_ENABLE_RUNTIME_BOOTSTRAP` para controlar thread `_bootstrap_dados_iniciais`.
- Mensagens de startup explicitas quando bootstrap estiver desativado.

## Fase 2 - Extracao de migracoes do `main.py`
Status: CONCLUIDA em 2026-04-16

Escopo:
- Retirar DDL/DML de compatibilidade do import da API.
- Converter bloco de compatibilidade em scripts versionados e manuais.
- Definir checklist de execucao por janela de manutencao.

Entregas:
- Script manual versionado: `backend/scripts/aplicar_compatibilidade_schema.py`.
- Bloco de compatibilidade removido da execucao automatica no `main.py`.
- Startup da API sem aplicacao automatica de DDL/DML de compatibilidade.

## Fase 3 - Padronizacao seed x runtime
Status: CONCLUIDA em 2026-04-16

Escopo:
- Separar seeds de dados base de jobs de normalizacao global.
- Garantir idempotencia com auditoria de execucao.
- Bloquear reexecucoes perigosas em startup HTTP.

Entregas:
- Servico dedicado: `backend/services/runtime_bootstrap_service.py`.
- Execucao manual: `backend/scripts/executar_bootstrap_runtime_global.py`.
- Trilha de auditoria por execucao em `backend/backups/runtime_bootstrap_audit.jsonl`.
- Startup HTTP bloqueado por padrao para jobs globais, liberado somente com `BRANA_ALLOW_HTTP_RUNTIME_BOOTSTRAP=1`.

## Fase 4 - Hardening de deploy
Status: CONCLUIDA em 2026-04-16

Escopo:
- Definir politica unica por ambiente (local/staging/producao).
- Garantir healthcheck sem dependencias de jobs pesados.
- Criar trilha de auditoria operacional (quem executou, quando, impacto).

Entregas:
- Politica centralizada por ambiente em `backend/services/runtime_profile_service.py`.
- `main.py` usando politica unica para startup/health.
- `render.yaml` com `healthCheckPath: /health`.
- `render.yaml` com bloqueios explicitos de operacoes sensiveis (`BRANA_ALLOW_HTTP_RUNTIME_BOOTSTRAP=0`, `BRANA_ALLOW_SCHEMA_COMPAT_APPLY=0`).
- Trilha de auditoria de runtime bootstrap enriquecida com ator e profile.
- Guia operacional: `backend/OPERACAO_DEPLOY_FASE4.md`.

## Variaveis recomendadas
- `BRANA_RUNTIME_PROFILE=local|dev|development|staging|prod`
- `BRANA_ENABLE_SCHEMA_BOOTSTRAP=0|1`
- `BRANA_ENABLE_RUNTIME_BOOTSTRAP=0|1`
- `BRANA_ALLOW_HTTP_RUNTIME_BOOTSTRAP=0|1`
- `BRANA_ALLOW_SCHEMA_COMPAT_APPLY=0|1`
- `BRANA_SKIP_BOOTSTRAP=1` (legada, preservada)
