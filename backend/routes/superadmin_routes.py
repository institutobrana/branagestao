import csv
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models.assinatura import Assinatura
from models.cenario import Cenario
from models.clinica import Clinica
from models.email_code import EmailCode
from models.financeiro import CategoriaFinanceira, GrupoFinanceiro, ItemAuxiliar, Lancamento
from models.material import ListaMaterial, Material
from models.plano import Plano  # noqa: F401  # garante registro da tabela "planos" no metadata
from models.plataforma import PlataformaAssinatura, PlataformaAuditoria, PlataformaCobranca
from models.procedimento import Procedimento, ProcedimentoMaterial
from models.usuario import Usuario
from security.dependencies import get_current_user
from security.hash import hash_password
from security.system_accounts import is_system_user
from security.superadmin import is_owner_email, is_platform_superadmin_user
from services.platform_admin_service import (
    aplicar_plano_na_clinica,
    assinatura_plano_from_clinica,
    assinatura_status_from_clinica,
    registrar_auditoria,
    sync_assinatura_from_clinica,
)

router = APIRouter(prefix="/superadmin", tags=["superadmin"])


def _require_superadmin(current_user: Usuario):
    if not is_platform_superadmin_user(current_user):
        raise HTTPException(status_code=403, detail="Acesso restrito ao Super Admin da plataforma.")


def _fmt_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    v = str(value).strip().lower()
    if v in {"1", "true", "sim", "yes", "y"}:
        return True
    if v in {"0", "false", "nao", "não", "no", "n"}:
        return False
    return None


def _owner_clinica_ids(db: Session, clinica_ids: list[int] | None = None) -> set[int]:
    query = db.query(Usuario.clinica_id, Usuario.email)
    if clinica_ids:
        query = query.filter(Usuario.clinica_id.in_(clinica_ids))
    return {
        int(cid)
        for cid, email in query.all()
        if cid is not None and is_owner_email(email)
    }


def _is_owner_clinica(db: Session, clinica_id: int) -> bool:
    return int(clinica_id) in _owner_clinica_ids(db, [int(clinica_id)])


class SuperAdminSetStatusPayload(BaseModel):
    ativo: bool
    motivo: str | None = None


class SuperAdminSetPlanoPayload(BaseModel):
    plano: str
    dias: int | None = None
    manter_ativo: bool = True


class SuperAdminSetUserStatusPayload(BaseModel):
    ativo: bool


class SuperAdminSetUserPerfilPayload(BaseModel):
    is_admin: bool


class SuperAdminCreateUserPayload(BaseModel):
    clinica_id: int
    nome: str
    email: str
    senha: str
    is_admin: bool = True
    ativar_clinica: bool = True


class SuperAdminResetUserSenhaPayload(BaseModel):
    nova_senha: str


class SuperAdminExtendTrialPayload(BaseModel):
    dias: int


def _delete_clinica_definitiva(db: Session, clinica: Clinica) -> dict:
    clinica_id = int(clinica.id)
    usuario_emails = [
        (x[0] or "").strip().lower()
        for x in db.query(Usuario.email).filter(Usuario.clinica_id == clinica_id).all()
    ]
    emails_limpeza = {
        e
        for e in ([((clinica.email or "").strip().lower())] + usuario_emails)
        if e
    }

    usuarios_removidos = db.query(Usuario).filter(Usuario.clinica_id == clinica_id).count()

    lista_ids = [
        int(x[0])
        for x in db.query(ListaMaterial.id).filter(ListaMaterial.clinica_id == clinica_id).all()
        if x and x[0] is not None
    ]

    # Ordem de exclusao respeita relacionamentos/fks para remocao definitiva do tenant.
    db.query(ProcedimentoMaterial).filter(ProcedimentoMaterial.clinica_id == clinica_id).delete(synchronize_session=False)
    db.query(Procedimento).filter(Procedimento.clinica_id == clinica_id).delete(synchronize_session=False)
    if lista_ids:
        db.query(Material).filter(Material.lista_id.in_(lista_ids)).delete(synchronize_session=False)
    db.query(ListaMaterial).filter(ListaMaterial.clinica_id == clinica_id).delete(synchronize_session=False)

    db.query(Lancamento).filter(Lancamento.clinica_id == clinica_id).delete(synchronize_session=False)
    db.query(CategoriaFinanceira).filter(CategoriaFinanceira.clinica_id == clinica_id).delete(synchronize_session=False)
    db.query(GrupoFinanceiro).filter(GrupoFinanceiro.clinica_id == clinica_id).delete(synchronize_session=False)
    db.query(ItemAuxiliar).filter(ItemAuxiliar.clinica_id == clinica_id).delete(synchronize_session=False)

    db.query(Cenario).filter(Cenario.clinica_id == clinica_id).delete(synchronize_session=False)
    db.query(PlataformaCobranca).filter(PlataformaCobranca.clinica_id == clinica_id).delete(synchronize_session=False)
    db.query(PlataformaAssinatura).filter(PlataformaAssinatura.clinica_id == clinica_id).delete(synchronize_session=False)
    db.query(Assinatura).filter(Assinatura.clinica_id == clinica_id).delete(synchronize_session=False)
    db.query(Usuario).filter(Usuario.clinica_id == clinica_id).delete(synchronize_session=False)

    if emails_limpeza:
        db.query(EmailCode).filter(func.lower(EmailCode.email).in_(list(emails_limpeza))).delete(synchronize_session=False)

    db.delete(clinica)
    return {
        "clinica_id": clinica_id,
        "clinica_nome": clinica.nome,
        "clinica_email": clinica.email,
        "usuarios_removidos": int(usuarios_removidos or 0),
    }


