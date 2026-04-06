from typing import Any
import unicodedata

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.convenio_odonto import CalendarioFaturamentoOdonto, ConvenioOdonto, PlanoOdonto
from models.paciente import Paciente
from models.procedimento_tabela import ProcedimentoTabela
from models.tratamento import Tratamento
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access

router = APIRouter(
    prefix="/cadastros/convenios-planos",
    tags=["convenios-planos"],
    dependencies=[Depends(require_module_access("configuracao"))],
)


def _clean_text(value: Any, max_len: int | None = None) -> str | None:
    txt = " ".join(str(value or "").split()).strip()
    if not txt:
        return None
    if max_len is not None:
        return txt[:max_len]
    return txt


def _norm_sort(value: Any) -> str:
    txt = str(value or "").strip().lower()
    txt = unicodedata.normalize("NFD", txt)
    return "".join(ch for ch in txt if unicodedata.category(ch) != "Mn")


def _clean_int(value: Any) -> int | None:
    txt = str(value or "").strip()
    if not txt:
        return None
    try:
        return int(float(txt.replace(",", ".")))
    except (TypeError, ValueError):
        return None


class ConvenioPayload(BaseModel):
    codigo: str | None = None
    codigo_ans: str | None = None
    nome: str
    razao_social: str | None = None
    tipo_logradouro: int | None = None
    endereco: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    cep: str | None = None
    uf: str | None = None
    tipo_fone1: int | None = None
    telefone: str | None = None
    contato1: str | None = None
    tipo_fone2: int | None = None
    telefone2: str | None = None
    contato2: str | None = None
    tipo_fone3: int | None = None
    telefone3: str | None = None
    contato3: str | None = None
    tipo_fone4: int | None = None
    telefone4: str | None = None
    contato4: str | None = None
    email: str | None = None
    email_tecnico: str | None = None
    homepage: str | None = None
    cnpj: str | None = None
    inscricao_estadual: str | None = None
    inscricao_municipal: str | None = None
    tipo_faturamento: int | None = None
    historico_nf: str | None = None
    aviso_tratamento: str | None = None
    aviso_agenda: str | None = None
    observacoes: str | None = None
    inativo: bool = False


class PlanoPayload(BaseModel):
    convenio_row_id: int
    codigo: str | None = None
    nome: str
    cobertura: str | None = None
    inativo: bool = False


class CalendarioFaturamentoPayload(BaseModel):
    convenio_row_id: int
    data_fechamento: str | None = None
    data_pagamento: str | None = None


def _proximo_source_id(db: Session, model: type[ConvenioOdonto] | type[PlanoOdonto], clinica_id: int) -> int:
    rows = db.query(model).filter(model.clinica_id == clinica_id).all()
    atual = 0
    for item in rows:
        try:
            atual = max(atual, int(item.source_id or 0))
        except (TypeError, ValueError):
            continue
    return atual + 1


def _convenio_to_dict(item: ConvenioOdonto) -> dict[str, Any]:
    return {
        "id": int(item.source_id),
        "row_id": int(item.id),
        "codigo": (item.codigo or "").strip(),
        "codigo_ans": (item.codigo_ans or "").strip(),
        "nome": (item.nome or "").strip(),
        "telefone": (item.telefone or "").strip(),
        "telefone2": (item.telefone2 or "").strip(),
        "razao_social": (item.razao_social or "").strip(),
        "tipo_logradouro": item.tipo_logradouro,
        "endereco": (item.endereco or "").strip(),
        "numero": (item.numero or "").strip(),
        "complemento": (item.complemento or "").strip(),
        "bairro": (item.bairro or "").strip(),
        "cidade": (item.cidade or "").strip(),
        "cep": (item.cep or "").strip(),
        "uf": (item.uf or "").strip(),
        "tipo_fone1": item.tipo_fone1,
        "contato1": (item.contato1 or "").strip(),
        "tipo_fone2": item.tipo_fone2,
        "contato2": (item.contato2 or "").strip(),
        "tipo_fone3": item.tipo_fone3,
        "telefone3": (item.telefone3 or "").strip(),
        "contato3": (item.contato3 or "").strip(),
        "tipo_fone4": item.tipo_fone4,
        "telefone4": (item.telefone4 or "").strip(),
        "contato4": (item.contato4 or "").strip(),
        "email": (item.email or "").strip(),
        "email_tecnico": (item.email_tecnico or "").strip(),
        "homepage": (item.homepage or "").strip(),
        "cnpj": (item.cnpj or "").strip(),
        "inscricao_estadual": (item.inscricao_estadual or "").strip(),
        "inscricao_municipal": (item.inscricao_municipal or "").strip(),
        "tipo_faturamento": item.tipo_faturamento,
        "historico_nf": (item.historico_nf or "").strip(),
        "aviso_tratamento": (item.aviso_tratamento or "").strip(),
        "aviso_agenda": (item.aviso_agenda or "").strip(),
        "observacoes": (item.observacoes or "").strip(),
        "inativo": bool(item.inativo),
        "data_inclusao": (item.data_inclusao or "").strip(),
        "data_alteracao": (item.data_alteracao or "").strip(),
    }


