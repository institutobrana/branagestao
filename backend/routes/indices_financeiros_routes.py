from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.indice_financeiro import IndiceCotacao, IndiceFinanceiro
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access
from services.indices_service import (
    dados_indice_por_numero,
    garantir_indices_padrao_clinica,
    indice_em_uso,
    listar_indices,
    normalize_cotacao_data,
    proximo_numero_indice,
)

router = APIRouter(
    prefix="/indices-financeiros",
    tags=["indices-financeiros"],
    dependencies=[Depends(require_module_access("financeiro"))],
)


class IndicePayload(BaseModel):
    nome: str
    sigla: str


class IndiceUpdatePayload(BaseModel):
    nome: str | None = None
    sigla: str | None = None


class CotacaoPayload(BaseModel):
    data: str
    valor: float


def _load_indice_or_404(db: Session, clinica_id: int, numero: int) -> IndiceFinanceiro:
    indice = (
        db.query(IndiceFinanceiro)
        .filter(
            IndiceFinanceiro.clinica_id == int(clinica_id),
            IndiceFinanceiro.numero == int(numero),
        )
        .first()
    )
    if not indice:
        raise HTTPException(status_code=404, detail="Índice não encontrado.")
    return indice


def _load_cotacao_or_404(db: Session, clinica_id: int, cotacao_id: int) -> IndiceCotacao:
    cotacao = (
        db.query(IndiceCotacao)
        .filter(
            IndiceCotacao.clinica_id == int(clinica_id),
            IndiceCotacao.id == int(cotacao_id),
        )
        .first()
    )
    if not cotacao:
        raise HTTPException(status_code=404, detail="Cotação não encontrada.")
    return cotacao


@router.get("")
def listar(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return listar_indices(db, current_user.clinica_id, include_inativos=True)


@router.post("")
def criar(
    payload: IndicePayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nome = (payload.nome or "").strip()
    sigla = (payload.sigla or "").strip().upper()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome do índice.")
    if not sigla:
        raise HTTPException(status_code=400, detail="Informe a sigla do índice.")
    garantir_indices_padrao_clinica(db, current_user.clinica_id)
    numero = proximo_numero_indice(db, current_user.clinica_id)
    if not numero:
        raise HTTPException(status_code=400, detail="Limite de índices atingido.")
    indice = IndiceFinanceiro(
        clinica_id=current_user.clinica_id,
        numero=numero,
        nome=nome,
        sigla=sigla,
        reservado=False,
        ativo=True,
    )
    db.add(indice)
    db.commit()
    return dados_indice_por_numero(db, current_user.clinica_id, numero)


@router.patch("/{numero}")
def atualizar(
    numero: int,
    payload: IndiceUpdatePayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    indice = _load_indice_or_404(db, current_user.clinica_id, numero)
    if indice.reservado:
        raise HTTPException(status_code=400, detail="Índice reservado do sistema.")
    nome = (payload.nome or "").strip()
    sigla = (payload.sigla or "").strip().upper()
    if nome:
        indice.nome = nome
    if sigla:
        indice.sigla = sigla
    db.add(indice)
    db.commit()
    return dados_indice_por_numero(db, current_user.clinica_id, numero)


@router.get("/{numero}/em-uso")
def verificar_em_uso(
    numero: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"em_uso": indice_em_uso(db, current_user.clinica_id, int(numero))}


@router.post("/{numero}/migrar-e-excluir")
def migrar_e_excluir(
    numero: int,
    payload: dict,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    destino = int(payload.get("numero_destino") or 0)
    if destino <= 0:
        raise HTTPException(status_code=400, detail="Selecione o índice destino.")
    origem = _load_indice_or_404(db, current_user.clinica_id, numero)
    if origem.reservado:
        raise HTTPException(status_code=400, detail="Índice reservado do sistema.")
    _load_indice_or_404(db, current_user.clinica_id, destino)

    from models.material import ListaMaterial
    from models.procedimento_tabela import ProcedimentoTabela
    from models.tratamento import Tratamento

    db.query(ProcedimentoTabela).filter(
        ProcedimentoTabela.clinica_id == current_user.clinica_id,
        ProcedimentoTabela.nro_indice == int(numero),
    ).update({"nro_indice": destino})
    db.query(ListaMaterial).filter(
        ListaMaterial.clinica_id == current_user.clinica_id,
        ListaMaterial.nro_indice == int(numero),
    ).update({"nro_indice": destino})
    db.query(Tratamento).filter(
        Tratamento.clinica_id == current_user.clinica_id,
        Tratamento.indice == int(numero),
    ).update({"indice": destino})

    db.delete(origem)
    db.commit()
    return {"detail": "Índice migrado e excluído com sucesso."}


@router.delete("/{numero}")
def excluir(
    numero: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    indice = _load_indice_or_404(db, current_user.clinica_id, numero)
    if indice.reservado:
        raise HTTPException(status_code=400, detail="Índice reservado do sistema.")
    if indice_em_uso(db, current_user.clinica_id, int(numero)):
        raise HTTPException(
            status_code=409,
            detail="Índice em uso. Migre os registros para outro índice antes de excluir.",
        )
    db.delete(indice)
    db.commit()
    return {"detail": "Índice eliminado."}


@router.get("/{numero}/cotacoes")
def listar_cotacoes(
    numero: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    indice = _load_indice_or_404(db, current_user.clinica_id, numero)
    itens = (
        db.query(IndiceCotacao)
        .filter(
            IndiceCotacao.clinica_id == current_user.clinica_id,
            IndiceCotacao.indice_id == indice.id,
        )
        .order_by(IndiceCotacao.data.asc(), IndiceCotacao.id.asc())
        .all()
    )
    return [
        {"id": c.id, "data": c.data, "valor": float(c.valor or 0)}
        for c in itens
    ]


@router.post("/{numero}/cotacoes")
def criar_cotacao(
    numero: int,
    payload: CotacaoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    indice = _load_indice_or_404(db, current_user.clinica_id, numero)
    try:
        data_iso = normalize_cotacao_data(payload.data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    valor = float(payload.valor or 0)
    if valor <= 0:
        raise HTTPException(status_code=400, detail="Informe um valor válido.")
    cotacao = IndiceCotacao(
        clinica_id=current_user.clinica_id,
        indice_id=indice.id,
        data=data_iso,
        valor=valor,
    )
    db.add(cotacao)
    db.commit()
    return {"detail": "Cotação salva."}


@router.patch("/{numero}/cotacoes/{cotacao_id}")
def atualizar_cotacao(
    numero: int,
    cotacao_id: int,
    payload: CotacaoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    indice = _load_indice_or_404(db, current_user.clinica_id, numero)
    cotacao = _load_cotacao_or_404(db, current_user.clinica_id, cotacao_id)
    if cotacao.indice_id != indice.id:
        raise HTTPException(status_code=400, detail="Cotação não pertence ao índice selecionado.")
    try:
        data_iso = normalize_cotacao_data(payload.data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    valor = float(payload.valor or 0)
    if valor <= 0:
        raise HTTPException(status_code=400, detail="Informe um valor válido.")
    cotacao.data = data_iso
    cotacao.valor = valor
    db.add(cotacao)
    db.commit()
    return {"detail": "Cotação atualizada."}


@router.delete("/{numero}/cotacoes/{cotacao_id}")
def excluir_cotacao(
    numero: int,
    cotacao_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _load_indice_or_404(db, current_user.clinica_id, numero)
    cotacao = _load_cotacao_or_404(db, current_user.clinica_id, cotacao_id)
    db.delete(cotacao)
    db.commit()
    return {"detail": "Cotação eliminada."}
