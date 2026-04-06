import re
import unicodedata
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models.clinica import Clinica
from models.convenio_odonto import ConvenioOdonto
from models.financeiro import ItemAuxiliar
from models.paciente import Paciente
from models.procedimento_tabela import ProcedimentoTabela
from models.tiss_tipo_tabela import TissTipoTabela
from models.tratamento import Tratamento
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access
from services.indices_service import (
    DEFAULT_INDICE_NUMERO,
    dados_indice_por_numero,
    listar_indices,
    resolver_numero_indice,
)

router = APIRouter(
    prefix="/tratamentos",
    tags=["tratamentos"],
    dependencies=[Depends(require_module_access("procedimentos"))],
)


SITUACOES_PADRAO = ["Aberto", "Finalizado", "Cancelado"]
ARCADAS_PADRAO = ["Permanente", "Decidua", "Mista"]
SINAIS_PADRAO = [
    {"id": 3, "nome": "<<Nao avaliado>>"},
    {"id": 1, "nome": "Sim"},
    {"id": 2, "nome": "Nao"},
]


class NovoTratamentoPayload(BaseModel):
    paciente_id: int
    data_inicio: str | None = None
    data_finalizacao: str | None = None
    situacao: str | None = None

    tabela_codigo: int | str | None = None
    indice: int | str | None = None

    cirurgiao_responsavel_id: int | None = None
    unidade_atendimento: str | None = None
    observacoes: str | None = None

    arcada_predominante: str | None = None
    copiar_de: str | None = None
    copiar_intervencoes: bool = False

    convenio_nome: str | None = None
    id_convenio: int | None = None
    tipo_atendimento_tiss_id: int | str | None = None

    cirurgiao_contratado_id: int | None = None
    cirurgiao_solicitante_id: int | None = None
    cirurgiao_executante_id: int | None = None

    sinais_doenca_periodontal: int | str | None = None
    alteracao_tecidos: int | str | None = None
    numero_guia: str | None = None
    data_autorizacao: str | None = None
    senha_autorizacao: str | None = None
    validade_senha: str | None = None

    extra: dict[str, Any] = Field(default_factory=dict)


def _norm(texto: str) -> str:
    base = (texto or "").strip().lower()
    base = unicodedata.normalize("NFD", base)
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def _clean_text(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _clean_int(value: int | str | None) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if not re.match(r"^-?\d+$", text):
        return None
    try:
        return int(text)
    except Exception:
        return None


def _clean_date(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", text)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m2 = re.match(r"^(\d{4})-(\d{2})-(\d{2}).*$", text)
    if m2:
        return f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)}"
    return None


def _iso_to_br(value: str | None) -> str:
    iso = _clean_date(value)
    if not iso:
        return ""
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


def _idade_texto(data_nascimento: str | None) -> str:
    iso = _clean_date(data_nascimento)
    if not iso:
        return "?"
    try:
        nasc = datetime.strptime(iso, "%Y-%m-%d").date()
    except Exception:
        return "?"
    hoje = date.today()
    if nasc > hoje:
        return "?"
    anos = hoje.year - nasc.year
    meses = hoje.month - nasc.month
    if hoje.day < nasc.day:
        meses -= 1
    if meses < 0:
        anos -= 1
        meses += 12
    if anos < 0:
        return "?"
    return f"{anos}a {meses}m"


def _paciente_or_404(db: Session, clinica_id: int, paciente_id: int) -> Paciente:
    paciente = (
        db.query(Paciente)
        .filter(
            Paciente.id == int(paciente_id),
            Paciente.clinica_id == clinica_id,
        )
        .first()
    )
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente nao encontrado.")
    return paciente


def _listar_indices(db: Session, clinica_id: int) -> list[dict]:
    return listar_indices(db, clinica_id, include_inativos=True)


def _resolver_indice(db: Session, clinica_id: int, valor: int | str | None, default: int = DEFAULT_INDICE_NUMERO) -> int:
    return resolver_numero_indice(db, clinica_id, valor, default=default)


