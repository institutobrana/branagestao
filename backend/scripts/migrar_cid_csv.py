from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from database import SessionLocal
import models.clinica  # noqa: F401
import models.usuario  # noqa: F401
from models.doenca_cid import DoencaCid


def _clean_text(value: str | None) -> str:
    text = (value or "").replace("\x00", "").strip()
    while text and ord(text[0]) < 32:
        text = text[1:]
    return " ".join(text.split())


def _to_bool(value: str | None) -> bool:
    base = _clean_text(value or "").lower()
    return base in {"1", "true", "t", "sim", "s", "yes", "y"}


def _get(row: dict[str, str], key: str, mapping: dict[str, str]) -> str:
    src = mapping.get(key, key)
    return row.get(src, "")


def _norm_codigo(value: str | None) -> str:
    return _clean_text(value or "").upper()


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa CID a partir de CSV.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--clinica-id", type=int, required=True)
    parser.add_argument("--delimiter", default=";")
    parser.add_argument("--map", dest="map_path", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    mapping: dict[str, str] = {}
    if args.map_path:
        mapping = json.loads(Path(args.map_path).read_text(encoding="utf-8"))

    inserted = 0
    updated = 0
    skipped = 0

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=args.delimiter)
        rows = list(reader)

    db = SessionLocal()
    existentes_map: dict[str, DoencaCid] = {}
    codigos_processados: set[str] = set()
    try:
        existentes = (
            db.query(DoencaCid)
            .filter(DoencaCid.clinica_id == args.clinica_id)
            .all()
        )
        for item in existentes:
            existentes_map[_norm_codigo(item.codigo)] = item

        for row in rows:
            codigo = _norm_codigo(_get(row, "codigo", mapping))
            descricao = _clean_text(_get(row, "descricao", mapping) or _get(row, "doenca", mapping))
            if not codigo or not descricao:
                skipped += 1
                continue
            if codigo in codigos_processados:
                skipped += 1
                continue

            existente = existentes_map.get(codigo)
            if existente and not args.update:
                skipped += 1
                continue

            payload = {
                "clinica_id": args.clinica_id,
                "codigo": codigo,
                "descricao": descricao,
                "observacoes": _clean_text(_get(row, "observacoes", mapping)),
                "preferido": _to_bool(_get(row, "preferido", mapping)),
            }

            if existente:
                for key, value in payload.items():
                    setattr(existente, key, value)
                updated += 1
            else:
                novo = DoencaCid(**payload)
                db.add(novo)
                inserted += 1
                existentes_map[codigo] = novo
            codigos_processados.add(codigo)

        if args.dry_run:
            db.rollback()
        else:
            db.commit()
    finally:
        db.close()

    print(f"Inseridos: {inserted}")
    print(f"Atualizados: {updated}")
    print(f"Pulados: {skipped}")
    if args.dry_run:
        print("Dry-run: nenhuma alteração persistida.")


if __name__ == "__main__":
    main()
