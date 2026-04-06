from __future__ import annotations

import argparse
import csv
import json
import importlib
import os
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv

try:
    import pyodbc  # type: ignore
except Exception:  # pragma: no cover
    pyodbc = None

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal  # noqa: E402
from models.clinica import Clinica  # noqa: E402
from models.usuario import Usuario  # noqa: E402
from security.permissions import (  # noqa: E402
    MODULE_PERMISSION_SCHEMA,
    dump_permissions_json,
    sanitize_permissions,
)


DEFAULT_EASY_SERVER = r"DELL_SERVIDOR\EDS70"
DEFAULT_EASY_DATABASE = "eds70"
DEFAULT_EASY_UID = "easy"
DEFAULT_EASY_PWD = "ysae"

DEFAULT_ENV_PATH = BACKEND_DIR / ".env"
DEFAULT_CSV_DIR = PROJECT_DIR
DEFAULT_REPORT = PROJECT_DIR / "docs" / "migracao_permissoes_usuarios_eds70_20260330.md"
DEFAULT_MAPPING_CSV = PROJECT_DIR / "docs" / "mapeamento_permissoes_eds70_para_saas_20260330.csv"

LEVEL_BY_NIVEL = {1: "habilitado", 3: "protegido"}


@dataclass
class EasyModule:
    id: int
    nome: str


@dataclass
class EasyFunction:
    id: int
    modulo_id: int
    nome: str


@dataclass
class EasyUser:
    id: int
    apelido: str | None
    nome: str | None


def _normalize_text(value: str | None) -> str:
    text = (value or "").strip().lower()
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _load_model_registry() -> None:
    models_dir = BACKEND_DIR / "models"
    for path in models_dir.glob("*.py"):
        if path.name.startswith("_"):
            continue
        importlib.import_module(f"models.{path.stem}")


def _connect_easy(server: str, database: str, user: str, password: str, trusted: bool):
    if pyodbc is None:
        raise RuntimeError("pyodbc nao instalado. Instale pyodbc para conectar ao EasyDental.")
    if trusted:
        conn_str = (
            "DRIVER={SQL Server};"
            f"SERVER={server};"
            f"DATABASE={database};"
            "Trusted_Connection=yes"
        )
    else:
        conn_str = (
            "DRIVER={SQL Server};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={user};"
            f"PWD={password};"
            "Trusted_Connection=no"
        )
    return pyodbc.connect(conn_str, timeout=10)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _load_easy_data_from_sql(
    server: str,
    database: str,
    user: str,
    password: str,
    trusted: bool,
) -> tuple[list[EasyModule], list[EasyFunction], list[EasyUser], list[dict[str, Any]], list[dict[str, Any]]]:
    conn = _connect_easy(server, database, user, password, trusted)
    try:
        cur = conn.cursor()
        cur.execute("SELECT ID_MODULO, NOME_MODULO FROM SIS_MODULO ORDER BY ID_MODULO")
        modules = [EasyModule(int(row[0]), str(row[1])) for row in cur.fetchall()]

        cur.execute("SELECT ID_FUNCAO, ID_MODULO, NOME_FUNCAO FROM SIS_FUNCAO ORDER BY ID_FUNCAO")
        funcoes = [EasyFunction(int(row[0]), int(row[1]), str(row[2])) for row in cur.fetchall()]

        cur.execute("SELECT NROUSR, APELIDO, NOME FROM USUARIO ORDER BY NROUSR")
        users = [EasyUser(int(row[0]), row[1], row[2]) for row in cur.fetchall()]

        cur.execute("SELECT ID_USUARIO, ID_MODULO, NIVEL FROM USUARIO_MODULO")
        usuario_modulo = [
            {"ID_USUARIO": int(row[0]), "ID_MODULO": int(row[1]), "NIVEL": int(row[2])}
            for row in cur.fetchall()
        ]

        cur.execute("SELECT ID_USUARIO, ID_FUNCAO, NIVEL FROM USUARIO_FUNCAO")
        usuario_funcao = [
            {"ID_USUARIO": int(row[0]), "ID_FUNCAO": int(row[1]), "NIVEL": int(row[2])}
            for row in cur.fetchall()
        ]
    finally:
        conn.close()
    return modules, funcoes, users, usuario_modulo, usuario_funcao


