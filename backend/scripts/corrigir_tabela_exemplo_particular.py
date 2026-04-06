import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal  # noqa: E402
from services.signup_service import separar_tabela_exemplo_particular_todas_clinicas  # noqa: E402
from sqlalchemy import text  # noqa: E402
from models.tiss_tipo_tabela import TissTipoTabela  # noqa: F401,E402
from models.procedimento_generico import ProcedimentoGenerico  # noqa: F401,E402


def _contagens(db):
    rows = db.execute(
        text(
            "SELECT clinica_id, tabela_id, COUNT(*) "
            "FROM procedimento "
            "GROUP BY clinica_id, tabela_id "
            "ORDER BY clinica_id, tabela_id"
        )
    ).fetchall()
    return rows


def main():
    db = SessionLocal()
    try:
        antes = _contagens(db)
        total = separar_tabela_exemplo_particular_todas_clinicas(db)
        db.commit()
        depois = _contagens(db)
        print("OK: ajustes", total)
        print("Antes:", antes)
        print("Depois:", depois)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
