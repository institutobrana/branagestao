import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models.convenio_odonto import ConvenioOdonto
from models.financeiro import ItemAuxiliar
from models.prestador_odonto import (
    PrestadorComissaoOdonto,
    PrestadorCredenciamentoOdonto,
    PrestadorOdonto,
)
from models.procedimento_generico import ProcedimentoGenerico
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access
from security.system_accounts import (
    SYSTEM_PRESTADOR_CODIGO,
    SYSTEM_PRESTADOR_SOURCE_ID,
    SYSTEM_PRESTADOR_TIPO,
    SYSTEM_USER_NOME,
    is_system_prestador,
    is_system_user,
)

router = APIRouter(
    prefix="/cadastros/prestadores",
    tags=["prestadores"],
    dependencies=[Depends(require_module_access("prestadores"))],
)
TIPO_AUX_PRESTADOR = "Tipos de prestador"
TIPO_AUX_CBOS = "CBO-S"
TIPOS_AUX_ESPECIALIDADE = ("Especialidade", "Especialidades")
TIPOS_USUARIO_COM_PRESTADOR = {
    "Cirurgião dentista",
    "Protético",
    "Perito",
    "THD",
}
TIPOS_PRESTADOR_PADRAO = [
    ("01", "Cirurgião dentista"),
    ("02", "Clínica odontológica"),
    ("03", "Clínica ortodôntica"),
    ("04", "Clínica radiológica"),
    ("05", "Perito"),
]
CBOS_PRESTADOR_PADRAO = [
    ("06310", "Cir.Dentista em Geral"),
    ("06330", "Cir.Dentista (saúde pública)"),
    ("06335", "Cir.Dentista (traumatologia buco maxilo facial)"),
    ("06340", "Cir.Dentista (endodontia)"),
    ("06345", "Cir.Dentista (ortodontia)"),
    ("06350", "Cir.Dentista (patologia bucal)"),
    ("06355", "Cir.Dentista (pediatria)"),
    ("06360", "Cir.Dentista (prótese)"),
    ("06365", "Cir.Dentista (radiologia)"),
    ("06370", "Cir.Dentista (periodontia)"),
]


def _clean_text(value: Any, max_len: int | None = None) -> str | None:
    txt = " ".join(str(value or "").split()).strip()
    if not txt:
        return None
    if max_len is not None:
        return txt[:max_len]
    return txt


def _clean_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    txt = str(value).strip().lower()
    if txt in {"1", "true", "sim", "s", "yes"}:
        return True
    if txt in {"0", "false", "nao", "não", "n", "no"}:
        return False
    return default


def _split_obs_cred_legado(obs_texto: str) -> tuple[str, str]:
    bruto = str(obs_texto or "").strip()
    if not bruto.startswith("[ALERTA]"):
        return "", bruto
    marcador = "\n[OBS]\n"
    if marcador not in bruto:
        return "", bruto
    corpo = bruto[len("[ALERTA]") :].lstrip("\r\n")
    alerta, obs = corpo.split(marcador, 1)
    return alerta.strip(), obs.strip()


def _tipo_repasse_para_codigo(txt: str | None, codigo: int | None) -> int:
    try:
        if codigo is not None:
            valor = int(codigo)
            if valor in (1, 2):
                return valor
    except Exception:
        pass
    texto = str(txt or "").strip().lower()
    if "%" in texto:
        return 1
    if "fix" in texto:
        return 2
    return 1


def _tipo_repasse_para_texto(txt: str | None, codigo: int | None) -> str:
    cod = _tipo_repasse_para_codigo(txt, codigo)
    return "% sobre valor" if cod == 1 else "Valor fixo"


def _buscar_especialidade_aux(
    db: Session,
    clinica_id: int,
    row_id: int | None,
    nome: str | None,
) -> ItemAuxiliar | None:
    try:
        if row_id and int(row_id) > 0:
            return (
                db.query(ItemAuxiliar)
                .filter(
                    ItemAuxiliar.clinica_id == clinica_id,
                    ItemAuxiliar.id == int(row_id),
                    ItemAuxiliar.tipo.in_(TIPOS_AUX_ESPECIALIDADE),
                )
                .first()
            )
    except Exception:
        pass
    nome_limpo = _clean_text(nome, 255)
    if not nome_limpo:
        return None
    return (
        db.query(ItemAuxiliar)
        .filter(
            ItemAuxiliar.clinica_id == clinica_id,
            ItemAuxiliar.tipo.in_(TIPOS_AUX_ESPECIALIDADE),
            func.lower(ItemAuxiliar.descricao) == nome_limpo.lower(),
        )
        .first()
    )


def _clean_br_date(value: Any) -> str | None:
    txt = str(value or "").strip()
    if not txt:
        return None
    parts = txt.split("/")
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail="Informe a data no formato dd/mm/aaaa.")
    dia, mes, ano = parts
    if not (dia.isdigit() and mes.isdigit() and ano.isdigit() and len(ano) == 4):
        raise HTTPException(status_code=400, detail="Informe a data no formato dd/mm/aaaa.")
    d = int(dia)
    m = int(mes)
    y = int(ano)
    if d < 1 or d > 31 or m < 1 or m > 12 or y < 1900 or y > 2100:
        raise HTTPException(status_code=400, detail="Informe uma data valida no formato dd/mm/aaaa.")
    return f"{d:02d}/{m:02d}/{y:04d}"


def _today_br_date() -> str:
    return datetime.now().strftime("%d/%m/%Y")


