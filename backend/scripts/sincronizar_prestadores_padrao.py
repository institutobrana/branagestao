import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import SessionLocal  # noqa: E402
from models.clinica import Clinica  # noqa: E402
from models.prestador_odonto import PrestadorOdonto  # noqa: E402
from routes.prestadores_routes import _sync_default_prestadores  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincroniza prestadores padrao a partir dos usuarios da clinica.")
    parser.add_argument("--email", help="E-mail da clinica alvo")
    parser.add_argument("--apply", action="store_true", help="Aplica as alteracoes. Sem isso, roda em dry-run.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(Clinica).order_by(Clinica.id.asc())
        if args.email:
            query = query.filter(Clinica.email == args.email.strip().lower())
        clinicas = query.all()
        if not clinicas:
            print("Nenhuma clinica encontrada.")
            return

        for clinica in clinicas:
            antes = db.query(PrestadorOdonto).filter(PrestadorOdonto.clinica_id == clinica.id).count()
            if args.apply:
                _sync_default_prestadores(db, int(clinica.id))
            depois = db.query(PrestadorOdonto).filter(PrestadorOdonto.clinica_id == clinica.id).count()
            print(
                f"Clinica {clinica.id} <{clinica.email}>: prestadores antes={antes} depois={depois}"
                + (" [apply]" if args.apply else " [dry-run]")
            )

        if not args.apply:
            db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
