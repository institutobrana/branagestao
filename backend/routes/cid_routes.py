from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import get_db
from models.doenca_cid import DoencaCid
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access

router = APIRouter(
    prefix="/cid",
    tags=["cid"],
    dependencies=[Depends(require_module_access("anamnese"))],
)


class CidPayload(BaseModel):
    codigo: str
    descricao: str
    observacoes: str | None = None
    preferido: bool = False


def _clean_text(value: str | None) -> str:
    text = (value or "").replace("\x00", "").strip()
    while text and ord(text[0]) < 32:
        text = text[1:]
    return " ".join(text.split())


def _to_dict(item: DoencaCid) -> dict:
    return {
        "id": int(item.id),
        "legacy_registro": int(item.legacy_registro or 0),
        "codigo": str(item.codigo or "").strip(),
        "descricao": str(item.descricao or "").strip(),
        "observacoes": str(item.observacoes or "").strip(),
        "preferido": bool(item.preferido),
    }


def _load_or_404(db: Session, clinica_id: int, item_id: int) -> DoencaCid:
    item = (
        db.query(DoencaCid)
        .filter(
            DoencaCid.id == item_id,
            DoencaCid.clinica_id == clinica_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Doenca CID nao encontrada.")
    return item


@router.get("")
def listar_cid(
    q: str = Query(default=""),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(DoencaCid).filter(DoencaCid.clinica_id == current_user.clinica_id)
    termo = _clean_text(q)
    if termo:
        like = f"%{termo}%"
        query = query.filter(or_(DoencaCid.codigo.ilike(like), DoencaCid.descricao.ilike(like)))
    itens = query.order_by(DoencaCid.codigo.asc(), DoencaCid.id.asc()).all()
    return [_to_dict(item) for item in itens]


@router.post("")
def criar_cid(
    payload: CidPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    codigo = _clean_text(payload.codigo)
    descricao = _clean_text(payload.descricao)
    if not codigo or not descricao:
        raise HTTPException(status_code=400, detail="Informe codigo e descricao.")
    item = DoencaCid(
        clinica_id=current_user.clinica_id,
        codigo=codigo,
        descricao=descricao,
        observacoes=_clean_text(payload.observacoes or ""),
        preferido=bool(payload.preferido),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_dict(item)


@router.put("/{cid_id}")
def atualizar_cid(
    cid_id: int,
    payload: CidPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _load_or_404(db, current_user.clinica_id, cid_id)
    codigo = _clean_text(payload.codigo)
    descricao = _clean_text(payload.descricao)
    if not codigo or not descricao:
        raise HTTPException(status_code=400, detail="Informe codigo e descricao.")
    item.codigo = codigo
    item.descricao = descricao
    item.observacoes = _clean_text(payload.observacoes or "")
    item.preferido = bool(payload.preferido)
    db.commit()
    db.refresh(item)
    return _to_dict(item)


@router.delete("/{cid_id}")
def excluir_cid(
    cid_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _load_or_404(db, current_user.clinica_id, cid_id)
    db.delete(item)
    db.commit()
    return {"detail": "CID excluido."}
