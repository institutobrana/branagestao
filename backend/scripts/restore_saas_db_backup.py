import argparse
import csv
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import psycopg2
from dotenv import load_dotenv


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
DEFAULT_ENV_PATH = BACKEND_DIR / ".env"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Restaura um backup gerado por backup_saas_db.py para o banco do SaaS."
    )
    parser.add_argument(
        "backup_path",
        help="Diretorio do backup ou arquivo .zip gerado pelo script de backup.",
    )
    parser.add_argument(
        "--env-path",
        default=str(DEFAULT_ENV_PATH),
        help="Caminho para o .env do backend do SaaS.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirma que o banco atual pode ser sobrescrito.",
    )
    return parser.parse_args()


def _load_database_url(env_path: Path) -> str:
    if not env_path.exists():
        raise FileNotFoundError(f".env nao encontrado: {env_path}")
    load_dotenv(env_path, override=True)
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(f"DATABASE_URL nao encontrado em {env_path}")
    return database_url


def _redact_database_url(database_url: str) -> str:
    parsed = urlparse(database_url)
    username = parsed.username or ""
    host = parsed.hostname or ""
    port = parsed.port or ""
    database = (parsed.path or "").lstrip("/")
    auth = username if username else ""
    if auth:
        auth = f"{auth}:***@"
    host_part = host
    if port:
        host_part = f"{host}:{port}"
    return f"{parsed.scheme}://{auth}{host_part}/{database}"


def _resolve_backup_path(backup_path: Path) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if backup_path.is_dir():
        return backup_path, None
    if backup_path.is_file() and backup_path.suffix.lower() == ".zip":
        temp_dir = tempfile.TemporaryDirectory(prefix="saas_restore_")
        with zipfile.ZipFile(backup_path, "r") as archive:
            archive.extractall(temp_dir.name)
        return Path(temp_dir.name), temp_dir
    raise FileNotFoundError(f"Backup nao encontrado: {backup_path}")


def _load_metadata(backup_dir: Path) -> dict[str, Any]:
    metadata_path = backup_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.json nao encontrado em {backup_dir}")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _build_restore_entries(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    tables = metadata.get("tables", [])
    if not tables:
        return []
    dependencies = metadata.get("dependencies", [])
    by_name = {item["table_name"]: item for item in tables}
    ordered_names = _compute_restore_order(list(by_name.keys()), dependencies)
    ordered_names = _enforce_precedence(ordered_names, before="prestador_odonto", after="usuarios")
    metadata_restore_order = [name for name in metadata.get("restore_order", []) if name in by_name]
    if metadata_restore_order and metadata_restore_order != ordered_names:
        print("[WARN] restore_order do metadata difere da ordem recalculada por dependencies.")
    return [by_name[name] for name in ordered_names]


def _enforce_precedence(ordered_names: list[str], before: str, after: str) -> list[str]:
    if before not in ordered_names or after not in ordered_names:
        return ordered_names
    before_idx = ordered_names.index(before)
    after_idx = ordered_names.index(after)
    if before_idx < after_idx:
        return ordered_names
    reordered = [name for name in ordered_names if name != before]
    after_idx = reordered.index(after)
    reordered.insert(after_idx, before)
    print(f"[WARN] Ajustando ordem para garantir {before} antes de {after}.")
    return reordered


def _compute_restore_order(table_names: list[str], dependencies: list[dict[str, Any]]) -> list[str]:
    indegree = {name: 0 for name in table_names}
    graph: dict[str, set[str]] = {name: set() for name in table_names}

    for dep in dependencies:
        parent = dep.get("parent_table")
        child = dep.get("child_table")
        if parent not in indegree or child not in indegree:
            continue
        if child in graph[parent]:
            continue
        graph[parent].add(child)
        indegree[child] += 1

    queue = sorted([name for name, degree in indegree.items() if degree == 0])
    ordered: list[str] = []

    while queue:
        current = queue.pop(0)
        ordered.append(current)
        for neighbor in sorted(graph[current]):
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)
        queue.sort()

    if len(ordered) != len(table_names):
        remaining = sorted([name for name in table_names if name not in ordered])
        ordered.extend(remaining)

    return ordered


