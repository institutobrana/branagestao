import json
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models.convenio_odonto import ConvenioOdonto
from models.financeiro import ItemAuxiliar
from models.modelo_documento import ModeloDocumento
from models.procedimento_tabela import ProcedimentoTabela
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access
from security.system_accounts import is_system_user

router = APIRouter(
    prefix="/preferences",
    tags=["preferences"],
    dependencies=[Depends(require_module_access("configuracao"))],
)

PESQUISA_PADRAO_ODONTOGRAMA = [
    {"id": "geral", "label": "Geral"},
    {"id": "codigo", "label": "Codigo"},
    {"id": "nome", "label": "Nome"},
]

PREFERENCIAS_GERAL_PADRAO = {
    "pesquisa_padrao_odontograma": "geral",
    "tabela_padrao_id": None,
    "convenio_padrao_id": 0,
    "mensagem_padrao_orcamentos": "",
    "historico_padrao_conta_corrente": "Honorarios odontologicos",
    "exibir_quadro_avisos": True,
    "busca_automatica_pacientes_agendados": True,
    "alarme_habilitado": False,
    "alarme_minutos_antecedencia": 1,
}

PREFERENCIAS_MODELOS_PADRAO = {
    "modelo_impresso_atestados_id": None,
    "modelo_impresso_receitas_id": None,
    "modelo_impresso_recibos_id": None,
    "modelo_padrao_etiquetas_id": None,
    "modelo_texto_email_agenda_id": None,
    "modelo_padrao_orcamentos_id": None,
    "modelo_texto_whatsapp_agenda_id": None,
}

AMBIENTE_FONTES = [
    "Tahoma",
    "Segoe UI",
    "Arial",
    "Verdana",
    "Trebuchet MS",
    "Georgia",
    "Times New Roman",
    "Courier New",
]

AMBIENTE_SECOES = [
    {"id": "enunciados", "label": "Enunciados"},
    {"id": "campos_edicao", "label": "Campos de edicao"},
    {"id": "botoes_funcao", "label": "Botoes de funcao"},
    {"id": "outros_botoes", "label": "Outros botoes"},
    {"id": "itens_lista", "label": "Itens de lista"},
]

AMBIENTE_ESTILO_PADRAO = {
    "fonte_nome": "Tahoma",
    "fonte_tamanho": 12,
    "fonte_estilo": "normal",
    "cor_texto": "#000000",
    "riscado": False,
    "sublinhado": False,
    "script": "Ocidental",
}

AMBIENTE_FONT_STYLES = [
    {"id": "normal", "label": "Normal"},
    {"id": "negrito", "label": "Negrito"},
    {"id": "italico", "label": "Italico"},
    {"id": "negrito-italico", "label": "Italico e negrito"},
]

PREFERENCIAS_AMBIENTE_PADRAO = {
    "secao_ativa": "enunciados",
    "secoes": {item["id"]: dict(AMBIENTE_ESTILO_PADRAO) for item in AMBIENTE_SECOES},
}

# Observacao: os filtros abaixo reproduzem o combo do EasyDental e devem ser
# reutilizados no futuro modulo Odontograma. "no tratamento" filtra pelas
# intervencoes do tratamento ativo, enquanto as opcoes sem esse sufixo filtram
# pelo odontograma/arcada. "caracteristicas_arcada" limita as anomalias.
ODONTOGRAMA_FILTROS_PADRAO = [
    {"id": "todas_tratamento", "label": "Todas as intervenções no tratamento"},
    {"id": "condicao_observada", "label": "Condição observada"},
    {"id": "ja_realizado", "label": "Já realizado"},
    {"id": "a_realizar", "label": "A realizar"},
    {"id": "todas_intervencoes", "label": "Todas as intervenções"},
    {"id": "condicao_tratamento", "label": "Condição observada no tratamento"},
    {"id": "ja_realizado_tratamento", "label": "Já realizado no tratamento"},
    {"id": "a_realizar_tratamento", "label": "A realizar no tratamento"},
    {"id": "caracteristicas_arcada", "label": "Características da arcada"},
]

ODONTOGRAMA_ESPECIALIDADES_PADRAO = [
    {"id": "clinica", "label": "Gerais"},
    {"id": "dentistica", "label": "Dentística"},
    {"id": "endodontia", "label": "Endodontia"},
    {"id": "periodontia", "label": "Periodontia"},
    {"id": "ortodontia", "label": "Ortodontia"},
    {"id": "protese", "label": "Prótese"},
    {"id": "implantodontia", "label": "Implantodontia"},
    {"id": "anomalias", "label": "Características e anomalias"},
]

PREFERENCIAS_ODONTOGRAMA_PADRAO = {
    "especialidade_mais_utilizada": "clinica",
    "filtro_mais_utilizado": "todos",
    "exibir_alerta_anamnese": True,
    "exibir_icones_alerta": True,
    "exibir_imagens_easycapture": True,
    "exibir_coluna_cirurgiao_historico": False,
    "exibir_historico_ordem_decrescente": True,
    "exibir_dados_paciente": True,
    "exibir_dados_tratamento": True,
    "exibir_observacoes": True,
    "exibir_documentos": True,
    "exibir_agenda_dia": True,
    "cor_a_realizar": "#ff0000",
    "cor_realizado": "#0000ff",
    "cor_condicao_observada": "#008000",
    "cor_anomalia": "#000000",
}

REPORT_SECOES = ["titulo", "cabecalho", "colunas", "corpo", "rodape"]