def _load_easy_data_from_csv(csv_dir: Path):
    modules_csv = csv_dir / "sis_modulo_sql.csv"
    funcoes_csv = csv_dir / "sis_funcao_sql.csv"
    users_csv = csv_dir / "usuarios_sql.csv"
    usuario_modulo_csv = csv_dir / "usuario_modulo_sql.csv"
    usuario_funcao_csv = csv_dir / "usuario_funcao_sql.csv"

    missing = [p for p in [modules_csv, funcoes_csv, users_csv, usuario_modulo_csv, usuario_funcao_csv] if not p.exists()]
    if missing:
        raise RuntimeError(
            "CSVs necessarios nao encontrados. Faltando: " + ", ".join(str(p) for p in missing)
        )

    modules = [
        EasyModule(int(row["ID_MODULO"]), row["NOME_MODULO"])
        for row in _read_csv(modules_csv)
    ]
    funcoes = [
        EasyFunction(int(row["ID_FUNCAO"]), int(row["ID_MODULO"]), row["NOME_FUNCAO"])
        for row in _read_csv(funcoes_csv)
    ]
    users = [
        EasyUser(int(row["NROUSR"]), row.get("APELIDO"), row.get("NOME"))
        for row in _read_csv(users_csv)
    ]
    usuario_modulo = [
        {
            "ID_USUARIO": int(row["ID_USUARIO"]),
            "ID_MODULO": int(row["ID_MODULO"]),
            "NIVEL": int(row["NIVEL"]),
        }
        for row in _read_csv(usuario_modulo_csv)
    ]
    usuario_funcao = [
        {
            "ID_USUARIO": int(row["ID_USUARIO"]),
            "ID_FUNCAO": int(row["ID_FUNCAO"]),
            "NIVEL": int(row["NIVEL"]),
        }
        for row in _read_csv(usuario_funcao_csv)
    ]
    return modules, funcoes, users, usuario_modulo, usuario_funcao


def _resolve_mapping_for_module(name: str) -> str:
    base = name.strip().lower()
    if base.startswith("odontograma") or base.startswith("tratamento") or base.startswith("tratamento - orçamento"):
        return "procedimentos"
    if base.startswith("especialidades"):
        return "procedimentos"
    if base.startswith("cadastro - ficha de histórico"):
        return "procedimentos"
    if base.startswith("cadastro - dados pessoais"):
        return "procedimentos"
    if base.startswith("cadastro - dados complementares"):
        return "procedimentos"
    if base.startswith("cadastro - anotações do paciente"):
        return "procedimentos"
    if base.startswith("cadastro - controle de protéticos"):
        return "procedimentos"
    if base.startswith("configuração - tabelas de intervenções"):
        return "procedimentos"
    if base.startswith("configuração - tabela de procedimentos genéricos"):
        return "procedimentos"
    if base.startswith("configuração - símbolos gráficos"):
        return "procedimentos"
    if base.startswith("configuração - tabelas de serviços de prótese"):
        return "procedimentos"

    if base.startswith("agenda -"):
        return "agenda"
    if base.startswith("configuração - agendas"):
        return "agenda"
    if base.startswith("cadastro - controle de retornos"):
        return "agenda"

    if base.startswith("cadastro - ficha de anamnese"):
        return "anamnese"
    if base.startswith("configuração - anamnese"):
        return "anamnese"
    if base.startswith("configuração - tabela de doenças"):
        return "anamnese"
    if base.startswith("cadastro - restrições terapêuticas"):
        return "anamnese"

    if base.startswith("financeiro -"):
        return "financeiro"
    if base.startswith("configuração - índices financeiros"):
        return "financeiro"
    if base.startswith("configuração - plano de contas"):
        return "financeiro"

    if base.startswith("cadastro - controle de estoque"):
        return "materiais"
    if base.startswith("configuração - tabelas de materiais"):
        return "materiais"

    if base.startswith("relatório -") or base.startswith("relatorio -"):
        return "relatorios"
    if base.startswith("configuração - relatórios"):
        return "relatorios"
    if base.startswith("configuração - etiquetas"):
        return "relatorios"

    if base.startswith("cadastro - prestadores"):
        return "prestadores"

    if base.startswith("configuração -"):
        return "configuracao"
    if base.startswith("cadastro -"):
        return "configuracao"
    if base.startswith("ferramentas -"):
        return "configuracao"
    return "configuracao"