def _truncate_tables(cur, table_names: list[str]) -> None:
    quoted_tables = ", ".join(f'public."{name}"' for name in table_names)
    cur.execute(f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE")


def _copy_table(cur, table_name: str, columns: list[str], file_path: Path) -> None:
    if not file_path.exists():
        raise FileNotFoundError(f"CSV nao encontrado para a tabela {table_name}: {file_path}")
    quoted_cols = ", ".join(f'"{col}"' for col in columns)
    copy_query = f'COPY public."{table_name}" ({quoted_cols}) FROM STDIN WITH CSV HEADER'
    with file_path.open("r", encoding="utf-8", newline="") as handle:
        cur.copy_expert(copy_query, handle)


def _resolve_csv_file(backup_dir: Path, csv_path: str) -> Path:
    return backup_dir / Path(csv_path)


def _build_phase1_csv_if_needed(
    table_name: str,
    columns: list[str],
    source_csv: Path,
    temp_work_dir: Path,
) -> tuple[Path, str | None]:
    circular_column = None
    if table_name == "usuarios" and "prestador_id" in columns:
        circular_column = "prestador_id"
    elif table_name == "prestador_odonto" and "usuario_id" in columns:
        circular_column = "usuario_id"

    if circular_column is None:
        return source_csv, None

    phase1_path = temp_work_dir / f"{table_name}__phase1.csv"
    with source_csv.open("r", encoding="utf-8", newline="") as src, phase1_path.open(
        "w", encoding="utf-8", newline=""
    ) as dst:
        reader = csv.DictReader(src)
        if reader.fieldnames is None:
            raise RuntimeError(f"CSV sem cabecalho: {source_csv}")
        writer = csv.DictWriter(dst, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            row[circular_column] = ""
            writer.writerow(row)

    return phase1_path, circular_column


def _parse_optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return int(text)


def _collect_fk_updates_from_csv(csv_path: Path, key_col: str, fk_col: str) -> list[tuple[int, int]]:
    updates: list[tuple[int, int]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise RuntimeError(f"CSV sem cabecalho: {csv_path}")
        if key_col not in reader.fieldnames or fk_col not in reader.fieldnames:
            return updates
        for row in reader:
            key_value = _parse_optional_int(row.get(key_col))
            fk_value = _parse_optional_int(row.get(fk_col))
            if key_value is None or fk_value is None:
                continue
            updates.append((fk_value, key_value))
    return updates


def _apply_circular_fk_updates(
    cur,
    backup_dir: Path,
    by_table: dict[str, dict[str, Any]],
) -> None:
    print("[PHASE 2] Religando FKs circulares entre usuarios e prestador_odonto")

    usuarios_meta = by_table.get("usuarios")
    prestador_meta = by_table.get("prestador_odonto")

    if usuarios_meta is not None:
        usuarios_csv = _resolve_csv_file(backup_dir, usuarios_meta["csv_path"])
        usuarios_updates = _collect_fk_updates_from_csv(usuarios_csv, key_col="id", fk_col="prestador_id")
        print(f"[PHASE 2] usuarios.prestador_id updates: {len(usuarios_updates)}")
        if usuarios_updates:
            cur.executemany(
                'UPDATE public."usuarios" SET "prestador_id" = %s WHERE "id" = %s',
                usuarios_updates,
            )

    if prestador_meta is not None:
        prestador_csv = _resolve_csv_file(backup_dir, prestador_meta["csv_path"])
        prestador_updates = _collect_fk_updates_from_csv(prestador_csv, key_col="id", fk_col="usuario_id")
        print(f"[PHASE 2] prestador_odonto.usuario_id updates: {len(prestador_updates)}")
        if prestador_updates:
            cur.executemany(
                'UPDATE public."prestador_odonto" SET "usuario_id" = %s WHERE "id" = %s',
                prestador_updates,
            )


def _reset_sequences(cur, sequences: list[dict[str, str]]) -> None:
    for item in sequences:
        table_name = item["table_name"]
        column_name = item["column_name"]
        sequence_name = item["sequence_name"]
        cur.execute(
            f"""
            SELECT setval(
                %s,
                COALESCE((SELECT MAX("{column_name}") FROM public."{table_name}"), 1),
                EXISTS(SELECT 1 FROM public."{table_name}")
            )
            """,
            (sequence_name,),
        )


def _try_set_replication_role(cur, role: str) -> bool:
    sql_stmt = f"SET session_replication_role = {role}"
    try:
        cur.execute(sql_stmt)
        return True
    except psycopg2.Error as exc:
        if exc.pgcode == "42501":
            print(
                "[WARN] Sem permissao para alterar session_replication_role. "
                "Continuando sem alterar esse parametro."
            )
            cur.connection.rollback()
            print("[TX] rollback apos falha de permissao em session_replication_role")
            return False
        raise


def main() -> int:
    args = _parse_args()
    if not args.yes:
        raise RuntimeError(
            "Esta restauracao sobrescreve os dados atuais. Rode novamente com --yes quando estiver pronto."
        )

    env_path = Path(args.env_path).resolve()
    database_url = _load_database_url(env_path)
    print(f"[ENV] env_path={env_path}")
    print(f"[ENV] database_url={_redact_database_url(database_url)}")

    backup_source = Path(args.backup_path).resolve()
    backup_dir, temp_dir = _resolve_backup_path(backup_source)
    phase1_temp_dir = tempfile.TemporaryDirectory(prefix="saas_restore_phase1_")
    phase1_dir = Path(phase1_temp_dir.name)
    try:
        metadata = _load_metadata(backup_dir)
        restore_entries = _build_restore_entries(metadata)
        if not restore_entries:
            raise RuntimeError("Nenhuma tabela encontrada no metadata do backup.")
        by_table = {item["table_name"]: item for item in restore_entries}

        table_names = [item["table_name"] for item in restore_entries]
        connection = psycopg2.connect(database_url)
        connection.autocommit = False

        try:
            with connection.cursor() as cur:
                cur.execute("SELECT current_database(), current_user")
                db_name, db_user = cur.fetchone()
                print(f"[TARGET] database={db_name} user={db_user}")

                replication_role_set = _try_set_replication_role(cur, "replica")
                _truncate_tables(cur, table_names)
                for item in restore_entries:
                    source_csv = _resolve_csv_file(backup_dir, item["csv_path"])
                    phase1_csv, nulled_column = _build_phase1_csv_if_needed(
                        table_name=item["table_name"],
                        columns=item["columns"],
                        source_csv=source_csv,
                        temp_work_dir=phase1_dir,
                    )
                    if nulled_column:
                        print(
                            f"[PHASE 1] {item['table_name']}: usando CSV temporario com {nulled_column} vazio"
                        )
                    _copy_table(
                        cur,
                        item["table_name"],
                        item["columns"],
                        phase1_csv,
                    )
                _apply_circular_fk_updates(cur, backup_dir, by_table)
                _reset_sequences(cur, metadata.get("sequences", []))
                if replication_role_set:
                    _try_set_replication_role(cur, "origin")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    finally:
        phase1_temp_dir.cleanup()
        if temp_dir is not None:
            temp_dir.cleanup()

    print(f"Backup restaurado com sucesso a partir de: {backup_source}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise
