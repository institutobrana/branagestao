import hashlib
import json
import os
import random
import re
from datetime import datetime, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.clinica import Clinica
from models.email_code import EmailCode
from models.usuario import Usuario
from security.admin_password import verify_admin_password
from security.hash import hash_password, verify_password
from security.jwt_handler import create_access_token
from security.dependencies import get_current_user
from security.permissions import MODULE_PERMISSION_SCHEMA, get_module_access_level
from security.system_accounts import is_system_user
from security.superadmin import is_owner_email, is_platform_superadmin_user
from security.user_context import build_user_context
from services.email_service import EmailDeliveryError, send_verification_code
from services.signup_service import criar_conta_saas

router = APIRouter()

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
DISPOSABLE_DOMAINS = {
    "mailinator.com",
    "tempmail.com",
    "10minutemail.com",
    "guerrillamail.com",
    "yopmail.com",
    "trashmail.com",
}
SIGNUP_CODE_EXP_MINUTES = max(1, int(os.getenv("SIGNUP_CODE_EXP_MINUTES", "10")))
RESET_CODE_EXP_MINUTES = max(1, int(os.getenv("RESET_CODE_EXP_MINUTES", "10")))
PROTECTED_GRANT_EXPIRE_MINUTES = max(1, int(os.getenv("PROTECTED_GRANT_EXPIRE_MINUTES", "20")))
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class SignupRequest(BaseModel):
    nome: str
    email: str
    senha: str


class SignupConfirm(SignupRequest):
    codigo: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    codigo: str
    nova_senha: str


class ProtectedUnlockRequest(BaseModel):
    senha: str
    module_code: str | None = None


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_email(email: str):
    if not EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=400, detail="E-mail invalido.")

    domain = email.split("@", 1)[1].lower()
    if domain in DISPOSABLE_DOMAINS:
        raise HTTPException(status_code=400, detail="Use um e-mail real (dominio temporario bloqueado).")


def validate_password(password: str):
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Senha deve ter no minimo 6 caracteres.")


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def create_email_code(db: Session, email: str, purpose: str) -> str:
    code = generate_code()
    exp_minutes = SIGNUP_CODE_EXP_MINUTES if purpose == "signup" else RESET_CODE_EXP_MINUTES
    record = EmailCode(
        email=email,
        purpose=purpose,
        code_hash=hash_code(code),
        expires_at=datetime.utcnow() + timedelta(minutes=exp_minutes),
        used=False,
    )
    db.add(record)
    db.commit()
    return code


def load_valid_code(db: Session, email: str, purpose: str, code: str):
    records = (
        db.query(EmailCode)
        .filter(
            EmailCode.email == email,
            EmailCode.purpose == purpose,
            EmailCode.used == False,  # noqa: E712
        )
        .order_by(EmailCode.id.desc())
        .all()
    )

    if not records:
        raise HTTPException(status_code=400, detail="Codigo invalido.")

    now = datetime.utcnow()
    typed_hash = hash_code(code.strip())
    has_non_expired = False

    for record in records:
        if record.expires_at < now:
            continue
        has_non_expired = True
        if record.code_hash == typed_hash:
            return record

    if has_non_expired:
        raise HTTPException(status_code=400, detail="Codigo invalido.")
    raise HTTPException(status_code=400, detail="Codigo expirado.")


def send_code_or_fail(email: str, code: str, purpose: str):
    try:
        send_verification_code(email, code, purpose)
    except EmailDeliveryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _google_settings():
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8000/auth/google/callback").strip()
    return client_id, client_secret, redirect_uri


def _upsert_google_user(db: Session, email: str, nome: str):
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario:
        return usuario

    criar_conta_saas(db, nome=nome, email=email, senha=hashlib.sha256(email.encode("utf-8")).hexdigest()[:20])
    return db.query(Usuario).filter(Usuario.email == email).first()


