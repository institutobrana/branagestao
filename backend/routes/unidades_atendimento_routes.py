from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.unidade_atendimento import UnidadeAtendimento
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access

router = APIRouter(
    prefix="/cadastros/unidades-atendimento",
    tags=["unidades-atendimento"],
    dependencies=[Depends(require_module_access("configuracao"))],
)


class UnidadePayload(BaseModel):
    codigo: str | None = None
    nome: str
    logradouro_tipo: str | None = None
    endereco: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    cep: str | None = None
    uf: str | None = None
    fone1_tipo: str | None = None
    fone1: str | None = None
    contato1: str | None = None
    fone2_tipo: str | None = None
    fone2: str | None = None
    contato2: str | None = None
    fone3_tipo: str | None = None
    fone3: str | None = None
    contato3: str | None = None
    fone4_tipo: str | None = None
    fone4: str | None = None
    contato4: str | None = None
    qtd_sala: int | None = None
    ativo: bool = True
    inclusao: str | None = None
    alteracao: str | None = None


def _clean_text(value: Any, max_len: int | None = None) -> str | None:
    txt = " ".join(str(value or "").split()).strip()
    if not txt:
        return None
    return txt[:max_len] if max_len is not None else txt


def _clean_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    txt = str(value).strip().lower()
    if txt in {"1", "true", "sim", "s", "yes"}:
        return True
    if txt in {"0", "false", "nao", "n", "no"}:
        return False
    return default


def _clean_br_date(value: Any) -> str | None:
    txt = str(value or "").strip()
    if not txt:
        return None
    parts = txt.split("/")
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail="Data invalida. Use dd/mm/aaaa.")
    dia, mes, ano = parts
    if not (dia.isdigit() and mes.isdigit() and ano.isdigit() and len(ano) == 4):
        raise HTTPException(status_code=400, detail="Data invalida. Use dd/mm/aaaa.")
    d = int(dia)
    m = int(mes)
    y = int(ano)
    if d < 1 or d > 31 or m < 1 or m > 12 or y < 1900 or y > 2100:
        raise HTTPException(status_code=400, detail="Data invalida. Use dd/mm/aaaa.")
    return f"{d:02d}/{m:02d}/{y:04d}"


def _proximo_source_id(db: Session, clinica_id: int) -> int:
    rows = db.query(UnidadeAtendimento.source_id).filter(UnidadeAtendimento.clinica_id == int(clinica_id)).all()
    atual = 0
    for row in rows:
        try:
            atual = max(atual, int(row[0] or 0))
        except Exception:
            continue
    return atual + 1


def _proximo_codigo(db: Session, clinica_id: int) -> str:
    rows = db.query(UnidadeAtendimento.codigo).filter(UnidadeAtendimento.clinica_id == int(clinica_id)).all()
    atual = 0
    for row in rows:
        txt = str(row[0] or "").strip()
        if txt.isdigit():
            atual = max(atual, int(txt))
    return str(atual + 1).zfill(4)


def _to_dict(item: UnidadeAtendimento) -> dict[str, Any]:
    return {
        "id": int(item.id),
        "row_id": int(item.id),
        "source_id": int(item.source_id or 0),
        "codigo": str(item.codigo or "").strip(),
        "nome": str(item.nome or "").strip(),
        "logradouro_tipo": str(item.logradouro_tipo or "").strip(),
        "endereco": str(item.endereco or "").strip(),
        "numero": str(item.numero or "").strip(),
        "complemento": str(item.complemento or "").strip(),
        "bairro": str(item.bairro or "").strip(),
        "cidade": str(item.cidade or "").strip(),
        "cep": str(item.cep or "").strip(),
        "uf": str(item.uf or "").strip(),
        "fone1_tipo": str(item.fone1_tipo or "").strip(),
        "fone1": str(item.fone1 or "").strip(),
        "contato1": str(item.contato1 or "").strip(),
        "fone2_tipo": str(item.fone2_tipo or "").strip(),
        "fone2": str(item.fone2 or "").strip(),
        "contato2": str(item.contato2 or "").strip(),
        "fone3_tipo": str(item.fone3_tipo or "").strip(),
        "fone3": str(item.fone3 or "").strip(),
        "contato3": str(item.contato3 or "").strip(),
        "fone4_tipo": str(item.fone4_tipo or "").strip(),
        "fone4": str(item.fone4 or "").strip(),
        "contato4": str(item.contato4 or "").strip(),
        "qtd_sala": int(item.qtd_sala or 0),
        "ativo": not bool(item.inativo),
        "inclusao": str(item.data_inclusao or "").strip(),
        "alteracao": str(item.data_alteracao or "").strip(),
    }


