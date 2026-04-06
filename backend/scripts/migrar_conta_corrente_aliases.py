from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def _load_env() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(env_path)


def main() -> int:
    _load_env()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERRO: DATABASE_URL não encontrado.")
        return 1

    engine = create_engine(db_url)
    with engine.begin() as conn:
        pre = conn.execute(
            text(
                """
                SELECT COALESCE(NULLIF(btrim(conta), ''), '(vazio)') AS conta, count(*)
                FROM lancamento
                GROUP BY 1
                ORDER BY 2 DESC, 1
                """
            )
        ).fetchall()

        upd_clinica = conn.execute(
            text(
                """
                UPDATE lancamento
                SET conta = 'CLINICA'
                WHERE conta IS NULL
                   OR btrim(conta) = ''
                   OR upper(btrim(conta)) IN ('EMPRESARIAL', 'CLÍNICA')
                """
            )
        ).rowcount

        upd_cirurgiao = conn.execute(
            text(
                """
                UPDATE lancamento
                SET conta = 'CIRURGIAO'
                WHERE upper(btrim(conta)) IN ('PESSOAL', 'CIRURGIAO', 'CIRURGIÃO')
                """
            )
        ).rowcount

        post = conn.execute(
            text(
                """
                SELECT COALESCE(NULLIF(btrim(conta), ''), '(vazio)') AS conta, count(*)
                FROM lancamento
                GROUP BY 1
                ORDER BY 2 DESC, 1
                """
            )
        ).fetchall()

    print("=== ANTES ===")
    for conta, total in pre:
        print(f"{conta}: {total}")

    print("=== ATUALIZAÇÕES ===")
    print(f"CLINICA: {upd_clinica}")
    print(f"CIRURGIAO: {upd_cirurgiao}")

    print("=== DEPOIS ===")
    for conta, total in post:
        print(f"{conta}: {total}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
