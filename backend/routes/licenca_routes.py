import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.clinica import Clinica
from models.usuario import Usuario
from security.dependencies import get_current_user
from security.superadmin import is_owner_email, is_superadmin_account_type
from services.platform_admin_service import (
    registrar_auditoria,
    registrar_checkout_cobranca,
    registrar_pagamento_cobranca,
    sync_assinatura_from_clinica,
)

router = APIRouter(prefix="/licenca", tags=["licenca"])

VERSAO_SISTEMA = "1.0.0"
EMAIL_SUPORTE = os.getenv("LICENCA_SUPORTE_EMAIL", "institutobrana@gmail.com").strip() or "institutobrana@gmail.com"

MERCADOPAGO_ACCESS_TOKEN = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "").strip()
MERCADOPAGO_API_BASE = (
    os.getenv("MERCADOPAGO_API_BASE", "https://api.mercadopago.com").strip()
    or "https://api.mercadopago.com"
).rstrip("/")
MERCADOPAGO_WEBHOOK_URL = os.getenv("MERCADOPAGO_WEBHOOK_URL", "").strip()
MERCADOPAGO_BACK_URL = os.getenv("MERCADOPAGO_BACK_URL", "").strip()
MERCADOPAGO_USE_SANDBOX = os.getenv("MERCADOPAGO_USE_SANDBOX", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

PAGAMENTO_MENSAL_URL_FALLBACK = os.getenv("PAGAMENTO_MENSAL_URL", "https://mpago.la/2cBeBE9").strip()
PAGAMENTO_ANUAL_URL_FALLBACK = os.getenv("PAGAMENTO_ANUAL_URL", "https://mpago.li/1yGWto9").strip()


def _env_price(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)).strip())
    except Exception:
        return float(default)


PLANO_MENSAL_VALOR = _env_price("PLANO_MENSAL_VALOR", 149.90)
PLANO_ANUAL_VALOR = _env_price("PLANO_ANUAL_VALOR", 1499.00)

PLANO_CONFIG = {
    "MENSAL": {
        "tipo_conta": "Mensal",
        "duracao_dias": 30,
        "titulo": "Brana SaaS - Plano mensal",
        "valor": PLANO_MENSAL_VALOR,
        "fallback_url": PAGAMENTO_MENSAL_URL_FALLBACK,
    },
    "ANUAL": {
        "tipo_conta": "Anual",
        "duracao_dias": 365,
        "titulo": "Brana SaaS - Plano anual",
        "valor": PLANO_ANUAL_VALOR,
        "fallback_url": PAGAMENTO_ANUAL_URL_FALLBACK,
    },
}


class CheckoutLicencaPayload(BaseModel):
    plano: str


class ConfirmarPagamentoPayload(BaseModel):
    payment_id: str


class SincronizarPagamentoPayload(BaseModel):
    external_reference: str | None = None


def _mercadopago_habilitado() -> bool:
    return bool(MERCADOPAGO_ACCESS_TOKEN)


def _assunto_plano(plano: str, strict: bool = True) -> str | None:
    valor = (plano or "").strip().upper()
    if valor in {"MENSAL", "MENSALIDADE", "MONTHLY"}:
        return "MENSAL"
    if valor in {"ANUAL", "YEARLY", "ANNUAL"}:
        return "ANUAL"
    if strict:
        raise HTTPException(status_code=400, detail="Plano invalido. Use: Mensal ou Anual.")
    return None


def _plano_from_tipo_conta(tipo_conta: str | None) -> str:
    base = (tipo_conta or "DEMO 7 dias").strip().lower()
    if is_superadmin_account_type(base):
        return "SUPERADMIN"
    if "anual" in base:
        return "ANUAL"
    if "mensal" in base:
        return "MENSAL"
    return "DEMO"


def _licenca_expirada(clinica: Clinica) -> bool:
    if not clinica.trial_ate:
        return True
    return clinica.trial_ate < datetime.utcnow()


def _dias_restantes(clinica: Clinica) -> int:
    if not clinica.trial_ate:
        return 0
    return max(0, (clinica.trial_ate.date() - datetime.utcnow().date()).days)


