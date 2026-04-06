import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.material import ListaMaterial, Material
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access
from services.indices_service import (
    DEFAULT_INDICE_NUMERO,
    dados_indice_por_numero,
    listar_indices,
    resolver_numero_indice,
)

router = APIRouter(
    prefix="/materiais",
    tags=["materiais"],
    dependencies=[Depends(require_module_access("materiais"))],
)



class ListaPayload(BaseModel):
    nome: str
    nro_indice: int | str | None = None


class MaterialPayload(BaseModel):
    codigo: str
    nome: str
    preco: float = 0
    relacao: float = 0
    custo: float = 0
    unidade_compra: str = ""
    unidade_consumo: str = ""
    validade_dias: int = 0
    preferido: bool = False
    classificacao: str = ""
    lista_id: int


def _chave_ordenacao(texto: str) -> str:
    base = (texto or "").strip().lower()
    base = unicodedata.normalize("NFD", base)
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def _lista_to_dict(db: Session, clinica_id: int, lista: ListaMaterial) -> dict:
    indice = dados_indice_por_numero(db, clinica_id, lista.nro_indice)
    return {
        "id": lista.id,
        "nome": lista.nome,
        "nro_indice": int(indice["id"]),
        "indice": int(indice["id"]),
        "indice_id": int(indice["id"]),
        "indice_sigla": str(indice["sigla"]),
        "indice_nome": str(indice["nome"]),
    }


def _material_to_dict(mat: Material) -> dict:
    return {
        "id": mat.id,
        "codigo": mat.codigo,
        "nome": mat.nome,
        "preco": float(mat.preco or 0),
        "relacao": float(mat.relacao or 0),
        "custo": float(mat.custo or 0),
        "unidade_compra": (mat.unidade_compra or ""),
        "unidade_consumo": (mat.unidade_consumo or ""),
        "validade_dias": int(mat.validade_dias or 0),
        "preferido": bool(mat.preferido),
        "classificacao": (mat.classificacao or ""),
        "lista_id": mat.lista_id,
    }


def _load_lista_or_404(db: Session, clinica_id: int, lista_id: int) -> ListaMaterial:
    lista = (
        db.query(ListaMaterial)
        .filter(
            ListaMaterial.id == lista_id,
            ListaMaterial.clinica_id == clinica_id,
        )
        .first()
    )
    if not lista:
        raise HTTPException(status_code=404, detail="Tabela de materiais nao encontrada.")
    return lista


def _codigo_em_uso(
    db: Session,
    lista_id: int,
    codigo: str,
    ignore_material_id: int | None = None,
) -> bool:
    query = db.query(Material).filter(Material.lista_id == lista_id, Material.codigo == codigo)
    if ignore_material_id:
        query = query.filter(Material.id != ignore_material_id)
    return db.query(query.exists()).scalar()


def _resolver_nro_indice(db: Session, clinica_id: int, valor: int | str | None, default: int = DEFAULT_INDICE_NUMERO) -> int:
    return resolver_numero_indice(db, clinica_id, valor, default=default)


def _listar_indices_moeda(db: Session, clinica_id: int) -> list[dict]:
    return listar_indices(db, clinica_id, include_inativos=True)


