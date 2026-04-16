import re
import csv
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import bindparam, func, text

from models.anamnese import AnamnesePergunta, AnamneseQuestionario
from models.clinica import Clinica
from models.convenio_odonto import ConvenioOdonto, PlanoOdonto
from models.financeiro import CategoriaFinanceira, GrupoFinanceiro, ItemAuxiliar, Lancamento
from models.material import ListaMaterial, Material
from models.prestador_odonto import PrestadorOdonto
from models.procedimento import Procedimento, ProcedimentoMaterial
from models.procedimento_generico import ProcedimentoGenerico
from models.procedimento_tabela import ProcedimentoTabela
from models.usuario import Usuario
from seeds.procedimentos_genericos import seed_procedimentos_genericos
from seeds.procedimentos_padrao import seed_procedimentos
from seeds.simbolos_graficos import seed_simbolos_graficos
from security.permissions import dump_permissions_json, sanitize_permissions
from security.system_accounts import (
    SYSTEM_PRESTADOR_CODIGO,
    SYSTEM_PRESTADOR_SOURCE_ID,
    SYSTEM_PRESTADOR_TIPO,
    SYSTEM_USER_CODIGO,
    SYSTEM_USER_NOME,
    SYSTEM_USER_TIPO,
    build_system_user_email,
)
from services.access_profiles_service import ensure_access_profiles
from services.procedimentos_legado_service import resolver_codigo_generico_particular_snapshot
from services.etiquetas_service import garantir_modelos_etiqueta_clinica, garantir_padroes_etiqueta
from services.indices_service import garantir_indices_padrao_clinica
from services.simbolos_service import carregar_mapa_simbolos_por_legacy_id
from security.hash import hash_password