def _build_mapping(modules: list[EasyModule]) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for mod in modules:
        mapping[mod.id] = _resolve_mapping_for_module(mod.nome)
    return mapping


def _write_mapping_csv(modules: list[EasyModule], mapping: dict[int, str], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id_modulo", "nome_modulo", "saas_modulo"],
        )
        writer.writeheader()
        for mod in modules:
            writer.writerow(
                {
                    "id_modulo": mod.id,
                    "nome_modulo": mod.nome,
                    "saas_modulo": mapping.get(mod.id, ""),
                }
            )


def _nivel_to_label(value: int | None) -> str | None:
    if value is None:
        return None
    return LEVEL_BY_NIVEL.get(value)


def _pick_conservative_level(levels: Iterable[str]) -> str:
    normalized = {str(level or "").strip().lower() for level in levels}
    if "protegido" in normalized:
        return "protegido"
    if "habilitado" in normalized:
        return "habilitado"
    return "desabilitado"


def _match_easy_user(
    easy_users: list[EasyUser],
    *,
    codigo: int | None,
    apelido: str | None,
    nome: str | None,
) -> tuple[EasyUser | None, str]:
    if codigo is not None:
        for user in easy_users:
            if user.id == codigo:
                return user, "codigo"
    apelido_norm = _normalize_text(apelido)
    if apelido_norm:
        matches = [u for u in easy_users if _normalize_text(u.apelido) == apelido_norm]
        if len(matches) == 1:
            return matches[0], "apelido"
    nome_norm = _normalize_text(nome)
    if nome_norm:
        matches = [u for u in easy_users if _normalize_text(u.nome) == nome_norm]
        if len(matches) == 1:
            return matches[0], "nome"
    return None, ""


def _load_env(env_path: Path) -> None:
    if env_path.exists():
        load_dotenv(env_path)


