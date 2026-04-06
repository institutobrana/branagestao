from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.etiqueta_modelo import EtiquetaModelo
from models.etiqueta_padrao import EtiquetaPadrao
from models.modelo_documento import ModeloDocumento
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access


router = APIRouter(
    prefix="/config/etiquetas",
    tags=["etiquetas"],
    dependencies=[Depends(require_module_access("relatorios"))],
)


class EtiquetaModeloPayload(BaseModel):
    nome: str
    padrao_id: int | None = None
    modelo_documento_id: int | None = None
    margem_esq: float | None = None
    margem_sup: float | None = None
    esp_horizontal: float | None = None
    esp_vertical: float | None = None
    nro_colunas: int | None = None
    nro_linhas: int | None = None


def _clean_text(value: Any, max_len: int | None = None) -> str:
    text = str(value or "").strip()
    if max_len is not None:
        return text[:max_len]
    return text


def _to_float(value: Any, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return default


def _to_int(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except Exception:
        return default


def _serialize_padrao(item: EtiquetaPadrao) -> dict[str, Any]:
    return {
        "id": int(item.id),
        "nome": item.nome or "",
        "reservado": bool(item.reservado),
        "margem_esq": float(item.margem_esq or 0),
        "margem_sup": float(item.margem_sup or 0),
        "esp_horizontal": float(item.esp_horizontal or 0),
        "esp_vertical": float(item.esp_vertical or 0),
        "nro_colunas": int(item.nro_colunas or 0),
        "nro_linhas": int(item.nro_linhas or 0),
    }


def _serialize_modelo(item: EtiquetaModelo) -> dict[str, Any]:
    padrao = item.padrao
    arquivo = item.modelo_documento
    return {
        "id": int(item.id),
        "nome": item.nome or "",
        "padrao_id": int(padrao.id) if padrao else None,
        "padrao_nome": padrao.nome if padrao else "Definido pelo usuário",
        "margem_esq": float(item.margem_esq or 0),
        "margem_sup": float(item.margem_sup or 0),
        "esp_horizontal": float(item.esp_horizontal or 0),
        "esp_vertical": float(item.esp_vertical or 0),
        "nro_colunas": int(item.nro_colunas or 0),
        "nro_linhas": int(item.nro_linhas or 0),
        "modelo_documento_id": int(arquivo.id) if arquivo else None,
        "nome_arquivo": arquivo.nome_arquivo if arquivo else "",
        "reservado": bool(item.reservado),
        "ativo": bool(item.ativo),
    }


def _load_modelo_documento(
    db: Session, clinica_id: int, modelo_documento_id: int | None
) -> ModeloDocumento | None:
    if modelo_documento_id is None:
        return None
    return (
        db.query(ModeloDocumento)
        .filter(
            ModeloDocumento.id == modelo_documento_id,
            ModeloDocumento.tipo_modelo == "etiquetas",
            ModeloDocumento.ativo.is_(True),
            (
                (ModeloDocumento.clinica_id == clinica_id)
                | (ModeloDocumento.clinica_id.is_(None))
            ),
        )
        .first()
    )


@router.get("/padroes")
def listar_padroes(db: Session = Depends(get_db)) -> dict[str, Any]:
    padroes = db.query(EtiquetaPadrao).order_by(EtiquetaPadrao.id.asc()).all()
    return {"padroes": [_serialize_padrao(p) for p in padroes]}


@router.get("/arquivos")
def listar_arquivos(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> dict[str, Any]:
    clinica_id = int(current_user.clinica_id or 0)
    itens = (
        db.query(ModeloDocumento)
        .filter(
            ModeloDocumento.tipo_modelo == "etiquetas",
            ModeloDocumento.ativo.is_(True),
            (
                (ModeloDocumento.clinica_id == clinica_id)
                | (ModeloDocumento.clinica_id.is_(None))
            ),
        )
        .order_by(
            ModeloDocumento.clinica_id.is_(None).asc(),
            ModeloDocumento.nome_exibicao.asc(),
            ModeloDocumento.id.asc(),
        )
        .all()
    )
    return {
        "arquivos": [
            {
                "id": int(item.id),
                "nome": item.nome_exibicao or item.nome_arquivo,
                "nome_arquivo": item.nome_arquivo,
                "clinica_id": int(item.clinica_id) if item.clinica_id is not None else None,
                "origem": item.origem or "",
            }
            for item in itens
        ]
    }


@router.get("/modelos")
def listar_modelos(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> dict[str, Any]:
    clinica_id = int(current_user.clinica_id or 0)
    itens = (
        db.query(EtiquetaModelo)
        .filter(EtiquetaModelo.clinica_id == clinica_id)
        .order_by(EtiquetaModelo.nome.asc(), EtiquetaModelo.id.asc())
        .all()
    )
    return {"modelos": [_serialize_modelo(item) for item in itens]}


@router.post("/modelos")
def criar_modelo(
    payload: EtiquetaModeloPayload,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> dict[str, Any]:
    nome = _clean_text(payload.nome, 80)
    if not nome:
        raise HTTPException(status_code=400, detail="Nome do modelo é obrigatório.")
    clinica_id = int(current_user.clinica_id or 0)
    modelo_doc = _load_modelo_documento(db, clinica_id, payload.modelo_documento_id)
    if modelo_doc is None:
        raise HTTPException(status_code=400, detail="Arquivo de modelo inválido.")
    padrao = None
    if payload.padrao_id:
        padrao = db.query(EtiquetaPadrao).filter(EtiquetaPadrao.id == payload.padrao_id).first()
        if not padrao:
            raise HTTPException(status_code=400, detail="Padrão de etiqueta inválido.")
    item = EtiquetaModelo(
        clinica_id=clinica_id,
        padrao_id=padrao.id if padrao else None,
        nome=nome,
        reservado=False,
        margem_esq=_to_float(payload.margem_esq, padrao.margem_esq if padrao else None),
        margem_sup=_to_float(payload.margem_sup, padrao.margem_sup if padrao else None),
        esp_horizontal=_to_float(payload.esp_horizontal, padrao.esp_horizontal if padrao else None),
        esp_vertical=_to_float(payload.esp_vertical, padrao.esp_vertical if padrao else None),
        nro_colunas=_to_int(payload.nro_colunas, padrao.nro_colunas if padrao else None),
        nro_linhas=_to_int(payload.nro_linhas, padrao.nro_linhas if padrao else None),
        modelo_documento_id=modelo_doc.id,
        ativo=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"detail": "Modelo criado com sucesso.", "modelo": _serialize_modelo(item)}


@router.put("/modelos/{modelo_id}")
def atualizar_modelo(
    modelo_id: int,
    payload: EtiquetaModeloPayload,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> dict[str, Any]:
    clinica_id = int(current_user.clinica_id or 0)
    item = (
        db.query(EtiquetaModelo)
        .filter(EtiquetaModelo.id == modelo_id, EtiquetaModelo.clinica_id == clinica_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Modelo não encontrado.")
    nome = _clean_text(payload.nome, 80)
    if nome:
        item.nome = nome
    modelo_doc = _load_modelo_documento(db, clinica_id, payload.modelo_documento_id)
    if modelo_doc is None:
        raise HTTPException(status_code=400, detail="Arquivo de modelo inválido.")
    item.modelo_documento_id = modelo_doc.id
    padrao = None
    if payload.padrao_id:
        padrao = db.query(EtiquetaPadrao).filter(EtiquetaPadrao.id == payload.padrao_id).first()
        if not padrao:
            raise HTTPException(status_code=400, detail="Padrão de etiqueta inválido.")
    item.padrao_id = padrao.id if padrao else None
    item.margem_esq = _to_float(payload.margem_esq, item.margem_esq)
    item.margem_sup = _to_float(payload.margem_sup, item.margem_sup)
    item.esp_horizontal = _to_float(payload.esp_horizontal, item.esp_horizontal)
    item.esp_vertical = _to_float(payload.esp_vertical, item.esp_vertical)
    item.nro_colunas = _to_int(payload.nro_colunas, item.nro_colunas)
    item.nro_linhas = _to_int(payload.nro_linhas, item.nro_linhas)
    if padrao:
        item.margem_esq = _to_float(payload.margem_esq, padrao.margem_esq)
        item.margem_sup = _to_float(payload.margem_sup, padrao.margem_sup)
        item.esp_horizontal = _to_float(payload.esp_horizontal, padrao.esp_horizontal)
        item.esp_vertical = _to_float(payload.esp_vertical, padrao.esp_vertical)
        item.nro_colunas = _to_int(payload.nro_colunas, padrao.nro_colunas)
        item.nro_linhas = _to_int(payload.nro_linhas, padrao.nro_linhas)
    db.commit()
    db.refresh(item)
    return {"detail": "Modelo atualizado com sucesso.", "modelo": _serialize_modelo(item)}


@router.delete("/modelos/{modelo_id}")
def excluir_modelo(
    modelo_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> dict[str, Any]:
    clinica_id = int(current_user.clinica_id or 0)
    item = (
        db.query(EtiquetaModelo)
        .filter(EtiquetaModelo.id == modelo_id, EtiquetaModelo.clinica_id == clinica_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Modelo não encontrado.")
    if item.reservado:
        raise HTTPException(status_code=400, detail="Modelo reservado do sistema.")
    db.delete(item)
    db.commit()
    return {"detail": "Modelo eliminado com sucesso."}
