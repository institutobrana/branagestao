import json
import os
import re
import unicodedata
from datetime import date, datetime, time, timedelta
from html import escape
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, case, or_
from sqlalchemy.orm import Session

from database import get_db
from models.agenda_legado import AgendaLegadoBloqueio, AgendaLegadoEvento
from models.convenio_odonto import ConvenioOdonto
from models.financeiro import ItemAuxiliar
from models.modelo_documento import ModeloDocumento
from models.paciente import Paciente
from models.prestador_odonto import PrestadorOdonto
from models.procedimento_tabela import ProcedimentoTabela
from models.unidade_atendimento import UnidadeAtendimento
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access
from services.email_service import EmailDeliveryError, enviar_email
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
HHMM_PATTERN = re.compile(r"^(\d{1,2}):(\d{2})$")
PLACEHOLDER_PATTERN = re.compile(r"<<\s*([^>]+?)\s*>>")
TIPOS_ENVIO_AVISO = (
    {"id": "email", "label": "E-mail"},
    {"id": "whatsapp", "label": "WhatsApp"},
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


class AgendaRepeticaoPayload(BaseModel):
    item_id: int
    modo: str
    sobrepor: bool = False
    qtd_dias: int | None = None
    qtd_semanas: int | None = None
    dia_semana: int | None = None
    dia_mes: int | None = None
    qtd_meses: int | None = None


class AvisoAgendaEnviarItemPayload(BaseModel):
    agenda_id: int
    ok: bool = True


class AvisoAgendaEnviarPayload(BaseModel):
    tipo_envio: str
    modelo_id: int | None = None
    itens: list[AvisoAgendaEnviarItemPayload] = []
    assunto: str | None = None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None


def _parse_date_any(value: str | None) -> date | None:
    txt = str(value or "").strip()
    if not txt:
        return None
    parsed_iso = _parse_date(txt)
    if parsed_iso:
        return parsed_iso
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(txt, fmt).date()
        except Exception:
            continue
    return None


def _parse_hhmm_to_ms(value: str | None, default: int | None = None) -> int | None:
    txt = str(value or "").strip()
    if not txt:
        return default
    match = HHMM_PATTERN.match(txt)
    if not match:
        return default
    hh = int(match.group(1))
    mm = int(match.group(2))
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        return default
    return (hh * 60 + mm) * 60000


def _format_hhmm(ms: int) -> str:
    total = max(0, int(ms // 60000))
    hh = total // 60
    mm = total % 60
    return f"{hh:02d}:{mm:02d}"


def _dia_semana_label(value: int) -> str:
    labels = {
        1: "Segunda",
        2: "Terca",
        3: "Quarta",
        4: "Quinta",
        5: "Sexta",
        6: "Sabado",
        7: "Domingo",
    }
    return labels.get(int(value or 0), "")


def _parse_dias_semana(raw: str | None) -> set[int]:
    txt = str(raw or "").strip()
    if not txt:
        return {1, 2, 3, 4, 5, 6}
    dias: set[int] = set()
    for token in txt.split(","):
        token_txt = token.strip()
        if not token_txt:
            continue
        try:
            dia = int(token_txt)
        except Exception:
            continue
        if 1 <= dia <= 7:
            dias.add(dia)
    return dias


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    valid = [(int(ini), int(fim)) for ini, fim in intervals if int(fim) > int(ini)]
    if not valid:
        return []
    valid.sort(key=lambda x: (x[0], x[1]))
    merged: list[list[int]] = [[valid[0][0], valid[0][1]]]
    for ini, fim in valid[1:]:
        last = merged[-1]
        if ini <= last[1]:
            last[1] = max(last[1], fim)
        else:
            merged.append([ini, fim])
    return [(ini, fim) for ini, fim in merged]


def _config_bloqueio_interval(item: dict) -> tuple[int, int] | None:
    try:
        ini_ms = int(item.get("hora_ini_ms")) if item.get("hora_ini_ms") is not None else None
    except Exception:
        ini_ms = None
    try:
        fim_ms = int(item.get("hora_fin_ms")) if item.get("hora_fin_ms") is not None else None
    except Exception:
        fim_ms = None
    if ini_ms is None:
        ini_ms = _parse_hhmm_to_ms(str(item.get("hora_ini") or item.get("inicio") or "").strip())
    if fim_ms is None:
        fim_ms = _parse_hhmm_to_ms(str(item.get("hora_fin") or item.get("final") or "").strip())
    if ini_ms is None or fim_ms is None or fim_ms <= ini_ms:
        return None
    return int(ini_ms), int(fim_ms)


def _config_bloqueio_aplica(item: dict, data_ref: date, unidade_id: int | None) -> bool:
    dia_sem_raw = item.get("dia_sem")
    dia_sem = None
    if dia_sem_raw is not None and str(dia_sem_raw).strip():
        try:
            dia_sem = int(dia_sem_raw)
        except Exception:
            dia_sem = None
    if dia_sem is not None and dia_sem != (data_ref.weekday() + 1):
        return False

    if unidade_id:
        unidade_raw = item.get("unidade_id") or item.get("source_id")
        if unidade_raw is not None and str(unidade_raw).strip():
            try:
                if int(unidade_raw) != int(unidade_id):
                    return False
            except Exception:
                pass

    data_ini = _parse_date_any(item.get("data_ini") or item.get("vigencia_inicio") or item.get("vigencia"))
    data_fin = _parse_date_any(item.get("data_fin") or item.get("vigencia_fim"))
    if data_ini and data_ref < data_ini:
        return False
    if data_fin and data_ref > data_fin:
        return False
    return True


def _load_prestador_agenda_config(db: Session, clinica_id: int, prestador_id: int) -> dict:
    if int(prestador_id or 0) <= 0:
        return _normalize_agenda_config({})
    prestador = (
        db.query(PrestadorOdonto)
        .filter(
            PrestadorOdonto.clinica_id == int(clinica_id),
            PrestadorOdonto.id == int(prestador_id),
        )
        .first()
    )
    raw: dict = {}
    if prestador:
        try:
            txt = str(prestador.agenda_config_json or "").strip()
            if txt:
                parsed = json.loads(txt)
                if isinstance(parsed, dict):
                    raw = parsed
        except Exception:
            raw = {}
    return _normalize_agenda_config(raw)


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


def _hora_inicio_para_hhmm(value: int | None) -> str:
    total_min = max(0, int(int(value or 0) // 60000))
    hh = total_min // 60
    mm = total_min % 60
    return f"{hh:02d}:{mm:02d}"


def _data_br(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _preferencias_usuario_json(usuario: Usuario) -> dict:
    raw = (usuario.preferencias_usuario_json or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _catalogo_modelos_para_aviso(db: Session, usuario: Usuario, tipo_modelo: str) -> list[dict]:
    rows = (
        db.query(ModeloDocumento)
        .filter(
            ModeloDocumento.ativo.is_(True),
            ModeloDocumento.tipo_modelo == tipo_modelo,
            ((ModeloDocumento.clinica_id == usuario.clinica_id) | (ModeloDocumento.clinica_id.is_(None))),
        )
        .order_by(
            ModeloDocumento.clinica_id.is_(None).asc(),
            ModeloDocumento.nome_exibicao.asc(),
            ModeloDocumento.id.asc(),
        )
        .all()
    )
    return [
        {
            "id": int(item.id),
            "nome": str(item.nome_exibicao or "").strip(),
            "caminho": str(item.caminho_arquivo or "").strip(),
        }
        for item in rows
    ]


def _modelo_documento_por_id(
    db: Session,
    clinica_id: int,
    modelo_id: int,
    tipo_modelo: str,
) -> ModeloDocumento | None:
    if int(modelo_id or 0) <= 0:
        return None
    return (
        db.query(ModeloDocumento)
        .filter(
            ModeloDocumento.id == int(modelo_id),
            ModeloDocumento.ativo.is_(True),
            ModeloDocumento.tipo_modelo == tipo_modelo,
            ((ModeloDocumento.clinica_id == int(clinica_id)) | (ModeloDocumento.clinica_id.is_(None))),
        )
        .first()
    )


def _ler_texto_modelo(item: ModeloDocumento | None) -> str:
    if not item:
        return ""
    caminho_rel = str(item.caminho_arquivo or "").strip()
    if not caminho_rel:
        return ""
    caminho_abs = (PROJECT_DIR / caminho_rel).resolve()
    try:
        base = PROJECT_DIR.resolve()
        if not str(caminho_abs).startswith(str(base)):
            return ""
    except Exception:
        return ""
    if not caminho_abs.exists() or not caminho_abs.is_file():
        return ""
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return caminho_abs.read_text(encoding=enc).replace("\x00", "")
        except Exception:
            continue
    return ""


def _normalizar_chave_placeholder(valor: str) -> str:
    txt = str(valor or "")
    txt = unicodedata.normalize("NFD", txt)
    txt = "".join(ch for ch in txt if unicodedata.category(ch) != "Mn")
    txt = txt.lower()
    txt = re.sub(r"[^a-z0-9]+", "", txt)
    return txt


def _normalizar_whatsapp_numero(raw: str | None) -> str:
    digitos = re.sub(r"\D+", "", str(raw or ""))
    if not digitos:
        return ""
    if digitos.startswith("00"):
        digitos = digitos[2:]
    if len(digitos) >= 12 and digitos.startswith("55"):
        return digitos
    if len(digitos) in {10, 11}:
        return f"55{digitos}"
    return digitos


def _telefone_whatsapp_paciente(paciente: Paciente | None) -> tuple[str, str]:
    if not paciente:
        return "", ""
    candidatos: list[tuple[str, str]] = []
    for idx in range(1, 5):
        tipo = str(getattr(paciente, f"tipo_fone{idx}", "") or "").strip()
        valor = str(getattr(paciente, f"fone{idx}", "") or "").strip()
        if valor:
            candidatos.append((tipo, valor))
    if not candidatos:
        return "", ""
    for tipo, valor in candidatos:
        if "cel" in tipo.lower():
            normal = _normalizar_whatsapp_numero(valor)
            if normal:
                return normal, valor
    for _, valor in candidatos:
        normal = _normalizar_whatsapp_numero(valor)
        if normal:
            return normal, valor
    return "", ""


def _build_template_context(
    evento: AgendaLegadoEvento,
    paciente: Paciente | None,
    prestador_nome: str,
) -> dict[str, str]:
    data_base = evento.data.date() if evento.data else date.today()
    nome_paciente = str((paciente.nome_completo if paciente and paciente.nome_completo else None) or (paciente.nome if paciente else "") or evento.nome or "").strip()
    assunto = str(evento.motivo or "").strip()
    email = str((paciente.email if paciente else "") or "").strip()
    numero_wa, telefone_exibicao = _telefone_whatsapp_paciente(paciente)
    return {
        "pacientenome": nome_paciente,
        "nomecompleto": nome_paciente,
        "nome": nome_paciente,
        "agendadata": _data_br(data_base),
        "agendahora": _hora_inicio_para_hhmm(evento.hora_inicio),
        "cirurgiaonome": str(prestador_nome or "").strip(),
        "prestadornome": str(prestador_nome or "").strip(),
        "assunto": assunto,
        "motivo": assunto,
        "email": email,
        "telefone": telefone_exibicao,
        "whatsapp": numero_wa,
    }


def _render_template_mensagem(
    template: str,
    contexto: dict[str, str],
) -> str:
    texto = str(template or "").replace("\r\n", "\n").replace("\r", "\n")

    def _replace(match: re.Match[str]) -> str:
        chave_raw = str(match.group(1) or "")
        chave = _normalizar_chave_placeholder(chave_raw)
        if not chave:
            return ""
        return str(contexto.get(chave, ""))

    return PLACEHOLDER_PATTERN.sub(_replace, texto)


def _enviar_whatsapp_meta(numero: str, mensagem: str) -> dict:
    telefone = _normalizar_whatsapp_numero(numero)
    if not telefone:
        return {"enviado": False, "detail": "Telefone inválido."}
    token = str(os.getenv("WHATSAPP_TOKEN", "")).strip()
    phone_number_id = str(os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")).strip()
    if not token or not phone_number_id:
        link = f"https://wa.me/{telefone}?text={quote(str(mensagem or ''))}"
        return {"enviado": False, "detail": "Integração WhatsApp não configurada.", "url": link}
    try:
        import requests  # lazy import para evitar custo quando não utilizado

        resp = requests.post(
            f"https://graph.facebook.com/v22.0/{phone_number_id}/messages",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to": telefone,
                "type": "text",
                "text": {"body": str(mensagem or "")[:4096]},
            },
            timeout=20,
        )
        if resp.status_code >= 400:
            detalhe = resp.text.strip() or f"status={resp.status_code}"
            link = f"https://wa.me/{telefone}?text={quote(str(mensagem or ''))}"
            return {"enviado": False, "detail": detalhe, "url": link}
        return {"enviado": True}
    except Exception as exc:
        link = f"https://wa.me/{telefone}?text={quote(str(mensagem or ''))}"
        return {"enviado": False, "detail": str(exc), "url": link}


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


@router.get("/avisos-agendamento/opcoes")
def listar_opcoes_avisos_agendamento(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prefs = _preferencias_usuario_json(current_user)
    modelos_vals = prefs.get("modelos") if isinstance(prefs.get("modelos"), dict) else {}

    def _to_int(value: object) -> int | None:
        try:
            val = int(value)  # type: ignore[arg-type]
        except Exception:
            return None
        return val if val > 0 else None

    modelos_email = _catalogo_modelos_para_aviso(db, current_user, "email_agenda")
    modelos_whatsapp = _catalogo_modelos_para_aviso(db, current_user, "whatsapp_agenda")
    default_email_id = _to_int(modelos_vals.get("modelo_texto_email_agenda_id"))
    default_whatsapp_id = _to_int(modelos_vals.get("modelo_texto_whatsapp_agenda_id"))

    if default_email_id and not any(int(x["id"]) == default_email_id for x in modelos_email):
        default_email_id = None
    if default_whatsapp_id and not any(int(x["id"]) == default_whatsapp_id for x in modelos_whatsapp):
        default_whatsapp_id = None

    if default_email_id is None and modelos_email:
        default_email_id = int(modelos_email[0]["id"])
    if default_whatsapp_id is None and modelos_whatsapp:
        default_whatsapp_id = int(modelos_whatsapp[0]["id"])

    hoje = date.today().isoformat()
    return {
        "tipos_envio": list(TIPOS_ENVIO_AVISO),
        "modelos": {
            "email": modelos_email,
            "whatsapp": modelos_whatsapp,
        },
        "defaults": {
            "email_modelo_id": default_email_id,
            "whatsapp_modelo_id": default_whatsapp_id,
            "periodo_ini": hoje,
            "periodo_fim": hoje,
        },
    }


@router.get("/avisos-agendamento")
def pesquisar_avisos_agendamento(
    data_ini: str = Query(default=""),
    data_fim: str = Query(default=""),
    tipo_envio: str = Query(default="email"),
    todos_cirurgioes: bool = Query(default=True),
    id_prestador: int | None = Query(default=None),
    limit: int = Query(default=2000, ge=1, le=10000),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tipo = str(tipo_envio or "email").strip().lower()
    if tipo not in {"email", "whatsapp"}:
        raise HTTPException(status_code=400, detail="Tipo de envio inválido.")
    dt_ini = _parse_date(data_ini)
    dt_fim = _parse_date(data_fim)
    if not dt_ini or not dt_fim:
        raise HTTPException(status_code=400, detail="Informe um período válido.")
    if dt_fim < dt_ini:
        raise HTTPException(status_code=400, detail="Período de pesquisa inválido.")

    query = (
        db.query(AgendaLegadoEvento, Paciente, PrestadorOdonto)
        .outerjoin(
            Paciente,
            and_(
                Paciente.clinica_id == AgendaLegadoEvento.clinica_id,
                or_(Paciente.codigo == AgendaLegadoEvento.nro_pac, Paciente.id == AgendaLegadoEvento.nro_pac),
            ),
        )
        .outerjoin(
            PrestadorOdonto,
            and_(
                PrestadorOdonto.clinica_id == AgendaLegadoEvento.clinica_id,
                PrestadorOdonto.id == AgendaLegadoEvento.id_prestador,
            ),
        )
        .filter(
            AgendaLegadoEvento.clinica_id == current_user.clinica_id,
            AgendaLegadoEvento.data >= datetime.combine(dt_ini, time.min),
            AgendaLegadoEvento.data <= datetime.combine(dt_fim, time.max),
            AgendaLegadoEvento.tipo == 1,
            or_(AgendaLegadoEvento.status.is_(None), AgendaLegadoEvento.status != 2),
        )
    )
    if not todos_cirurgioes:
        prestador_alvo = int(id_prestador or current_user.prestador_id or 0)
        if prestador_alvo > 0:
            query = query.filter(AgendaLegadoEvento.id_prestador == prestador_alvo)

    rows = (
        query.order_by(
            AgendaLegadoEvento.data.asc(),
            AgendaLegadoEvento.hora_inicio.asc(),
            AgendaLegadoEvento.id.asc(),
        )
        .limit(int(limit))
        .all()
    )

    itens: list[dict] = []
    for evento, paciente, prestador in rows:
        contato = ""
        if tipo == "email":
            contato = str((paciente.email if paciente else "") or "").strip()
            if not contato:
                continue
        else:
            _, contato_exibicao = _telefone_whatsapp_paciente(paciente)
            contato = str(contato_exibicao or "").strip()
            if not contato:
                continue
        nome = str((paciente.nome_completo if paciente and paciente.nome_completo else None) or (paciente.nome if paciente else "") or evento.nome or "").strip()
        if not nome:
            continue
        data_evento = evento.data.date() if evento.data else dt_ini
        itens.append(
            {
                "id": int(evento.id),
                "data": data_evento.isoformat(),
                "hora": _hora_inicio_para_hhmm(evento.hora_inicio),
                "paciente": nome,
                "contato": contato,
                "ok": True,
                "id_prestador": int(evento.id_prestador),
                "cirurgiao": str(prestador.apelido or prestador.nome or "").strip() if prestador else "",
            }
        )
    return itens


@router.post("/avisos-agendamento/enviar")
def enviar_avisos_agendamento(
    payload: AvisoAgendaEnviarPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tipo = str(payload.tipo_envio or "").strip().lower()
    if tipo not in {"email", "whatsapp"}:
        raise HTTPException(status_code=400, detail="Tipo de envio inválido.")

    selecionados = [int(item.agenda_id) for item in (payload.itens or []) if bool(item.ok) and int(item.agenda_id or 0) > 0]
    if not selecionados:
        return {
            "tipo_envio": tipo,
            "total_selecionados": 0,
            "enviados": 0,
            "pendentes": 0,
            "falhas": [],
            "links_whatsapp": [],
        }

    modelo_tipo = "email_agenda" if tipo == "email" else "whatsapp_agenda"
    modelo = _modelo_documento_por_id(db, int(current_user.clinica_id), int(payload.modelo_id or 0), modelo_tipo)
    template_texto = _ler_texto_modelo(modelo).strip()
    if not template_texto:
        template_texto = (
            "Olá <<Paciente.Nome>>, seu agendamento é em <<Agenda.Data>> às <<Agenda.Hora>> com <<Cirurgião.Nome>>."
        )

    rows = (
        db.query(AgendaLegadoEvento, Paciente, PrestadorOdonto)
        .outerjoin(
            Paciente,
            and_(
                Paciente.clinica_id == AgendaLegadoEvento.clinica_id,
                or_(Paciente.codigo == AgendaLegadoEvento.nro_pac, Paciente.id == AgendaLegadoEvento.nro_pac),
            ),
        )
        .outerjoin(
            PrestadorOdonto,
            and_(
                PrestadorOdonto.clinica_id == AgendaLegadoEvento.clinica_id,
                PrestadorOdonto.id == AgendaLegadoEvento.id_prestador,
            ),
        )
        .filter(
            AgendaLegadoEvento.clinica_id == current_user.clinica_id,
            AgendaLegadoEvento.id.in_(selecionados),
        )
        .all()
    )
    by_id = {int(evento.id): (evento, paciente, prestador) for evento, paciente, prestador in rows}

    enviados = 0
    pendentes = 0
    falhas: list[dict] = []
    links_whatsapp: list[dict] = []
    assunto_padrao = str(payload.assunto or "").strip()
    for agenda_id in selecionados:
        trio = by_id.get(int(agenda_id))
        if not trio:
            falhas.append({"agenda_id": int(agenda_id), "motivo": "Agendamento não encontrado."})
            continue
        evento, paciente, prestador = trio
        prestador_nome = str((prestador.apelido if prestador and prestador.apelido else None) or (prestador.nome if prestador else "") or "").strip()
        contexto = _build_template_context(evento, paciente, prestador_nome)
        mensagem = _render_template_mensagem(template_texto, contexto).strip()
        if tipo == "email":
            email = str((paciente.email if paciente else "") or "").strip()
            if not email:
                falhas.append({"agenda_id": int(agenda_id), "motivo": "Paciente sem e-mail cadastrado."})
                continue
            assunto = assunto_padrao or f"Aviso de agendamento {_data_br(evento.data.date())}"
            html = f'<pre style="font-family:Arial,sans-serif;white-space:pre-wrap">{escape(mensagem)}</pre>'
            try:
                enviar_email(destinatario=email, assunto=assunto, html=html, texto=mensagem)
                enviados += 1
            except EmailDeliveryError as exc:
                falhas.append({"agenda_id": int(agenda_id), "motivo": str(exc)})
            except Exception as exc:
                falhas.append({"agenda_id": int(agenda_id), "motivo": str(exc)})
            continue

        numero_whatsapp, numero_exibicao = _telefone_whatsapp_paciente(paciente)
        if not numero_whatsapp:
            falhas.append({"agenda_id": int(agenda_id), "motivo": "Paciente sem telefone válido para WhatsApp."})
            continue
        resultado_wa = _enviar_whatsapp_meta(numero_whatsapp, mensagem)
        if bool(resultado_wa.get("enviado")):
            enviados += 1
        else:
            pendentes += 1
            detalhe = str(resultado_wa.get("detail") or "Envio pendente.")
            falhas.append({"agenda_id": int(agenda_id), "motivo": detalhe})
            url = str(resultado_wa.get("url") or "").strip()
            if url:
                links_whatsapp.append(
                    {
                        "agenda_id": int(agenda_id),
                        "paciente": str(contexto.get("pacientenome") or evento.nome or "").strip(),
                        "telefone": numero_exibicao,
                        "url": url,
                    }
                )

    return {
        "tipo_envio": tipo,
        "total_selecionados": len(selecionados),
        "enviados": int(enviados),
        "pendentes": int(pendentes),
        "falhas": falhas,
        "links_whatsapp": links_whatsapp,
    }


@router.get("/horarios-livres")
def pesquisar_horarios_livres(
    dias_semana: str = Query(default="1,2,3,4,5,6"),
    prestador_id: int | None = Query(default=None),
    unidade_id: int | None = Query(default=None),
    hora_inicio: str = Query(default=""),
    hora_fim: str = Query(default=""),
    data_ini: str = Query(default=""),
    data_fim: str = Query(default=""),
    limit: int = Query(default=3000, ge=1, le=10000),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)
    id_prestador = int(prestador_id or current_user.prestador_id or 0)
    id_unidade = int(unidade_id or current_user.unidade_atendimento_id or 0)
    if id_prestador <= 0:
        raise HTTPException(status_code=400, detail="Informe o cirurgiao/prestador.")
    if id_unidade <= 0:
        raise HTTPException(status_code=400, detail="Informe a unidade.")

    dias_validos = _parse_dias_semana(dias_semana)
    if not dias_validos:
        return []

    raw_data_ini = str(data_ini or "").strip()
    raw_data_fim = str(data_fim or "").strip()
    start_date = _parse_date_any(raw_data_ini) if raw_data_ini else None
    end_date = _parse_date_any(raw_data_fim) if raw_data_fim else None
    if raw_data_ini and not start_date:
        raise HTTPException(status_code=400, detail="Data inicial invalida.")
    if raw_data_fim and not end_date:
        raise HTTPException(status_code=400, detail="Data final invalida.")
    if not start_date and not end_date:
        start_date = date.today()
        end_date = start_date + timedelta(days=56)
    elif start_date and not end_date:
        end_date = start_date + timedelta(days=56)
    elif end_date and not start_date:
        start_date = date.today()
    if not start_date or not end_date or end_date < start_date:
        raise HTTPException(status_code=400, detail="Periodo de pesquisa invalido.")

    cfg = _load_prestador_agenda_config(db, clinica_id, id_prestador)
    step_min = max(5, int(str(cfg.get("duracao") or "5")))
    step_ms = step_min * 60000
    default_ini_ms = _parse_hhmm_to_ms(str(cfg.get("manha_inicio") or ""), default=7 * 60 * 60000)
    default_fim_ms = _parse_hhmm_to_ms(str(cfg.get("tarde_fim") or ""), default=20 * 60 * 60000)
    faixa_ini_ms = _parse_hhmm_to_ms(hora_inicio, default=default_ini_ms)
    faixa_fim_ms = _parse_hhmm_to_ms(hora_fim, default=default_fim_ms)
    if (
        faixa_ini_ms is None
        or faixa_fim_ms is None
        or int(faixa_fim_ms) <= int(faixa_ini_ms)
    ):
        raise HTTPException(status_code=400, detail="Faixa de horario invalida.")
    escala_intervals: list[tuple[int, int]] = []
    for ini_txt, fim_txt in (
        (str(cfg.get("manha_inicio") or ""), str(cfg.get("manha_fim") or "")),
        (str(cfg.get("tarde_inicio") or ""), str(cfg.get("tarde_fim") or "")),
    ):
        ini_ms = _parse_hhmm_to_ms(ini_txt)
        fim_ms = _parse_hhmm_to_ms(fim_txt)
        if ini_ms is None or fim_ms is None:
            continue
        if int(fim_ms) > int(ini_ms):
            escala_intervals.append((int(ini_ms), int(fim_ms)))
    if not escala_intervals:
        escala_intervals = [(int(faixa_ini_ms), int(faixa_fim_ms))]

    data_inicio_dt = datetime.combine(start_date, time.min)
    data_fim_dt = datetime.combine(end_date, time.max)

    eventos = (
        db.query(AgendaLegadoEvento)
        .filter(
            AgendaLegadoEvento.clinica_id == clinica_id,
            AgendaLegadoEvento.id_prestador == id_prestador,
            AgendaLegadoEvento.id_unidade == id_unidade,
            AgendaLegadoEvento.data >= data_inicio_dt,
            AgendaLegadoEvento.data <= data_fim_dt,
        )
        .order_by(AgendaLegadoEvento.data.asc(), AgendaLegadoEvento.hora_inicio.asc())
        .all()
    )
    eventos_by_date: dict[date, list[tuple[int, int]]] = {}
    for item in eventos:
        ini, fim = _normalize_interval(int(item.hora_inicio or 0), int(item.hora_fim or 0))
        if fim <= ini:
            continue
        eventos_by_date.setdefault(item.data.date(), []).append((ini, fim))

    bloqueios_db = (
        db.query(AgendaLegadoBloqueio)
        .filter(
            AgendaLegadoBloqueio.clinica_id == clinica_id,
            AgendaLegadoBloqueio.id_prestador == id_prestador,
            AgendaLegadoBloqueio.id_unidade == id_unidade,
            AgendaLegadoBloqueio.data_ini <= data_fim_dt,
            or_(AgendaLegadoBloqueio.data_fin.is_(None), AgendaLegadoBloqueio.data_fin >= data_inicio_dt),
        )
        .all()
    )
    bloqueios_cfg = cfg.get("bloqueios_itens") if isinstance(cfg.get("bloqueios_itens"), list) else []

    prestador_nome = (
        db.query(PrestadorOdonto.nome)
        .filter(PrestadorOdonto.clinica_id == clinica_id, PrestadorOdonto.id == id_prestador)
        .scalar()
    )
    prestador_nome_txt = str(prestador_nome or "").strip()

    resultados: list[dict] = []
    data_cursor = start_date
    while data_cursor <= end_date and len(resultados) < int(limit):
        dia_sem = data_cursor.weekday() + 1
        if dia_sem == 7 or dia_sem not in dias_validos:
            data_cursor += timedelta(days=1)
            continue

        intervals: list[tuple[int, int]] = []
        intervals.extend(eventos_by_date.get(data_cursor, []))

        for bloqueio in bloqueios_db:
            if int(bloqueio.dia_sem or 0) and int(bloqueio.dia_sem or 0) != dia_sem:
                continue
            inicio_b = bloqueio.data_ini.date() if bloqueio.data_ini else None
            fim_b = bloqueio.data_fin.date() if bloqueio.data_fin else None
            if inicio_b and data_cursor < inicio_b:
                continue
            if fim_b and data_cursor > fim_b:
                continue
            hora_ini_b = int(bloqueio.hora_ini or 0)
            hora_fim_b = int(bloqueio.hora_fin or 0)
            if hora_fim_b > hora_ini_b:
                intervals.append((hora_ini_b, hora_fim_b))

        for raw_item in bloqueios_cfg:
            if not isinstance(raw_item, dict):
                continue
            if not _config_bloqueio_aplica(raw_item, data_cursor, id_unidade):
                continue
            intervalo = _config_bloqueio_interval(raw_item)
            if intervalo:
                intervals.append(intervalo)

        merged = _merge_intervals(intervals)
        for escala_ini, escala_fim in escala_intervals:
            inicio_busca = max(int(faixa_ini_ms), int(escala_ini))
            fim_busca = min(int(faixa_fim_ms), int(escala_fim))
            if fim_busca <= inicio_busca:
                continue
            cursor_ms = inicio_busca
            while cursor_ms < fim_busca and len(resultados) < int(limit):
                ocupado = None
                prox_inicio_ocupado = fim_busca
                for ini, fim in merged:
                    if ini <= cursor_ms < fim:
                        ocupado = (ini, fim)
                        break
                    if ini > cursor_ms:
                        prox_inicio_ocupado = ini
                        break
                if ocupado:
                    cursor_ms = max(cursor_ms + step_ms, int(ocupado[1]))
                    continue
                disponivel_fim = min(fim_busca, int(prox_inicio_ocupado))
                duracao_min = max(0, (disponivel_fim - cursor_ms) // 60000)
                if duracao_min >= step_min:
                    resultados.append(
                        {
                            "data": data_cursor.isoformat(),
                            "dia": _dia_semana_label(dia_sem),
                            "hora": _format_hhmm(cursor_ms),
                            "hora_inicio": int(cursor_ms),
                            "duracao_min": int(duracao_min),
                            "duracao": int(duracao_min),
                            "cirurgiao": prestador_nome_txt,
                            "id_prestador": id_prestador,
                            "id_unidade": id_unidade,
                        }
                    )
                cursor_ms += step_ms
            if len(resultados) >= int(limit):
                break
        data_cursor += timedelta(days=1)

    return resultados


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


def _prestadores_com_usuario_associado(db: Session, clinica_id: int) -> set[int]:
    associados: set[int] = set()
    rows_prestador = (
        db.query(PrestadorOdonto.id)
        .filter(
            PrestadorOdonto.clinica_id == int(clinica_id),
            PrestadorOdonto.usuario_id.isnot(None),
        )
        .all()
    )
    for (prestador_id,) in rows_prestador:
        pid = int(prestador_id or 0)
        if pid > 0:
            associados.add(pid)

    rows_usuario = (
        db.query(Usuario.prestador_id)
        .filter(
            Usuario.clinica_id == int(clinica_id),
            Usuario.prestador_id.isnot(None),
        )
        .all()
    )
    for (prestador_id,) in rows_usuario:
        pid = int(prestador_id or 0)
        if pid > 0:
            associados.add(pid)
    return associados


@router.get("/prestadores")
def listar_prestadores(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)
    elegiveis_com_usuario = _prestadores_com_usuario_associado(db, clinica_id)
    rows = (
        db.query(PrestadorOdonto)
        .filter(PrestadorOdonto.clinica_id == clinica_id)
        .order_by(PrestadorOdonto.nome.asc(), PrestadorOdonto.id.asc())
        .all()
    )
    itens: list[dict] = []
    for item in rows:
        prestador_id = int(item.id)
        if prestador_id not in elegiveis_com_usuario:
            continue
        ativo = not bool(item.inativo)
        if not ativo:
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
    clinica_id = int(current_user.clinica_id)
    rows = (
        db.query(Paciente)
        .filter(Paciente.clinica_id == clinica_id)
        .order_by(Paciente.codigo.asc(), Paciente.id.asc())
        .limit(int(limit))
        .all()
    )
    convenio_ids = {
        int(x.id_convenio)
        for x in rows
        if x.id_convenio is not None and int(x.id_convenio) > 0
    }
    tabela_codigos = {
        int(x.tabela_codigo)
        for x in rows
        if x.tabela_codigo is not None and int(x.tabela_codigo) > 0
    }
    convenios_map: dict[int, str] = {}
    if convenio_ids:
        conv_rows = (
            db.query(ConvenioOdonto)
            .filter(ConvenioOdonto.clinica_id == clinica_id)
            .filter(
                or_(
                    ConvenioOdonto.source_id.in_(list(convenio_ids)),
                    ConvenioOdonto.id.in_(list(convenio_ids)),
                )
            )
            .all()
        )
        for conv in conv_rows:
            nome = str(conv.nome or "").strip()
            if not nome:
                continue
            convenios_map[int(conv.source_id)] = nome
            convenios_map[int(conv.id)] = nome
    tabelas_map: dict[int, str] = {}
    if tabela_codigos:
        tabela_rows = (
            db.query(ProcedimentoTabela)
            .filter(
                ProcedimentoTabela.clinica_id == clinica_id,
                ProcedimentoTabela.codigo.in_(list(tabela_codigos)),
            )
            .all()
        )
        for tabela in tabela_rows:
            nome = str(tabela.nome or "").strip()
            if nome:
                tabelas_map[int(tabela.codigo)] = nome
    itens: list[dict] = []
    for x in rows:
        nome = str(x.nome or "").strip()
        nome_completo = str(x.nome_completo or "").strip()
        if not nome and not nome_completo:
            continue
        extra = x.source_payload if isinstance(x.source_payload, dict) else {}
        id_convenio = int(x.id_convenio) if x.id_convenio is not None else None
        tabela_codigo = int(x.tabela_codigo) if x.tabela_codigo is not None else None
        convenio_nome_extra = str(extra.get("convenio_nome") or "").strip()
        tabela_nome_extra = str(extra.get("tabela_nome") or "").strip()
        itens.append(
            {
                "id": int(x.id),
                "codigo": int(x.codigo) if x.codigo is not None else None,
                "nome": nome,
                "sobrenome": str(x.sobrenome or "").strip(),
                "nome_completo": nome_completo,
                "tipo_fone1": str(x.tipo_fone1 or "").strip(),
                "fone1": str(x.fone1 or "").strip(),
                "tipo_fone2": str(x.tipo_fone2 or "").strip(),
                "fone2": str(x.fone2 or "").strip(),
                "tipo_fone3": str(x.tipo_fone3 or "").strip(),
                "fone3": str(x.fone3 or "").strip(),
                "tipo_fone4": str(x.tipo_fone4 or "").strip(),
                "fone4": str(x.fone4 or "").strip(),
                "cod_prontuario": str(x.cod_prontuario or "").strip(),
                "matricula": str(x.matricula or "").strip(),
                "id_convenio": id_convenio,
                "convenio_nome": convenio_nome_extra or convenios_map.get(int(id_convenio or 0), ""),
                "tabela_codigo": tabela_codigo,
                "tabela_nome": tabela_nome_extra or tabelas_map.get(int(tabela_codigo or 0), ""),
            }
        )
    return itens


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
