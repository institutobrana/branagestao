import json
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, case, or_
from sqlalchemy.orm import Session

from database import get_db
from models.agenda_legado import AgendaLegadoEvento
from models.financeiro import ItemAuxiliar
from models.paciente import Paciente
from models.prestador_odonto import PrestadorOdonto
from models.unidade_atendimento import UnidadeAtendimento
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access
from services.signup_service import garantir_auxiliares_raw_clinica

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

AGENDA_CONFIG_PADRAO = {
    "manha_inicio": "07:00",
    "manha_fim": "13:00",
    "tarde_inicio": "13:00",
    "tarde_fim": "20:00",
    "duracao": "5",
    "semana_horarios": "12",
    "dia_horarios": "12",
    "apresentacao_particular_cor": "#ffff00",
    "apresentacao_convenio_cor": "#0000ff",
    "apresentacao_compromisso_cor": "#00e5ef",
    "apresentacao_fonte": {
        "family": "MS Sans Serif",
        "size": 8,
        "bold": False,
        "italic": False,
        "underline": False,
        "strike": False,
        "color": "#000000",
        "script": "Ocidental",
    },
    "visualizacao_campos": [],
    "bloqueios_itens": [],
}

PROJECT_DIR = Path(__file__).resolve().parents[3]
COMPROMISSO_RAW_PATH = PROJECT_DIR / "Dados" / "Dist" / "_COMPROMISSO.raw"
COMPROMISSO_UTF16_PATTERN = re.compile(rb"(?:[\x20-\x7E\x80-\xFF]\x00){2,}")


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


class AgendaRepeticaoPayload(BaseModel):
    item_id: int
    modo: str
    sobrepor: bool = False
    qtd_dias: int | None = None
    qtd_semanas: int | None = None
    dia_semana: int | None = None
    dia_mes: int | None = None
    qtd_meses: int | None = None


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


def _normalize_interval(hora_inicio: int, hora_fim: int | None) -> tuple[int, int]:
    inicio = int(hora_inicio or 0)
    fim_raw = int(hora_fim or 0)
    if fim_raw <= inicio:
        fim_raw = inicio + 300000
    return inicio, fim_raw


def _tem_conflito_intervalo(
    db: Session,
    clinica_id: int,
    id_prestador: int,
    id_unidade: int,
    data_base: date,
    hora_inicio: int,
    hora_fim: int,
    ignore_id: int | None = None,
) -> bool:
    data_ref = datetime.combine(data_base, time.min)
    fim_expr = case(
        (AgendaLegadoEvento.hora_fim.is_(None), AgendaLegadoEvento.hora_inicio + 300000),
        (AgendaLegadoEvento.hora_fim <= AgendaLegadoEvento.hora_inicio, AgendaLegadoEvento.hora_inicio + 300000),
        else_=AgendaLegadoEvento.hora_fim,
    )
    query = db.query(AgendaLegadoEvento.id).filter(
        AgendaLegadoEvento.clinica_id == clinica_id,
        AgendaLegadoEvento.id_prestador == id_prestador,
        AgendaLegadoEvento.id_unidade == id_unidade,
        AgendaLegadoEvento.data == data_ref,
        AgendaLegadoEvento.hora_inicio < int(hora_fim),
        fim_expr > int(hora_inicio),
    )
    if ignore_id:
        query = query.filter(AgendaLegadoEvento.id != int(ignore_id))
    return query.first() is not None


def _iter_eventos_sobrepostos(
    db: Session,
    clinica_id: int,
    id_prestador: int,
    id_unidade: int,
    data_base: date,
    hora_inicio: int,
    hora_fim: int,
) -> list[AgendaLegadoEvento]:
    data_ref = datetime.combine(data_base, time.min)
    fim_expr = case(
        (AgendaLegadoEvento.hora_fim.is_(None), AgendaLegadoEvento.hora_inicio + 300000),
        (AgendaLegadoEvento.hora_fim <= AgendaLegadoEvento.hora_inicio, AgendaLegadoEvento.hora_inicio + 300000),
        else_=AgendaLegadoEvento.hora_fim,
    )
    return (
        db.query(AgendaLegadoEvento)
        .filter(
            AgendaLegadoEvento.clinica_id == clinica_id,
            AgendaLegadoEvento.id_prestador == id_prestador,
            AgendaLegadoEvento.id_unidade == id_unidade,
            AgendaLegadoEvento.data == data_ref,
            AgendaLegadoEvento.hora_inicio < int(hora_fim),
            fim_expr > int(hora_inicio),
        )
        .order_by(AgendaLegadoEvento.hora_inicio.asc(), AgendaLegadoEvento.id.asc())
        .all()
    )


