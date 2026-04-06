import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal
from models.tiss_tipo_tabela import TissTipoTabela  # noqa: F401
from services.signup_service import garantir_convenios_planos_padrao_todas_clinicas


def main() -> None:
    parser = argparse.ArgumentParser(description="Replica convênios e planos padrão para todas as clínicas.")
    parser.add_argument("--origem-clinica-id", type=int, default=1)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        resultado = garantir_convenios_planos_padrao_todas_clinicas(
            db,
            origem_clinica_id=args.origem_clinica_id,
        )
        db.commit()
        for clinica_id, info in sorted(resultado.items()):
            print(
                f"Clinica {clinica_id}: convenios={int(info.get('convenios') or 0)} "
                f"planos={int(info.get('planos') or 0)}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
