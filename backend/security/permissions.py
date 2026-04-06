import csv
import json
import unicodedata
from pathlib import Path


TIPO_USUARIO_CLINICA = "Clínica"
TIPO_USUARIO_DENTISTA = "Cirurgião dentista"

PERMISSION_LEVELS = ("desabilitado", "protegido", "habilitado")
MODULE_PERMISSION_SCHEMA = [
    {"codigo": "usuarios", "nome": "Usuários"},
    {"codigo": "prestadores", "nome": "Prestadores"},
    {"codigo": "agenda", "nome": "Agenda"},
    {"codigo": "financeiro", "nome": "Financeiro"},
    {"codigo": "materiais", "nome": "Materiais"},
    {"codigo": "procedimentos", "nome": "Procedimentos"},
    {"codigo": "anamnese", "nome": "Anamnese"},
    {"codigo": "relatorios", "nome": "Relatórios"},
    {"codigo": "configuracao", "nome": "Configuração"},
]

ACCESS_PROFILE_SCHEMA = [
    {"codigo": "admin", "nome": "Administrador", "tipo_usuario": "", "is_admin": True},
    {"codigo": "clinica", "nome": "Clínica", "tipo_usuario": TIPO_USUARIO_CLINICA, "is_admin": False},
    {"codigo": "dentista", "nome": "Cirurgião dentista", "tipo_usuario": TIPO_USUARIO_DENTISTA, "is_admin": False},
    {"codigo": "auxiliar", "nome": "Auxiliar odontológico(a)", "tipo_usuario": "Auxiliar odontológico(a)", "is_admin": False},
    {"codigo": "func_admin", "nome": "Funcionário(a) administrativo(a)", "tipo_usuario": "Funcionário(a) administrativo(a)", "is_admin": False},
    {"codigo": "gerente_admin", "nome": "Gerente administrativo", "tipo_usuario": "Gerente administrativo", "is_admin": False},
    {"codigo": "atendente", "nome": "Atendente", "tipo_usuario": "Atendente", "is_admin": False},
]

MODULE_FUNCTION_HINTS = {
    "usuarios": [
        "Inserir usuário",
        "Alterar usuário",
        "Eliminar usuário",
        "Alterar senha",
        "Configurar permissões",
    ],
    "prestadores": [
        "Inserir prestador",
        "Alterar prestador",
        "Eliminar prestador",
        "Configurar credenciamento",
        "Configurar comissão",
    ],
    "agenda": [
        "Inserir agendamento",
        "Alterar agendamento",
        "Eliminar agendamento",
        "Agenda de contatos",
        "Quadro de avisos",
        "Controle de retornos",
    ],
    "financeiro": [
        "Inserir lançamento",
        "Alterar lançamento",
        "Eliminar lançamento",
        "Baixa de lançamento",
        "Emitir recibo",
        "Contas a receber",
        "Comissões internas",
    ],
    "materiais": [
        "Inserir item",
        "Alterar item",
        "Eliminar item",
        "Inserir movimentação",
        "Alterar movimentação",
        "Eliminar movimentação",
    ],
    "procedimentos": [
        "Inserir intervenções",
        "Alterar intervenções",
        "Eliminar intervenções",
        "Criação de tratamento",
        "Alteração de tratamento",
        "Orçamento",
        "Especialidades",
    ],
    "anamnese": [
        "Alterar resposta",
        "Inserir medicamento",
        "Alterar medicamento",
        "Eliminar medicamento",
        "Restrições terapêuticas",
        "Questionários de anamnese",
    ],
    "relatorios": [
        "Pesquisa pacientes",
        "Pesquisa contatos",
        "Tratamentos",
        "Financeiros",
        "Estatísticos",
        "Agendas",
        "Estoques",
        "Protéticos",
        "Fichas em branco",
        "Mala direta",
    ],
    "configuracao": [
        "Preferências",
        "Tabelas auxiliares",
        "Convênios e planos",
        "Unidades de atendimento",
        "Chat interno",
    ],
}

ROOT_DIR = Path(__file__).resolve().parents[3]
EASY_MODULES_CSV = ROOT_DIR / "sis_modulo_sql.csv"
EASY_FUNCOES_CSV = ROOT_DIR / "sis_funcao_sql.csv"
_EASY_SCHEMA_CACHE: dict | None = None


def _normalize_level(value: str | None) -> str:
    txt = str(value or "").strip().lower()
    return txt if txt in PERMISSION_LEVELS else "desabilitado"


