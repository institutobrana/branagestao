from __future__ import annotations

import argparse
import csv
from pathlib import Path

from sqlalchemy import text

from database import SessionLocal
import models.clinica  # noqa: F401
import models.doenca_cid  # noqa: F401


CSV_DEFAULT = Path(__file__).resolve().parent / "_migracao_eds70" / "cid_migracao.csv"


def _clean_text(value: str | None) -> str:
    text = (value or "").replace("\x00", "").strip()
    while text and ord(text[0]) < 32:
        text = text[1:]
    return " ".join(text.split())


def main() -> None:
    parser = argparse.ArgumentParser(description="Reimporta o CID do Easy preservando registros duplicados.")
    parser.add_argument("--csv", default=str(CSV_DEFAULT))
    parser.add_argument("--seed-clinica-id", type=int, default=1)
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter=";"))

    db = SessionLocal()
    try:
        db.execute(text("ALTER TABLE doenca_cid ADD COLUMN IF NOT EXISTS legacy_registro INTEGER"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_doenca_cid_legacy_registro ON doenca_cid (legacy_registro)"))
        db.execute(
            text(
                """
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'uq_doenca_cid_clinica_codigo'
                    ) THEN
                        ALTER TABLE doenca_cid
                        DROP CONSTRAINT uq_doenca_cid_clinica_codigo;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'uq_doenca_cid_clinica_registro'
                    ) THEN
                        ALTER TABLE doenca_cid
                        ADD CONSTRAINT uq_doenca_cid_clinica_registro
                        UNIQUE (clinica_id, legacy_registro);
                    END IF;
                END$$;
                """
            )
        )
        clinicas = [int(x[0]) for x in db.execute(text("SELECT id FROM clinicas ORDER BY id")).fetchall()]
        seed_clinica_id = int(args.seed_clinica_id)
        if seed_clinica_id not in clinicas:
            raise RuntimeError(f"Clinica base {seed_clinica_id} nao encontrada.")

        # Recria a clínica base exatamente como o CSV do Easy.
        db.execute(text("DELETE FROM doenca_cid WHERE clinica_id = :cid"), {"cid": seed_clinica_id})
        for idx, row in enumerate(rows, start=1):
            codigo = _clean_text(row.get("codigo"))
            descricao = _clean_text(row.get("descricao"))
            if not codigo or not descricao:
                continue
            db.execute(
                text(
                    """
                    INSERT INTO doenca_cid (
                        clinica_id, legacy_registro, codigo, descricao, observacoes, preferido
                    ) VALUES (
                        :clinica_id, :legacy_registro, :codigo, :descricao, :observacoes, :preferido
                    )
                    """
                ),
                {
                    "clinica_id": seed_clinica_id,
                    "legacy_registro": idx,
                    "codigo": codigo,
                    "descricao": descricao,
                    "observacoes": _clean_text(row.get("observacoes")),
                    "preferido": str(row.get("preferido") or "0").strip() in {"1", "true", "True"},
                },
            )

        # Replica o conjunto exato para as demais clínicas existentes.
        for clinica_id in clinicas:
            if clinica_id == seed_clinica_id:
                continue
            db.execute(text("DELETE FROM doenca_cid WHERE clinica_id = :cid"), {"cid": clinica_id})
            db.execute(
                text(
                    """
                    INSERT INTO doenca_cid (
                        clinica_id, legacy_registro, codigo, descricao, observacoes, preferido
                    )
                    SELECT :dest, legacy_registro, codigo, descricao, observacoes, preferido
                    FROM doenca_cid
                    WHERE clinica_id = :src
                    ORDER BY legacy_registro ASC, id ASC
                    """
                ),
                {"dest": clinica_id, "src": seed_clinica_id},
            )

        db.commit()

        totais = db.execute(
            text(
                """
                SELECT clinica_id, COUNT(*)
                FROM doenca_cid
                GROUP BY clinica_id
                ORDER BY clinica_id
                """
            )
        ).fetchall()
    finally:
        db.close()

    for clinica_id, total in totais:
        print(f"clinica={int(clinica_id)} total={int(total)}")


if __name__ == "__main__":
    main()
