from __future__ import annotations

import argparse
import csv
import importlib
import json
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal  # noqa: E402
from models.clinica import Clinica  # noqa: E402
from models.prestador_odonto import PrestadorOdonto  # noqa: E402
from models.usuario import Usuario  # noqa: E402
from security.hash import hash_password  # noqa: E402
from security.permissions import (  # noqa: E402
    compute_internal_permissions_from_easy,
    dump_permissions_json,
    merge_permissions_payload,
    normalize_tipo_usuario,
    parse_permissions_json,
    sanitize_easy_permissions,
    sanitize_permissions,
)
from security.system_accounts import SYSTEM_USER_CODIGO, is_system_user  # noqa: E402


DEFAULT_USERS_CSV = PROJECT_DIR / "usuarios_sql.csv"
DEFAULT_TIPOS_CSV = PROJECT_DIR / "output" / "easy_tipo_usuario_20260331.csv"
DEFAULT_USUARIO_MODULO_CSV = PROJECT_DIR / "usuario_modulo_sql.csv"
DEFAULT_USUARIO_FUNCAO_CSV = PROJECT_DIR / "usuario_funcao_sql.csv"
DEFAULT_SIS_MODULO_CSV = PROJECT_DIR / "sis_modulo_sql.csv"
DEFAULT_SIS_FUNCAO_CSV = PROJECT_DIR / "sis_funcao_sql.csv"
DEFAULT_USUARIO_PRESTADOR_JSON = (
    PROJECT_DIR / "output" / "investigacao_clinica_prestador_usuario_20260331.json"
)
DEFAULT_REPORT = PROJECT_DIR / "docs" / f"migracao_usuarios_easy_{datetime.now().date().isoformat()}.md"
DEFAULT_CHANGES = PROJECT_DIR / "output" / "migracao_usuarios_easy_changes.csv"


LEVEL_BY_NIVEL = {1: "habilitado", 3: "protegido"}


@dataclass
class EasyUser:
    codigo: int
    apelido: str
    nome: str
    tipo: int
    inativo: bool


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        delimiter = ","
        if ";" in sample and sample.count(";") >= sample.count(","):
            delimiter = ";"
        return list(csv.DictReader(handle, delimiter=delimiter))


def _load_model_registry() -> None:
    models_dir = BACKEND_DIR / "models"
    for path in models_dir.glob("*.py"):
        if path.name.startswith("_"):
            continue
        importlib.import_module(f"models.{path.stem}")


def _normalize(text: str | None) -> str:
    base = str(text or "").strip().lower()
    if not base:
        return ""
    base = unicodedata.normalize("NFKD", base)
    return "".join(ch for ch in base if not unicodedata.combining(ch))


def _build_internal_email(clinica_id: int, codigo: int, nome: str) -> str:
    slug = "".join(ch for ch in _normalize(nome) if ch.isalnum())[:20] or "usuario"
    return f"{slug}.{codigo}.c{int(clinica_id)}@local.brana"


def _ensure_unique_email(db, email: str) -> str:
    if not db.query(Usuario).filter(Usuario.email == email).first():
        return email
    base, _, domain = email.partition("@")
    idx = 1
    while True:
        candidate = f"{base}.{idx}@{domain}"
        if not db.query(Usuario).filter(Usuario.email == candidate).first():
            return candidate
        idx += 1


def _load_tipo_usuario_map(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}
    rows = _read_csv(path)
    mapping = {}
    for row in rows:
        try:
            codigo = int(row.get("REGISTRO") or 0)
        except Exception:
            codigo = 0
        if codigo <= 0:
            continue
        descricao = str(row.get("DESCRICAO") or "").strip()
        nome = str(row.get("NOME") or "").strip()
        mapping[codigo] = descricao or nome
    return mapping


def _load_easy_users(path: Path) -> list[EasyUser]:
    rows = _read_csv(path)
    users = []
    for row in rows:
        try:
            codigo = int(row.get("NROUSR") or 0)
        except Exception:
            codigo = 0
        if codigo <= 0:
            continue
        apelido = str(row.get("APELIDO") or "").strip()
        nome = str(row.get("NOME") or "").strip()
        try:
            tipo = int(row.get("TIPO") or 0)
        except Exception:
            tipo = 0
        inativo = str(row.get("INATIVO") or "").strip() not in {"0", "", "false", "False"}
        users.append(EasyUser(codigo=codigo, apelido=apelido, nome=nome, tipo=tipo, inativo=inativo))
    return users