def _resolve_mapping_for_module(name: str) -> str:
    base = name.strip().lower()
    if base.startswith("odontograma") or base.startswith("tratamento") or base.startswith("tratamento - orçamento"):
        return "procedimentos"
    if base.startswith("especialidades"):
        return "procedimentos"
    if base.startswith("cadastro - ficha de histórico"):
        return "procedimentos"
    if base.startswith("cadastro - dados pessoais"):
        return "procedimentos"
    if base.startswith("cadastro - dados complementares"):
        return "procedimentos"
    if base.startswith("cadastro - anotações do paciente"):
        return "procedimentos"
    if base.startswith("cadastro - controle de protéticos"):
        return "procedimentos"
    if base.startswith("configuração - tabelas de intervenções"):
        return "procedimentos"
    if base.startswith("configuração - tabela de procedimentos genéricos"):
        return "procedimentos"
    if base.startswith("configuração - símbolos gráficos"):
        return "procedimentos"
    if base.startswith("configuração - tabelas de serviços de prótese"):
        return "procedimentos"

    if base.startswith("agenda -"):
        return "agenda"
    if base.startswith("configuração - agendas"):
        return "agenda"
    if base.startswith("cadastro - controle de retornos"):
        return "agenda"

    if base.startswith("cadastro - ficha de anamnese"):
        return "anamnese"
    if base.startswith("configuração - anamnese"):
        return "anamnese"
    if base.startswith("configuração - tabela de doenças"):
        return "anamnese"
    if base.startswith("cadastro - restrições terapêuticas"):
        return "anamnese"

    if base.startswith("financeiro -"):
        return "financeiro"
    if base.startswith("configuração - índices financeiros"):
        return "financeiro"
    if base.startswith("configuração - plano de contas"):
        return "financeiro"

    if base.startswith("cadastro - controle de estoque"):
        return "materiais"
    if base.startswith("configuração - tabelas de materiais"):
        return "materiais"

    if base.startswith("relatório -") or base.startswith("relatorio -"):
        return "relatorios"
    if base.startswith("configuração - relatórios"):
        return "relatorios"
    if base.startswith("configuração - etiquetas"):
        return "relatorios"

    if base.startswith("cadastro - prestadores"):
        return "prestadores"

    if base.startswith("configuração -"):
        return "configuracao"
    if base.startswith("cadastro -"):
        return "configuracao"
    if base.startswith("ferramentas -"):
        return "configuracao"
    return "configuracao"


def _load_easy_permission_schema() -> dict | None:
    global _EASY_SCHEMA_CACHE
    if _EASY_SCHEMA_CACHE is not None:
        return _EASY_SCHEMA_CACHE
    if not EASY_MODULES_CSV.exists() or not EASY_FUNCOES_CSV.exists():
        _EASY_SCHEMA_CACHE = None
        return None

    modules = []
    with EASY_MODULES_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                mod_id = int(row.get("ID_MODULO") or 0)
            except Exception:
                mod_id = 0
            nome = str(row.get("NOME_MODULO") or "").strip()
            if mod_id <= 0 or not nome:
                continue
            modules.append({"id": mod_id, "codigo": str(mod_id), "nome": nome})

    functions_by_module: dict[str, list[dict]] = {}
    functions_flat: dict[str, dict] = {}
    with EASY_FUNCOES_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                func_id = int(row.get("ID_FUNCAO") or 0)
            except Exception:
                func_id = 0
            try:
                mod_id = int(row.get("ID_MODULO") or 0)
            except Exception:
                mod_id = 0
            nome = str(row.get("NOME_FUNCAO") or "").strip()
            if func_id <= 0 or mod_id <= 0 or not nome:
                continue
            item = {"id": func_id, "codigo": str(func_id), "nome": nome, "modulo_id": mod_id}
            key = str(mod_id)
            functions_by_module.setdefault(key, []).append(item)
            functions_flat[str(func_id)] = item

    module_map = {str(mod["id"]): _resolve_mapping_for_module(mod["nome"]) for mod in modules}

    _EASY_SCHEMA_CACHE = {
        "modules": modules,
        "functions_by_module": functions_by_module,
        "functions_flat": functions_flat,
        "module_map": module_map,
        "levels": list(PERMISSION_LEVELS),
    }
    return _EASY_SCHEMA_CACHE


def get_easy_permission_schema() -> dict | None:
    return _load_easy_permission_schema()