def _listar_usuarios_superadmin(
    db: Session,
    q: str = "",
    clinica_id: int | None = None,
    ativo: str | None = None,
    admin: str | None = None,
    plano: str | None = None,
    clinica_status: str | None = None,
    limit: int = 300,
):
    query = db.query(Usuario)
    term = (q or "").strip().lower()
    if term:
        like = f"%{term}%"
        query = query.filter((func.lower(Usuario.nome).like(like)) | (func.lower(Usuario.email).like(like)))

    if clinica_id:
        query = query.filter(Usuario.clinica_id == clinica_id)

    ativo_bool = _parse_bool(ativo)
    if ativo_bool is not None:
        query = query.filter(Usuario.ativo == ativo_bool)  # noqa: E712

    admin_bool = _parse_bool(admin)
    if admin_bool is not None:
        query = query.filter(Usuario.is_admin == admin_bool)  # noqa: E712

    usuarios = query.order_by(Usuario.id.asc()).limit(limit).all()
    clinicas = {c.id: c for c in db.query(Clinica).all()}
    owner_clinica_ids = _owner_clinica_ids(db, list(clinicas.keys()) if clinicas else None)
    plano_filter = (plano or "").strip().upper()
    status_filter = (clinica_status or "").strip().lower()
    out = []
    for u in usuarios:
        c = clinicas.get(u.clinica_id)
        owner_clinica = bool(c and c.id in owner_clinica_ids)
        clin_status = ("ativa" if owner_clinica else assinatura_status_from_clinica(c)) if c else None
        clin_plano = ("MASTER" if owner_clinica else assinatura_plano_from_clinica(c)) if c else None
        if plano_filter and plano_filter not in {"TODOS", "ALL"} and clin_plano != plano_filter:
            continue
        if status_filter and status_filter not in {"todas", "todos", "all"} and clin_status != status_filter:
            continue
        out.append(
            {
                "id": u.id,
                "nome": u.nome,
                "email": u.email,
                "is_admin": bool(u.is_admin),
                "ativo": bool(u.ativo),
                "clinica_id": u.clinica_id,
                "clinica_nome": c.nome if c else None,
                "clinica_email": c.email if c else None,
                "clinica_ativa": bool(c.ativo) if c else None,
                "clinica_tipo_conta": ("MASTER" if owner_clinica else c.tipo_conta) if c else None,
                "clinica_status": clin_status,
                "clinica_plano": clin_plano,
                "clinica_trial_ate": None if owner_clinica else (_fmt_datetime(c.trial_ate) if c else None),
                "clinica_data_ativacao": _fmt_datetime(c.data_ativacao) if c else None,
                "clinica_cnpj": c.cnpj if c else None,
                "is_owner_account": is_owner_email(u.email),
                "is_system_user": is_system_user(u),
            }
        )
    return out