def _load_easy_permissions(csv_modulo: Path, csv_funcao: Path) -> tuple[dict[int, dict[int, str]], dict[int, dict[int, str]]]:
    if not csv_modulo.exists() or not csv_funcao.exists():
        return {}, {}
    mods = {}
    for row in _read_csv(csv_modulo):
        try:
            user_id = int(row.get("ID_USUARIO") or 0)
            mod_id = int(row.get("ID_MODULO") or 0)
            nivel = int(row.get("NIVEL") or 0)
        except Exception:
            continue
        if user_id <= 0 or mod_id <= 0:
            continue
        level = LEVEL_BY_NIVEL.get(nivel, "desabilitado")
        mods.setdefault(user_id, {})[mod_id] = level

    funs = {}
    for row in _read_csv(csv_funcao):
        try:
            user_id = int(row.get("ID_USUARIO") or 0)
            func_id = int(row.get("ID_FUNCAO") or 0)
            nivel = int(row.get("NIVEL") or 0)
        except Exception:
            continue
        if user_id <= 0 or func_id <= 0:
            continue
        level = LEVEL_BY_NIVEL.get(nivel, "desabilitado")
        funs.setdefault(user_id, {})[func_id] = level
    return mods, funs


def _load_usuario_prestador_map(path: Path) -> dict[int, int]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    users_all = payload.get("users_all") if isinstance(payload, dict) else None
    if not isinstance(users_all, list):
        return {}
    mapping: dict[int, int] = {}
    for row in users_all:
        if not isinstance(row, dict):
            continue
        try:
            user_id = int(row.get("NROUSR") or 0)
        except Exception:
            user_id = 0
        try:
            prest_id = int(row.get("ID_PRESTADOR") or 0)
        except Exception:
            prest_id = 0
        if user_id > 0 and prest_id > 0:
            mapping[user_id] = prest_id
    return mapping


def _load_module_names(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}
    return {int(row["ID_MODULO"]): str(row["NOME_MODULO"]).strip() for row in _read_csv(path) if row.get("ID_MODULO")}


def _build_easy_module_levels(
    user_id: int,
    modules: dict[int, str],
    user_mods: dict[int, dict[int, str]],
) -> dict[str, str]:
    levels = {}
    mod_levels = user_mods.get(user_id, {})
    for mod_id in modules.keys():
        levels[str(mod_id)] = mod_levels.get(mod_id, "desabilitado")
    return levels


def _build_easy_function_levels(
    user_id: int,
    user_funcs: dict[int, dict[int, str]],
) -> dict[str, str]:
    return {str(func_id): level for func_id, level in user_funcs.get(user_id, {}).items()}


