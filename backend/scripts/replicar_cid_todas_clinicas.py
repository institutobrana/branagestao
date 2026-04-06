from __future__ import annotations

import argparse

from database import SessionLocal
import models.clinica  # noqa: F401
import models.doenca_cid  # noqa: F401
import models.procedimento_tabela  # noqa: F401
import models.tiss_tipo_tabela  # noqa: F401
from services.signup_service import garantir_cid_padrao_todas_clinicas


def main() -> None:
    parser = argparse.ArgumentParser(description="Replica CID da clinica base para todas as clinicas.")
    parser.add_argument("--origem-clinica-id", type=int, default=1)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        garantir_cid_padrao_todas_clinicas(db, origem_clinica_id=args.origem_clinica_id)
        db.commit()
    finally:
        db.close()

    print("CID replicado para todas as clinicas (se faltava).")


if __name__ == "__main__":
    main()