def _build_permissions_for_user(
    *,
    saas_user: Usuario,
    easy_user_id: int,
    mapping: dict[int, str],
    module_levels: dict[tuple[int, int], str],
    module_ids: list[int],
) -> dict[str, str]:
    if saas_user.is_admin:
        return {item["codigo"]: "habilitado" for item in MODULE_PERMISSION_SCHEMA}

    by_code: dict[str, list[str]] = {item["codigo"]: [] for item in MODULE_PERMISSION_SCHEMA}
    for mod_id in module_ids:
        saas_code = mapping.get(mod_id)
        if not saas_code:
            continue
        level = module_levels.get((easy_user_id, mod_id))
        if level:
            by_code.setdefault(saas_code, []).append(level)

    resolved = {}
    for item in MODULE_PERMISSION_SCHEMA:
        code = item["codigo"]
        levels = by_code.get(code, [])
        # Consolidation is conservative because multiple Easy modules/functions
        # can map to one SaaS module code.
        resolved[code] = _pick_conservative_level(levels) if levels else "desabilitado"
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migra permissoes de usuarios do EasyDental (EDS70) para permissoes_json do SaaS."
    )
    parser.add_argument("--server", default=DEFAULT_EASY_SERVER)
    parser.add_argument("--database", default=DEFAULT_EASY_DATABASE)
    parser.add_argument("--user", default=DEFAULT_EASY_UID)
    parser.add_argument("--password", default=DEFAULT_EASY_PWD)
    parser.add_argument("--trusted", action="store_true")
    parser.add_argument("--env-path", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--csv-dir", default=str(DEFAULT_CSV_DIR))
    parser.add_argument("--mapping-csv", default=str(DEFAULT_MAPPING_CSV))
    parser.add_argument("--email", default="", help="Email de usuario do SaaS para identificar a clinica alvo.")
    parser.add_argument("--clinica-id", type=int, default=0, help="ID da clinica alvo (opcional).")
    parser.add_argument("--all-clinicas", action="store_true", help="Processa todas as clinicas do SaaS.")
    parser.add_argument("--apply", action="store_true", help="Aplica as mudancas no banco do SaaS.")
    parser.add_argument("--overwrite", action="store_true", help="Sobrescreve permissoes_json existentes.")
    parser.add_argument("--auto-match", action="store_true", help="Tenta casar usuarios por codigo/apelido/nome.")
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    args = parser.parse_args()

    _load_env(Path(args.env_path))
    _load_model_registry()

    try:
        modules, funcoes, easy_users, usuario_modulo, usuario_funcao = _load_easy_data_from_sql(
            args.server,
            args.database,
            args.user,
            args.password,
            args.trusted,
        )
        source = "SQL"
    except Exception as exc:
        modules, funcoes, easy_users, usuario_modulo, usuario_funcao = _load_easy_data_from_csv(
            Path(args.csv_dir)
        )
        source = f"CSV ({exc})"

    mapping = _build_mapping(modules)
    _write_mapping_csv(modules, mapping, Path(args.mapping_csv))

    module_ids = [mod.id for mod in modules]
    fun_mod_by_id = {fn.id: fn.modulo_id for fn in funcoes}

    module_level_buckets: dict[tuple[int, int], list[str]] = {}
    for row in usuario_modulo:
        level = _nivel_to_label(row.get("NIVEL"))
        if level:
            key = (row["ID_USUARIO"], row["ID_MODULO"])
            module_level_buckets.setdefault(key, []).append(level)
    for row in usuario_funcao:
        mod_id = fun_mod_by_id.get(row["ID_FUNCAO"])
        if mod_id is None:
            continue
        level = _nivel_to_label(row.get("NIVEL"))
        if not level:
            continue
        key = (row["ID_USUARIO"], mod_id)
        module_level_buckets.setdefault(key, []).append(level)
    module_levels: dict[tuple[int, int], str] = {
        key: _pick_conservative_level(levels)
        for key, levels in module_level_buckets.items()
    }

    db = SessionLocal()
    try:
        clinicas: list[Clinica] = []
        if args.all_clinicas:
            clinicas = db.query(Clinica).order_by(Clinica.id).all()
        elif args.clinica_id:
            clinica = db.query(Clinica).filter(Clinica.id == args.clinica_id).first()
            if clinica:
                clinicas = [clinica]
        elif args.email:
            user = db.query(Usuario).filter(Usuario.email == args.email).first()
            if user:
                clinica = db.query(Clinica).filter(Clinica.id == user.clinica_id).first()
                if clinica:
                    clinicas = [clinica]

        if not clinicas:
            raise RuntimeError("Clinica alvo nao encontrada. Use --clinica-id, --email ou --all-clinicas.")

        easy_users_by_id = {user.id: user for user in easy_users}

        report_lines: list[str] = []
        report_lines.append(f"# Migração de permissões Easy -> SaaS ({datetime.now().date().isoformat()})")
        report_lines.append("")
        report_lines.append(f"Fonte Easy: {source}")
        report_lines.append(f"Modo: {'APLICADO' if args.apply else 'DRY-RUN'}")
        report_lines.append("")
        report_lines.append("## Resumo por clinica")
        report_lines.append("")

        changes: list[dict[str, Any]] = []
        unchanged: list[dict[str, Any]] = []
        unmatched_saas: list[dict[str, Any]] = []
        skipped_existing = 0
        matched_easy_ids: set[int] = set()
        for clinica in clinicas:
            saas_users = (
                db.query(Usuario)
                .filter(Usuario.clinica_id == clinica.id)
                .order_by(Usuario.id)
                .all()
            )
            report_lines.append(f"### Clinica {clinica.id} - {clinica.nome}")
            report_lines.append(f"- Usuarios SaaS: {len(saas_users)}")

            for saas_user in saas_users:
                match = None
                match_type = ""
                if args.auto_match:
                    match, match_type = _match_easy_user(
                        easy_users,
                        codigo=saas_user.codigo,
                        apelido=saas_user.apelido,
                        nome=saas_user.nome,
                    )
                if match is None:
                    unmatched_saas.append(
                        {
                            "clinica_id": clinica.id,
                            "saas_user_id": saas_user.id,
                            "saas_nome": saas_user.nome,
                        }
                    )
                    report_lines.append(
                        f"  - Usuario {saas_user.id} ({saas_user.nome}) sem correspondencia no Easy."
                    )
                    continue
                matched_easy_ids.add(match.id)

                permissoes = _build_permissions_for_user(
                    saas_user=saas_user,
                    easy_user_id=match.id,
                    mapping=mapping,
                    module_levels=module_levels,
                    module_ids=module_ids,
                )
                permissoes = sanitize_permissions(
                    permissoes,
                    tipo_usuario=saas_user.tipo_usuario,
                    is_admin=bool(saas_user.is_admin),
                )
                novo_json = dump_permissions_json(permissoes)
                atual_json = saas_user.permissoes_json
                if atual_json and not args.overwrite:
                    skipped_existing += 1
                    report_lines.append(
                        f"  - Usuario {saas_user.id} ({saas_user.nome}) mantido "
                        f"(permissoes_json ja existe)."
                    )
                    continue

                if atual_json == novo_json:
                    unchanged.append(
                        {
                            "saas_user_id": saas_user.id,
                            "saas_nome": saas_user.nome,
                            "easy_user_id": match.id,
                            "easy_nome": match.nome,
                            "match_type": match_type,
                        }
                    )
                    report_lines.append(
                        f"  - Usuario {saas_user.id} ({saas_user.nome}) <= Easy {match.id} "
                        f"({match.nome}) via {match_type} (sem alteracao)."
                    )
                    continue

                changes.append(
                    {
                        "saas_user_id": saas_user.id,
                        "saas_nome": saas_user.nome,
                        "easy_user_id": match.id,
                        "easy_nome": match.nome,
                        "match_type": match_type,
                        "permissoes_json_old": atual_json,
                        "permissoes_json_new": novo_json,
                    }
                )

                report_lines.append(
                    f"  - Usuario {saas_user.id} ({saas_user.nome}) <= Easy {match.id} "
                    f"({match.nome}) via {match_type}."
                )

                if args.apply:
                    saas_user.permissoes_json = novo_json

        if args.apply:
            db.commit()
        else:
            db.rollback()

        report_lines.append("")
        report_lines.append("## Alteracoes planejadas")
        if not changes:
            report_lines.append("- Nenhuma alteracao.")
        else:
            report_lines.append(f"- Total de usuarios alterados: {len(changes)}")
        report_lines.append(f"- Usuarios sem alteracao (json identico): {len(unchanged)}")
        report_lines.append(f"- Usuarios sem match SaaS -> Easy: {len(unmatched_saas)}")
        report_lines.append(f"- Usuarios mantidos por permissoes_json existente: {skipped_existing}")

        easy_without_match = [u for u in easy_users if u.id not in matched_easy_ids]
        report_lines.append(f"- Usuarios Easy sem match no SaaS processado: {len(easy_without_match)}")

        if unmatched_saas:
            report_lines.append("")
            report_lines.append("## SaaS sem correspondencia no Easy")
            for row in unmatched_saas:
                report_lines.append(
                    f"- Clinica {row['clinica_id']} | Usuario {row['saas_user_id']} ({row['saas_nome']})"
                )

        if easy_without_match:
            report_lines.append("")
            report_lines.append("## Easy sem correspondencia no SaaS")
            for u in easy_without_match:
                report_lines.append(
                    f"- Easy {u.id} ({u.nome or '-'} / {u.apelido or '-'})"
                )

        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(report_lines), encoding="utf-8")

        changes_path = PROJECT_DIR / "output" / "migracao_permissoes_usuarios_changes.csv"
        changes_path.parent.mkdir(parents=True, exist_ok=True)
        with changes_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "saas_user_id",
                    "saas_nome",
                    "easy_user_id",
                    "easy_nome",
                    "match_type",
                    "permissoes_json_old",
                    "permissoes_json_new",
                ],
            )
            writer.writeheader()
            for row in changes:
                writer.writerow(row)

        print(f"Relatorio: {report_path}")
        print(f"Mudancas: {changes_path}")
        print("Modo:", "APLICADO" if args.apply else "DRY-RUN")
    finally:
        db.close()


if __name__ == "__main__":
    main()
