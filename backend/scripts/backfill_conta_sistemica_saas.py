from __future__ import annotations

import argparse
import importlib
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent.parent

if str(BACKEND_DIR) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(BACKEND_DIR))

from database import SessionLocal  # noqa: E402
from models.clinica import Clinica  # noqa: E402
from models.prestador_odonto import PrestadorOdonto  # noqa: E402
from models.usuario import Usuario  # noqa: E402
from security.system_accounts import (  # noqa: E402
    SYSTEM_PRESTADOR_SOURCE_ID,
    SYSTEM_USER_CODIGO,
    SYSTEM_USER_NOME,
    SYSTEM_USER_TIPO,
    SYSTEM_PRESTADOR_TIPO,
    is_system_prestador,
    is_system_user,
)
from services.signup_service import (  # noqa: E402
    _garantir_prestador_sistemico_clinica,
    _garantir_usuario_sistemico_clinica,
)


def _load_model_registry() -> None:
    models_dir = BACKEND_DIR / "models"
    for path in models_dir.glob("*.py"):
        if path.name.startswith("_"):
            continue
        importlib.import_module(f"models.{path.stem}")


def _find_system_user(db: Session, clinica_id: int) -> Usuario | None:
    users = (
        db.query(Usuario)
        .filter(Usuario.clinica_id == int(clinica_id))
        .order_by(Usuario.id.asc())
        .all()
    )
    for user in users:
        if is_system_user(user):
            return user
    return (
        db.query(Usuario)
        .filter(Usuario.clinica_id == int(clinica_id), Usuario.codigo == int(SYSTEM_USER_CODIGO))
        .first()
    )


def _find_system_prestador(db: Session, clinica_id: int) -> PrestadorOdonto | None:
    prestadores = (
        db.query(PrestadorOdonto)
        .filter(PrestadorOdonto.clinica_id == int(clinica_id))
        .order_by(PrestadorOdonto.id.asc())
        .all()
    )
    for item in prestadores:
        if is_system_prestador(item):
            return item
    return (
        db.query(PrestadorOdonto)
        .filter(
            PrestadorOdonto.clinica_id == int(clinica_id),
            PrestadorOdonto.source_id == int(SYSTEM_PRESTADOR_SOURCE_ID),
        )
        .first()
    )


def _detect_issues(db: Session, clinica_id: int) -> list[str]:
    issues: list[str] = []
    sys_user = _find_system_user(db, clinica_id)
    sys_prest = _find_system_prestador(db, clinica_id)

    if not sys_user:
        issues.append("missing_system_user")
    if not sys_prest:
        issues.append("missing_system_prestador")
    if sys_user:
        if (sys_user.nome or "").strip() != SYSTEM_USER_NOME:
            issues.append("system_user_nome_mismatch")
        if (sys_user.tipo_usuario or "").strip() != SYSTEM_USER_TIPO:
            issues.append("system_user_tipo_mismatch")
        if int(sys_user.codigo or 0) != int(SYSTEM_USER_CODIGO):
            issues.append("system_user_codigo_mismatch")
        if not bool(getattr(sys_user, "is_system_user", False)):
            issues.append("system_user_flag_missing")
        if not bool(getattr(sys_user, "ativo", False)):
            issues.append("system_user_inativo")
        if bool(getattr(sys_user, "online", False)):
            issues.append("system_user_online")
    if sys_prest:
        if int(sys_prest.source_id or 0) != int(SYSTEM_PRESTADOR_SOURCE_ID):
            issues.append("system_prestador_source_id_mismatch")
        if (sys_prest.nome or "").strip() != SYSTEM_USER_NOME:
            issues.append("system_prestador_nome_mismatch")
        if (sys_prest.tipo_prestador or "").strip() != SYSTEM_PRESTADOR_TIPO:
            issues.append("system_prestador_tipo_mismatch")
        if not bool(getattr(sys_prest, "is_system_prestador", False)):
            issues.append("system_prestador_flag_missing")
        if bool(getattr(sys_prest, "inativo", False)):
            issues.append("system_prestador_inativo")
        if not bool(getattr(sys_prest, "executa_procedimento", False)):
            issues.append("system_prestador_executa_false")
    if sys_user and sys_prest:
        if int(sys_user.prestador_id or 0) != int(sys_prest.id):
            issues.append("user_prestador_link_mismatch")
        if int(sys_prest.usuario_id or 0) != int(sys_user.id):
            issues.append("prestador_user_link_mismatch")
    return issues