def compute_internal_permissions_from_easy(easy_modules: dict[str, str]) -> dict[str, str]:
    schema = _load_easy_permission_schema()
    internal = {item["codigo"]: "desabilitado" for item in MODULE_PERMISSION_SCHEMA}
    if not schema:
        return internal
    module_map = schema.get("module_map", {})

    buckets: dict[str, list[str]] = {}
    for mod_id, level in (easy_modules or {}).items():
        internal_code = module_map.get(str(mod_id))
        if not internal_code:
            continue
        buckets.setdefault(internal_code, []).append(_normalize_level(level))

    for codigo, levels in buckets.items():
        normalized = {lvl for lvl in levels}
        if "protegido" in normalized:
            internal[codigo] = "protegido"
        elif "habilitado" in normalized:
            internal[codigo] = "habilitado"
        else:
            internal[codigo] = "desabilitado"
    return internal


def sanitize_easy_permissions(
    easy_modules: dict[str, str] | None,
    easy_funcoes: dict[str, str] | None,
) -> tuple[dict[str, str], dict[str, str]]:
    schema = _load_easy_permission_schema()
    if not schema:
        return {}, {}
    allowed_modules = {str(item["id"]) for item in schema["modules"]}
    allowed_funcoes = set(schema["functions_flat"].keys())

    modules_out: dict[str, str] = {}
    for key, value in (easy_modules or {}).items():
        k = str(key)
        if k in allowed_modules:
            modules_out[k] = _normalize_level(value)

    funcoes_out: dict[str, str] = {}
    for key, value in (easy_funcoes or {}).items():
        k = str(key)
        if k in allowed_funcoes:
            funcoes_out[k] = _normalize_level(value)

    return modules_out, funcoes_out


def extract_easy_permissions(
    raw_permissions: dict | None,
    internal_permissions: dict[str, str],
) -> tuple[dict[str, str], dict[str, str]]:
    schema = _load_easy_permission_schema()
    if not schema:
        return {}, {}
    raw = raw_permissions if isinstance(raw_permissions, dict) else {}
    easy_modules_raw = raw.get("easy_modules") if isinstance(raw.get("easy_modules"), dict) else None
    easy_funcoes_raw = raw.get("easy_funcoes") if isinstance(raw.get("easy_funcoes"), dict) else None
    if easy_modules_raw or easy_funcoes_raw:
        return sanitize_easy_permissions(easy_modules_raw or {}, easy_funcoes_raw or {})

    module_map = schema.get("module_map", {})
    easy_modules: dict[str, str] = {}
    for mod in schema["modules"]:
        mod_id = str(mod["id"])
        internal_code = module_map.get(mod_id, "")
        easy_modules[mod_id] = _normalize_level(internal_permissions.get(internal_code))
    return easy_modules, {}


def merge_permissions_payload(
    existing_raw: dict | None,
    internal_permissions: dict[str, str],
    easy_modules: dict[str, str] | None = None,
    easy_funcoes: dict[str, str] | None = None,
) -> dict[str, dict]:
    raw = existing_raw if isinstance(existing_raw, dict) else {}
    payload: dict[str, dict] = {"modules": dict(internal_permissions)}
    if easy_modules is not None or "easy_modules" in raw:
        payload["easy_modules"] = dict(easy_modules or raw.get("easy_modules") or {})
    if easy_funcoes is not None or "easy_funcoes" in raw:
        payload["easy_funcoes"] = dict(easy_funcoes or raw.get("easy_funcoes") or {})
    return payload


def _normalize_ascii(value: str | None) -> str:
    txt = " ".join(str(value or "").split()).strip().lower()
    if not txt:
        return ""
    # Compatibilidade para textos que possam vir com mojibake legado.
    txt = (
        txt.replace("ã£", "ã")
        .replace("ã¡", "á")
        .replace("ã©", "é")
        .replace("ã³", "ó")
        .replace("ã§", "ç")
        .replace("Ã£", "ã")
        .replace("Ã¡", "á")
        .replace("Ã©", "é")
        .replace("Ã³", "ó")
        .replace("Ã§", "ç")
    )
    normalized = unicodedata.normalize("NFKD", txt)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_tipo_usuario(value: str | None) -> str:
    txt = " ".join(str(value or "").split()).strip()
    if not txt:
        return ""
    low = _normalize_ascii(txt)
    aliases = {
        "clinica": TIPO_USUARIO_CLINICA,
        "cirurgiao dentista": TIPO_USUARIO_DENTISTA,
        "dentista": TIPO_USUARIO_DENTISTA,
        "funcionario(a) administrativo(a)": "Funcionário(a) administrativo(a)",
        "gerente administrativo": "Gerente administrativo",
        "auxiliar odontologico(a)": "Auxiliar odontológico(a)",
        "atendente": "Atendente",
        "protetico": "Protético",
        "perito": "Perito",
        "crc": "CRC",
        "thd": "THD",
    }
    return aliases.get(low, txt)