REPORT_SECAO_PADRAO = {
    "fontFamily": "Tahoma",
    "fontSize": 10,
    "bold": False,
    "italic": False,
    "underline": False,
    "strike": False,
    "color": "#111111",
}

REPORT_CONFIG_PADRAO = {
    "headerText": "",
    "printLogo": True,
    "logoPath": r"C:\EDS70\Textos\CABECALHO.bmp",
    "logoDataUrl": "",
    "printUser": False,
    "printPage": True,
    "printDateTime": True,
    "sectionId": "titulo",
    "sectionStyles": {sec: dict(REPORT_SECAO_PADRAO) for sec in REPORT_SECOES},
    "usePrinterPaper": True,
    "paperHeightCm": 29.7,
    "paperWidthCm": 21.0,
    "marginLeftCm": 1.0,
    "marginRightCm": 1.0,
    "marginTopCm": 1.0,
    "marginBottomCm": 1.0,
    "printerName": "Escolher no navegador",
    "printerStatus": "Disponivel ao imprimir",
    "printerType": "Destino do navegador",
    "printerWhere": "Definido pelo sistema",
    "printerComment": "A impressora fisica e escolhida no dialogo final do navegador.",
    "paperSize": "A4",
    "paperSource": "Origem padrao",
    "printerOrientation": "retrato",
}

MODELOS_FIELD_TO_TIPO = {
    "modelo_impresso_atestados_id": "atestados",
    "modelo_impresso_receitas_id": "receitas",
    "modelo_impresso_recibos_id": "recibos",
    "modelo_padrao_etiquetas_id": "etiquetas",
    "modelo_texto_email_agenda_id": "email_agenda",
    "modelo_padrao_orcamentos_id": "orcamentos",
    "modelo_texto_whatsapp_agenda_id": "whatsapp_agenda",
}


class GeneralPreferencesUpdateRequest(BaseModel):
    user_id: int | None = None
    pesquisa_padrao_odontograma: str = "geral"
    tabela_padrao_id: int | None = None
    convenio_padrao_id: int | None = 0
    mensagem_padrao_orcamentos: str = ""
    historico_padrao_conta_corrente: str = ""
    exibir_quadro_avisos: bool = True
    busca_automatica_pacientes_agendados: bool = True
    alarme_habilitado: bool = False
    alarme_minutos_antecedencia: int = 1


class ModelPreferencesUpdateRequest(BaseModel):
    user_id: int | None = None
    modelo_impresso_atestados_id: int | None = None
    modelo_impresso_receitas_id: int | None = None
    modelo_impresso_recibos_id: int | None = None
    modelo_padrao_etiquetas_id: int | None = None
    modelo_texto_email_agenda_id: int | None = None
    modelo_padrao_orcamentos_id: int | None = None
    modelo_texto_whatsapp_agenda_id: int | None = None


class EnvironmentPreferencesUpdateRequest(BaseModel):
    user_id: int | None = None
    secao_ativa: str = "enunciados"
    secoes: dict[str, dict] = Field(default_factory=dict)


class UserDataPreferencesUpdateRequest(BaseModel):
    user_id: int | None = None
    nome: str
    apelido: str | None = None
    email: str | None = None
    endereco: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    cep: str | None = None
    uf: str | None = None
    pais: str | None = None
    telefones: str | None = None
    cro: str | None = None
    cpf: str | None = None


class OdontogramPreferencesUpdateRequest(BaseModel):
    user_id: int | None = None
    especialidade_mais_utilizada: str = "clinica"
    filtro_mais_utilizado: str = "todos"
    exibir_alerta_anamnese: bool = True
    exibir_icones_alerta: bool = True
    exibir_imagens_easycapture: bool = True
    exibir_coluna_cirurgiao_historico: bool = False
    exibir_historico_ordem_decrescente: bool = True
    exibir_dados_paciente: bool = True
    exibir_dados_tratamento: bool = True
    exibir_observacoes: bool = True
    exibir_documentos: bool = True
    exibir_agenda_dia: bool = True
    cor_a_realizar: str = "#0000ff"
    cor_realizado: str = "#008000"
    cor_condicao_observada: str = "#ff0000"
    cor_anomalia: str = "#800080"


class ReportConfigUpdateRequest(BaseModel):
    user_id: int | None = None
    config: dict = Field(default_factory=dict)


def _clean_text(value: str | None, max_len: int | None = None) -> str:
    txt = " ".join(str(value or "").split()).strip()
    if not txt:
        return ""
    return txt[:max_len] if max_len is not None else txt


