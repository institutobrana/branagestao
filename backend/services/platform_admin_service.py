import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models.clinica import Clinica
from models.plataforma import PlataformaAssinatura, PlataformaAuditoria, PlataformaCobranca
from models.usuario import Usuario
from security.superadmin import is_superadmin_account_type


def normalize_plano_value(plano: str) -> tuple[str, str, int]:
    value = (plano or "").strip().upper()
    if value in {"DEMO", "DEMO 7 DIAS", "TRIAL"}:
        return "DEMO", "DEMO 7 dias", 7
    if value in {"MENSAL", "MENSALIDADE", "MONTHLY"}:
        return "MENSAL", "Mensal", 30
    if value in {"ANUAL", "YEARLY", "ANNUAL"}:
        return "ANUAL", "Anual", 365
    if value in {"SUPER ADMIN", "SUPERADMIN", "MASTER", "OWNER", "VITALICIA", "VITALÍCIA"}:
        return "SUPERADMIN", "Super Admin", 36500
    raise ValueError("Plano invalido. Use: DEMO, Mensal, Anual ou Super Admin.")


def assinatura_status_from_clinica(clinica: Clinica) -> str:
    if not clinica.ativo:
        return "suspensa"
    if is_superadmin_account_type(clinica.tipo_conta):
        return "ativa"
    if not clinica.trial_ate or clinica.trial_ate < datetime.utcnow():
        return "expirada"
    plano = (clinica.tipo_conta or "DEMO 7 dias").strip().lower()
    if "mensal" in plano or "anual" in plano:
        return "ativa"
    return "trial"


def assinatura_plano_from_clinica(clinica: Clinica) -> str:
    if is_superadmin_account_type(clinica.tipo_conta):
        return "SUPERADMIN"
    plano = (clinica.tipo_conta or "DEMO 7 dias").strip().lower()
    if "mensal" in plano:
        return "MENSAL"
    if "anual" in plano:
        return "ANUAL"
    return "DEMO"


def sync_assinatura_from_clinica(db: Session, clinica: Clinica) -> PlataformaAssinatura:
    assinatura = db.query(PlataformaAssinatura).filter(PlataformaAssinatura.clinica_id == clinica.id).first()
    if not assinatura:
        assinatura = PlataformaAssinatura(clinica_id=clinica.id)
        db.add(assinatura)

    assinatura.plano = assinatura_plano_from_clinica(clinica)
    assinatura.status = assinatura_status_from_clinica(clinica)
    assinatura.inicio_em = clinica.data_ativacao
    assinatura.fim_em = clinica.trial_ate
    assinatura.proxima_cobranca_em = clinica.trial_ate if assinatura.plano in {"MENSAL", "ANUAL"} else None
    assinatura.bloqueada = not clinica.ativo
    db.flush()
    return assinatura


def registrar_checkout_cobranca(
    db: Session,
    clinica_id: int,
    plano: str,
    external_reference: str | None,
    valor: float | None,
    origem: str = "checkout",
):
    row = PlataformaCobranca(
        clinica_id=clinica_id,
        payment_id=None,
        external_reference=(external_reference or "").strip() or None,
        plano=(plano or "").strip().upper() or None,
        status="checkout_open",
        valor=float(valor) if valor is not None else None,
        moeda="BRL",
        origem=(origem or "checkout").strip().lower(),
        payload_json=None,
    )
    db.add(row)
    db.flush()
    return row


def registrar_pagamento_cobranca(
    db: Session,
    clinica_id: int,
    payment_id: str | None,
    external_reference: str | None,
    plano: str | None,
    status: str | None,
    valor: float | None,
    moeda: str | None,
    origem: str,
    payload: dict | None = None,
):
    payment_key = (payment_id or "").strip()
    row = None
    if payment_key:
        row = db.query(PlataformaCobranca).filter(PlataformaCobranca.payment_id == payment_key).first()

    if not row and external_reference:
        row = (
            db.query(PlataformaCobranca)
            .filter(PlataformaCobranca.external_reference == external_reference.strip())
            .order_by(PlataformaCobranca.id.desc())
            .first()
        )

    if not row:
        row = PlataformaCobranca(clinica_id=clinica_id)
        db.add(row)

    row.clinica_id = clinica_id
    row.payment_id = payment_key or row.payment_id
    row.external_reference = (external_reference or "").strip() or row.external_reference
    row.plano = (plano or row.plano or "").strip().upper() or None
    row.status = (status or row.status or "unknown").strip().lower()
    row.valor = float(valor) if valor is not None else row.valor
    row.moeda = (moeda or row.moeda or "BRL").strip().upper()
    row.origem = (origem or row.origem or "webhook").strip().lower()
    if payload is not None:
        row.payload_json = json.dumps(payload, ensure_ascii=True)
    db.flush()
    return row


def registrar_auditoria(
    db: Session,
    actor: Usuario | None,
    acao: str,
    alvo_tipo: str,
    alvo_id: str | int | None = None,
    detalhes: dict | None = None,
    ip: str | None = None,
):
    row = PlataformaAuditoria(
        actor_user_id=int(actor.id) if actor else None,
        actor_email=(actor.email if actor else None),
        acao=(acao or "").strip(),
        alvo_tipo=(alvo_tipo or "").strip(),
        alvo_id=str(alvo_id) if alvo_id is not None else None,
        detalhes_json=json.dumps(detalhes or {}, ensure_ascii=True),
        ip=(ip or "").strip() or None,
    )
    db.add(row)
    db.flush()
    return row


def aplicar_plano_na_clinica(clinica: Clinica, plano: str, dias_override: int | None = None):
    plano_norm, tipo_conta, dias_default = normalize_plano_value(plano)
    dias = int(dias_override) if dias_override is not None else dias_default
    if dias < 1:
        dias = dias_default

    clinica.tipo_conta = tipo_conta
    clinica.trial_ate = datetime.utcnow() + timedelta(days=dias)
    clinica.ativo = True
    if plano_norm in {"MENSAL", "ANUAL", "SUPERADMIN"}:
        clinica.data_ativacao = datetime.utcnow()
    return plano_norm, dias
