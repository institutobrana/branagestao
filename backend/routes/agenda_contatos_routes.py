from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db
from models.contato import Contato
from models.protetico import Protetico
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access

router = APIRouter(
    prefix="/agenda-contatos",
    tags=["agenda-contatos"],
    dependencies=[Depends(require_module_access("agenda"))],
)


class ContatoPayload(BaseModel):
    nome: str
    tipo: str | None = None
    contato: str | None = None
    aniversario_dia: int | None = None
    aniversario_mes: int | None = None
    endereco: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    cep: str | None = None
    uf: str | None = None
    pais: str | None = None
    tel1_tipo: str | None = None
    tel1: str | None = None
    tel2_tipo: str | None = None
    tel2: str | None = None
    tel3_tipo: str | None = None
    tel3: str | None = None
    tel4_tipo: str | None = None
    tel4: str | None = None
    email: str | None = None
    homepage: str | None = None
    palavra_chave_1: str | None = None
    palavra_chave_2: str | None = None
    registro: str | None = None
    especialidade: str | None = None
    incluir_malas_diretas: bool = True
    incluir_preferidos: bool = False
    observacoes: str | None = None
    protetico_id: int | None = None


def _clean_text(value: str | None) -> str:
    text = (value or "").replace("\x00", "").strip()
    while text and ord(text[0]) < 32:
        text = text[1:]
    return " ".join(text.split())


def _fix_int(value: int | None, min_val: int, max_val: int) -> int | None:
    if value is None:
        return None
    try:
        val = int(value)
    except Exception:
        return None
    if val < min_val or val > max_val:
        return None
    return val


def _normalizar_tipo(value: str | None) -> str:
    return _clean_text(value or "").casefold()


def _eh_tipo_protetico(value: str | None) -> bool:
    return "protet" in _normalizar_tipo(value)


def _sincronizar_protetico_contato(
    db: Session,
    clinica_id: int,
    nome: str,
    tipo: str | None,
    protetico_id_atual: int | None = None,
) -> int | None:
    if not _eh_tipo_protetico(tipo):
        return None
    nome_limpo = _clean_text(nome)
    if not nome_limpo:
        return None
    prot = None
    if protetico_id_atual:
        prot = (
            db.query(Protetico)
            .filter(
                Protetico.id == int(protetico_id_atual),
                Protetico.clinica_id == clinica_id,
            )
            .first()
        )
    if prot is None:
        prot = (
            db.query(Protetico)
            .filter(
                Protetico.clinica_id == clinica_id,
                Protetico.nome == nome_limpo,
            )
            .first()
        )
    if prot is None:
        prot = Protetico(nome=nome_limpo, clinica_id=clinica_id)
        db.add(prot)
        db.flush()
        return int(prot.id)
    if protetico_id_atual and prot.nome != nome_limpo:
        existe_mesmo_nome = (
            db.query(Protetico.id)
            .filter(
                Protetico.clinica_id == clinica_id,
                Protetico.nome == nome_limpo,
                Protetico.id != prot.id,
            )
            .first()
        )
        if not existe_mesmo_nome:
            prot.nome = nome_limpo
            db.flush()
    return int(prot.id)


def _to_dict(item: Contato) -> dict:
    return {
        "id": int(item.id),
        "nome": str(item.nome or "").strip(),
        "tipo": str(item.tipo or "").strip(),
        "contato": str(item.contato or "").strip(),
        "aniversario_dia": item.aniversario_dia,
        "aniversario_mes": item.aniversario_mes,
        "endereco": str(item.endereco or "").strip(),
        "complemento": str(item.complemento or "").strip(),
        "bairro": str(item.bairro or "").strip(),
        "cidade": str(item.cidade or "").strip(),
        "cep": str(item.cep or "").strip(),
        "uf": str(item.uf or "").strip(),
        "pais": str(item.pais or "").strip(),
        "tel1_tipo": str(item.tel1_tipo or "").strip(),
        "tel1": str(item.tel1 or "").strip(),
        "tel2_tipo": str(item.tel2_tipo or "").strip(),
        "tel2": str(item.tel2 or "").strip(),
        "tel3_tipo": str(item.tel3_tipo or "").strip(),
        "tel3": str(item.tel3 or "").strip(),
        "tel4_tipo": str(item.tel4_tipo or "").strip(),
        "tel4": str(item.tel4 or "").strip(),
        "email": str(item.email or "").strip(),
        "homepage": str(item.homepage or "").strip(),
        "palavra_chave_1": str(item.palavra_chave_1 or "").strip(),
        "palavra_chave_2": str(item.palavra_chave_2 or "").strip(),
        "registro": str(item.registro or "").strip(),
        "especialidade": str(item.especialidade or "").strip(),
        "incluir_malas_diretas": bool(item.incluir_malas_diretas),
        "incluir_preferidos": bool(item.incluir_preferidos),
        "observacoes": str(item.observacoes or "").strip(),
        "protetico_id": int(item.protetico_id) if item.protetico_id else None,
    }


