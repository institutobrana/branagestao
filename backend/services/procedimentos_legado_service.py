from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from models.clinica import Clinica  # noqa: F401
from models.material import ListaMaterial, Material
from models.procedimento import Procedimento
from models.procedimento_generico import (
    ProcedimentoGenerico,
    ProcedimentoGenericoFase,
    ProcedimentoGenericoMaterial,
)
from models.simbolo_grafico import SimboloGrafico
from models.usuario import Usuario  # noqa: F401
from services.simbolos_service import carregar_mapa_simbolos_por_legacy_id

try:
    import pyodbc  # type: ignore
except Exception:  # pragma: no cover - fallback defensivo para ambientes sem driver
    pyodbc = None


PROJECT_DIR = Path(__file__).resolve().parents[3]
PRIVATE_TABLE_CODE = 4
TAB_GEN_ITEM_RAW_PATH = PROJECT_DIR / "Dados" / "Dist" / "TAB_GEN_ITEM.raw"
SIMBOLO_ODONTO_RAW_PATH = PROJECT_DIR / "Dados" / "Dist" / "_SIMBOLO_ODONTO.raw"
PARTICULAR_CSV_PATH = PROJECT_DIR / "Dados" / "particular_336_procedimentos.csv"
GENERICOS_SQL_SNAPSHOT_PATH = PROJECT_DIR / "scripts" / "easy_genericos_canonicos_snapshot.json"
PARTICULAR_SQL_SNAPSHOT_PATH = PROJECT_DIR / "scripts" / "easy_particular_atual_snapshot.json"
EASY_SQL_CONNECTION_STRING = (
    "DRIVER=SQL Server;"
    "SERVER=DELL_SERVIDOR\\EDS70;"
    "DATABASE=eds70;"
    "UID=easy;"
    "PWD=ysae;"
    "Trusted_Connection=no"
)
GENERICOS_HARMONIZACAO_CANONICOS = [
    ("00200", "Lipo de papada"),
    ("00201", "Bichectomia"),
    ("00202", "Fios de sustentação"),
    ("00203", "Micro agulhamento"),
    ("00204", "Preenchimento"),
    ("00205", "Botox"),
    ("00206", "Harmonização"),
]

# Tradução segura confirmada por consulta direta ao SQL do Easy em 2026-03-20.
# Aqui entram apenas os IDs internos da PARTICULAR cujo genérico canônico já existe
# no catálogo local do SaaS com a mesma semântica.
PARTICULAR_ID_PRC_GEN_CANONICO_SEGURO = {
    597: "00203",  # Micro agulhamento
    598: "00201",  # Bichectomia
    599: "00205",  # Botox
    602: "00200",  # Lipo de papada
    603: "00204",  # Preenchimento
}


@dataclass(slots=True)
class _ProcedimentoGenericoLegado:
    codigo: str
    descricao: str
    descricao_norm: str
    simbolo_legacy_id: int | None
    especialidade_legacy_id: int | None
    mostrar_simbolo: bool


@dataclass(slots=True)
class _MatchGenerico:
    item: ProcedimentoGenerico | None
    legacy_id: int | None
    score: float


@dataclass(slots=True)
class _FaseGenericoCanonica:
    sequencia: int
    codigo: str
    descricao: str
    tempo: int


@dataclass(slots=True)
class _MaterialGenericoCanonico:
    codigo: str
    nome: str
    quantidade: float
    custo_medio: float
    custo_unitario: float


@dataclass(slots=True)
class _GenericoCanonicoSql:
    codigo: str
    descricao: str
    tempo: int
    custo_lab: float
    custo_material: float
    peso: float
    especialidade: str
    simbolo_grafico: str
    mostrar_simbolo: bool
    data_inclusao: str | None
    data_alteracao: str | None
    fases: list[_FaseGenericoCanonica]
    materiais: list[_MaterialGenericoCanonico]


def _norm(texto: str) -> str:
    base = (texto or "").strip().lower()
    base = unicodedata.normalize("NFKD", base)
    base = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
    base = base.encode("ascii", "ignore").decode("ascii", errors="ignore")
    base = re.sub(r"[^a-z0-9]+", " ", base)
    base = re.sub(r"\s+", " ", base)
    return base.strip()


def _norm_strip_qualificadores(texto: str) -> str:
    base = _norm(texto)
    base = re.sub(r"\s*-\s*\(.*?\)", "", base).strip()
    base = re.sub(r"\s*\(.*?\)", "", base).strip()
    base = re.sub(r"\s+", " ", base)
    return base.strip()


def _descricao_limpa(texto: str) -> str:
    base = (
        str(texto or "")
        .replace("\ufeff", "")
        .replace("\x00", "")
        .replace("\u00A0", " ")
        .strip()
    )
    return re.sub(r"\s+", " ", base).strip()


def resolver_codigo_generico_particular_snapshot(id_prc_gen: int | str | None) -> str:
    valor = 0
    try:
        valor = int(float(str(id_prc_gen or "").strip() or 0))
    except Exception:
        valor = 0
    if valor <= 0:
        return ""
    codigo_seguro = PARTICULAR_ID_PRC_GEN_CANONICO_SEGURO.get(valor)
    if codigo_seguro:
        return codigo_seguro
    return f"{valor:04d}"


