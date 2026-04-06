from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    import pyodbc  # type: ignore
except Exception:  # pragma: no cover
    pyodbc = None


PATTERNS = [
    "CONTATO",
    "AGENDA",
    "CID",
    "DOEN",
    "PROT",
    "LAB",
    "FORNEC",
    "TERCEIR",
]


def _matches(text: str) -> bool:
    upper = (text or "").upper()
    return any(pat in upper for pat in PATTERNS)


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
    parser = argparse.ArgumentParser(description="Mapeia tabelas/colunas do EasyDental para contatos/CID/protetico.")
    parser.add_argument("--server", default=r"DELL_SERVIDOR\EDS70")
    parser.add_argument("--database", default="eds70")
    parser.add_argument("--user", default="easy")
    parser.add_argument("--password", default="ysae")
    parser.add_argument("--trusted", action="store_true", help="Usa autenticacao integrada do Windows.")
    parser.add_argument("--out", default="output/eds70_modulos_map.json")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    conn = _connect(args.server, args.database, args.user, args.password, args.trusted)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT t.name AS table_name,
                   c.name AS column_name,
                   ty.name AS type_name,
                   c.max_length,
                   c.is_nullable
            FROM sys.tables t
            JOIN sys.columns c ON c.object_id = t.object_id
            JOIN sys.types ty ON c.user_type_id = ty.user_type_id
            WHERE t.is_ms_shipped = 0
            ORDER BY t.name, c.column_id
            """
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    tables: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        table = str(row.table_name)
        col = {
            "name": str(row.column_name),
            "type": str(row.type_name),
            "max_length": int(row.max_length),
            "nullable": bool(row.is_nullable),
        }
        tables.setdefault(table, []).append(col)

    candidatos: dict[str, list[dict[str, object]]] = {}
    for table, cols in tables.items():
        if _matches(table) or any(_matches(col["name"]) for col in cols):
            candidatos[table] = cols

    payload = {
        "server": args.server,
        "database": args.database,
        "patterns": PATTERNS,
        "tables_total": len(tables),
        "candidatos_total": len(candidatos),
        "candidatos": candidatos,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Mapa gerado: {out_path}")
    print(f"Total tabelas: {len(tables)} | Candidatas: {len(candidatos)}")


if __name__ == "__main__":
    main()