def _render_state(db: Session, clinica_id: int) -> dict:
    sys_user = _find_system_user(db, clinica_id)
    sys_prest = _find_system_prestador(db, clinica_id)
    return {
        "system_user": {
            "exists": sys_user is not None,
            "usuario_id": int(sys_user.id) if sys_user else None,
            "codigo": int(sys_user.codigo) if sys_user and sys_user.codigo is not None else None,
            "nome": (sys_user.nome or "").strip() if sys_user else None,
            "tipo_usuario": (sys_user.tipo_usuario or "").strip() if sys_user else None,
            "prestador_id": int(sys_user.prestador_id) if sys_user and sys_user.prestador_id else None,
            "ativo": bool(getattr(sys_user, "ativo", False)) if sys_user else False,
            "online": bool(getattr(sys_user, "online", False)) if sys_user else False,
            "is_system_flag": bool(getattr(sys_user, "is_system_user", False)) if sys_user else False,
            "is_system_eval": bool(is_system_user(sys_user)) if sys_user else False,
        },
        "system_prestador": {
            "exists": sys_prest is not None,
            "prestador_id": int(sys_prest.id) if sys_prest else None,
            "source_id": int(sys_prest.source_id) if sys_prest and sys_prest.source_id is not None else None,
            "codigo": (sys_prest.codigo or "").strip() if sys_prest else None,
            "nome": (sys_prest.nome or "").strip() if sys_prest else None,
            "tipo_prestador": (sys_prest.tipo_prestador or "").strip() if sys_prest else None,
            "usuario_id": int(sys_prest.usuario_id) if sys_prest and sys_prest.usuario_id else None,
            "ativo": not bool(getattr(sys_prest, "inativo", False)) if sys_prest else False,
            "executa_procedimento": bool(getattr(sys_prest, "executa_procedimento", False)) if sys_prest else False,
            "is_system_flag": bool(getattr(sys_prest, "is_system_prestador", False)) if sys_prest else False,
            "is_system_eval": bool(is_system_prestador(sys_prest)) if sys_prest else False,
        },
    }


def _apply_fix(db: Session, clinica_id: int) -> dict:
    prestador = _garantir_prestador_sistemico_clinica(db, clinica_id)
    usuario = _garantir_usuario_sistemico_clinica(db, clinica_id, prestador)
    db.flush()
    return {
        "system_user_id": int(usuario.id),
        "system_prestador_id": int(prestador.id),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill conta sistemica (usuario/prestador 255) por clinica.")
    parser.add_argument("--apply", action="store_true", help="Aplica as correcoes no banco SaaS.")
    parser.add_argument("--clinica-id", type=int, default=0, help="Filtra uma clinica especifica.")
    args = parser.parse_args()

    _load_model_registry()
    today = datetime.now().strftime("%Y%m%d")
    today_human = datetime.now().strftime("%Y-%m-%d")

    with SessionLocal() as db:
        clinicas = db.query(Clinica).order_by(Clinica.id.asc()).all()
        if int(args.clinica_id) > 0:
            clinicas = [c for c in clinicas if int(c.id) == int(args.clinica_id)]

        results = []
        for clinica in clinicas:
            before = _render_state(db, int(clinica.id))
            issues = _detect_issues(db, int(clinica.id))
            applied = None
            if args.apply and issues:
                applied = _apply_fix(db, int(clinica.id))
            after = _render_state(db, int(clinica.id))
            results.append(
                {
                    "clinica_id": int(clinica.id),
                    "clinica_nome": clinica.nome,
                    "issues_before": issues,
                    "applied": applied,
                    "state_before": before,
                    "state_after": after,
                }
            )
        if args.apply:
            db.commit()

    output_dir = PROJECT_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"backfill_conta_sistemica_saas_{today}.json"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    docs_dir = PROJECT_DIR / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    report_path = docs_dir / f"backfill_conta_sistemica_saas_{today}.md"

    lines = []
    lines.append(f"# Backfill conta sistemica (SaaS) - {today_human}\n\n")
    lines.append(f"Modo: {'APLICADO' if args.apply else 'DRY-RUN'}\n\n")
    lines.append(
        f"Padrao: usuario codigo={SYSTEM_USER_CODIGO} nome='{SYSTEM_USER_NOME}' tipo='{SYSTEM_USER_TIPO}'\n\n"
    )
    for item in results:
        lines.append(f"## Clinica {item['clinica_id']} - {item['clinica_nome']}\n\n")
        issues = item["issues_before"] or []
        lines.append(f"- Issues before: {', '.join(issues) if issues else 'none'}\n")
        lines.append(f"- Applied: {item['applied']}\n")
        lines.append("- System user before:\n")
        lines.append(f"  - {item['state_before']['system_user']}\n")
        lines.append("- System prestador before:\n")
        lines.append(f"  - {item['state_before']['system_prestador']}\n")
        lines.append("- System user after:\n")
        lines.append(f"  - {item['state_after']['system_user']}\n")
        lines.append("- System prestador after:\n")
        lines.append(f"  - {item['state_after']['system_prestador']}\n\n")

    report_path.write_text("".join(lines), encoding="utf-8")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