@router.get("/overview")
def superadmin_overview(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superadmin(current_user)

    clinicas = db.query(Clinica).order_by(Clinica.id.asc()).all()
    owner_clinica_ids = _owner_clinica_ids(db, [c.id for c in clinicas] if clinicas else None)
    total_clinicas = len(clinicas)
    total_usuarios = db.query(func.count(Usuario.id)).scalar() or 0
    usuarios_ativos = db.query(func.count(Usuario.id)).filter(Usuario.ativo == True).scalar() or 0  # noqa: E712

    contagem_users = dict(
        db.query(Usuario.clinica_id, func.count(Usuario.id))
        .group_by(Usuario.clinica_id)
        .all()
    )

    ativas = 0
    suspensas = 0
    expiradas = 0
    trial = 0
    mensal = 0
    anual = 0
    sem_usuario = 0
    arquivadas = 0

    for c in clinicas:
        owner_clinica = c.id in owner_clinica_ids
        if int(contagem_users.get(c.id, 0)) == 0:
            sem_usuario += 1

        email_norm = (c.email or "").strip().lower()
        if email_norm.startswith("deleted+") and email_norm.endswith("@brana.local"):
            arquivadas += 1

        status = "ativa" if owner_clinica else assinatura_status_from_clinica(c)
        if status == "suspensa":
            suspensas += 1
        elif status == "expirada":
            expiradas += 1
        elif status == "trial":
            trial += 1
            ativas += 1
        else:
            ativas += 1

        if not owner_clinica:
            tipo = (c.tipo_conta or "").lower()
            if "mensal" in tipo:
                mensal += 1
            elif "anual" in tipo:
                anual += 1

    monthly_price = 149.90
    annual_price = 1499.00
    mrr_estimado = mensal * monthly_price + anual * (annual_price / 12.0)
    arr_estimado = mensal * monthly_price * 12.0 + anual * annual_price

    cobrancas_30d = (
        db.query(PlataformaCobranca)
        .filter(
            PlataformaCobranca.status == "approved",
            PlataformaCobranca.criado_em >= (datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)),
        )
        .count()
    )
    online_rows = (
        db.query(Usuario.id, Usuario.nome, Usuario.email, Usuario.clinica_id, Clinica.nome)
        .join(Clinica, Clinica.id == Usuario.clinica_id)
        .filter(Usuario.online == True)  # noqa: E712
        .order_by(Usuario.nome.asc(), Usuario.id.asc())
        .all()
    )
    online_resumo = "; ".join(
        f"{(nome or email or f'Usuário #{user_id}').strip()} / {(clinica_nome or f'Clínica #{clinica_id}')}"
        for user_id, nome, email, clinica_id, clinica_nome in online_rows
    ) or "Nenhum usuário online."

    return {
        "total_clinicas": total_clinicas,
        "total_usuarios": int(total_usuarios),
        "usuarios_ativos": int(usuarios_ativos),
        "clinicas_ativas": ativas,
        "clinicas_suspensas": suspensas,
        "clinicas_expiradas": expiradas,
        "clinicas_trial": trial,
        "clinicas_sem_usuario": sem_usuario,
        "clinicas_arquivadas": arquivadas,
        "planos_mensal": mensal,
        "planos_anual": anual,
        "mrr_estimado": round(float(mrr_estimado), 2),
        "arr_estimado": round(float(arr_estimado), 2),
        "cobrancas_aprovadas_hoje": int(cobrancas_30d),
        "online_resumo": online_resumo,
    }


