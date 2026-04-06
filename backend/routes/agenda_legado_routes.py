import json
from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from database import get_db
from models.agenda_legado import AgendaLegadoEvento
from models.financeiro import ItemAuxiliar
from models.paciente import Paciente
from models.prestador_odonto import PrestadorOdonto
from models.unidade_atendimento import UnidadeAtendimento
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access

router = APIRouter(
    prefix="/agenda-legado",
    tags=["agenda-legado"],
    dependencies=[Depends(require_module_access("agenda"))],
)

TIPOS_AUX_ESPECIALIDADE = ("Especialidade", "Especialidades")
TIPOS_AUX_STATUS_AGENDA = ("Situação do agendamento", "Situacao do agendamento")
TIPOS_FONE_AGENDA = (
    {"id": 1, "codigo": "1", "descricao": "Residencial", "ordem": 1, "valor_int": 1},
    {"id": 2, "codigo": "2", "descricao": "Comercial", "ordem": 2, "valor_int": 2},
    {"id": 3, "codigo": "3", "descricao": "Fax", "ordem": 3, "valor_int": 3},
    {"id": 4, "codigo": "4", "descricao": "Celular", "ordem": 4, "valor_int": 4},
    {"id": 5, "codigo": "5", "descricao": "Recado", "ordem": 5, "valor_int": 5},
)


class AgendaPayload(BaseModel):
    data: str
    hora_inicio: int
    hora_fim: int | None = None
    sala: int | None = None
    tipo: int | None = None
    nro_pac: int | None = None
    nome: str | None = None
    motivo: str | None = None
    status: int | None = None
    observ: str | None = None
    tip_fone1: int | None = None
    fone1: str | None = None
    tip_fone2: int | None = None
    fone2: str | None = None
    tip_fone3: int | None = None
    fone3: str | None = None
    id_prestador: int | None = None
    id_unidade: int | None = None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None


def _hora_ms(dt: datetime) -> int:
    return int((dt.hour * 3600 + dt.minute * 60 + dt.second) * 1000)


def _to_dict(item: AgendaLegadoEvento) -> dict:
    return {
        "id": int(item.id),
        "data": item.data.date().isoformat(),
        "hora_inicio": int(item.hora_inicio or 0),
        "hora_fim": int(item.hora_fim or 0),
        "sala": int(item.sala) if item.sala is not None else None,
        "nome": str(item.nome or "").strip(),
        "motivo": str(item.motivo or "").strip(),
        "fone1": str(item.fone1 or "").strip(),
        "fone2": str(item.fone2 or "").strip(),
        "fone3": str(item.fone3 or "").strip(),
        "status": int(item.status) if item.status is not None else None,
        "id_prestador": int(item.id_prestador),
        "id_unidade": int(item.id_unidade),
        "nro_pac": int(item.nro_pac) if item.nro_pac is not None else None,
        "tipo": int(item.tipo) if item.tipo is not None else None,
        "observ": str(item.observ or "").strip(),
        "tip_fone1": int(item.tip_fone1) if item.tip_fone1 is not None else None,
        "tip_fone2": int(item.tip_fone2) if item.tip_fone2 is not None else None,
        "tip_fone3": int(item.tip_fone3) if item.tip_fone3 is not None else None,
        "time_stamp_ins": item.time_stamp_ins.isoformat() if item.time_stamp_ins else None,
        "time_stamp_upd": item.time_stamp_upd.isoformat() if item.time_stamp_upd else None,
    }