def _clonar_evento_intervalo(
    source: AgendaLegadoEvento,
    hora_inicio: int,
    hora_fim: int,
    user_id: int,
) -> AgendaLegadoEvento:
    now = datetime.now()
    return AgendaLegadoEvento(
        clinica_id=source.clinica_id,
        id_prestador=source.id_prestador,
        id_unidade=source.id_unidade,
        data=source.data,
        hora_inicio=int(hora_inicio),
        hora_fim=int(hora_fim),
        sala=source.sala,
        tipo=source.tipo,
        nro_pac=source.nro_pac,
        nome=source.nome,
        motivo=source.motivo,
        status=source.status,
        observ=source.observ,
        tip_fone1=source.tip_fone1,
        fone1=source.fone1,
        tip_fone2=source.tip_fone2,
        fone2=source.fone2,
        tip_fone3=source.tip_fone3,
        fone3=source.fone3,
        palm_id=source.palm_id,
        palm_upd=source.palm_upd,
        myeasy_id=source.myeasy_id,
        myeasy_upd=source.myeasy_upd,
        user_stamp_ins=user_id,
        time_stamp_ins=now,
        user_stamp_upd=user_id,
        time_stamp_upd=now,
    )


def _aplicar_sobreposicao_intervalo(
    db: Session,
    clinica_id: int,
    id_prestador: int,
    id_unidade: int,
    data_base: date,
    hora_inicio: int,
    hora_fim: int,
    user_id: int,
) -> dict:
    sobrepostos = _iter_eventos_sobrepostos(
        db=db,
        clinica_id=clinica_id,
        id_prestador=id_prestador,
        id_unidade=id_unidade,
        data_base=data_base,
        hora_inicio=hora_inicio,
        hora_fim=hora_fim,
    )
    removidos = 0
    ajustados = 0
    segmentos = 0
    for item in sobrepostos:
        ini, fim = _normalize_interval(int(item.hora_inicio or 0), int(item.hora_fim or 0))
        if hora_inicio <= ini and hora_fim >= fim:
            db.delete(item)
            removidos += 1
            continue
        if hora_inicio <= ini and hora_fim < fim:
            if hora_fim < fim:
                item.hora_inicio = int(hora_fim)
                item.hora_fim = int(fim)
                item.user_stamp_upd = user_id
                item.time_stamp_upd = datetime.now()
                ajustados += 1
            continue
        if hora_inicio > ini and hora_fim >= fim:
            if hora_inicio > ini:
                item.hora_inicio = int(ini)
                item.hora_fim = int(hora_inicio)
                item.user_stamp_upd = user_id
                item.time_stamp_upd = datetime.now()
                ajustados += 1
            continue
        if hora_inicio > ini and hora_fim < fim:
            item.hora_inicio = int(ini)
            item.hora_fim = int(hora_inicio)
            item.user_stamp_upd = user_id
            item.time_stamp_upd = datetime.now()
            ajustados += 1
            right = _clonar_evento_intervalo(item, hora_fim, fim, user_id)
            db.add(right)
            segmentos += 1
    return {"removidos": removidos, "ajustados": ajustados, "segmentos": segmentos}