@router.get("/clinicas")
def superadmin_list_clinicas(
    q: str = Query(default="", max_length=120),
    status: str = Query(default="todas", max_length=20),
    ativo: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superadmin(current_user)

    query = db.query(Clinica)
    term = (q or "").strip().lower()
    if term:
        like = f"%{term}%"
        query = query.filter((func.lower(Clinica.nome).like(like)) | (func.lower(Clinica.email).like(like)))

    ativo_bool = _parse_bool(ativo)
    if ativo_bool is not None:
        query = query.filter(Clinica.ativo == ativo_bool)  # noqa: E712

    clinicas = query.order_by(Clinica.id.asc()).limit(limit).all()
    owner_clinica_ids = _owner_clinica_ids(db, [c.id for c in clinicas] if clinicas else None)

    contagem_users = dict(
        db.query(Usuario.clinica_id, func.count(Usuario.id))
        .group_by(Usuario.clinica_id)
        .all()
    )
    contagem_users_ativos = dict(
        db.query(Usuario.clinica_id, func.count(Usuario.id))
        .filter(Usuario.ativo == True)  # noqa: E712
        .group_by(Usuario.clinica_id)
        .all()
    )

    ultimas_cobrancas = {}
    for c in (
        db.query(PlataformaCobranca)
        .order_by(PlataformaCobranca.criado_em.desc(), PlataformaCobranca.id.desc())
        .all()
    ):
        if c.clinica_id not in ultimas_cobrancas:
            ultimas_cobrancas[c.clinica_id] = c

    out = []
    status_filter = (status or "todas").strip().lower()
    owner_view = is_owner_email(current_user.email)
    for c in clinicas:
        owner_clinica = c.id in owner_clinica_ids
        assinatura_status = assinatura_status_from_clinica(c) if (owner_clinica and owner_view) else (
            "ativa" if owner_clinica else assinatura_status_from_clinica(c)
        )
        if status_filter not in {"", "todas", "all"} and assinatura_status != status_filter:
            continue

        sync_assinatura_from_clinica(db, c)
        cobr = ultimas_cobrancas.get(c.id)
        out.append(
            {
                "id": c.id,
                "nome": c.nome,
                "email": c.email,
                "ativo": bool(c.ativo),
                "tipo_conta": c.tipo_conta if (owner_clinica and owner_view) else ("MASTER" if owner_clinica else c.tipo_conta),
                "trial_ate": _fmt_datetime(c.trial_ate) if (owner_clinica and owner_view) else (None if owner_clinica else _fmt_datetime(c.trial_ate)),
                "data_ativacao": _fmt_datetime(c.data_ativacao),
                "assinatura_status": assinatura_status,
                "usuarios_total": int(contagem_users.get(c.id, 0)),
                "usuarios_ativos": int(contagem_users_ativos.get(c.id, 0)),
                "ultimo_pagamento_status": cobr.status if cobr else None,
                "ultimo_pagamento_valor": float(cobr.valor or 0) if cobr else 0,
                "ultimo_pagamento_em": _fmt_datetime(cobr.criado_em) if cobr else None,
                "is_owner_clinica": bool(owner_clinica),
            }
        )

    db.commit()
    return out


@router.post("/usuarios")
def superadmin_create_usuario(
    payload: SuperAdminCreateUserPayload,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superadmin(current_user)

    clinica = db.query(Clinica).filter(Clinica.id == int(payload.clinica_id)).first()
    if not clinica:
        raise HTTPException(status_code=404, detail="Clinica nao encontrada.")

    email = (payload.email or "").strip().lower()
    nome = (payload.nome or "").strip()
    senha = (payload.senha or "").strip()

    if not nome:
        raise HTTPException(status_code=400, detail="Nome obrigatorio.")
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="E-mail invalido.")
    if len(senha) < 6:
        raise HTTPException(status_code=400, detail="Senha deve ter no minimo 6 caracteres.")
    if db.query(Usuario.id).filter(Usuario.email == email).first():
        raise HTTPException(status_code=400, detail="E-mail ja cadastrado em usuario.")

    usuario = Usuario(
        nome=nome,
        email=email,
        senha_hash=hash_password(senha),
        clinica_id=clinica.id,
        is_admin=bool(payload.is_admin),
        ativo=True,
        is_system_user=False,
    )
    db.add(usuario)
    if payload.ativar_clinica:
        clinica.ativo = True

    registrar_auditoria(
        db=db,
        actor=current_user,
        acao="usuario_create",
        alvo_tipo="usuario",
        alvo_id=usuario.id,
        detalhes={
            "clinica_id": clinica.id,
            "email": email,
            "is_admin": bool(payload.is_admin),
            "ativar_clinica": bool(payload.ativar_clinica),
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(usuario)
    return {
        "detail": "Usuario criado com sucesso.",
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "clinica_id": usuario.clinica_id,
        "is_admin": bool(usuario.is_admin),
        "ativo": bool(usuario.ativo),
    }


@router.get("/usuarios")
def superadmin_list_usuarios(
    q: str = Query(default="", max_length=120),
    clinica_id: int | None = Query(default=None, ge=1),
    ativo: str | None = Query(default=None),
    admin: str | None = Query(default=None),
    plano: str | None = Query(default=None, max_length=20),
    clinica_status: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=300, ge=1, le=2000),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superadmin(current_user)
    return _listar_usuarios_superadmin(
        db=db,
        q=q,
        clinica_id=clinica_id,
        ativo=ativo,
        admin=admin,
        plano=plano,
        clinica_status=clinica_status,
        limit=limit,
    )


@router.get("/usuarios/export.csv")
def superadmin_export_usuarios_csv(
    q: str = Query(default="", max_length=120),
    clinica_id: int | None = Query(default=None, ge=1),
    ativo: str | None = Query(default=None),
    admin: str | None = Query(default=None),
    plano: str | None = Query(default=None, max_length=20),
    clinica_status: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=5000, ge=1, le=20000),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superadmin(current_user)
    rows = _listar_usuarios_superadmin(
        db=db,
        q=q,
        clinica_id=clinica_id,
        ativo=ativo,
        admin=admin,
        plano=plano,
        clinica_status=clinica_status,
        limit=limit,
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        [
            "usuario_id",
            "nome",
            "email",
            "perfil",
            "status_usuario",
            "is_owner_account",
            "clinica_id",
            "clinica_nome",
            "clinica_email",
            "clinica_plano",
            "clinica_status",
            "clinica_trial_ate",
            "clinica_data_ativacao",
            "clinica_cnpj",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r.get("id"),
                r.get("nome") or "",
                r.get("email") or "",
                "Admin" if r.get("is_admin") else "Usuario",
                "Ativo" if r.get("ativo") else "Inativo",
                "Sim" if r.get("is_owner_account") else "Nao",
                r.get("clinica_id"),
                r.get("clinica_nome") or "",
                r.get("clinica_email") or "",
                r.get("clinica_plano") or "",
                r.get("clinica_status") or "",
                r.get("clinica_trial_ate") or "",
                r.get("clinica_data_ativacao") or "",
                r.get("clinica_cnpj") or "",
            ]
        )
    filename = f"usuarios_plataforma_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=buffer.getvalue(), media_type="text/csv; charset=utf-8", headers=headers)


@router.post("/usuarios/{user_id}/reset-senha")
def superadmin_reset_usuario_senha(
    user_id: int,
    payload: SuperAdminResetUserSenhaPayload,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superadmin(current_user)
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")
    if is_owner_email(usuario.email):
        raise HTTPException(status_code=400, detail="Conta proprietaria nao pode ser alterada por este endpoint.")
    if is_system_user(usuario):
        raise HTTPException(status_code=400, detail="Conta base 'Clínica' é protegida.")

    nova_senha = (payload.nova_senha or "").strip()
    if len(nova_senha) < 6:
        raise HTTPException(status_code=400, detail="Senha deve ter no minimo 6 caracteres.")

    usuario.senha_hash = hash_password(nova_senha)
    registrar_auditoria(
        db=db,
        actor=current_user,
        acao="usuario_reset_senha",
        alvo_tipo="usuario",
        alvo_id=usuario.id,
        detalhes={"email": usuario.email},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return {
        "detail": "Senha do usuario redefinida com sucesso.",
        "id": usuario.id,
    }


@router.patch("/usuarios/{user_id}/status")
def superadmin_set_usuario_status(
    user_id: int,
    payload: SuperAdminSetUserStatusPayload,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superadmin(current_user)
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")
    if is_owner_email(usuario.email):
        raise HTTPException(status_code=400, detail="Conta proprietaria nao pode ser alterada por este endpoint.")
    if is_system_user(usuario):
        raise HTTPException(status_code=400, detail="Conta base 'Clínica' é protegida.")

    usuario.ativo = bool(payload.ativo)
    registrar_auditoria(
        db=db,
        actor=current_user,
        acao="usuario_status_update",
        alvo_tipo="usuario",
        alvo_id=usuario.id,
        detalhes={"ativo": bool(payload.ativo), "email": usuario.email},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(usuario)
    return {
        "detail": "Status do usuario atualizado.",
        "id": usuario.id,
        "ativo": bool(usuario.ativo),
    }


@router.patch("/usuarios/{user_id}/perfil")
def superadmin_set_usuario_perfil(
    user_id: int,
    payload: SuperAdminSetUserPerfilPayload,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superadmin(current_user)
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")
    if is_owner_email(usuario.email):
        raise HTTPException(status_code=400, detail="Conta proprietaria nao pode ser alterada por este endpoint.")
    if is_system_user(usuario):
        raise HTTPException(status_code=400, detail="Conta base 'Clínica' é protegida.")

    usuario.is_admin = bool(payload.is_admin)
    registrar_auditoria(
        db=db,
        actor=current_user,
        acao="usuario_perfil_update",
        alvo_tipo="usuario",
        alvo_id=usuario.id,
        detalhes={"is_admin": bool(payload.is_admin), "email": usuario.email},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(usuario)
    return {
        "detail": "Perfil do usuario atualizado.",
        "id": usuario.id,
        "is_admin": bool(usuario.is_admin),
    }


@router.patch("/clinicas/{clinica_id}/status")
def superadmin_set_clinica_status(
    clinica_id: int,
    payload: SuperAdminSetStatusPayload,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superadmin(current_user)
    clinica = db.query(Clinica).filter(Clinica.id == clinica_id).first()
    if not clinica:
        raise HTTPException(status_code=404, detail="Clinica nao encontrada.")
    if _is_owner_clinica(db, clinica.id) and not is_owner_email(current_user.email):
        raise HTTPException(status_code=403, detail="Clinica MASTER nao pode ser alterada por este endpoint.")

    clinica.ativo = bool(payload.ativo)
    sync_assinatura_from_clinica(db, clinica)
    registrar_auditoria(
        db=db,
        actor=current_user,
        acao="clinica_status_update",
        alvo_tipo="clinica",
        alvo_id=clinica.id,
        detalhes={
            "ativo": bool(payload.ativo),
            "motivo": (payload.motivo or "").strip(),
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(clinica)
    return {
        "detail": "Status da clinica atualizado.",
        "clinica_id": clinica.id,
        "ativo": bool(clinica.ativo),
        "assinatura_status": assinatura_status_from_clinica(clinica),
    }


@router.patch("/clinicas/{clinica_id}/plano")
def superadmin_set_clinica_plano(
    clinica_id: int,
    payload: SuperAdminSetPlanoPayload,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superadmin(current_user)
    clinica = db.query(Clinica).filter(Clinica.id == clinica_id).first()
    if not clinica:
        raise HTTPException(status_code=404, detail="Clinica nao encontrada.")
    if _is_owner_clinica(db, clinica.id) and not is_owner_email(current_user.email):
        raise HTTPException(status_code=403, detail="Clinica MASTER nao pode ser alterada por este endpoint.")

    try:
        plano_norm, dias = aplicar_plano_na_clinica(clinica, payload.plano, payload.dias)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not payload.manter_ativo:
        clinica.ativo = False

    sync_assinatura_from_clinica(db, clinica)
    registrar_auditoria(
        db=db,
        actor=current_user,
        acao="clinica_plano_update",
        alvo_tipo="clinica",
        alvo_id=clinica.id,
        detalhes={
            "plano": plano_norm,
            "dias": dias,
            "manter_ativo": payload.manter_ativo,
            "tipo_conta": clinica.tipo_conta,
            "trial_ate": _fmt_datetime(clinica.trial_ate),
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(clinica)

    return {
        "detail": "Plano da clinica atualizado.",
        "clinica_id": clinica.id,
        "plano": plano_norm,
        "tipo_conta": clinica.tipo_conta,
        "trial_ate": _fmt_datetime(clinica.trial_ate),
        "ativo": bool(clinica.ativo),
        "assinatura_status": assinatura_status_from_clinica(clinica),
    }


@router.patch("/clinicas/{clinica_id}/trial-extra")
def superadmin_extend_clinica_trial(
    clinica_id: int,
    payload: SuperAdminExtendTrialPayload,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superadmin(current_user)
    clinica = db.query(Clinica).filter(Clinica.id == clinica_id).first()
    if not clinica:
        raise HTTPException(status_code=404, detail="Clinica nao encontrada.")
    if _is_owner_clinica(db, clinica.id) and not is_owner_email(current_user.email):
        raise HTTPException(status_code=403, detail="Clinica MASTER nao pode ser alterada por este endpoint.")

    dias = int(payload.dias or 0)
    if dias < 1 or dias > 3650:
        raise HTTPException(status_code=400, detail="Dias invalidos. Informe entre 1 e 3650.")

    base = clinica.trial_ate if clinica.trial_ate and clinica.trial_ate > datetime.utcnow() else datetime.utcnow()
    clinica.trial_ate = base + timedelta(days=dias)
    clinica.tipo_conta = "DEMO 7 dias"
    clinica.ativo = True

    sync_assinatura_from_clinica(db, clinica)
    registrar_auditoria(
        db=db,
        actor=current_user,
        acao="clinica_trial_extend",
        alvo_tipo="clinica",
        alvo_id=clinica.id,
        detalhes={"dias": dias, "trial_ate": _fmt_datetime(clinica.trial_ate)},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(clinica)
    return {
        "detail": f"Teste prorrogado por {dias} dias.",
        "clinica_id": clinica.id,
        "dias": dias,
        "tipo_conta": clinica.tipo_conta,
        "trial_ate": _fmt_datetime(clinica.trial_ate),
        "ativo": bool(clinica.ativo),
        "assinatura_status": assinatura_status_from_clinica(clinica),
    }


@router.delete("/clinicas/{clinica_id}")
def superadmin_delete_clinica(
    clinica_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superadmin(current_user)
    clinica = db.query(Clinica).filter(Clinica.id == clinica_id).first()
    if not clinica:
        raise HTTPException(status_code=404, detail="Clinica nao encontrada.")
    if _is_owner_clinica(db, clinica.id):
        raise HTTPException(status_code=403, detail="Clinica MASTER nao pode ser excluida.")

    detalhes = _delete_clinica_definitiva(db, clinica)
    registrar_auditoria(
        db=db,
        actor=current_user,
        acao="clinica_delete_definitivo",
        alvo_tipo="clinica",
        alvo_id=clinica_id,
        detalhes=detalhes,
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return {
        "detail": "Conta removida definitivamente.",
        **detalhes,
    }


@router.get("/cobrancas")
def superadmin_list_cobrancas(
    status: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=200, ge=1, le=1000),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superadmin(current_user)

    query = db.query(PlataformaCobranca)
    status_term = (status or "").strip().lower()
    if status_term:
        query = query.filter(func.lower(PlataformaCobranca.status) == status_term)

    rows = query.order_by(PlataformaCobranca.criado_em.desc(), PlataformaCobranca.id.desc()).limit(limit).all()
    clinicas = {c.id: c.nome for c in db.query(Clinica.id, Clinica.nome).all()}

    return [
        {
            "id": r.id,
            "clinica_id": r.clinica_id,
            "clinica_nome": clinicas.get(r.clinica_id),
            "payment_id": r.payment_id,
            "external_reference": r.external_reference,
            "plano": r.plano,
            "status": r.status,
            "valor": float(r.valor or 0),
            "moeda": r.moeda,
            "origem": r.origem,
            "criado_em": _fmt_datetime(r.criado_em),
            "atualizado_em": _fmt_datetime(r.atualizado_em),
        }
        for r in rows
    ]


@router.get("/auditoria")
def superadmin_list_auditoria(
    limit: int = Query(default=200, ge=1, le=1000),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superadmin(current_user)
    rows = (
        db.query(PlataformaAuditoria)
        .order_by(PlataformaAuditoria.criado_em.desc(), PlataformaAuditoria.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "actor_user_id": r.actor_user_id,
            "actor_email": r.actor_email,
            "acao": r.acao,
            "alvo_tipo": r.alvo_tipo,
            "alvo_id": r.alvo_id,
            "detalhes_json": r.detalhes_json,
            "ip": r.ip,
            "criado_em": _fmt_datetime(r.criado_em),
        }
        for r in rows
    ]


@router.get("/assinaturas")
def superadmin_list_assinaturas(
    limit: int = Query(default=500, ge=1, le=2000),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superadmin(current_user)
    rows = db.query(PlataformaAssinatura).order_by(PlataformaAssinatura.clinica_id.asc()).limit(limit).all()
    clinicas = {c.id: c.nome for c in db.query(Clinica.id, Clinica.nome).all()}
    return [
        {
            "id": r.id,
            "clinica_id": r.clinica_id,
            "clinica_nome": clinicas.get(r.clinica_id),
            "plano": r.plano,
            "status": r.status,
            "inicio_em": _fmt_datetime(r.inicio_em),
            "fim_em": _fmt_datetime(r.fim_em),
            "proxima_cobranca_em": _fmt_datetime(r.proxima_cobranca_em),
            "bloqueada": bool(r.bloqueada),
            "atualizado_em": _fmt_datetime(r.atualizado_em),
        }
        for r in rows
    ]