@router.get("/indices")
def listar_indices_endpoint(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _listar_indices_moeda(db, current_user.clinica_id)


@router.get("/listas")
def listar_tabelas(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listas = (
        db.query(ListaMaterial)
        .filter(ListaMaterial.clinica_id == current_user.clinica_id)
        .order_by(ListaMaterial.nome.asc())
        .all()
    )
    return [_lista_to_dict(db, current_user.clinica_id, x) for x in listas]


@router.post("/listas")
def criar_tabela(
    payload: ListaPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nome = (payload.nome or "").strip()
    nro_indice = _resolver_nro_indice(db, current_user.clinica_id, payload.nro_indice)
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome da tabela.")

    existe = (
        db.query(ListaMaterial.id)
        .filter(
            ListaMaterial.clinica_id == current_user.clinica_id,
            ListaMaterial.nome == nome,
        )
        .first()
    )
    if existe:
        raise HTTPException(status_code=400, detail="Ja existe uma tabela com esse nome.")

    lista = ListaMaterial(nome=nome, clinica_id=current_user.clinica_id, nro_indice=nro_indice)
    db.add(lista)
    db.commit()
    db.refresh(lista)
    return _lista_to_dict(db, current_user.clinica_id, lista)


@router.patch("/listas/{lista_id}")
def renomear_tabela(
    lista_id: int,
    payload: ListaPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lista = _load_lista_or_404(db, current_user.clinica_id, lista_id)
    nome = (payload.nome or "").strip()
    nro_indice = _resolver_nro_indice(
        db,
        current_user.clinica_id,
        payload.nro_indice,
        default=int(lista.nro_indice or DEFAULT_INDICE_NUMERO),
    )
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o novo nome da tabela.")

    existe = (
        db.query(ListaMaterial.id)
        .filter(
            ListaMaterial.clinica_id == current_user.clinica_id,
            ListaMaterial.nome == nome,
            ListaMaterial.id != lista.id,
        )
        .first()
    )
    if existe:
        raise HTTPException(status_code=400, detail="Ja existe uma tabela com esse nome.")

    lista.nome = nome
    lista.nro_indice = nro_indice
    db.commit()
    db.refresh(lista)
    return _lista_to_dict(db, current_user.clinica_id, lista)


@router.delete("/listas/{lista_id}")
def excluir_tabela(
    lista_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lista = _load_lista_or_404(db, current_user.clinica_id, lista_id)
    db.delete(lista)
    db.commit()
    return {"detail": "Tabela excluida com sucesso."}


@router.get("/listas/{lista_id}/proximo-codigo")
def sugerir_codigo(
    lista_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _load_lista_or_404(db, current_user.clinica_id, lista_id)
    codigos = db.query(Material.codigo).filter(Material.lista_id == lista_id).all()
    usados = set()
    for (codigo,) in codigos:
        try:
            usados.add(int(str(codigo)))
        except ValueError:
            continue

    proximo = 1
    while proximo in usados:
        proximo += 1

    return {"codigo": str(proximo).zfill(5)}


@router.get("")
def listar_materiais(
    lista_id: int = Query(...),
    q: str = Query(default=""),
    classificacao: str = Query(default="__todos__"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _load_lista_or_404(db, current_user.clinica_id, lista_id)
    query = db.query(Material).filter(Material.lista_id == lista_id)
    filtro_classificacao = (classificacao or "").strip()
    if filtro_classificacao == "__mais_usados__":
        query = query.filter(Material.preferido.is_(True))
    elif filtro_classificacao and filtro_classificacao != "__todos__":
        query = query.filter(Material.classificacao == filtro_classificacao)
    termo = (q or "").strip()
    if termo:
        like = f"%{termo}%"
        query = query.filter((Material.nome.ilike(like)) | (Material.codigo.ilike(like)))

    materiais = query.all()
    materiais.sort(key=lambda m: _chave_ordenacao(m.nome))
    return [_material_to_dict(x) for x in materiais]


@router.post("")
def criar_material(
    payload: MaterialPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _load_lista_or_404(db, current_user.clinica_id, payload.lista_id)

    codigo = (payload.codigo or "").strip()
    nome = (payload.nome or "").strip()
    if not codigo or not nome:
        raise HTTPException(status_code=400, detail="Codigo e nome sao obrigatorios.")

    if _codigo_em_uso(db, payload.lista_id, codigo):
        raise HTTPException(status_code=400, detail="Codigo ja esta em uso.")

    mat = Material(
        codigo=codigo,
        nome=nome,
        preco=float(payload.preco or 0),
        relacao=float(payload.relacao or 0),
        custo=float(payload.custo or 0),
        unidade_compra=(payload.unidade_compra or "").strip(),
        unidade_consumo=(payload.unidade_consumo or "").strip(),
        validade_dias=max(int(payload.validade_dias or 0), 0),
        preferido=bool(payload.preferido),
        classificacao=(payload.classificacao or "").strip(),
        lista_id=payload.lista_id,
    )
    db.add(mat)
    db.commit()
    db.refresh(mat)
    return _material_to_dict(mat)


@router.put("/{material_id}")
def atualizar_material(
    material_id: int,
    payload: MaterialPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _load_lista_or_404(db, current_user.clinica_id, payload.lista_id)
    mat = db.query(Material).filter(Material.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material nao encontrado.")
    _load_lista_or_404(db, current_user.clinica_id, mat.lista_id)

    codigo = (payload.codigo or "").strip()
    nome = (payload.nome or "").strip()
    if not codigo or not nome:
        raise HTTPException(status_code=400, detail="Codigo e nome sao obrigatorios.")

    if _codigo_em_uso(db, payload.lista_id, codigo, ignore_material_id=material_id):
        raise HTTPException(status_code=400, detail="Codigo ja esta em uso.")

    mat.codigo = codigo
    mat.nome = nome
    mat.preco = float(payload.preco or 0)
    mat.relacao = float(payload.relacao or 0)
    mat.custo = float(payload.custo or 0)
    mat.unidade_compra = (payload.unidade_compra or "").strip()
    mat.unidade_consumo = (payload.unidade_consumo or "").strip()
    mat.validade_dias = max(int(payload.validade_dias or 0), 0)
    mat.preferido = bool(payload.preferido)
    mat.classificacao = (payload.classificacao or "").strip()
    mat.lista_id = payload.lista_id
    db.commit()
    db.refresh(mat)
    return _material_to_dict(mat)


@router.delete("/{material_id}")
def excluir_material(
    material_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mat = db.query(Material).filter(Material.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material nao encontrado.")

    _load_lista_or_404(db, current_user.clinica_id, mat.lista_id)
    db.delete(mat)
    db.commit()
    return {"detail": "Material excluido com sucesso."}
