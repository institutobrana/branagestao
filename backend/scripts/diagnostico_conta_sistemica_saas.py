from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
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
    is_system_prestador,
    is_system_user,
)


def _load_model_registry() -> None:
    models_dir = BACKEND_DIR / "models"
    for path in models_dir.glob("*.py"):
        if path.name.startswith("_"):
            continue
        importlib.import_module(f"models.{path.stem}")


@dataclass
class SystemUserStatus:
    exists: bool
    usuario_id: int | None
    codigo: int | None
    nome: str | None
    tipo_usuario: str | None
    email: str | None
    is_system_flag: bool
    is_system_eval: bool
    prestador_id: int | None


@dataclass
class SystemPrestadorStatus:
    exists: bool
    prestador_id: int | None
    source_id: int | None
    codigo: str | None
    nome: str | None
    tipo_prestador: str | None
    is_system_flag: bool
    is_system_eval: bool
    usuario_id: int | None


def _build_user_status(usuario: Usuario | None) -> SystemUserStatus:
    if not usuario:
        return SystemUserStatus(
            exists=False,
            usuario_id=None,
            codigo=None,
            nome=None,
            tipo_usuario=None,
            email=None,
            is_system_flag=False,
            is_system_eval=False,
            prestador_id=None,
        )
    return SystemUserStatus(
        exists=True,
        usuario_id=int(usuario.id),
        codigo=int(usuario.codigo) if usuario.codigo is not None else None,
        nome=(usuario.nome or "").strip() or None,
        tipo_usuario=(usuario.tipo_usuario or "").strip() or None,
        email=(usuario.email or "").strip() or None,
        is_system_flag=bool(getattr(usuario, "is_system_user", False)),
        is_system_eval=bool(is_system_user(usuario)),
        prestador_id=int(usuario.prestador_id) if usuario.prestador_id else None,
    )


def _build_prestador_status(prestador: PrestadorOdonto | None) -> SystemPrestadorStatus:
    if not prestador:
        return SystemPrestadorStatus(
            exists=False,
            prestador_id=None,
            source_id=None,
            codigo=None,
            nome=None,
            tipo_prestador=None,
            is_system_flag=False,
            is_system_eval=False,
            usuario_id=None,
        )
    return SystemPrestadorStatus(
        exists=True,
        prestador_id=int(prestador.id),
        source_id=int(prestador.source_id) if prestador.source_id is not None else None,
        codigo=(prestador.codigo or "").strip() or None,
        nome=(prestador.nome or "").strip() or None,
        tipo_prestador=(prestador.tipo_prestador or "").strip() or None,
        is_system_flag=bool(getattr(prestador, "is_system_prestador", False)),
        is_system_eval=bool(is_system_prestador(prestador)),
        usuario_id=int(prestador.usuario_id) if prestador.usuario_id else None,
    )


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


def _diagnose_clinic(db: Session, clinica: Clinica) -> dict:
    clinica_id = int(clinica.id)
    users = (
        db.query(Usuario)
        .filter(Usuario.clinica_id == clinica_id)
        .order_by(Usuario.id.asc())
        .all()
    )
    prestadores = (
        db.query(PrestadorOdonto)
        .filter(PrestadorOdonto.clinica_id == clinica_id)
        .order_by(PrestadorOdonto.id.asc())
        .all()
    )

    sys_user = _find_system_user(db, clinica_id)
    sys_prest = _find_system_prestador(db, clinica_id)

    user_status = _build_user_status(sys_user)
    prest_status = _build_prestador_status(sys_prest)

    link_user_to_prest = None
    link_prest_to_user = None
    if user_status.exists and prest_status.exists:
        link_user_to_prest = int(user_status.prestador_id or 0) == int(prest_status.prestador_id or 0)
        link_prest_to_user = int(prest_status.usuario_id or 0) == int(user_status.usuario_id or 0)

    issues = []
    if not user_status.exists:
        issues.append("missing_system_user")
    if not prest_status.exists:
        issues.append("missing_system_prestador")
    if user_status.exists:
        if (user_status.nome or "").strip() != SYSTEM_USER_NOME:
            issues.append("system_user_nome_mismatch")
        if (user_status.tipo_usuario or "").strip() != SYSTEM_USER_TIPO:
            issues.append("system_user_tipo_mismatch")
    if prest_status.exists:
        if int(prest_status.source_id or 0) != int(SYSTEM_PRESTADOR_SOURCE_ID):
            issues.append("system_prestador_source_id_mismatch")
        if (prest_status.nome or "").strip() != SYSTEM_USER_NOME:
            issues.append("system_prestador_nome_mismatch")
    if user_status.exists and prest_status.exists:
        if link_user_to_prest is False:
            issues.append("user_prestador_link_mismatch")
        if link_prest_to_user is False:
            issues.append("prestador_user_link_mismatch")

    return {
        "clinica_id": clinica_id,
        "clinica_nome": clinica.nome,
        "usuarios_total": len(users),
        "prestadores_total": len(prestadores),
        "system_user": user_status.__dict__,
        "system_prestador": prest_status.__dict__,
        "link_user_to_prestador_ok": link_user_to_prest,
        "link_prestador_to_user_ok": link_prest_to_user,
        "issues": issues,
    }


