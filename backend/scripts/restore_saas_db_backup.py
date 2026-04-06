import argparse
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

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
    load_dotenv(env_path)
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(f"DATABASE_URL nao encontrado em {env_path}")
    return database_url


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


def _truncate_tables(cur, table_names: list[str]) -> None:
    quoted_tables = ", ".join(f'public."{name}"' for name in table_names)
    cur.execute(f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE")


def _copy_table(cur, backup_dir: Path, table_name: str, columns: list[str], csv_path: str) -> None:
    file_path = backup_dir / Path(csv_path)
    if not file_path.exists():
        raise FileNotFoundError(f"CSV nao encontrado para a tabela {table_name}: {file_path}")
    quoted_cols = ", ".join(f'"{col}"' for col in columns)
    copy_query = f'COPY public."{table_name}" ({quoted_cols}) FROM STDIN WITH CSV HEADER'
    with file_path.open("r", encoding="utf-8", newline="") as handle:
        cur.copy_expert(copy_query, handle)


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


def main() -> int:
    args = _parse_args()
    if not args.yes:
        raise RuntimeError(
            "Esta restauracao sobrescreve os dados atuais. Rode novamente com --yes quando estiver pronto."
        )

    env_path = Path(args.env_path).resolve()
    database_url = _load_database_url(env_path)

    backup_source = Path(args.backup_path).resolve()
    backup_dir, temp_dir = _resolve_backup_path(backup_source)
    try:
        metadata = _load_metadata(backup_dir)
        tables = metadata.get("tables", [])
        if not tables:
            raise RuntimeError("Nenhuma tabela encontrada no metadata do backup.")

        table_names = [item["table_name"] for item in tables]
        connection = psycopg2.connect(database_url)
        connection.autocommit = False

        try:
            with connection.cursor() as cur:
                cur.execute("SET session_replication_role = replica")
                _truncate_tables(cur, table_names)
                for item in tables:
                    _copy_table(
                        cur,
                        backup_dir,
                        item["table_name"],
                        item["columns"],
                        item["csv_path"],
                    )
                _reset_sequences(cur, metadata.get("sequences", []))
                cur.execute("SET session_replication_role = origin")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    finally:
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