def _plano_to_dict(item: PlanoOdonto) -> dict[str, Any]:
    return {
        "id": int(item.source_id),
        "row_id": int(item.id),
        "codigo": (item.codigo or "").strip(),
        "nome": (item.nome or "").strip(),
        "cobertura": (item.cobertura or "").strip(),
        "convenio_id": int(item.convenio_source_id or 0) or None,
        "convenio_row_id": int(item.convenio_id or 0) or None,
        "inativo": bool(item.inativo),
        "data_inclusao": (item.data_inclusao or "").strip(),
        "data_alteracao": (item.data_alteracao or "").strip(),
    }


def _apply_convenio_payload(item: ConvenioOdonto, payload: ConvenioPayload) -> None:
    nome = _clean_text(payload.nome, 120)
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome do convênio.")
    item.codigo = _clean_text(payload.codigo, 20)
    item.codigo_ans = _clean_text(payload.codigo_ans, 20)
    item.nome = nome
    item.razao_social = _clean_text(payload.razao_social, 160)
    item.tipo_logradouro = _clean_int(payload.tipo_logradouro)
    item.endereco = _clean_text(payload.endereco, 180)
    item.numero = _clean_text(payload.numero, 20)
    item.complemento = _clean_text(payload.complemento, 120)
    item.bairro = _clean_text(payload.bairro, 120)
    item.cidade = _clean_text(payload.cidade, 120)
    item.cep = _clean_text(payload.cep, 20)
    item.uf = _clean_text(payload.uf, 10)
    item.tipo_fone1 = _clean_int(payload.tipo_fone1)
    item.telefone = _clean_text(payload.telefone, 40)
    item.contato1 = _clean_text(payload.contato1, 120)
    item.tipo_fone2 = _clean_int(payload.tipo_fone2)
    item.telefone2 = _clean_text(payload.telefone2, 40)
    item.contato2 = _clean_text(payload.contato2, 120)
    item.tipo_fone3 = _clean_int(payload.tipo_fone3)
    item.telefone3 = _clean_text(payload.telefone3, 40)
    item.contato3 = _clean_text(payload.contato3, 120)
    item.tipo_fone4 = _clean_int(payload.tipo_fone4)
    item.telefone4 = _clean_text(payload.telefone4, 40)
    item.contato4 = _clean_text(payload.contato4, 120)
    item.email = _clean_text(payload.email, 180)
    item.email_tecnico = _clean_text(payload.email_tecnico, 180)
    item.homepage = _clean_text(payload.homepage, 180)
    item.cnpj = _clean_text(payload.cnpj, 30)
    item.inscricao_estadual = _clean_text(payload.inscricao_estadual, 40)
    item.inscricao_municipal = _clean_text(payload.inscricao_municipal, 40)
    item.tipo_faturamento = _clean_int(payload.tipo_faturamento)
    item.historico_nf = _clean_text(payload.historico_nf)
    item.aviso_tratamento = _clean_text(payload.aviso_tratamento)
    item.aviso_agenda = _clean_text(payload.aviso_agenda)
    item.observacoes = _clean_text(payload.observacoes)
    item.inativo = bool(payload.inativo)


def _apply_plano_payload(item: PlanoOdonto, payload: PlanoPayload, convenio: ConvenioOdonto) -> None:
    nome = _clean_text(payload.nome, 120)
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome do plano.")
    item.codigo = _clean_text(payload.codigo, 20)
    item.nome = nome
    item.cobertura = _clean_text(payload.cobertura)
    item.inativo = bool(payload.inativo)
    item.convenio_id = int(convenio.id)
    item.convenio_source_id = int(convenio.source_id)


def _clean_br_date(value: Any) -> str | None:
    txt = str(value or "").strip()
    if not txt:
        return None
    parts = txt.split("/")
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail="Informe a data no formato dd/mm/aaaa.")
    dia, mes, ano = parts
    if not (dia.isdigit() and mes.isdigit() and ano.isdigit()):
        raise HTTPException(status_code=400, detail="Informe a data no formato dd/mm/aaaa.")
    if len(ano) != 4:
        raise HTTPException(status_code=400, detail="Informe a data no formato dd/mm/aaaa.")
    d = int(dia)
    m = int(mes)
    y = int(ano)
    if d < 1 or d > 31 or m < 1 or m > 12 or y < 1900 or y > 2100:
        raise HTTPException(status_code=400, detail="Informe uma data válida no formato dd/mm/aaaa.")
    return f"{d:02d}/{m:02d}/{y:04d}"


