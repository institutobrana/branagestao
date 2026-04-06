import re
import csv
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models.clinica import Clinica
from models.access_profile import AccessProfile
from models.prestador_odonto import PrestadorOdonto
from models.usuario_perfil_acesso import UsuarioPerfilAcesso
from models.unidade_atendimento import UnidadeAtendimento
from models.usuario import Usuario
from security.dependencies import (
    get_current_user,
    require_admin_password_if_user_control_enabled,
    require_module_access,
)
from security.hash import hash_password, verify_password
from security.permissions import (
    MODULE_PERMISSION_SCHEMA,
    PERMISSION_LEVELS,
    compute_internal_permissions_from_easy,
    dump_permissions_json,
    extract_easy_permissions,
    get_access_profile_templates,
    get_easy_permission_schema,
    get_module_function_hints,
    merge_permissions_payload,
    normalize_tipo_usuario,
    parse_permissions_json,
    sanitize_easy_permissions,
    sanitize_permissions,
)
from security.system_accounts import SYSTEM_USER_CODIGO, is_system_prestador, is_system_user
from services.access_profiles_service import ensure_access_profiles

router = APIRouter(
    prefix="/admin/users",
    tags=["admin-users"],
    dependencies=[
        Depends(require_module_access("usuarios")),
        Depends(require_admin_password_if_user_control_enabled("usuarios")),
    ],
)

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
ROOT_DIR = Path(__file__).resolve().parents[3]


def _build_apelido(nome: str | None) -> str | None:
    txt = " ".join(str(nome or "").split()).strip()
    if not txt:
        return None
    return txt.split(" ", 1)[0][:60]




class AdminCreateUserRequest(BaseModel):
    nome: str
    senha: str
    confirma_senha: str | None = None
    codigo: int | None = None
    email: str | None = None
    apelido: str | None = None
    tipo_usuario: str | None = None
    prestador_row_id: int | None = None
    unidade_row_id: int | None = None
    forcar_troca_senha: bool = False
    is_admin: bool = False


class AdminUpdateUserRequest(BaseModel):
    nome: str
    email: str | None = None
    apelido: str | None = None
    tipo_usuario: str | None = None
    prestador_row_id: int | None = None
    unidade_row_id: int | None = None
    forcar_troca_senha: bool = False
    is_admin: bool = False
    ativo: bool = True


class AdminSetActiveRequest(BaseModel):
    ativo: bool


class AdminResetPasswordRequest(BaseModel):
    nova_senha: str


class AdminSetAccountTypeRequest(BaseModel):
    tipo_conta: str


class AdminChangePasswordRequest(BaseModel):
    usuario: str
    senha_atual: str
    nova_senha: str
    confirma_senha: str
    codigo: int | None = None


class AdminUpdatePermissionsRequest(BaseModel):
    permissoes: dict[str, str] | None = None
    easy_modules: dict[str, str] | None = None
    easy_funcoes: dict[str, str] | None = None
    easy_mode: bool | None = None


class AdminVerifyUserPasswordRequest(BaseModel):
    senha: str


class AdminUpdateUserProfilesRequest(BaseModel):
    perfil_id: int
    prestador_ids: list[int] = Field(default_factory=list)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _validate_email(email: str):
    if not EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=400, detail="E-mail invalido.")


def _validate_password(password: str):
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Senha deve ter no minimo 6 caracteres.")


def _validate_nome(nome: str):
    if not (nome or "").strip():
        raise HTTPException(status_code=400, detail="Informe o nome do usuario.")


def _clean_text(value: str | None, max_len: int | None = None) -> str | None:
    txt = " ".join(str(value or "").split()).strip()
    if not txt:
        return None
    return txt[:max_len] if max_len is not None else txt


def _require_admin(current_user: Usuario):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Apenas admin pode executar esta acao.")


def _assert_not_system_user(usuario: Usuario):
    if is_system_user(usuario):
        raise HTTPException(status_code=400, detail="Conta base 'Clínica' é protegida.")


