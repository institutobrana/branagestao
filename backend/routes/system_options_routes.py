import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models.clinica import Clinica
from models.financeiro import CategoriaFinanceira, ItemAuxiliar
from models.usuario import Usuario
from security.dependencies import (
    get_current_user,
    require_admin_password_if_user_control_enabled,
    require_module_access,
)
from services.indices_service import listar_indices

router = APIRouter(
    prefix="/system-options",
    tags=["system-options"],
    dependencies=[
        Depends(require_module_access("configuracao")),
        Depends(require_admin_password_if_user_control_enabled("configuracao")),
    ],
)

FORMATOS_DATA_PADRAO = [
    {"id": "DD/MM/AA", "label": "DD/MM/AA"},
    {"id": "DD/MM/AAAA", "label": "DD/MM/AAAA"},
]

FORMATOS_EMAIL_PADRAO = [
    {"id": "texto_simples", "label": "Texto simples"},
    {"id": "formatado_sem_imagens", "label": "Formatado (sem imagens)"},
    {"id": "formatado_com_imagens", "label": "Formatado com imagens (anexo)"},
    {"id": "saas_nativo", "label": "Envio nativo do sistema (SaaS)"},
]

SISTEMAS_CAPTURA_PADRAO = [
    {"id": "EasyCapture", "label": "EasyCapture"},
    {"id": "Nativo", "label": "Captura nativa"},
    {"id": "Desativado", "label": "Desativado"},
]

VERSOES_WORD_PADRAO = [
    {"id": "Word 2000", "label": "Word 2000"},
    {"id": "Word 2003", "label": "Word 2003"},
    {"id": "Word XP", "label": "Word XP"},
    {"id": "Word 2007+", "label": "Word 2007 ou superior"},
]


def _default_local_paths() -> dict:
    base_dir = Path(__file__).resolve().parents[1]
    saas_dir = base_dir.parent
    storage_dir = saas_dir / "storage"
    return {
        "banco_dados": "SaaS (banco gerenciado)",
        "pasta_temp": str(storage_dir / "tmp"),
        "pasta_textos": str(storage_dir / "textos"),
        "pasta_imagens": str(storage_dir / "imagens"),
        "pasta_tiss": str(storage_dir / "tiss"),
        "solicitar_backup_saida": True,
    }


DEFAULT_VALUES = {
    "clinica": {
        "nome": "",
        "endereco": "",
        "complemento": "",
        "bairro": "",
        "cidade": "",
        "cep": "",
        "uf": "SP",
        "telefones": "",
        "cnpj": "",
        "inscricao_estadual": "",
    },
    "financeiro": {
        "indice_padrao_id": 255,
        "moeda_corrente": "Reais",
        "sigla_moeda": "R$",
        "periodo_parcelamento": 30,
        "tipo_cobranca_padrao": "",
        "categoria_mensalidade_ortodontia_id": None,
        "indice_relatorios_id": 255,
        "pedir_indices_diariamente": True,
        "lancar_creditos_baixa_clinica": True,
        "lancar_debitos_convenio_paciente": True,
        "considerar_creditos_futuros_devedores": False,
    },
    "seguranca": {
        "ativar_controle_usuarios": True,
        "ativar_auditoria": True,
    },
    "data": {
        "formato_data": "DD/MM/AAAA",
        "considerar_ano_2000_menor_que": 15,
        "semanas_horarios_livres": 5,
    },
    "local": _default_local_paths(),
    "telefone_sms": {
        "rediscar_quando_ocupado": False,
        "tentativas_rediscagem": 1,
        "numero_linha_externa": "",
        "ddd_sms": "17",
        "limite_caracteres_sms": 145,
    },
    "avancado": {
        "sistema_captura_imagens": "EasyCapture",
        "versao_word": "Word 2000",
        "formato_envio_email": "formatado_com_imagens",
        "qtd_imagens_odontograma": 40,
        "habilitar_validacao_cpf": True,
        "bloquear_duplicidade_cpf": True,
        "habilitar_mensagens_depuracao": True,
        "ignorar_copias_driver": False,
        "salvar_arquivos_myeasy": False,
        "atualizar_agenda_automaticamente": True,
        "exigir_orcamento_aprovado": False,
        "habilitar_dente_3d": True,
        "habilitar_cep_online": True,
        "enviar_somente_num_paciente_servico_protese": False,
    },
}


