import contextvars

# Variável global de requisição (thread safe)
tenant_clinica_id = contextvars.ContextVar("tenant_clinica_id")