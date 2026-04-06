import json
from typing import Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models.cenario import Cenario
from models.financeiro import CategoriaFinanceira, GrupoFinanceiro, Lancamento
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access

router = APIRouter(
    dependencies=[Depends(require_module_access("financeiro"))],
)
CONTA_PESSOAL_VARIANTES = ["PESSOAL", "CIRURGIAO", "CIRURGIÃO"]
CONTA_CLINICA_VARIANTES = ["EMPRESARIAL", "CLINICA", "CLÍNICA"]


class CenarioPayload(BaseModel):
    meses_trabalhados: float = 0
    dias_uteis_mes: float = 0
    dias_uteis_ano: float = 0
    horas_atendimento_dia: float = 0
    num_consultorios: int = 1
    num_consultorios_flex: int = 1
    horas_ano: float = 0
    modo_horas: str = "Perfil Fixo"
    gasto_anual_particular: float = 0
    gasto_anual_empresa: float = 0
    cartao: float = 0
    ir: float = 0
    cd: float = 0
    custo_ano: float = 0
    cfph: float = 0
    cfpm: float = 0
    total_horas_fixo: float = 0
    total_minutos_fixo: float = 0
    total_turnos_fixo: float = 0
    total_horas_flex: float = 0
    total_minutos_flex: float = 0
    total_turnos_flex: float = 0
    turnos_flex: Dict[str, Dict[str, float]] = {}


class AnoPayload(BaseModel):
    ano: int


def _cenario_to_dict(cenario: Cenario):
    turnos = {}
    try:
        if cenario.turnos_flex:
            turnos = json.loads(cenario.turnos_flex)
    except Exception:
        turnos = {}

    return {
        "meses_trabalhados": float(cenario.meses_trabalhados or 0),
        "dias_uteis_mes": float(cenario.dias_uteis_mes or 0),
        "dias_uteis_ano": float(cenario.dias_uteis_ano or 0),
        "horas_atendimento_dia": float(cenario.horas_atendimento_dia or 0),
        "num_consultorios": int(cenario.num_consultorios or 1),
        "num_consultorios_flex": int(cenario.num_consultorios_flex or 1),
        "horas_ano": float(cenario.horas_ano or 0),
        "modo_horas": cenario.modo_horas or "Perfil Fixo",
        "gasto_anual_particular": float(cenario.gasto_anual_particular or 0),
        "gasto_anual_empresa": float(cenario.gasto_anual_empresa or 0),
        "cartao": float(cenario.cartao or 0),
        "ir": float(cenario.ir or 0),
        "cd": float(cenario.cd or 0),
        "custo_ano": float(cenario.custo_ano or 0),
        "cfph": float(cenario.cfph or 0),
        "cfpm": float(cenario.cfpm or 0),
        "total_horas_fixo": float(cenario.total_horas_fixo or 0),
        "total_minutos_fixo": float(cenario.total_minutos_fixo or 0),
        "total_turnos_fixo": float(cenario.total_turnos_fixo or 0),
        "total_horas_flex": float(cenario.total_horas_flex or 0),
        "total_minutos_flex": float(cenario.total_minutos_flex or 0),
        "total_turnos_flex": float(cenario.total_turnos_flex or 0),
        "turnos_flex": turnos,
    }


def _scenario_default():
    return CenarioPayload().model_dump()


@router.get("/cenario")
def get_cenario(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cenario = db.query(Cenario).filter(Cenario.clinica_id == current_user.clinica_id).first()
    if not cenario:
        return _scenario_default()
    return _cenario_to_dict(cenario)


@router.post("/cenario")
def save_cenario(
    payload: CenarioPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = payload.model_dump()
    data["turnos_flex"] = json.dumps(data["turnos_flex"] or {})

    cenario = db.query(Cenario).filter(Cenario.clinica_id == current_user.clinica_id).first()

    if cenario:
        for key, value in data.items():
            setattr(cenario, key, value)
    else:
        cenario = Cenario(clinica_id=current_user.clinica_id, **data)
        db.add(cenario)

    db.commit()
    return {"detail": "Cenario salvo com sucesso."}


@router.post("/cenario/calcular-fixos")
def calcular_fixos_por_ano(
    payload: AnoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ano = str(payload.ano)

    grupos_alvo = ["Custo fixo pessoal", "Custo fixo profissional"]

    total_pessoal = (
        db.query(func.coalesce(func.sum(Lancamento.valor), 0.0))
        .join(CategoriaFinanceira, CategoriaFinanceira.id == Lancamento.categoria_id)
        .join(GrupoFinanceiro, GrupoFinanceiro.id == CategoriaFinanceira.grupo_id)
        .filter(
            Lancamento.clinica_id == current_user.clinica_id,
            Lancamento.tipo == "debito",
            func.upper(Lancamento.conta).in_(CONTA_PESSOAL_VARIANTES),
            GrupoFinanceiro.nome.in_(grupos_alvo),
            Lancamento.data_pagamento.like(f"%{ano}%"),
        )
        .scalar()
    )

    total_empresa = (
        db.query(func.coalesce(func.sum(Lancamento.valor), 0.0))
        .join(CategoriaFinanceira, CategoriaFinanceira.id == Lancamento.categoria_id)
        .join(GrupoFinanceiro, GrupoFinanceiro.id == CategoriaFinanceira.grupo_id)
        .filter(
            Lancamento.clinica_id == current_user.clinica_id,
            Lancamento.tipo == "debito",
            func.upper(Lancamento.conta).in_(CONTA_CLINICA_VARIANTES),
            GrupoFinanceiro.nome.in_(grupos_alvo),
            Lancamento.data_pagamento.like(f"%{ano}%"),
        )
        .scalar()
    )

    total_anual = float(total_pessoal or 0) + float(total_empresa or 0)

    return {
        "fixo_pessoal": float(total_pessoal or 0),
        "fixo_empresa": float(total_empresa or 0),
        "custo_anual": float(total_anual),
    }
