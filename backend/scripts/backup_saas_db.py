import argparse
import csv
import json
import os
import shutil
import sys
import zipfile
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent.parent
DEFAULT_ENV_PATH = BACKEND_DIR / ".env"
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "backups"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera um backup completo do banco PostgreSQL usado pelo SaaS."
    )
    parser.add_argument(
        "--env-path",
        default=str(DEFAULT_ENV_PATH),
        help="Caminho para o .env do backend do SaaS.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Diretorio onde o pacote de backup sera criado.",
    )
    parser.add_argument(
        "--backup-name",
        default="",
        help="Nome base do backup. Se omitido, usa timestamp.",
    )
    parser.add_argument(
        "--include-desktop-db",
        action="store_true",
        help="Inclui o arquivo legado dados.db, se existir no projeto.",
    )
    return parser.parse_args()


def _load_database_url(env_path: Path) -> str:
    if not env_path.exists():
        raise FileNotFoundError(f".env nao encontrado: {env_path}")
    load_dotenv(env_path)
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(f"DATABASE_URL nao encontrado em {env_path}")
    return database_url


def _quote_copy_query(table_name: str, columns: list[str]) -> sql.SQL:
    return sql.SQL("COPY (SELECT {cols} FROM {table}) TO STDOUT WITH CSV HEADER").format(
        cols=sql.SQL(", ").join(sql.Identifier(col) for col in columns),
        table=sql.SQL(".").join([sql.Identifier("public"), sql.Identifier(table_name)]),
    )


def _quote_copy_from_query(table_name: str, columns: list[str]) -> str:
    quoted_cols = ", ".join(f'"{col}"' for col in columns)
    return f'COPY public."{table_name}" ({quoted_cols}) FROM STDIN WITH CSV HEADER'


def _list_tables(cur) -> list[str]:
    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    return [row[0] for row in cur.fetchall()]