def _or_404(db: Session, clinica_id: int, row_id: int) -> UnidadeAtendimento:
    item = (
        db.query(UnidadeAtendimento)
        .filter(
            UnidadeAtendimento.id == int(row_id),
            UnidadeAtendimento.clinica_id == int(clinica_id),
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Unidade nao encontrada.")
    return item


def _apply_payload(item: UnidadeAtendimento, payload: UnidadePayload) -> None:
    nome = _clean_text(payload.nome, 180)
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome da unidade.")
    item.codigo = _clean_text(payload.codigo, 20)
    item.nome = nome
    item.logradouro_tipo = _clean_text(payload.logradouro_tipo, 60)
    item.endereco = _clean_text(payload.endereco, 180)
    item.numero = _clean_text(payload.numero, 30)
    item.complemento = _clean_text(payload.complemento, 120)
    item.bairro = _clean_text(payload.bairro, 120)
    item.cidade = _clean_text(payload.cidade, 120)
    item.cep = _clean_text(payload.cep, 20)
    item.uf = _clean_text(payload.uf, 10)

    item.fone1_tipo = _clean_text(payload.fone1_tipo, 40)
    item.fone1 = _clean_text(payload.fone1, 40)
    item.contato1 = _clean_text(payload.contato1, 120)
    item.fone2_tipo = _clean_text(payload.fone2_tipo, 40)
    item.fone2 = _clean_text(payload.fone2, 40)
    item.contato2 = _clean_text(payload.contato2, 120)
    item.fone3_tipo = _clean_text(payload.fone3_tipo, 40)
    item.fone3 = _clean_text(payload.fone3, 40)
    item.contato3 = _clean_text(payload.contato3, 120)
    item.fone4_tipo = _clean_text(payload.fone4_tipo, 40)
    item.fone4 = _clean_text(payload.fone4, 40)
    item.contato4 = _clean_text(payload.contato4, 120)
    try:
        item.qtd_sala = max(0, int(payload.qtd_sala or 0))
    except Exception:
        item.qtd_sala = 0

    item.inativo = not _clean_bool(payload.ativo, True)
    item.data_inclusao = _clean_br_date(payload.inclusao) if str(payload.inclusao or "").strip() else item.data_inclusao
    item.data_alteracao = _clean_br_date(payload.alteracao) if str(payload.alteracao or "").strip() else None


@router.get("")
def listar(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    itens = (
        db.query(UnidadeAtendimento)
        .filter(UnidadeAtendimento.clinica_id == int(current_user.clinica_id))
        .order_by(UnidadeAtendimento.source_id.asc(), UnidadeAtendimento.id.asc())
        .all()
    )
    return {"itens": [_to_dict(item) for item in itens]}


@router.get("/combos")
def listar_combos(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    itens = (
        db.query(UnidadeAtendimento)
        .filter(
            UnidadeAtendimento.clinica_id == int(current_user.clinica_id),
            UnidadeAtendimento.inativo.is_(False),
        )
        .order_by(UnidadeAtendimento.source_id.asc(), UnidadeAtendimento.id.asc())
        .all()
    )
    return [
        {
            "id": int(item.source_id or 0) or int(item.id),
            "row_id": int(item.id),
            "nome": str(item.nome or "").strip(),
            "descricao": str(item.nome or "").strip(),
        }
        for item in itens
        if str(item.nome or "").strip()
    ]


@router.get("/proximo-codigo")
def proximo_codigo(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"codigo": _proximo_codigo(db, current_user.clinica_id)}


@router.post("")
def criar(
    payload: UnidadePayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = UnidadeAtendimento(
        clinica_id=int(current_user.clinica_id),
        source_id=_proximo_source_id(db, current_user.clinica_id),
        codigo=_clean_text(payload.codigo, 20) or _proximo_codigo(db, current_user.clinica_id),
        nome="TEMP",
        data_inclusao=datetime.now().strftime("%d/%m/%Y"),
    )
    _apply_payload(item, payload)
    if not str(item.data_inclusao or "").strip():
        item.data_inclusao = datetime.now().strftime("%d/%m/%Y")
    item.data_alteracao = str(payload.alteracao or "").strip() or item.data_alteracao
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_dict(item)


@router.put("/{row_id}")
def atualizar(
    row_id: int,
    payload: UnidadePayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _or_404(db, current_user.clinica_id, row_id)
    _apply_payload(item, payload)
    if not str(item.data_alteracao or "").strip():
        item.data_alteracao = datetime.now().strftime("%d/%m/%Y")
    db.commit()
    db.refresh(item)
    return _to_dict(item)


@router.delete("/{row_id}")
def excluir(
    row_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _or_404(db, current_user.clinica_id, row_id)
    db.delete(item)
    db.commit()
    return {"detail": "Unidade excluida."}