class SystemOptionsUpdateRequest(BaseModel):
    values: dict = Field(default_factory=dict)


def _load_json(clinica: Clinica) -> dict:
    raw = (clinica.opcoes_sistema_json or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _dump_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)

def _sanitize_response(values: dict) -> dict:
    if not isinstance(values, dict):
        return values
    cleaned = dict(values)
    cleaned.pop("local", None)
    return cleaned


def _merge_defaults(defaults: dict, incoming: dict) -> dict:
    merged = {}
    for key, val in defaults.items():
        if isinstance(val, dict):
            src = incoming.get(key)
            merged[key] = _merge_defaults(val, src if isinstance(src, dict) else {})
        else:
            merged[key] = incoming.get(key, val)
    for key, val in incoming.items():
        if key not in merged:
            merged[key] = val
    return merged


def _to_bool(value, default=False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    txt = str(value or "").strip().lower()
    if txt in {"1", "true", "t", "sim", "s", "yes", "y", "on"}:
        return True
    if txt in {"0", "false", "f", "nao", "não", "n", "off"}:
        return False
    return default


def _to_int(value, default=0, min_value=None, max_value=None) -> int:
    try:
        num = int(value)
    except Exception:
        num = int(default)
    if min_value is not None:
        num = max(num, min_value)
    if max_value is not None:
        num = min(num, max_value)
    return num


def _to_str(value, default="") -> str:
    txt = str(value or "").strip()
    return txt if txt else default


def _normalize_choice(value, allowed: set[str], default: str) -> str:
    txt = str(value or "").strip()
    return txt if txt in allowed else default


def _sanitize_values(values: dict) -> dict:
    merged = _merge_defaults(DEFAULT_VALUES, values or {})

    clinica = merged.get("clinica", {})
    clinica["nome"] = _to_str(clinica.get("nome"), "")
    clinica["endereco"] = _to_str(clinica.get("endereco"), "")
    clinica["complemento"] = _to_str(clinica.get("complemento"), "")
    clinica["bairro"] = _to_str(clinica.get("bairro"), "")
    clinica["cidade"] = _to_str(clinica.get("cidade"), "")
    clinica["cep"] = _to_str(clinica.get("cep"), "")
    clinica["uf"] = _to_str(clinica.get("uf"), "SP")
    clinica["telefones"] = _to_str(clinica.get("telefones"), "")
    clinica["cnpj"] = _to_str(clinica.get("cnpj"), "")
    clinica["inscricao_estadual"] = _to_str(clinica.get("inscricao_estadual"), "")

    financeiro = merged.get("financeiro", {})
    financeiro["indice_padrao_id"] = _to_int(financeiro.get("indice_padrao_id"), 255)
    financeiro["moeda_corrente"] = _to_str(financeiro.get("moeda_corrente"), "Reais")
    financeiro["sigla_moeda"] = _to_str(financeiro.get("sigla_moeda"), "R$")
    financeiro["periodo_parcelamento"] = _to_int(financeiro.get("periodo_parcelamento"), 30, 1)
    financeiro["tipo_cobranca_padrao"] = _to_str(financeiro.get("tipo_cobranca_padrao"), "")
    cat_val = financeiro.get("categoria_mensalidade_ortodontia_id")
    financeiro["categoria_mensalidade_ortodontia_id"] = (
        _to_int(cat_val, 0) if str(cat_val or "").strip().isdigit() else None
    )
    financeiro["indice_relatorios_id"] = _to_int(financeiro.get("indice_relatorios_id"), 255)
    financeiro["pedir_indices_diariamente"] = _to_bool(financeiro.get("pedir_indices_diariamente"), True)
    financeiro["lancar_creditos_baixa_clinica"] = _to_bool(financeiro.get("lancar_creditos_baixa_clinica"), True)
    financeiro["lancar_debitos_convenio_paciente"] = _to_bool(
        financeiro.get("lancar_debitos_convenio_paciente"), True
    )
    financeiro["considerar_creditos_futuros_devedores"] = _to_bool(
        financeiro.get("considerar_creditos_futuros_devedores"), False
    )

    seguranca = merged.get("seguranca", {})
    seguranca["ativar_controle_usuarios"] = _to_bool(seguranca.get("ativar_controle_usuarios"), True)
    seguranca["ativar_auditoria"] = _to_bool(seguranca.get("ativar_auditoria"), True)

    data_cfg = merged.get("data", {})
    allowed_fmt = {item["id"] for item in FORMATOS_DATA_PADRAO}
    data_cfg["formato_data"] = _normalize_choice(
        data_cfg.get("formato_data"), allowed_fmt, "DD/MM/AAAA"
    )
    data_cfg["considerar_ano_2000_menor_que"] = _to_int(
        data_cfg.get("considerar_ano_2000_menor_que"), 15, 0, 99
    )
    data_cfg["semanas_horarios_livres"] = _to_int(
        data_cfg.get("semanas_horarios_livres"), 5, 1, 12
    )

    local_cfg = merged.get("local", {})
    local_defaults = _default_local_paths()
    local_cfg["banco_dados"] = _to_str(local_cfg.get("banco_dados"), local_defaults["banco_dados"])
    local_cfg["pasta_temp"] = _to_str(local_cfg.get("pasta_temp"), local_defaults["pasta_temp"])
    local_cfg["pasta_textos"] = _to_str(local_cfg.get("pasta_textos"), local_defaults["pasta_textos"])
    local_cfg["pasta_imagens"] = _to_str(local_cfg.get("pasta_imagens"), local_defaults["pasta_imagens"])
    local_cfg["pasta_tiss"] = _to_str(local_cfg.get("pasta_tiss"), local_defaults["pasta_tiss"])
    local_cfg["solicitar_backup_saida"] = _to_bool(local_cfg.get("solicitar_backup_saida"), True)

    telefone = merged.get("telefone_sms", {})
    telefone["rediscar_quando_ocupado"] = _to_bool(telefone.get("rediscar_quando_ocupado"), False)
    telefone["tentativas_rediscagem"] = _to_int(telefone.get("tentativas_rediscagem"), 1, 0, 9)
    telefone["numero_linha_externa"] = _to_str(telefone.get("numero_linha_externa"), "")
    telefone["ddd_sms"] = _to_str(telefone.get("ddd_sms"), "17")
    telefone["limite_caracteres_sms"] = _to_int(telefone.get("limite_caracteres_sms"), 145, 30, 160)

    avancado = merged.get("avancado", {})
    allowed_captura = {item["id"] for item in SISTEMAS_CAPTURA_PADRAO}
    allowed_word = {item["id"] for item in VERSOES_WORD_PADRAO}
    allowed_email = {item["id"] for item in FORMATOS_EMAIL_PADRAO}
    avancado["sistema_captura_imagens"] = _normalize_choice(
        avancado.get("sistema_captura_imagens"), allowed_captura, "EasyCapture"
    )
    avancado["versao_word"] = _normalize_choice(avancado.get("versao_word"), allowed_word, "Word 2000")
    avancado["formato_envio_email"] = _normalize_choice(
        avancado.get("formato_envio_email"), allowed_email, "formatado_com_imagens"
    )
    avancado["qtd_imagens_odontograma"] = _to_int(
        avancado.get("qtd_imagens_odontograma"), 40, 1, 200
    )
    avancado["habilitar_validacao_cpf"] = _to_bool(avancado.get("habilitar_validacao_cpf"), True)
    avancado["bloquear_duplicidade_cpf"] = _to_bool(avancado.get("bloquear_duplicidade_cpf"), True)
    avancado["habilitar_mensagens_depuracao"] = _to_bool(
        avancado.get("habilitar_mensagens_depuracao"), True
    )
    avancado["ignorar_copias_driver"] = _to_bool(avancado.get("ignorar_copias_driver"), False)
    avancado["salvar_arquivos_myeasy"] = _to_bool(avancado.get("salvar_arquivos_myeasy"), False)
    avancado["atualizar_agenda_automaticamente"] = _to_bool(
        avancado.get("atualizar_agenda_automaticamente"), True
    )
    avancado["exigir_orcamento_aprovado"] = _to_bool(
        avancado.get("exigir_orcamento_aprovado"), False
    )
    avancado["habilitar_dente_3d"] = _to_bool(avancado.get("habilitar_dente_3d"), True)
    avancado["habilitar_cep_online"] = _to_bool(avancado.get("habilitar_cep_online"), True)
    avancado["enviar_somente_num_paciente_servico_protese"] = _to_bool(
        avancado.get("enviar_somente_num_paciente_servico_protese"), False
    )

    merged["clinica"] = clinica
    merged["financeiro"] = financeiro
    merged["seguranca"] = seguranca
    merged["data"] = data_cfg
    merged["local"] = local_cfg
    merged["telefone_sms"] = telefone
    merged["avancado"] = avancado
    return merged


def _carregar_opcoes_auxiliares(db: Session, clinica_id: int) -> dict:
    cobrancas = (
        db.query(ItemAuxiliar)
        .filter(
            ItemAuxiliar.clinica_id == clinica_id,
            ItemAuxiliar.tipo == "Tipos de cobrança",
        )
        .order_by(ItemAuxiliar.descricao.asc())
        .all()
    )
    categorias = (
        db.query(CategoriaFinanceira)
        .filter(CategoriaFinanceira.clinica_id == clinica_id)
        .order_by(CategoriaFinanceira.nome.asc())
        .all()
    )
    return {
        "indices": listar_indices(db, clinica_id, include_inativos=True),
        "formatos_data": [dict(x) for x in FORMATOS_DATA_PADRAO],
        "formatos_email": [dict(x) for x in FORMATOS_EMAIL_PADRAO],
        "sistemas_captura": [dict(x) for x in SISTEMAS_CAPTURA_PADRAO],
        "versoes_word": [dict(x) for x in VERSOES_WORD_PADRAO],
        "tipos_cobranca": [
            {"codigo": str(x.codigo or "").strip(), "descricao": str(x.descricao or "").strip()}
            for x in cobrancas
        ],
        "categorias_financeiras": [
            {
                "id": c.id,
                "nome": c.nome,
                "tipo": c.tipo,
                "grupo_id": c.grupo_id,
            }
            for c in categorias
        ],
    }


def _garantir_admin(current_user: Usuario) -> None:
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Acesso restrito para administradores.")


def _carregar_clinica(db: Session, clinica_id: int) -> Clinica:
    clinica = db.query(Clinica).filter(Clinica.id == clinica_id).first()
    if not clinica:
        raise HTTPException(status_code=404, detail="Clinica nao encontrada.")
    return clinica


@router.get("")
def obter_opcoes_sistema(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _garantir_admin(current_user)
    clinica = _carregar_clinica(db, current_user.clinica_id)
    raw = _load_json(clinica)
    values = _sanitize_values(raw)
    values["clinica"]["nome"] = values["clinica"]["nome"] or clinica.nome
    values["clinica"]["cnpj"] = values["clinica"]["cnpj"] or (clinica.cnpj or "")
    now = datetime.now()
    values["data"]["data_atual"] = now.strftime("%d/%m/%Y")
    values["data"]["hora_atual"] = now.strftime("%H:%M")
    options = _carregar_opcoes_auxiliares(db, current_user.clinica_id)
    return {
        "values": _sanitize_response(values),
        "options": options,
    }


@router.patch("")
def atualizar_opcoes_sistema(
    payload: SystemOptionsUpdateRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _garantir_admin(current_user)
    clinica = _carregar_clinica(db, current_user.clinica_id)
    values = _sanitize_values(payload.values or {})

    nome = str((values.get("clinica") or {}).get("nome") or "").strip()
    if nome:
        clinica.nome = nome
    clinica.cnpj = (values.get("clinica") or {}).get("cnpj")

    clinica.opcoes_sistema_json = _dump_json(values)
    db.add(clinica)
    db.commit()
    db.refresh(clinica)

    now = datetime.now()
    values["data"]["data_atual"] = now.strftime("%d/%m/%Y")
    values["data"]["hora_atual"] = now.strftime("%H:%M")
    options = _carregar_opcoes_auxiliares(db, current_user.clinica_id)
    return {
        "detail": "Opções do sistema atualizadas com sucesso.",
        "values": _sanitize_response(values),
        "options": options,
    }
