from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from models.clinica import Clinica
from models.indice_financeiro import IndiceCotacao, IndiceFinanceiro

DEFAULT_INDICE_NUMERO = 255

INDICES_PADRAO = [
    {"numero": 255, "sigla": "R$", "nome": "Reais", "reservado": True},
    {"numero": 2, "sigla": "UHO", "nome": "Unid. Honorario", "reservado": True},
    {"numero": 3, "sigla": "UPO", "nome": "Unid. Procedimento Odontologico", "reservado": True},
    {"numero": 1, "sigla": "USO", "nome": "Unid. Servico", "reservado": True},
]


def _norm_text(value: str | None) -> str:
    return str(value or "").strip()


def _norm_sigla(value: str | None) -> str:
    return _norm_text(value).upper()


def garantir_indices_padrao_clinica(db: Session, clinica_id: int) -> None:
    if not clinica_id:
        return
    existentes = {
        int(item.numero): item
        for item in db.query(IndiceFinanceiro)
        .filter(IndiceFinanceiro.clinica_id == int(clinica_id))
        .all()
    }
    for item in INDICES_PADRAO:
        numero = int(item["numero"])
        idx = existentes.get(numero)
        if not idx:
            db.add(
                IndiceFinanceiro(
                    clinica_id=int(clinica_id),
                    numero=numero,
                    sigla=_norm_text(item["sigla"]) or "R$",
                    nome=_norm_text(item["nome"]) or "Reais",
                    reservado=True,
                    ativo=True,
                )
            )
            continue
        if not _norm_text(idx.sigla):
            idx.sigla = _norm_text(item["sigla"]) or idx.sigla
        if not _norm_text(idx.nome):
            idx.nome = _norm_text(item["nome"]) or idx.nome
        idx.reservado = True
        idx.ativo = True if idx.ativo is None else idx.ativo
        db.add(idx)
    db.flush()


def garantir_indices_padrao_todas_clinicas(db: Session) -> None:
    clinicas = [int(item[0]) for item in db.query(Clinica.id).all() if item and item[0]]
    for clinica_id in clinicas:
        garantir_indices_padrao_clinica(db, clinica_id)


def _valor_atual_indice(db: Session, indice_id: int, *, reservado: bool) -> float:
    cot = (
        db.query(IndiceCotacao)
        .filter(IndiceCotacao.indice_id == int(indice_id))
        .order_by(desc(IndiceCotacao.data), desc(IndiceCotacao.id))
        .first()
    )
    if cot and cot.valor is not None:
        return float(cot.valor)
    return 1.0 if reservado else 0.0


def listar_indices(db: Session, clinica_id: int, *, include_inativos: bool = True) -> list[dict]:
    garantir_indices_padrao_clinica(db, clinica_id)
    query = db.query(IndiceFinanceiro).filter(IndiceFinanceiro.clinica_id == int(clinica_id))
    if not include_inativos:
        query = query.filter(IndiceFinanceiro.ativo.is_(True))
    itens = query.order_by(IndiceFinanceiro.nome.asc()).all()
    return [
        {
            "id": int(item.numero),
            "numero": int(item.numero),
            "sigla": _norm_text(item.sigla),
            "nome": _norm_text(item.nome),
            "reservado": bool(item.reservado),
            "ativo": bool(item.ativo),
            "valor_atual": _valor_atual_indice(db, item.id, reservado=bool(item.reservado)),
        }
        for item in itens
    ]


def listar_indices_com_map(db: Session, clinica_id: int) -> tuple[list[dict], dict[int, dict], dict[str, int]]:
    indices = listar_indices(db, clinica_id, include_inativos=True)
    por_numero = {int(item["id"]): item for item in indices}
    por_sigla = {
        _norm_sigla(item.get("sigla")): int(item["id"])
        for item in indices
        if _norm_sigla(item.get("sigla"))
    }
    return indices, por_numero, por_sigla


def resolver_numero_indice(
    db: Session,
    clinica_id: int,
    valor: int | str | None,
    *,
    default: int = DEFAULT_INDICE_NUMERO,
) -> int:
    _, por_numero, por_sigla = listar_indices_com_map(db, clinica_id)
    fallback = default if default in por_numero else (next(iter(por_numero.keys()), default))
    if valor is None:
        return int(fallback)
    raw = str(valor).strip()
    if not raw:
        return int(fallback)
    if raw.isdigit():
        numero = int(raw)
        return numero if numero in por_numero else int(fallback)
    sigla = _norm_sigla(raw)
    return int(por_sigla.get(sigla, fallback))


def dados_indice_por_numero(
    db: Session,
    clinica_id: int,
    numero: int | str | None,
) -> dict:
    indices, por_numero, _ = listar_indices_com_map(db, clinica_id)
    fallback = por_numero.get(DEFAULT_INDICE_NUMERO) or (indices[0] if indices else None)
    try:
        num = int(numero or DEFAULT_INDICE_NUMERO)
    except Exception:
        num = DEFAULT_INDICE_NUMERO
    return por_numero.get(num) or fallback or {"id": DEFAULT_INDICE_NUMERO, "sigla": "R$", "nome": "Reais"}


def proximo_numero_indice(db: Session, clinica_id: int) -> int | None:
    existentes = {
        int(item.numero)
        for item in db.query(IndiceFinanceiro.numero)
        .filter(IndiceFinanceiro.clinica_id == int(clinica_id))
        .all()
    }
    for numero in range(1, DEFAULT_INDICE_NUMERO):
        if numero not in existentes:
            return numero
    return None


def indice_em_uso(db: Session, clinica_id: int, numero: int) -> bool:
    from models.material import ListaMaterial
    from models.procedimento_tabela import ProcedimentoTabela
    from models.tratamento import Tratamento

    if (
        db.query(ProcedimentoTabela.id)
        .filter(
            ProcedimentoTabela.clinica_id == int(clinica_id),
            ProcedimentoTabela.nro_indice == int(numero),
        )
        .first()
    ):
        return True
    if (
        db.query(ListaMaterial.id)
        .filter(
            ListaMaterial.clinica_id == int(clinica_id),
            ListaMaterial.nro_indice == int(numero),
        )
        .first()
    ):
        return True
    if (
        db.query(Tratamento.id)
        .filter(
            Tratamento.clinica_id == int(clinica_id),
            Tratamento.indice == int(numero),
        )
        .first()
    ):
        return True
    return False


def normalize_cotacao_data(data_raw: str | None) -> str:
    raw = str(data_raw or "").strip()
    if not raw:
        raise ValueError("Data invalida.")
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    raise ValueError("Data invalida. Use DD/MM/AAAA ou YYYY-MM-DD.")
