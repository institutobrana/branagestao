from datetime import datetime

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from database import SessionLocal
from models.clinica import Clinica
from models.usuario import Usuario
from security.jwt_handler import decode_token
from security.superadmin import is_owner_email, is_superadmin_account_type
from security.tenant_context import tenant_clinica_id


class TrialMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        public_routes = {
            "/",
            "/app",
            "/docs",
            "/docs/oauth2-redirect",
            "/openapi.json",
            "/redoc",
            "/favicon.ico",
            "/login",
            "/auth/google/login",
            "/auth/google/callback",
            "/signup/request-code",
            "/signup/confirm",
            "/password/forgot",
            "/password/reset",
        }

        path = request.url.path

        if (
            path in public_routes
            or path.startswith("/frontend")
            or path.startswith("/desktop-assets")
            or path.startswith("/licenca/mercadopago/webhook")
        ):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Token nao informado"})

        token = auth_header.replace("Bearer ", "", 1).strip()
        payload = decode_token(token)

        if not payload:
            return JSONResponse(status_code=401, content={"detail": "Sessão expirada, faça login novamente!"})

        user_id = payload.get("user_id")
        if not user_id:
            return JSONResponse(status_code=401, content={"detail": "Usuario invalido"})

        db = SessionLocal()
        try:
            usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
            if not usuario:
                return JSONResponse(status_code=401, content={"detail": "Usuario invalido"})

            clinica_id = int(usuario.clinica_id or 0)
            if clinica_id <= 0:
                return JSONResponse(status_code=401, content={"detail": "Clinica invalida"})

            tenant_clinica_id.set(clinica_id)
            clinica = db.query(Clinica).filter(Clinica.id == clinica_id).first()
            if not clinica:
                return JSONResponse(status_code=401, content={"detail": "Clinica invalida"})
            owner_user = bool(usuario and is_owner_email(usuario.email))
            owner_clinica = bool(is_owner_email(clinica.email))
            if owner_user or owner_clinica:
                return await call_next(request)

            if not clinica.ativo and not path.startswith("/licenca"):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Conta suspensa. Contate o suporte da plataforma."},
                )

            licenca_expirada = (not is_superadmin_account_type(clinica.tipo_conta)) and (not clinica.trial_ate or clinica.trial_ate < datetime.utcnow())
            if licenca_expirada and not path.startswith("/licenca"):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Licenca expirada. Abra Ajuda > Ativacao de licenca para regularizar."},
                )
        finally:
            db.close()

        return await call_next(request)