def _calendario_to_dict(item: CalendarioFaturamentoOdonto) -> dict[str, Any]:
    return {
        "id": int(item.source_id),
        "row_id": int(item.id),
        "convenio_id": int(item.convenio_source_id or 0) or None,
        "convenio_row_id": int(item.convenio_id or 0) or None,
        "convenio_nome": (item.convenio.nome if item.convenio else "") or "",
        "data_fechamento": (item.data_fechamento or "").strip(),
        "data_pagamento": (item.data_pagamento or "").strip(),
    }


def _apply_calendario_payload(
    item: CalendarioFaturamentoOdonto,
    payload: CalendarioFaturamentoPayload,
    convenio: ConvenioOdonto,
) -> None:
    item.convenio_id = int(convenio.id)
    item.convenio_source_id = int(convenio.source_id)
    item.data_fechamento = _clean_br_date(payload.data_fechamento)
    item.data_pagamento = _clean_br_date(payload.data_pagamento)


@router.get("/combos")
def carregar_combos_convenios_planos(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)

    convenios = (
        db.query(ConvenioOdonto)
        .filter(ConvenioOdonto.clinica_id == clinica_id)
        .all()
    )
    convenios.sort(key=lambda item: (bool(item.inativo), _norm_sort(item.nome), str(item.codigo or ""), int(item.id or 0)))
    planos = (
        db.query(PlanoOdonto)
        .filter(PlanoOdonto.clinica_id == clinica_id)
        .order_by(PlanoOdonto.inativo.asc(), PlanoOdonto.nome.asc(), PlanoOdonto.id.asc())
        .all()
    )
    tabelas = (
        db.query(ProcedimentoTabela)
        .filter(ProcedimentoTabela.clinica_id == clinica_id)
        .order_by(ProcedimentoTabela.nome.asc(), ProcedimentoTabela.codigo.asc(), ProcedimentoTabela.id.asc())
        .all()
    )

    return {
        "convenios": [_convenio_to_dict(item) for item in convenios],
        "planos": [_plano_to_dict(item) for item in planos],
        "tabelas": [
            {
                "id": int(item.codigo or 0),
                "row_id": int(item.id),
                "nome": (item.nome or "").strip() or f"Tabela {int(item.codigo or 0)}",
                "fonte_pagadora": (item.fonte_pagadora or "").strip(),
                "inativo": bool(item.inativo),
            }
            for item in tabelas
            if int(item.codigo or 0) > 0
        ],
    }


@router.post("/convenios")
def criar_convenio(
    payload: ConvenioPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)
    item = ConvenioOdonto(clinica_id=clinica_id, source_id=_proximo_source_id(db, ConvenioOdonto, clinica_id))
    _apply_convenio_payload(item, payload)
    db.add(item)
    db.flush()
    item.data_inclusao = item.data_inclusao or (item.criado_em.strftime("%d/%m/%Y") if item.criado_em else "")
    item.data_alteracao = item.data_alteracao or (item.atualizado_em.strftime("%d/%m/%Y") if item.atualizado_em else "")
    db.commit()
    db.refresh(item)
    return _convenio_to_dict(item)