def _load_or_404(db: Session, clinica_id: int, item_id: int) -> AgendaLegadoEvento:
    item = (
        db.query(AgendaLegadoEvento)
        .filter(AgendaLegadoEvento.id == item_id, AgendaLegadoEvento.clinica_id == clinica_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Agendamento nao encontrado.")
    return item


def _load_json_list(value: str | None) -> list[str]:
    txt = str(value or "").strip()
    if not txt:
        return []
    try:
        data = json.loads(txt)
        if isinstance(data, list):
            return [str(item).strip() for item in data if str(item or "").strip()]
    except Exception:
        pass
    return []


def _aux_to_options(rows: list[ItemAuxiliar]) -> list[dict]:
    itens = []
    for row in rows:
        codigo = str(row.codigo or "").strip()
        descricao = str(row.descricao or "").strip()
        if not codigo and not descricao:
            continue
        valor_int = None
        if codigo.isdigit():
            valor_int = int(codigo)
        elif row.ordem is not None:
            valor_int = int(row.ordem)
        itens.append(
            {
                "id": int(row.id),
                "codigo": codigo,
                "descricao": descricao or codigo,
                "ordem": int(row.ordem) if row.ordem is not None else None,
                "valor_int": valor_int,
            }
        )
    return itens


@router.get("")
def listar_agenda(
    start: str = Query(default=""),
    end: str = Query(default=""),
    prestador_id: int | None = Query(default=None),
    unidade_id: int | None = Query(default=None),
    nome: str = Query(default=""),
    limit: int = Query(default=2000),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    query = db.query(AgendaLegadoEvento).filter(AgendaLegadoEvento.clinica_id == current_user.clinica_id)

    if start_date:
        query = query.filter(AgendaLegadoEvento.data >= datetime.combine(start_date, time.min))
    if end_date:
        query = query.filter(AgendaLegadoEvento.data <= datetime.combine(end_date, time.max))

    if prestador_id:
        query = query.filter(AgendaLegadoEvento.id_prestador == prestador_id)
    if unidade_id:
        query = query.filter(AgendaLegadoEvento.id_unidade == unidade_id)

    termo = (nome or "").strip()
    if termo:
        like = f"%{termo}%"
        query = query.filter(
            or_(
                AgendaLegadoEvento.nome.ilike(like),
                AgendaLegadoEvento.motivo.ilike(like),
            )
        )

    limite = max(1, min(int(limit or 2000), 10000))
    itens = (
        query.order_by(AgendaLegadoEvento.data.asc(), AgendaLegadoEvento.hora_inicio.asc())
        .limit(limite)
        .all()
    )
    return [_to_dict(item) for item in itens]


@router.get("/next")
def proximo_agendado(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now()
    today = now.date()
    now_ms = _hora_ms(now)
    item = (
        db.query(AgendaLegadoEvento)
        .filter(AgendaLegadoEvento.clinica_id == current_user.clinica_id)
        .filter(
            or_(
                AgendaLegadoEvento.data > datetime.combine(today, time.min),
                and_(
                    AgendaLegadoEvento.data == datetime.combine(today, time.min),
                    AgendaLegadoEvento.hora_inicio >= now_ms,
                ),
            )
        )
        .order_by(AgendaLegadoEvento.data.asc(), AgendaLegadoEvento.hora_inicio.asc())
        .first()
    )
    return _to_dict(item) if item else None


@router.get("/prestadores")
def listar_prestadores(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)
    current_prestador_id = int(current_user.prestador_id or 0) or None
    rows = (
        db.query(PrestadorOdonto)
        .filter(PrestadorOdonto.clinica_id == clinica_id)
        .order_by(PrestadorOdonto.nome.asc(), PrestadorOdonto.id.asc())
        .all()
    )
    itens: list[dict] = []
    for item in rows:
        prestador_id = int(item.id)
        ativo = not bool(item.inativo)
        if not ativo and (current_prestador_id is None or prestador_id != current_prestador_id):
            continue
        nome = str(item.nome or "").strip()
        if not nome:
            continue
        especialidades_exec = _load_json_list(item.especialidades_json)
        itens.append(
            {
                "id": prestador_id,
                "row_id": prestador_id,
                "nome": nome,
                "ativo": ativo,
                "executa_procedimento": bool(item.executa_procedimento),
                "especialidade": str(item.especialidade or "").strip(),
                "especialidades_exec": especialidades_exec,
            }
        )
    itens.sort(key=lambda x: (str(x.get("nome") or "").lower(), int(x.get("id") or 0)))
    return itens


@router.get("/unidades")
def listar_unidades(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)
    current_unidade_id = int(current_user.unidade_atendimento_id or 0) or None
    rows = (
        db.query(UnidadeAtendimento)
        .filter(UnidadeAtendimento.clinica_id == clinica_id)
        .order_by(UnidadeAtendimento.source_id.asc(), UnidadeAtendimento.id.asc())
        .all()
    )
    itens: list[dict] = []
    for item in rows:
        unidade_id = int(item.id)
        ativo = not bool(item.inativo)
        if not ativo and (current_unidade_id is None or unidade_id != current_unidade_id):
            continue
        nome = str(item.nome or "").strip()
        if not nome:
            continue
        itens.append(
            {
                "id": unidade_id,
                "row_id": unidade_id,
                "nome": nome,
                "descricao": nome,
                "ativo": ativo,
            }
        )
    return itens


@router.get("/especialidades")
def listar_especialidades(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)
    nomes: set[str] = set()

    aux_rows = (
        db.query(ItemAuxiliar)
        .filter(
            ItemAuxiliar.clinica_id == clinica_id,
            ItemAuxiliar.tipo.in_(TIPOS_AUX_ESPECIALIDADE),
            ItemAuxiliar.inativo.is_(False),
        )
        .order_by(ItemAuxiliar.ordem.asc().nullslast(), ItemAuxiliar.descricao.asc())
        .all()
    )
    for row in aux_rows:
        nome = str(row.descricao or "").strip()
        if nome:
            nomes.add(nome)

    prest_rows = (
        db.query(PrestadorOdonto)
        .filter(PrestadorOdonto.clinica_id == clinica_id, PrestadorOdonto.inativo.is_(False))
        .all()
    )
    for item in prest_rows:
        esp = str(item.especialidade or "").strip()
        if esp:
            nomes.add(esp)
        for nome in _load_json_list(item.especialidades_json):
            txt = str(nome or "").strip()
            if txt:
                nomes.add(txt)

    itens = sorted(nomes, key=lambda x: x.lower())
    return [{"codigo": nome, "nome": nome} for nome in itens]


@router.get("/status-agendamento")
def listar_status_agendamento(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ItemAuxiliar)
        .filter(
            ItemAuxiliar.clinica_id == int(current_user.clinica_id),
            ItemAuxiliar.tipo.in_(TIPOS_AUX_STATUS_AGENDA),
            ItemAuxiliar.inativo.is_(False),
        )
        .order_by(ItemAuxiliar.ordem.asc().nullslast(), ItemAuxiliar.descricao.asc(), ItemAuxiliar.id.asc())
        .all()
    )
    return _aux_to_options(rows)


@router.get("/tipos-contato")
def listar_tipos_contato(
    current_user: Usuario = Depends(get_current_user),
):
    # Compatibilidade retroativa:
    # Este endpoint era consumido pela agenda para TIPFONE.
    # No Easy, TIPFONE não usa a tabela _TIPO_CONTATO (tipo de entidade de contato),
    # então retornamos aqui o domínio canônico de telefone.
    _ = current_user
    return list(TIPOS_FONE_AGENDA)


@router.get("/tipos-fone")
def listar_tipos_fone_agenda(
    current_user: Usuario = Depends(get_current_user),
):
    _ = current_user
    return list(TIPOS_FONE_AGENDA)


@router.get("/pacientes")
def listar_pacientes_agenda(
    limit: int = Query(default=5000, ge=1, le=10000),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Paciente)
        .filter(Paciente.clinica_id == int(current_user.clinica_id))
        .order_by(Paciente.codigo.asc(), Paciente.id.asc())
        .limit(int(limit))
        .all()
    )
    return [
        {
            "id": int(x.id),
            "codigo": int(x.codigo) if x.codigo is not None else None,
            "nome": str(x.nome or "").strip(),
            "sobrenome": str(x.sobrenome or "").strip(),
            "nome_completo": str(x.nome_completo or "").strip(),
            "tipo_fone1": str(x.tipo_fone1 or "").strip(),
            "fone1": str(x.fone1 or "").strip(),
            "tipo_fone2": str(x.tipo_fone2 or "").strip(),
            "fone2": str(x.fone2 or "").strip(),
            "tipo_fone3": str(x.tipo_fone3 or "").strip(),
            "fone3": str(x.fone3 or "").strip(),
            "tipo_fone4": str(x.tipo_fone4 or "").strip(),
            "fone4": str(x.fone4 or "").strip(),
        }
        for x in rows
        if str(x.nome or "").strip() or str(x.nome_completo or "").strip()
    ]


@router.post("")
def criar_agendamento(
    payload: AgendaPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = _parse_date(payload.data)
    if not data:
        raise HTTPException(status_code=400, detail="Informe uma data valida.")
    hora_inicio = int(payload.hora_inicio or 0)
    if hora_inicio <= 0:
        raise HTTPException(status_code=400, detail="Informe horario inicial.")
    id_prestador = int(payload.id_prestador or 0) or int(current_user.prestador_id or 0)
    id_unidade = int(payload.id_unidade or 0) or int(current_user.unidade_atendimento_id or 0)
    if id_prestador <= 0:
        raise HTTPException(status_code=400, detail="Informe o cirurgiao/prestador.")
    if id_unidade <= 0:
        raise HTTPException(status_code=400, detail="Informe a unidade.")
    item = AgendaLegadoEvento(
        clinica_id=current_user.clinica_id,
        id_prestador=id_prestador,
        id_unidade=id_unidade,
        data=datetime.combine(data, time.min),
        hora_inicio=hora_inicio,
        hora_fim=int(payload.hora_fim) if payload.hora_fim is not None else None,
        sala=int(payload.sala) if payload.sala is not None else None,
        tipo=int(payload.tipo) if payload.tipo is not None else None,
        nro_pac=int(payload.nro_pac) if payload.nro_pac is not None else None,
        nome=(payload.nome or "").strip(),
        motivo=(payload.motivo or "").strip(),
        status=int(payload.status) if payload.status is not None else None,
        observ=(payload.observ or "").strip(),
        tip_fone1=int(payload.tip_fone1) if payload.tip_fone1 is not None else None,
        fone1=(payload.fone1 or "").strip(),
        tip_fone2=int(payload.tip_fone2) if payload.tip_fone2 is not None else None,
        fone2=(payload.fone2 or "").strip(),
        tip_fone3=int(payload.tip_fone3) if payload.tip_fone3 is not None else None,
        fone3=(payload.fone3 or "").strip(),
        user_stamp_ins=int(current_user.id or 0),
        time_stamp_ins=datetime.now(),
        user_stamp_upd=int(current_user.id or 0),
        time_stamp_upd=datetime.now(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_dict(item)


@router.put("/{item_id}")
def atualizar_agendamento(
    item_id: int,
    payload: AgendaPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _load_or_404(db, current_user.clinica_id, item_id)
    data = _parse_date(payload.data)
    if not data:
        raise HTTPException(status_code=400, detail="Informe uma data valida.")
    hora_inicio = int(payload.hora_inicio or 0)
    if hora_inicio <= 0:
        raise HTTPException(status_code=400, detail="Informe horario inicial.")
    id_prestador = int(payload.id_prestador or 0) or int(current_user.prestador_id or 0)
    id_unidade = int(payload.id_unidade or 0) or int(current_user.unidade_atendimento_id or 0)
    if id_prestador <= 0:
        raise HTTPException(status_code=400, detail="Informe o cirurgiao/prestador.")
    if id_unidade <= 0:
        raise HTTPException(status_code=400, detail="Informe a unidade.")
    item.data = datetime.combine(data, time.min)
    item.hora_inicio = hora_inicio
    item.hora_fim = int(payload.hora_fim) if payload.hora_fim is not None else None
    item.sala = int(payload.sala) if payload.sala is not None else None
    item.tipo = int(payload.tipo) if payload.tipo is not None else None
    item.nro_pac = int(payload.nro_pac) if payload.nro_pac is not None else None
    item.nome = (payload.nome or "").strip()
    item.motivo = (payload.motivo or "").strip()
    item.status = int(payload.status) if payload.status is not None else None
    item.observ = (payload.observ or "").strip()
    item.tip_fone1 = int(payload.tip_fone1) if payload.tip_fone1 is not None else None
    item.fone1 = (payload.fone1 or "").strip()
    item.tip_fone2 = int(payload.tip_fone2) if payload.tip_fone2 is not None else None
    item.fone2 = (payload.fone2 or "").strip()
    item.tip_fone3 = int(payload.tip_fone3) if payload.tip_fone3 is not None else None
    item.fone3 = (payload.fone3 or "").strip()
    item.id_prestador = id_prestador
    item.id_unidade = id_unidade
    item.user_stamp_upd = int(current_user.id or 0)
    item.time_stamp_upd = datetime.now()
    db.commit()
    db.refresh(item)
    return _to_dict(item)


@router.delete("/{item_id}")
def excluir_agendamento(
    item_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _load_or_404(db, current_user.clinica_id, item_id)
    db.delete(item)
    db.commit()
    return {"ok": True}
