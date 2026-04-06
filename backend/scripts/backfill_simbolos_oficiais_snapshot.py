from __future__ import annotations

from database import SessionLocal
from models.simbolo_grafico import SimboloGrafico
from services.simbolos_service import carregar_seed_simbolos


def main() -> None:
    db = SessionLocal()
    try:
        seed = [row for row in carregar_seed_simbolos() if int(row.get("legacy_id") or 0) > 0]
        if not seed:
            print("Nenhum simbolo oficial encontrado no snapshot.")
            return

        oficiais = {
            int(item.legacy_id): item
            for item in db.query(SimboloGrafico).filter(SimboloGrafico.ativo.is_(True), SimboloGrafico.legacy_id.isnot(None)).all()
        }

        alterados = 0
        for row in seed:
            legacy_id = int(row.get("legacy_id") or 0)
            item = oficiais.get(legacy_id)
            if not item:
                continue
            for campo in ("especialidade", "tipo_marca", "tipo_simbolo", "bitmap1", "bitmap2", "bitmap3", "icone", "sobreposicao"):
                novo_valor = row.get(campo)
                if getattr(item, campo) != novo_valor:
                    setattr(item, campo, novo_valor)
                    alterados += 1
            item.tipo_simbolo = 1

        db.commit()
        print(f"Backfill concluido. Campos alterados: {alterados}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