def _status_licenca(clinica: Clinica) -> str:
    if is_superadmin_account_type(clinica.tipo_conta):
        return "SUPERADMIN"
    if _licenca_expirada(clinica):
        return "EXPIRADO"
    return _plano_from_tipo_conta(clinica.tipo_conta)


def _fmt_date(value: datetime | None) -> str:
    if not value:
        return "-"
    return value.strftime("%d/%m/%Y")


def _mensagem_ativacao(status: str, dias: int, data_limite: str, automatico: bool) -> str:
    if status == "SUPERADMIN":
        return "Conta Super Admin com acesso permanente."
    if status == "DEMO":
        return f"Sua versao DEMO expira em {dias} dias."
    if status == "MENSAL":
        return f"Plano mensal ativo ate {data_limite}."
    if status == "ANUAL":
        return f"Plano anual ativo ate {data_limite}."
    if automatico:
        return "Licenca expirada. Escolha Mensal ou Anual e conclua o pagamento no Mercado Pago."
    return "Licenca expirada. Configure o Mercado Pago para ativacao automatica."


def _mensagem_sobre(status: str, dias: int, data_limite: str) -> str:
    if status == "SUPERADMIN":
        return "CONTA SUPER ADMIN | ACESSO PERMANENTE"
    if status == "DEMO":
        return f"VERSAO DEMO | Expira em {dias} dias"
    if status == "MENSAL":
        return f"PLANO MENSAL ATIVADO | Valido ate {data_limite}"
    if status == "ANUAL":
        return f"PLANO ANUAL ATIVADO | Valido ate {data_limite}"
    return "LICENCA EXPIRADA"


def _serial_conta(clinica_id: int) -> str:
    ano = datetime.utcnow().year
    base = str(clinica_id).zfill(4)[-4:]
    return f"BRANA-{ano}-{base}"


def _clinica_or_404(db: Session, current_user: Usuario) -> Clinica:
    clinica = db.query(Clinica).filter(Clinica.id == current_user.clinica_id).first()
    if not clinica:
        raise HTTPException(status_code=404, detail="Clinica nao encontrada.")
    return clinica


def _montar_info(clinica: Clinica, current_user: Usuario | None = None) -> dict:
    status = _status_licenca(clinica)
    dias = _dias_restantes(clinica)
    plano = _plano_from_tipo_conta(clinica.tipo_conta)
    owner = bool(current_user and is_owner_email(current_user.email))
    if owner:
        # Conta proprietaria nao segue janela DEMO/expiracao.
        status = "OWNER"
        plano = "OWNER"
        dias = 9999
    usuario_registro = (
        (clinica.licenca_usuario or "").strip()
        or (clinica.nome or "").strip()
        or ((current_user.nome or "").strip() if current_user else "")
        or "Registrado"
    )
    data_limite = _fmt_date(clinica.trial_ate)
    automatico = _mercadopago_habilitado()
    mensagem_ativacao = _mensagem_ativacao(status, dias, data_limite, automatico)
    mensagem_sobre = _mensagem_sobre(status, dias, data_limite)
    if owner:
        mensagem_ativacao = "Conta proprietaria com acesso permanente."
        mensagem_sobre = "CONTA PROPRIETARIA | ACESSO PERMANENTE"
        data_limite = "-"
    return {
        "status": status,
        "plano": plano,
        "dias_restantes": dias,
        "expira_em": data_limite,
        "usuario_registro": usuario_registro,
        "versao_sistema": VERSAO_SISTEMA,
        "email_suporte": EMAIL_SUPORTE,
        "machine_id": f"CLINICA-{clinica.id}",
        "serial": _serial_conta(clinica.id),
        "mensagem_ativacao": mensagem_ativacao,
        "mensagem_sobre": mensagem_sobre,
        "checkout_disponivel": automatico,
        "preco_mensal": PLANO_MENSAL_VALOR,
        "preco_anual": PLANO_ANUAL_VALOR,
        "pagamento_mensal_url": PAGAMENTO_MENSAL_URL_FALLBACK,
        "pagamento_anual_url": PAGAMENTO_ANUAL_URL_FALLBACK,
    }


def _resolve_base_url(request: Request) -> str:
    if MERCADOPAGO_BACK_URL:
        return MERCADOPAGO_BACK_URL.rstrip("/")
    return str(request.base_url).rstrip("/")