def _normalize_account_type(tipo_conta: str) -> str:
    value = (tipo_conta or "").strip().lower()
    if value in {"demo", "demo 7 dias", "trial", "trial 7 dias"}:
        return "DEMO 7 dias"
    if value in {"mensal", "monthly"}:
        return "Mensal"
    if value in {"anual", "yearly", "annual"}:
        return "Anual"
    raise HTTPException(status_code=400, detail="tipo_conta invalido. Use: DEMO 7 dias, Mensal ou Anual.")


def _infer_account_type(clinica: Clinica) -> str:
    if clinica.tipo_conta:
        return clinica.tipo_conta
    if clinica.trial_ate and clinica.trial_ate >= datetime.utcnow():
        return "DEMO 7 dias"
    return "Mensal"


def _build_archived_clinic_email(clinica_id: int) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"deleted+{clinica_id}+{stamp}@brana.local"


def _next_codigo_for_clinic(db: Session, clinica_id: int) -> int:
    max_codigo = (
        db.query(func.max(Usuario.codigo))
        .filter(Usuario.clinica_id == clinica_id, Usuario.codigo.isnot(None))
        .scalar()
    )
    return int(max_codigo or 0) + 1


def _ensure_codigo_disponivel(db: Session, clinica_id: int, codigo: int):
    if codigo <= 0:
        raise HTTPException(status_code=400, detail="Codigo deve ser numerico e maior que zero.")
    exists = (
        db.query(Usuario.id)
        .filter(
            Usuario.clinica_id == clinica_id,
            Usuario.codigo == codigo,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Codigo ja cadastrado para esta clinica.")


def _ensure_nome_disponivel(db: Session, clinica_id: int, nome: str):
    exists = (
        db.query(Usuario.id)
        .filter(
            Usuario.clinica_id == clinica_id,
            func.lower(Usuario.nome) == nome.strip().lower(),
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Usuario ja cadastrado para esta clinica.")


def _validate_nome_disponivel_for_update(db: Session, clinica_id: int, user_id: int, nome: str):
    exists = (
        db.query(Usuario.id)
        .filter(
            Usuario.clinica_id == clinica_id,
            Usuario.id != user_id,
            func.lower(Usuario.nome) == nome.strip().lower(),
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Usuario ja cadastrado para esta clinica.")


def _build_internal_user_email(clinica_id: int, codigo: int, nome: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "", (nome or "").strip().lower())[:20] or "usuario"
    return f"{slug}.{codigo}.c{clinica_id}@local.brana"


def _resolve_email_for_new_user(db: Session, clinica_id: int, codigo: int, nome: str, email_raw: str | None) -> str:
    if (email_raw or "").strip():
        email = _normalize_email(email_raw)
        _validate_email(email)
        if db.query(Usuario).filter(Usuario.email == email).first():
            raise HTTPException(status_code=400, detail="E-mail ja cadastrado.")
        return email

    base = _build_internal_user_email(clinica_id, codigo, nome)
    email = base
    idx = 1
    while db.query(Usuario.id).filter(Usuario.email == email).first():
        idx += 1
        email = base.replace("@", f".{idx}@", 1)
    return email


def _ensure_access_profiles(db: Session, clinica_id: int) -> list[dict]:
    perfis = ensure_access_profiles(db, clinica_id)
    return [
        {
            "id": int(item.id),
            "source_id": int(item.source_id or 0) or None,
            "nome": str(item.nome or "").strip(),
            "reservado": bool(item.reservado),
        }
        for item in perfis
    ]


def _load_perfil_from_same_clinic(db: Session, clinica_id: int, perfil_id: int) -> AccessProfile:
    perfil = (
        db.query(AccessProfile)
        .filter(
            AccessProfile.id == int(perfil_id),
            AccessProfile.clinica_id == int(clinica_id),
        )
        .first()
    )
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil nao encontrado.")
    return perfil


def _resolve_email_for_existing_user(
    db: Session,
    usuario: Usuario,
    nome: str,
    email_raw: str | None,
) -> str:
    if (email_raw or "").strip():
        email = _normalize_email(email_raw)
        _validate_email(email)
        exists = db.query(Usuario.id).filter(Usuario.email == email, Usuario.id != usuario.id).first()
        if exists:
            raise HTTPException(status_code=400, detail="E-mail ja cadastrado.")
        return email
    return usuario.email


def _load_prestador_from_same_clinic(db: Session, clinica_id: int, row_id: int | None) -> PrestadorOdonto | None:
    if row_id is None:
        return None
    try:
        row_id_int = int(row_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Prestador invalido.")
    if row_id_int <= 0:
        return None
    prestador = (
        db.query(PrestadorOdonto)
        .filter(
            PrestadorOdonto.id == row_id_int,
            PrestadorOdonto.clinica_id == clinica_id,
        )
        .first()
    )
    if not prestador:
        raise HTTPException(status_code=404, detail="Prestador nao encontrado.")
    if is_system_prestador(prestador):
        raise HTTPException(status_code=400, detail="Prestador base 'Clínica' é reservado.")
    return prestador


def _load_unidade_from_same_clinic(db: Session, clinica_id: int, row_id: int | None) -> UnidadeAtendimento | None:
    if row_id is None:
        return None
    try:
        row_id_int = int(row_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Unidade invalida.")
    if row_id_int <= 0:
        return None
    unidade = (
        db.query(UnidadeAtendimento)
        .filter(
            UnidadeAtendimento.id == row_id_int,
            UnidadeAtendimento.clinica_id == clinica_id,
        )
        .first()
    )
    if not unidade:
        raise HTTPException(status_code=404, detail="Unidade nao encontrada.")
    return unidade


def _load_prestadores_for_profile(db: Session, clinica_id: int, prestador_ids: list[int]) -> list[PrestadorOdonto]:
    ids = [int(pid) for pid in prestador_ids if int(pid) > 0]
    if not ids:
        return []
    prestadores = (
        db.query(PrestadorOdonto)
        .filter(
            PrestadorOdonto.clinica_id == int(clinica_id),
            PrestadorOdonto.id.in_(ids),
        )
        .all()
    )
    encontrados = {int(p.id) for p in prestadores}
    faltando = [pid for pid in ids if pid not in encontrados]
    if faltando:
        raise HTTPException(status_code=404, detail="Prestador(es) nao encontrado(s).")
    return prestadores


def _apply_user_links(db: Session, usuario: Usuario, prestador: PrestadorOdonto | None, unidade: UnidadeAtendimento | None):
    if usuario.id:
        antigos = (
            db.query(PrestadorOdonto)
            .filter(
                PrestadorOdonto.clinica_id == usuario.clinica_id,
                PrestadorOdonto.usuario_id == usuario.id,
            )
            .all()
        )
        for antigo in antigos:
            if not prestador or antigo.id != prestador.id:
                antigo.usuario_id = None

    usuario.prestador_id = int(prestador.id) if prestador else None
    usuario.unidade_atendimento_id = int(unidade.id) if unidade else None

    if prestador:
        prestador.usuario_id = int(usuario.id) if usuario.id else prestador.usuario_id


def _permission_schema_payload() -> dict:
    payload = {
        "modules": MODULE_PERMISSION_SCHEMA,
        "levels": list(PERMISSION_LEVELS),
        "profiles": get_access_profile_templates(),
        "functions_by_module": get_module_function_hints(),
    }
    easy_schema = get_easy_permission_schema()
    if easy_schema:
        payload["easy_modules_schema"] = easy_schema.get("modules", [])
        payload["easy_levels"] = easy_schema.get("levels", list(PERMISSION_LEVELS))
        payload["easy_functions_by_module"] = easy_schema.get("functions_by_module", {})
    return payload


def _user_to_dict(usuario: Usuario, clinica: Clinica | None = None) -> dict:
    prestador = usuario.prestador
    unidade = usuario.unidade_atendimento
    permissoes = sanitize_permissions(
        parse_permissions_json(usuario.permissoes_json),
        tipo_usuario=usuario.tipo_usuario,
        is_admin=bool(usuario.is_admin),
    )
    return {
        "id": usuario.id,
        "codigo": int(usuario.codigo or usuario.id),
        "codigo_definido": usuario.codigo is not None,
        "nome": usuario.nome,
        "apelido": (usuario.apelido or "").strip(),
        "tipo_usuario": (usuario.tipo_usuario or "").strip(),
        "email": usuario.email,
        "is_system_user": is_system_user(usuario),
        "is_admin": bool(usuario.is_admin),
        "ativo": bool(usuario.ativo),
        "online": bool(usuario.online),
        "forcar_troca_senha": bool(usuario.forcar_troca_senha),
        "permissoes": permissoes,
        "prestador_row_id": int(usuario.prestador_id or 0) or None,
        "prestador_nome": ((prestador.nome if prestador else "") or "").strip(),
        "unidade_row_id": int(usuario.unidade_atendimento_id or 0) or None,
        "unidade_nome": ((unidade.nome if unidade else "") or "").strip(),
        "clinica_id": usuario.clinica_id,
        "clinica_nome": clinica.nome if clinica else None,
        "tipo_conta": _infer_account_type(clinica) if clinica else None,
    }


def _load_user_from_same_clinic(db: Session, current_user: Usuario, user_id: int) -> Usuario:
    usuario = (
        db.query(Usuario)
        .filter(
            Usuario.id == user_id,
            Usuario.clinica_id == current_user.clinica_id,
        )
        .first()
    )
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")
    return usuario


@router.get("")
def admin_list_users(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    usuarios = (
        db.query(Usuario)
        .filter(Usuario.clinica_id == current_user.clinica_id)
        .order_by(func.lower(Usuario.nome).asc(), Usuario.id.asc())
        .all()
    )
    clinica = db.query(Clinica).filter(Clinica.id == current_user.clinica_id).first()
    return [_user_to_dict(u, clinica=clinica) for u in usuarios]


@router.get("/proximo-codigo")
def admin_next_codigo(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    return {"codigo": _next_codigo_for_clinic(db, current_user.clinica_id)}


@router.get("/permissions/schema")
def admin_permissions_schema(
    current_user: Usuario = Depends(get_current_user),
):
    _require_admin(current_user)
    return _permission_schema_payload()


@router.post("")
def admin_create_user(
    payload: AdminCreateUserRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    _validate_nome(payload.nome)
    _validate_password(payload.senha)

    if payload.confirma_senha is not None and payload.senha != payload.confirma_senha:
        raise HTTPException(status_code=400, detail="A confirmacao da senha nao confere.")

    codigo = int(payload.codigo) if payload.codigo else _next_codigo_for_clinic(db, current_user.clinica_id)
    if int(codigo) == int(SYSTEM_USER_CODIGO):
        raise HTTPException(status_code=400, detail="Código 255 é reservado para a conta base 'Clínica'.")
    _ensure_codigo_disponivel(db, current_user.clinica_id, codigo)
    _ensure_nome_disponivel(db, current_user.clinica_id, payload.nome)
    prestador = _load_prestador_from_same_clinic(db, current_user.clinica_id, payload.prestador_row_id)
    unidade = _load_unidade_from_same_clinic(db, current_user.clinica_id, payload.unidade_row_id)

    email = _resolve_email_for_new_user(
        db=db,
        clinica_id=current_user.clinica_id,
        codigo=codigo,
        nome=payload.nome,
        email_raw=payload.email,
    )

    usuario = Usuario(
        codigo=codigo,
        nome=payload.nome.strip(),
        apelido=_clean_text(payload.apelido, 60) or _build_apelido(payload.nome),
        tipo_usuario=normalize_tipo_usuario(_clean_text(payload.tipo_usuario, 80)),
        email=email,
        senha_hash=hash_password(payload.senha),
        clinica_id=current_user.clinica_id,
        is_admin=bool(payload.is_admin),
        ativo=True,
        online=False,
        forcar_troca_senha=bool(payload.forcar_troca_senha),
        is_system_user=False,
        permissoes_json=dump_permissions_json(
            sanitize_permissions({}, tipo_usuario=payload.tipo_usuario, is_admin=bool(payload.is_admin))
        ),
    )
    db.add(usuario)
    db.flush()
    _apply_user_links(db, usuario, prestador, unidade)
    db.commit()
    db.refresh(usuario)
    clinica = db.query(Clinica).filter(Clinica.id == current_user.clinica_id).first()
    return _user_to_dict(usuario, clinica=clinica)


@router.patch("/{user_id}")
def admin_update_user(
    user_id: int,
    payload: AdminUpdateUserRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    _validate_nome(payload.nome)
    usuario = _load_user_from_same_clinic(db, current_user, user_id)
    _assert_not_system_user(usuario)
    _validate_nome_disponivel_for_update(db, current_user.clinica_id, user_id, payload.nome)
    prestador = _load_prestador_from_same_clinic(db, current_user.clinica_id, payload.prestador_row_id)
    unidade = _load_unidade_from_same_clinic(db, current_user.clinica_id, payload.unidade_row_id)
    tipo_usuario_normalizado = normalize_tipo_usuario(_clean_text(payload.tipo_usuario, 80))
    usuario.nome = payload.nome.strip()
    usuario.apelido = _clean_text(payload.apelido, 60) or _build_apelido(payload.nome)
    usuario.tipo_usuario = tipo_usuario_normalizado
    usuario.email = _resolve_email_for_existing_user(db, usuario, payload.nome, payload.email)
    usuario.is_admin = bool(payload.is_admin)
    usuario.ativo = bool(payload.ativo)
    if not usuario.ativo:
        usuario.online = False
    usuario.forcar_troca_senha = bool(payload.forcar_troca_senha)
    raw_permissions = parse_permissions_json(usuario.permissoes_json)
    internal_permissions = sanitize_permissions(
        raw_permissions,
        tipo_usuario=tipo_usuario_normalizado,
        is_admin=bool(payload.is_admin),
    )
    usuario.permissoes_json = dump_permissions_json(
        merge_permissions_payload(raw_permissions, internal_permissions)
    )
    _apply_user_links(db, usuario, prestador, unidade)
    db.commit()
    db.refresh(usuario)
    clinica = db.query(Clinica).filter(Clinica.id == current_user.clinica_id).first()
    return _user_to_dict(usuario, clinica=clinica)


@router.get("/{user_id}/permissions")
def admin_get_user_permissions(
    user_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    usuario = _load_user_from_same_clinic(db, current_user, user_id)
    _assert_not_system_user(usuario)
    raw_permissions = parse_permissions_json(usuario.permissoes_json)
    internal_permissions = sanitize_permissions(
        raw_permissions,
        tipo_usuario=usuario.tipo_usuario,
        is_admin=bool(usuario.is_admin),
    )
    easy_modules, easy_funcoes = extract_easy_permissions(raw_permissions, internal_permissions)
    return {
        "user_id": usuario.id,
        "nome": usuario.nome,
        "apelido": usuario.apelido,
        "tipo_usuario": usuario.tipo_usuario,
        "is_system_user": is_system_user(usuario),
        "permissoes": internal_permissions,
        "easy_modules": easy_modules,
        "easy_funcoes": easy_funcoes,
        **_permission_schema_payload(),
    }


@router.patch("/{user_id}/permissions")
def admin_update_user_permissions(
    user_id: int,
    payload: AdminUpdatePermissionsRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    usuario = _load_user_from_same_clinic(db, current_user, user_id)
    _assert_not_system_user(usuario)
    raw_permissions = parse_permissions_json(usuario.permissoes_json)
    easy_modules = None
    easy_funcoes = None
    if payload.easy_modules is not None or payload.easy_funcoes is not None or payload.easy_mode:
        easy_modules, easy_funcoes = sanitize_easy_permissions(payload.easy_modules or {}, payload.easy_funcoes or {})
        permissoes = compute_internal_permissions_from_easy(easy_modules)
    else:
        permissoes = sanitize_permissions(
            payload.permissoes or {},
            tipo_usuario=usuario.tipo_usuario,
            is_admin=bool(usuario.is_admin),
        )
    usuario.permissoes_json = dump_permissions_json(
        merge_permissions_payload(raw_permissions, permissoes, easy_modules=easy_modules, easy_funcoes=easy_funcoes)
    )
    db.commit()
    return {
        "detail": "Permissões atualizadas com sucesso.",
        "user_id": usuario.id,
        "permissoes": permissoes,
    }


@router.post("/{user_id}/verify-password")
def admin_verify_user_password(
    user_id: int,
    payload: AdminVerifyUserPasswordRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    usuario = _load_user_from_same_clinic(db, current_user, user_id)
    _assert_not_system_user(usuario)
    if not verify_password(payload.senha, usuario.senha_hash):
        raise HTTPException(status_code=400, detail="Senha incorreta.")
    return {"detail": "Senha confirmada."}


@router.get("/{user_id}/profiles")
def admin_get_user_profiles(
    user_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    usuario = _load_user_from_same_clinic(db, current_user, user_id)
    _assert_not_system_user(usuario)
    profiles = _ensure_access_profiles(db, current_user.clinica_id)
    prestadores = (
        db.query(PrestadorOdonto)
        .filter(PrestadorOdonto.clinica_id == current_user.clinica_id)
        .order_by(func.lower(PrestadorOdonto.nome).asc(), PrestadorOdonto.id.asc())
        .all()
    )
    assignments: dict[str, list[int]] = {}
    rows = (
        db.query(UsuarioPerfilAcesso)
        .filter(
            UsuarioPerfilAcesso.clinica_id == current_user.clinica_id,
            UsuarioPerfilAcesso.usuario_id == usuario.id,
        )
        .all()
    )
    for row in rows:
        key = str(int(row.perfil_id))
        assignments.setdefault(key, []).append(int(row.prestador_id))
    prestadores_payload = [
        {
            "id": int(item.id),
            "nome": str(item.nome or "").strip(),
            "inativo": bool(item.inativo),
            "is_system": bool(item.is_system_prestador),
        }
        for item in prestadores
    ]
    return {
        "user_id": usuario.id,
        "profiles": profiles,
        "prestadores": prestadores_payload,
        "assignments": assignments,
    }


@router.patch("/{user_id}/profiles")
def admin_update_user_profiles(
    user_id: int,
    payload: AdminUpdateUserProfilesRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    usuario = _load_user_from_same_clinic(db, current_user, user_id)
    _assert_not_system_user(usuario)
    _ensure_access_profiles(db, current_user.clinica_id)
    perfil = _load_perfil_from_same_clinic(db, current_user.clinica_id, payload.perfil_id)
    prestadores = _load_prestadores_for_profile(db, current_user.clinica_id, payload.prestador_ids)

    (
        db.query(UsuarioPerfilAcesso)
        .filter(
            UsuarioPerfilAcesso.clinica_id == current_user.clinica_id,
            UsuarioPerfilAcesso.usuario_id == usuario.id,
            UsuarioPerfilAcesso.perfil_id == perfil.id,
        )
        .delete(synchronize_session=False)
    )

    for prest in prestadores:
        db.add(
            UsuarioPerfilAcesso(
                clinica_id=current_user.clinica_id,
                usuario_id=usuario.id,
                prestador_id=prest.id,
                perfil_id=perfil.id,
            )
        )
    db.commit()
    return {
        "detail": "Perfil atualizado com sucesso.",
        "perfil_id": int(perfil.id),
        "prestador_ids": [int(p.id) for p in prestadores],
    }


@router.patch("/{user_id}/active")
def admin_set_user_active(
    user_id: int,
    payload: AdminSetActiveRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    usuario = _load_user_from_same_clinic(db, current_user, user_id)
    _assert_not_system_user(usuario)

    if current_user.id == usuario.id and not payload.ativo:
        raise HTTPException(status_code=400, detail="Voce nao pode se desativar.")

    usuario.ativo = bool(payload.ativo)
    if not usuario.ativo:
        usuario.online = False
    db.commit()
    db.refresh(usuario)
    return {"id": usuario.id, "ativo": bool(usuario.ativo), "online": bool(usuario.online)}


@router.post("/{user_id}/reset-password")
def admin_reset_user_password(
    user_id: int,
    payload: AdminResetPasswordRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    _validate_password(payload.nova_senha)
    usuario = _load_user_from_same_clinic(db, current_user, user_id)
    _assert_not_system_user(usuario)
    usuario.senha_hash = hash_password(payload.nova_senha)
    db.commit()
    return {"detail": "Senha atualizada com sucesso."}


@router.post("/change-password")
def admin_change_password_by_user(
    payload: AdminChangePasswordRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _validate_password(payload.nova_senha)
    if payload.nova_senha != payload.confirma_senha:
        raise HTTPException(status_code=400, detail="Senha e confirmacao devem ser identicas.")

    usuario = None
    if current_user.is_admin:
        usuario_txt = (payload.usuario or "").strip()
        if not usuario_txt:
            raise HTTPException(status_code=400, detail="Informe o usuario.")

        query = db.query(Usuario).filter(
            Usuario.clinica_id == current_user.clinica_id,
            func.lower(Usuario.nome) == usuario_txt.lower(),
        )
        if payload.codigo:
            query = query.filter(Usuario.codigo == int(payload.codigo))

        usuarios = query.order_by(Usuario.id.asc()).all()
        if not usuarios:
            raise HTTPException(status_code=404, detail="Usuario nao encontrado.")
        if len(usuarios) > 1:
            raise HTTPException(status_code=400, detail="Mais de um usuario encontrado. Informe tambem o codigo.")

        usuario = usuarios[0]
    else:
        usuario = current_user

    _assert_not_system_user(usuario)

    senha_atual = (payload.senha_atual or "").strip()
    if usuario.senha_hash:
        if not senha_atual:
            raise HTTPException(status_code=400, detail="Senha nao pode ser nula.")
        if not verify_password(senha_atual, usuario.senha_hash):
            raise HTTPException(status_code=400, detail="Senha atual incorreta.")

    usuario.senha_hash = hash_password(payload.nova_senha)
    usuario.forcar_troca_senha = False
    db.commit()
    return {"detail": "Senha alterada com sucesso."}


@router.delete("/{user_id}")
def admin_delete_user(
    user_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    usuario = _load_user_from_same_clinic(db, current_user, user_id)
    _assert_not_system_user(usuario)

    if current_user.id == usuario.id:
        raise HTTPException(status_code=400, detail="Voce nao pode excluir seu proprio usuario.")

    clinica_id = usuario.clinica_id
    db.delete(usuario)
    db.flush()

    has_other_users = db.query(Usuario.id).filter(Usuario.clinica_id == clinica_id).first()
    if not has_other_users:
        clinica = db.query(Clinica).filter(Clinica.id == clinica_id).first()
        if clinica:
            clinica.email = _build_archived_clinic_email(clinica.id)
            clinica.ativo = False

    db.commit()
    return {"detail": "Usuario excluido com sucesso."}


@router.patch("/{user_id}/account-type")
def admin_set_user_account_type(
    user_id: int,
    payload: AdminSetAccountTypeRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    usuario = _load_user_from_same_clinic(db, current_user, user_id)
    _assert_not_system_user(usuario)
    clinica = db.query(Clinica).filter(Clinica.id == usuario.clinica_id).first()
    if not clinica:
        raise HTTPException(status_code=404, detail="Clinica nao encontrada.")

    clinica.tipo_conta = _normalize_account_type(payload.tipo_conta)
    db.commit()
    return {"clinica_id": clinica.id, "tipo_conta": clinica.tipo_conta}
