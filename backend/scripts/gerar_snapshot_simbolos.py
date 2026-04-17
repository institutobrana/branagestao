from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = BACKEND_DIR / "scripts" / "easy_simbolos_catalogo_atual_snapshot.json"


def _load_env() -> None:
    load_dotenv(BACKEND_DIR / ".env")
    load_dotenv()


def _database_url() -> str:
    _load_env()
    db_url = str(os.getenv("DATABASE_URL") or "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL nao definido no ambiente/.env.")
    return db_url


def _pick_source_clinica(engine, explicit_clinica_id: int | None) -> int | None:
    if explicit_clinica_id and explicit_clinica_id > 0:
        return int(explicit_clinica_id)

    sql_best = text(
        """
        SELECT clinica_id, COUNT(*) AS qtd
        FROM simbolo_grafico_catalogo
        WHERE clinica_id IS NOT NULL
          AND legacy_id IS NOT NULL
          AND legacy_id > 0
        GROUP BY clinica_id
        ORDER BY qtd DESC, clinica_id ASC
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql_best).mappings().first()
        if row and row.get("clinica_id") is not None:
            return int(row["clinica_id"])

    sql_any = text(
        """
        SELECT clinica_id
        FROM simbolo_grafico_catalogo
        WHERE clinica_id IS NOT NULL
        ORDER BY clinica_id ASC
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql_any).mappings().first()
        if row and row.get("clinica_id") is not None:
            return int(row["clinica_id"])
    return None


def _normalizar_linha(row: dict[str, Any]) -> dict[str, Any]:
    def _int_or_none(key: str) -> int | None:
        val = row.get(key)
        if val is None:
            return None
        try:
            return int(val)
        except Exception:
            return None

    out = {
        "nrosim": _int_or_none("legacy_id"),
        "descricao": str(row.get("descricao") or "").strip(),
        "icone": str(row.get("icone") or "").strip() or None,
        "bitmap1": str(row.get("bitmap1") or "").strip() or None,
        "bitmap2": str(row.get("bitmap2") or "").strip() or None,
        "bitmap3": str(row.get("bitmap3") or "").strip() or None,
        "especial": _int_or_none("especialidade"),
        "tipmarca": _int_or_none("tipo_marca"),
        "sobrepos": _int_or_none("sobreposicao"),
        "tiposim": _int_or_none("tipo_simbolo"),
        "codigo": str(row.get("codigo") or "").strip() or None,
        "ativo": bool(row.get("ativo")) if row.get("ativo") is not None else True,
    }
    return out


def _carregar_simbolos_da_clinica(engine, clinica_id: int) -> list[dict[str, Any]]:
    sql = text(
        """
        SELECT
            legacy_id,
            codigo,
            descricao,
            especialidade,
            tipo_marca,
            tipo_simbolo,
            bitmap1,
            bitmap2,
            bitmap3,
            icone,
            sobreposicao,
            ativo
        FROM simbolo_grafico_catalogo
        WHERE clinica_id = :clinica_id
          AND legacy_id IS NOT NULL
          AND legacy_id > 0
        ORDER BY legacy_id ASC, id ASC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"clinica_id": int(clinica_id)}).mappings().all()

    dedup: dict[int, dict[str, Any]] = {}
    for row in rows:
        legacy_id = int(row.get("legacy_id") or 0)
        if legacy_id <= 0:
            continue
        if legacy_id not in dedup:
            dedup[legacy_id] = _normalizar_linha(dict(row))
    return [dedup[k] for k in sorted(dedup.keys())]


def _salvar_json(path: Path, payload: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera snapshot JSON de simbolos (compatível com carregar_seed_simbolos)."
    )
    parser.add_argument(
        "--clinica-id",
        type=int,
        default=0,
        help="Clinica de origem para exportar os simbolos oficiais (legacy_id > 0).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT),
        help="Caminho do JSON de saida.",
    )
    args = parser.parse_args()

    db_url = _database_url()
    engine = create_engine(db_url)

    clinica_id = _pick_source_clinica(engine, args.clinica_id or None)
    if not clinica_id:
        print("[snapshot-simbolos] Nenhuma clinica encontrada em simbolo_grafico_catalogo.")
        _salvar_json(Path(args.output), [])
        print(f"[snapshot-simbolos] Arquivo gerado vazio em: {args.output}")
        return 0

    simbolos = _carregar_simbolos_da_clinica(engine, clinica_id)
    out_path = Path(args.output).resolve()
    _salvar_json(out_path, simbolos)

    print(f"[snapshot-simbolos] Clinica origem: {clinica_id}")
    print(f"[snapshot-simbolos] Registros exportados: {len(simbolos)}")
    print(f"[snapshot-simbolos] Arquivo: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