def _parse_tab_gen_item_legado() -> list[_ProcedimentoGenericoLegado]:
    if not TAB_GEN_ITEM_RAW_PATH.exists():
        return []

    raw_bytes = TAB_GEN_ITEM_RAW_PATH.read_bytes()
    starts: list[int] = []
    total = len(raw_bytes)
    for pos in range(0, total - 12):
        registro_id = int.from_bytes(raw_bytes[pos : pos + 4], "little", signed=False)
        if not (1 <= registro_id <= 9999):
            continue
        if raw_bytes[pos + 4 : pos + 12] == f"{registro_id:04d}".encode("utf-16le"):
            starts.append(pos)

    itens: list[_ProcedimentoGenericoLegado] = []
    vistos: set[str] = set()
    for idx, inicio in enumerate(starts):
        fim = starts[idx + 1] if idx + 1 < len(starts) else total
        bloco = raw_bytes[inicio:fim]
        if len(bloco) < 534:
            continue

        codigo = _descricao_limpa(bloco[4:24].decode("utf-16le", errors="ignore"))
        descricao = _descricao_limpa(bloco[24:534].decode("utf-16le", errors="ignore"))
        if not codigo or not descricao or codigo in vistos:
            continue

        # O bloco legado traz o simbolo no byte 535.
        simbolo_legacy_id = None
        if len(bloco) > 535:
            bruto = int.from_bytes(bloco[535:539], "little", signed=False)
            if bruto > 0:
                simbolo_legacy_id = bruto
        especialidade_legacy_id = None
        if len(bloco) >= 543:
            especialidade_bruta = int.from_bytes(bloco[539:543], "little", signed=False)
            if especialidade_bruta > 0:
                especialidade_legacy_id = especialidade_bruta
        mostrar_simbolo = False
        if len(bloco) >= 550:
            mostrar_bruto = int.from_bytes(bloco[546:550], "little", signed=False)
            mostrar_simbolo = mostrar_bruto not in {0}

        vistos.add(codigo)
        itens.append(
            _ProcedimentoGenericoLegado(
                codigo=codigo,
                descricao=descricao,
                descricao_norm=_norm(descricao),
                simbolo_legacy_id=simbolo_legacy_id,
                especialidade_legacy_id=especialidade_legacy_id,
                mostrar_simbolo=mostrar_simbolo,
            )
        )
    return itens


def _parse_especialidades_raw_legado() -> dict[int, dict[str, str]]:
    path = PROJECT_DIR / "Dados" / "Dist" / "_ESPECIALIDADE.raw"
    if not path.exists():
        return {}

    raw_bytes = path.read_bytes()
    starts: list[int] = []
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

    especiais: dict[int, dict[str, str]] = {}
    for inicio in starts:
        registro_id = int.from_bytes(raw_bytes[inicio : inicio + 4], "little", signed=False)
        codigo = raw_bytes[inicio + 6 : inicio + 10].decode("utf-16le", errors="ignore").strip()
        nome_len = int.from_bytes(raw_bytes[inicio + 10 : inicio + 12], "little", signed=False)
        nome = raw_bytes[inicio + 12 : inicio + 12 + nome_len].decode("utf-16le", errors="ignore").strip()
        if registro_id <= 0 or not codigo or not nome:
            continue
        especiais[int(registro_id)] = {"codigo": codigo, "nome": nome}
    return especiais


def carregar_metadados_genericos_legado() -> dict[str, dict[str, object]]:
    genericos_legado = _parse_tab_gen_item_legado()
    if not genericos_legado:
        return {}

    especialidades = _parse_especialidades_raw_legado()
    simbolos_por_legacy_id = _parse_mapa_simbolos_legado()
    itens: dict[str, dict[str, object]] = {}
    for item in genericos_legado:
        codigo = str(item.codigo or "").strip()
        if not codigo:
            continue
        especialidade_codigo = ""
        especial = especialidades.get(int(item.especialidade_legacy_id or 0))
        if especial:
            especialidade_codigo = str(especial.get("codigo") or "").strip()
        simbolo_codigo = str(simbolos_por_legacy_id.get(int(item.simbolo_legacy_id or 0)) or "").strip()
        itens[codigo] = {
            "codigo": codigo,
            "descricao": item.descricao,
            "especialidade": especialidade_codigo,
            "simbolo_grafico": simbolo_codigo,
            "mostrar_simbolo": bool(item.mostrar_simbolo or simbolo_codigo),
        }
    return itens


def _connect_easy_sql():
    if pyodbc is None:
        return None
    try:
        return pyodbc.connect(EASY_SQL_CONNECTION_STRING, timeout=8)
    except Exception:
        return None