def _resolve_webhook_url(request: Request) -> str:
    if MERCADOPAGO_WEBHOOK_URL:
        return MERCADOPAGO_WEBHOOK_URL.strip()
    return f"{_resolve_base_url(request)}/licenca/mercadopago/webhook"


def _mercadopago_request(method: str, path: str, payload: dict | None = None) -> dict:
    if not _mercadopago_habilitado():
        raise HTTPException(
            status_code=503,
            detail="Mercado Pago nao configurado. Defina MERCADOPAGO_ACCESS_TOKEN.",
        )

    url = path if path.startswith("http") else f"{MERCADOPAGO_API_BASE}{path}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Bearer {MERCADOPAGO_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    req = UrlRequest(url=url, data=body, headers=headers, method=method.upper())

    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
            return data if isinstance(data, dict) else {}
    except HTTPError as exc:
        detalhe = "Falha ao comunicar com Mercado Pago."
        try:
            raw = exc.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
            if isinstance(data, dict):
                detalhe = str(
                    data.get("message")
                    or data.get("error_description")
                    or data.get("error")
                    or detalhe
                )
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=f"Mercado Pago: {detalhe}") from exc
    except URLError as exc:
        raise HTTPException(status_code=502, detail="Mercado Pago indisponivel.") from exc


def _to_int(value) -> int | None:
    try:
        return int(str(value).strip())
    except Exception:
        return None


def _gerar_external_reference(clinica_id: int, plano: str) -> str:
    return f"BRANA|{clinica_id}|{plano}|{int(datetime.utcnow().timestamp())}"


def _parse_external_reference(external_reference: str | None) -> tuple[int | None, str | None]:
    parts = str(external_reference or "").strip().split("|")
    if len(parts) >= 3 and parts[0] == "BRANA":
        clinica_id = _to_int(parts[1])
        plano = _assunto_plano(parts[2], strict=False)
        return clinica_id, plano
    return None, None


def _parse_mp_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.utcnow()
    raw = str(value).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except Exception:
        return datetime.utcnow()
    if dt.tzinfo:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _extract_payment_id(body: dict, request: Request) -> str:
    q = request.query_params
    payment_id = (q.get("data.id") or q.get("id") or "").strip()
    if payment_id:
        return payment_id

    data = body.get("data") if isinstance(body, dict) else None
    if isinstance(data, dict):
        candidate = str(data.get("id") or "").strip()
        if candidate:
            return candidate

    resource = body.get("resource") if isinstance(body, dict) else None
    if isinstance(resource, str):
        match = re.search(r"/v1/payments/(\d+)", resource)
        if match:
            return match.group(1)
    return ""


def _extract_plano_from_pagamento(pagamento: dict) -> str | None:
    metadata = pagamento.get("metadata") if isinstance(pagamento, dict) else None
    if isinstance(metadata, dict):
        plano_meta = _assunto_plano(str(metadata.get("plano") or ""), strict=False)
        if plano_meta:
            return plano_meta

    _, plano_ref = _parse_external_reference(str(pagamento.get("external_reference") or ""))
    if plano_ref:
        return plano_ref

    descricao = str(pagamento.get("description") or "").lower()
    if "anual" in descricao:
        return "ANUAL"
    if "mensal" in descricao:
        return "MENSAL"
    return None


def _extract_clinica_id_from_pagamento(pagamento: dict) -> int | None:
    metadata = pagamento.get("metadata") if isinstance(pagamento, dict) else None
    if isinstance(metadata, dict):
        clinica_id = _to_int(metadata.get("clinica_id"))
        if clinica_id:
            return clinica_id

    clinica_ref, _ = _parse_external_reference(str(pagamento.get("external_reference") or ""))
    return clinica_ref


