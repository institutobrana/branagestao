from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from sqlalchemy.orm import Session

from models.simbolo_grafico import SimboloGrafico


PROJECT_DIR = Path(__file__).resolve().parents[3]
RAW_SIMBOLOS_PATH = PROJECT_DIR / "Dados" / "Dist" / "_SIMBOLO_ODONTO.raw"
EASY_ASSETS_DIR = PROJECT_DIR / "assets" / "easy"
SQL_SIMBOLOS_SNAPSHOT_PATH = PROJECT_DIR / "scripts" / "easy_simbolos_catalogo_atual_snapshot.json"
PARTICULAR_SNAPSHOT_PATH = PROJECT_DIR / "scripts" / "easy_particular_atual_snapshot.json"
ESPECIALIDADES_SNAPSHOT_PATH = PROJECT_DIR / "scripts" / "easy_especialidades_atual_snapshot.json"
GENERICOS_SNAPSHOT_PATH = PROJECT_DIR / "scripts" / "easy_genericos_canonicos_snapshot.json"
_TEXTO_SIMBOLOS_CACHE: str | None = None


def _texto_raw_simbolos() -> str:
    global _TEXTO_SIMBOLOS_CACHE
    if _TEXTO_SIMBOLOS_CACHE is not None:
        return _TEXTO_SIMBOLOS_CACHE
    if not RAW_SIMBOLOS_PATH.exists():
        _TEXTO_SIMBOLOS_CACHE = ""
        return _TEXTO_SIMBOLOS_CACHE
    try:
        _TEXTO_SIMBOLOS_CACHE = RAW_SIMBOLOS_PATH.read_bytes().decode("utf-16le", errors="ignore")
    except Exception:
        _TEXTO_SIMBOLOS_CACHE = ""
    return _TEXTO_SIMBOLOS_CACHE


def _sanitizar_descricao(valor: str) -> str:
    permitido = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        " /+-.,()"
        "áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ"
    )
    out: list[str] = []
    for ch in str(valor or ""):
        if ch in permitido:
            out.append(ch)
        elif out:
            break
    texto = " ".join("".join(out).split())
    return texto.strip(" -.,()")


def _norm_texto(valor: str) -> str:
    base = str(valor or "").strip().lower()
    base = unicodedata.normalize("NFD", base)
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def _extrair_descricao_por_bitmap(texto_raw: str, bitmap: str) -> str:
    if not texto_raw or not bitmap:
        return ""
    idx = texto_raw.lower().find(bitmap.lower())
    if idx < 0:
        return ""
    inicio = texto_raw.rfind("<", max(0, idx - 220), idx)
    if inicio < 0:
        return ""
    return _sanitizar_descricao(texto_raw[inicio + 1 : idx])


def _normalizar_bitmap_nome(valor: str | None) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""
    texto = re.sub(r"\s+", " ", texto).strip()
    if texto.lower().endswith(".bmp"):
        return texto
    if texto.lower().startswith(("int_", "sim_")):
        return f"{texto}.bmp"
    return ""