def _carregar_genericos_canonicos_snapshot() -> dict[str, _GenericoCanonicoSql]:
    if not GENERICOS_SQL_SNAPSHOT_PATH.exists():
        return {}
    try:
        payload = json.loads(GENERICOS_SQL_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

    itens: dict[str, _GenericoCanonicoSql] = {}
    for row in payload if isinstance(payload, list) else []:
        codigo = _descricao_limpa(str((row or {}).get("codigo") or ""))
        if not codigo:
            continue
        fases = []
        for fase in (row or {}).get("fases") or []:
            descricao = _descricao_limpa(str((fase or {}).get("descricao") or ""))
            if not descricao:
                continue
            fases.append(
                _FaseGenericoCanonica(
                    sequencia=max(1, int((fase or {}).get("sequencia") or 1)),
                    codigo=_descricao_limpa(str((fase or {}).get("codigo") or "")),
                    descricao=descricao,
                    tempo=max(0, int((fase or {}).get("tempo") or 0)),
                )
            )
        materiais = []
        for mat in (row or {}).get("materiais") or []:
            codigo_material = _descricao_limpa(str((mat or {}).get("codigo") or ""))
            nome_material = _descricao_limpa(str((mat or {}).get("nome") or ""))
            if not codigo_material and not nome_material:
                continue
            materiais.append(
                _MaterialGenericoCanonico(
                    codigo=codigo_material,
                    nome=nome_material,
                    quantidade=float((mat or {}).get("quantidade") or 0),
                    custo_medio=float((mat or {}).get("custo_medio") or 0),
                    custo_unitario=float((mat or {}).get("custo_unitario") or 0),
                )
            )
        itens[codigo] = _GenericoCanonicoSql(
            codigo=codigo,
            descricao=_descricao_limpa(str((row or {}).get("descricao") or "")),
            tempo=max(0, int((row or {}).get("tempo") or 0)),
            custo_lab=float((row or {}).get("custo_lab") or 0),
            custo_material=float((row or {}).get("custo_material") or 0),
            peso=float((row or {}).get("peso") or 0),
            especialidade=_descricao_limpa(str((row or {}).get("especialidade") or "")),
            simbolo_grafico=_descricao_limpa(str((row or {}).get("simbolo_grafico") or "")),
            mostrar_simbolo=bool((row or {}).get("mostrar_simbolo")),
            data_inclusao=_descricao_limpa(str((row or {}).get("data_inclusao") or "")) or None,
            data_alteracao=_descricao_limpa(str((row or {}).get("data_alteracao") or "")) or None,
            fases=fases,
            materiais=materiais,
        )
    return itens


def carregar_genericos_canonicos_sql() -> dict[str, _GenericoCanonicoSql]:
    snapshot = _carregar_genericos_canonicos_snapshot()
    if snapshot:
        return snapshot

    cn = _connect_easy_sql()
    if cn is None:
        return {}

    itens: dict[str, _GenericoCanonicoSql] = {}
    try:
        cur = cn.cursor()
        simbolos_por_legacy_id = _parse_mapa_simbolos_legado()
        especialidades = _parse_especialidades_raw_legado()
        cur.execute(
            """
            select
                rtrim(CODIGO) as codigo,
                rtrim(NOME) as nome,
                TEMPO,
                CUSTO_PROTETICO,
                CUSTO_MATERIAL,
                PESO,
                ID_SIMBOLO,
                ID_ESPECIALIDADE,
                MOSTRAR_SIMBOLO,
                convert(varchar(10), TIME_STAMP_INS, 23) as data_inclusao,
                convert(varchar(10), TIME_STAMP_UPD, 23) as data_alteracao
            from TAB_GEN_ITEM
            where CODIGO is not null and rtrim(CODIGO) <> ''
            order by CODIGO
            """
        )
        for row in cur.fetchall():
            codigo = _descricao_limpa(getattr(row, "codigo", "") or "")
            if not codigo:
                continue
            itens[codigo] = _GenericoCanonicoSql(
                codigo=codigo,
                descricao=_descricao_limpa(getattr(row, "nome", "") or ""),
                tempo=max(0, int(getattr(row, "TEMPO", 0) or 0)),
                custo_lab=float(getattr(row, "CUSTO_PROTETICO", 0) or 0),
                custo_material=float(getattr(row, "CUSTO_MATERIAL", 0) or 0),
                peso=float(getattr(row, "PESO", 0) or 0),
                especialidade=str(
                    (especialidades.get(int(getattr(row, "ID_ESPECIALIDADE", 0) or 0)) or {}).get("codigo") or ""
                ).strip(),
                simbolo_grafico=str(
                    simbolos_por_legacy_id.get(int(getattr(row, "ID_SIMBOLO", 0) or 0)) or ""
                ).strip(),
                mostrar_simbolo=bool(getattr(row, "MOSTRAR_SIMBOLO", 0) or getattr(row, "ID_SIMBOLO", 0)),
                data_inclusao=_descricao_limpa(getattr(row, "data_inclusao", "") or "") or None,
                data_alteracao=_descricao_limpa(getattr(row, "data_alteracao", "") or "") or None,
                fases=[],
                materiais=[],
            )

        cur.execute(
            """
            select
                rtrim(g.CODIGO) as codigo_proc,
                f.NROSEQ as sequencia,
                f.TEMPO as tempo,
                rtrim(fp.CODIGO) as codigo_fase,
                rtrim(fp.NOME) as nome_fase
            from TAB_GEN_ITEM_FASE f
            join TAB_GEN_ITEM g on g.ID_PRC_GEN = f.ID_PRC_GEN
            left join _FASE_PROCEDIMENTO fp on fp.REGISTRO = f.ID_FASE
            order by g.CODIGO, f.NROSEQ
            """
        )
        for row in cur.fetchall():
            codigo_proc = _descricao_limpa(getattr(row, "codigo_proc", "") or "")
            item = itens.get(codigo_proc)
            if item is None:
                continue
            descricao = _descricao_limpa(getattr(row, "nome_fase", "") or "")
            if not descricao:
                continue
            item.fases.append(
                _FaseGenericoCanonica(
                    sequencia=max(1, int(getattr(row, "sequencia", 1) or 1)),
                    codigo=_descricao_limpa(getattr(row, "codigo_fase", "") or ""),
                    descricao=descricao,
                    tempo=max(0, int(getattr(row, "tempo", 0) or 0)),
                )
            )

        cur.execute(
            """
            select
                rtrim(g.CODIGO) as codigo_proc,
                rtrim(m.CODIGO) as codigo_material,
                rtrim(m.NOME) as nome_material,
                mm.QTD_MEDIA as quantidade,
                mm.CUSTO_MEDIO as custo_medio,
                m.VALOR_CUSTO as custo_unitario
            from TAB_GEN_ITEM_MAT mm
            join TAB_GEN_ITEM g on g.ID_PRC_GEN = mm.ID_PRC_GEN
            join TAB_MAT_ITEM m on m.ID_MATERIAL = mm.ID_MATERIAL
            order by g.CODIGO, m.NOME
            """
        )
        for row in cur.fetchall():
            codigo_proc = _descricao_limpa(getattr(row, "codigo_proc", "") or "")
            item = itens.get(codigo_proc)
            if item is None:
                continue
            codigo_material = _descricao_limpa(getattr(row, "codigo_material", "") or "")
            nome_material = _descricao_limpa(getattr(row, "nome_material", "") or "")
            if not codigo_material and not nome_material:
                continue
            item.materiais.append(
                _MaterialGenericoCanonico(
                    codigo=codigo_material,
                    nome=nome_material,
                    quantidade=float(getattr(row, "quantidade", 0) or 0),
                    custo_medio=float(getattr(row, "custo_medio", 0) or 0),
                    custo_unitario=float(getattr(row, "custo_unitario", 0) or 0),
                )
            )
    finally:
        cn.close()
    return itens


def _material_maps_por_clinica(db: Session) -> dict[int, dict[str, dict[str, Material]]]:
    rows = (
        db.query(Material, ListaMaterial)
        .join(ListaMaterial, ListaMaterial.id == Material.lista_id)
        .order_by(ListaMaterial.clinica_id.asc(), ListaMaterial.nro_indice.asc(), Material.id.asc())
        .all()
    )
    por_clinica: dict[int, dict[str, dict[str, Material]]] = {}
    for material, lista in rows:
        clinica_id = int(getattr(lista, "clinica_id", 0) or 0)
        if clinica_id <= 0:
            continue
        bucket = por_clinica.setdefault(clinica_id, {"por_codigo": {}, "por_nome": {}})
        codigo = str(getattr(material, "codigo", "") or "").strip()
        nome = _norm(getattr(material, "nome", "") or "")
        if codigo and codigo not in bucket["por_codigo"]:
            bucket["por_codigo"][codigo] = material
        if nome and nome not in bucket["por_nome"]:
            bucket["por_nome"][nome] = material
    return por_clinica


def _carregar_particular_sql_snapshot() -> dict[str, dict[str, Any]]:
    if not PARTICULAR_SQL_SNAPSHOT_PATH.exists():
        return {"por_nro": {}, "por_codconv": {}, "por_desc": {}}
    try:
        payload = json.loads(PARTICULAR_SQL_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"por_nro": {}, "por_codconv": {}, "por_desc": {}}

    por_nro: dict[int, dict[str, Any]] = {}
    por_codconv: dict[str, dict[str, Any]] = {}
    por_desc: dict[str, dict[str, Any]] = {}
    for row in payload if isinstance(payload, list) else []:
        try:
            nro = int((row or {}).get("nroproctab") or 0)
        except Exception:
            nro = 0
        codconv = _descricao_limpa(str((row or {}).get("codconv") or ""))
        descricao = _descricao_limpa(str((row or {}).get("descricao") or ""))
        item = {
            "nroproctab": nro,
            "codconv": codconv,
            "descricao": descricao,
            "nrosim": int((row or {}).get("nrosim") or 0),
            "especial": int((row or {}).get("especial") or 0),
            "tipocobr": int((row or {}).get("tipocobr") or 0),
            "mostrar_simbolo": bool((row or {}).get("mostrar_simbolo")),
            "garantia": int((row or {}).get("garantia") or 0),
            "preferido": bool(int((row or {}).get("preferido") or 0)),
            "id_prc_gen": int((row or {}).get("id_prc_gen") or 0),
            "data_inclusao": _descricao_limpa(str((row or {}).get("data_inclusao") or "")),
            "data_alteracao": _descricao_limpa(str((row or {}).get("data_alteracao") or "")),
        }
        if nro > 0:
            por_nro[nro] = item
        if codconv:
            por_codconv[codconv] = item
        if descricao:
            por_desc[_norm(descricao)] = item
    return {"por_nro": por_nro, "por_codconv": por_codconv, "por_desc": por_desc}


def _mapear_forma_cobranca_easy(tipo_cobr: int | None) -> str:
    valor = int(tipo_cobr or 0)
    if valor == 1:
        return "ELEMENTO_FACE"
    if valor == 2:
        return "INTERVENCAO"
    return ""


def _backfill_genericos_por_snapshot_particular(
    db: Session,
    particular_snapshot: dict[str, dict[str, Any]],
    simbolos_por_legacy_id: dict[int, str],
) -> int:
    alterados = 0
    genericos = {
        str(item.codigo or "").strip(): item
        for item in db.query(ProcedimentoGenerico).all()
        if str(item.codigo or "").strip()
    }
    itens_snapshot = list(particular_snapshot.get("por_nro", {}).values())
    for row in itens_snapshot:
        id_prc_gen = int(row.get("id_prc_gen") or 0)
        if id_prc_gen <= 0:
            continue
        codigo4 = f"{id_prc_gen:04d}"
        codigo5 = f"{id_prc_gen:05d}"
        generico = genericos.get(codigo5) or genericos.get(codigo4)
        if generico is None:
            continue
        mudou = False
        simbolo_codigo = str(simbolos_por_legacy_id.get(int(row.get("nrosim") or 0)) or "").strip()
        if simbolo_codigo and not str(generico.simbolo_grafico or "").strip():
            generico.simbolo_grafico = simbolo_codigo
            mudou = True
        if int(row.get("especial") or 0) > 0 and not str(generico.especialidade or "").strip():
            generico.especialidade = f"{int(row.get('especial') or 0):02d}"
            mudou = True
        if bool(row.get("mostrar_simbolo")) and not bool(generico.mostrar_simbolo):
            generico.mostrar_simbolo = True
            mudou = True
        if str(row.get("data_inclusao") or "").strip() and not str(generico.data_inclusao or "").strip():
            generico.data_inclusao = str(row.get("data_inclusao") or "").strip()
            mudou = True
        if str(row.get("data_alteracao") or "").strip() and not str(generico.data_alteracao or "").strip():
            generico.data_alteracao = str(row.get("data_alteracao") or "").strip()
            mudou = True
        if mudou:
            alterados += 1
    if alterados:
        db.flush()
    return alterados


def _resolver_material_clinica(
    material: _MaterialGenericoCanonico,
    materiais_clinica: dict[str, dict[str, Material]],
) -> Material | None:
    codigo = str(material.codigo or "").strip()
    if codigo:
        item = materiais_clinica.get("por_codigo", {}).get(codigo)
        if item is not None:
            return item
    nome_norm = _norm(material.nome or "")
    if nome_norm:
        return materiais_clinica.get("por_nome", {}).get(nome_norm)
    return None


def _garantir_vinculos_genericos_canonicos(db: Session) -> int:
    canonicos = carregar_genericos_canonicos_sql()
    if not canonicos:
        return 0

    materiais_por_clinica = _material_maps_por_clinica(db)
    alterados = 0
    genericos = db.query(ProcedimentoGenerico).order_by(ProcedimentoGenerico.clinica_id.asc(), ProcedimentoGenerico.codigo.asc()).all()
    for item in genericos:
        canonico = canonicos.get(str(item.codigo or "").strip())
        if canonico is None:
            continue

        mudou = False
        if canonico.tempo > 0 and int(item.tempo or 0) <= 0:
            item.tempo = canonico.tempo
            mudou = True
        if canonico.custo_lab > 0 and float(item.custo_lab or 0) <= 0:
            item.custo_lab = canonico.custo_lab
            mudou = True
        if canonico.peso > 0 and float(item.peso or 0) <= 0:
            item.peso = canonico.peso
            mudou = True
        if canonico.especialidade and not str(item.especialidade or "").strip():
            item.especialidade = canonico.especialidade
            mudou = True
        if canonico.simbolo_grafico and not str(item.simbolo_grafico or "").strip():
            item.simbolo_grafico = canonico.simbolo_grafico
            mudou = True
        if canonico.mostrar_simbolo and not bool(item.mostrar_simbolo):
            item.mostrar_simbolo = True
            mudou = True
        if canonico.data_inclusao and not str(item.data_inclusao or "").strip():
            item.data_inclusao = canonico.data_inclusao
            mudou = True
        if canonico.data_alteracao and not str(item.data_alteracao or "").strip():
            item.data_alteracao = canonico.data_alteracao
            mudou = True

        if mudou:
            alterados += 1

        fases_existentes = list(item.fases or [])
        if canonico.fases and not fases_existentes:
            for fase in canonico.fases:
                db.add(
                    ProcedimentoGenericoFase(
                        procedimento_generico_id=int(item.id),
                        clinica_id=int(item.clinica_id),
                        codigo=str(fase.codigo or "").strip() or None,
                        descricao=fase.descricao,
                        sequencia=max(1, int(fase.sequencia or 1)),
                        tempo=max(0, int(fase.tempo or 0)),
                    )
                )
                alterados += 1

        materiais_existentes = {
            int(getattr(v, "material_id", 0) or 0): v for v in list(item.materiais_vinculados or [])
        }
        if canonico.materiais:
            materiais_clinica = materiais_por_clinica.get(int(item.clinica_id), {})
            for mat in canonico.materiais:
                material_local = _resolver_material_clinica(mat, materiais_clinica)
                if material_local is None:
                    continue
                existente = materiais_existentes.get(int(material_local.id))
                if existente is None:
                    db.add(
                        ProcedimentoGenericoMaterial(
                            procedimento_generico_id=int(item.id),
                            material_id=int(material_local.id),
                            quantidade=float(mat.quantidade or 0),
                            clinica_id=int(item.clinica_id),
                        )
                    )
                    alterados += 1
                    continue
                if float(getattr(existente, "quantidade", 0) or 0) <= 0 and float(mat.quantidade or 0) > 0:
                    existente.quantidade = float(mat.quantidade or 0)
                    alterados += 1

    if alterados:
        db.flush()
    return alterados


def _garantir_genericos_harmonizacao_facial(db: Session) -> int:
    clinicas = [int(x[0]) for x in db.query(Clinica.id).order_by(Clinica.id.asc()).all()]
    alterados = 0
    for clinica_id in clinicas:
        for codigo, descricao in GENERICOS_HARMONIZACAO_CANONICOS:
            codigo_antigo = codigo[1:] if codigo.startswith("0") else codigo
            item = (
                db.query(ProcedimentoGenerico)
                .filter(
                    ProcedimentoGenerico.clinica_id == clinica_id,
                    ProcedimentoGenerico.codigo == codigo,
                )
                .first()
            )
            item_antigo = None
            if codigo_antigo != codigo:
                item_antigo = (
                    db.query(ProcedimentoGenerico)
                    .filter(
                        ProcedimentoGenerico.clinica_id == clinica_id,
                        ProcedimentoGenerico.codigo == codigo_antigo,
                    )
                    .first()
                )
            if item is not None and item_antigo is not None and int(item.id) != int(item_antigo.id):
                (
                    db.query(Procedimento)
                    .filter(
                        Procedimento.clinica_id == clinica_id,
                        Procedimento.procedimento_generico_id == int(item_antigo.id),
                    )
                    .update({"procedimento_generico_id": int(item.id)}, synchronize_session=False)
                )
                if not list(item.fases or []) and list(item_antigo.fases or []):
                    for fase_antiga in list(item_antigo.fases or []):
                        db.add(
                            ProcedimentoGenericoFase(
                                procedimento_generico_id=int(item.id),
                                clinica_id=clinica_id,
                                codigo=str(fase_antiga.codigo or "").strip() or None,
                                descricao=str(fase_antiga.descricao or "").strip(),
                                sequencia=max(1, int(fase_antiga.sequencia or 1)),
                                tempo=max(0, int(fase_antiga.tempo or 0)),
                            )
                        )
                mats_destino = {int(getattr(v, "material_id", 0) or 0) for v in list(item.materiais_vinculados or [])}
                for mat_antigo in list(item_antigo.materiais_vinculados or []):
                    if int(getattr(mat_antigo, "material_id", 0) or 0) in mats_destino:
                        continue
                    db.add(
                        ProcedimentoGenericoMaterial(
                            procedimento_generico_id=int(item.id),
                            material_id=int(mat_antigo.material_id),
                            quantidade=float(mat_antigo.quantidade or 0),
                            clinica_id=clinica_id,
                        )
                    )
                db.delete(item_antigo)
                item_antigo = None
                alterados += 1
            if item is None and item_antigo is not None:
                item = item_antigo
                item.codigo = codigo
                alterados += 1
            if item is None:
                db.add(
                    ProcedimentoGenerico(
                        clinica_id=clinica_id,
                        codigo=codigo,
                        descricao=descricao,
                        especialidade="14",
                        tempo=0,
                        custo_lab=0,
                        peso=0,
                        mostrar_simbolo=False,
                        inativo=False,
                    )
                )
                alterados += 1
                continue

            usos = (
                db.query(Procedimento.id)
                .filter(
                    Procedimento.clinica_id == clinica_id,
                    Procedimento.procedimento_generico_id == int(item.id),
                )
                .first()
                is not None
            )
            if usos:
                if str(item.especialidade or "").strip() != "14" and _norm(item.descricao or "") == _norm(descricao):
                    item.especialidade = "14"
                    alterados += 1
                continue

            mudou = False
            if str(item.descricao or "").strip() != descricao:
                item.descricao = descricao
                mudou = True
            if str(item.especialidade or "").strip() != "14":
                item.especialidade = "14"
                mudou = True
            if bool(item.inativo):
                item.inativo = False
                mudou = True
            if mudou:
                alterados += 1
    if alterados:
        db.flush()
    return alterados


def garantir_metadados_procedimentos_genericos(db: Session) -> int:
    alterados = _garantir_genericos_harmonizacao_facial(db)
    metadados = carregar_metadados_genericos_legado()
    if metadados:
        itens = db.query(ProcedimentoGenerico).all()
        for item in itens:
            meta = metadados.get(str(item.codigo or "").strip())
            if not meta:
                continue
            mudou = False
            especialidade = str(meta.get("especialidade") or "").strip()
            simbolo_grafico = str(meta.get("simbolo_grafico") or "").strip()
            mostrar_simbolo = bool(meta.get("mostrar_simbolo"))
            if especialidade and not str(item.especialidade or "").strip():
                item.especialidade = especialidade
                mudou = True
            if simbolo_grafico and not str(item.simbolo_grafico or "").strip():
                item.simbolo_grafico = simbolo_grafico
                mudou = True
            if mostrar_simbolo and not bool(item.mostrar_simbolo):
                item.mostrar_simbolo = True
                mudou = True
            if mudou:
                alterados += 1
    alterados += _garantir_vinculos_genericos_canonicos(db)
    if alterados:
        db.flush()
    return alterados


def _parse_mapa_simbolos_legado() -> dict[int, str]:
    mapa_sql = carregar_mapa_simbolos_por_legacy_id()
    if mapa_sql:
        return mapa_sql
    if not SIMBOLO_ODONTO_RAW_PATH.exists():
        return {}

    texto = SIMBOLO_ODONTO_RAW_PATH.read_bytes().decode("utf-16le", errors="ignore")
    pattern = re.compile(r"(.?)\x00<.*?\((int_[^\s)]+\.bmp|sim_[^\s)]+\.bmp)", re.I | re.S)
    mapa: dict[int, str] = {}
    for match in pattern.finditer(texto):
        legacy_id = ord(match.group(1))
        bitmap = str(match.group(2) or "").strip()
        if 1 <= legacy_id <= 255 and bitmap:
            mapa.setdefault(legacy_id, bitmap)
    return mapa


def _carregar_particular_csv() -> dict[str, dict]:
    if not PARTICULAR_CSV_PATH.exists():
        return {"por_nro": {}, "por_codconv": {}}

    itens_por_nro: dict[int, dict] = {}
    itens_por_codconv: dict[str, dict] = {}
    with PARTICULAR_CSV_PATH.open("r", encoding="latin-1", newline="") as arquivo:
        for row in csv.DictReader(arquivo):
            try:
                codigo = int(row.get("NROPROCTAB") or 0)
            except (TypeError, ValueError):
                continue
            if codigo <= 0:
                continue
            codconv = _descricao_limpa(row.get("CODCONV") or "")
            item = {
                "nroproctab": codigo,
                "codconv": codconv,
                "descricao": _descricao_limpa(row.get("DESCRICAO") or ""),
            }
            itens_por_nro[codigo] = item
            if codconv:
                itens_por_codconv[codconv] = item
    return {"por_nro": itens_por_nro, "por_codconv": itens_por_codconv}


def _resolver_origem_particular(proc: Procedimento, particulares_csv: dict[str, dict]) -> dict | None:
    por_nro = particulares_csv.get("por_nro", {})
    por_codconv = particulares_csv.get("por_codconv", {})
    codigo_num = int(getattr(proc, "codigo", 0) or 0)
    codigo_txt = str(codigo_num).strip()
    origem = por_nro.get(codigo_num)
    if origem:
        return origem
    if codigo_txt:
        origem = por_codconv.get(codigo_txt.zfill(4)) or por_codconv.get(codigo_txt)
        if origem:
            return origem
    return None


def _inferir_forma_cobranca(nome: str) -> str:
    base = _norm(nome)
    if not base:
        return "INTERVENCAO"
    marcadores_elemento = (
        "por elemento",
        "por face",
        "por faces",
        "por raiz",
        "sextante",
        "segmento",
        "grupo de dentes",
    )
    if any(chave in base for chave in marcadores_elemento):
        return "ELEMENTO_FACE"
    return "INTERVENCAO"


def _resolver_generico(
    nome: str,
    genericos_por_desc: dict[str, ProcedimentoGenerico],
    genericos_por_desc_strip: dict[str, ProcedimentoGenerico],
    genericos_legado: list[_ProcedimentoGenericoLegado],
    genericos_locais_por_codigo: dict[str, ProcedimentoGenerico],
) -> tuple[ProcedimentoGenerico | None, int | None]:
    descricao_norm = _norm(nome)
    if not descricao_norm:
        return None, None

    direto = genericos_por_desc.get(descricao_norm)
    if direto:
        legado = next((x for x in genericos_legado if x.codigo == direto.codigo), None)
        return direto, (legado.simbolo_legacy_id if legado else None)

    strip = genericos_por_desc_strip.get(_norm_strip_qualificadores(nome))
    if strip:
        legado = next((x for x in genericos_legado if x.codigo == strip.codigo), None)
        return strip, (legado.simbolo_legacy_id if legado else None)

    melhor: tuple[float, _ProcedimentoGenericoLegado] | None = None
    segundo_melhor = 0.0
    for legado in genericos_legado:
        score = SequenceMatcher(None, descricao_norm, legado.descricao_norm).ratio()
        if melhor is None or score > melhor[0]:
            segundo_melhor = melhor[0] if melhor else 0.0
            melhor = (score, legado)
        elif score > segundo_melhor:
            segundo_melhor = score

    if not melhor or melhor[0] < 0.90 or (melhor[0] - segundo_melhor) < 0.03:
        return None, None

    local = genericos_locais_por_codigo.get(melhor[1].codigo)
    if not local:
        return None, melhor[1].simbolo_legacy_id
    return local, melhor[1].simbolo_legacy_id


def _score_match_generico(nome_a: str, nome_b: str) -> float:
    norm_a = _norm(nome_a)
    norm_b = _norm(nome_b)
    strip_a = _norm_strip_qualificadores(nome_a)
    strip_b = _norm_strip_qualificadores(nome_b)
    score = max(
        SequenceMatcher(None, norm_a, norm_b).ratio() if norm_a and norm_b else 0.0,
        SequenceMatcher(None, strip_a, strip_b).ratio() if strip_a and strip_b else 0.0,
    )
    if strip_a and strip_b and (strip_a in strip_b or strip_b in strip_a):
        score = max(score, 0.98)
    return score


def _melhor_generico_local(
    nome: str,
    especialidade: str,
    itens: list[ProcedimentoGenerico],
    genericos_legado_por_codigo: dict[str, _ProcedimentoGenericoLegado],
) -> _MatchGenerico:
    especialidade = str(especialidade or "").strip()
    candidatos = [
        item
        for item in itens
        if not especialidade or str(getattr(item, "especialidade", "") or "").strip() == especialidade
    ] or itens
    melhor_item = None
    melhor_score = 0.0
    segundo_score = 0.0
    for item in candidatos:
        score = _score_match_generico(nome, str(getattr(item, "descricao", "") or ""))
        if score > melhor_score:
            segundo_score = melhor_score
            melhor_score = score
            melhor_item = item
        elif score > segundo_score:
            segundo_score = score
    if melhor_item is None or melhor_score < 0.60 or (melhor_score - segundo_score) < 0.02:
        return _MatchGenerico(None, None, melhor_score)
    legado = genericos_legado_por_codigo.get(str(getattr(melhor_item, "codigo", "") or "").strip())
    return _MatchGenerico(
        melhor_item,
        int(getattr(legado, "simbolo_legacy_id", 0) or 0) or None,
        melhor_score,
    )


def _resolver_simbolo_por_descricao(nome: str, simbolos: list[SimboloGrafico]) -> str | None:
    nome_norm = _norm(nome)
    if not nome_norm:
        return None

    melhor_codigo = None
    melhor_tamanho = 0
    for simbolo in simbolos:
        descricao_norm = _norm(getattr(simbolo, "descricao", "") or "")
        codigo = str(getattr(simbolo, "codigo", "") or "").strip()
        if not codigo or len(descricao_norm) < 5:
            continue
        if descricao_norm in nome_norm and len(descricao_norm) > melhor_tamanho:
            melhor_codigo = codigo
            melhor_tamanho = len(descricao_norm)
    return melhor_codigo


def _backfill_campos_procedimentos_por_generico(db: Session) -> int:
    alterados = 0
    rows = (
        db.query(Procedimento, ProcedimentoGenerico)
        .join(ProcedimentoGenerico, ProcedimentoGenerico.id == Procedimento.procedimento_generico_id)
        .all()
    )
    for proc, generico in rows:
        mudou = False
        if int(getattr(proc, "tempo", 0) or 0) <= 0 and int(getattr(generico, "tempo", 0) or 0) > 0:
            proc.tempo = int(generico.tempo or 0)
            mudou = True
        if float(getattr(proc, "custo_lab", 0) or 0) <= 0 and float(getattr(generico, "custo_lab", 0) or 0) > 0:
            proc.custo_lab = float(generico.custo_lab or 0)
            mudou = True
        if not str(getattr(proc, "especialidade", "") or "").strip() and str(getattr(generico, "especialidade", "") or "").strip():
            proc.especialidade = str(generico.especialidade or "").strip()
            mudou = True
        if not str(getattr(proc, "simbolo_grafico", "") or "").strip() and str(getattr(generico, "simbolo_grafico", "") or "").strip():
            proc.simbolo_grafico = str(generico.simbolo_grafico or "").strip()
            mudou = True
        if bool(getattr(generico, "mostrar_simbolo", False)) and not bool(getattr(proc, "mostrar_simbolo", False)):
            proc.mostrar_simbolo = True
            mudou = True
        if not str(getattr(proc, "observacoes", "") or "").strip() and str(getattr(generico, "observacoes", "") or "").strip():
            proc.observacoes = str(generico.observacoes or "").strip()
            mudou = True
        if not str(getattr(proc, "data_inclusao", "") or "").strip() and str(getattr(generico, "data_inclusao", "") or "").strip():
            proc.data_inclusao = str(generico.data_inclusao or "").strip()
            mudou = True
        if not str(getattr(proc, "data_alteracao", "") or "").strip() and str(getattr(generico, "data_alteracao", "") or "").strip():
            proc.data_alteracao = str(generico.data_alteracao or "").strip()
            mudou = True
        if mudou:
            alterados += 1
    if alterados:
        db.flush()
    return alterados


def garantir_metadados_tabela_particular(db: Session) -> int:
    garantir_metadados_procedimentos_genericos(db)
    particulares_csv = _carregar_particular_csv()
    particular_snapshot = _carregar_particular_sql_snapshot()
    if not particulares_csv.get("por_nro"):
        return 0

    genericos_legado = _parse_tab_gen_item_legado()
    if not genericos_legado:
        return 0

    simbolos_por_legacy_id = _parse_mapa_simbolos_legado()
    alterados = _backfill_genericos_por_snapshot_particular(db, particular_snapshot, simbolos_por_legacy_id)
    genericos_locais = db.query(ProcedimentoGenerico).all()
    simbolos_catalogo = db.query(SimboloGrafico).all()
    genericos_locais_por_clinica: dict[int, dict[str, dict[str, ProcedimentoGenerico]]] = {}
    for item in genericos_locais:
        clinica_id = int(getattr(item, "clinica_id", 0) or 0)
        if clinica_id <= 0:
            continue
        bucket = genericos_locais_por_clinica.setdefault(
            clinica_id,
            {"por_codigo": {}, "por_desc": {}, "por_desc_strip": {}, "itens": []},
        )
        bucket["itens"].append(item)
        codigo = str(item.codigo or "").strip()
        if codigo:
            bucket["por_codigo"][codigo] = item
        desc = _norm(item.descricao or "")
        if desc:
            bucket["por_desc"][desc] = item
        desc_strip = _norm_strip_qualificadores(item.descricao or "")
        if desc_strip:
            bucket["por_desc_strip"][desc_strip] = item

    genericos_legado_por_codigo = {str(item.codigo or "").strip(): item for item in genericos_legado}
    procedimentos = (
        db.query(Procedimento)
        .filter(Procedimento.tabela_id == PRIVATE_TABLE_CODE)
        .order_by(Procedimento.clinica_id.asc(), Procedimento.codigo.asc(), Procedimento.id.asc())
        .all()
    )
    for proc in procedimentos:
        origem = _resolver_origem_particular(proc, particulares_csv)
        if not origem:
            continue
        snapshot_meta = None
        codigo_txt = str(int(getattr(proc, "codigo", 0) or 0)).strip()
        if codigo_txt:
            snapshot_meta = (
                particular_snapshot.get("por_codconv", {}).get(codigo_txt.zfill(4))
                or particular_snapshot.get("por_codconv", {}).get(codigo_txt)
            )
        if snapshot_meta is None:
            snapshot_meta = particular_snapshot.get("por_nro", {}).get(int(origem.get("nroproctab") or 0))
        if snapshot_meta is None:
            snapshot_meta = particular_snapshot.get("por_desc", {}).get(_norm(origem.get("descricao") or proc.nome or ""))

        nome_origem = origem["descricao"] or proc.nome or ""
        mapas_clinica = genericos_locais_por_clinica.get(int(proc.clinica_id or 0), {})
        generico_local, simbolo_legacy_id = _resolver_generico(
            nome_origem,
            mapas_clinica.get("por_desc", {}),
            mapas_clinica.get("por_desc_strip", {}),
            genericos_legado,
            mapas_clinica.get("por_codigo", {}),
        )
        melhor_local = _MatchGenerico(generico_local, simbolo_legacy_id, 1.0 if generico_local else 0.0)
        if melhor_local.item is None:
            melhor_local = _melhor_generico_local(
                nome_origem,
                str(proc.especialidade or "").strip(),
                mapas_clinica.get("itens", []),
                genericos_legado_por_codigo,
            )
            generico_local = melhor_local.item
            simbolo_legacy_id = melhor_local.legacy_id
        if snapshot_meta and int(snapshot_meta.get("nrosim") or 0) > 0:
            simbolo_legacy_id = int(snapshot_meta.get("nrosim") or 0)
        simbolo_codigo = simbolos_por_legacy_id.get(int(simbolo_legacy_id or 0))
        if not simbolo_codigo:
            simbolo_codigo = _resolver_simbolo_por_descricao(nome_origem, simbolos_catalogo)
        forma_cobranca = _mapear_forma_cobranca_easy((snapshot_meta or {}).get("tipocobr")) or _inferir_forma_cobranca(nome_origem)

        mudou = False
        codigo_easy = str(origem.get("codconv") or "").strip()
        if codigo_easy:
            try:
                codigo_easy_num = int(codigo_easy)
            except (TypeError, ValueError):
                codigo_easy_num = 0
            if codigo_easy_num > 0 and int(proc.codigo or 0) != codigo_easy_num:
                existe_codigo = (
                    db.query(Procedimento.id)
                    .filter(
                        Procedimento.clinica_id == proc.clinica_id,
                        Procedimento.tabela_id == proc.tabela_id,
                        Procedimento.codigo == codigo_easy_num,
                        Procedimento.id != proc.id,
                    )
                    .first()
                    is not None
                )
                if not existe_codigo:
                    proc.codigo = codigo_easy_num
                    mudou = True
        if generico_local and proc.procedimento_generico_id is None and melhor_local.score >= 0.86:
            proc.procedimento_generico_id = generico_local.id
            mudou = True
        if snapshot_meta and int(snapshot_meta.get("id_prc_gen") or 0) > 0 and generico_local is None:
            id_prc_gen_snapshot = int(snapshot_meta.get("id_prc_gen") or 0)
            codigo_generico_snapshot = resolver_codigo_generico_particular_snapshot(id_prc_gen_snapshot)
            codigo_generico_snapshot5 = codigo_generico_snapshot.zfill(5) if codigo_generico_snapshot else ""
            generico_por_codigo = (
                mapas_clinica.get("por_codigo", {}).get(codigo_generico_snapshot5)
                or mapas_clinica.get("por_codigo", {}).get(codigo_generico_snapshot)
            )
            if generico_por_codigo is not None and proc.procedimento_generico_id != generico_por_codigo.id:
                proc.procedimento_generico_id = generico_por_codigo.id
                generico_local = generico_por_codigo
                mudou = True
        if generico_local and not str(proc.especialidade or "").strip() and str(generico_local.especialidade or "").strip():
            proc.especialidade = str(generico_local.especialidade or "").strip()
            mudou = True
        if snapshot_meta and int(snapshot_meta.get("especial") or 0) > 0 and not str(proc.especialidade or "").strip():
            proc.especialidade = f"{int(snapshot_meta.get('especial') or 0):02d}"
            mudou = True
        if generico_local and not str(proc.simbolo_grafico or "").strip() and str(generico_local.simbolo_grafico or "").strip():
            proc.simbolo_grafico = str(generico_local.simbolo_grafico or "").strip()
            mudou = True
        if simbolo_codigo and not str(proc.simbolo_grafico or "").strip():
            proc.simbolo_grafico = simbolo_codigo
            mudou = True
        if (simbolo_codigo or bool((snapshot_meta or {}).get("mostrar_simbolo"))) and not bool(proc.mostrar_simbolo):
            proc.mostrar_simbolo = True
            mudou = True
        if forma_cobranca and not str(proc.forma_cobranca or "").strip():
            proc.forma_cobranca = forma_cobranca
            mudou = True
        if int(getattr(proc, "garantia_meses", 0) or 0) <= 0 and int((snapshot_meta or {}).get("garantia") or 0) > 0:
            proc.garantia_meses = int((snapshot_meta or {}).get("garantia") or 0)
            mudou = True
        if not bool(getattr(proc, "preferido", False)) and bool((snapshot_meta or {}).get("preferido")):
            proc.preferido = True
            mudou = True
        if not str(getattr(proc, "data_inclusao", "") or "").strip() and str((snapshot_meta or {}).get("data_inclusao") or "").strip():
            proc.data_inclusao = str((snapshot_meta or {}).get("data_inclusao") or "").strip()
            mudou = True
        if not str(getattr(proc, "data_alteracao", "") or "").strip() and str((snapshot_meta or {}).get("data_alteracao") or "").strip():
            proc.data_alteracao = str((snapshot_meta or {}).get("data_alteracao") or "").strip()
            mudou = True

        if mudou:
            alterados += 1

    if alterados:
        db.flush()
    alterados += _backfill_campos_procedimentos_por_generico(db)
    return alterados