def _clean_json_list(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        txt = value.strip()
        if not txt:
            return None
        try:
            parsed = json.loads(txt)
        except Exception:
            parsed = [txt]
    elif isinstance(value, list):
        parsed = value
    else:
        parsed = [str(value)]
    normalized = [str(item).strip() for item in parsed if str(item or "").strip()]
    if not normalized:
        return None
    return json.dumps(normalized, ensure_ascii=False)


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


def _coerce_int(value: Any) -> int | None:
    try:
        n = int(str(value).strip())
        return n if n > 0 else None
    except Exception:
        return None


def _normalize_hhmm(value: Any) -> str | None:
    txt = str(value or "").strip()
    if not txt:
        return None
    parts = txt.split(":")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return None
    h = int(parts[0])
    m = int(parts[1])
    if h < 0 or h > 23 or m < 0 or m > 59:
        return None
    return f"{h:02d}:{m:02d}"


def _hhmm_to_ms(value: str | None) -> int | None:
    if not value:
        return None
    try:
        h, m = value.split(":")
        return (int(h) * 60 + int(m)) * 60000
    except Exception:
        return None


def _normalize_dia_sem(value: Any) -> int | None:
    txt = str(value or "").strip().lower()
    if not txt:
        return None
    mapa = {
        "segunda": 1,
        "terça": 2,
        "terca": 2,
        "quarta": 3,
        "quinta": 4,
        "sexta": 5,
        "sábado": 6,
        "sabado": 6,
        "domingo": 7,
    }
    if txt in mapa:
        return mapa[txt]
    try:
        n = int(txt)
        return n if 1 <= n <= 7 else None
    except Exception:
        return None


def _dia_sem_to_label(value: int | None) -> str:
    labels = {
        1: "Segunda",
        2: "Terça",
        3: "Quarta",
        4: "Quinta",
        5: "Sexta",
        6: "Sábado",
        7: "Domingo",
    }
    return labels.get(int(value or 0), "")


def _normalize_agenda_bloqueio_item(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    try:
        data_ini = _clean_br_date(
            raw.get("data_ini") or raw.get("vigencia_inicio") or raw.get("vigencia")
        ) if str(raw.get("data_ini") or raw.get("vigencia_inicio") or raw.get("vigencia") or "").strip() else None
    except HTTPException:
        data_ini = None
    try:
        data_fin = _clean_br_date(
            raw.get("data_fin") or raw.get("vigencia_fim")
        ) if str(raw.get("data_fin") or raw.get("vigencia_fim") or "").strip() else None
    except HTTPException:
        data_fin = None
    hora_ini = _normalize_hhmm(raw.get("hora_ini") or raw.get("inicio"))
    hora_fin = _normalize_hhmm(raw.get("hora_fin") or raw.get("final"))
    dia_sem = _normalize_dia_sem(raw.get("dia_sem") or raw.get("dia"))
    dia = _clean_text(raw.get("dia"), 20) or _dia_sem_to_label(dia_sem)
    unidade = _clean_text(raw.get("unidade"), 180)
    if not unidade and not data_ini and not data_fin and not hora_ini and not hora_fin:
        return None
    return {
        "id": _coerce_int(raw.get("id")) or int(datetime.now().timestamp() * 1000),
        "unidade": unidade or "",
        "unidade_id": _coerce_int(raw.get("unidade_id") or raw.get("source_id")),
        "unidade_row_id": _coerce_int(raw.get("unidade_row_id") or raw.get("row_id")),
        "dia": dia or "",
        "dia_sem": dia_sem,
        "vigencia_inicio": data_ini or "",
        "vigencia_fim": data_fin or "",
        "data_ini": data_ini or "",
        "data_fin": data_fin or "",
        "inicio": hora_ini or "",
        "final": hora_fin or "",
        "hora_ini": hora_ini or "",
        "hora_fin": hora_fin or "",
        "hora_ini_ms": _hhmm_to_ms(hora_ini),
        "hora_fin_ms": _hhmm_to_ms(hora_fin),
        "mensagem": _clean_text(raw.get("mensagem") or raw.get("msg_agenda"), 500) or "",
        "msg_agenda": _clean_text(raw.get("msg_agenda") or raw.get("mensagem"), 500) or "",
    }


def _normalize_agenda_config(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    cfg = dict(raw)
    itens = raw.get("bloqueios_itens")
    if isinstance(itens, list):
        normalized: list[dict[str, Any]] = []
        for item in itens:
            norm = _normalize_agenda_bloqueio_item(item)
            if norm:
                normalized.append(norm)
        cfg["bloqueios_itens"] = normalized
    return cfg


def _ensure_tipos_prestador(db: Session, clinica_id: int) -> list[ItemAuxiliar]:
    rows = (
        db.query(ItemAuxiliar)
        .filter(
            ItemAuxiliar.clinica_id == clinica_id,
            ItemAuxiliar.tipo == TIPO_AUX_PRESTADOR,
        )
        .order_by(ItemAuxiliar.codigo.asc(), ItemAuxiliar.id.asc())
        .all()
    )
    by_codigo = {str(item.codigo or "").strip(): item for item in rows}
    changed = False
    for codigo, descricao in TIPOS_PRESTADOR_PADRAO:
        item = by_codigo.get(codigo)
        if item is None:
            db.add(
                ItemAuxiliar(
                    clinica_id=clinica_id,
                    tipo=TIPO_AUX_PRESTADOR,
                    codigo=codigo,
                    descricao=descricao,
                )
            )
            changed = True
            continue
        if (item.descricao or "").strip() != descricao:
            item.descricao = descricao
            changed = True
    if changed:
        db.commit()
        rows = (
            db.query(ItemAuxiliar)
            .filter(
                ItemAuxiliar.clinica_id == clinica_id,
                ItemAuxiliar.tipo == TIPO_AUX_PRESTADOR,
            )
            .order_by(ItemAuxiliar.codigo.asc(), ItemAuxiliar.id.asc())
            .all()
        )
    return rows


def _ensure_cbos_prestador(db: Session, clinica_id: int) -> list[ItemAuxiliar]:
    rows = (
        db.query(ItemAuxiliar)
        .filter(
            ItemAuxiliar.clinica_id == clinica_id,
            ItemAuxiliar.tipo == TIPO_AUX_CBOS,
        )
        .order_by(ItemAuxiliar.codigo.asc(), ItemAuxiliar.id.asc())
        .all()
    )
    by_codigo = {str(item.codigo or "").strip(): item for item in rows}
    changed = False
    for codigo, descricao in CBOS_PRESTADOR_PADRAO:
        item = by_codigo.get(codigo)
        if item is None:
            db.add(
                ItemAuxiliar(
                    clinica_id=clinica_id,
                    tipo=TIPO_AUX_CBOS,
                    codigo=codigo,
                    descricao=descricao,
                )
            )
            changed = True
            continue
        if (item.descricao or "").strip() != descricao:
            item.descricao = descricao
            changed = True
    if changed:
        db.commit()
        rows = (
            db.query(ItemAuxiliar)
            .filter(
                ItemAuxiliar.clinica_id == clinica_id,
                ItemAuxiliar.tipo == TIPO_AUX_CBOS,
            )
            .order_by(ItemAuxiliar.codigo.asc(), ItemAuxiliar.id.asc())
            .all()
        )
    return rows


class PrestadorPayload(BaseModel):
    codigo: str | None = None
    nome: str
    apelido: str | None = None
    tipo_prestador: str | None = None
    inicio: str | None = None
    termino: str | None = None
    ativo: bool = True
    executa_procedimento: bool = True
    cro: str | None = None
    uf_cro: str | None = None
    cpf: str | None = None
    rg: str | None = None
    inss: str | None = None
    ccm: str | None = None
    contrato: str | None = None
    cnes: str | None = None
    cbos: str | None = None
    nascimento: str | None = None
    sexo: str | None = None
    estado_civil: str | None = None
    prefixo: str | None = None
    inclusao: str | None = None
    alteracao: str | None = None
    id_interno: str | None = None
    fone1_tipo: str | None = None
    fone1: str | None = None
    fone2_tipo: str | None = None
    fone2: str | None = None
    email: str | None = None
    homepage: str | None = None
    logradouro_tipo: str | None = None
    endereco: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    cep: str | None = None
    uf: str | None = None
    banco: str | None = None
    agencia: str | None = None
    conta: str | None = None
    nome_conta: str | None = None
    modo_pagamento: str | None = None
    faculdade: str | None = None
    formatura: str | None = None
    alerta_agendamentos: str | None = None
    especialidade: str | None = None
    especialidades_exec: list[str] | None = None
    agenda_config: dict[str, Any] | None = None
    observacoes: str | None = None


class CredenciamentoPayload(BaseModel):
    codigo: str | None = None
    convenio_row_id: int
    prestador_row_id: int | None = None
    inicio: str | None = None
    fim: str | None = None
    valor_us: str | None = None
    aviso: str | None = None
    observacoes: str | None = None


class ComissaoPayload(BaseModel):
    vigencia: str | None = None
    prestador_row_id: int | None = None
    convenio_row_id: int
    especialidade_row_id: int | None = None
    especialidade: str | None = None
    procedimento_generico_id: int | None = None
    tipo_repasse_codigo: int | None = None
    tipo_repasse: str | None = None
    repasse: str | None = None


def _proximo_source_id(db: Session, model: type[Any], clinica_id: int) -> int:
    rows = db.query(model).filter(model.clinica_id == clinica_id).all()
    atual = 0
    for item in rows:
        try:
            atual = max(atual, int(item.source_id or 0))
        except Exception:
            continue
    return atual + 1


def _prestador_to_dict(item: PrestadorOdonto) -> dict[str, Any]:
    especialidades_exec = _load_json_list(item.especialidades_json)
    agenda_cfg: dict[str, Any] = {}
    try:
        if str(item.agenda_config_json or "").strip():
            agenda_cfg = json.loads(item.agenda_config_json or "{}")
    except Exception:
        agenda_cfg = {}
    return {
        "id": int(item.id),
        "row_id": int(item.id),
        "source_id": int(item.source_id),
        "codigo": (item.codigo or "").strip(),
        "nome": (item.nome or "").strip(),
        "apelido": (item.apelido or "").strip(),
        "tipo_prestador": (item.tipo_prestador or "").strip(),
        "inicio": (item.data_inicio or "").strip(),
        "termino": (item.data_termino or "").strip(),
        "ativo": not bool(item.inativo),
        "executa_procedimento": bool(item.executa_procedimento),
        "cro": (item.cro or "").strip(),
        "uf_cro": (item.uf_cro or "").strip(),
        "cpf": (item.cpf or "").strip(),
        "rg": (item.rg or "").strip(),
        "inss": (item.inss or "").strip(),
        "ccm": (item.ccm or "").strip(),
        "contrato": (item.contrato or "").strip(),
        "cnes": (item.cnes or "").strip(),
        "cbos": (item.cbos or "").strip(),
        "nascimento": (item.nascimento or "").strip(),
        "sexo": (item.sexo or "").strip(),
        "estado_civil": (item.estado_civil or "").strip(),
        "prefixo": (item.prefixo or "").strip(),
        "inclusao": (item.data_inclusao or "").strip(),
        "alteracao": (item.data_alteracao or "").strip(),
        "id_interno": (item.id_interno or "").strip(),
        "fone1_tipo": (item.fone1_tipo or "").strip(),
        "fone1": (item.fone1 or "").strip(),
        "fone2_tipo": (item.fone2_tipo or "").strip(),
        "fone2": (item.fone2 or "").strip(),
        "email": (item.email or "").strip(),
        "homepage": (item.homepage or "").strip(),
        "logradouro_tipo": (item.logradouro_tipo or "").strip(),
        "endereco": (item.endereco or "").strip(),
        "numero": (item.numero or "").strip(),
        "complemento": (item.complemento or "").strip(),
        "bairro": (item.bairro or "").strip(),
        "cidade": (item.cidade or "").strip(),
        "cep": (item.cep or "").strip(),
        "uf": (item.uf or "").strip(),
        "banco": (item.banco or "").strip(),
        "agencia": (item.agencia or "").strip(),
        "conta": (item.conta or "").strip(),
        "nome_conta": (item.nome_conta or "").strip(),
        "modo_pagamento": (item.modo_pagamento or "").strip(),
        "faculdade": (item.faculdade or "").strip(),
        "formatura": (item.formatura or "").strip(),
        "alerta_agendamentos": (item.alerta_agendamentos or "").strip(),
        "especialidade": (item.especialidade or "").strip(),
        "especialidades_exec": especialidades_exec,
        "agenda_config": agenda_cfg,
        "observacoes": (item.observacoes or "").strip(),
        "usuario_id": int(item.usuario_id or 0) or None,
        "is_system_prestador": is_system_prestador(item),
    }


def _clinica_sintetica(current_user: Usuario) -> dict[str, Any]:
    return {
        "id": -1,
        "row_id": None,
        "source_id": SYSTEM_PRESTADOR_SOURCE_ID,
        "codigo": SYSTEM_PRESTADOR_CODIGO,
        "nome": SYSTEM_USER_NOME,
        "apelido": "",
        "tipo_prestador": SYSTEM_PRESTADOR_TIPO,
        "inicio": "",
        "termino": "",
        "ativo": True,
        "executa_procedimento": True,
        "cro": "",
        "uf_cro": "",
        "cpf": "",
        "rg": "",
        "inss": "",
        "ccm": "",
        "contrato": "",
        "cnes": "",
        "cbos": "",
        "nascimento": "",
        "sexo": "",
        "estado_civil": "",
        "prefixo": "",
        "inclusao": "",
        "alteracao": "",
        "id_interno": str(SYSTEM_PRESTADOR_SOURCE_ID),
        "fone1_tipo": "",
        "fone1": "",
        "fone2_tipo": "",
        "fone2": "",
        "email": "",
        "homepage": "",
        "logradouro_tipo": "",
        "endereco": "",
        "numero": "",
        "complemento": "",
        "bairro": "",
        "cidade": "",
        "cep": "",
        "uf": "",
        "banco": "",
        "agencia": "",
        "conta": "",
        "nome_conta": "",
        "modo_pagamento": "",
        "faculdade": "",
        "formatura": "",
        "alerta_agendamentos": "",
        "especialidade": "",
        "especialidades_exec": [],
        "agenda_config": {},
        "observacoes": "",
        "usuario_id": None,
        "is_system_prestador": True,
    }


def _credenciamento_to_dict(item: PrestadorCredenciamentoOdonto) -> dict[str, Any]:
    return {
        "id": int(item.id),
        "row_id": int(item.id),
        "codigo": (item.codigo or "").strip(),
        "prestador_row_id": int(item.prestador_id or 0) or None,
        "prestador_id": int(item.prestador_id or 0) or -1,
        "prestador_nome": ((item.prestador.nome if item.prestador else "") or "Clínica").strip(),
        "convenio_row_id": int(item.convenio_id),
        "convenio_id": int(item.convenio_source_id or 0) or None,
        "convenio_nome": ((item.convenio.nome if item.convenio else "") or "").strip(),
        "inicio": (item.inicio or "").strip(),
        "fim": (item.fim or "").strip(),
        "valor_us": (item.valor_us or "").strip(),
        "inclusao": (item.data_inclusao or "").strip(),
        "alteracao": (item.data_alteracao or "").strip(),
        "aviso": (item.aviso or "").strip(),
        "alerta": (item.aviso or "").strip(),
        "obs": (item.observacoes or "").strip(),
    }


def _comissao_to_dict(item: PrestadorComissaoOdonto) -> dict[str, Any]:
    return {
        "id": int(item.id),
        "row_id": int(item.id),
        "vigencia": (item.vigencia or "").strip(),
        "prestador_row_id": int(item.prestador_id or 0) or None,
        "prestador_id": int(item.prestador_id or 0) or -1,
        "prestador_nome": ((item.prestador.nome if item.prestador else "") or "Clínica").strip(),
        "convenio_row_id": int(item.convenio_id),
        "convenio_id": int(item.convenio_source_id or 0) or None,
        "convenio_nome": ((item.convenio.nome if item.convenio else "") or "").strip(),
        "especialidade_row_id": int(item.especialidade_row_id or 0) or None,
        "especialidade": (item.especialidade or "").strip(),
        "procedimento_generico_id": int(item.procedimento_generico_id or 0) or None,
        "procedimento_generico_nome": (
            item.procedimento_generico_nome
            or (item.procedimento_generico.descricao if item.procedimento_generico else "")
            or ""
        ).strip(),
        "tipo_repasse_codigo": int(item.tipo_repasse_codigo or 0) or _tipo_repasse_para_codigo(item.tipo_repasse, None),
        "tipo_repasse": _tipo_repasse_para_texto(item.tipo_repasse, item.tipo_repasse_codigo),
        "repasse": (item.repasse or "").strip(),
        "inclusao": (item.data_inclusao or "").strip(),
        "alteracao": (item.data_alteracao or "").strip(),
    }


def _credenciamento_to_dict(item: PrestadorCredenciamentoOdonto) -> dict[str, Any]:
    aviso = (item.aviso or "").strip()
    obs = (item.observacoes or "").strip()
    if not aviso and obs:
        alerta_legado, obs_legado = _split_obs_cred_legado(obs)
        if alerta_legado:
            aviso = alerta_legado
            obs = obs_legado
    return {
        "id": int(item.id),
        "row_id": int(item.id),
        "codigo": (item.codigo or "").strip(),
        "prestador_row_id": int(item.prestador_id or 0) or None,
        "prestador_id": int(item.prestador_id or 0) or -1,
        "prestador_nome": ((item.prestador.nome if item.prestador else "") or "Clinica").strip(),
        "convenio_row_id": int(item.convenio_id),
        "convenio_id": int(item.convenio_source_id or 0) or None,
        "convenio_nome": ((item.convenio.nome if item.convenio else "") or "").strip(),
        "inicio": (item.inicio or "").strip(),
        "fim": (item.fim or "").strip(),
        "valor_us": (item.valor_us or "").strip(),
        "inclusao": (item.data_inclusao or "").strip(),
        "alteracao": (item.data_alteracao or "").strip(),
        "aviso": aviso,
        "alerta": aviso,
        "obs": obs,
    }


def _apply_prestador_payload(item: PrestadorOdonto, payload: PrestadorPayload) -> None:
    nome = _clean_text(payload.nome, 160)
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome do prestador.")
    item.codigo = _clean_text(payload.codigo, 20)
    item.nome = nome
    item.apelido = _clean_text(payload.apelido, 120)
    item.tipo_prestador = _clean_text(payload.tipo_prestador, 80)
    item.data_inicio = _clean_br_date(payload.inicio) if str(payload.inicio or "").strip() else None
    item.data_termino = _clean_br_date(payload.termino) if str(payload.termino or "").strip() else None
    item.inativo = not _clean_bool(payload.ativo, True)
    item.executa_procedimento = _clean_bool(payload.executa_procedimento, True)
    item.cro = _clean_text(payload.cro, 40)
    item.uf_cro = _clean_text(payload.uf_cro, 10)
    item.cpf = _clean_text(payload.cpf, 20)
    item.rg = _clean_text(payload.rg, 30)
    item.inss = _clean_text(payload.inss, 40)
    item.ccm = _clean_text(payload.ccm, 40)
    item.contrato = _clean_text(payload.contrato, 40)
    item.cnes = _clean_text(payload.cnes, 40)
    item.cbos = _clean_text(payload.cbos, 120)
    item.nascimento = _clean_br_date(payload.nascimento) if str(payload.nascimento or "").strip() else None
    item.sexo = _clean_text(payload.sexo, 20)
    item.estado_civil = _clean_text(payload.estado_civil, 40)
    item.prefixo = _clean_text(payload.prefixo, 40)
    item.data_inclusao = _clean_br_date(payload.inclusao) if str(payload.inclusao or "").strip() else item.data_inclusao
    item.data_alteracao = _clean_br_date(payload.alteracao) if str(payload.alteracao or "").strip() else item.data_alteracao
    item.id_interno = _clean_text(payload.id_interno, 40)
    item.fone1_tipo = _clean_text(payload.fone1_tipo, 40)
    item.fone1 = _clean_text(payload.fone1, 40)
    item.fone2_tipo = _clean_text(payload.fone2_tipo, 40)
    item.fone2 = _clean_text(payload.fone2, 40)
    item.email = _clean_text(payload.email, 180)
    item.homepage = _clean_text(payload.homepage, 180)
    item.logradouro_tipo = _clean_text(payload.logradouro_tipo, 40)
    item.endereco = _clean_text(payload.endereco, 180)
    item.numero = _clean_text(payload.numero, 20)
    item.complemento = _clean_text(payload.complemento, 120)
    item.bairro = _clean_text(payload.bairro, 120)
    item.cidade = _clean_text(payload.cidade, 120)
    item.cep = _clean_text(payload.cep, 20)
    item.uf = _clean_text(payload.uf, 10)
    item.banco = _clean_text(payload.banco, 120)
    item.agencia = _clean_text(payload.agencia, 40)
    item.conta = _clean_text(payload.conta, 40)
    item.nome_conta = _clean_text(payload.nome_conta, 160)
    item.modo_pagamento = _clean_text(payload.modo_pagamento, 80)
    item.faculdade = _clean_text(payload.faculdade, 180)
    item.formatura = _clean_text(payload.formatura, 20)
    item.alerta_agendamentos = _clean_text(payload.alerta_agendamentos, 255)
    item.especialidade = _clean_text(payload.especialidade, 80)
    item.especialidades_json = _clean_json_list(payload.especialidades_exec)
    agenda_cfg = _normalize_agenda_config(payload.agenda_config or {})
    item.agenda_config_json = json.dumps(agenda_cfg, ensure_ascii=False) if agenda_cfg else None
    item.observacoes = _clean_text(payload.observacoes)


def _apply_credenciamento_payload(
    item: PrestadorCredenciamentoOdonto,
    payload: CredenciamentoPayload,
    convenio: ConvenioOdonto,
    prestador: PrestadorOdonto | None,
) -> None:
    item.codigo = _clean_text(payload.codigo, 20)
    item.convenio_id = int(convenio.id)
    item.convenio_source_id = int(convenio.source_id)
    item.prestador_id = int(prestador.id) if prestador else None
    item.prestador_source_id = int(prestador.source_id) if prestador else None
    item.inicio = _clean_br_date(payload.inicio) if str(payload.inicio or "").strip() else None
    item.fim = _clean_br_date(payload.fim) if str(payload.fim or "").strip() else None
    item.valor_us = _clean_text(payload.valor_us, 30)
    item.aviso = _clean_text(payload.aviso)
    item.observacoes = _clean_text(payload.observacoes)


def _apply_comissao_payload(
    item: PrestadorComissaoOdonto,
    db: Session,
    clinica_id: int,
    payload: ComissaoPayload,
    convenio: ConvenioOdonto,
    prestador: PrestadorOdonto | None,
    procedimento_generico: ProcedimentoGenerico | None,
) -> None:
    item.vigencia = _clean_br_date(payload.vigencia) if str(payload.vigencia or "").strip() else None
    item.convenio_id = int(convenio.id)
    item.convenio_source_id = int(convenio.source_id)
    item.prestador_id = int(prestador.id) if prestador else None
    item.prestador_source_id = int(prestador.source_id) if prestador else None
    esp_aux = _buscar_especialidade_aux(db, clinica_id, payload.especialidade_row_id, payload.especialidade)
    item.especialidade_row_id = int(esp_aux.id) if esp_aux else None
    item.especialidade = (
        _clean_text((esp_aux.descricao if esp_aux else payload.especialidade), 80)
        if (esp_aux or payload.especialidade)
        else None
    )
    item.procedimento_generico_id = int(procedimento_generico.id) if procedimento_generico else None
    item.procedimento_generico_nome = (
        _clean_text(procedimento_generico.descricao if procedimento_generico else None, 180)
        if procedimento_generico
        else None
    )
    tipo_codigo = _tipo_repasse_para_codigo(payload.tipo_repasse, payload.tipo_repasse_codigo)
    item.tipo_repasse_codigo = tipo_codigo
    item.tipo_repasse = _tipo_repasse_para_texto(payload.tipo_repasse, tipo_codigo)
    item.repasse = _clean_text(payload.repasse, 30)


def _sync_default_prestadores(db: Session, clinica_id: int) -> None:
    usuarios = (
        db.query(Usuario)
        .filter(Usuario.clinica_id == clinica_id)
        .order_by(Usuario.codigo.asc().nullslast(), Usuario.id.asc())
        .all()
    )
    existentes = db.query(PrestadorOdonto).filter(PrestadorOdonto.clinica_id == clinica_id).all()
    system_prestador_ids = {int(item.id) for item in existentes if is_system_prestador(item)}
    system_user_ids = {int(user.id) for user in usuarios if is_system_user(user)}
    by_usuario = {int(item.usuario_id): item for item in existentes if item.usuario_id}
    possui_nao_sistemicos = any(not is_system_prestador(item) for item in existentes)
    if possui_nao_sistemicos:
        # Prestadores ja foram definidos manualmente ou importados do Easy.
        # Para manter a logica do Easy, nao sincroniza automaticamente via usuarios.
        return
    permitir_criacao = True
    next_source = _proximo_source_id(db, PrestadorOdonto, clinica_id)
    next_codigo = 2
    for item in existentes:
        try:
            next_codigo = max(next_codigo, int(item.codigo or 0) + 1)
        except Exception:
            continue
    changed = False
    for user in usuarios:
        if int(user.id) in system_user_ids:
            continue
        tipo_usuario = str(getattr(user, "tipo_usuario", "") or "").strip()
        usuario_deve_virar_prestador = bool(getattr(user, "prestador_id", None)) or tipo_usuario in TIPOS_USUARIO_COM_PRESTADOR

        row = None
        if getattr(user, "prestador_id", None):
            row = next((item for item in existentes if int(item.id) == int(user.prestador_id)), None)
            if row and int(row.id) in system_prestador_ids:
                continue
            if row and row.usuario_id != int(user.id):
                row.usuario_id = int(user.id)
                changed = True
        if row is None:
            row = by_usuario.get(int(user.id))
            if row and int(row.id) in system_prestador_ids:
                continue
        if not usuario_deve_virar_prestador:
            if row and row.usuario_id == int(user.id):
                row.usuario_id = None
                changed = True
            continue
        if row is None:
            if not permitir_criacao:
                continue
            codigo = user.codigo if user.codigo is not None else next_codigo
            row = PrestadorOdonto(
                clinica_id=clinica_id,
                source_id=next_source,
                usuario_id=int(user.id),
                codigo=str(codigo).zfill(3),
                nome=(user.nome or user.email or f"Prestador {next_source}").strip(),
                tipo_prestador="Cirurgião dentista",
                executa_procedimento=True,
                inativo=not bool(user.ativo),
                email=(user.email or "").strip() or None,
                id_interno=str(user.id),
            )
            db.add(row)
            next_source += 1
            next_codigo = max(next_codigo, int(codigo) + 1)
            changed = True
            continue
        new_name = (user.nome or user.email or row.nome or "").strip()
        if new_name and row.nome != new_name:
            row.nome = new_name
            changed = True
        new_email = (user.email or "").strip() or None
        if (row.email or None) != new_email:
            row.email = new_email
            changed = True
        inativo = not bool(user.ativo)
        if bool(row.inativo) != inativo:
            row.inativo = inativo
            changed = True
        if not str(row.id_interno or "").strip():
            row.id_interno = str(user.id)
            changed = True
        apelido = (getattr(user, "apelido", None) or "").strip() or None
        if (row.apelido or None) != apelido:
            row.apelido = apelido
            changed = True
        if getattr(user, "prestador_id", None) and int(user.prestador_id) == int(row.id):
            if tipo_usuario and (row.tipo_prestador or "").strip() != tipo_usuario:
                row.tipo_prestador = tipo_usuario
                changed = True
    if changed:
        db.commit()


def _buscar_prestador_ou_none(db: Session, clinica_id: int, row_id: int | None) -> PrestadorOdonto | None:
    if not row_id or int(row_id) <= 0:
        return None
    item = (
        db.query(PrestadorOdonto)
        .filter(PrestadorOdonto.clinica_id == clinica_id, PrestadorOdonto.id == int(row_id))
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Prestador nao encontrado.")
    if is_system_prestador(item):
        return None
    return item


@router.get("")
def listar_prestadores(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)
    _ensure_tipos_prestador(db, clinica_id)
    _ensure_cbos_prestador(db, clinica_id)
    _sync_default_prestadores(db, clinica_id)
    rows = (
        db.query(PrestadorOdonto)
        .filter(PrestadorOdonto.clinica_id == clinica_id)
        .order_by(PrestadorOdonto.codigo.asc().nullslast(), PrestadorOdonto.nome.asc())
        .all()
    )
    persistidos = [_prestador_to_dict(item) for item in rows]
    sistema = [item for item in persistidos if bool(item.get("is_system_prestador"))]
    outros = [item for item in persistidos if not bool(item.get("is_system_prestador"))]
    itens = (sistema + outros) if sistema else ([_clinica_sintetica(current_user)] + outros)
    return {"itens": itens}


@router.get("/tipos")
def listar_tipos_prestador(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)
    rows = _ensure_tipos_prestador(db, clinica_id)
    _ensure_cbos_prestador(db, clinica_id)
    return [
        {
            "id": int(item.id),
            "codigo": (item.codigo or "").strip(),
            "descricao": (item.descricao or "").strip(),
        }
        for item in rows
    ]


@router.post("")
def criar_prestador(
    payload: PrestadorPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)
    item = PrestadorOdonto(
        clinica_id=clinica_id,
        source_id=_proximo_source_id(db, PrestadorOdonto, clinica_id),
    )
    _apply_prestador_payload(item, payload)
    if not item.data_inclusao:
        item.data_inclusao = item.data_alteracao or None
    db.add(item)
    db.commit()
    db.refresh(item)
    return _prestador_to_dict(item)


@router.put("/{row_id}")
def alterar_prestador(
    row_id: int,
    payload: PrestadorPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if int(row_id) <= 0:
        raise HTTPException(status_code=400, detail="Prestador invalido.")
    item = _buscar_prestador_ou_none(db, int(current_user.clinica_id), row_id)
    if item is None:
        raise HTTPException(status_code=400, detail="A conta Clinica nao pode ser alterada por aqui.")
    _apply_prestador_payload(item, payload)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _prestador_to_dict(item)


@router.delete("/{row_id}")
def excluir_prestador(
    row_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _buscar_prestador_ou_none(db, int(current_user.clinica_id), row_id)
    if item is None:
        raise HTTPException(status_code=400, detail="A conta Clinica nao pode ser eliminada.")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/credenciamentos")
def listar_credenciamentos(
    convenio_row_id: int | None = None,
    prestador_row_id: int | None = None,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)
    query = db.query(PrestadorCredenciamentoOdonto).filter(PrestadorCredenciamentoOdonto.clinica_id == clinica_id)
    if convenio_row_id and int(convenio_row_id) > 0:
        query = query.filter(PrestadorCredenciamentoOdonto.convenio_id == int(convenio_row_id))
    if prestador_row_id is not None:
        if int(prestador_row_id) <= 0:
            query = query.filter(PrestadorCredenciamentoOdonto.prestador_id.is_(None))
        else:
            query = query.filter(PrestadorCredenciamentoOdonto.prestador_id == int(prestador_row_id))
    rows = query.order_by(PrestadorCredenciamentoOdonto.codigo.asc().nullslast(), PrestadorCredenciamentoOdonto.id.asc()).all()
    return {"itens": [_credenciamento_to_dict(item) for item in rows]}


@router.post("/credenciamentos")
def criar_credenciamento(
    payload: CredenciamentoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)
    convenio = (
        db.query(ConvenioOdonto)
        .filter(ConvenioOdonto.clinica_id == clinica_id, ConvenioOdonto.id == int(payload.convenio_row_id))
        .first()
    )
    if not convenio:
        raise HTTPException(status_code=404, detail="Convenio nao encontrado.")
    prestador = _buscar_prestador_ou_none(db, clinica_id, payload.prestador_row_id)
    item = PrestadorCredenciamentoOdonto(
        clinica_id=clinica_id,
        source_id=_proximo_source_id(db, PrestadorCredenciamentoOdonto, clinica_id),
        data_inclusao=_today_br_date(),
        data_alteracao=_today_br_date(),
    )
    _apply_credenciamento_payload(item, payload, convenio, prestador)
    if not str(item.data_inclusao or "").strip():
        item.data_inclusao = _today_br_date()
    item.data_alteracao = _today_br_date()
    db.add(item)
    db.commit()
    db.refresh(item)
    return _credenciamento_to_dict(item)


@router.put("/credenciamentos/{row_id}")
def alterar_credenciamento(
    row_id: int,
    payload: CredenciamentoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)
    item = (
        db.query(PrestadorCredenciamentoOdonto)
        .filter(PrestadorCredenciamentoOdonto.clinica_id == clinica_id, PrestadorCredenciamentoOdonto.id == int(row_id))
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Credenciamento nao encontrado.")
    convenio = (
        db.query(ConvenioOdonto)
        .filter(ConvenioOdonto.clinica_id == clinica_id, ConvenioOdonto.id == int(payload.convenio_row_id))
        .first()
    )
    if not convenio:
        raise HTTPException(status_code=404, detail="Convenio nao encontrado.")
    prestador = _buscar_prestador_ou_none(db, clinica_id, payload.prestador_row_id)
    _apply_credenciamento_payload(item, payload, convenio, prestador)
    item.data_alteracao = _today_br_date()
    db.add(item)
    db.commit()
    db.refresh(item)
    return _credenciamento_to_dict(item)


@router.delete("/credenciamentos/{row_id}")
def excluir_credenciamento(
    row_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(PrestadorCredenciamentoOdonto)
        .filter(
            PrestadorCredenciamentoOdonto.clinica_id == int(current_user.clinica_id),
            PrestadorCredenciamentoOdonto.id == int(row_id),
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Credenciamento nao encontrado.")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/comissoes")
def listar_comissoes(
    convenio_row_id: int | None = None,
    prestador_row_id: int | None = None,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)
    query = db.query(PrestadorComissaoOdonto).filter(PrestadorComissaoOdonto.clinica_id == clinica_id)
    if convenio_row_id and int(convenio_row_id) > 0:
        query = query.filter(PrestadorComissaoOdonto.convenio_id == int(convenio_row_id))
    if prestador_row_id is not None:
        if int(prestador_row_id) <= 0:
            query = query.filter(PrestadorComissaoOdonto.prestador_id.is_(None))
        else:
            query = query.filter(PrestadorComissaoOdonto.prestador_id == int(prestador_row_id))
    rows = query.order_by(PrestadorComissaoOdonto.vigencia.asc().nullslast(), PrestadorComissaoOdonto.id.asc()).all()
    return {"itens": [_comissao_to_dict(item) for item in rows]}


@router.post("/comissoes")
def criar_comissao(
    payload: ComissaoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)
    convenio = (
        db.query(ConvenioOdonto)
        .filter(ConvenioOdonto.clinica_id == clinica_id, ConvenioOdonto.id == int(payload.convenio_row_id))
        .first()
    )
    if not convenio:
        raise HTTPException(status_code=404, detail="Convenio nao encontrado.")
    prestador = _buscar_prestador_ou_none(db, clinica_id, payload.prestador_row_id)
    procedimento_generico = None
    if payload.procedimento_generico_id:
        procedimento_generico = (
            db.query(ProcedimentoGenerico)
            .filter(
                ProcedimentoGenerico.clinica_id == clinica_id,
                ProcedimentoGenerico.id == int(payload.procedimento_generico_id),
            )
            .first()
        )
        if not procedimento_generico:
            raise HTTPException(status_code=404, detail="Procedimento generico nao encontrado.")
    item = PrestadorComissaoOdonto(
        clinica_id=clinica_id,
        source_id=_proximo_source_id(db, PrestadorComissaoOdonto, clinica_id),
        data_inclusao=_clean_br_date(payload.vigencia) if str(payload.vigencia or "").strip() else None,
    )
    _apply_comissao_payload(item, db, clinica_id, payload, convenio, prestador, procedimento_generico)
    if not item.data_inclusao:
        item.data_inclusao = item.vigencia
    item.data_alteracao = item.vigencia
    db.add(item)
    db.commit()
    db.refresh(item)
    return _comissao_to_dict(item)


@router.put("/comissoes/{row_id}")
def alterar_comissao(
    row_id: int,
    payload: ComissaoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)
    item = (
        db.query(PrestadorComissaoOdonto)
        .filter(PrestadorComissaoOdonto.clinica_id == clinica_id, PrestadorComissaoOdonto.id == int(row_id))
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Fator de comissao nao encontrado.")
    convenio = (
        db.query(ConvenioOdonto)
        .filter(ConvenioOdonto.clinica_id == clinica_id, ConvenioOdonto.id == int(payload.convenio_row_id))
        .first()
    )
    if not convenio:
        raise HTTPException(status_code=404, detail="Convenio nao encontrado.")
    prestador = _buscar_prestador_ou_none(db, clinica_id, payload.prestador_row_id)
    procedimento_generico = None
    if payload.procedimento_generico_id:
        procedimento_generico = (
            db.query(ProcedimentoGenerico)
            .filter(
                ProcedimentoGenerico.clinica_id == clinica_id,
                ProcedimentoGenerico.id == int(payload.procedimento_generico_id),
            )
            .first()
        )
        if not procedimento_generico:
            raise HTTPException(status_code=404, detail="Procedimento generico nao encontrado.")
    _apply_comissao_payload(item, db, clinica_id, payload, convenio, prestador, procedimento_generico)
    item.data_alteracao = item.vigencia or item.data_alteracao
    db.add(item)
    db.commit()
    db.refresh(item)
    return _comissao_to_dict(item)


@router.delete("/comissoes/{row_id}")
def excluir_comissao(
    row_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(PrestadorComissaoOdonto)
        .filter(
            PrestadorComissaoOdonto.clinica_id == int(current_user.clinica_id),
            PrestadorComissaoOdonto.id == int(row_id),
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Fator de comissao nao encontrado.")
    db.delete(item)
    db.commit()
    return {"ok": True}
