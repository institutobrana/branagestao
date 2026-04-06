from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

# Contexto global do tenant
tenant_clinica_id = ContextVar("tenant_clinica_id", default=None)


def set_tenant_clinica_id(clinica_id):
    tenant_clinica_id.set(clinica_id)


def get_tenant_clinica_id():
    return tenant_clinica_id.get()


# ⭐ Middleware SaaS para capturar tenant da requisição
class TenantMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):

        # Aqui você pode capturar tenant via header, token ou domínio
        # Exemplo comum SaaS: Header X-Tenant-ID

        tenant_id = request.headers.get("X-Tenant-ID")

        if tenant_id:
            set_tenant_clinica_id(tenant_id)

        response = await call_next(request)

        return response