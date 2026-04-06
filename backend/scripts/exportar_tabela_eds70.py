from __future__ import annotations

import argparse
import csv
from pathlib import Path

try:
    import pyodbc  # type: ignore
except Exception:  # pragma: no cover
    pyodbc = None


def _connect(server: str, database: str, user: str, password: str, trusted: bool):
    if pyodbc is None:
        raise RuntimeError("pyodbc nao instalado. Instale pyodbc para conectar ao EasyDental.")
    if trusted:
        conn_str = (
            "DRIVER=SQL Server;"
            f"SERVER={server};"
            f"DATABASE={database};"
            "Trusted_Connection=yes"
        )
    else:
        conn_str = (
            "DRIVER=SQL Server;"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={user};"
            f"PWD={password};"
            "Trusted_Connection=no"
        )
    return pyodbc.connect(conn_str, timeout=10)


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta uma tabela do EasyDental (SQL Server) para CSV.")
    parser.add_argument("--server", default=r"DELL_SERVIDOR\EDS70")
    parser.add_argument("--database", default="eds70")
    parser.add_argument("--user", default="easy")
    parser.add_argument("--password", default="ysae")
    parser.add_argument("--trusted", action="store_true", help="Usa autenticacao integrada do Windows.")
    parser.add_argument("--table", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--where", default="")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    conn = _connect(args.server, args.database, args.user, args.password, args.trusted)
    try:
        cur = conn.cursor()
        top_clause = f"TOP {int(args.limit)} " if args.limit and args.limit > 0 else ""
        where_clause = f" WHERE {args.where}" if args.where else ""
        cur.execute(f"SELECT {top_clause}* FROM {args.table}{where_clause}")
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    finally:
        conn.close()

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(cols)
        for row in rows:
            writer.writerow([str(val) if val is not None else "" for val in row])

    print(f"Exportado: {out_path} ({len(rows)} linhas)")


if __name__ == "__main__":
    main()