def _load_or_404(db: Session, clinica_id: int, contato_id: int) -> Contato:
    item = (
        db.query(Contato)
        .filter(
            Contato.id == contato_id,
            Contato.clinica_id == clinica_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Contato nao encontrado.")
    return item


@router.get("")
def listar_contatos(
    q: str = Query(default=""),
    tipo: str = Query(default=""),
    limit: int = Query(default=2000),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Contato).filter(Contato.clinica_id == current_user.clinica_id)
    filtro_tipo = _clean_text(tipo)
    if filtro_tipo:
        query = query.filter(Contato.tipo == filtro_tipo)

    termo = _clean_text(q)
    if termo:
        like = f"%{termo}%"
        query = query.filter(
            or_(
                Contato.nome.ilike(like),
                Contato.contato.ilike(like),
                Contato.email.ilike(like),
                Contato.tel1.ilike(like),
                Contato.tel2.ilike(like),
                Contato.tel3.ilike(like),
                Contato.tel4.ilike(like),
            )
        )

    limite = max(1, min(int(limit or 2000), 5000))
    itens = query.order_by(Contato.nome.asc(), Contato.id.asc()).limit(limite).all()
    return [_to_dict(item) for item in itens]


@router.post("")
def criar_contato(
    payload: ContatoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nome = _clean_text(payload.nome)
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome.")
    protetico_id = _sincronizar_protetico_contato(
        db,
        current_user.clinica_id,
        nome,
        payload.tipo,
        int(payload.protetico_id) if payload.protetico_id else None,
    )
    item = Contato(
        clinica_id=current_user.clinica_id,
        protetico_id=protetico_id,
        nome=nome,
        tipo=_clean_text(payload.tipo or ""),
        contato=_clean_text(payload.contato or ""),
        aniversario_dia=_fix_int(payload.aniversario_dia, 1, 31),
        aniversario_mes=_fix_int(payload.aniversario_mes, 1, 12),
        endereco=_clean_text(payload.endereco or ""),
        complemento=_clean_text(payload.complemento or ""),
        bairro=_clean_text(payload.bairro or ""),
        cidade=_clean_text(payload.cidade or ""),
        cep=_clean_text(payload.cep or ""),
        uf=_clean_text(payload.uf or "").upper(),
        pais=_clean_text(payload.pais or ""),
        tel1_tipo=_clean_text(payload.tel1_tipo or ""),
        tel1=_clean_text(payload.tel1 or ""),
        tel2_tipo=_clean_text(payload.tel2_tipo or ""),
        tel2=_clean_text(payload.tel2 or ""),
        tel3_tipo=_clean_text(payload.tel3_tipo or ""),
        tel3=_clean_text(payload.tel3 or ""),
        tel4_tipo=_clean_text(payload.tel4_tipo or ""),
        tel4=_clean_text(payload.tel4 or ""),
        email=_clean_text(payload.email or ""),
        homepage=_clean_text(payload.homepage or ""),
        palavra_chave_1=_clean_text(payload.palavra_chave_1 or ""),
        palavra_chave_2=_clean_text(payload.palavra_chave_2 or ""),
        registro=_clean_text(payload.registro or ""),
        especialidade=_clean_text(payload.especialidade or ""),
        incluir_malas_diretas=bool(payload.incluir_malas_diretas),
        incluir_preferidos=bool(payload.incluir_preferidos),
        observacoes=_clean_text(payload.observacoes or ""),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_dict(item)


@router.put("/{contato_id}")
def atualizar_contato(
    contato_id: int,
    payload: ContatoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _load_or_404(db, current_user.clinica_id, contato_id)
    nome = _clean_text(payload.nome)
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome.")
    item.protetico_id = _sincronizar_protetico_contato(
        db,
        current_user.clinica_id,
        nome,
        payload.tipo,
        int(payload.protetico_id) if payload.protetico_id else item.protetico_id,
    )
    item.nome = nome
    item.tipo = _clean_text(payload.tipo or "")
    item.contato = _clean_text(payload.contato or "")
    item.aniversario_dia = _fix_int(payload.aniversario_dia, 1, 31)
    item.aniversario_mes = _fix_int(payload.aniversario_mes, 1, 12)
    item.endereco = _clean_text(payload.endereco or "")
    item.complemento = _clean_text(payload.complemento or "")
    item.bairro = _clean_text(payload.bairro or "")
    item.cidade = _clean_text(payload.cidade or "")
    item.cep = _clean_text(payload.cep or "")
    item.uf = _clean_text(payload.uf or "").upper()
    item.pais = _clean_text(payload.pais or "")
    item.tel1_tipo = _clean_text(payload.tel1_tipo or "")
    item.tel1 = _clean_text(payload.tel1 or "")
    item.tel2_tipo = _clean_text(payload.tel2_tipo or "")
    item.tel2 = _clean_text(payload.tel2 or "")
    item.tel3_tipo = _clean_text(payload.tel3_tipo or "")
    item.tel3 = _clean_text(payload.tel3 or "")
    item.tel4_tipo = _clean_text(payload.tel4_tipo or "")
    item.tel4 = _clean_text(payload.tel4 or "")
    item.email = _clean_text(payload.email or "")
    item.homepage = _clean_text(payload.homepage or "")
    item.palavra_chave_1 = _clean_text(payload.palavra_chave_1 or "")
    item.palavra_chave_2 = _clean_text(payload.palavra_chave_2 or "")
    item.registro = _clean_text(payload.registro or "")
    item.especialidade = _clean_text(payload.especialidade or "")
    item.incluir_malas_diretas = bool(payload.incluir_malas_diretas)
    item.incluir_preferidos = bool(payload.incluir_preferidos)
    item.observacoes = _clean_text(payload.observacoes or "")
    db.commit()
    db.refresh(item)
    return _to_dict(item)


@router.delete("/{contato_id}")
def excluir_contato(
    contato_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _load_or_404(db, current_user.clinica_id, contato_id)
    db.delete(item)
    db.commit()
    return {"detail": "Contato excluido."}