def _load_preferences_json(usuario: Usuario) -> dict:
    raw = (usuario.preferencias_usuario_json or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _dump_preferences_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _resolve_target_user(
    db: Session,
    current_user: Usuario,
    user_id: int | None,
) -> Usuario:
    if not user_id or int(user_id) == int(current_user.id):
        return current_user

    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Apenas administradores podem alterar preferencias de outro usuario.")

    usuario = (
        db.query(Usuario)
        .filter(
            Usuario.id == int(user_id),
            Usuario.clinica_id == current_user.clinica_id,
        )
        .first()
    )
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")
    if is_system_user(usuario):
        raise HTTPException(status_code=400, detail="Conta base 'Clínica' é protegida.")
    return usuario


def _sanitize_preferences_values(
    db: Session,
    clinica_id: int,
    values: dict,
) -> dict:
    data = dict(PREFERENCIAS_GERAL_PADRAO)
    data.update(values or {})

    # Enquanto o odontograma ainda nao existe no SaaS, esta preferencia e alinhada
    # ao mesmo conjunto de campos usado hoje pelo Menu de pacientes (fichaMenuPac).
    # Quando o odontograma for criado, ele deve reutilizar exatamente estes ids.
    pesquisa = str(data.get("pesquisa_padrao_odontograma") or "geral").strip().lower()
    if pesquisa not in {item["id"] for item in PESQUISA_PADRAO_ODONTOGRAMA}:
        pesquisa = "geral"

    tabela_padrao_id = data.get("tabela_padrao_id")
    try:
        tabela_padrao_id = int(tabela_padrao_id) if tabela_padrao_id not in (None, "", 0, "0") else None
    except Exception:
        tabela_padrao_id = None
    if tabela_padrao_id:
        tabela_exists = (
            db.query(ProcedimentoTabela.id)
            .filter(
                ProcedimentoTabela.id == tabela_padrao_id,
                ProcedimentoTabela.clinica_id == clinica_id,
                ProcedimentoTabela.inativo.is_(False),
            )
            .first()
        )
        if not tabela_exists:
            tabela_padrao_id = None

    convenio_padrao_id = data.get("convenio_padrao_id")
    try:
        convenio_padrao_id = int(convenio_padrao_id) if convenio_padrao_id not in (None, "") else 0
    except Exception:
        convenio_padrao_id = 0
    if convenio_padrao_id > 0:
        convenio_exists = (
            db.query(ConvenioOdonto.id)
            .filter(
                ConvenioOdonto.id == convenio_padrao_id,
                ConvenioOdonto.clinica_id == clinica_id,
                ConvenioOdonto.inativo.is_(False),
            )
            .first()
        )
        if not convenio_exists:
            convenio_padrao_id = 0
    else:
        convenio_padrao_id = 0

    try:
        alarme_minutos = int(data.get("alarme_minutos_antecedencia") or 1)
    except Exception:
        alarme_minutos = 1
    alarme_minutos = max(1, min(120, alarme_minutos))

    return {
        "pesquisa_padrao_odontograma": pesquisa,
        "tabela_padrao_id": tabela_padrao_id,
        "convenio_padrao_id": convenio_padrao_id,
        "mensagem_padrao_orcamentos": _clean_text(data.get("mensagem_padrao_orcamentos"), 500),
        "historico_padrao_conta_corrente": _clean_text(data.get("historico_padrao_conta_corrente"), 200),
        "exibir_quadro_avisos": bool(data.get("exibir_quadro_avisos", True)),
        "busca_automatica_pacientes_agendados": bool(data.get("busca_automatica_pacientes_agendados", True)),
        "alarme_habilitado": bool(data.get("alarme_habilitado", False)),
        "alarme_minutos_antecedencia": alarme_minutos,
    }


def _catalogo_modelos_para_usuario(db: Session, usuario: Usuario, tipo_modelo: str) -> list[dict]:
    rows = (
        db.query(ModeloDocumento)
        .filter(
            ModeloDocumento.ativo.is_(True),
            ModeloDocumento.tipo_modelo == tipo_modelo,
            ((ModeloDocumento.clinica_id == usuario.clinica_id) | (ModeloDocumento.clinica_id.is_(None))),
        )
        .order_by(
            ModeloDocumento.clinica_id.is_(None).asc(),
            func.lower(ModeloDocumento.nome_exibicao).asc(),
            ModeloDocumento.id.asc(),
        )
        .all()
    )
    options = [{"id": None, "nome": ""}]
    for item in rows:
        origem = "Clínica" if item.clinica_id == usuario.clinica_id else "Base"
        label = f"{item.nome_exibicao} [{origem}]"
        options.append(
            {
                "id": item.id,
                "nome": label,
                "scope": "clinica" if item.clinica_id == usuario.clinica_id else "base",
                "arquivo": item.nome_arquivo,
                "caminho": item.caminho_arquivo,
            }
        )
    return options


def _sanitize_model_choice(
    db: Session,
    usuario: Usuario,
    field_name: str,
    value,
) -> int | None:
    tipo_modelo = MODELOS_FIELD_TO_TIPO[field_name]
    options = _catalogo_modelos_para_usuario(db, usuario, tipo_modelo)
    allowed = {item.get("id") for item in options}
    if value in (None, "", 0, "0"):
        return None
    try:
        current = int(value)
    except Exception:
        current = None
    return current if current in allowed else None


def _sanitize_model_preferences(db: Session, usuario: Usuario, values: dict) -> dict:
    data = dict(PREFERENCIAS_MODELOS_PADRAO)
    data.update(values or {})
    if "modelo_texto_whatsapp_agenda_id" not in data and "modelo_texto_sms_agenda" in (values or {}):
        data["modelo_texto_whatsapp_agenda_id"] = values.get("modelo_texto_sms_agenda")
    return {
        "modelo_impresso_atestados_id": _sanitize_model_choice(db, usuario, "modelo_impresso_atestados_id", data.get("modelo_impresso_atestados_id")),
        "modelo_impresso_receitas_id": _sanitize_model_choice(db, usuario, "modelo_impresso_receitas_id", data.get("modelo_impresso_receitas_id")),
        "modelo_impresso_recibos_id": _sanitize_model_choice(db, usuario, "modelo_impresso_recibos_id", data.get("modelo_impresso_recibos_id")),
        "modelo_padrao_etiquetas_id": _sanitize_model_choice(db, usuario, "modelo_padrao_etiquetas_id", data.get("modelo_padrao_etiquetas_id")),
        "modelo_texto_email_agenda_id": _sanitize_model_choice(db, usuario, "modelo_texto_email_agenda_id", data.get("modelo_texto_email_agenda_id")),
        "modelo_padrao_orcamentos_id": _sanitize_model_choice(db, usuario, "modelo_padrao_orcamentos_id", data.get("modelo_padrao_orcamentos_id")),
        "modelo_texto_whatsapp_agenda_id": _sanitize_model_choice(db, usuario, "modelo_texto_whatsapp_agenda_id", data.get("modelo_texto_whatsapp_agenda_id")),
    }


def _sanitize_environment_preferences(values: dict) -> dict:
    data = values if isinstance(values, dict) else {}

    def normalize_style_id(value: str | None) -> str:
        raw = str(value or "").strip().lower()
        if raw in {"fsbold", "bold", "negrito"}:
            return "negrito"
        if raw in {"fsitalic", "italic", "italico"}:
            return "italico"
        if raw in {"fsbolditalic", "fsitalicbold", "bolditalic", "italicbold", "negrito-italico", "italico-negrito"}:
            return "negrito-italico"
        return "normal"

    old_style = {
        "fonte_nome": data.get("fonte_nome"),
        "fonte_tamanho": data.get("fonte_tamanho"),
        "fonte_estilo": data.get("fonte_estilo"),
        "cor_texto": data.get("cor_texto"),
        "riscado": data.get("riscado"),
        "sublinhado": data.get("sublinhado"),
        "script": data.get("script"),
    }
    secoes_raw = data.get("secoes") if isinstance(data.get("secoes"), dict) else {}

    def sanitize_style(source: dict | None) -> dict:
        ref = source if isinstance(source, dict) else {}
        fonte_nome = str(ref.get("fonte_nome") or old_style.get("fonte_nome") or AMBIENTE_ESTILO_PADRAO["fonte_nome"]).strip()
        if fonte_nome not in AMBIENTE_FONTES:
            fonte_nome = AMBIENTE_ESTILO_PADRAO["fonte_nome"]
        try:
            fonte_tamanho = int(ref.get("fonte_tamanho") or old_style.get("fonte_tamanho") or AMBIENTE_ESTILO_PADRAO["fonte_tamanho"])
        except Exception:
            fonte_tamanho = AMBIENTE_ESTILO_PADRAO["fonte_tamanho"]
        fonte_tamanho = max(8, min(36, fonte_tamanho))
        fonte_estilo = normalize_style_id(ref.get("fonte_estilo") or old_style.get("fonte_estilo"))
        cor_texto = str(ref.get("cor_texto") or old_style.get("cor_texto") or AMBIENTE_ESTILO_PADRAO["cor_texto"]).strip() or AMBIENTE_ESTILO_PADRAO["cor_texto"]
        if not cor_texto.startswith("#") or len(cor_texto) not in {4, 7}:
            cor_texto = AMBIENTE_ESTILO_PADRAO["cor_texto"]
        script = str(ref.get("script") or old_style.get("script") or AMBIENTE_ESTILO_PADRAO["script"]).strip() or AMBIENTE_ESTILO_PADRAO["script"]
        return {
            "fonte_nome": fonte_nome,
            "fonte_tamanho": fonte_tamanho,
            "fonte_estilo": fonte_estilo,
            "cor_texto": cor_texto.lower(),
            "riscado": bool(ref.get("riscado", old_style.get("riscado", AMBIENTE_ESTILO_PADRAO["riscado"]))),
            "sublinhado": bool(ref.get("sublinhado", old_style.get("sublinhado", AMBIENTE_ESTILO_PADRAO["sublinhado"]))),
            "script": script,
        }

    secoes = {
        item["id"]: sanitize_style(secoes_raw.get(item["id"]))
        for item in AMBIENTE_SECOES
    }
    secao_ativa = str(data.get("secao_ativa") or PREFERENCIAS_AMBIENTE_PADRAO["secao_ativa"]).strip().lower()
    if secao_ativa not in secoes:
        secao_ativa = PREFERENCIAS_AMBIENTE_PADRAO["secao_ativa"]
    return {
        "secao_ativa": secao_ativa,
        "secoes": secoes,
    }


def _sanitize_user_data_values(db: Session, usuario: Usuario, values: dict) -> dict:
    data = values or {}
    nome = _clean_text(data.get("nome"), 160)
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome do usuario.")
    apelido = _clean_text(data.get("apelido"), 60)
    email = str(data.get("email") or usuario.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Informe o e-mail do usuario.")
    if "@" not in email:
        raise HTTPException(status_code=400, detail="E-mail invalido.")
    exists = (
        db.query(Usuario.id)
        .filter(
            Usuario.id != usuario.id,
            func.lower(Usuario.email) == email,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="E-mail ja cadastrado.")
    endereco = _clean_text(data.get("endereco"), 180)
    bairro = _clean_text(data.get("bairro"), 120)
    cidade = _clean_text(data.get("cidade"), 120)
    cep = _clean_text(data.get("cep"), 20)
    uf = _clean_text(data.get("uf"), 10).upper()
    pais = _clean_text(data.get("pais"), 80) or "Brasil"
    telefones_raw = _clean_text(data.get("telefones"), 120)
    telefones_parts = [p for p in re.split(r"[;,/|\n\r]+", telefones_raw) if p and p.strip()]
    telefones_parts = [p.strip() for p in telefones_parts if p.strip()]
    fone1 = telefones_parts[0] if len(telefones_parts) > 0 else ""
    fone2 = telefones_parts[1] if len(telefones_parts) > 1 else ""
    cro = _clean_text(data.get("cro"), 40)
    cpf = _clean_text(data.get("cpf"), 20)
    return {
        "nome": nome,
        "apelido": apelido or "",
        "email": email,
        "endereco": endereco,
        "bairro": bairro,
        "cidade": cidade,
        "cep": cep,
        "uf": uf,
        "pais": pais,
        "telefones": telefones_raw,
        "fone1": fone1,
        "fone2": fone2,
        "cro": cro,
        "cpf": cpf,
    }


def _listar_especialidades_odontograma(db: Session, usuario: Usuario) -> list[dict]:
    rows = (
        db.query(ItemAuxiliar)
        .filter(
            ItemAuxiliar.clinica_id == usuario.clinica_id,
            ItemAuxiliar.tipo.in_(["Especialidade", "Especialidade odontologica"]),
            ItemAuxiliar.inativo.is_(False),
        )
        .order_by(func.coalesce(ItemAuxiliar.ordem, 9999).asc(), func.lower(ItemAuxiliar.descricao).asc())
        .all()
    )
    if not rows:
        return list(ODONTOGRAMA_ESPECIALIDADES_PADRAO)
    items = []
    for row in rows:
        label = str(row.descricao or "").strip()
        if not label:
            continue
        ident = (
            str(row.codigo or label)
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )
        items.append({"id": ident, "label": label})
    return items or list(ODONTOGRAMA_ESPECIALIDADES_PADRAO)


def _normalize_color(value: str | None, default: str) -> str:
    color = str(value or default).strip() or default
    if not color.startswith("#") or len(color) not in {4, 7}:
        return default.lower()
    return color.lower()


def _sanitize_odontogram_preferences(db: Session, usuario: Usuario, values: dict) -> dict:
    data = dict(PREFERENCIAS_ODONTOGRAMA_PADRAO)
    data.update(values or {})
    especialidades = _listar_especialidades_odontograma(db, usuario)
    allowed_especialidades = {item["id"] for item in especialidades}
    filtros = {item["id"] for item in ODONTOGRAMA_FILTROS_PADRAO}
    especialidade = str(data.get("especialidade_mais_utilizada") or "clinica").strip().lower()
    if especialidade not in allowed_especialidades:
        especialidade = especialidades[0]["id"] if especialidades else "clinica"
    filtro = str(data.get("filtro_mais_utilizado") or "todos").strip().lower()
    if filtro not in filtros:
        filtro = "todos"
    return {
        "especialidade_mais_utilizada": especialidade,
        "filtro_mais_utilizado": filtro,
        "exibir_alerta_anamnese": bool(data.get("exibir_alerta_anamnese", True)),
        "exibir_icones_alerta": bool(data.get("exibir_icones_alerta", True)),
        "exibir_imagens_easycapture": bool(data.get("exibir_imagens_easycapture", True)),
        "exibir_coluna_cirurgiao_historico": bool(data.get("exibir_coluna_cirurgiao_historico", False)),
        "exibir_historico_ordem_decrescente": bool(data.get("exibir_historico_ordem_decrescente", True)),
        "exibir_dados_paciente": bool(data.get("exibir_dados_paciente", True)),
        "exibir_dados_tratamento": bool(data.get("exibir_dados_tratamento", True)),
        "exibir_observacoes": bool(data.get("exibir_observacoes", True)),
        "exibir_documentos": bool(data.get("exibir_documentos", True)),
        "exibir_agenda_dia": bool(data.get("exibir_agenda_dia", True)),
        "cor_a_realizar": _normalize_color(data.get("cor_a_realizar"), PREFERENCIAS_ODONTOGRAMA_PADRAO["cor_a_realizar"]),
        "cor_realizado": _normalize_color(data.get("cor_realizado"), PREFERENCIAS_ODONTOGRAMA_PADRAO["cor_realizado"]),
        "cor_condicao_observada": _normalize_color(data.get("cor_condicao_observada"), PREFERENCIAS_ODONTOGRAMA_PADRAO["cor_condicao_observada"]),
        "cor_anomalia": _normalize_color(data.get("cor_anomalia"), PREFERENCIAS_ODONTOGRAMA_PADRAO["cor_anomalia"]),
    }


def _normalize_report_color(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw.startswith("#") and len(raw) in {4, 7}:
        return raw
    return REPORT_SECAO_PADRAO["color"]


def _normalize_report_number(value: object, default: float, min_val: float, max_val: float) -> float:
    try:
        num = float(str(value or "").replace(",", "."))
    except Exception:
        num = default
    if num < min_val:
        return min_val
    if num > max_val:
        return max_val
    return num


def _normalize_report_section(values: dict | None) -> dict:
    data = values if isinstance(values, dict) else {}
    fonte = str(data.get("fontFamily") or REPORT_SECAO_PADRAO["fontFamily"]).strip() or REPORT_SECAO_PADRAO["fontFamily"]
    try:
        tamanho = int(data.get("fontSize") or REPORT_SECAO_PADRAO["fontSize"])
    except Exception:
        tamanho = REPORT_SECAO_PADRAO["fontSize"]
    tamanho = max(6, min(72, tamanho))
    return {
        "fontFamily": fonte,
        "fontSize": tamanho,
        "bold": bool(data.get("bold", REPORT_SECAO_PADRAO["bold"])),
        "italic": bool(data.get("italic", REPORT_SECAO_PADRAO["italic"])),
        "underline": bool(data.get("underline", REPORT_SECAO_PADRAO["underline"])),
        "strike": bool(data.get("strike", REPORT_SECAO_PADRAO["strike"])),
        "color": _normalize_report_color(data.get("color")),
    }


def _load_report_config(usuario: Usuario) -> dict:
    raw = (usuario.preferencias_impressora_json or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _sanitize_report_config(values: dict) -> dict:
    data = dict(REPORT_CONFIG_PADRAO)
    data.update(values or {})

    section_styles_raw = data.get("sectionStyles") if isinstance(data.get("sectionStyles"), dict) else {}
    section_styles = {sec: _normalize_report_section(section_styles_raw.get(sec)) for sec in REPORT_SECOES}

    section_id = str(data.get("sectionId") or "titulo").strip().lower()
    if section_id not in REPORT_SECOES:
        section_id = "titulo"

    logo_data = str(data.get("logoDataUrl") or "")
    # Permite logotipos maiores (ex.: BMP) sem descartar o dado.
    # 2 MB em base64 cobre usos comuns sem sobrecarregar o JSON.
    if len(logo_data) > 2_000_000:
        logo_data = ""

    return {
        "headerText": _clean_text(data.get("headerText"), 250),
        "printLogo": bool(data.get("printLogo", True)),
        "logoPath": _clean_text(data.get("logoPath"), 260),
        "logoDataUrl": logo_data,
        "printUser": bool(data.get("printUser", False)),
        "printPage": bool(data.get("printPage", True)),
        "printDateTime": bool(data.get("printDateTime", True)),
        "sectionId": section_id,
        "sectionStyles": section_styles,
        "usePrinterPaper": bool(data.get("usePrinterPaper", True)),
        "paperHeightCm": _normalize_report_number(data.get("paperHeightCm"), 29.7, 10.0, 100.0),
        "paperWidthCm": _normalize_report_number(data.get("paperWidthCm"), 21.0, 10.0, 100.0),
        "marginLeftCm": _normalize_report_number(data.get("marginLeftCm"), 1.0, 0.0, 10.0),
        "marginRightCm": _normalize_report_number(data.get("marginRightCm"), 1.0, 0.0, 10.0),
        "marginTopCm": _normalize_report_number(data.get("marginTopCm"), 1.0, 0.0, 10.0),
        "marginBottomCm": _normalize_report_number(data.get("marginBottomCm"), 1.0, 0.0, 10.0),
        "printerName": _clean_text(data.get("printerName"), 120),
        "printerStatus": _clean_text(data.get("printerStatus"), 120),
        "printerType": _clean_text(data.get("printerType"), 120),
        "printerWhere": _clean_text(data.get("printerWhere"), 120),
        "printerComment": _clean_text(data.get("printerComment"), 200),
        "paperSize": _clean_text(data.get("paperSize"), 60),
        "paperSource": _clean_text(data.get("paperSource"), 60),
        "printerOrientation": _clean_text(data.get("printerOrientation"), 20),
    }


def _build_general_payload(db: Session, usuario: Usuario) -> dict:
    prefs = _load_preferences_json(usuario)
    values = _sanitize_preferences_values(
        db=db,
        clinica_id=usuario.clinica_id,
        values=prefs.get("geral") if isinstance(prefs.get("geral"), dict) else {},
    )
    tabelas = (
        db.query(ProcedimentoTabela)
        .filter(
            ProcedimentoTabela.clinica_id == usuario.clinica_id,
            ProcedimentoTabela.inativo.is_(False),
        )
        .order_by(func.lower(ProcedimentoTabela.nome).asc(), ProcedimentoTabela.id.asc())
        .all()
    )
    convenios = (
        db.query(ConvenioOdonto)
        .filter(
            ConvenioOdonto.clinica_id == usuario.clinica_id,
            ConvenioOdonto.inativo.is_(False),
        )
        .order_by(func.lower(ConvenioOdonto.nome).asc(), ConvenioOdonto.id.asc())
        .all()
    )
    return {
        "user": {
            "id": usuario.id,
            "nome": usuario.nome,
            "apelido": (usuario.apelido or usuario.nome or "").strip(),
        },
        "values": values,
        "options": {
            "pesquisa_padrao_odontograma": list(PESQUISA_PADRAO_ODONTOGRAMA),
            "tabelas_intervencoes": [
                {
                    "id": item.id,
                    "nome": item.nome,
                    "codigo": item.codigo,
                    "fonte_pagadora": item.fonte_pagadora,
                }
                for item in tabelas
            ],
            "convenios": [
                {"id": 0, "nome": "Particular"},
                *[
                    {
                        "id": item.id,
                        "nome": item.nome,
                        "codigo": item.codigo,
                    }
                    for item in convenios
                ],
            ],
        },
    }


def _build_model_payload(db: Session, usuario: Usuario) -> dict:
    prefs = _load_preferences_json(usuario)
    values = _sanitize_model_preferences(
        db=db,
        usuario=usuario,
        values=prefs.get("modelos") if isinstance(prefs.get("modelos"), dict) else {},
    )
    return {
        "user": {
            "id": usuario.id,
            "nome": usuario.nome,
            "apelido": (usuario.apelido or usuario.nome or "").strip(),
        },
        "values": values,
        "options": {
            "modelo_impresso_atestados": _catalogo_modelos_para_usuario(db, usuario, "atestados"),
            "modelo_impresso_receitas": _catalogo_modelos_para_usuario(db, usuario, "receitas"),
            "modelo_impresso_recibos": _catalogo_modelos_para_usuario(db, usuario, "recibos"),
            "modelo_padrao_etiquetas": _catalogo_modelos_para_usuario(db, usuario, "etiquetas"),
            "modelo_texto_email_agenda": _catalogo_modelos_para_usuario(db, usuario, "email_agenda"),
            "modelo_padrao_orcamentos": _catalogo_modelos_para_usuario(db, usuario, "orcamentos"),
            "modelo_texto_whatsapp_agenda": _catalogo_modelos_para_usuario(db, usuario, "whatsapp_agenda"),
        },
    }


def _build_environment_payload(usuario: Usuario) -> dict:
    prefs = _load_preferences_json(usuario)
    values = _sanitize_environment_preferences(
        prefs.get("ambiente") if isinstance(prefs.get("ambiente"), dict) else {}
    )
    return {
        "user": {
            "id": usuario.id,
            "nome": usuario.nome,
            "apelido": (usuario.apelido or usuario.nome or "").strip(),
        },
        "values": values,
        "options": {
            "secoes": list(AMBIENTE_SECOES),
            "fontes": [{"id": item, "label": item} for item in AMBIENTE_FONTES],
            "tamanhos": [{"id": item, "label": str(item)} for item in [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36]],
            "estilos": list(AMBIENTE_FONT_STYLES),
            "scripts": [{"id": "Ocidental", "label": "Ocidental"}],
        },
    }


def _build_user_data_payload(usuario: Usuario) -> dict:
    prefs = _load_preferences_json(usuario)
    dados_pref = prefs.get("dados_usuario") if isinstance(prefs.get("dados_usuario"), dict) else {}
    prestador = usuario.prestador
    endereco = ""
    if prestador:
        partes = [
            str(prestador.endereco or "").strip(),
            str(prestador.numero or "").strip(),
            str(prestador.complemento or "").strip(),
        ]
        partes = [parte for parte in partes if parte]
        if partes:
            endereco = ", ".join(partes)
    if not endereco:
        endereco = str(dados_pref.get("endereco") or "").strip()
    fones = []
    if prestador:
        if prestador.fone1:
            fones.append(str(prestador.fone1).strip())
        if prestador.fone2:
            fones.append(str(prestador.fone2).strip())
    telefones = " / ".join([fone for fone in fones if fone])
    if not telefones:
        telefones = str(dados_pref.get("telefones") or "").strip()
    return {
        "user": {
            "id": usuario.id,
            "nome": usuario.nome,
            "apelido": (usuario.apelido or usuario.nome or "").strip(),
        },
        "values": {
            "nome": usuario.nome,
            "apelido": (usuario.apelido or "").strip(),
            "email": usuario.email,
            "tipo_usuario": (usuario.tipo_usuario or "").strip(),
            "prestador_nome": (getattr(usuario.prestador, "nome", "") or "").strip(),
            "unidade_nome": (getattr(usuario.unidade_atendimento, "nome", "") or "").strip(),
            "endereco": endereco,
            "bairro": (getattr(prestador, "bairro", None) or dados_pref.get("bairro") or "").strip(),
            "cidade": (getattr(prestador, "cidade", None) or dados_pref.get("cidade") or "").strip(),
            "cep": (getattr(prestador, "cep", None) or dados_pref.get("cep") or "").strip(),
            "uf": (getattr(prestador, "uf", None) or dados_pref.get("uf") or "").strip().upper(),
            "pais": (dados_pref.get("pais") or "Brasil").strip() or "Brasil",
            "telefones": telefones,
            "cro": (getattr(prestador, "cro", None) or dados_pref.get("cro") or "").strip(),
            "cpf": (getattr(prestador, "cpf", None) or dados_pref.get("cpf") or "").strip(),
        },
    }


def _build_odontogram_payload(db: Session, usuario: Usuario) -> dict:
    prefs = _load_preferences_json(usuario)
    values = _sanitize_odontogram_preferences(
        db=db,
        usuario=usuario,
        values=prefs.get("odontograma") if isinstance(prefs.get("odontograma"), dict) else {},
    )
    return {
        "user": {
            "id": usuario.id,
            "nome": usuario.nome,
            "apelido": (usuario.apelido or usuario.nome or "").strip(),
        },
        "values": values,
        "options": {
            "especialidades": _listar_especialidades_odontograma(db, usuario),
            "filtros": list(ODONTOGRAMA_FILTROS_PADRAO),
        },
        "integration_hint": (
            "Estas preferencias ja estao prontas para o futuro modulo Odontograma. "
            "Ao implementar o modulo, reutilize os mesmos ids de especialidade e filtro aqui salvos."
        ),
    }


@router.get("/general")
def get_general_preferences(
    user_id: int | None = Query(default=None),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    usuario = _resolve_target_user(db, current_user, user_id)
    return _build_general_payload(db, usuario)


@router.patch("/general")
def update_general_preferences(
    payload: GeneralPreferencesUpdateRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    usuario = _resolve_target_user(db, current_user, payload.user_id)
    valores = _sanitize_preferences_values(
        db=db,
        clinica_id=usuario.clinica_id,
        values=payload.model_dump(),
    )
    prefs = _load_preferences_json(usuario)
    prefs["geral"] = valores
    usuario.preferencias_usuario_json = _dump_preferences_json(prefs)
    db.commit()
    db.refresh(usuario)
    return {
        "detail": "Preferencias atualizadas com sucesso.",
        **_build_general_payload(db, usuario),
    }


@router.get("/models")
def get_model_preferences(
    user_id: int | None = Query(default=None),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    usuario = _resolve_target_user(db, current_user, user_id)
    return _build_model_payload(db, usuario)


@router.patch("/models")
def update_model_preferences(
    payload: ModelPreferencesUpdateRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    usuario = _resolve_target_user(db, current_user, payload.user_id)
    valores = _sanitize_model_preferences(db, usuario, payload.model_dump())
    prefs = _load_preferences_json(usuario)
    prefs["modelos"] = valores
    usuario.preferencias_usuario_json = _dump_preferences_json(prefs)
    db.commit()
    db.refresh(usuario)
    return {
        "detail": "Preferencias de modelos atualizadas com sucesso.",
        **_build_model_payload(db, usuario),
    }


@router.get("/environment")
def get_environment_preferences(
    user_id: int | None = Query(default=None),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    usuario = _resolve_target_user(db, current_user, user_id)
    return _build_environment_payload(usuario)


@router.patch("/environment")
def update_environment_preferences(
    payload: EnvironmentPreferencesUpdateRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    usuario = _resolve_target_user(db, current_user, payload.user_id)
    valores = _sanitize_environment_preferences(payload.model_dump())
    prefs = _load_preferences_json(usuario)
    prefs["ambiente"] = valores
    usuario.preferencias_usuario_json = _dump_preferences_json(prefs)
    db.commit()
    db.refresh(usuario)
    return {
        "detail": "Preferencias de ambiente atualizadas com sucesso.",
        **_build_environment_payload(usuario),
    }


@router.get("/user-data")
def get_user_data_preferences(
    user_id: int | None = Query(default=None),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    usuario = _resolve_target_user(db, current_user, user_id)
    return _build_user_data_payload(usuario)


@router.patch("/user-data")
def update_user_data_preferences(
    payload: UserDataPreferencesUpdateRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    usuario = _resolve_target_user(db, current_user, payload.user_id)
    valores = _sanitize_user_data_values(db, usuario, payload.model_dump())
    usuario.nome = valores["nome"]
    usuario.apelido = valores["apelido"] or None
    usuario.email = valores["email"]
    prestador = usuario.prestador
    if prestador:
        prestador.nome = valores["nome"]
        prestador.apelido = valores["apelido"] or None
        prestador.endereco = valores["endereco"] or None
        prestador.bairro = valores["bairro"] or None
        prestador.cidade = valores["cidade"] or None
        prestador.cep = valores["cep"] or None
        prestador.uf = valores["uf"] or None
        prestador.cro = valores["cro"] or None
        prestador.cpf = valores["cpf"] or None
        prestador.fone1 = valores["fone1"] or None
        prestador.fone2 = valores["fone2"] or None

    prefs = _load_preferences_json(usuario)
    dados_pref = prefs.get("dados_usuario") if isinstance(prefs.get("dados_usuario"), dict) else {}
    dados_pref["pais"] = valores["pais"] or "Brasil"
    if not prestador:
        dados_pref.update(
            {
                "endereco": valores["endereco"],
                "bairro": valores["bairro"],
                "cidade": valores["cidade"],
                "cep": valores["cep"],
                "uf": valores["uf"],
                "telefones": valores["telefones"],
                "cro": valores["cro"],
                "cpf": valores["cpf"],
            }
        )
    prefs["dados_usuario"] = dados_pref
    usuario.preferencias_usuario_json = _dump_preferences_json(prefs)
    db.commit()
    db.refresh(usuario)
    return {
        "detail": "Dados do usuario atualizados com sucesso.",
        **_build_user_data_payload(usuario),
    }


@router.get("/odontogram")
def get_odontogram_preferences(
    user_id: int | None = Query(default=None),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    usuario = _resolve_target_user(db, current_user, user_id)
    return _build_odontogram_payload(db, usuario)


@router.patch("/odontogram")
def update_odontogram_preferences(
    payload: OdontogramPreferencesUpdateRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    usuario = _resolve_target_user(db, current_user, payload.user_id)
    valores = _sanitize_odontogram_preferences(db, usuario, payload.model_dump())
    prefs = _load_preferences_json(usuario)
    prefs["odontograma"] = valores
    usuario.preferencias_usuario_json = _dump_preferences_json(prefs)
    db.commit()
    db.refresh(usuario)
    return {
        "detail": "Preferencias do odontograma atualizadas com sucesso.",
        **_build_odontogram_payload(db, usuario),
    }


@router.get("/report-config")
def get_report_config(
    user_id: int | None = Query(default=None),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    usuario = _resolve_target_user(db, current_user, user_id)
    config = _sanitize_report_config(_load_report_config(usuario))
    return {
        "user": {
            "id": usuario.id,
            "nome": usuario.nome,
            "apelido": (usuario.apelido or usuario.nome or "").strip(),
        },
        "config": config,
    }


@router.patch("/report-config")
def update_report_config(
    payload: ReportConfigUpdateRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    usuario = _resolve_target_user(db, current_user, payload.user_id)
    config = _sanitize_report_config(payload.config or {})
    usuario.preferencias_impressora_json = json.dumps(config, ensure_ascii=False, separators=(",", ":"))
    db.commit()
    db.refresh(usuario)
    return {
        "detail": "Configuração de impressos atualizada com sucesso.",
        "user": {
            "id": usuario.id,
            "nome": usuario.nome,
            "apelido": (usuario.apelido or usuario.nome or "").strip(),
        },
        "config": config,
    }
