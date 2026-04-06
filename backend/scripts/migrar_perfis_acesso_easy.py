from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal  # noqa: E402
from models.access_profile import AccessProfile  # noqa: E402
from models.clinica import Clinica  # noqa: E402
from models.prestador_odonto import PrestadorOdonto  # noqa: E402
from models.usuario import Usuario  # noqa: E402
from models.usuario_perfil_acesso import UsuarioPerfilAcesso  # noqa: E402
from services.access_profiles_service import ensure_access_profiles  # noqa: E402


DEFAULT_PERFIS_CSV = PROJECT_DIR / "sis_perfil_sql.csv"
DEFAULT_USUARIO_PERFIL_CSV = PROJECT_DIR / "usuario_perfil_sql.csv"


@dataclass
class PerfilRow:
    usuario_id: int
    prestador_id: int
    perfil_id: int


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        delimiter = "," if sample.count(",") >= sample.count(";") else ";"
        return list(csv.DictReader(handle, delimiter=delimiter))


def _load_usuario_perfil_rows(path: Path) -> list[PerfilRow]:
    rows = []
    for row in _read_csv(path):
        try:
            usuario_id = int(row.get("ID_USUARIO") or 0)
        except Exception:
            usuario_id = 0
        try:
            prestador_id = int(row.get("ID_PRESTADOR") or 0)
        except Exception:
            prestador_id = 0
        try:
            perfil_id = int(row.get("ID_PERFIL") or 0)
        except Exception:
            perfil_id = 0
        if usuario_id <= 0 or prestador_id <= 0 or perfil_id <= 0:
            continue
        rows.append(PerfilRow(usuario_id=usuario_id, prestador_id=prestador_id, perfil_id=perfil_id))
    return rows


def _resolve_clinica_id(db, email: str | None, clinica_id: int | None) -> int:
    if clinica_id:
        clinica = db.query(Clinica).filter(Clinica.id == int(clinica_id)).first()
        if not clinica:
            raise RuntimeError("Clinica nao encontrada.")
        return int(clinica.id)
    if email:
        usuario = db.query(Usuario).filter(Usuario.email == email.strip().lower()).first()
        if not usuario:
            raise RuntimeError("Usuario nao encontrado para o e-mail informado.")
        return int(usuario.clinica_id)
    raise RuntimeError("Informe --email ou --clinica-id.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Migra perfis de acesso do Easy (usuario_perfil_sql.csv).")
    parser.add_argument("--email", default="", help="Email do usuario SaaS dono da clinica.")
    parser.add_argument("--clinica-id", type=int, default=0, help="Clinica alvo (opcional).")
    parser.add_argument("--perfis-csv", default=str(DEFAULT_PERFIS_CSV))
    parser.add_argument("--usuario-perfil-csv", default=str(DEFAULT_USUARIO_PERFIL_CSV))
    parser.add_argument("--dry-run", action="store_true", help="Nao grava alteracoes.")
    args = parser.parse_args()

    load_dotenv()
    perfis_csv = Path(args.perfis_csv)
    usuario_perfil_csv = Path(args.usuario_perfil_csv)
    if not perfis_csv.exists():
        raise RuntimeError(f"CSV de perfis nao encontrado: {perfis_csv}")
    if not usuario_perfil_csv.exists():
        raise RuntimeError(f"CSV de usuario_perfil nao encontrado: {usuario_perfil_csv}")

    db = SessionLocal()
    try:
        clinica_id = _resolve_clinica_id(db, args.email or None, args.clinica_id or None)
        ensure_access_profiles(db, clinica_id)

        perfis = (
            db.query(AccessProfile)
            .filter(AccessProfile.clinica_id == clinica_id)
            .all()
        )
        perfil_map = {int(p.source_id or 0): p for p in perfis if int(p.source_id or 0) > 0}

        usuarios = (
            db.query(Usuario)
            .filter(Usuario.clinica_id == clinica_id)
            .all()
        )
        usuario_map = {int(u.codigo or 0): u for u in usuarios if int(u.codigo or 0) > 0}

        prestadores = (
            db.query(PrestadorOdonto)
            .filter(PrestadorOdonto.clinica_id == clinica_id)
            .all()
        )
        prest_map = {int(p.source_id or 0): p for p in prestadores if int(p.source_id or 0) > 0}

        rows = _load_usuario_perfil_rows(usuario_perfil_csv)
        existentes = {
            (int(r.usuario_id), int(r.prestador_id), int(r.perfil_id))
            for r in db.query(UsuarioPerfilAcesso)
            .filter(UsuarioPerfilAcesso.clinica_id == clinica_id)
            .all()
        }

        inseridos = 0
        ignorados = 0
        faltantes = 0
        for row in rows:
            usuario = usuario_map.get(row.usuario_id)
            prestador = prest_map.get(row.prestador_id)
            perfil = perfil_map.get(row.perfil_id)
            if not usuario or not prestador or not perfil:
                faltantes += 1
                continue
            key = (int(usuario.id), int(prestador.id), int(perfil.id))
            if key in existentes:
                ignorados += 1
                continue
            existentes.add(key)
            db.add(
                UsuarioPerfilAcesso(
                    clinica_id=clinica_id,
                    usuario_id=int(usuario.id),
                    prestador_id=int(prestador.id),
                    perfil_id=int(perfil.id),
                )
            )
            inseridos += 1

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

        print(f"Clinica {clinica_id} | inseridos={inseridos} ignorados={ignorados} faltantes={faltantes}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
