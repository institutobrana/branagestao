from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from database import SessionLocal
import models.clinica  # noqa: F401
import models.usuario  # noqa: F401
from models.contato import Contato
from models.protetico import Protetico


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa contatos a partir de CSV.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--clinica-id", type=int, required=True)
    parser.add_argument("--delimiter", default=";")
    parser.add_argument("--map", dest="map_path", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--vincular-proteticos", action="store_true")
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
    try:
        for row in rows:
            nome = _clean_text(_get(row, "nome", mapping))
            if not nome:
                skipped += 1
                continue

            tel1 = _clean_text(_get(row, "tel1", mapping))
            email = _clean_text(_get(row, "email", mapping))
            existente = (
                db.query(Contato)
                .filter(
                    Contato.clinica_id == args.clinica_id,
                    Contato.nome == nome,
                    Contato.tel1 == tel1,
                    Contato.email == email,
                )
                .first()
            )
            if existente and not args.update:
                skipped += 1
                continue

            tipo = _clean_text(_get(row, "tipo", mapping))
            protetico_id = None
            if args.vincular_proteticos and "prot" in tipo.lower():
                prot = (
                    db.query(Protetico)
                    .filter(Protetico.clinica_id == args.clinica_id, Protetico.nome == nome)
                    .first()
                )
                if not prot and not args.dry_run:
                    prot = Protetico(nome=nome, clinica_id=args.clinica_id)
                    db.add(prot)
                    db.flush()
                protetico_id = prot.id if prot else None

            payload = {
                "clinica_id": args.clinica_id,
                "protetico_id": protetico_id,
                "nome": nome,
                "tipo": tipo,
                "contato": _clean_text(_get(row, "contato", mapping)),
                "aniversario_dia": int(_get(row, "aniversario_dia", mapping) or 0) or None,
                "aniversario_mes": int(_get(row, "aniversario_mes", mapping) or 0) or None,
                "endereco": _clean_text(_get(row, "endereco", mapping)),
                "complemento": _clean_text(_get(row, "complemento", mapping)),
                "bairro": _clean_text(_get(row, "bairro", mapping)),
                "cidade": _clean_text(_get(row, "cidade", mapping)),
                "cep": _clean_text(_get(row, "cep", mapping)),
                "uf": _clean_text(_get(row, "uf", mapping)).upper(),
                "pais": _clean_text(_get(row, "pais", mapping)),
                "tel1_tipo": _clean_text(_get(row, "tel1_tipo", mapping)),
                "tel1": tel1,
                "tel2_tipo": _clean_text(_get(row, "tel2_tipo", mapping)),
                "tel2": _clean_text(_get(row, "tel2", mapping)),
                "tel3_tipo": _clean_text(_get(row, "tel3_tipo", mapping)),
                "tel3": _clean_text(_get(row, "tel3", mapping)),
                "tel4_tipo": _clean_text(_get(row, "tel4_tipo", mapping)),
                "tel4": _clean_text(_get(row, "tel4", mapping)),
                "email": email,
                "homepage": _clean_text(_get(row, "homepage", mapping)),
                "incluir_malas_diretas": _to_bool(_get(row, "incluir_malas_diretas", mapping)),
                "incluir_preferidos": _to_bool(_get(row, "incluir_preferidos", mapping)),
                "observacoes": _clean_text(_get(row, "observacoes", mapping)),
            }

            if existente:
                for key, value in payload.items():
                    setattr(existente, key, value)
                updated += 1
            else:
                db.add(Contato(**payload))
                inserted += 1

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