def _coerce_repeat_int(value: object, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(str(value).strip())
    except Exception:
        parsed = default
    return max(minimum, min(maximum, parsed))


def _normalizar_data_sem_domingo(value: date) -> date:
    # No modo "Próximos", domingo avança para segunda.
    if value.weekday() == 6:
        return value + timedelta(days=1)
    return value


def _normalizar_data_mes_sem_domingo(value: date) -> date:
    # No modo "Todo o dia", domingo recua um dia quando possível.
    if value.weekday() == 6:
        if value.day > 1:
            return value - timedelta(days=1)
        return value + timedelta(days=1)
    return value


def _add_months(base: date, months: int) -> tuple[int, int]:
    month_index = (base.month - 1) + months
    year = base.year + (month_index // 12)
    month = (month_index % 12) + 1
    return year, month


def _ultimo_dia_mes(year: int, month: int) -> int:
    if month == 12:
        prox = date(year + 1, 1, 1)
    else:
        prox = date(year, month + 1, 1)
    return (prox - timedelta(days=1)).day


def _datas_repeticao(base_data: date, payload: AgendaRepeticaoPayload) -> list[date]:
    modo = str(payload.modo or "").strip().lower()
    targets: list[date] = []
    if modo == "dias":
        qtd_dias = _coerce_repeat_int(payload.qtd_dias, minimum=1, maximum=60, default=1)
        for idx in range(1, qtd_dias + 1):
            alvo = _normalizar_data_sem_domingo(base_data + timedelta(days=idx))
            if alvo > base_data:
                targets.append(alvo)
    elif modo == "semanas":
        qtd_semanas = _coerce_repeat_int(payload.qtd_semanas, minimum=1, maximum=60, default=1)
        dia_semana = _coerce_repeat_int(payload.dia_semana, minimum=1, maximum=6, default=1)
        weekday_py = dia_semana - 1  # segunda=0 ... sábado=5
        inicio_semana = base_data - timedelta(days=base_data.weekday())
        for idx in range(1, qtd_semanas + 1):
            alvo = inicio_semana + timedelta(days=(idx * 7) + weekday_py)
            if alvo > base_data and alvo.weekday() != 6:
                targets.append(alvo)
    elif modo == "meses":
        qtd_meses = _coerce_repeat_int(payload.qtd_meses, minimum=1, maximum=60, default=1)
        dia_mes = _coerce_repeat_int(payload.dia_mes, minimum=1, maximum=31, default=base_data.day)
        for idx in range(1, qtd_meses + 1):
            year, month = _add_months(base_data, idx)
            ultimo = _ultimo_dia_mes(year, month)
            alvo = date(year, month, min(dia_mes, ultimo))
            alvo = _normalizar_data_mes_sem_domingo(alvo)
            if alvo > base_data:
                targets.append(alvo)
    # Evita duplicidade após normalizações (ex.: domingo -> segunda já existente).
    unicos: list[date] = []
    vistos: set[date] = set()
    for alvo in targets:
        if alvo in vistos:
            continue
        vistos.add(alvo)
        unicos.append(alvo)
    return unicos


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


def _extract_utf16_texts(raw_bytes: bytes) -> list[str]:
    textos: list[str] = []
    for match in COMPROMISSO_UTF16_PATTERN.finditer(raw_bytes):
        txt = match.group().decode("utf-16le", errors="ignore").replace("\x00", "").strip()
        if txt:
            textos.append(txt)
    return textos


def _assuntos_compromisso_raw_options() -> list[dict]:
    if not COMPROMISSO_RAW_PATH.exists():
        return []
    try:
        strings = _extract_utf16_texts(COMPROMISSO_RAW_PATH.read_bytes())
    except Exception:
        return []
    itens: list[dict] = []
    vistos: set[str] = set()
    i = 0
    ordem = 1
    while i < len(strings):
        atual = str(strings[i] or "").strip()
        prox = str(strings[i + 1] or "").strip() if i + 1 < len(strings) else ""
        codigo = ""
        descricao = ""
        if atual.isdigit() and prox:
            codigo = atual if len(atual) > 1 else atual.zfill(2)
            descricao = prox
            i += 2
        else:
            descricao = atual
            i += 1
        descricao = " ".join(descricao.split()).strip()
        if not descricao:
            continue
        chave = descricao.casefold()
        if chave in vistos:
            continue
        vistos.add(chave)
        if not codigo:
            codigo = f"{ordem:02d}"
        valor_int = int(codigo) if codigo.isdigit() else ordem
        itens.append(
            {
                "id": ordem,
                "codigo": codigo,
                "descricao": descricao,
                "ordem": ordem,
                "valor_int": valor_int,
            }
        )
        ordem += 1
    return itens


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
                "cor_apresentacao": str(getattr(row, "cor_apresentacao", "") or "").strip(),
            }
        )
    return itens


def _coerce_agenda_int(value: object, default: int, minimum: int) -> str:
    try:
        parsed = int(str(value).strip())
    except Exception:
        parsed = default
    return str(max(minimum, parsed))