def _listar_tabelas(db: Session, clinica_id: int) -> list[dict]:
    tabelas = (
        db.query(ProcedimentoTabela)
        .filter(ProcedimentoTabela.clinica_id == clinica_id)
        .order_by(ProcedimentoTabela.codigo.asc())
        .all()
    )
    payload: list[dict] = []
    for t in tabelas:
        indice_id = _resolver_indice(db, current_user.clinica_id, t.nro_indice, DEFAULT_INDICE_NUMERO)
        indice_item = dados_indice_por_numero(db, current_user.clinica_id, indice_id)
        payload.append(
            {
                "id": int(t.codigo or 0),
                "nome": (t.nome or "").strip() or f"Tabela {int(t.codigo or 0)}",
                "indice_id": int(indice_id),
                "indice_sigla": str(indice_item["sigla"]),
            }
        )
    return payload


def _resolver_tabela_codigo(valor: int | str | None, tabelas: list[dict], default: int = 1) -> int:
    numero = _clean_int(valor)
    if numero and any(int(x["id"]) == int(numero) for x in tabelas):
        return int(numero)
    if any(int(x["id"]) == int(default) for x in tabelas):
        return int(default)
    if tabelas:
        return int(tabelas[0]["id"])
    return int(default)


def _listar_tipos_tiss(db: Session) -> list[dict]:
    rows = (
        db.query(TissTipoTabela)
        .filter(TissTipoTabela.ativo.is_(True))
        .order_by(TissTipoTabela.id.asc())
        .all()
    )
    if not rows:
        rows = db.query(TissTipoTabela).order_by(TissTipoTabela.id.asc()).all()
    if not rows:
        return [{"id": 1, "codigo": "00", "nome": "Outras Tabelas"}]
    return [
        {
            "id": int(x.id),
            "codigo": (x.codigo or "").strip(),
            "nome": (x.nome or "").strip(),
        }
        for x in rows
    ]


def _listar_cirurgioes(db: Session, clinica_id: int) -> list[dict]:
    usuarios = (
        db.query(Usuario)
        .filter(
            Usuario.clinica_id == clinica_id,
            Usuario.ativo.is_(True),
        )
        .order_by(func.lower(Usuario.nome).asc(), Usuario.id.asc())
        .all()
    )
    return [
        {
            "id": int(u.id),
            "codigo": int(u.codigo or u.id),
            "nome": (u.nome or "").strip(),
        }
        for u in usuarios
    ]


def _listar_unidades(db: Session, clinica_id: int, clinica_nome: str) -> list[dict]:
    unidades = (
        db.query(ItemAuxiliar)
        .filter(
            ItemAuxiliar.clinica_id == clinica_id,
            ItemAuxiliar.tipo.ilike("Unidade de atendimento"),
        )
        .order_by(ItemAuxiliar.descricao.asc())
        .all()
    )
    nomes: list[str] = []
    vistos: set[str] = set()
    for item in unidades:
        nome = (item.descricao or "").strip()
        chave = _norm(nome)
        if not nome or not chave or chave in vistos:
            continue
        vistos.add(chave)
        nomes.append(nome)
    if not nomes:
        fallback = (clinica_nome or "").strip() or "Unidade principal"
        nomes = [fallback]
    return [{"id": idx + 1, "nome": nome} for idx, nome in enumerate(nomes)]