def parse_permissions_json(value: str | None) -> dict:
    txt = str(value or "").strip()
    if not txt:
        return {}
    try:
        data = json.loads(txt)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def dump_permissions_json(value: dict | None) -> str | None:
    if not value:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def default_permissions(tipo_usuario: str | None, is_admin: bool) -> dict:
    tipo = normalize_tipo_usuario(tipo_usuario)
    if is_admin:
        return {item["codigo"]: "habilitado" for item in MODULE_PERMISSION_SCHEMA}
    if tipo == TIPO_USUARIO_DENTISTA:
        return {
            "usuarios": "desabilitado",
            "prestadores": "desabilitado",
            "agenda": "habilitado",
            "financeiro": "protegido",
            "materiais": "habilitado",
            "procedimentos": "habilitado",
            "anamnese": "habilitado",
            "relatorios": "protegido",
            "configuracao": "desabilitado",
        }
    if tipo == TIPO_USUARIO_CLINICA:
        return {
            "usuarios": "protegido",
            "prestadores": "protegido",
            "agenda": "habilitado",
            "financeiro": "protegido",
            "materiais": "habilitado",
            "procedimentos": "habilitado",
            "anamnese": "habilitado",
            "relatorios": "protegido",
            "configuracao": "protegido",
        }
    if tipo in {"Gerente administrativo", "Funcionário(a) administrativo(a)"}:
        return {
            "usuarios": "desabilitado",
            "prestadores": "protegido",
            "agenda": "habilitado",
            "financeiro": "protegido",
            "materiais": "protegido",
            "procedimentos": "protegido",
            "anamnese": "protegido",
            "relatorios": "protegido",
            "configuracao": "protegido",
        }
    return {
        "usuarios": "desabilitado",
        "prestadores": "desabilitado",
        "agenda": "habilitado",
        "financeiro": "desabilitado",
        "materiais": "desabilitado",
        "procedimentos": "desabilitado",
        "anamnese": "habilitado",
        "relatorios": "desabilitado",
        "configuracao": "desabilitado",
    }


def sanitize_permissions(
    value: dict | None,
    *,
    tipo_usuario: str | None = None,
    is_admin: bool = False,
) -> dict:
    base = default_permissions(tipo_usuario, is_admin)
    if isinstance(value, dict) and isinstance(value.get("modules"), dict):
        incoming = value.get("modules") or {}
    else:
        incoming = value if isinstance(value, dict) else {}
    allowed_modules = {item["codigo"] for item in MODULE_PERMISSION_SCHEMA}
    sanitized = {}
    for codigo in allowed_modules:
        nivel = str(incoming.get(codigo, base.get(codigo, "desabilitado")) or "").strip().lower()
        sanitized[codigo] = nivel if nivel in PERMISSION_LEVELS else base.get(codigo, "desabilitado")
    return sanitized


def get_module_access_level(usuario, module_code: str) -> str:
    if getattr(usuario, "is_admin", False):
        return "habilitado"
    current = sanitize_permissions(
        parse_permissions_json(getattr(usuario, "permissoes_json", None)),
        tipo_usuario=getattr(usuario, "tipo_usuario", None),
        is_admin=bool(getattr(usuario, "is_admin", False)),
    )
    return current.get(module_code, "desabilitado")


def user_can_access_module(usuario, module_code: str, *, allow_protected: bool = True) -> bool:
    nivel = get_module_access_level(usuario, module_code)
    if nivel == "habilitado":
        return True
    if allow_protected and nivel == "protegido":
        return True
    return False


def get_access_profile_templates() -> list[dict]:
    templates = []
    for item in ACCESS_PROFILE_SCHEMA:
        tipo_usuario = item.get("tipo_usuario")
        is_admin = bool(item.get("is_admin"))
        templates.append(
            {
                "codigo": item.get("codigo"),
                "nome": item.get("nome"),
                "tipo_usuario": tipo_usuario,
                "is_admin": is_admin,
                "permissoes": sanitize_permissions({}, tipo_usuario=tipo_usuario, is_admin=is_admin),
            }
        )
    return templates


def get_module_function_hints() -> dict:
    return {codigo: list(funcoes) for codigo, funcoes in MODULE_FUNCTION_HINTS.items()}