@router.put("/convenios/{row_id}")
def alterar_convenio(
    row_id: int,
    payload: ConvenioPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(ConvenioOdonto)
        .filter(ConvenioOdonto.id == row_id, ConvenioOdonto.clinica_id == current_user.clinica_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Convênio não encontrado.")
    _apply_convenio_payload(item, payload)
    item.data_alteracao = item.atualizado_em.strftime("%d/%m/%Y") if item.atualizado_em else item.data_alteracao
    db.commit()
    db.refresh(item)
    return _convenio_to_dict(item)


@router.delete("/convenios/{row_id}")
def excluir_convenio(
    row_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(ConvenioOdonto)
        .filter(ConvenioOdonto.id == row_id, ConvenioOdonto.clinica_id == current_user.clinica_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Convênio não encontrado.")
    if db.query(PlanoOdonto).filter(PlanoOdonto.clinica_id == current_user.clinica_id, PlanoOdonto.convenio_id == item.id).count():
        raise HTTPException(status_code=400, detail="Exclua os planos vinculados antes de eliminar o convênio.")
    if db.query(Paciente).filter(Paciente.clinica_id == current_user.clinica_id, Paciente.id_convenio == int(item.source_id)).count():
        raise HTTPException(status_code=400, detail="Este convênio está vinculado a pacientes.")
    if db.query(Tratamento).filter(Tratamento.clinica_id == current_user.clinica_id, Tratamento.id_convenio == int(item.source_id)).count():
        raise HTTPException(status_code=400, detail="Este convênio está vinculado a tratamentos.")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.post("/planos")
def criar_plano(
    payload: PlanoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)
    convenio = (
        db.query(ConvenioOdonto)
        .filter(ConvenioOdonto.id == int(payload.convenio_row_id), ConvenioOdonto.clinica_id == clinica_id)
        .first()
    )
    if not convenio:
        raise HTTPException(status_code=404, detail="Convênio do plano não encontrado.")
    item = PlanoOdonto(clinica_id=clinica_id, source_id=_proximo_source_id(db, PlanoOdonto, clinica_id))
    _apply_plano_payload(item, payload, convenio)
    db.add(item)
    db.flush()
    item.data_inclusao = item.data_inclusao or (item.criado_em.strftime("%d/%m/%Y") if item.criado_em else "")
    item.data_alteracao = item.data_alteracao or (item.atualizado_em.strftime("%d/%m/%Y") if item.atualizado_em else "")
    db.commit()
    db.refresh(item)
    return _plano_to_dict(item)


@router.put("/planos/{row_id}")
def alterar_plano(
    row_id: int,
    payload: PlanoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(PlanoOdonto)
        .filter(PlanoOdonto.id == row_id, PlanoOdonto.clinica_id == current_user.clinica_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")
    convenio = (
        db.query(ConvenioOdonto)
        .filter(ConvenioOdonto.id == int(payload.convenio_row_id), ConvenioOdonto.clinica_id == current_user.clinica_id)
        .first()
    )
    if not convenio:
        raise HTTPException(status_code=404, detail="Convênio do plano não encontrado.")
    _apply_plano_payload(item, payload, convenio)
    item.data_alteracao = item.atualizado_em.strftime("%d/%m/%Y") if item.atualizado_em else item.data_alteracao
    db.commit()
    db.refresh(item)
    return _plano_to_dict(item)


@router.delete("/planos/{row_id}")
def excluir_plano(
    row_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(PlanoOdonto)
        .filter(PlanoOdonto.id == row_id, PlanoOdonto.clinica_id == current_user.clinica_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")
    if db.query(Paciente).filter(Paciente.clinica_id == current_user.clinica_id, Paciente.id_plano == int(item.source_id)).count():
        raise HTTPException(status_code=400, detail="Este plano está vinculado a pacientes.")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/calendario-faturamento")
def listar_calendario_faturamento(
    convenio_row_id: int | None = None,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(CalendarioFaturamentoOdonto)
        .filter(CalendarioFaturamentoOdonto.clinica_id == current_user.clinica_id)
        .order_by(
            CalendarioFaturamentoOdonto.convenio_id.asc(),
            CalendarioFaturamentoOdonto.data_fechamento.asc(),
            CalendarioFaturamentoOdonto.id.asc(),
        )
    )
    if convenio_row_id:
        query = query.filter(CalendarioFaturamentoOdonto.convenio_id == int(convenio_row_id))
    rows = query.all()
    return {"itens": [_calendario_to_dict(item) for item in rows]}


@router.post("/calendario-faturamento")
def criar_calendario_faturamento(
    payload: CalendarioFaturamentoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)
    convenio = (
        db.query(ConvenioOdonto)
        .filter(ConvenioOdonto.id == int(payload.convenio_row_id), ConvenioOdonto.clinica_id == clinica_id)
        .first()
    )
    if not convenio:
        raise HTTPException(status_code=404, detail="Convênio não encontrado.")
    item = CalendarioFaturamentoOdonto(
        clinica_id=clinica_id,
        source_id=_proximo_source_id(db, CalendarioFaturamentoOdonto, clinica_id),
    )
    _apply_calendario_payload(item, payload, convenio)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _calendario_to_dict(item)


@router.put("/calendario-faturamento/{row_id}")
def alterar_calendario_faturamento(
    row_id: int,
    payload: CalendarioFaturamentoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(CalendarioFaturamentoOdonto)
        .filter(CalendarioFaturamentoOdonto.id == row_id, CalendarioFaturamentoOdonto.clinica_id == current_user.clinica_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Data de faturamento não encontrada.")
    convenio = (
        db.query(ConvenioOdonto)
        .filter(ConvenioOdonto.id == int(payload.convenio_row_id), ConvenioOdonto.clinica_id == current_user.clinica_id)
        .first()
    )
    if not convenio:
        raise HTTPException(status_code=404, detail="Convênio não encontrado.")
    _apply_calendario_payload(item, payload, convenio)
    db.commit()
    db.refresh(item)
    return _calendario_to_dict(item)


@router.delete("/calendario-faturamento/{row_id}")
def excluir_calendario_faturamento(
    row_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(CalendarioFaturamentoOdonto)
        .filter(CalendarioFaturamentoOdonto.id == row_id, CalendarioFaturamentoOdonto.clinica_id == current_user.clinica_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Data de faturamento não encontrada.")
    db.delete(item)
    db.commit()
    return {"ok": True}