def _listar_convenios(db: Session, clinica_id: int, paciente: Paciente) -> list[dict]:
    out: list[dict] = [{"id": "particular", "nome": "Particular"}]
    vistos: set[str] = {"particular|particular"}

    def _add(conv_id: str | int | None, nome: str):
        nome_txt = (nome or "").strip()
        if not nome_txt:
            return
        id_txt = str(conv_id if conv_id is not None else nome_txt).strip()
        chave = f"{id_txt.lower()}|{_norm(nome_txt)}"
        if chave in vistos:
            return
        vistos.add(chave)
        out.append({"id": id_txt, "nome": nome_txt})

    convenios = (
        db.query(ConvenioOdonto)
        .filter(ConvenioOdonto.clinica_id == clinica_id)
        .order_by(ConvenioOdonto.inativo.asc(), ConvenioOdonto.nome.asc(), ConvenioOdonto.id.asc())
        .all()
    )
    for item in convenios:
        _add(int(item.source_id), (item.nome or "").strip())

    if paciente.id_convenio is not None:
        _add(int(paciente.id_convenio), f"Convenio {int(paciente.id_convenio)}")
    extra = dict(paciente.source_payload or {})
    conv_nome = str(extra.get("convenio_nome") or "").strip()
    if conv_nome:
        _add(conv_nome, conv_nome)

    nomes_tra = (
        db.query(Tratamento.convenio_nome)
        .filter(
            Tratamento.clinica_id == clinica_id,
            Tratamento.convenio_nome.isnot(None),
        )
        .distinct()
        .all()
    )
    for (nome,) in nomes_tra:
        nome_txt = str(nome or "").strip()
        if nome_txt:
            _add(nome_txt, nome_txt)
    return out


def _listar_tratamentos_anteriores(db: Session, clinica_id: int, paciente_id: int) -> list[dict]:
    rows = (
        db.query(Tratamento)
        .filter(
            Tratamento.clinica_id == clinica_id,
            Tratamento.paciente_id == paciente_id,
        )
        .order_by(Tratamento.nrotra.desc(), Tratamento.id.desc())
        .limit(80)
        .all()
    )
    out = [{"id": "", "nome": "Copiar do tratamento anterior"}]
    for item in rows:
        dt = _iso_to_br(item.data_inicio)
        sufixo = f" ({dt})" if dt else ""
        out.append(
            {
                "id": str(int(item.id)),
                "nome": f"Tratamento {int(item.nrotra or 0)}{sufixo}",
            }
        )
    return out


def _resolver_usuario_id(db: Session, clinica_id: int, usuario_id: int | None) -> int | None:
    uid = _clean_int(usuario_id)
    if not uid:
        return None
    existe = (
        db.query(Usuario.id)
        .filter(
            Usuario.id == int(uid),
            Usuario.clinica_id == clinica_id,
        )
        .first()
    )
    return int(uid) if existe else None


def _resolver_tiss_id(db: Session, valor: int | str | None, default: int = 1) -> int:
    tipo_id = _clean_int(valor)
    if not tipo_id:
        return int(default)
    existe = db.query(TissTipoTabela.id).filter(TissTipoTabela.id == int(tipo_id)).first()
    return int(tipo_id) if existe else int(default)


def _resolver_sinal(valor: int | str | None, default: int = 3) -> int:
    numero = _clean_int(valor)
    if numero in {1, 2, 3}:
        return int(numero)
    return int(default)


def _nome_usuario_por_id(cirurgioes: list[dict], usuario_id: int | None) -> str | None:
    if not usuario_id:
        return None
    alvo = int(usuario_id)
    row = next((x for x in cirurgioes if int(x["id"]) == alvo), None)
    return str(row["nome"]).strip() if row else None


def _tratamento_to_dict(item: Tratamento) -> dict[str, Any]:
    return {
        "id": int(item.id),
        "paciente_id": int(item.paciente_id),
        "nrotra": int(item.nrotra or 0),
        "data_inicio": item.data_inicio or "",
        "data_finalizacao": item.data_finalizacao or "",
        "situacao": item.situacao or "",
        "tabela_codigo": int(item.tabela_codigo or 1),
        "indice": int(item.indice or 255),
        "cirurgiao_responsavel_id": item.cirurgiao_responsavel_id,
        "cirurgiao_responsavel_nome": item.cirurgiao_responsavel_nome or "",
        "unidade_atendimento": item.unidade_atendimento or "",
        "observacoes": item.observacoes or "",
        "arcada_predominante": item.arcada_predominante or "",
        "copiar_de": item.copiar_de or "",
        "copiar_intervencoes": bool(item.copiar_intervencoes),
        "convenio_nome": item.convenio_nome or "",
        "id_convenio": item.id_convenio,
        "tipo_atendimento_tiss_id": item.tipo_atendimento_tiss_id,
        "tipo_atendimento_tiss_nome": item.tipo_atendimento_tiss_nome or "",
        "cirurgiao_contratado_id": item.cirurgiao_contratado_id,
        "cirurgiao_solicitante_id": item.cirurgiao_solicitante_id,
        "cirurgiao_executante_id": item.cirurgiao_executante_id,
        "sinais_doenca_periodontal": int(item.sinais_doenca_periodontal or 3),
        "alteracao_tecidos": int(item.alteracao_tecidos or 3),
        "numero_guia": item.numero_guia or "",
        "data_autorizacao": item.data_autorizacao or "",
        "senha_autorizacao": item.senha_autorizacao or "",
        "validade_senha": item.validade_senha or "",
        "criado_em": item.criado_em.isoformat() if item.criado_em else None,
        "atualizado_em": item.atualizado_em.isoformat() if item.atualizado_em else None,
    }


