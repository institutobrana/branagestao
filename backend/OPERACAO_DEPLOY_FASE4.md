# Operacao de Deploy - Fase 4

## Objetivo
Padronizar comportamento de startup por ambiente, manter healthcheck leve e formalizar execucao de scripts manuais com rastreabilidade.

## Politica por ambiente

### `local`
- `BRANA_RUNTIME_PROFILE=local`
- `BRANA_ENABLE_SCHEMA_BOOTSTRAP=1` (padrao)
- `BRANA_ENABLE_RUNTIME_BOOTSTRAP=1` (padrao)
- `BRANA_ALLOW_HTTP_RUNTIME_BOOTSTRAP=0` (recomendado)

### `staging`
- `BRANA_RUNTIME_PROFILE=staging`
- `BRANA_ENABLE_SCHEMA_BOOTSTRAP=0`
- `BRANA_ENABLE_RUNTIME_BOOTSTRAP=0`
- `BRANA_ALLOW_HTTP_RUNTIME_BOOTSTRAP=0`

### `prod`
- `BRANA_RUNTIME_PROFILE=prod`
- `BRANA_ENABLE_SCHEMA_BOOTSTRAP=0`
- `BRANA_ENABLE_RUNTIME_BOOTSTRAP=0`
- `BRANA_ALLOW_HTTP_RUNTIME_BOOTSTRAP=0`
- `BRANA_ALLOW_SCHEMA_COMPAT_APPLY=0`

## Healthcheck
- Endpoint de health: `GET /health`
- Sem dependencias de job pesado ou migracao.
- Retorna status e policy efetiva de runtime.

## Scripts manuais

### Compatibilidade de schema/dados (Fase 2)
Executar somente em janela de manutencao:

```bash
python scripts/aplicar_compatibilidade_schema.py
```

### Bootstrap global de runtime (Fase 3)
Executar sob demanda:

```bash
python scripts/executar_bootstrap_runtime_global.py
```

## Auditoria operacional
- Runtime bootstrap: `backend/backups/runtime_bootstrap_audit.jsonl`
- Campos: `source`, `actor`, `profile`, `ok`, `skipped`, `reason`, `duration_ms`, `jobs`.

## Checklist antes de subir
1. Conferir variaveis em `render.yaml`.
2. Garantir que scripts manuais nao estao rodando em paralelo.
3. Validar `GET /health` apos deploy.
4. Registrar janela e operador para qualquer script manual.