def main() -> None:
    _load_model_registry()
    today = datetime.now().strftime("%Y%m%d")
    today_human = datetime.now().strftime("%Y-%m-%d")

    with SessionLocal() as db:
        clinicas = db.query(Clinica).order_by(Clinica.id.asc()).all()
        payload = [_diagnose_clinic(db, clinica) for clinica in clinicas]

    output_dir = PROJECT_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"diagnostico_conta_sistemica_saas_{today}.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    docs_dir = PROJECT_DIR / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    report_path = docs_dir / f"diagnostico_conta_sistemica_saas_{today}.md"

    lines = []
    lines.append(f"# Diagnostico conta sistemica (SaaS) - {today_human}\n\n")
    lines.append("Este relatorio e dry-run. Nenhuma alteracao foi aplicada.\n\n")
    lines.append(
        f"Padrao esperado: usuario codigo={SYSTEM_USER_CODIGO} nome='{SYSTEM_USER_NOME}' tipo='{SYSTEM_USER_TIPO}'\n\n"
    )

    for item in payload:
        lines.append(f"## Clinica {item['clinica_id']} - {item['clinica_nome']}\n\n")
        lines.append(f"- Usuarios: {item['usuarios_total']}\n")
        lines.append(f"- Prestadores: {item['prestadores_total']}\n")
        su = item["system_user"]
        sp = item["system_prestador"]
        lines.append("- System user:\n")
        lines.append(f"  - exists: {su['exists']}\n")
        lines.append(f"  - usuario_id: {su['usuario_id']}\n")
        lines.append(f"  - codigo: {su['codigo']}\n")
        lines.append(f"  - nome: {su['nome']}\n")
        lines.append(f"  - tipo_usuario: {su['tipo_usuario']}\n")
        lines.append(f"  - is_system_flag: {su['is_system_flag']}\n")
        lines.append(f"  - is_system_eval: {su['is_system_eval']}\n")
        lines.append(f"  - prestador_id: {su['prestador_id']}\n")
        lines.append("- System prestador:\n")
        lines.append(f"  - exists: {sp['exists']}\n")
        lines.append(f"  - prestador_id: {sp['prestador_id']}\n")
        lines.append(f"  - source_id: {sp['source_id']}\n")
        lines.append(f"  - codigo: {sp['codigo']}\n")
        lines.append(f"  - nome: {sp['nome']}\n")
        lines.append(f"  - tipo_prestador: {sp['tipo_prestador']}\n")
        lines.append(f"  - is_system_flag: {sp['is_system_flag']}\n")
        lines.append(f"  - is_system_eval: {sp['is_system_eval']}\n")
        lines.append(f"  - usuario_id: {sp['usuario_id']}\n")
        lines.append(f"- Link usuario->prestador OK: {item['link_user_to_prestador_ok']}\n")
        lines.append(f"- Link prestador->usuario OK: {item['link_prestador_to_user_ok']}\n")
        issues = item.get("issues") or []
        if issues:
            lines.append(f"- Issues: {', '.join(issues)}\n\n")
        else:
            lines.append("- Issues: none\n\n")

    report_path.write_text("".join(lines), encoding="utf-8")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