DEFAULT_LIST_NAME = "Tabela Brana"
DEFAULT_LIST_NAME_FALLBACK = "LISTA PADRÃO"
DEFAULT_LIST_NAME_LEGACY = "LISTA PADRAO"
DEFAULT_LIST_NAMES = (DEFAULT_LIST_NAME, DEFAULT_LIST_NAME_FALLBACK, DEFAULT_LIST_NAME_LEGACY)
LEGACY_DEFAULT_LIST_NAME = "Tabela modelo"
HOSTED_DEFAULT_LIST_NAMES = (DEFAULT_LIST_NAME, DEFAULT_LIST_NAME_FALLBACK, DEFAULT_LIST_NAME_LEGACY, LEGACY_DEFAULT_LIST_NAME)
PRIVATE_TABLE_CODE = 4
PRIVATE_TABLE_NAME = "PARTICULAR"
ESPECIALIDADE_RAW_PATH = Path(__file__).resolve().parents[3] / "Dados" / "Dist" / "_ESPECIALIDADE.raw"
RAW_DIST_DIR = Path(__file__).resolve().parents[3] / "Dados" / "Dist"
HOSTED_SEED_DIR = Path(__file__).resolve().parents[1] / "backups" / "brana_saas_full_20260313_234848" / "data"
PARTICULAR_SEED_PATH = Path(__file__).resolve().parents[3] / "Dados" / "particular_336_procedimentos.csv"
AUX_SQL_SEED_PATH = Path(__file__).resolve().parents[3] / "Dados" / "auxiliares_easydental_seed.json"
CID_SEED_CLINICA_ID = 1
CONVENIOS_PLANOS_SEED_CLINICA_ID = 1
SPECIALIDADE_SQL_SNAPSHOT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "easy_especialidades_atual_snapshot.json"
FASES_SQL_SNAPSHOT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "easy_fases_procedimento_atual_snapshot.json"
TIPOS_COBRANCA_SQL_SNAPSHOT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "easy_tipos_cobranca_atual_snapshot.json"
TIPOS_MATERIAL_SQL_SNAPSHOT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "easy_tipos_material_atual_snapshot.json"
UNIDADES_MEDIDA_SQL_SNAPSHOT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "easy_unidades_medida_atual_snapshot.json"
TIPOS_USO_SQL_SNAPSHOT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "easy_tipos_uso_atual_snapshot.json"
TIPOS_APRESENTACAO_SQL_SNAPSHOT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "easy_tipos_apresentacao_atual_snapshot.json"
PARTICULAR_SQL_SNAPSHOT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "easy_particular_atual_snapshot.json"
RAW_AUX_TIPO_ARQUIVO = {
    "Bancos": "_BANCO.raw",
    "Bairro": "_BAIRRO.raw",
    "Cidade": "_CIDADE.raw",
    "Especialidade": "_ESPECIALIDADE.raw",
    "Estado civil": "_ESTADO_CIVIL.raw",
    "Fabricantes": "_FABRICANTE.raw",
    "Fase procedimento": "_FASE_PROCEDIMENTO.raw",
    "Índices de moeda": "_INDICE.raw",
    "Grupo de medicamento": "DEF_GRUPO.raw",
    "Motivo de atestado": "_MOTIVO_ATESTADO.raw",
    "Motivo de retorno": "_MOTIVO_RETORNO.raw",
    "Palavra chave": "_PALAVRA_CHAVE.raw",
    "Prefixo pessoais": "_PREFIXO_PESSOA.raw",
    "Situação do agendamento": "_STATUS_AGENDA.raw",
    "Situação do paciente": "_STATUS_PACIENTE.raw",
    "Tipos de apresentação": "_TIPO_APRESENTACAO.raw",
    "Tipos de cobrança": "_TIPO_COBRANCA.raw",
    "Tipos de contato": "_TIPO_CONTATO.raw",
    "Tipos de indicação": "_TIPO_INDICA.raw",
    "Tipos de logradouro": "_TIPO_LOGRADOURO.raw",
    "Tipos de material": "_TIPO_MAT.raw",
    "Tipos de pagamento": "_TIPO_PAGTO.raw",
    "Tipos de uso": "_TIPO_USO.raw",
    "Tipos de usuário": "_TIPO_USUARIO.raw",
    "Unidades de medida": "_UNID_MEDIDA.raw",
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
RAW_AUX_SEM_ARQUIVO = {
    "Bairro",
    "Cidade",
    "Fabricantes",
    "Grupo de medicamento",
    "Motivo de retorno",
    "Palavra chave",
    "Tipos de cobrança",
}
_AUX_RAW_CACHE = None
SNAPSHOT_SQL_AUXILIARES = {
    "Especialidade": SPECIALIDADE_SQL_SNAPSHOT_PATH,
    "Fase procedimento": FASES_SQL_SNAPSHOT_PATH,
    "Tipos de cobrança": TIPOS_COBRANCA_SQL_SNAPSHOT_PATH,
    "Tipos de material": TIPOS_MATERIAL_SQL_SNAPSHOT_PATH,
    "Unidades de medida": UNIDADES_MEDIDA_SQL_SNAPSHOT_PATH,
    "Tipos de uso": TIPOS_USO_SQL_SNAPSHOT_PATH,
    "Tipos de apresentação": TIPOS_APRESENTACAO_SQL_SNAPSHOT_PATH,
}
ESPECIALIDADES_FALLBACK = [
    ("01", "Dentística"),
    ("02", "Prótese"),
    ("03", "Endodontia"),
    ("04", "Periodontia"),
    ("05", "Gerais"),
    ("06", "Cirurgia"),
    ("07", "Ortodontia"),
    ("08", "Prevenção"),
    ("09", "Odontopediatria"),
    ("10", "Diagnóstico"),
    ("11", "Radiologia"),
    ("12", "Estética"),
    ("13", "Implantodontia"),
]
ANAMNESE_QUESTIONARIO_PADRAO = "Principal"
ANAMNESE_PERGUNTAS_PADRAO = [
    "Esta bem de saude no momento?",
    "Quando fez seu ultimo tratamento medico?",
    "Esta atualmente em tratamento medico?",
    "Apresenta alergia a medicamentos? Quais?",
    "Possui alguma doenca grave? Qual?",
    "Esta tomando algum medicamento? Qual?",
    "Quando fez seu ultimo tratamento dentario?",
    "Sente dificuldade em abrir a boca",
    "Range os dentes a noite?",
    "Aperta os dentes costumeiramente?",
    "Alguma complicacao durante tratamento odontologico?",
    "Tem sinusite?",
    "Tem perdido peso nos ultimos meses?",
    "Tem ganho peso nos ultimos meses?",
    "Ja foi hospitalizado(a) alguma vez?",
    "Foi submetido(a) a cirurgia?",
    "Ja recebeu transfusao de sangue?",
]

MODEL_STORAGE_DIR = Path(__file__).resolve().parents[2] / "storage" / "modelos" / "clinicas"
MODELO_TIPOS_DIR = (
    "atestados",
    "receitas",
    "recibos",
    "etiquetas",
    "orcamentos",
    "email_agenda",
    "whatsapp_agenda",
    "outros",
)


def _garantir_diretorios_modelos_clinica(clinica_id: int) -> None:
    base_clinica_dir = MODEL_STORAGE_DIR / str(int(clinica_id))
    for tipo in MODELO_TIPOS_DIR:
        (base_clinica_dir / tipo).mkdir(parents=True, exist_ok=True)


def _codigo_material_variantes(codigo):
    base = str(codigo or "").strip()
    if not base:
        return []
    variantes = [base]
    if base.isdigit():
        variantes.append(str(int(base)))
        variantes.append(base.zfill(5))
    return list(dict.fromkeys(variantes))


def _to_bool(value):
    return str(value or "").strip().lower() in {"1", "true", "t", "sim", "s", "yes", "y"}


def _to_int(value, default=0):
    try:
        texto = str(value or "").strip()
        if not texto:
            return default
        return int(float(texto))
    except Exception:
        return default


def _to_float(value, default=0.0):
    try:
        texto = str(value or "").strip()
        if not texto:
            return default
        return float(texto)
    except Exception:
        return default


def _seed_csv_rows(filename):
    path = HOSTED_SEED_DIR / filename
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _pick_hosted_seed_clinica_id(rows, clinica_field="clinica_id"):
    counts = {}
    for row in rows:
        clinica_id = _to_int(row.get(clinica_field), 0)
        if clinica_id <= 0:
            continue
        counts[clinica_id] = counts.get(clinica_id, 0) + 1
    if not counts:
        return 0
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _norm_texto(texto):
    base = str(texto or "").strip().lower()
    base = unicodedata.normalize("NFD", base)
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def _normalizar_nome_convenio(nome):
    txt = str(nome or "").strip()
    chave = _norm_texto(txt)
    mapa = {
        "telebr s": "Telebrás",
        "telebras": "Telebrás",
        "petrobr s": "Petrobrás",
        "petrobras": "Petrobrás",
    }
    return mapa.get(chave, txt)


def _extraia_textos_utf16(raw_bytes):
    pattern = re.compile(rb"(?:[\x20-\x7E\x80-\xFF]\x00){2,}")
    textos = []
    for m in pattern.finditer(raw_bytes):
        txt = m.group().decode("utf-16le", errors="ignore")
        txt = txt.replace("\x00", "").strip()
        if txt:
            textos.append(txt)
    return textos


def _limpa_texto_aux(txt):
    base = str(txt or "").replace("\ufeff", "").strip()
    if not base:
        return ""
    while base and ord(base[0]) < 32:
        base = base[1:]
    base = base.strip()
    base = re.sub(r"\s+", " ", base)
    return base.strip()


def _limpa_codigo_aux(txt):
    base = _limpa_texto_aux(txt)
    if not base:
        return ""
    base = base.strip(" \"'`")
    return base


def _limpa_descricao_aux(txt):
    base = _limpa_texto_aux(txt)
    base = re.sub(r"^[\"'$@,.;:()<>\\/-]+", "", base).strip()
    return base


def _mapear_forma_cobranca_easy(tipo_cobr):
    valor = int(tipo_cobr or 0)
    if valor == 1:
        return "ELEMENTO_FACE"
    if valor == 2:
        return "INTERVENCAO"
    return ""


def _carregar_mapa_simbolos_particular_snapshot() -> dict[str, dict[str, str]]:
    if not PARTICULAR_SQL_SNAPSHOT_PATH.exists():
        return {"por_codconv": {}, "por_desc": {}}
    try:
        payload = json.loads(PARTICULAR_SQL_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"por_codconv": {}, "por_desc": {}}

    simbolos_por_legacy = carregar_mapa_simbolos_por_legacy_id()
    por_codconv: dict[str, str] = {}
    por_desc: dict[str, str] = {}
    for row in payload if isinstance(payload, list) else []:
        if not isinstance(row, dict):
            continue
        try:
            nrosim = int(row.get("nrosim") or 0)
        except Exception:
            nrosim = 0
        if nrosim <= 0:
            continue
        codigo = simbolos_por_legacy.get(nrosim)
        if not codigo:
            continue
        codconv = _limpa_codigo_aux(row.get("codconv") or "")
        descricao = _limpa_descricao_aux(row.get("descricao") or "")
        if codconv and codconv not in por_codconv:
            por_codconv[codconv] = codigo
        if descricao:
            desc_norm = _norm_texto(descricao)
            if desc_norm and desc_norm not in por_desc:
                por_desc[desc_norm] = codigo
    return {"por_codconv": por_codconv, "por_desc": por_desc}


def _is_codigo_like(txt):
    base = _limpa_codigo_aux(txt)
    if not base or " " in base:
        return False
    if re.fullmatch(r"\d{1,6}", base):
        return True
    if re.fullmatch(r"[A-Z]{1,6}", base):
        return True
    if re.fullmatch(r"[A-Z0-9._/\-]{1,12}", base) and base.upper() == base:
        return True
    return False


def _split_codigo_descricao_inline(txt):
    base = _limpa_texto_aux(txt)
    m = re.match(r"^([0-9A-Za-z]{1,6})[\.\-:;, _]+(.+)$", base)
    if not m:
        return "", base
    return _limpa_codigo_aux(m.group(1)), _limpa_descricao_aux(m.group(2))


def _normaliza_pares_aux(pares):
    saida = []
    vistos = set()
    seq = 1
    for codigo, descricao in pares:
        cod = _limpa_codigo_aux(codigo)
        desc = _limpa_descricao_aux(descricao)
        if not desc:
            continue
        if not cod:
            cod = f"{seq:02d}"
        seq += 1
        if cod and len(cod) == 1 and cod.isdigit() and desc and not desc[0].isdigit():
            cod = f"0{cod}"
        if cod and desc and cod.isdigit():
            # Alguns RAW trazem ruido no inicio da descricao (ex.: 06"Texto ou 4Texto).
            while desc and (desc[0].isdigit() or desc[0] in " .-:;,\"'"):
                desc = desc[1:]
        key = (_norm_texto(cod), _norm_texto(desc))
        if key in vistos:
            continue
        vistos.add(key)
        saida.append((cod, desc))
    return saida


def _parse_aux_raw_padrao(strings):
    pares = []
    i = 0
    while i < len(strings):
        atual = strings[i]
        if _is_codigo_like(atual):
            codigo = atual
            if i + 1 < len(strings):
                prox = strings[i + 1]
                if not _is_codigo_like(prox):
                    pares.append((codigo, prox))
                    i += 2
                    continue
            pares.append((codigo, ""))
            i += 1
            continue

        if i + 1 < len(strings) and _is_codigo_like(strings[i + 1]):
            pares.append((strings[i + 1], atual))
            i += 2
            continue

        codigo_inline, desc_inline = _split_codigo_descricao_inline(atual)
        if codigo_inline and desc_inline:
            pares.append((codigo_inline, desc_inline))
        else:
            pares.append(("", atual))
        i += 1
    return _normaliza_pares_aux(pares)


def _parse_aux_raw_tipo_logradouro(strings):
    pares = []
    i = 0
    while i < len(strings):
        atual = _limpa_texto_aux(strings[i])
        prox = _limpa_texto_aux(strings[i + 1]) if i + 1 < len(strings) else ""

        # Formato observado no Easy (_TIPO_LOGRADOURO.raw):
        # 00108, BAL, 00109, BC, ...
        if re.fullmatch(r"\d{3,6}", atual or "") and prox:
            sigla = _limpa_codigo_aux(prox)
            if sigla and not re.fullmatch(r"\d{1,6}", sigla):
                pares.append((sigla, sigla))
                i += 2
                continue

        token = _limpa_codigo_aux(atual)
        if token and not re.fullmatch(r"\d{1,6}", token):
            pares.append((token, token))
        i += 1

    return _normaliza_pares_aux(pares)


def _parse_aux_raw_bancos(strings):
    pares = []
    i = 0
    while i < len(strings):
        atual = _limpa_texto_aux(strings[i])
        if not atual:
            i += 1
            continue

        m_num = re.fullmatch(r"(\d{3})", atual)
        if m_num:
            codigo = m_num.group(1)
            descricao = ""
            if i + 1 < len(strings):
                prox = _limpa_descricao_aux(strings[i + 1])
                if prox and not re.match(r"^\d{3}([^\d].*)?$", prox):
                    descricao = prox
                    i += 1
            if descricao:
                pares.append((codigo, descricao))
            i += 1
            continue

        m = re.match(r"^(\d{3})(.*)$", atual)
        if m:
            codigo = m.group(1)
            resto = _limpa_descricao_aux(m.group(2))
            if not resto and i + 1 < len(strings):
                resto = _limpa_descricao_aux(strings[i + 1])
                if resto:
                    i += 1
            if resto:
                pares.append((codigo, resto))
        i += 1
    return _normaliza_pares_aux(pares)


def _parse_aux_raw_tipo_usuario(strings):
    pares = []
    seq = 1
    for raw in strings:
        base = _limpa_texto_aux(raw)
        if not base:
            continue
        desc = re.split(r"[$0@,]", base, maxsplit=1)[0].strip()
        desc = _limpa_descricao_aux(desc or base)
        if not desc:
            continue
        pares.append((f"{seq:02d}", desc))
        seq += 1
    return _normaliza_pares_aux(pares)


def _parse_aux_raw_sem_codigo(strings):
    pares = []
    seq = 1
    for s in strings:
        desc = _limpa_descricao_aux(s)
        if not desc:
            continue
        pares.append((f"{seq:02d}", desc))
        seq += 1
    return _normaliza_pares_aux(pares)


def _carregar_auxiliares_raw_por_tipo(tipo, arquivo):
    path = RAW_DIST_DIR / arquivo
    if not path.exists():
        return []
    try:
        strings = _extraia_textos_utf16(path.read_bytes())
    except Exception:
        return []
    if not strings:
        return []

    if arquivo == "_BANCO.raw":
        return _parse_aux_raw_bancos(strings)
    if arquivo == "_TIPO_LOGRADOURO.raw":
        return _parse_aux_raw_tipo_logradouro(strings)
    if arquivo == "_TIPO_USUARIO.raw":
        return _parse_aux_raw_tipo_usuario(strings)
    if arquivo in {"_ESTADO_CIVIL.raw", "_TIPO_CONTATO.raw"}:
        return _parse_aux_raw_sem_codigo(strings)
    return _parse_aux_raw_padrao(strings)


def _carregar_seed_auxiliares_raw():
    global _AUX_RAW_CACHE
    if _AUX_RAW_CACHE is not None:
        return _AUX_RAW_CACHE

    seed = {}
    for tipo, arquivo in RAW_AUX_TIPO_ARQUIVO.items():
        itens = _carregar_auxiliares_raw_por_tipo(tipo, arquivo)
        if itens:
            seed[tipo] = itens

    # Snapshot extraido direto do SQL do EasyDental, quando disponivel.
    if AUX_SQL_SEED_PATH.exists():
        try:
            payload = json.loads(AUX_SQL_SEED_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                for tipo, itens in payload.items():
                    pares = []
                    if isinstance(itens, list):
                        for item in itens:
                            if isinstance(item, (list, tuple)) and len(item) >= 2:
                                pares.append((item[0], item[1]))
                            elif isinstance(item, dict):
                                pares.append((item.get("codigo", ""), item.get("descricao", "")))
                    pares = _normaliza_pares_aux(pares)
                    if pares:
                        seed[str(tipo)] = pares
        except Exception:
            pass

    for tipo, path in SNAPSHOT_SQL_AUXILIARES.items():
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        pares = []
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    pares.append((item.get("codigo", ""), item.get("descricao", "")))
        pares = _normaliza_pares_aux(pares)
        if pares:
            seed[tipo] = pares

    seed.setdefault("Tipos de prestador", TIPOS_PRESTADOR_PADRAO)
    seed.setdefault("CBO-S", CBOS_PRESTADOR_PADRAO)
    _AUX_RAW_CACHE = seed
    return seed


def _parse_especialidades_raw(raw_bytes):
    starts = []
    total = len(raw_bytes)

    for pos in range(0, total - 12):
        registro_id = int.from_bytes(raw_bytes[pos : pos + 4], "little", signed=False)
        if not (1 <= registro_id <= 99):
            continue
        if raw_bytes[pos + 4 : pos + 6] != b"\x04\x00":
            continue
        codigo = f"{registro_id:02d}"
        if raw_bytes[pos + 6 : pos + 10] != codigo.encode("utf-16le"):
            continue
        nome_len = int.from_bytes(raw_bytes[pos + 10 : pos + 12], "little", signed=False)
        if nome_len <= 0 or pos + 12 + nome_len > total:
            continue
        starts.append(pos)

    especiais = []
    vistos = set()
    for inicio in starts:
        codigo = raw_bytes[inicio + 6 : inicio + 10].decode("utf-16le", errors="ignore").strip()
        nome_len = int.from_bytes(raw_bytes[inicio + 10 : inicio + 12], "little", signed=False)
        nome = raw_bytes[inicio + 12 : inicio + 12 + nome_len].decode("utf-16le", errors="ignore").strip()
        chave = _norm_texto(nome)
        if not codigo or not nome or not chave or chave in vistos:
            continue
        vistos.add(chave)
        especiais.append((codigo, nome))
    return especiais


def _carregar_seed_especialidades():
    if SPECIALIDADE_SQL_SNAPSHOT_PATH.exists():
        try:
            payload = json.loads(SPECIALIDADE_SQL_SNAPSHOT_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(payload, list):
                itens = _normaliza_pares_aux(
                    [(item.get("codigo", ""), item.get("descricao", "")) for item in payload if isinstance(item, dict)]
                )
                if itens:
                    return itens
        except Exception:
            pass
    if ESPECIALIDADE_RAW_PATH.exists():
        try:
            itens = _parse_especialidades_raw(ESPECIALIDADE_RAW_PATH.read_bytes())
            if itens:
                return itens
        except Exception:
            pass
    return ESPECIALIDADES_FALLBACK[:]


def _carregar_seed_materiais_hosted():
    listas = [row for row in _seed_csv_rows("lista_material.csv") if (row.get("nome") or "").strip() in HOSTED_DEFAULT_LIST_NAMES]
    materiais = _seed_csv_rows("material.csv")
    if not listas or not materiais:
        return []

    lista_ids_por_clinica = {}
    for row in listas:
        clinica_id = _to_int(row.get("clinica_id"), 0)
        lista_id = _to_int(row.get("id"), 0)
        if clinica_id > 0 and lista_id > 0:
            lista_ids_por_clinica.setdefault(clinica_id, []).append(lista_id)

    contagens = {
        clinica_id: sum(1 for item in materiais if _to_int(item.get("lista_id"), 0) in lista_ids)
        for clinica_id, lista_ids in lista_ids_por_clinica.items()
    }
    if not contagens:
        return []

    seed_clinica_id = sorted(contagens.items(), key=lambda item: (-item[1], item[0]))[0][0]
    lista_ids = set(lista_ids_por_clinica.get(seed_clinica_id, []))
    return [
        {
            "codigo": str(row.get("codigo") or "").strip(),
            "nome": str(row.get("nome") or "").strip(),
            "preco": _to_float(row.get("preco"), 0),
            "relacao": _to_float(row.get("relacao"), 0),
            "custo": _to_float(row.get("custo"), 0),
            "unidade_compra": str(row.get("unidade_compra") or "").strip(),
            "unidade_consumo": str(row.get("unidade_consumo") or "").strip(),
            "validade_dias": _to_int(row.get("validade_dias"), 0),
            "preferido": _to_bool(row.get("preferido")),
            "classificacao": str(row.get("classificacao") or "").strip(),
        }
        for row in materiais
        if _to_int(row.get("lista_id"), 0) in lista_ids
        and str(row.get("codigo") or "").strip()
        and str(row.get("nome") or "").strip()
    ]


def _carregar_seed_procedimentos_hosted_por_tabela():
    rows_proc = _seed_csv_rows("procedimento.csv")
    rows_links = _seed_csv_rows("procedimento_material.csv")
    rows_mats = _seed_csv_rows("material.csv")
    rows_listas = [
        row
        for row in _seed_csv_rows("lista_material.csv")
        if (row.get("nome") or "").strip() in HOSTED_DEFAULT_LIST_NAMES
    ]
    if not rows_proc:
        return {"exemplo": {"procedimentos": [], "links": []}, "particular": {"procedimentos": [], "links": []}}

    proc_seed_clinica = _pick_hosted_seed_clinica_id(rows_proc)
    link_seed_clinica = _pick_hosted_seed_clinica_id(rows_links)

    def _build_procedimentos(tabela_id: int):
        return [
            {
                "codigo": _to_int(row.get("codigo"), 0),
                "nome": str(row.get("nome") or "").strip(),
                "tempo": _to_int(row.get("tempo"), 0),
                "preco": _to_float(row.get("preco"), 0),
                "custo": _to_float(row.get("custo"), 0),
                "custo_lab": _to_float(row.get("custo_lab"), 0),
                "lucro_hora": _to_float(row.get("lucro_hora"), 0),
                "especialidade": str(row.get("especialidade") or "").strip(),
            }
            for row in rows_proc
            if _to_int(row.get("clinica_id"), 0) == proc_seed_clinica
            and _to_int(row.get("tabela_id"), 0) == tabela_id
            and _to_int(row.get("codigo"), 0) > 0
            and str(row.get("nome") or "").strip()
        ]

    procedimentos_exemplo = _build_procedimentos(1)

    procedimentos_particular = []
    mapa_simbolos_particular = _carregar_mapa_simbolos_particular_snapshot()
    codconv_simbolo = mapa_simbolos_particular.get("por_codconv", {})
    desc_simbolo = mapa_simbolos_particular.get("por_desc", {})

    particular_snapshot = None
    if PARTICULAR_SQL_SNAPSHOT_PATH.exists():
        try:
            particular_snapshot = json.loads(PARTICULAR_SQL_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        except Exception:
            particular_snapshot = None

    if isinstance(particular_snapshot, list) and particular_snapshot:
        for row in particular_snapshot:
            if not isinstance(row, dict):
                continue
            codconv = _limpa_codigo_aux(row.get("codconv") or "")
            codigo = _to_int(codconv, 0) if codconv else 0
            if codigo <= 0:
                codigo = _to_int(row.get("nroproctab"), 0)
            if codigo <= 0:
                continue
            descricao = _limpa_descricao_aux(row.get("descricao") or "")
            if not descricao:
                descricao = f"Procedimento {codigo:03d}"
            nrosim = _to_int(row.get("nrosim"), 0)
            simbolo_grafico = ""
            if codconv:
                simbolo_grafico = (
                    codconv_simbolo.get(codconv)
                    or codconv_simbolo.get(codconv.zfill(4))
                    or codconv_simbolo.get(codconv.zfill(5))
                    or ""
                )
            if not simbolo_grafico:
                simbolo_grafico = desc_simbolo.get(_norm_texto(descricao), "")
            simbolo_grafico_legacy_id = nrosim if simbolo_grafico and nrosim > 0 else None
            procedimentos_particular.append(
                {
                    "codigo": codigo,
                    "nome": descricao,
                    "tempo": 0,
                    "preco": _to_float(row.get("valor_paciente"), 0.0),
                    "custo": 0.0,
                    "custo_lab": 0.0,
                    "lucro_hora": 0.0,
                    "especialidade": f"{_to_int(row.get('especial'), 0):02d}" if _to_int(row.get("especial"), 0) > 0 else "",
                    "simbolo_grafico": simbolo_grafico,
                    "simbolo_grafico_legacy_id": simbolo_grafico_legacy_id,
                    "mostrar_simbolo": bool(simbolo_grafico),
                    "generico_codigo": resolver_codigo_generico_particular_snapshot(row.get("id_prc_gen")),
                    "forma_cobranca": _mapear_forma_cobranca_easy(_to_int(row.get("tipocobr"), 0)),
                    "garantia_meses": _to_int(row.get("garantia"), 0),
                    "preferido": _to_bool(row.get("preferido")),
                    "valor_repasse": _to_float(row.get("valor_repasse"), 0.0),
                    "inativo": _to_bool(row.get("inativo")),
                    "data_inclusao": _limpa_descricao_aux(row.get("data_inclusao") or ""),
                    "data_alteracao": _limpa_descricao_aux(row.get("data_alteracao") or ""),
                }
            )
    elif PARTICULAR_SEED_PATH.exists():
        with PARTICULAR_SEED_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                codconv = str(row.get("CODCONV") or "").strip()
                codigo = _to_int(codconv, 0) if codconv else 0
                if codigo <= 0:
                    codigo = _to_int(row.get("NROPROCTAB"), 0)
                if codigo <= 0:
                    continue
                descricao = _limpa_descricao_aux(row.get("DESCRICAO") or "")
                if not descricao:
                    descricao = f"Procedimento {codigo:03d}"
                codconv_key = _limpa_codigo_aux(codconv or "")
                simbolo_grafico = ""
                if codconv_key:
                    simbolo_grafico = (
                        codconv_simbolo.get(codconv_key)
                        or codconv_simbolo.get(codconv_key.zfill(4))
                        or codconv_simbolo.get(codconv_key.zfill(5))
                        or ""
                    )
                if not simbolo_grafico:
                    simbolo_grafico = desc_simbolo.get(_norm_texto(descricao), "")
                procedimentos_particular.append(
                    {
                        "codigo": codigo,
                        "nome": descricao,
                        "tempo": 0,
                        "preco": 0.0,
                        "custo": 0.0,
                        "custo_lab": 0.0,
                        "lucro_hora": 0.0,
                        "especialidade": "",
                        "simbolo_grafico": simbolo_grafico,
                        "simbolo_grafico_legacy_id": None,
                        "mostrar_simbolo": bool(simbolo_grafico),
                        "generico_codigo": "",
                        "forma_cobranca": "",
                        "garantia_meses": 0,
                        "preferido": False,
                        "valor_repasse": 0.0,
                        "inativo": False,
                        "data_inclusao": "",
                        "data_alteracao": "",
                    }
                )

    lista_ids_por_clinica = {
        _to_int(row.get("clinica_id"), 0): _to_int(row.get("id"), 0)
        for row in rows_listas
        if _to_int(row.get("clinica_id"), 0) > 0 and _to_int(row.get("id"), 0) > 0
    }
    lista_seed_id = lista_ids_por_clinica.get(link_seed_clinica, 0)
    mats_por_id = {
        _to_int(row.get("id"), 0): str(row.get("codigo") or "").strip()
        for row in rows_mats
        if _to_int(row.get("lista_id"), 0) == lista_seed_id
    }
    proc_codigo_por_id = {}
    proc_tabela_por_id = {}
    for row in rows_proc:
        if _to_int(row.get("clinica_id"), 0) != link_seed_clinica:
            continue
        pid = _to_int(row.get("id"), 0)
        if pid <= 0:
            continue
        proc_codigo_por_id[pid] = _to_int(row.get("codigo"), 0)
        proc_tabela_por_id[pid] = _to_int(row.get("tabela_id"), 0)

    links_exemplo = [
        {
            "procedimento_codigo": proc_codigo_por_id.get(_to_int(row.get("procedimento_id"), 0), 0),
            "material_codigo": mats_por_id.get(_to_int(row.get("material_id"), 0), ""),
            "quantidade": _to_float(row.get("quantidade"), 0),
        }
        for row in rows_links
        if _to_int(row.get("clinica_id"), 0) == link_seed_clinica
        and proc_tabela_por_id.get(_to_int(row.get("procedimento_id"), 0), 0) == 1
        and proc_codigo_por_id.get(_to_int(row.get("procedimento_id"), 0), 0) > 0
        and mats_por_id.get(_to_int(row.get("material_id"), 0), "")
        and _to_float(row.get("quantidade"), 0) > 0
    ]

    return {
        "exemplo": {"procedimentos": procedimentos_exemplo, "links": links_exemplo},
        "particular": {"procedimentos": procedimentos_particular, "links": []},
    }


def _carregar_seed_procedimentos_hosted():
    seeds = _carregar_seed_procedimentos_hosted_por_tabela()
    return seeds["exemplo"]


def _carregar_seed_financeiro_hosted():
    grupos_rows = _seed_csv_rows("grupo_financeiro.csv")
    categorias_rows = _seed_csv_rows("categoria_financeira.csv")
    itens_rows = _seed_csv_rows("item_auxiliar.csv")
    if not grupos_rows:
        return {"grupos": [], "categorias": [], "itens": [], "lancamentos": []}

    seed_clinica_id = _pick_hosted_seed_clinica_id(grupos_rows)
    grupos_seed = [row for row in grupos_rows if _to_int(row.get("clinica_id"), 0) == seed_clinica_id]
    grupo_nome_por_id = {
        _to_int(row.get("id"), 0): str(row.get("nome") or "").strip()
        for row in grupos_seed
        if _to_int(row.get("id"), 0) > 0 and str(row.get("nome") or "").strip()
    }
    categorias_seed = [row for row in categorias_rows if _to_int(row.get("clinica_id"), 0) == seed_clinica_id]
    itens_seed = [row for row in itens_rows if _to_int(row.get("clinica_id"), 0) == seed_clinica_id]

    return {
        "grupos": [
            {"nome": str(row.get("nome") or "").strip(), "tipo": str(row.get("tipo") or "").strip()}
            for row in grupos_seed
            if str(row.get("nome") or "").strip()
        ],
        "categorias": [
            {
                "nome": str(row.get("nome") or "").strip(),
                "tipo": str(row.get("tipo") or "").strip(),
                "tributavel": _to_int(row.get("tributavel"), 0),
                "grupo_nome": grupo_nome_por_id.get(_to_int(row.get("grupo_id"), 0), ""),
            }
            for row in categorias_seed
            if str(row.get("nome") or "").strip() and grupo_nome_por_id.get(_to_int(row.get("grupo_id"), 0), "")
        ],
        "itens": [
            {
                "tipo": str(row.get("tipo") or "").strip(),
                "codigo": str(row.get("codigo") or "").strip(),
                "descricao": str(row.get("descricao") or "").strip(),
            }
            for row in itens_seed
            if str(row.get("tipo") or "").strip() and str(row.get("codigo") or "").strip()
        ],
        "lancamentos": [],
    }


def _carregar_seed_materiais_clinica(db):
    sub = (
        db.query(
            ListaMaterial.id.label("lista_id"),
            func.count(Material.id).label("qtd"),
        )
        .outerjoin(Material, Material.lista_id == ListaMaterial.id)
        .filter(ListaMaterial.nome.in_(DEFAULT_LIST_NAMES))
        .group_by(ListaMaterial.id)
        .subquery()
    )
    row = db.query(sub.c.lista_id, sub.c.qtd).order_by(sub.c.qtd.desc(), sub.c.lista_id.asc()).first()
    if not row or int(row.qtd or 0) <= 0:
        return []
    mats = (
        db.query(Material)
        .filter(Material.lista_id == row.lista_id)
        .order_by(Material.codigo.asc(), Material.id.asc())
        .all()
    )
    return [
        {
            "codigo": str(m.codigo or "").strip(),
            "nome": str(m.nome or "").strip(),
            "preco": float(m.preco or 0),
            "relacao": float(m.relacao or 0),
            "custo": float(m.custo or 0),
            "unidade_compra": str(m.unidade_compra or "").strip(),
            "unidade_consumo": str(m.unidade_consumo or "").strip(),
            "validade_dias": int(m.validade_dias or 0),
            "preferido": bool(m.preferido),
            "classificacao": str(m.classificacao or "").strip(),
        }
        for m in mats
        if str(m.codigo or "").strip() and str(m.nome or "").strip()
    ]


def _carregar_seed_procedimentos_clinica(db):
    row = (
        db.query(Procedimento.clinica_id, func.count(Procedimento.id).label("qtd"))
        .group_by(Procedimento.clinica_id)
        .order_by(func.count(Procedimento.id).desc(), Procedimento.clinica_id.asc())
        .first()
    )
    if not row or int(row.qtd or 0) <= 0:
        return {"procedimentos": [], "links": []}

    clinica_id = int(row.clinica_id)
    procs = (
        db.query(Procedimento)
        .filter(Procedimento.clinica_id == clinica_id)
        .order_by(Procedimento.codigo.asc(), Procedimento.id.asc())
        .all()
    )
    procedimentos = [
        {
            "codigo": int(p.codigo or 0),
            "nome": str(p.nome or "").strip(),
            "tempo": int(p.tempo or 0),
            "preco": float(p.preco or 0),
            "custo": float(p.custo or 0),
            "custo_lab": float(p.custo_lab or 0),
            "lucro_hora": float(p.lucro_hora or 0),
            "especialidade": str(p.especialidade or "").strip(),
        }
        for p in procs
        if int(p.codigo or 0) > 0 and str(p.nome or "").strip()
    ]
    links_raw = (
        db.query(Procedimento.codigo, Material.codigo, ProcedimentoMaterial.quantidade)
        .join(Procedimento, Procedimento.id == ProcedimentoMaterial.procedimento_id)
        .join(Material, Material.id == ProcedimentoMaterial.material_id)
        .join(ListaMaterial, ListaMaterial.id == Material.lista_id)
        .filter(
            Procedimento.clinica_id == clinica_id,
            ListaMaterial.clinica_id == clinica_id,
        )
        .order_by(ProcedimentoMaterial.id.asc())
        .all()
    )
    links = [
        {
            "procedimento_codigo": int(x[0] or 0),
            "material_codigo": str(x[1] or "").strip(),
            "quantidade": float(x[2] or 0),
        }
        for x in links_raw
        if int(x[0] or 0) > 0 and str(x[1] or "").strip() and float(x[2] or 0) > 0
    ]
    return {"procedimentos": procedimentos, "links": links}


def _carregar_seed_financeiro_clinica(db):
    row = (
        db.query(Lancamento.clinica_id, func.count(Lancamento.id).label("qtd"))
        .group_by(Lancamento.clinica_id)
        .order_by(func.count(Lancamento.id).desc(), Lancamento.clinica_id.asc())
        .first()
    )
    if not row or int(row.qtd or 0) <= 0:
        return {"grupos": [], "categorias": [], "itens": [], "lancamentos": []}

    clinica_id = int(row.clinica_id)
    grupos = db.query(GrupoFinanceiro).filter(GrupoFinanceiro.clinica_id == clinica_id).order_by(GrupoFinanceiro.id.asc()).all()
    categorias = (
        db.query(CategoriaFinanceira)
        .join(GrupoFinanceiro, GrupoFinanceiro.id == CategoriaFinanceira.grupo_id)
        .filter(CategoriaFinanceira.clinica_id == clinica_id)
        .order_by(CategoriaFinanceira.id.asc())
        .all()
    )
    itens = db.query(ItemAuxiliar).filter(ItemAuxiliar.clinica_id == clinica_id).order_by(ItemAuxiliar.id.asc()).all()
    lancs = (
        db.query(Lancamento)
        .join(CategoriaFinanceira, CategoriaFinanceira.id == Lancamento.categoria_id)
        .join(GrupoFinanceiro, GrupoFinanceiro.id == CategoriaFinanceira.grupo_id)
        .filter(Lancamento.clinica_id == clinica_id)
        .order_by(Lancamento.id.asc())
        .all()
    )
    return {
        "grupos": [{"nome": g.nome, "tipo": g.tipo} for g in grupos if (g.nome or "").strip()],
        "categorias": [
            {
                "nome": c.nome,
                "tipo": c.tipo,
                "tributavel": int(c.tributavel or 0),
                "grupo_nome": c.grupo.nome if c.grupo else "",
            }
            for c in categorias
            if (c.nome or "").strip() and c.grupo
        ],
        "itens": [
            {"tipo": i.tipo, "codigo": i.codigo, "descricao": i.descricao}
            for i in itens
            if (i.tipo or "").strip() and (i.codigo or "").strip()
        ],
        "lancamentos": [
            {
                "categoria_nome": l.categoria.nome if l.categoria else "",
                "grupo_nome": l.categoria.grupo.nome if l.categoria and l.categoria.grupo else "",
                "historico": l.historico or "",
                "valor": float(l.valor or 0),
                "data_lancamento": l.data_lancamento or "",
                "data_pagamento": l.data_pagamento or "",
                "tipo": l.tipo or "debito",
                "situacao": l.situacao or "Aberto",
                "forma_pagamento": l.forma_pagamento,
                "conta": l.conta or "CLINICA",
                "data_vencimento": l.data_vencimento,
                "data_inclusao": l.data_inclusao,
                "data_alteracao": l.data_alteracao,
                "documento": l.documento,
                "referencia": l.referencia,
                "complemento": l.complemento,
                "tributavel": int(l.tributavel or 0),
                "parcelado": int(l.parcelado or 0),
                "qtd_parcelas": int(l.qtd_parcelas or 1),
                "parcela_atual": int(l.parcela_atual or 1),
            }
            for l in lancs
            if l.categoria and l.categoria.grupo
        ],
    }


def _carregar_seed_materiais(db):
    seed = _carregar_seed_materiais_clinica(db)
    return seed if seed else _carregar_seed_materiais_hosted()


def _carregar_seed_procedimentos(db):
    # A Tabela Exemplo deve sempre herdar o seed canônico empacotado no SaaS,
    # incluindo os vínculos de materiais. O seed "por clínica" pode vir
    # de contas que tenham procedimentos sem os vínculos completos.
    hosted_seed = _carregar_seed_procedimentos_hosted()
    if hosted_seed["procedimentos"]:
        return hosted_seed
    return _carregar_seed_procedimentos_clinica(db)


def _carregar_seed_procedimentos_particular(db):
    seeds = _carregar_seed_procedimentos_hosted_por_tabela()
    seed_particular = seeds["particular"]
    if seed_particular["procedimentos"]:
        return seed_particular
    return {"procedimentos": [], "links": []}


def _carregar_seed_financeiro(db):
    seed = _carregar_seed_financeiro_clinica(db)
    if seed["grupos"] and seed["categorias"]:
        return seed
    return _carregar_seed_financeiro_hosted()


def _upsert_materiais_na_lista(db, lista_id, materiais_seed):
    existentes = {m.codigo: m for m in db.query(Material).filter(Material.lista_id == lista_id).all()}
    for item in materiais_seed:
        codigo = item["codigo"]
        if codigo in existentes:
            mat = existentes[codigo]
            mat.nome = item["nome"]
            mat.preco = float(item["preco"] or 0)
            mat.relacao = float(item["relacao"] or 0)
            mat.custo = float(item["custo"] or 0)
            mat.unidade_compra = str(item.get("unidade_compra", "") or "").strip()
            mat.unidade_consumo = str(item.get("unidade_consumo", "") or "").strip()
            mat.validade_dias = int(item.get("validade_dias", 0) or 0)
            mat.preferido = bool(item.get("preferido", False))
            mat.classificacao = str(item.get("classificacao", "") or "").strip()
        else:
            db.add(
                Material(
                    codigo=codigo,
                    nome=item["nome"],
                    preco=float(item["preco"] or 0),
                    relacao=float(item["relacao"] or 0),
                    custo=float(item["custo"] or 0),
                    unidade_compra=str(item.get("unidade_compra", "") or "").strip(),
                    unidade_consumo=str(item.get("unidade_consumo", "") or "").strip(),
                    validade_dias=int(item.get("validade_dias", 0) or 0),
                    preferido=bool(item.get("preferido", False)),
                    classificacao=str(item.get("classificacao", "") or "").strip(),
                    lista_id=lista_id,
                )
            )


def _upsert_procedimentos_na_clinica(db, clinica_id, seed, reset_preco: bool = False):
    tabela_exemplo_id = 1
    existentes = {
        int(p.codigo): p
        for p in db.query(Procedimento)
        .filter(
            Procedimento.clinica_id == clinica_id,
            Procedimento.tabela_id == tabela_exemplo_id,
        )
        .all()
    }
    codigo_para_id = {}
    for item in seed["procedimentos"]:
        codigo = int(item["codigo"])
        preco_seed = 0.0 if reset_preco else float(item["preco"] or 0)
        if codigo in existentes:
            proc = existentes[codigo]
            proc.nome = item["nome"]
            proc.tempo = int(item["tempo"] or 0)
            proc.preco = preco_seed
            proc.custo = float(item["custo"] or 0)
            proc.custo_lab = float(item["custo_lab"] or 0)
            proc.lucro_hora = float(item["lucro_hora"] or 0)
            proc.especialidade = str(item.get("especialidade") or "").strip() or None
        else:
            proc = Procedimento(
                codigo=codigo,
                nome=item["nome"],
                tempo=int(item["tempo"] or 0),
                preco=preco_seed,
                custo=float(item["custo"] or 0),
                custo_lab=float(item["custo_lab"] or 0),
                lucro_hora=float(item["lucro_hora"] or 0),
                especialidade=str(item.get("especialidade") or "").strip() or None,
                tabela_id=tabela_exemplo_id,
                clinica_id=clinica_id,
            )
            db.add(proc)
            db.flush()
        codigo_para_id[codigo] = int(proc.id)

    db.flush()
    mats = (
        db.query(Material.codigo, Material.id)
        .join(ListaMaterial, ListaMaterial.id == Material.lista_id)
        .filter(ListaMaterial.clinica_id == clinica_id)
        .all()
    )
    mat_por_codigo = {}
    for c, i in mats:
        for v in _codigo_material_variantes(c):
            mat_por_codigo[v] = int(i)

    vinculos_existentes = {
        (int(v.procedimento_id), int(v.material_id)): v
        for v in db.query(ProcedimentoMaterial)
        .join(Procedimento, Procedimento.id == ProcedimentoMaterial.procedimento_id)
        .filter(
            ProcedimentoMaterial.clinica_id == clinica_id,
            Procedimento.clinica_id == clinica_id,
            Procedimento.tabela_id == tabela_exemplo_id,
        )
        .all()
    }

    for item in seed["links"]:
        proc_id = codigo_para_id.get(int(item["procedimento_codigo"] or 0))
        mat_id = None
        for v in _codigo_material_variantes(item["material_codigo"]):
            mat_id = mat_por_codigo.get(v)
            if mat_id:
                break
        qtd = float(item["quantidade"] or 0)
        if not proc_id or not mat_id or qtd <= 0:
            continue
        chave = (int(proc_id), int(mat_id))
        if chave in vinculos_existentes:
            vinculos_existentes[chave].quantidade = qtd
            continue
        novo_vinculo = ProcedimentoMaterial(
            procedimento_id=proc_id,
            material_id=mat_id,
            quantidade=qtd,
            clinica_id=clinica_id,
        )
        db.add(novo_vinculo)
        vinculos_existentes[chave] = novo_vinculo
    db.flush()


def _upsert_procedimentos_particular_na_clinica(db, clinica_id, seed, reset_preco: bool = False):
    tabela_particular_id = (
        db.query(ProcedimentoTabela.id)
        .filter(
            ProcedimentoTabela.clinica_id == clinica_id,
            ProcedimentoTabela.codigo == PRIVATE_TABLE_CODE,
        )
        .scalar()
    )
    if not tabela_particular_id:
        tabela = ProcedimentoTabela(
            clinica_id=clinica_id,
            codigo=PRIVATE_TABLE_CODE,
            nome=PRIVATE_TABLE_NAME,
            nro_indice=255,
            fonte_pagadora="particular",
            inativo=False,
            tipo_tiss_id=1,
        )
        db.add(tabela)
        db.flush()
        tabela_particular_id = int(tabela.id)
    existentes = {
        int(p.codigo): p
        for p in db.query(Procedimento)
        .filter(
            Procedimento.clinica_id == clinica_id,
            Procedimento.tabela_id == tabela_particular_id,
        )
        .all()
    }
    genericos = {
        str(g.codigo or "").strip(): int(g.id)
        for g in db.query(ProcedimentoGenerico)
        .filter(ProcedimentoGenerico.clinica_id == clinica_id)
        .all()
        if str(g.codigo or "").strip()
    }
    for item in seed["procedimentos"]:
        codigo = int(item["codigo"])
        preco_seed = 0.0 if reset_preco else float(item["preco"] or 0)
        simbolo_seed = str(item.get("simbolo_grafico") or "").strip()
        simbolo_legacy_seed = int(item.get("simbolo_grafico_legacy_id") or 0) or None
        mostrar_seed = bool(item.get("mostrar_simbolo"))
        forma_cobranca = str(item.get("forma_cobranca") or "").strip()
        garantia_meses = int(item.get("garantia_meses") or 0)
        valor_repasse = float(item.get("valor_repasse") or 0)
        preferido = bool(item.get("preferido"))
        inativo = bool(item.get("inativo"))
        data_inclusao = str(item.get("data_inclusao") or "").strip()
        data_alteracao = str(item.get("data_alteracao") or "").strip()
        generico_codigo = str(item.get("generico_codigo") or "").strip()
        generico_id = None
        if generico_codigo:
            generico_id = (
                genericos.get(generico_codigo)
                or genericos.get(generico_codigo.zfill(4))
                or genericos.get(generico_codigo.zfill(5))
            )
        if codigo in existentes:
            proc = existentes[codigo]
            proc.nome = item["nome"]
            proc.tempo = int(item["tempo"] or 0)
            proc.preco = preco_seed
            proc.custo = float(item["custo"] or 0)
            proc.custo_lab = float(item["custo_lab"] or 0)
            proc.lucro_hora = float(item["lucro_hora"] or 0)
            proc.especialidade = str(item.get("especialidade") or "").strip() or None
            if generico_id and proc.procedimento_generico_id is None:
                proc.procedimento_generico_id = int(generico_id)
            if simbolo_seed and not str(proc.simbolo_grafico or "").strip():
                proc.simbolo_grafico = simbolo_seed
            if simbolo_legacy_seed and not int(getattr(proc, "simbolo_grafico_legacy_id", 0) or 0):
                proc.simbolo_grafico_legacy_id = simbolo_legacy_seed
            if mostrar_seed and not bool(proc.mostrar_simbolo):
                proc.mostrar_simbolo = True
            if forma_cobranca and not str(proc.forma_cobranca or "").strip():
                proc.forma_cobranca = forma_cobranca
            if int(getattr(proc, "garantia_meses", 0) or 0) <= 0 and garantia_meses > 0:
                proc.garantia_meses = garantia_meses
            if float(getattr(proc, "valor_repasse", 0) or 0) <= 0 and valor_repasse > 0:
                proc.valor_repasse = valor_repasse
            if preferido and not bool(getattr(proc, "preferido", False)):
                proc.preferido = True
            if inativo and not bool(getattr(proc, "inativo", False)):
                proc.inativo = True
            if data_inclusao and not str(getattr(proc, "data_inclusao", "") or "").strip():
                proc.data_inclusao = data_inclusao
            if data_alteracao and not str(getattr(proc, "data_alteracao", "") or "").strip():
                proc.data_alteracao = data_alteracao
        else:
            db.add(
                Procedimento(
                    codigo=codigo,
                    nome=item["nome"],
                    tempo=int(item["tempo"] or 0),
                    preco=preco_seed,
                    custo=float(item["custo"] or 0),
                    custo_lab=float(item["custo_lab"] or 0),
                    lucro_hora=float(item["lucro_hora"] or 0),
                    especialidade=str(item.get("especialidade") or "").strip() or None,
                    procedimento_generico_id=int(generico_id) if generico_id else None,
                    simbolo_grafico=simbolo_seed or None,
                    simbolo_grafico_legacy_id=simbolo_legacy_seed,
                    mostrar_simbolo=bool(simbolo_seed) or mostrar_seed,
                    forma_cobranca=forma_cobranca or None,
                    garantia_meses=garantia_meses,
                    valor_repasse=valor_repasse,
                    preferido=preferido,
                    inativo=inativo,
                    data_inclusao=data_inclusao or None,
                    data_alteracao=data_alteracao or None,
                    tabela_id=tabela_particular_id,
                    clinica_id=clinica_id,
                )
            )
    db.flush()


def _upsert_financeiro_na_clinica(db, clinica_id, seed):
    grupos_exist = {
        (g.nome or "").strip().lower(): g
        for g in db.query(GrupoFinanceiro).filter(GrupoFinanceiro.clinica_id == clinica_id).all()
    }
    grupo_por_nome = {}
    for g in seed["grupos"]:
        nome = (g["nome"] or "").strip()
        if not nome:
            continue
        key = nome.lower()
        if key in grupos_exist:
            grupo = grupos_exist[key]
            grupo.tipo = (g["tipo"] or "").strip() or grupo.tipo
        else:
            grupo = GrupoFinanceiro(clinica_id=clinica_id, nome=nome, tipo=(g["tipo"] or "").strip() or "Profissional")
            db.add(grupo)
            db.flush()
            grupos_exist[key] = grupo
        grupo_por_nome[key] = grupo

    cats_exist = {
        (int(c.grupo_id), (c.nome or "").strip().lower()): c
        for c in db.query(CategoriaFinanceira).filter(CategoriaFinanceira.clinica_id == clinica_id).all()
    }
    for c in seed["categorias"]:
        gkey = (c["grupo_nome"] or "").strip().lower()
        grupo = grupo_por_nome.get(gkey) or grupos_exist.get(gkey)
        if not grupo:
            continue
        nome = (c["nome"] or "").strip()
        if not nome:
            continue
        key = (int(grupo.id), nome.lower())
        if key in cats_exist:
            cat = cats_exist[key]
            cat.tipo = (c["tipo"] or "").strip() or cat.tipo
            cat.tributavel = int(c["tributavel"] or 0)
        else:
            cat = CategoriaFinanceira(
                clinica_id=clinica_id,
                grupo_id=int(grupo.id),
                nome=nome,
                tipo=(c["tipo"] or "").strip() or "Saída",
                tributavel=int(c["tributavel"] or 0),
            )
            db.add(cat)
            db.flush()
            cats_exist[key] = cat

    item_exist = {
        ((i.tipo or "").strip().lower(), (i.codigo or "").strip().lower()): i
        for i in db.query(ItemAuxiliar).filter(ItemAuxiliar.clinica_id == clinica_id).all()
    }
    for i in seed["itens"]:
        tipo = (i["tipo"] or "").strip()
        codigo = (i["codigo"] or "").strip()
        if not tipo or not codigo:
            continue
        key = (tipo.lower(), codigo.lower())
        if key in item_exist:
            item_exist[key].descricao = (i["descricao"] or "").strip()
        else:
            db.add(
                ItemAuxiliar(
                    clinica_id=clinica_id,
                    tipo=tipo,
                    codigo=codigo,
                    descricao=(i["descricao"] or "").strip(),
                )
            )
    db.flush()
    # Regra de onboarding SaaS:
    # novos tenants recebem estrutura financeira (grupos/categorias/auxiliares),
    # mas a conta corrente deve iniciar zerada (sem lançamentos).
    return


def _upsert_auxiliares_raw_na_clinica(db, clinica_id, seed):
    inseridos = 0
    atualizados = 0

    existentes = [
        x
        for x in db.query(ItemAuxiliar).filter(ItemAuxiliar.clinica_id == clinica_id).all()
        if (x.tipo or "").strip() in seed
    ]

    por_tipo_codigo = {}
    por_tipo_desc = {}
    for item in existentes:
        tipo_key = _norm_texto(item.tipo)
        por_tipo_codigo[(tipo_key, _norm_texto(item.codigo))] = item
        por_tipo_desc[(tipo_key, _norm_texto(item.descricao))] = item

    for tipo, itens in seed.items():
        tipo_key = _norm_texto(tipo)
        for codigo, descricao in itens:
            cod = str(codigo or "").strip()
            desc = str(descricao or "").strip()
            if not cod or not desc:
                continue

            chave_codigo = (tipo_key, _norm_texto(cod))
            chave_desc = (tipo_key, _norm_texto(desc))

            if chave_codigo in por_tipo_codigo:
                item = por_tipo_codigo[chave_codigo]
                if (item.descricao or "").strip() != desc:
                    item.descricao = desc
                    atualizados += 1
                continue

            # Se a mesma descricao ja existe nesse tipo, nao duplica.
            if chave_desc in por_tipo_desc:
                continue

            novo = ItemAuxiliar(
                clinica_id=clinica_id,
                tipo=tipo,
                codigo=cod,
                descricao=desc,
            )
            db.add(novo)
            por_tipo_codigo[chave_codigo] = novo
            por_tipo_desc[chave_desc] = novo
            inseridos += 1

    db.flush()
    return {"inseridos": inseridos, "atualizados": atualizados}


def _upsert_especialidades_na_clinica(db, clinica_id, especiais):
    existentes = {
        (str(i.codigo or "").strip().lower()): i
        for i in db.query(ItemAuxiliar)
        .filter(ItemAuxiliar.clinica_id == clinica_id, ItemAuxiliar.tipo.ilike("Especialidade"))
        .all()
    }

    nomes_existentes = {
        _norm_texto(i.descricao): i
        for i in db.query(ItemAuxiliar)
        .filter(ItemAuxiliar.clinica_id == clinica_id, ItemAuxiliar.tipo.ilike("Especialidade"))
        .all()
        if _norm_texto(i.descricao)
    }

    for codigo, descricao in especiais:
        cod = str(codigo or "").strip()
        desc = str(descricao or "").strip()
        if not cod or not desc:
            continue
        key = cod.lower()
        nome_key = _norm_texto(desc)

        if key in existentes:
            existentes[key].descricao = desc
            continue
        if nome_key and nome_key in nomes_existentes:
            item = nomes_existentes[nome_key]
            item.codigo = cod
            item.descricao = desc
            existentes[key] = item
            continue

        novo = ItemAuxiliar(
            clinica_id=clinica_id,
            tipo="Especialidade",
            codigo=cod,
            descricao=desc,
        )
        db.add(novo)
        existentes[key] = novo
        if nome_key:
            nomes_existentes[nome_key] = novo

    db.flush()


def garantir_especialidades_padrao_clinica(db, clinica_id):
    qtd = (
        db.query(ItemAuxiliar)
        .filter(ItemAuxiliar.clinica_id == clinica_id, ItemAuxiliar.tipo.ilike("Especialidade"))
        .count()
    )
    if qtd > 0:
        return
    especiais = _carregar_seed_especialidades()
    if not especiais:
        return
    _upsert_especialidades_na_clinica(db, clinica_id, especiais)


def garantir_auxiliares_raw_clinica(db, clinica_id):
    seed = _carregar_seed_auxiliares_raw()
    if not seed:
        return {"inseridos": 0, "atualizados": 0}
    return _upsert_auxiliares_raw_na_clinica(db, clinica_id, seed)


def garantir_lista_padrao_clinica(db, clinica_id):
    lista = (
        db.query(ListaMaterial)
        .filter(
            ListaMaterial.clinica_id == clinica_id,
            ListaMaterial.nome.in_(DEFAULT_LIST_NAMES),
        )
        .first()
    )
    if not lista:
        lista = ListaMaterial(nome=DEFAULT_LIST_NAME, clinica_id=clinica_id, nro_indice=255)
        db.add(lista)
        db.flush()
    qtd = db.query(Material).filter(Material.lista_id == lista.id).count()
    if qtd > 0:
        return
    seed = _carregar_seed_materiais(db)
    if not seed:
        return
    _upsert_materiais_na_lista(db, lista.id, seed)
    db.flush()


def garantir_procedimentos_padrao_clinica(db, clinica_id, reset_preco: bool = False):
    seed = _carregar_seed_procedimentos(db)
    if not seed["procedimentos"]:
        return
    _upsert_procedimentos_na_clinica(db, clinica_id, seed, reset_preco=reset_preco)
    seed_particular = _carregar_seed_procedimentos_particular(db)
    if seed_particular["procedimentos"]:
        _upsert_procedimentos_particular_na_clinica(db, clinica_id, seed_particular, reset_preco=reset_preco)


def garantir_financeiro_padrao_clinica(db, clinica_id):
    seed = _carregar_seed_financeiro(db)
    if not seed["grupos"] or not seed["categorias"]:
        return
    _upsert_financeiro_na_clinica(db, clinica_id, seed)


def garantir_lista_padrao_todas_clinicas(db):
    for clinica_id in [x[0] for x in db.query(Clinica.id).all()]:
        garantir_lista_padrao_clinica(db, clinica_id)


def garantir_procedimentos_padrao_todas_clinicas(db):
    for clinica_id in [x[0] for x in db.query(Clinica.id).all()]:
        garantir_procedimentos_padrao_clinica(db, clinica_id)


def _seed_codigos_tabela_exemplo():
    seed = _carregar_seed_procedimentos_hosted_por_tabela()
    return {
        int(item.get("codigo") or 0)
        for item in seed.get("exemplo", {}).get("procedimentos", [])
        if int(item.get("codigo") or 0) > 0
    }


def _resolver_nome_tabela_particular(nome_tabela: str | None) -> str:
    nome = (nome_tabela or "").strip()
    if not nome or nome.lower() == "tabela exemplo":
        return PRIVATE_TABLE_NAME
    return nome


def separar_tabela_exemplo_particular_todas_clinicas(db):
    seeds = _carregar_seed_procedimentos_hosted_por_tabela()
    exemplo_seed = seeds.get("exemplo", {}).get("procedimentos", [])
    particular_seed = seeds.get("particular", {}).get("procedimentos", [])
    codigos_exemplo = {int(item.get("codigo") or 0) for item in exemplo_seed if int(item.get("codigo") or 0) > 0}
    codigos_particular = {int(item.get("codigo") or 0) for item in particular_seed if int(item.get("codigo") or 0) > 0}
    if not codigos_exemplo or not codigos_particular:
        return 0
    exemplo_por_codigo = {int(item.get("codigo") or 0): item for item in exemplo_seed if int(item.get("codigo") or 0) > 0}
    particular_por_codigo = {
        int(item.get("codigo") or 0): item for item in particular_seed if int(item.get("codigo") or 0) > 0
    }
    total_movidos = 0
    engine = db.get_bind()
    with engine.begin() as conn:
        clinicas = conn.execute(
            text("SELECT id, nome_tabela_procedimentos FROM clinicas ORDER BY id")
        ).fetchall()
        for clinica_id, nome_tabela in clinicas:
            conn.execute(
                text(
                    "INSERT INTO procedimento_tabela (clinica_id, codigo, nome, nro_indice, fonte_pagadora) "
                    "SELECT :cid, :codigo, :nome, 255, 'particular' "
                    "WHERE NOT EXISTS ("
                    "  SELECT 1 FROM procedimento_tabela WHERE clinica_id = :cid AND codigo = :codigo"
                    ")"
                ),
                {
                    "cid": int(clinica_id),
                    "nome": _resolver_nome_tabela_particular(nome_tabela),
                    "codigo": PRIVATE_TABLE_CODE,
                },
            )
            tabela_particular_id = conn.execute(
                text("SELECT id FROM procedimento_tabela WHERE clinica_id = :cid AND codigo = :codigo"),
                {"cid": int(clinica_id), "codigo": PRIVATE_TABLE_CODE},
            ).scalar()
            if not tabela_particular_id:
                tabela_particular_id = PRIVATE_TABLE_CODE

            removidos = conn.execute(
                text(
                    "DELETE FROM procedimento "
                    "WHERE clinica_id = :cid AND tabela_id = 1 AND codigo NOT IN :codigos"
                ),
                {"cid": int(clinica_id), "codigos": tuple(sorted(codigos_exemplo))},
            ).rowcount
            if removidos:
                total_movidos += int(removidos)

            removidos = conn.execute(
                text(
                    "DELETE FROM procedimento "
                    "WHERE clinica_id = :cid AND tabela_id = :tabela_particular_id AND codigo NOT IN :codigos"
                ),
                {
                    "cid": int(clinica_id),
                    "tabela_particular_id": int(tabela_particular_id),
                    "codigos": tuple(sorted(codigos_particular)),
                },
            ).rowcount
            if removidos:
                total_movidos += int(removidos)

            existentes_exemplo = {
                int(r[0])
                for r in conn.execute(
                    text(
                        "SELECT codigo FROM procedimento "
                        "WHERE clinica_id = :cid AND tabela_id = 1"
                    ),
                    {"cid": int(clinica_id)},
                ).fetchall()
            }
            existentes_particular = {
                int(r[0])
                for r in conn.execute(
                    text(
                        "SELECT codigo FROM procedimento "
                        "WHERE clinica_id = :cid AND tabela_id = :tabela_particular_id"
                    ),
                    {"cid": int(clinica_id), "tabela_particular_id": int(tabela_particular_id)},
                ).fetchall()
            }

            faltando_exemplo = codigos_exemplo - existentes_exemplo
            if faltando_exemplo:
                payload = []
                for codigo in sorted(faltando_exemplo):
                    item = exemplo_por_codigo.get(codigo) or particular_por_codigo.get(codigo) or {}
                    payload.append(
                        {
                            "codigo": int(codigo),
                            "nome": item.get("nome") or f"Procedimento {codigo:03d}",
                            "tempo": int(item.get("tempo") or 0),
                            "preco": float(item.get("preco") or 0),
                            "custo": float(item.get("custo") or 0),
                            "custo_lab": float(item.get("custo_lab") or 0),
                            "lucro_hora": float(item.get("lucro_hora") or 0),
                            "tabela_id": 1,
                            "especialidade": str(item.get("especialidade") or "").strip() or None,
                            "clinica_id": int(clinica_id),
                            "preferido": False,
                            "inativo": False,
                            "mostrar_simbolo": False,
                        }
                    )
                conn.execute(
                    text(
                        "INSERT INTO procedimento "
                        "(codigo, nome, tempo, preco, custo, custo_lab, lucro_hora, tabela_id, "
                        "especialidade, clinica_id, preferido, inativo, mostrar_simbolo) "
                        "VALUES "
                        "(:codigo, :nome, :tempo, :preco, :custo, :custo_lab, :lucro_hora, :tabela_id, "
                        ":especialidade, :clinica_id, :preferido, :inativo, :mostrar_simbolo)"
                    ),
                    payload,
                )
                total_movidos += len(payload)

            faltando_particular = codigos_particular - existentes_particular
            if faltando_particular:
                payload = []
                for codigo in sorted(faltando_particular):
                    item = particular_por_codigo.get(codigo) or exemplo_por_codigo.get(codigo) or {}
                    simbolo_seed = str(item.get("simbolo_grafico") or "").strip()
                    simbolo_legacy_seed = int(item.get("simbolo_grafico_legacy_id") or 0) or None
                    mostrar_seed = bool(item.get("mostrar_simbolo")) or bool(simbolo_seed)
                    payload.append(
                        {
                            "codigo": int(codigo),
                            "nome": item.get("nome") or f"Procedimento {codigo:03d}",
                            "tempo": int(item.get("tempo") or 0),
                            "preco": float(item.get("preco") or 0),
                            "custo": float(item.get("custo") or 0),
                            "custo_lab": float(item.get("custo_lab") or 0),
                            "lucro_hora": float(item.get("lucro_hora") or 0),
                            "tabela_id": int(tabela_particular_id),
                            "especialidade": str(item.get("especialidade") or "").strip() or None,
                            "clinica_id": int(clinica_id),
                            "preferido": False,
                            "inativo": False,
                            "simbolo_grafico": simbolo_seed or None,
                            "simbolo_grafico_legacy_id": simbolo_legacy_seed,
                            "mostrar_simbolo": bool(mostrar_seed),
                        }
                    )
                conn.execute(
                    text(
                        "INSERT INTO procedimento "
                        "(codigo, nome, tempo, preco, custo, custo_lab, lucro_hora, tabela_id, "
                        "especialidade, clinica_id, preferido, inativo, simbolo_grafico, simbolo_grafico_legacy_id, mostrar_simbolo) "
                        "VALUES "
                        "(:codigo, :nome, :tempo, :preco, :custo, :custo_lab, :lucro_hora, :tabela_id, "
                        ":especialidade, :clinica_id, :preferido, :inativo, :simbolo_grafico, :simbolo_grafico_legacy_id, :mostrar_simbolo)"
                    ),
                    payload,
                )
                total_movidos += len(payload)
    return total_movidos


def garantir_financeiro_padrao_todas_clinicas(db):
    for clinica_id in [x[0] for x in db.query(Clinica.id).all()]:
        garantir_financeiro_padrao_clinica(db, clinica_id)


def garantir_especialidades_padrao_todas_clinicas(db):
    for clinica_id in [x[0] for x in db.query(Clinica.id).all()]:
        garantir_especialidades_padrao_clinica(db, clinica_id)


def garantir_auxiliares_raw_todas_clinicas(db):
    resultado = {}
    for clinica_id in [x[0] for x in db.query(Clinica.id).all()]:
        resultado[clinica_id] = garantir_auxiliares_raw_clinica(db, clinica_id)
    return resultado


def garantir_cid_padrao_clinica(db, clinica_id, origem_clinica_id=CID_SEED_CLINICA_ID):
    if int(clinica_id) == int(origem_clinica_id):
        return 0

    total_origem = db.execute(
        text("SELECT COUNT(*) FROM doenca_cid WHERE clinica_id = :src"),
        {"src": int(origem_clinica_id)},
    ).scalar()
    if not total_origem:
        return 0

    db.execute(
        text(
            """
            INSERT INTO doenca_cid (clinica_id, legacy_registro, codigo, descricao, observacoes, preferido)
            SELECT :dest, legacy_registro, codigo, descricao, observacoes, preferido
            FROM doenca_cid
            WHERE clinica_id = :src
            ON CONFLICT (clinica_id, legacy_registro) DO NOTHING
            """
        ),
        {"dest": int(clinica_id), "src": int(origem_clinica_id)},
    )
    db.flush()
    return int(total_origem)


def garantir_cid_padrao_todas_clinicas(db, origem_clinica_id=CID_SEED_CLINICA_ID):
    for clinica_id in [x[0] for x in db.query(Clinica.id).all()]:
        garantir_cid_padrao_clinica(db, clinica_id, origem_clinica_id=origem_clinica_id)


def garantir_convenios_planos_padrao_clinica(
    db,
    clinica_id,
    origem_clinica_id=CONVENIOS_PLANOS_SEED_CLINICA_ID,
):
    clinica_id = int(clinica_id)
    origem_clinica_id = int(origem_clinica_id)
    if clinica_id <= 0 or origem_clinica_id <= 0:
        return {"convenios": 0, "planos": 0}

    convenios_origem = (
        db.query(ConvenioOdonto)
        .filter(ConvenioOdonto.clinica_id == origem_clinica_id)
        .order_by(ConvenioOdonto.source_id.asc(), ConvenioOdonto.id.asc())
        .all()
    )
    planos_origem = (
        db.query(PlanoOdonto)
        .filter(PlanoOdonto.clinica_id == origem_clinica_id)
        .order_by(PlanoOdonto.source_id.asc(), PlanoOdonto.id.asc())
        .all()
    )
    if not convenios_origem:
        return {"convenios": 0, "planos": 0}

    existentes_conv = {
        int(item.source_id or 0): item
        for item in db.query(ConvenioOdonto).filter(ConvenioOdonto.clinica_id == clinica_id).all()
        if int(item.source_id or 0) > 0
    }
    existentes_plan = {
        int(item.source_id or 0): item
        for item in db.query(PlanoOdonto).filter(PlanoOdonto.clinica_id == clinica_id).all()
        if int(item.source_id or 0) > 0
    }

    total_conv = 0
    for origem in convenios_origem:
        source_id = int(origem.source_id or 0)
        if source_id <= 0:
            continue
        item = existentes_conv.get(source_id)
        if item is None:
            item = ConvenioOdonto(clinica_id=clinica_id, source_id=source_id)
            db.add(item)
            existentes_conv[source_id] = item
        item.codigo = origem.codigo
        item.codigo_ans = origem.codigo_ans
        item.nome = _normalizar_nome_convenio(origem.nome)
        item.razao_social = origem.razao_social
        item.tipo_logradouro = origem.tipo_logradouro
        item.endereco = origem.endereco
        item.numero = origem.numero
        item.complemento = origem.complemento
        item.bairro = origem.bairro
        item.cidade = origem.cidade
        item.cep = origem.cep
        item.uf = origem.uf
        item.tipo_fone1 = origem.tipo_fone1
        item.telefone = origem.telefone
        item.contato1 = origem.contato1
        item.tipo_fone2 = origem.tipo_fone2
        item.telefone2 = origem.telefone2
        item.contato2 = origem.contato2
        item.tipo_fone3 = origem.tipo_fone3
        item.telefone3 = origem.telefone3
        item.contato3 = origem.contato3
        item.tipo_fone4 = origem.tipo_fone4
        item.telefone4 = origem.telefone4
        item.contato4 = origem.contato4
        item.email = origem.email
        item.email_tecnico = origem.email_tecnico
        item.homepage = origem.homepage
        item.cnpj = origem.cnpj
        item.inscricao_estadual = origem.inscricao_estadual
        item.inscricao_municipal = origem.inscricao_municipal
        item.tipo_faturamento = origem.tipo_faturamento
        item.historico_nf = origem.historico_nf
        item.aviso_tratamento = origem.aviso_tratamento
        item.aviso_agenda = origem.aviso_agenda
        item.observacoes = origem.observacoes
        item.inativo = bool(origem.inativo)
        item.data_inclusao = origem.data_inclusao
        item.data_alteracao = origem.data_alteracao
        total_conv += 1

    db.flush()

    convenios_destino_por_source = {
        int(item.source_id or 0): item
        for item in db.query(ConvenioOdonto).filter(ConvenioOdonto.clinica_id == clinica_id).all()
        if int(item.source_id or 0) > 0
    }

    total_plan = 0
    for origem in planos_origem:
        source_id = int(origem.source_id or 0)
        if source_id <= 0:
            continue
        convenio_destino = convenios_destino_por_source.get(int(origem.convenio_source_id or 0))
        if convenio_destino is None:
            continue
        item = existentes_plan.get(source_id)
        if item is None:
            item = PlanoOdonto(clinica_id=clinica_id, source_id=source_id)
            db.add(item)
            existentes_plan[source_id] = item
        item.codigo = origem.codigo
        item.nome = origem.nome
        item.cobertura = origem.cobertura
        item.inativo = bool(origem.inativo)
        item.convenio_id = int(convenio_destino.id)
        item.convenio_source_id = int(convenio_destino.source_id)
        item.data_inclusao = origem.data_inclusao
        item.data_alteracao = origem.data_alteracao
        total_plan += 1

    db.flush()
    return {"convenios": total_conv, "planos": total_plan}


def garantir_convenios_planos_padrao_todas_clinicas(
    db,
    origem_clinica_id=CONVENIOS_PLANOS_SEED_CLINICA_ID,
):
    resultado = {}
    for clinica_id in [x[0] for x in db.query(Clinica.id).all()]:
        resultado[int(clinica_id)] = garantir_convenios_planos_padrao_clinica(
            db,
            clinica_id,
            origem_clinica_id=origem_clinica_id,
        )
    return resultado


def garantir_anamnese_padrao_clinica(db, clinica_id):
    nome_padrao = ANAMNESE_QUESTIONARIO_PADRAO
    questionario = (
        db.query(AnamneseQuestionario)
        .filter(
            AnamneseQuestionario.clinica_id == int(clinica_id),
            AnamneseQuestionario.nome == nome_padrao,
        )
        .first()
    )
    if questionario is None:
        ordem = (
            db.query(func.max(AnamneseQuestionario.ordem))
            .filter(AnamneseQuestionario.clinica_id == int(clinica_id))
            .scalar()
        )
        questionario = AnamneseQuestionario(
            clinica_id=int(clinica_id),
            nome=nome_padrao,
            ativo=True,
            ordem=int(ordem or 0) + 1,
        )
        db.add(questionario)
        db.flush()

    existentes = {
        int(row.numero): row
        for row in db.query(AnamnesePergunta)
        .filter(
            AnamnesePergunta.clinica_id == int(clinica_id),
            AnamnesePergunta.questionario_id == int(questionario.id),
        )
        .all()
    }
    numero = 1
    for texto in ANAMNESE_PERGUNTAS_PADRAO:
        texto_limpo = str(texto or "").strip()
        if not texto_limpo:
            numero += 1
            continue
        atual = existentes.get(numero)
        if atual is None:
            db.add(
                AnamnesePergunta(
                    clinica_id=int(clinica_id),
                    questionario_id=int(questionario.id),
                    numero=numero,
                    texto=texto_limpo,
                    ativo=True,
                )
            )
        else:
            if not str(atual.texto or "").strip():
                atual.texto = texto_limpo
            if not atual.ativo:
                atual.ativo = True
        numero += 1


def garantir_anamnese_padrao_todas_clinicas(db):
    for clinica_id in [x[0] for x in db.query(Clinica.id).all()]:
        garantir_anamnese_padrao_clinica(db, clinica_id)


def _garantir_prestador_sistemico_clinica(db, clinica_id: int) -> PrestadorOdonto:
    prestador = (
        db.query(PrestadorOdonto)
        .filter(
            PrestadorOdonto.clinica_id == int(clinica_id),
            PrestadorOdonto.source_id == int(SYSTEM_PRESTADOR_SOURCE_ID),
        )
        .order_by(PrestadorOdonto.id.asc())
        .first()
    )
    if not prestador:
        prestador = PrestadorOdonto(
            clinica_id=int(clinica_id),
            source_id=int(SYSTEM_PRESTADOR_SOURCE_ID),
            codigo=SYSTEM_PRESTADOR_CODIGO,
            nome=SYSTEM_USER_NOME,
            apelido=SYSTEM_USER_NOME,
            tipo_prestador=SYSTEM_PRESTADOR_TIPO,
            inativo=False,
            executa_procedimento=True,
            id_interno=str(SYSTEM_PRESTADOR_SOURCE_ID),
            is_system_prestador=True,
        )
        db.add(prestador)
        db.flush()
        return prestador

    changed = False
    if str(prestador.codigo or "").strip() != SYSTEM_PRESTADOR_CODIGO:
        prestador.codigo = SYSTEM_PRESTADOR_CODIGO
        changed = True
    if str(prestador.nome or "").strip() != SYSTEM_USER_NOME:
        prestador.nome = SYSTEM_USER_NOME
        changed = True
    if str(prestador.apelido or "").strip() != SYSTEM_USER_NOME:
        prestador.apelido = SYSTEM_USER_NOME
        changed = True
    if str(prestador.tipo_prestador or "").strip() != SYSTEM_PRESTADOR_TIPO:
        prestador.tipo_prestador = SYSTEM_PRESTADOR_TIPO
        changed = True
    if not bool(prestador.is_system_prestador):
        prestador.is_system_prestador = True
        changed = True
    if bool(prestador.inativo):
        prestador.inativo = False
        changed = True
    if not bool(prestador.executa_procedimento):
        prestador.executa_procedimento = True
        changed = True
    if str(prestador.id_interno or "").strip() != str(SYSTEM_PRESTADOR_SOURCE_ID):
        prestador.id_interno = str(SYSTEM_PRESTADOR_SOURCE_ID)
        changed = True
    if changed:
        db.add(prestador)
        db.flush()
    return prestador


def _garantir_usuario_sistemico_clinica(db, clinica_id: int, prestador: PrestadorOdonto | None) -> Usuario:
    usuario = (
        db.query(Usuario)
        .filter(
            Usuario.clinica_id == int(clinica_id),
            Usuario.codigo == int(SYSTEM_USER_CODIGO),
        )
        .order_by(Usuario.id.asc())
        .first()
    )
    if not usuario:
        usuario = Usuario(
            codigo=int(SYSTEM_USER_CODIGO),
            nome=SYSTEM_USER_NOME,
            apelido=SYSTEM_USER_NOME,
            tipo_usuario=SYSTEM_USER_TIPO,
            email=build_system_user_email(int(clinica_id)),
            senha_hash=hash_password(f"system::{clinica_id}::{SYSTEM_USER_CODIGO}"),
            clinica_id=int(clinica_id),
            is_admin=False,
            ativo=True,
            online=False,
            forcar_troca_senha=False,
            setup_completed=True,
            is_system_user=True,
            prestador_id=int(prestador.id) if prestador else None,
            permissoes_json=dump_permissions_json(
                sanitize_permissions({}, tipo_usuario=SYSTEM_USER_TIPO, is_admin=False)
            ),
        )
        db.add(usuario)
        db.flush()
    else:
        changed = False
        if not bool(usuario.is_system_user):
            usuario.is_system_user = True
            changed = True
        if int(usuario.codigo or 0) != int(SYSTEM_USER_CODIGO):
            usuario.codigo = int(SYSTEM_USER_CODIGO)
            changed = True
        if str(usuario.nome or "").strip() != SYSTEM_USER_NOME:
            usuario.nome = SYSTEM_USER_NOME
            changed = True
        if str(usuario.apelido or "").strip() != SYSTEM_USER_NOME:
            usuario.apelido = SYSTEM_USER_NOME
            changed = True
        if str(usuario.tipo_usuario or "").strip() != SYSTEM_USER_TIPO:
            usuario.tipo_usuario = SYSTEM_USER_TIPO
            changed = True
        if not str(usuario.email or "").strip():
            usuario.email = build_system_user_email(int(clinica_id))
            changed = True
        if not bool(usuario.ativo):
            usuario.ativo = True
            changed = True
        if bool(usuario.online):
            usuario.online = False
            changed = True
        if not bool(getattr(usuario, "setup_completed", False)):
            usuario.setup_completed = True
            changed = True
        if bool(usuario.is_admin):
            usuario.is_admin = False
            changed = True
        if changed:
            db.add(usuario)
            db.flush()

    if prestador and int(usuario.prestador_id or 0) != int(prestador.id):
        usuario.prestador_id = int(prestador.id)
        db.add(usuario)
        db.flush()
    if prestador and int(prestador.usuario_id or 0) != int(usuario.id):
        prestador.usuario_id = int(usuario.id)
        db.add(prestador)
        db.flush()
    return usuario


def criar_conta_saas(db, nome, email, senha):
    clinica = Clinica(
        nome=nome,
        email=email,
        tipo_conta="DEMO 7 dias",
        trial_ate=datetime.utcnow() + timedelta(days=7),
        ativo=True,
    )
    db.add(clinica)
    db.flush()
    _garantir_diretorios_modelos_clinica(clinica.id)
    garantir_padroes_etiqueta(db)
    garantir_modelos_etiqueta_clinica(db, clinica.id)
    prestador_sistemico = _garantir_prestador_sistemico_clinica(db, clinica.id)
    _garantir_usuario_sistemico_clinica(db, clinica.id, prestador_sistemico)
    ensure_access_profiles(db, clinica.id)

    db.add(
        Usuario(
            codigo=1,
            nome=nome,
            apelido=(str(nome or "").strip().split(" ", 1)[0][:60] if str(nome or "").strip() else None),
            tipo_usuario="Clínica",
            email=email,
            senha_hash=hash_password(senha),
            clinica_id=clinica.id,
            is_admin=True,
            online=False,
            setup_completed=False,
            is_system_user=False,
            permissoes_json=dump_permissions_json(
                sanitize_permissions({}, tipo_usuario="Clínica", is_admin=True)
            ),
        )
    )

    garantir_lista_padrao_clinica(db, clinica.id)
    # Seed oficial estatico (extraido da conta modelo) para novas contas.
    seed_simbolos_graficos(db, clinica.id)
    seed_procedimentos_genericos(db, clinica.id)
    seed_procedimentos(db, clinica.id)
    garantir_financeiro_padrao_clinica(db, clinica.id)
    garantir_indices_padrao_clinica(db, clinica.id)
    garantir_especialidades_padrao_clinica(db, clinica.id)
    garantir_auxiliares_raw_clinica(db, clinica.id)
    garantir_convenios_planos_padrao_clinica(db, clinica.id)
    garantir_cid_padrao_clinica(db, clinica.id)
    garantir_anamnese_padrao_clinica(db, clinica.id)

    db.commit()
    return clinica