def _normalize_agenda_config(raw: object) -> dict:
    cfg = dict(AGENDA_CONFIG_PADRAO)
    if isinstance(raw, dict):
        cfg.update(raw)
    cfg["duracao"] = _coerce_agenda_int(cfg.get("duracao", "5"), default=5, minimum=5)
    cfg["semana_horarios"] = _coerce_agenda_int(cfg.get("semana_horarios", "12"), default=12, minimum=1)
    cfg["dia_horarios"] = _coerce_agenda_int(cfg.get("dia_horarios", "12"), default=12, minimum=1)
    if not isinstance(cfg.get("visualizacao_campos"), list):
        cfg["visualizacao_campos"] = []
    if not isinstance(cfg.get("bloqueios_itens"), list):
        cfg["bloqueios_itens"] = []
    if not isinstance(cfg.get("apresentacao_fonte"), dict):
        cfg["apresentacao_fonte"] = dict(AGENDA_CONFIG_PADRAO["apresentacao_fonte"])
    return cfg


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
        agenda_config_raw = {}
        try:
            txt = str(item.agenda_config_json or "").strip()
            if txt:
                parsed = json.loads(txt)
                if isinstance(parsed, dict):
                    agenda_config_raw = parsed
        except Exception:
            agenda_config_raw = {}
        itens.append(
            {
                "id": prestador_id,
                "row_id": prestador_id,
                "nome": nome,
                "ativo": ativo,
                "executa_procedimento": bool(item.executa_procedimento),
                "especialidade": str(item.especialidade or "").strip(),
                "especialidades_exec": especialidades_exec,
                "agenda_config": _normalize_agenda_config(agenda_config_raw),
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
    clinica_id = int(current_user.clinica_id)
    rows = (
        db.query(ItemAuxiliar)
        .filter(
            ItemAuxiliar.clinica_id == clinica_id,
            ItemAuxiliar.tipo.in_(TIPOS_AUX_STATUS_AGENDA),
            or_(ItemAuxiliar.inativo.is_(False), ItemAuxiliar.inativo.is_(None)),
        )
        .order_by(ItemAuxiliar.ordem.asc().nullslast(), ItemAuxiliar.descricao.asc(), ItemAuxiliar.id.asc())
        .all()
    )
    if not rows:
        try:
            garantir_auxiliares_raw_clinica(db, clinica_id)
        except Exception:
            pass
        rows = (
            db.query(ItemAuxiliar)
            .filter(
                ItemAuxiliar.clinica_id == clinica_id,
                or_(ItemAuxiliar.inativo.is_(False), ItemAuxiliar.inativo.is_(None)),
                ItemAuxiliar.tipo.ilike("%agendamento%"),
            )
            .order_by(ItemAuxiliar.ordem.asc().nullslast(), ItemAuxiliar.descricao.asc(), ItemAuxiliar.id.asc())
            .all()
        )
    return _aux_to_options(rows)


@router.get("/assuntos-compromisso")
def listar_assuntos_compromisso(
    current_user: Usuario = Depends(get_current_user),
):
    _ = current_user
    return _assuntos_compromisso_raw_options()


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
    hora_inicio, hora_fim_norm = _normalize_interval(hora_inicio, payload.hora_fim)
    id_prestador = int(payload.id_prestador or 0) or int(current_user.prestador_id or 0)
    id_unidade = int(payload.id_unidade or 0) or int(current_user.unidade_atendimento_id or 0)
    if id_prestador <= 0:
        raise HTTPException(status_code=400, detail="Informe o cirurgiao/prestador.")
    if id_unidade <= 0:
        raise HTTPException(status_code=400, detail="Informe a unidade.")
    if _tem_conflito_intervalo(
        db=db,
        clinica_id=int(current_user.clinica_id),
        id_prestador=id_prestador,
        id_unidade=id_unidade,
        data_base=data,
        hora_inicio=hora_inicio,
        hora_fim=hora_fim_norm,
    ):
        raise HTTPException(status_code=409, detail="Ja existe agendamento no horario informado.")
    item = AgendaLegadoEvento(
        clinica_id=current_user.clinica_id,
        id_prestador=id_prestador,
        id_unidade=id_unidade,
        data=datetime.combine(data, time.min),
        hora_inicio=hora_inicio,
        hora_fim=hora_fim_norm,
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
    hora_inicio, hora_fim_norm = _normalize_interval(hora_inicio, payload.hora_fim)
    id_prestador = int(payload.id_prestador or 0) or int(current_user.prestador_id or 0)
    id_unidade = int(payload.id_unidade or 0) or int(current_user.unidade_atendimento_id or 0)
    if id_prestador <= 0:
        raise HTTPException(status_code=400, detail="Informe o cirurgiao/prestador.")
    if id_unidade <= 0:
        raise HTTPException(status_code=400, detail="Informe a unidade.")
    if _tem_conflito_intervalo(
        db=db,
        clinica_id=int(current_user.clinica_id),
        id_prestador=id_prestador,
        id_unidade=id_unidade,
        data_base=data,
        hora_inicio=hora_inicio,
        hora_fim=hora_fim_norm,
        ignore_id=int(item_id),
    ):
        raise HTTPException(status_code=409, detail="Ja existe agendamento no horario informado.")
    item.data = datetime.combine(data, time.min)
    item.hora_inicio = hora_inicio
    item.hora_fim = hora_fim_norm
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


@router.post("/repetir")
def repetir_agendamento(
    payload: AgendaRepeticaoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item_base = _load_or_404(db, current_user.clinica_id, int(payload.item_id))
    base_data = item_base.data.date()
    base_inicio, base_fim = _normalize_interval(int(item_base.hora_inicio or 0), int(item_base.hora_fim or 0))
    if base_inicio <= 0 or base_fim <= base_inicio:
        raise HTTPException(status_code=400, detail="Agendamento base inválido para repetição.")

    datas = _datas_repeticao(base_data, payload)
    user_id = int(current_user.id or 0)
    resumo = {
        "datas_avaliadas": len(datas),
        "criados": 0,
        "removidos": 0,
        "ajustados": 0,
        "segmentos": 0,
        "conflitos": 0,
        "datas_conflito": [],
        "datas_aplicadas": [],
    }
    for alvo in datas:
        if bool(payload.sobrepor):
            faixa = _aplicar_sobreposicao_intervalo(
                db=db,
                clinica_id=int(current_user.clinica_id),
                id_prestador=int(item_base.id_prestador),
                id_unidade=int(item_base.id_unidade),
                data_base=alvo,
                hora_inicio=base_inicio,
                hora_fim=base_fim,
                user_id=user_id,
            )
            resumo["removidos"] += int(faixa.get("removidos", 0) or 0)
            resumo["ajustados"] += int(faixa.get("ajustados", 0) or 0)
            resumo["segmentos"] += int(faixa.get("segmentos", 0) or 0)
        else:
            conflito = _tem_conflito_intervalo(
                db=db,
                clinica_id=int(current_user.clinica_id),
                id_prestador=int(item_base.id_prestador),
                id_unidade=int(item_base.id_unidade),
                data_base=alvo,
                hora_inicio=base_inicio,
                hora_fim=base_fim,
            )
            if conflito:
                resumo["conflitos"] += 1
                resumo["datas_conflito"].append(alvo.isoformat())
                continue
        novo = AgendaLegadoEvento(
            clinica_id=int(item_base.clinica_id),
            id_prestador=int(item_base.id_prestador),
            id_unidade=int(item_base.id_unidade),
            data=datetime.combine(alvo, time.min),
            hora_inicio=int(base_inicio),
            hora_fim=int(base_fim),
            sala=item_base.sala,
            tipo=item_base.tipo,
            nro_pac=item_base.nro_pac,
            nome=(item_base.nome or "").strip(),
            motivo=(item_base.motivo or "").strip(),
            status=item_base.status,
            observ=(item_base.observ or "").strip(),
            tip_fone1=item_base.tip_fone1,
            fone1=(item_base.fone1 or "").strip(),
            tip_fone2=item_base.tip_fone2,
            fone2=(item_base.fone2 or "").strip(),
            tip_fone3=item_base.tip_fone3,
            fone3=(item_base.fone3 or "").strip(),
            user_stamp_ins=user_id,
            time_stamp_ins=datetime.now(),
            user_stamp_upd=user_id,
            time_stamp_upd=datetime.now(),
        )
        db.add(novo)
        resumo["criados"] += 1
        resumo["datas_aplicadas"].append(alvo.isoformat())
    db.commit()
    return resumo


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