def _aplicar_pagamento_aprovado(db: Session, clinica: Clinica, plano: str, payment_id: str, data_base: datetime) -> bool:
    token_pagamento = f"MP:{payment_id}"
    if (clinica.chave_licenca or "").strip() == token_pagamento:
        return False

    cfg = PLANO_CONFIG[plano]
    inicio = data_base
    if clinica.trial_ate and clinica.trial_ate > inicio:
        inicio = clinica.trial_ate

    clinica.tipo_conta = cfg["tipo_conta"]
    clinica.trial_ate = inicio + timedelta(days=int(cfg["duracao_dias"]))
    clinica.ativo = True
    if not (clinica.licenca_usuario or "").strip():
        clinica.licenca_usuario = (clinica.nome or "").strip() or "Registrado"
    clinica.chave_licenca = token_pagamento
    clinica.data_ativacao = datetime.utcnow()
    return True


def _processar_pagamento(
    db: Session,
    payment_id: str,
    clinica_forcada_id: int | None = None,
    origem: str = "api",
    actor: Usuario | None = None,
    request_ip: str | None = None,
) -> dict:
    pagamento = _mercadopago_request("GET", f"/v1/payments/{payment_id}")
    status_pagamento = str(pagamento.get("status") or "").lower()
    plano = _extract_plano_from_pagamento(pagamento)
    clinica_id_pagamento = _extract_clinica_id_from_pagamento(pagamento) or clinica_forcada_id
    valor = pagamento.get("transaction_amount")
    moeda = pagamento.get("currency_id") or "BRL"
    external_reference = str(pagamento.get("external_reference") or "").strip() or None

    if clinica_id_pagamento:
        registrar_pagamento_cobranca(
            db=db,
            clinica_id=int(clinica_id_pagamento),
            payment_id=payment_id,
            external_reference=external_reference,
            plano=plano,
            status=status_pagamento or "unknown",
            valor=float(valor) if valor is not None else None,
            moeda=str(moeda or "BRL"),
            origem=origem,
            payload=pagamento,
        )

    if status_pagamento != "approved":
        db.commit()
        return {
            "aprovado": False,
            "aplicado": False,
            "detail": "Pagamento ainda nao aprovado.",
            "status_pagamento": status_pagamento or "unknown",
        }

    if not plano:
        db.commit()
        return {
            "aprovado": True,
            "aplicado": False,
            "detail": "Pagamento aprovado sem plano identificavel.",
            "status_pagamento": status_pagamento,
        }

    if not clinica_id_pagamento:
        db.commit()
        return {
            "aprovado": True,
            "aplicado": False,
            "detail": "Pagamento aprovado sem clinica identificavel.",
            "status_pagamento": status_pagamento,
        }

    if clinica_forcada_id and clinica_forcada_id != clinica_id_pagamento:
        raise HTTPException(status_code=403, detail="Pagamento nao pertence a esta clinica.")

    clinica = db.query(Clinica).filter(Clinica.id == clinica_id_pagamento).first()
    if not clinica:
        db.commit()
        return {
            "aprovado": True,
            "aplicado": False,
            "detail": "Clinica do pagamento nao encontrada.",
            "status_pagamento": status_pagamento,
        }

    data_base = _parse_mp_datetime(str(pagamento.get("date_approved") or ""))
    aplicado = _aplicar_pagamento_aprovado(db, clinica, plano, payment_id, data_base)
    sync_assinatura_from_clinica(db, clinica)
    if aplicado:
        registrar_auditoria(
            db=db,
            actor=actor,
            acao="licenca_pagamento_aprovado",
            alvo_tipo="clinica",
            alvo_id=clinica.id,
            detalhes={
                "payment_id": payment_id,
                "plano": plano,
                "status_pagamento": status_pagamento,
            },
            ip=request_ip,
        )
    db.commit()
    db.refresh(clinica)
    return {
        "aprovado": True,
        "aplicado": aplicado,
        "detail": "Pagamento processado com sucesso." if aplicado else "Pagamento ja processado.",
        "status_pagamento": status_pagamento,
        "clinica_id": clinica.id,
        "plano": plano,
    }


