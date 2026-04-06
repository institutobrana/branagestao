from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy.orm import Session

from models.access_profile import AccessProfile

ROOT_DIR = Path(__file__).resolve().parents[3]
EASY_PERFIS_CSV = ROOT_DIR / "sis_perfil_sql.csv"


def _read_easy_profiles(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    perfis = []
    for row in rows:
        try:
            source_id = int(row.get("ID_PERFIL") or 0)
        except Exception:
            source_id = 0
        nome = str(row.get("NOME_PERFIL") or "").strip()
        if source_id <= 0 or not nome:
            continue
        perfis.append({"source_id": source_id, "nome": nome})
    return perfis


def ensure_access_profiles(db: Session, clinica_id: int) -> list[AccessProfile]:
    clinica_id = int(clinica_id)
    perfis_seed = _read_easy_profiles(EASY_PERFIS_CSV)
    existentes = {
        int(item.source_id or 0): item
        for item in db.query(AccessProfile)
        .filter(AccessProfile.clinica_id == clinica_id)
        .all()
        if int(item.source_id or 0) > 0
    }

    for item in perfis_seed:
        source_id = int(item["source_id"])
        nome = str(item["nome"]).strip()
        profile = existentes.get(source_id)
        if not profile:
            profile = AccessProfile(
                clinica_id=clinica_id,
                source_id=source_id,
                nome=nome,
                reservado=True,
            )
            db.add(profile)
            existentes[source_id] = profile
            continue
        changed = False
        if (profile.nome or "").strip() != nome:
            profile.nome = nome
            changed = True
        if not bool(profile.reservado):
            profile.reservado = True
            changed = True
        if changed:
            db.add(profile)

    db.flush()
    return (
        db.query(AccessProfile)
        .filter(AccessProfile.clinica_id == clinica_id)
        .order_by(AccessProfile.source_id.asc(), AccessProfile.id.asc())
        .all()
    )
