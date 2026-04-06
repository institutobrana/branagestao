from __future__ import annotations

import csv
from pathlib import Path

import pyodbc


SERVER = r"DELL_SERVIDOR\EDS70"
DATABASE = "eds70"
UID = "easy"
PWD = "ysae"
OUT_DIR = Path("output")
OUT_CSV = OUT_DIR / "eds70_pacientes.csv"
OUT_SAMPLE = OUT_DIR / "eds70_pacientes_amostra.txt"
OUT_FIELDS = OUT_DIR / "eds70_pacientes_campos.txt"


def connect() -> pyodbc.Connection:
    return pyodbc.connect(
        "DRIVER={SQL Server};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        f"UID={UID};"
        f"PWD={PWD};"
        "Connection Timeout=15;"
    )


def safe_name(col: str) -> str:
    return (col or "").strip().upper()


def pick_first_column(columns: list[str], candidates: list[str]) -> str | None:
    colset = {safe_name(c): c for c in columns}
    for cand in candidates:
        if cand in colset:
            return colset[cand]
    return None


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cn = connect()
    cur = cn.cursor()

    cur.execute("SELECT TOP 1 * FROM PESSOAL")
    cols = [d[0] for d in cur.description]
    id_col = pick_first_column(cols, ["NROPAC", "NRODENT", "NROPESS", "REGISTRO", "CODIGO", "ID"])
    nome_col = pick_first_column(cols, ["PRINOM", "NOME", "NOMEPAC", "RAZAO"])
    sobrenome_col = pick_first_column(cols, ["SEGNOM", "SOBRENOME", "COMPLEMENTO_NOME"])

    if not id_col or not nome_col:
        raise RuntimeError(
            f"Nao foi possivel identificar colunas obrigatorias em PESSOAL. Colunas: {', '.join(cols)}"
        )

    order_cols = [id_col, nome_col]
    if sobrenome_col:
        order_cols.append(sobrenome_col)
    order_sql = ", ".join(f"[{c}]" for c in order_cols)

    cur.execute(f"SELECT COUNT(*) FROM PESSOAL")
    total = int(cur.fetchone()[0] or 0)

    cur.execute(
        f"SELECT MIN([{id_col}]), MAX([{id_col}]) FROM PESSOAL "
        f"WHERE [{id_col}] IS NOT NULL AND [{id_col}] > 0"
    )
    min_id, max_id = cur.fetchone()

    if sobrenome_col:
        adib_filter = f"(LTRIM(RTRIM([{nome_col}])) + ' ' + LTRIM(RTRIM([{sobrenome_col}]))) LIKE ?"
    else:
        adib_filter = f"[{nome_col}] LIKE ?"
    cur.execute(
        f"SELECT TOP 20 {order_sql} "
        f"FROM PESSOAL "
        f"WHERE {adib_filter} "
        f"ORDER BY [{id_col}]",
        ("%ADIB MIGUEL FILHO%",),
    )
    adib_rows = cur.fetchall()

    cur.execute(f"SELECT * FROM PESSOAL ORDER BY [{id_col}]")
    data_rows = cur.fetchall()
    all_cols = [d[0] for d in cur.description]

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(all_cols)
        for row in data_rows:
            w.writerow([str(x) if x is not None else "" for x in row])

    with OUT_SAMPLE.open("w", encoding="utf-8") as f:
        f.write(f"Servidor: {SERVER}\n")
        f.write(f"Banco: {DATABASE}\n")
        f.write(f"Tabela: PESSOAL\n")
        f.write(f"Total registros: {total}\n")
        f.write(f"ID coluna: {id_col}\n")
        f.write(f"Faixa IDs: {min_id} .. {max_id}\n")
        f.write("\n")
        f.write("Amostra nome 'Adib Miguel Filho':\n")
        if not adib_rows:
            f.write("- Nenhum registro encontrado com esse nome exato/contendo.\n")
        else:
            for row in adib_rows:
                f.write(" - " + " | ".join(str(x) for x in row) + "\n")
        f.write("\n")
        f.write("Primeiros 15 cadastros:\n")
        cur.execute(f"SELECT TOP 15 {order_sql} FROM PESSOAL ORDER BY [{id_col}]")
        for row in cur.fetchall():
            f.write(" - " + " | ".join(str(x) for x in row) + "\n")

    non_empty: list[tuple[str, int]] = []
    total_rows = len(data_rows)
    for idx, col in enumerate(all_cols):
        filled = 0
        for row in data_rows:
            val = row[idx]
            if val is None:
                continue
            if isinstance(val, str):
                if not val.strip():
                    continue
            filled += 1
        non_empty.append((col, filled))

    non_empty.sort(key=lambda x: (-x[1], x[0]))
    with OUT_FIELDS.open("w", encoding="utf-8") as f:
        f.write(f"Total pacientes: {total_rows}\n")
        f.write("Campos por preenchimento (nao vazio):\n")
        for col, filled in non_empty:
            f.write(f" - {col}: {filled}/{total_rows}\n")

    cn.close()
    print(f"OK total={total} faixa={min_id}..{max_id}")
    print(f"CSV: {OUT_CSV}")
    print(f"Amostra: {OUT_SAMPLE}")
    print(f"Campos: {OUT_FIELDS}")


if __name__ == "__main__":
    main()