def _match_existing_user(
    db,
    clinica_id: int,
    codigo: int,
    nome: str,
    clinica_email: str,
    *,
    allow_email_match: bool = False,
    exclude_user_id: int | None = None,
) -> Usuario | None:
    if codigo:
        match = (
            db.query(Usuario)
            .filter(Usuario.clinica_id == clinica_id, Usuario.codigo == codigo)
            .first()
        )
        if match and (exclude_user_id is None or match.id != exclude_user_id):
            return match

    norm_nome = _normalize(nome)
    if norm_nome:
        match = (
            db.query(Usuario)
            .filter(Usuario.clinica_id == clinica_id)
            .order_by(Usuario.id.asc())
            .all()
        )
        for item in match:
            if exclude_user_id is not None and item.id == exclude_user_id:
                continue
            if _normalize(item.nome) == norm_nome:
                return item

    if allow_email_match and clinica_email:
        match = (
            db.query(Usuario)
            .filter(Usuario.clinica_id == clinica_id, Usuario.email == clinica_email)
            .first()
        )
        if match and (exclude_user_id is None or match.id != exclude_user_id):
            return match
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Migra usuarios do EasyDental (CSV) para SaaS.")
    parser.add_argument("--email", help="E-mail do dono da clinica SaaS (ex: gleissontel@gmail.com).")
    parser.add_argument("--clinica-id", type=int, default=0, help="ID da clinica SaaS.")
    parser.add_argument("--csv", default=str(DEFAULT_USERS_CSV), help="CSV com usuarios do Easy (usuarios_sql.csv).")
    parser.add_argument("--tipos-csv", default=str(DEFAULT_TIPOS_CSV), help="CSV com tipos de usuario do Easy.")
    parser.add_argument("--usuario-modulo-csv", default=str(DEFAULT_USUARIO_MODULO_CSV))
    parser.add_argument("--usuario-funcao-csv", default=str(DEFAULT_USUARIO_FUNCAO_CSV))
    parser.add_argument("--sis-modulo-csv", default=str(DEFAULT_SIS_MODULO_CSV))
    parser.add_argument("--usuario-prestador-json", default=str(DEFAULT_USUARIO_PRESTADOR_JSON))
    parser.add_argument("--apply", action="store_true", help="Aplica a migracao no banco.")
    args = parser.parse_args()

    load_dotenv(BACKEND_DIR / ".env")
    _load_model_registry()

    users_csv = Path(args.csv)
    if not users_csv.exists():
        raise RuntimeError(f"CSV de usuarios nao encontrado: {users_csv}")

    tipo_map = _load_tipo_usuario_map(Path(args.tipos_csv))
    easy_users = _load_easy_users(users_csv)

    user_mods, user_funcs = _load_easy_permissions(
        Path(args.usuario_modulo_csv),
        Path(args.usuario_funcao_csv),
    )
    modules = _load_module_names(Path(args.sis_modulo_csv))
    usuario_prest_map = _load_usuario_prestador_map(Path(args.usuario_prestador_json))

    db = SessionLocal()
    try:
        clinica = None
        if args.clinica_id:
            clinica = db.query(Clinica).filter(Clinica.id == int(args.clinica_id)).first()
        if clinica is None and args.email:
            owner = db.query(Usuario).filter(Usuario.email == args.email).first()
            if owner:
                clinica = db.query(Clinica).filter(Clinica.id == owner.clinica_id).first()
        if not clinica:
            raise RuntimeError("Clinica alvo nao encontrada. Informe --email ou --clinica-id.")

        owner_user = None
        if args.email:
            owner_user = db.query(Usuario).filter(Usuario.email == args.email).first()

        clinica_nome_norm = _normalize(getattr(clinica, "nome", "") or "")
        owner_easy_codigo = None
        if clinica_nome_norm:
            for easy_user in easy_users:
                if _normalize(easy_user.nome) == clinica_nome_norm:
                    owner_easy_codigo = easy_user.codigo
                    break
        if owner_easy_codigo is None:
            for easy_user in easy_users:
                if easy_user.codigo == 1:
                    owner_easy_codigo = easy_user.codigo
                    break

        report_lines = []
        report_lines.append(f"# Migração de usuários Easy -> SaaS ({datetime.now().date().isoformat()})\n")
        report_lines.append(f"- Clínica: {clinica.id} - {clinica.nome}\n")
        report_lines.append(f"- Modo: {'APLICADO' if args.apply else 'DRY-RUN'}\n\n")
        report_lines.append(
            "| Easy ID | Nome | Tipo (Easy) | Prestador (Easy) | Usuário SaaS | Ação | E-mail | Forçar senha |\n"
        )
        report_lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |\n")

        changes = []

        prestadores = (
            db.query(PrestadorOdonto)
            .filter(PrestadorOdonto.clinica_id == clinica.id)
            .all()
        )
        prestador_by_source = {
            int(item.source_id): int(item.id)
            for item in prestadores
            if item.source_id is not None
        }

        for easy_user in easy_users:
            if easy_user.codigo == SYSTEM_USER_CODIGO:
                continue
            if not easy_user.nome:
                continue

            tipo_txt = tipo_map.get(easy_user.tipo, "")
            tipo_usuario = normalize_tipo_usuario(tipo_txt)
            apelido = easy_user.apelido or (easy_user.nome.split(" ", 1)[0] if easy_user.nome else "")

            is_owner = False
            if owner_user and owner_easy_codigo is not None and easy_user.codigo == owner_easy_codigo:
                is_owner = True
            elif owner_user and clinica_nome_norm and _normalize(easy_user.nome) == clinica_nome_norm:
                is_owner = True

            existing = None
            if is_owner and owner_user:
                existing = owner_user
            else:
                existing = _match_existing_user(
                    db,
                    clinica_id=clinica.id,
                    codigo=easy_user.codigo,
                    nome=easy_user.nome,
                    clinica_email=args.email or "",
                    allow_email_match=False,
                    exclude_user_id=owner_user.id if owner_user else None,
                )

            action = "criado"
            if existing:
                action = "atualizado"
                existing.nome = easy_user.nome
                if apelido:
                    existing.apelido = apelido
                if tipo_usuario:
                    existing.tipo_usuario = tipo_usuario
                if easy_user.codigo and (existing.codigo is None or int(existing.codigo) != int(easy_user.codigo)):
                    existing.codigo = int(easy_user.codigo)
                existing.ativo = not easy_user.inativo
                if not existing.ativo:
                    existing.online = False
                if is_owner:
                    existing.is_admin = True
                    existing.forcar_troca_senha = False
                else:
                    existing.is_admin = False
                    existing.forcar_troca_senha = True
                if not is_owner and args.email and existing.email == args.email:
                    existing.email = _ensure_unique_email(
                        db,
                        _build_internal_email(clinica.id, easy_user.codigo, easy_user.nome),
                    )
                if is_owner and args.email:
                    existing.email = args.email
                user = existing
            else:
                if is_owner and args.email:
                    email = args.email
                else:
                    email = _ensure_unique_email(
                        db,
                        _build_internal_email(clinica.id, easy_user.codigo, easy_user.nome),
                    )
                senha_temp = f"Temp@{easy_user.codigo}"
                user = Usuario(
                    codigo=int(easy_user.codigo),
                    nome=easy_user.nome,
                    apelido=apelido,
                    tipo_usuario=tipo_usuario,
                    email=email,
                    senha_hash=hash_password(senha_temp),
                    clinica_id=clinica.id,
                    is_admin=bool(is_owner),
                    ativo=not easy_user.inativo,
                    online=False,
                    forcar_troca_senha=False if is_owner else True,
                    is_system_user=False,
                )
                db.add(user)

            easy_mod_levels = _build_easy_module_levels(easy_user.codigo, modules, user_mods)
            easy_func_levels = _build_easy_function_levels(easy_user.codigo, user_funcs)
            easy_mod_levels, easy_func_levels = sanitize_easy_permissions(easy_mod_levels, easy_func_levels)
            internal = compute_internal_permissions_from_easy(easy_mod_levels)

            raw_permissions = user.permissoes_json
            existing_payload = (
                raw_permissions
                if isinstance(raw_permissions, dict)
                else parse_permissions_json(raw_permissions)
            )
            merged = merge_permissions_payload(
                existing_payload,
                internal,
                easy_modules=easy_mod_levels,
                easy_funcoes=easy_func_levels,
            )
            user.permissoes_json = dump_permissions_json(merged)

            prestador_easy = usuario_prest_map.get(easy_user.codigo) if usuario_prest_map else None
            if prestador_easy is not None:
                prest_row_id = prestador_by_source.get(int(prestador_easy))
                user.prestador_id = int(prest_row_id) if prest_row_id else None

            email_out = user.email or ""
            report_lines.append(
                f"| {easy_user.codigo} | {easy_user.nome} | {tipo_txt or easy_user.tipo} | {prestador_easy or ''} | {user.nome} | {action} | {email_out} | {user.forcar_troca_senha} |\n"
            )
            changes.append(
                {
                    "easy_id": easy_user.codigo,
                    "nome": easy_user.nome,
                    "tipo_easy": tipo_txt or str(easy_user.tipo),
                    "prestador_easy": prestador_easy or "",
                    "acao": action,
                    "email": email_out,
                    "forcar_troca_senha": user.forcar_troca_senha,
                }
            )

        if args.apply:
            db.commit()
        else:
            db.rollback()

        DEFAULT_REPORT.write_text("".join(report_lines), encoding="utf-8")
        DEFAULT_CHANGES.parent.mkdir(parents=True, exist_ok=True)
        with DEFAULT_CHANGES.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "easy_id",
                    "nome",
                    "tipo_easy",
                    "prestador_easy",
                    "acao",
                    "email",
                    "forcar_troca_senha",
                ],
            )
            writer.writeheader()
            writer.writerows(changes)
        print(f"Report: {DEFAULT_REPORT}")
        print(f"Changes: {DEFAULT_CHANGES}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