@router.get("/paciente/{paciente_id}")
def listar_tratamentos_paciente(
    paciente_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = current_user.clinica_id
    pid = int(paciente_id or 0)
    if pid <= 0:
        raise HTTPException(status_code=400, detail="Paciente invalido.")
    _paciente_or_404(db, clinica_id, pid)

    tabelas_rows = (
        db.query(ProcedimentoTabela)
        .filter(ProcedimentoTabela.clinica_id == clinica_id)
        .order_by(ProcedimentoTabela.codigo.asc())
        .all()
    )
    tabelas_map: dict[int, str] = {}
    for row in tabelas_rows:
        codigo = int(row.codigo or 0)
        if codigo <= 0:
            continue
        tabelas_map[codigo] = (row.nome or "").strip() or f"Tabela {codigo}"

    rows = (
        db.query(Tratamento)
        .filter(
            Tratamento.clinica_id == clinica_id,
            Tratamento.paciente_id == pid,
        )
        .order_by(Tratamento.nrotra.desc(), Tratamento.id.desc())
        .limit(500)
        .all()
    )

    tratamentos: list[dict[str, Any]] = []
    for item in rows:
        tabela_codigo = int(item.tabela_codigo or 1)
        tabela_nome = tabelas_map.get(tabela_codigo) or f"Tabela {tabela_codigo}"
        indice_id = _resolver_indice(db, current_user.clinica_id, item.indice, default=DEFAULT_INDICE_NUMERO)
        indice_item = dados_indice_por_numero(db, current_user.clinica_id, indice_id)
        data_inicio_br = _iso_to_br(item.data_inicio)
        data_finalizacao_br = _iso_to_br(item.data_finalizacao)

        rotulo = f"Tratamento {int(item.nrotra or 0)}"
        if data_inicio_br:
            rotulo += f" ({data_inicio_br})"
        if item.situacao:
            rotulo += f" - {item.situacao}"

        tratamentos.append(
            {
                "id": int(item.id),
                "nrotra": int(item.nrotra or 0),
                "rotulo": rotulo,
                "data_inicio": item.data_inicio or "",
                "data_inicio_br": data_inicio_br,
                "data_finalizacao": item.data_finalizacao or "",
                "data_finalizacao_br": data_finalizacao_br,
                "situacao": item.situacao or "",
                "tabela_codigo": tabela_codigo,
                "tabela_nome": tabela_nome,
                "indice": int(indice_id),
                "indice_sigla": str(indice_item["sigla"]),
                "cirurgiao_responsavel_nome": item.cirurgiao_responsavel_nome or "",
                "unidade_atendimento": item.unidade_atendimento or "",
                "observacoes": item.observacoes or "",
            }
        )

    return {
        "paciente_id": pid,
        "total": len(tratamentos),
        "selecionado_id": int(tratamentos[0]["id"]) if tratamentos else None,
        "tratamentos": tratamentos,
    }


@router.get("/novo/combos")
def carregar_combos_novo_tratamento(
    paciente_id: int = Query(default=0),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pid = int(paciente_id or 0)
    if pid <= 0:
        raise HTTPException(status_code=400, detail="Selecione um paciente para iniciar tratamento.")

    clinica_id = current_user.clinica_id
    paciente = _paciente_or_404(db, clinica_id, pid)
    clinica = db.query(Clinica).filter(Clinica.id == clinica_id).first()
    clinica_nome = (clinica.nome if clinica else "") or ""

    tabelas = _listar_tabelas(db, clinica_id)
    tabela_default = _resolver_tabela_codigo(paciente.tabela_codigo, tabelas, default=1)
    tabela_sel = next((x for x in tabelas if int(x["id"]) == tabela_default), None)
    indice_default = int(tabela_sel["indice_id"]) if tabela_sel else DEFAULT_INDICE_NUMERO

    cirurgioes = _listar_cirurgioes(db, clinica_id)
    cirurgiao_default_id = int(current_user.id)
    if not any(int(x["id"]) == cirurgiao_default_id for x in cirurgioes):
        cirurgiao_default_id = int(cirurgioes[0]["id"]) if cirurgioes else 0

    tipos_tiss = _listar_tipos_tiss(db)
    tipo_tiss_default = int(tipos_tiss[0]["id"]) if tipos_tiss else 1

    convenios = _listar_convenios(db, clinica_id, paciente)
    convenio_default = "particular"
    if paciente.id_convenio is not None:
        convenio_default = str(int(paciente.id_convenio))
    else:
        conv_extra = str(dict(paciente.source_payload or {}).get("convenio_nome") or "").strip()
        if conv_extra:
            convenio_default = conv_extra

    hoje_iso = date.today().isoformat()
    return {
        "paciente_id": int(paciente.id),
        "tabelas": tabelas,
        "indices": _listar_indices(db, current_user.clinica_id),
        "situacoes": [{"id": x, "nome": x} for x in SITUACOES_PADRAO],
        "arcadas": [{"id": x, "nome": x} for x in ARCADAS_PADRAO],
        "cirurgioes": cirurgioes,
        "unidades": _listar_unidades(db, clinica_id, clinica_nome),
        "convenios": convenios,
        "tipos_tiss": tipos_tiss,
        "sinais": [dict(x) for x in SINAIS_PADRAO],
        "tecidos": [dict(x) for x in SINAIS_PADRAO],
        "copias_tratamento": _listar_tratamentos_anteriores(db, clinica_id, int(paciente.id)),
        "defaults": {
            "data_inicio": hoje_iso,
            "data_finalizacao": "",
            "situacao": "Aberto",
            "tabela_codigo": int(tabela_default),
            "indice": int(indice_default),
            "cirurgiao_responsavel_id": int(cirurgiao_default_id or 0),
            "unidade_atendimento": (clinica_nome or "Unidade principal"),
            "tipo_atendimento_tiss_id": int(tipo_tiss_default),
            "convenio": convenio_default,
            "sinais_doenca_periodontal": 3,
            "alteracao_tecidos": 3,
            "idade_texto": _idade_texto(paciente.data_nascimento),
            "inclusao": hoje_iso,
            "alteracao": hoje_iso,
        },
    }


@router.post("/novo")
def salvar_novo_tratamento(
    payload: NovoTratamentoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = current_user.clinica_id
    paciente = _paciente_or_404(db, clinica_id, int(payload.paciente_id))

    tabelas = _listar_tabelas(db, clinica_id)
    tabela_codigo = _resolver_tabela_codigo(payload.tabela_codigo, tabelas, default=int(paciente.tabela_codigo or 1))
    tabela_sel = next((x for x in tabelas if int(x["id"]) == tabela_codigo), None)
    indice_default = int(tabela_sel["indice_id"]) if tabela_sel else DEFAULT_INDICE_NUMERO
    indice = _resolver_indice(db, current_user.clinica_id, payload.indice, default=indice_default)

    data_inicio = _clean_date(payload.data_inicio) or date.today().isoformat()
    data_finalizacao = _clean_date(payload.data_finalizacao)
    data_autorizacao = _clean_date(payload.data_autorizacao)
    validade_senha = _clean_date(payload.validade_senha)
    situacao = _clean_text(payload.situacao) or "Aberto"

    cirurgioes = _listar_cirurgioes(db, clinica_id)

    cir_resp = _resolver_usuario_id(db, clinica_id, payload.cirurgiao_responsavel_id)
    cir_con = _resolver_usuario_id(db, clinica_id, payload.cirurgiao_contratado_id)
    cir_sol = _resolver_usuario_id(db, clinica_id, payload.cirurgiao_solicitante_id)
    cir_exe = _resolver_usuario_id(db, clinica_id, payload.cirurgiao_executante_id)

    convenio_nome = _clean_text(payload.convenio_nome)
    id_convenio = _clean_int(payload.id_convenio)
    tipo_tiss = _resolver_tiss_id(db, payload.tipo_atendimento_tiss_id, default=1)
    tipo_tiss_row = db.query(TissTipoTabela).filter(TissTipoTabela.id == tipo_tiss).first()
    tipo_tiss_nome = (tipo_tiss_row.nome or "").strip() if tipo_tiss_row else ""

    max_nro = (
        db.query(func.max(Tratamento.nrotra))
        .filter(
            Tratamento.clinica_id == clinica_id,
            Tratamento.paciente_id == int(paciente.id),
        )
        .scalar()
    )
    nrotra = int(max_nro or 0) + 1

    item = Tratamento(
        clinica_id=clinica_id,
        paciente_id=int(paciente.id),
        nrotra=nrotra,
        data_inicio=data_inicio,
        data_finalizacao=data_finalizacao,
        situacao=situacao,
        tabela_codigo=tabela_codigo,
        indice=indice,
        cirurgiao_responsavel_id=cir_resp,
        cirurgiao_responsavel_nome=_nome_usuario_por_id(cirurgioes, cir_resp),
        unidade_atendimento=_clean_text(payload.unidade_atendimento),
        observacoes=_clean_text(payload.observacoes),
        arcada_predominante=_clean_text(payload.arcada_predominante),
        copiar_de=_clean_text(payload.copiar_de),
        copiar_intervencoes=bool(payload.copiar_intervencoes),
        convenio_nome=convenio_nome,
        id_convenio=id_convenio,
        tipo_atendimento_tiss_id=tipo_tiss,
        tipo_atendimento_tiss_nome=tipo_tiss_nome or None,
        cirurgiao_contratado_id=cir_con,
        cirurgiao_contratado_nome=_nome_usuario_por_id(cirurgioes, cir_con),
        cirurgiao_solicitante_id=cir_sol,
        cirurgiao_solicitante_nome=_nome_usuario_por_id(cirurgioes, cir_sol),
        cirurgiao_executante_id=cir_exe,
        cirurgiao_executante_nome=_nome_usuario_por_id(cirurgioes, cir_exe),
        sinais_doenca_periodontal=_resolver_sinal(payload.sinais_doenca_periodontal, default=3),
        alteracao_tecidos=_resolver_sinal(payload.alteracao_tecidos, default=3),
        numero_guia=_clean_text(payload.numero_guia),
        data_autorizacao=data_autorizacao,
        senha_autorizacao=_clean_text(payload.senha_autorizacao),
        validade_senha=validade_senha,
        source_payload=payload.extra if isinstance(payload.extra, dict) else None,
    )
    db.add(item)
    db.flush()

    paciente.tabela_codigo = int(tabela_codigo)
    if id_convenio is not None:
        paciente.id_convenio = int(id_convenio)
    elif not convenio_nome:
        paciente.id_convenio = None

    extra_paciente = dict(paciente.source_payload or {})
    if convenio_nome:
        extra_paciente["convenio_nome"] = convenio_nome
    else:
        extra_paciente.pop("convenio_nome", None)
    if item.id:
        extra_paciente["ultimo_tratamento_id"] = int(item.id)
    extra_paciente["ultimo_tratamento_nrotra"] = int(item.nrotra or 0)
    extra_paciente["ultimo_tratamento_situacao"] = item.situacao or ""
    extra_paciente["ultimo_tratamento_data_inicio"] = item.data_inicio or ""
    paciente.source_payload = extra_paciente or None

    db.commit()
    db.refresh(item)

    return {
        "detail": "Tratamento cadastrado com sucesso.",
        "tratamento": _tratamento_to_dict(item),
    }