def _enforce_owner_access(usuario: Usuario) -> bool:
    owner = is_owner_email(usuario.email)
    if owner:
        usuario.ativo = True
        usuario.is_admin = True
    return owner


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    email = normalize_email(form_data.username or "")
    if not email:
        raise HTTPException(status_code=400, detail="Usuario nao encontrado")

    usuario = db.query(Usuario).filter(
        Usuario.email == email
    ).first()

    if not usuario:
        raise HTTPException(status_code=400, detail="Usuario nao encontrado")

    if is_system_user(usuario):
        raise HTTPException(status_code=403, detail="Conta sistêmica sem login interativo.")

    owner = _enforce_owner_access(usuario)
    changed = False

    if not usuario.ativo and not owner:
        raise HTTPException(status_code=403, detail="Usuario inativo")

    if not verify_password(form_data.password, usuario.senha_hash):
        raise HTTPException(status_code=400, detail="Senha incorreta")

    if owner and (not usuario.is_admin or not usuario.ativo):
        usuario.is_admin = True
        usuario.ativo = True
        changed = True

    if not usuario.online:
        usuario.online = True
        changed = True

    if changed:
        db.commit()
        db.refresh(usuario)

    token = create_access_token(
        {
            "user_id": usuario.id,
            "clinica_id": usuario.clinica_id,
            "is_admin": True if owner else usuario.is_admin,
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


@router.get("/auth/google/login")
def google_login():
    client_id, _, redirect_uri = _google_settings()
    if not client_id:
        raise HTTPException(status_code=503, detail="Google OAuth nao configurado (GOOGLE_CLIENT_ID).")

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "prompt": "select_account",
        "access_type": "online",
    }

    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/auth/google/callback")
def google_callback(code: str | None = None, error: str | None = None, db: Session = Depends(get_db)):
    if error:
        return RedirectResponse(url=f"/app?oauth_error={error}")

    if not code:
        return RedirectResponse(url="/app?oauth_error=missing_code")

    client_id, client_secret, redirect_uri = _google_settings()
    if not client_id or not client_secret:
        return RedirectResponse(url="/app?oauth_error=google_oauth_not_configured")

    try:
        token_body = urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
        ).encode("utf-8")

        token_req = Request(
            GOOGLE_TOKEN_URL,
            data=token_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        with urlopen(token_req, timeout=20) as token_resp:
            token_data = json.loads(token_resp.read().decode("utf-8"))

        access_token = token_data.get("access_token")
        if not access_token:
            return RedirectResponse(url="/app?oauth_error=missing_access_token")

        user_req = Request(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            method="GET",
        )

        with urlopen(user_req, timeout=20) as userinfo_resp:
            profile = json.loads(userinfo_resp.read().decode("utf-8"))

        email = normalize_email(profile.get("email", ""))
        nome = (profile.get("name") or "Usuario Google").strip()
        email_verified = bool(profile.get("email_verified"))

        if not email or not email_verified:
            return RedirectResponse(url="/app?oauth_error=unverified_email")

        usuario = _upsert_google_user(db, email=email, nome=nome)
        if not usuario:
            return RedirectResponse(url="/app?oauth_error=account_create_failed")
        if is_system_user(usuario):
            return RedirectResponse(url="/app?oauth_error=system_account_login_blocked")
        owner = _enforce_owner_access(usuario)
        if not usuario.ativo and not owner:
            return RedirectResponse(url="/app?oauth_error=user_disabled")

        changed = False
        if owner and (not usuario.is_admin or not usuario.ativo):
            usuario.is_admin = True
            usuario.ativo = True
            changed = True
        if not usuario.online:
            usuario.online = True
            changed = True
        if changed:
            db.commit()
            db.refresh(usuario)

        token = create_access_token(
            {
                "user_id": usuario.id,
                "clinica_id": usuario.clinica_id,
                "is_admin": True if owner else usuario.is_admin,
            }
        )

        return RedirectResponse(url=f"/app?token={token}")

    except Exception:
        return RedirectResponse(url="/app?oauth_error=unexpected_google_error")


@router.post("/signup/request-code")
def signup_request_code(payload: SignupRequest, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    validate_email(email)
    validate_password(payload.senha)

    if db.query(Usuario).filter(Usuario.email == email).first():
        raise HTTPException(status_code=400, detail="E-mail ja cadastrado.")

    if db.query(Clinica).filter(Clinica.email == email).first():
        raise HTTPException(status_code=400, detail="E-mail ja cadastrado.")

    code = create_email_code(db, email=email, purpose="signup")
    send_code_or_fail(email=email, code=code, purpose="signup")

    return {"detail": "Codigo enviado para o e-mail informado."}


@router.post("/signup/confirm")
def signup_confirm(payload: SignupConfirm, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    validate_email(email)
    validate_password(payload.senha)

    if db.query(Usuario).filter(Usuario.email == email).first():
        raise HTTPException(status_code=400, detail="E-mail ja cadastrado.")

    record = load_valid_code(db, email=email, purpose="signup", code=payload.codigo)

    criar_conta_saas(db, nome=payload.nome.strip(), email=email, senha=payload.senha)

    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    record.used = True
    db.commit()

    token = create_access_token(
        {"user_id": usuario.id, "clinica_id": usuario.clinica_id, "is_admin": usuario.is_admin}
    )

    return {"detail": "Conta criada com sucesso.", "access_token": token, "token_type": "bearer"}


@router.post("/password/forgot")
def password_forgot(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    validate_email(email)

    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario:
        return {"detail": "Se o e-mail existir, o codigo sera enviado."}

    code = create_email_code(db, email=email, purpose="reset_password")
    send_code_or_fail(email=email, code=code, purpose="reset_password")

    return {"detail": "Se o e-mail existir, o codigo sera enviado."}


@router.post("/password/reset")
def password_reset(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    validate_email(email)
    validate_password(payload.nova_senha)

    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario:
        raise HTTPException(status_code=400, detail="Codigo invalido.")

    record = load_valid_code(db, email=email, purpose="reset_password", code=payload.codigo)

    usuario.senha_hash = hash_password(payload.nova_senha)
    record.used = True
    db.commit()

    return {"detail": "Senha atualizada com sucesso."}


@router.post("/logout")
def logout(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    usuario = db.query(Usuario).filter(Usuario.id == current_user.id).first()
    if usuario and usuario.online:
        usuario.online = False
        db.commit()
    return {"detail": "Sessao encerrada com sucesso."}


@router.post("/auth/protected/unlock")
def unlock_protected_module(
    payload: ProtectedUnlockRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    senha = (payload.senha or "").strip()
    if not senha:
        raise HTTPException(status_code=400, detail="Informe a senha atual.")
    if not verify_admin_password(db, current_user.clinica_id, senha):
        raise HTTPException(status_code=400, detail="Senha do administrador incorreta.")

    module_code = (payload.module_code or "*").strip().lower()
    valid_modules = {item["codigo"] for item in MODULE_PERMISSION_SCHEMA}
    if module_code != "*":
        if module_code not in valid_modules:
            raise HTTPException(status_code=400, detail="module_code invalido.")
        if get_module_access_level(current_user, module_code) == "desabilitado":
            raise HTTPException(
                status_code=403,
                detail=f"Acesso ao modulo '{module_code}' esta desabilitado.",
            )

    grant = create_access_token(
        {
            "type": "protected_grant",
            "user_id": current_user.id,
            "clinica_id": current_user.clinica_id,
            "module_code": module_code,
        },
        expires_minutes=PROTECTED_GRANT_EXPIRE_MINUTES,
    )
    return {
        "grant_token": grant,
        "module_code": module_code,
        "expires_in_minutes": PROTECTED_GRANT_EXPIRE_MINUTES,
    }


@router.get("/me")
def me(current_user = Depends(get_current_user)):
    is_super = is_platform_superadmin_user(current_user)
    return build_user_context(current_user, is_superadmin=is_super)