def _carregar_snapshot_sql_simbolos() -> list[dict]:
    if not SQL_SIMBOLOS_SNAPSHOT_PATH.exists():
        return []
    try:
        data = json.loads(SQL_SIMBOLOS_SNAPSHOT_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    itens: list[dict] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        nrosim = int(row.get("nrosim") or 0)
        descricao = _sanitizar_descricao(str(row.get("descricao") or ""))
        icone = _normalizar_bitmap_nome(row.get("icone"))
        bitmap1 = _normalizar_bitmap_nome(row.get("bitmap1"))
        bitmap2 = _normalizar_bitmap_nome(row.get("bitmap2"))
        bitmap3 = _normalizar_bitmap_nome(row.get("bitmap3"))
        codigo = icone or bitmap1 or bitmap2 or bitmap3
        if nrosim <= 0 or not codigo:
            continue
        itens.append(
            {
                "legacy_id": nrosim,
                "codigo": codigo,
                "descricao": descricao or codigo,
                "bitmap1": bitmap1 or codigo,
                "bitmap2": bitmap2 or None,
                "bitmap3": bitmap3 or None,
                "icone": icone or codigo,
                "especialidade": int(row.get("especial") or 0) or None,
                "tipo_marca": int(row.get("tipmarca") or 0) or None,
                # No SaaS, todo simbolo do catalogo oficial deve ser tratado como simbolo de sistema.
                "tipo_simbolo": 1,
                "sobreposicao": int(row.get("sobrepos") or 0) or None,
                "ativo": True,
            }
        )
    return itens


def carregar_codigos_catalogo_oficial() -> set[str]:
    codigos: set[str] = set()
    for row in _carregar_snapshot_sql_simbolos():
        codigo = str(row.get("codigo") or "").strip().lower()
        if codigo:
            codigos.add(codigo)
    return codigos


def carregar_legacy_ids_catalogo_oficial() -> set[int]:
    legacy_ids: set[int] = set()
    for row in _carregar_snapshot_sql_simbolos():
        try:
            legacy_id = int(row.get("legacy_id") or 0)
        except Exception:
            legacy_id = 0
        if legacy_id > 0:
            legacy_ids.add(legacy_id)
    return legacy_ids


def _carregar_mapa_nrosim_para_codigo() -> dict[int, str]:
    mapa: dict[int, str] = {}
    for row in _carregar_snapshot_sql_simbolos():
        try:
            legacy_id = int(row.get("legacy_id") or 0)
        except Exception:
            legacy_id = 0
        codigo = str(row.get("codigo") or "").strip().lower()
        if legacy_id > 0 and codigo:
            mapa[legacy_id] = codigo
    return mapa


def carregar_codigos_genericos() -> set[str]:
    if not GENERICOS_SNAPSHOT_PATH.exists():
        return set()
    try:
        data = json.loads(GENERICOS_SNAPSHOT_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return set()
    catalogo = carregar_codigos_catalogo_oficial()
    codigos = {
        str(row.get("simbolo_grafico") or "").strip().lower()
        for row in data
        if isinstance(row, dict)
    }
    codigos = {c for c in codigos if c}
    if catalogo:
        codigos = {c for c in codigos if c in catalogo}
    return codigos


def carregar_codigos_procedimentos() -> set[str]:
    if not PARTICULAR_SNAPSHOT_PATH.exists():
        return set()
    try:
        data = json.loads(PARTICULAR_SNAPSHOT_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return set()
    mapa = _carregar_mapa_nrosim_para_codigo()
    catalogo = carregar_codigos_catalogo_oficial()
    codigos: set[str] = set()
    for row in data if isinstance(data, list) else []:
        if not isinstance(row, dict):
            continue
        try:
            nrosim = int(row.get("nrosim") or 0)
        except Exception:
            nrosim = 0
        if nrosim <= 0:
            continue
        codigo = mapa.get(nrosim, "")
        if not codigo:
            continue
        if catalogo and codigo not in catalogo:
            continue
        codigos.add(codigo)
    return codigos


def _carregar_especialidades_por_nome() -> dict[str, int]:
    if not ESPECIALIDADES_SNAPSHOT_PATH.exists():
        return {}
    try:
        data = json.loads(ESPECIALIDADES_SNAPSHOT_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    out: dict[str, int] = {}
    for row in data if isinstance(data, list) else []:
        if not isinstance(row, dict):
            continue
        codigo = str(row.get("codigo") or "").strip()
        descricao = str(row.get("descricao") or "").strip()
        if not codigo or not descricao:
            continue
        try:
            codigo_int = int(codigo)
        except Exception:
            continue
        out[_norm_texto(descricao)] = codigo_int
    return out


def _carregar_mapa_especialidade_por_simbolo() -> dict[str, int]:
    if not GENERICOS_SNAPSHOT_PATH.exists():
        return {}
    try:
        data = json.loads(GENERICOS_SNAPSHOT_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    if not isinstance(data, list):
        return {}
    esp_por_nome = _carregar_especialidades_por_nome()
    if not esp_por_nome:
        return {}
    contagens: dict[str, dict[int, int]] = {}
    for row in data:
        if not isinstance(row, dict):
            continue
        simbolo = str(row.get("simbolo_grafico") or "").strip()
        if not simbolo:
            continue
        especialidade_raw = str(row.get("especialidade") or "").strip()
        if not especialidade_raw:
            continue
        esp_key = _norm_texto(especialidade_raw)
        codigo = esp_por_nome.get(esp_key)
        if codigo is None:
            try:
                codigo = int(especialidade_raw)
            except Exception:
                continue
        chave = simbolo.lower()
        contagens.setdefault(chave, {})
        contagens[chave][codigo] = contagens[chave].get(codigo, 0) + 1
    mapa: dict[str, int] = {}
    for simbolo, esp_counts in contagens.items():
        codigo = sorted(esp_counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        mapa[simbolo] = int(codigo)
    return mapa


def carregar_mapa_simbolos_por_legacy_id() -> dict[int, str]:
    mapa: dict[int, str] = {}
    for row in _carregar_snapshot_sql_simbolos():
        legacy_id = int(row.get("legacy_id") or 0)
        codigo = str(row.get("codigo") or "").strip()
        if legacy_id > 0 and codigo:
            mapa[legacy_id] = codigo
    return mapa


def carregar_seed_simbolos() -> list[dict]:
    texto_raw = _texto_raw_simbolos()
    seed_sql = _carregar_snapshot_sql_simbolos()
    esp_por_simbolo = _carregar_mapa_especialidade_por_simbolo()
    esp_por_nome = _carregar_especialidades_por_nome()
    esp_padrao = esp_por_nome.get(_norm_texto("Gerais")) or 5
    seed_sql_por_codigo = {
        str(item.get("codigo") or "").strip().lower(): item
        for item in seed_sql
        if str(item.get("codigo") or "").strip()
    }

    arquivos: list[str] = []
    if EASY_ASSETS_DIR.exists():
        arquivos = sorted(
            {
                item.name
                for item in EASY_ASSETS_DIR.iterdir()
                if item.is_file() and item.suffix.lower() == ".bmp" and item.name.lower().startswith(("int_", "sim_"))
            }
        )

    vistos_catalogo: set[int] = set()
    vistos_assets: set[str] = set()
    itens: list[dict] = []
    for row in seed_sql:
        codigo = str(row["codigo"]).strip()
        chave = codigo.lower()
        legacy_id = int(row.get("legacy_id") or 0)
        if not codigo or legacy_id <= 0 or legacy_id in vistos_catalogo:
            continue
        vistos_catalogo.add(legacy_id)
        vistos_assets.add(chave)
        item = dict(row)
        item["descricao"] = str(item.get("descricao") or codigo)[:120]
        item["especialidade"] = esp_por_simbolo.get(chave, esp_padrao)
        itens.append(item)

    if not texto_raw:
        return itens

    for bitmap in arquivos:
        codigo = bitmap.strip()
        chave = codigo.lower()
        if not codigo or chave in vistos_assets:
            continue
        descricao = str((seed_sql_por_codigo.get(chave) or {}).get("descricao") or "").strip()
        if not descricao:
            descricao = _extrair_descricao_por_bitmap(texto_raw, codigo)
        if not descricao:
            base = re.sub(r"\.bmp$", "", codigo, flags=re.I).replace("_", " ").strip()
            descricao = " ".join(parte.capitalize() for parte in base.split())
        vistos_assets.add(chave)
        itens.append(
            {
                "legacy_id": None,
                "codigo": codigo,
                "descricao": descricao[:120],
                "bitmap1": codigo,
                "bitmap2": None,
                "bitmap3": None,
                "icone": codigo,
                "especialidade": None,
                "tipo_marca": None,
                "tipo_simbolo": 2,
                "sobreposicao": None,
                "ativo": True,
            }
        )
    return itens


def garantir_catalogo_simbolos(db: Session) -> int:
    seed = carregar_seed_simbolos()
    if not seed:
        return 0

    existentes = list(db.query(SimboloGrafico).all())
    existentes_por_legacy = {
        int(item.legacy_id): item
        for item in existentes
        if int(getattr(item, "legacy_id", 0) or 0) > 0
    }
    existentes_sem_legacy: dict[tuple[str, str], SimboloGrafico] = {}
    existentes_sem_legacy_por_codigo: dict[str, list[SimboloGrafico]] = {}
    for item in existentes:
        if int(getattr(item, "legacy_id", 0) or 0) > 0:
            continue
        codigo = str(item.codigo or "").strip().lower()
        descricao = str(item.descricao or "").strip().lower()
        if codigo and descricao:
            existentes_sem_legacy.setdefault((codigo, descricao), item)
        if codigo:
            existentes_sem_legacy_por_codigo.setdefault(codigo, []).append(item)

    alterados = 0
    for row in seed:
        codigo = str(row["codigo"]).strip()
        chave = codigo.lower()
        descricao = str(row.get("descricao") or "").strip()
        legacy_id = int(row.get("legacy_id") or 0)
        item = None
        if legacy_id > 0:
            item = existentes_por_legacy.get(legacy_id)
            if item is None:
                item = existentes_sem_legacy.get((chave, descricao.lower()))
            if item is None:
                candidatos = existentes_sem_legacy_por_codigo.get(chave) or []
                if len(candidatos) == 1:
                    item = candidatos[0]
        else:
            item = existentes_sem_legacy.get((chave, descricao.lower()))

        if item is None:
            item = SimboloGrafico(**row)
            db.add(item)
            if legacy_id > 0:
                existentes_por_legacy[legacy_id] = item
            else:
                existentes_sem_legacy[(chave, descricao.lower())] = item
                existentes_sem_legacy_por_codigo.setdefault(chave, []).append(item)
            alterados += 1
            continue

        mudou = False
        for campo, valor in row.items():
            if getattr(item, campo) != valor:
                setattr(item, campo, valor)
                mudou = True
        if mudou:
            alterados += 1

    return alterados
