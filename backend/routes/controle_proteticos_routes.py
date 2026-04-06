from fastapi import APIRouter, Depends, Query
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from database import get_db
from models.controle_protetico import ControleProtetico
from models.paciente import Paciente
from models.protetico import Protetico, ServicoProtetico
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access

router = APIRouter(
    prefix="/controle-proteticos",
    tags=["controle-proteticos"],
    dependencies=[Depends(require_module_access("procedimentos"))],
)


def _fmt_data_br(value) -> str:
    if not value:
        return ""
    try:
        return value.strftime("%d/%m/%Y")
    except Exception:
        return str(value or "")


def _fmt_nome_paciente(item: Paciente | None) -> str:
    if not item:
        return ""
    nome_completo = str(item.nome_completo or "").strip()
    if nome_completo:
        return nome_completo
    partes = [str(item.nome or "").strip(), str(item.sobrenome or "").strip()]
    return " ".join(p for p in partes if p).strip()


@router.get("/filtros")
def listar_filtros(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    proteticos = (
        db.query(Protetico)
        .filter(Protetico.clinica_id == current_user.clinica_id)
        .order_by(func.lower(Protetico.nome).asc(), Protetico.id.asc())
        .all()
    )
    cirurgioes = (
        db.query(Usuario)
        .filter(
            Usuario.clinica_id == current_user.clinica_id,
            Usuario.ativo.is_(True),
        )
        .order_by(func.lower(Usuario.nome).asc(), Usuario.id.asc())
        .all()
    )
    return {
        "proteticos": [{"id": int(x.id), "nome": str(x.nome or "").strip()} for x in proteticos],
        "cirurgioes": [{"id": -1, "nome": "Clínica"}]
        + [{"id": int(x.id), "nome": str(x.nome or "").strip()} for x in cirurgioes],
    }


@router.get("")
def listar_registros(
    mes: int = Query(default=0),
    ano: int = Query(default=0),
    protetico_id: int = Query(default=0),
    cirurgiao_id: int = Query(default=0),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(ControleProtetico, Protetico, ServicoProtetico, Usuario, Paciente)
        .join(Protetico, Protetico.id == ControleProtetico.protetico_id)
        .outerjoin(ServicoProtetico, ServicoProtetico.id == ControleProtetico.servico_protetico_id)
        .outerjoin(Usuario, Usuario.id == ControleProtetico.cirurgiao_id)
        .outerjoin(Paciente, Paciente.id == ControleProtetico.paciente_id)
        .filter(ControleProtetico.clinica_id == current_user.clinica_id)
    )
    if int(protetico_id or 0) > 0:
        query = query.filter(ControleProtetico.protetico_id == int(protetico_id))
    if int(cirurgiao_id or 0) < 0:
        query = query.filter(ControleProtetico.cirurgiao_id.is_(None))
    elif int(cirurgiao_id or 0) > 0:
        query = query.filter(ControleProtetico.cirurgiao_id == int(cirurgiao_id))
    if int(ano or 0) > 0:
        query = query.filter(extract("year", ControleProtetico.data_entrega) == int(ano))
    if int(mes or 0) > 0:
        query = query.filter(extract("month", ControleProtetico.data_entrega) == int(mes))
    rows = query.order_by(
        ControleProtetico.data_entrega.asc().nullslast(),
        func.lower(ServicoProtetico.nome).asc().nullslast(),
        ControleProtetico.id.asc(),
    ).all()
    itens = []
    total_pendente = 0.0
    for registro, prot, servico, cirurgiao, paciente in rows:
        valor = float(registro.valor or 0)
        if not bool(registro.pago):
            total_pendente += valor
        itens.append(
            {
                "id": int(registro.id),
                "entrega": _fmt_data_br(registro.data_entrega),
                "servico": str(servico.nome or "").strip() if servico else "",
                "paciente": _fmt_nome_paciente(paciente),
                "indice": str(registro.indice or servico.indice if servico else registro.indice or "").strip(),
                "valor": valor,
                "ok": bool(registro.pago),
                "protetico_id": int(prot.id) if prot else None,
                "cirurgiao_id": int(cirurgiao.id) if cirurgiao else None,
            }
        )
    return {"itens": itens, "total_pendente": total_pendente}