def _list_columns(cur, table_name: str) -> list[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    return [row[0] for row in cur.fetchall()]


def _list_dependencies(cur) -> list[dict[str, str]]:
    cur.execute(
        """
        SELECT
            tc.table_name AS child_table,
            ccu.table_name AS parent_table,
            kcu.column_name AS child_column,
            ccu.column_name AS parent_column,
            tc.constraint_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
        ORDER BY child_table, parent_table, tc.constraint_name
        """
    )
    return [
        {
            "child_table": row[0],
            "parent_table": row[1],
            "child_column": row[2],
            "parent_column": row[3],
            "constraint_name": row[4],
        }
        for row in cur.fetchall()
    ]


def _topological_table_order(tables: list[str], dependencies: list[dict[str, str]]) -> list[str]:
    indegree = {table: 0 for table in tables}
    graph: dict[str, set[str]] = defaultdict(set)

    for dep in dependencies:
        parent = dep["parent_table"]
        child = dep["child_table"]
        if parent not in indegree or child not in indegree:
            continue
        if child in graph[parent]:
            continue
        graph[parent].add(child)
        indegree[child] += 1

    queue = deque(sorted(table for table, degree in indegree.items() if degree == 0))
    ordered: list[str] = []

    while queue:
        current = queue.popleft()
        ordered.append(current)
        for neighbor in sorted(graph[current]):
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    if len(ordered) != len(tables):
        remaining = [table for table in tables if table not in ordered]
        ordered.extend(sorted(remaining))

    return ordered


def _list_sequences(cur, tables: list[str]) -> list[dict[str, str]]:
    cur.execute(
        """
        SELECT
            t.relname AS table_name,
            a.attname AS column_name,
            pg_get_serial_sequence(format('%%I.%%I', n.nspname, t.relname), a.attname) AS sequence_name
        FROM pg_class t
        JOIN pg_namespace n ON n.oid = t.relnamespace
        JOIN pg_attribute a ON a.attrelid = t.oid
        WHERE n.nspname = 'public'
          AND t.relkind = 'r'
          AND a.attnum > 0
          AND NOT a.attisdropped
          AND t.relname = ANY(%s)
        ORDER BY t.relname, a.attnum
        """,
        (tables,),
    )
    results = []
    for table_name, column_name, sequence_name in cur.fetchall():
        if not sequence_name:
            continue
        results.append(
            {
                "table_name": table_name,
                "column_name": column_name,
                "sequence_name": sequence_name,
            }
        )
    return results


def _export_table(cur, table_name: str, columns: list[str], output_file: Path) -> int:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8", newline="") as handle:
        copy_query = _quote_copy_query(table_name, columns)
        cur.copy_expert(copy_query.as_string(cur.connection), handle)

    with output_file.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def _copy_extra_files(backup_dir: Path, include_desktop_db: bool) -> list[dict[str, Any]]:
    copied_files: list[dict[str, Any]] = []
    if not include_desktop_db:
        return copied_files

    desktop_db = PROJECT_ROOT / "dados.db"
    if desktop_db.exists():
        extra_dir = backup_dir / "extra_files"
        extra_dir.mkdir(parents=True, exist_ok=True)
        destination = extra_dir / desktop_db.name
        shutil.copy2(desktop_db, destination)
        copied_files.append(
            {
                "source": str(desktop_db),
                "destination": str(destination.relative_to(backup_dir)),
                "size_bytes": destination.stat().st_size,
            }
        )
    return copied_files


def _build_backup_name(database_url: str, provided_name: str) -> str:
    if provided_name.strip():
        return provided_name.strip()
    parsed = urlparse(database_url)
    db_name = (parsed.path or "/database").rsplit("/", 1)[-1] or "database"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{db_name}_full_{timestamp}"


def _write_metadata(
    backup_dir: Path,
    metadata: dict[str, Any],
) -> Path:
    metadata_path = backup_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata_path


def _zip_backup_dir(backup_dir: Path) -> Path:
    zip_path = backup_dir.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(backup_dir.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, arcname=file_path.relative_to(backup_dir))
    return zip_path


def main() -> int:
    args = _parse_args()
    env_path = Path(args.env_path).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    database_url = _load_database_url(env_path)
    backup_name = _build_backup_name(database_url, args.backup_name)
    backup_dir = output_dir / backup_name
    if backup_dir.exists():
        raise FileExistsError(f"O diretorio de backup ja existe: {backup_dir}")
    backup_dir.mkdir(parents=True, exist_ok=False)

    connection = psycopg2.connect(database_url)
    connection.autocommit = False
    table_summaries: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}

    try:
        with connection.cursor() as cur:
            cur.execute("SELECT current_database(), current_user, version()")
            current_database, current_user, server_version = cur.fetchone()

            tables = _list_tables(cur)
            dependencies = _list_dependencies(cur)
            restore_order = _topological_table_order(tables, dependencies)
            sequences = _list_sequences(cur, tables)

            data_dir = backup_dir / "data"
            for table_name in tables:
                columns = _list_columns(cur, table_name)
                row_count = _export_table(cur, table_name, columns, data_dir / f"{table_name}.csv")
                table_summaries.append(
                    {
                        "table_name": table_name,
                        "columns": columns,
                        "row_count": row_count,
                        "csv_path": str((Path("data") / f"{table_name}.csv").as_posix()),
                    }
                )

            extra_files = _copy_extra_files(backup_dir, args.include_desktop_db)

            metadata = {
                "backup_name": backup_name,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "source": {
                    "database_name": current_database,
                    "database_user": current_user,
                    "database_url_redacted": _redact_database_url(database_url),
                    "server_version": server_version,
                    "env_path": str(env_path),
                },
                "tables": table_summaries,
                "dependencies": dependencies,
                "restore_order": restore_order,
                "sequences": sequences,
                "extra_files": extra_files,
                "notes": [
                    "O backup contem um CSV por tabela do schema public.",
                    "Use o script restore_saas_db_backup.py para restaurar este pacote em um banco vazio ou ja inicializado pelo projeto.",
                ],
            }
            _write_metadata(backup_dir, metadata)
    finally:
        connection.close()

    zip_path = _zip_backup_dir(backup_dir)

    print(f"Backup criado em: {backup_dir}")
    print(f"Arquivo zip: {zip_path}")
    print(f"Tabelas exportadas: {len(table_summaries)}")
    for item in table_summaries:
        print(f"- {item['table_name']}: {item['row_count']} registros")
    if metadata.get("extra_files"):
        print("Arquivos extras incluidos:")
        for item in metadata["extra_files"]:
            print(f"- {item['destination']}")

    return 0


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


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise
