from collections.abc import Callable
import json

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db
from models.clinica import Clinica
from models.usuario import Usuario
from security.admin_password import verify_admin_password
from security.jwt_handler import decode_token
from security.permissions import get_module_access_level
from security.system_accounts import is_system_user
from security.superadmin import is_owner_email

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def _bool_from_value(value, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    txt = str(value or "").strip().lower()
    if txt in {"0", "false", "f", "nao", "não", "n", "off"}:
        return False
    if txt in {"1", "true", "t", "sim", "s", "on"}:
        return True
    return default


def _is_user_control_enabled(clinica: Clinica | None) -> bool:
    if not clinica:
        return True
    raw = (clinica.opcoes_sistema_json or "").strip()
    if not raw:
        return True
    try:
        data = json.loads(raw)
    except Exception:
        return True
    if not isinstance(data, dict):
        return True
    seg = data.get("seguranca")
    if not isinstance(seg, dict):
        return True
    return _bool_from_value(seg.get("ativar_controle_usuarios"), True)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Sessão expirada, faça login novamente!")

    user_id = payload.get("user_id")
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario nao encontrado")

    if is_system_user(usuario):
        raise HTTPException(status_code=403, detail="Conta sistêmica sem sessão interativa.")

    owner = is_owner_email(usuario.email)
    if not usuario.ativo and not owner:
        raise HTTPException(status_code=403, detail="Usuario inativo")

    # Conta proprietaria sempre com acesso total.
    if owner:
        usuario.ativo = True
        usuario.is_admin = True

    return usuario


def require_module_access(
    module_code: str,
    *,
    allow_protected: bool = True,
) -> Callable:
    def _dependency(
        request: Request,
        current_user: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> Usuario:
        nivel = get_module_access_level(current_user, module_code)
        if nivel == "habilitado":
            return current_user

        if nivel == "desabilitado":
            raise HTTPException(
                status_code=403,
                detail=f"Acesso ao modulo '{module_code}' negado (nivel atual: desabilitado).",
            )

        if not allow_protected:
            raise HTTPException(
                status_code=403,
                detail=f"Acesso ao modulo '{module_code}' negado (nivel atual: protegido).",
            )

        protected_password = (request.headers.get("X-Protected-Password") or "").strip()
        if protected_password and verify_admin_password(db, current_user.clinica_id, protected_password):
            return current_user

        grant_token = (request.headers.get("X-Protected-Grant") or "").strip()
        if grant_token:
            payload = decode_token(grant_token)
            if isinstance(payload, dict) and payload.get("type") == "protected_grant":
                same_user = int(payload.get("user_id") or 0) == int(current_user.id or 0)
                same_clinic = int(payload.get("clinica_id") or 0) == int(current_user.clinica_id or 0)
                granted_module = str(payload.get("module_code") or "").strip().lower()
                if same_user and same_clinic and granted_module in {"*", module_code.lower()}:
                    return current_user
                if (
                    same_user
                    and same_clinic
                    and granted_module == "configuracao"
                    and module_code.lower() == "usuarios"
                ):
                    return current_user

        raise HTTPException(
            status_code=403,
            detail={
                "error": "protected_password_required",
                "module_code": module_code,
                "message": (
                    f"O modulo '{module_code}' esta como protegido. "
                    "Informe a senha do administrador para continuar."
                ),
            },
        )

    return _dependency


def require_admin_password_if_user_control_enabled(module_code: str) -> Callable:
    def _dependency(
        request: Request,
        current_user: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> Usuario:
        clinica = (
            db.query(Clinica)
            .filter(Clinica.id == int(current_user.clinica_id))
            .first()
        )
        if not _is_user_control_enabled(clinica):
            return current_user

        protected_password = (request.headers.get("X-Protected-Password") or "").strip()
        if protected_password and verify_admin_password(db, current_user.clinica_id, protected_password):
            return current_user

        grant_token = (request.headers.get("X-Protected-Grant") or "").strip()
        if grant_token:
            payload = decode_token(grant_token)
            if isinstance(payload, dict) and payload.get("type") == "protected_grant":
                same_user = int(payload.get("user_id") or 0) == int(current_user.id or 0)
                same_clinic = int(payload.get("clinica_id") or 0) == int(current_user.clinica_id or 0)
                granted_module = str(payload.get("module_code") or "").strip().lower()
                if same_user and same_clinic and granted_module in {"*", module_code.lower()}:
                    return current_user
                if (
                    same_user
                    and same_clinic
                    and granted_module == "configuracao"
                    and module_code.lower() == "usuarios"
                ):
                    return current_user

        raise HTTPException(
            status_code=403,
            detail={
                "error": "protected_password_required",
                "module_code": module_code,
                "message": (
                    f"O módulo '{module_code}' está protegido pelas opções do sistema. "
                    "Informe a senha do administrador para continuar."
                ),
            },
        )

    return _dependency
