from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import bindparam, text

from database import SessionLocal
import models.tiss_tipo_tabela  # noqa: F401
from services.simbolos_service import carregar_mapa_simbolos_por_legacy_id


PROJECT_DIR = Path(__file__).resolve().parents[3]
PARTICULAR_SQL_SNAPSHOT_PATH = PROJECT_DIR / "scripts" / "easy_particular_atual_snapshot.json"
PRIVATE_TABLE_CODE = 4


def _to_int(value, default=0) -> int:
    try:
        txt = str(value or "").strip()
        if not txt:
            return default
        return int(float(txt))
    except Exception:
        return default


def _carregar_snapshot() -> list[dict]:
    if not PARTICULAR_SQL_SNAPSHOT_PATH.exists():
        return []
    try:
        data = json.loads(PARTICULAR_SQL_SNAPSHOT_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def main() -> None:
    snapshot = _carregar_snapshot()
    if not snapshot:
        print("Snapshot da PARTICULAR nao encontrado.")
        return

    simbolos_por_legacy = carregar_mapa_simbolos_por_legacy_id()
    payload = []
    for row in snapshot:
        if not isinstance(row, dict):
            continue
        codigo = _to_int(row.get("codconv"), 0) or _to_int(row.get("nroproctab"), 0)
        nrosim = _to_int(row.get("nrosim"), 0)
        if codigo <= 0 or nrosim <= 0:
            continue
        simbolo = simbolos_por_legacy.get(nrosim)
        if not simbolo:
            continue
        payload.append(
            {
                "codigo": codigo,
                "simbolo_grafico": simbolo,
                "simbolo_grafico_legacy_id": nrosim,
            }
        )

    if not payload:
        print("Nenhum procedimento da PARTICULAR com simbolo oficial encontrado no snapshot.")
        return

    db = SessionLocal()
    try:
        total = db.execute(
            text(
                """
                UPDATE procedimento p
                   SET simbolo_grafico = src.simbolo_grafico,
                       simbolo_grafico_legacy_id = src.simbolo_grafico_legacy_id,
                       mostrar_simbolo = TRUE
                  FROM (
                        SELECT
                            t.id AS tabela_id,
                            t.clinica_id,
                            x.codigo,
                            x.simbolo_grafico,
                            x.simbolo_grafico_legacy_id
                        FROM procedimento_tabela t
                        JOIN (
                            SELECT
                                CAST(:codigo AS INTEGER) AS codigo,
                                CAST(:simbolo_grafico AS VARCHAR(30)) AS simbolo_grafico,
                                CAST(:simbolo_grafico_legacy_id AS INTEGER) AS simbolo_grafico_legacy_id
                        ) x ON 1=1
                       WHERE t.codigo = :private_table_code
                    ) AS src
                 WHERE p.clinica_id = src.clinica_id
                   AND p.tabela_id = src.tabela_id
                   AND p.codigo = src.codigo
                """
            ).bindparams(
                bindparam("codigo"),
                bindparam("simbolo_grafico"),
                bindparam("simbolo_grafico_legacy_id"),
                bindparam("private_table_code"),
            ),
            [dict(item, private_table_code=PRIVATE_TABLE_CODE) for item in payload],
        ).rowcount
        db.commit()
        print(f"Backfill de simbolo_grafico_legacy_id concluido. Procedimentos atualizados: {total}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