def _buscar_pagamento_aprovado_para_clinica(
    clinica_id: int,
    email: str | None = None,
    external_reference: str | None = None,
) -> dict | None:
    params = {
        "sort": "date_created",
        "criteria": "desc",
        "limit": 30,
    }
    if email:
        params["payer.email"] = email.strip()
    if external_reference:
        params["external_reference"] = external_reference.strip()

    query = urlencode(params)
    resultado = _mercadopago_request("GET", f"/v1/payments/search?{query}")
    pagamentos = resultado.get("results")
    if not isinstance(pagamentos, list):
        return None

    for pagamento in pagamentos:
        if not isinstance(pagamento, dict):
            continue
        if str(pagamento.get("status") or "").lower() != "approved":
            continue
        if external_reference:
            if str(pagamento.get("external_reference") or "").strip() != external_reference.strip():
                continue
        clinica_pagamento = _extract_clinica_id_from_pagamento(pagamento)
        if clinica_pagamento != clinica_id:
            continue
        if not _extract_plano_from_pagamento(pagamento):
            continue
        return pagamento

    return None


@router.get("/info")
def info_licenca(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica = _clinica_or_404(db, current_user)
    return _montar_info(clinica, current_user)


@router.post("/checkout")
def criar_checkout_licenca(
    payload: CheckoutLicencaPayload,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica = _clinica_or_404(db, current_user)
    plano = _assunto_plano(payload.plano, strict=True)
    cfg = PLANO_CONFIG[plano]
    external_reference = _gerar_external_reference(clinica.id, plano)

    if not _mercadopago_habilitado():
        fallback_url = cfg.get("fallback_url") or ""
        if not fallback_url:
            raise HTTPException(
                status_code=503,
                detail="Mercado Pago nao configurado. Defina MERCADOPAGO_ACCESS_TOKEN.",
            )
        registrar_checkout_cobranca(
            db=db,
            clinica_id=clinica.id,
            plano=plano,
            external_reference=external_reference,
            valor=float(cfg["valor"]),
            origem="checkout_fallback",
        )
        sync_assinatura_from_clinica(db, clinica)
        registrar_auditoria(
            db=db,
            actor=current_user,
            acao="licenca_checkout_criado",
            alvo_tipo="clinica",
            alvo_id=clinica.id,
            detalhes={"plano": plano, "modo": "fallback", "external_reference": external_reference},
            ip=request.client.host if request.client else None,
        )
        db.commit()
        return {
            "detail": "Checkout em modo fallback por link direto.",
            "automatico": False,
            "plano": plano,
            "checkout_url": fallback_url,
            "external_reference": external_reference,
            "preference_id": None,
        }

    base_url = _resolve_base_url(request)
    app_url = f"{base_url}/app"
    preference_payload = {
        "items": [
            {
                "id": f"brana-{plano.lower()}",
                "title": cfg["titulo"],
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(cfg["valor"]),
            }
        ],
        "metadata": {
            "clinica_id": str(clinica.id),
            "plano": plano,
        },
        "external_reference": external_reference,
        "notification_url": _resolve_webhook_url(request),
        "back_urls": {
            "success": f"{app_url}?pagamento=aprovado",
            "failure": f"{app_url}?pagamento=falhou",
            "pending": f"{app_url}?pagamento=pendente",
        },
        "auto_return": "approved",
        "statement_descriptor": "BRANA SAAS",
    }
    payer_email = (current_user.email or "").strip().lower()
    if payer_email:
        preference_payload["payer"] = {"email": payer_email}

    preference = _mercadopago_request("POST", "/checkout/preferences", preference_payload)
    checkout_url = (
        preference.get("sandbox_init_point")
        if MERCADOPAGO_USE_SANDBOX
        else preference.get("init_point")
    ) or preference.get("init_point") or preference.get("sandbox_init_point")
    if not checkout_url:
        raise HTTPException(status_code=502, detail="Mercado Pago nao retornou URL de checkout.")

    registrar_checkout_cobranca(
        db=db,
        clinica_id=clinica.id,
        plano=plano,
        external_reference=external_reference,
        valor=float(cfg["valor"]),
        origem="checkout",
    )
    sync_assinatura_from_clinica(db, clinica)
    registrar_auditoria(
        db=db,
        actor=current_user,
        acao="licenca_checkout_criado",
        alvo_tipo="clinica",
        alvo_id=clinica.id,
        detalhes={"plano": plano, "modo": "mercadopago", "external_reference": external_reference},
        ip=request.client.host if request.client else None,
    )
    db.commit()

    return {
        "detail": "Checkout Mercado Pago criado com sucesso.",
        "automatico": True,
        "plano": plano,
        "checkout_url": checkout_url,
        "external_reference": external_reference,
        "preference_id": preference.get("id"),
    }


@router.post("/confirmar")
def confirmar_pagamento_licenca(
    payload: ConfirmarPagamentoPayload,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payment_id = (payload.payment_id or "").strip()
    if not payment_id:
        raise HTTPException(status_code=400, detail="payment_id e obrigatorio.")

    resultado = _processar_pagamento(
        db=db,
        payment_id=payment_id,
        clinica_forcada_id=current_user.clinica_id,
        origem="confirmar_api",
        actor=current_user,
        request_ip=request.client.host if request.client else None,
    )
    clinica = _clinica_or_404(db, current_user)

    if not resultado.get("aprovado"):
        return {
            "detail": resultado.get("detail") or "Pagamento ainda nao aprovado.",
            "aprovado": False,
            "aplicado": False,
            "status_pagamento": resultado.get("status_pagamento"),
            "info": _montar_info(clinica, current_user),
        }

    return {
        "detail": "Licenca atualizada automaticamente pelo pagamento." if resultado.get("aplicado") else resultado.get("detail"),
        "aprovado": True,
        "aplicado": bool(resultado.get("aplicado")),
        "status_pagamento": resultado.get("status_pagamento"),
        "info": _montar_info(clinica, current_user),
    }


@router.post("/sincronizar")
def sincronizar_pagamento_licenca(
    payload: SincronizarPagamentoPayload,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _mercadopago_habilitado():
        raise HTTPException(
            status_code=503,
            detail="Mercado Pago nao configurado. Defina MERCADOPAGO_ACCESS_TOKEN.",
        )

    clinica = _clinica_or_404(db, current_user)
    pagamento = _buscar_pagamento_aprovado_para_clinica(
        clinica_id=clinica.id,
        email=(current_user.email or "").strip(),
        external_reference=(payload.external_reference or "").strip() or None,
    )
    if not pagamento:
        return {
            "detail": "Nenhum pagamento aprovado encontrado para esta conta.",
            "aprovado": False,
            "aplicado": False,
            "info": _montar_info(clinica, current_user),
        }

    payment_id = str(pagamento.get("id") or "").strip()
    if not payment_id:
        return {
            "detail": "Pagamento encontrado sem id valido.",
            "aprovado": False,
            "aplicado": False,
            "info": _montar_info(clinica, current_user),
        }

    resultado = _processar_pagamento(
        db=db,
        payment_id=payment_id,
        clinica_forcada_id=current_user.clinica_id,
        origem="sincronizar_api",
        actor=current_user,
        request_ip=request.client.host if request.client else None,
    )
    clinica = _clinica_or_404(db, current_user)
    return {
        "detail": resultado.get("detail") or "Sincronizacao concluida.",
        "aprovado": bool(resultado.get("aprovado")),
        "aplicado": bool(resultado.get("aplicado")),
        "status_pagamento": resultado.get("status_pagamento"),
        "info": _montar_info(clinica, current_user),
    }


@router.api_route("/mercadopago/webhook", methods=["POST", "GET"])
async def webhook_mercadopago(
    request: Request,
    db: Session = Depends(get_db),
):
    if not _mercadopago_habilitado():
        return {"detail": "Webhook ignorado: Mercado Pago nao configurado."}

    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}

    payment_id = _extract_payment_id(body, request)
    if not payment_id:
        return {"detail": "Evento recebido sem payment_id. Ignorado."}

    try:
        resultado = _processar_pagamento(
            db=db,
            payment_id=payment_id,
            clinica_forcada_id=None,
            origem="webhook_mp",
            actor=None,
            request_ip=request.client.host if request.client else None,
        )
    except HTTPException as exc:
        return {"detail": f"Webhook recebido, mas nao aplicado: {exc.detail}"}

    return {
        "detail": resultado.get("detail") or "Webhook processado.",
        "aprovado": bool(resultado.get("aprovado")),
        "aplicado": bool(resultado.get("aplicado")),
        "status_pagamento": resultado.get("status_pagamento"),
        "clinica_id": resultado.get("clinica_id"),
        "plano": resultado.get("plano"),
    }
