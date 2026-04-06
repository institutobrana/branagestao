from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pyodbc


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BACKEND_DIR / ".env"

SOURCE_SERVER = r"DELL_SERVIDOR\EDS70"
SOURCE_DATABASE = "eds70"
SOURCE_UID = "easy"
SOURCE_PWD = "ysae"

LIST_PATTERNS = [
    "%INSTITUTO%BRANA%",
    "%INSTITUO%BRANA%",
]

SQLITE_CANDIDATES = [
    PROJECT_ROOT / "dados.db",
    PROJECT_ROOT / "dist" / "dados.db",
    PROJECT_ROOT / "dist" / "Brana" / "dados.db",
    PROJECT_ROOT / "BACKUP_2" / "dados.db",
    PROJECT_ROOT / "BACKUP_2" / "dadoss.db",
    PROJECT_ROOT / "BACKUP_2" / "dadossss.db",
    PROJECT_ROOT / "Dados" / "dados_alisson.db",
    PROJECT_ROOT / "instalador" / "app" / "dados.db",
    PROJECT_ROOT / "daados.db",
]

TEXT_TYPES = {"varchar", "nvarchar", "char", "nchar", "text", "ntext"}
TABLE_NAME_HINTS = ("MAT", "MATERIAL", "ESTOQ", "LIST", "TAB")
COLUMN_NAME_HINTS = ("NOME", "DESCR", "LIST", "TAB", "MAT", "ITEM")
TARGET_PRIMARY_NAME = "Tabela Brana"
TARGET_LIST_NAMES = (TARGET_PRIMARY_NAME, "LISTA PADRÃO", "LISTA PADRAO")


def _read_database_url() -> str:
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"DATABASE_URL nao encontrado em {ENV_PATH}")


def _connect_pg():
    parsed = urlparse(_read_database_url())
    return psycopg2.connect(
        dbname=parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
    )


def _connect_source_sql():
    return pyodbc.connect(
        "DRIVER={SQL Server};"
        f"SERVER={SOURCE_SERVER};"
        f"DATABASE={SOURCE_DATABASE};"
        f"UID={SOURCE_UID};"
        f"PWD={SOURCE_PWD};"
        "Connection Timeout=15;"
    )


def _print_header(title: str) -> None:
    print()
    print("=" * len(title))
    print(title)
    print("=" * len(title))


def inspect_sqlite_lists() -> None:
    _print_header("SQLite candidates")
    for path in SQLITE_CANDIDATES:
        if not path.exists():
            continue
        try:
            cn = sqlite3.connect(str(path))
            cur = cn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lista_material'")
            if not cur.fetchone():
                print(f"{path}: sem tabela lista_material")
                cn.close()
                continue
            cur.execute(
                """
                SELECT l.id, l.nome, COUNT(m.id) AS qtd
                FROM lista_material l
                LEFT JOIN material m ON m.lista_id = l.id
                GROUP BY l.id, l.nome
                ORDER BY l.id
                """
            )
            rows = cur.fetchall()
            print(path)
            for row in rows:
                print(f"  lista_id={row[0]} nome={row[1]!r} qtd={row[2]}")
            cn.close()
        except Exception as exc:
            print(f"{path}: erro {exc}")


def inspect_target_lists() -> None:
    _print_header("SaaS target lists")
    cn = _connect_pg()
    cur = cn.cursor()
    cur.execute(
        """
        SELECT c.id, COALESCE(c.nome, ''), l.id, COALESCE(l.nome, ''), COUNT(m.id) AS qtd
        FROM clinicas c
        LEFT JOIN lista_material l ON l.clinica_id = c.id
        LEFT JOIN material m ON m.lista_id = l.id
        GROUP BY c.id, c.nome, l.id, l.nome
        ORDER BY c.id, l.id
        """
    )
    for clinica_id, clinica_nome, lista_id, lista_nome, qtd in cur.fetchall():
        print(
            f"clinica_id={clinica_id} clinica={clinica_nome!r} "
            f"lista_id={lista_id} lista={lista_nome!r} qtd={qtd}"
        )
    cn.close()


def _source_tables_and_columns(cn) -> dict[tuple[str, str], list[tuple[str, str]]]:
    cur = cn.cursor()
    cur.execute(
        """
        SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo'
        ORDER BY TABLE_NAME, ORDINAL_POSITION
        """
    )
    grouped: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for schema, table, column, data_type in cur.fetchall():
        grouped[(str(schema), str(table))].append((str(column), str(data_type).lower()))
    return grouped


def _candidate_source_tables(table_filters: list[str] | None = None):
    cn = _connect_source_sql()
    grouped = _source_tables_and_columns(cn)
    candidate_tables = []
    for (schema, table), cols in grouped.items():
        table_upper = table.upper()
        col_names = [name.upper() for name, _dtype in cols]
        if table_filters and not any(f in table_upper for f in table_filters):
            continue
        if any(h in table_upper for h in TABLE_NAME_HINTS) or any(
            any(h in col for h in COLUMN_NAME_HINTS) for col in col_names
        ):
            candidate_tables.append((schema, table, cols))
    return cn, candidate_tables


def list_source_candidates(table_filters: list[str] | None = None) -> None:
    _print_header("EasyDental source candidate tables")
    cn, candidate_tables = _candidate_source_tables(table_filters)
    print(f"candidate_tables={len(candidate_tables)}")
    for schema, table, cols in candidate_tables:
        print(f"{schema}.{table}: cols={', '.join(name for name, _dtype in cols)}")
    cn.close()


def inspect_source_sql(table_filters: list[str] | None = None) -> None:
    _print_header("EasyDental source inspection")
    cn, candidate_tables = _candidate_source_tables(table_filters)
    print(f"candidate_tables={len(candidate_tables)}")
    for schema, table, cols in candidate_tables[:80]:
        text_cols = [name for name, dtype in cols if dtype in TEXT_TYPES]
        print(f"{schema}.{table}: cols={', '.join(name for name, _dtype in cols)}")
        if not text_cols:
            continue
        cur = cn.cursor()
        for col in text_cols:
            sql = (
                f"SELECT COUNT(*) FROM [{schema}].[{table}] "
                f"WHERE UPPER(LTRIM(RTRIM(CAST([{col}] AS NVARCHAR(4000))))) LIKE ?"
            )
            total = 0
            for pattern in LIST_PATTERNS:
                cur.execute(sql, pattern)
                total += int(cur.fetchone()[0] or 0)
            if total <= 0:
                continue
            print(f"  MATCH column={col} count={total}")
            sample_sql = (
                f"SELECT TOP 3 * FROM [{schema}].[{table}] "
                f"WHERE UPPER(LTRIM(RTRIM(CAST([{col}] AS NVARCHAR(4000))))) LIKE ?"
            )
            cur.execute(sample_sql, LIST_PATTERNS[0])
            rows = cur.fetchall()
            if not rows:
                cur.execute(sample_sql, LIST_PATTERNS[1])
                rows = cur.fetchall()
            columns = [d[0] for d in cur.description]
            for row in rows:
                data = {columns[idx]: row[idx] for idx in range(len(columns))}
                print(f"    sample={data}")
    cn.close()


def inspect_source_list() -> None:
    _print_header("EasyDental Instituto Brana")
    cn = _connect_source_sql()
    cur = cn.cursor()
    cur.execute(
        """
        SELECT ID_TAB_MAT, NOME
        FROM TAB_MAT
        WHERE UPPER(LTRIM(RTRIM(NOME))) LIKE ? OR UPPER(LTRIM(RTRIM(NOME))) LIKE ?
        ORDER BY ID_TAB_MAT
        """,
        LIST_PATTERNS[0],
        LIST_PATTERNS[1],
    )
    listas = cur.fetchall()
    if not listas:
        print("Lista Instituto Brana nao encontrada em TAB_MAT.")
        cn.close()
        return
    for list_id, nome in listas:
        print(f"id_tab_mat={list_id} nome={nome!r}")
        cur.execute(
            """
            SELECT COUNT(*)
            FROM TAB_MAT_ITEM
            WHERE ID_TAB_MAT = ?
            """,
            int(list_id),
        )
        total = int(cur.fetchone()[0] or 0)
        print(f"  total_itens={total}")
        cur.execute(
            """
            SELECT TOP 8
                   tmi.ID_MATERIAL,
                   tmi.CODIGO,
                   tmi.NOME,
                   tmi.TIPO,
                   tm.NOME AS TIPO_NOME,
                   tmi.VALOR_CUSTO,
                   tmi.UNID_CONSUMO,
                   uc.NOME AS UNID_CONSUMO_NOME,
                   tmi.UNID_COMPRA,
                   up.NOME AS UNID_COMPRA_NOME,
                   tmi.QTD_COMPRA,
                   tmi.VALIDADE,
                   tmi.PREFERIDO,
                   tmi.NROFAB,
                   fab.NOME AS FABRICANTE_NOME,
                   tmi.APRESENT,
                   tmi.CUSTO_INICIAL
            FROM TAB_MAT_ITEM tmi
            LEFT JOIN _TIPO_MAT tm ON tm.REGISTRO = tmi.TIPO
            LEFT JOIN _UNID_MEDIDA uc ON uc.REGISTRO = tmi.UNID_CONSUMO
            LEFT JOIN _UNID_MEDIDA up ON up.REGISTRO = tmi.UNID_COMPRA
            LEFT JOIN _FABRICANTE fab ON fab.REGISTRO = tmi.NROFAB
            WHERE tmi.ID_TAB_MAT = ?
            ORDER BY tmi.CODIGO, tmi.ID_MATERIAL
            """,
            int(list_id),
        )
        cols = [d[0] for d in cur.description]
        for row in cur.fetchall():
            data = {cols[idx]: row[idx] for idx in range(len(cols))}
            print(f"  sample={data}")
    cn.close()


def _load_source_materials() -> list[dict]:
    cn = _connect_source_sql()
    cur = cn.cursor()
    cur.execute(
        """
        SELECT TOP 1 ID_TAB_MAT
        FROM TAB_MAT
        WHERE UPPER(LTRIM(RTRIM(NOME))) LIKE ? OR UPPER(LTRIM(RTRIM(NOME))) LIKE ?
        ORDER BY ID_TAB_MAT
        """,
        LIST_PATTERNS[0],
        LIST_PATTERNS[1],
    )
    row = cur.fetchone()
    if not row:
        cn.close()
        raise RuntimeError("Lista Instituto Brana nao encontrada em TAB_MAT.")
    id_tab_mat = int(row[0])
    cur.execute(
        """
        SELECT
            LTRIM(RTRIM(tmi.CODIGO)) AS codigo,
            LTRIM(RTRIM(tmi.NOME)) AS nome,
            COALESCE(CONVERT(FLOAT, tmi.VALOR_CUSTO), 0) AS custo,
            COALESCE(CONVERT(FLOAT, tmi.QTD_COMPRA), 0) AS relacao,
            COALESCE(CONVERT(INT, tmi.VALIDADE), 0) AS validade_dias,
            CASE WHEN COALESCE(tmi.PREFERIDO, 0) <> 0 THEN 1 ELSE 0 END AS preferido,
            LTRIM(RTRIM(COALESCE(tm.NOME, ''))) AS classificacao,
            LTRIM(RTRIM(COALESCE(uc.NOME, ''))) AS unidade_consumo,
            LTRIM(RTRIM(COALESCE(up.NOME, ''))) AS unidade_compra
        FROM TAB_MAT_ITEM tmi
        LEFT JOIN _TIPO_MAT tm ON tm.REGISTRO = tmi.TIPO
        LEFT JOIN _UNID_MEDIDA uc ON uc.REGISTRO = tmi.UNID_CONSUMO
        LEFT JOIN _UNID_MEDIDA up ON up.REGISTRO = tmi.UNID_COMPRA
        WHERE tmi.ID_TAB_MAT = ?
        ORDER BY tmi.CODIGO, tmi.ID_MATERIAL
        """,
        id_tab_mat,
    )
    seen = set()
    out = []
    for codigo, nome, custo, relacao, validade_dias, preferido, classificacao, unidade_consumo, unidade_compra in cur.fetchall():
        codigo = str(codigo or "").strip()
        nome = str(nome or "").strip()
        if not codigo or not nome or codigo in seen:
            continue
        seen.add(codigo)
        out.append(
            {
                "codigo": codigo,
                "nome": nome,
                "custo": float(custo or 0),
                "relacao": float(relacao or 0),
                "validade_dias": int(validade_dias or 0),
                "preferido": bool(preferido),
                "classificacao": str(classificacao or "").strip(),
                "unidade_consumo": str(unidade_consumo or "").strip(),
                "unidade_compra": str(unidade_compra or "").strip(),
            }
        )
    cn.close()
    return out


def compare_target_with_source() -> None:
    _print_header("Compare source vs SaaS")
    source = _load_source_materials()
    source_codes = {x["codigo"] for x in source}
    print(f"source_total={len(source_codes)}")

    cn = _connect_pg()
    cur = cn.cursor()
    cur.execute(
        """
        SELECT c.id, COALESCE(c.nome, ''), l.id, COALESCE(l.nome, '')
        FROM lista_material l
        JOIN clinicas c ON c.id = l.clinica_id
        WHERE l.nome = ANY(%s)
        ORDER BY c.id, l.id
        """,
        (list(TARGET_LIST_NAMES),),
    )
    listas = cur.fetchall()
    for clinica_id, clinica_nome, lista_id, lista_nome in listas:
        cur.execute(
            """
            SELECT codigo, COALESCE(preco, 0), COALESCE(classificacao, ''), COALESCE(unidade_compra, ''), COALESCE(unidade_consumo, ''), COALESCE(preferido, FALSE)
            FROM material
            WHERE lista_id = %s
            ORDER BY codigo, id
            """,
            (lista_id,),
        )
        rows = cur.fetchall()
        target_codes = {str(r[0]).strip() for r in rows if str(r[0] or "").strip()}
        missing = sorted(source_codes - target_codes)
        extra = sorted(target_codes - source_codes)
        filled_cls = sum(1 for r in rows if str(r[2] or "").strip())
        filled_uc = sum(1 for r in rows if str(r[3] or "").strip())
        filled_uu = sum(1 for r in rows if str(r[4] or "").strip())
        filled_pref = sum(1 for r in rows if bool(r[5]))
        extra_links = []
        if extra:
            cur.execute(
                """
                SELECT m.codigo, COUNT(pm.id) AS links
                FROM material m
                LEFT JOIN procedimento_material pm ON pm.material_id = m.id
                WHERE m.lista_id = %s AND m.codigo = ANY(%s)
                GROUP BY m.codigo
                ORDER BY m.codigo
                """,
                (lista_id, extra),
            )
            extra_links = [(str(codigo), int(links or 0)) for codigo, links in cur.fetchall()]
        print(
            f"clinica_id={clinica_id} clinica={clinica_nome!r} lista_id={lista_id} lista={lista_nome!r} "
            f"target_total={len(target_codes)} missing={len(missing)} extra={len(extra)} "
            f"classificacao_preenchida={filled_cls} un_compra_preenchida={filled_uc} "
            f"un_consumo_preenchida={filled_uu} preferidos={filled_pref}"
        )
        if missing:
            print("  missing_sample=" + ", ".join(missing[:15]))
        if extra:
            print("  extra_sample=" + ", ".join(extra[:15]))
        if extra_links:
            print("  extra_links=" + ", ".join(f"{codigo}:{links}" for codigo, links in extra_links))
    cn.close()


def _upsert_auxiliares(cur, clinica_id: int, tipo: str, descricoes: set[str]) -> tuple[int, int]:
    cur.execute(
        """
        SELECT id, COALESCE(codigo, ''), COALESCE(descricao, '')
        FROM item_auxiliar
        WHERE clinica_id = %s AND tipo = %s
        ORDER BY id
        """,
        (clinica_id, tipo),
    )
    existentes = cur.fetchall()
    por_desc = {str(desc or "").strip().casefold(): (item_id, str(codigo or "").strip(), str(desc or "").strip()) for item_id, codigo, desc in existentes}
    max_codigo = 0
    for _item_id, codigo, _desc in existentes:
        codigo_limpo = str(codigo or "").strip()
        if codigo_limpo.isdigit():
            max_codigo = max(max_codigo, int(codigo_limpo))
    inseridos = 0
    atualizados = 0
    for descricao in sorted(x.strip() for x in descricoes if str(x or "").strip()):
        chave = descricao.casefold()
        if chave in por_desc:
            continue
        max_codigo += 1
        cur.execute(
            """
            INSERT INTO item_auxiliar (clinica_id, tipo, codigo, descricao)
            VALUES (%s, %s, %s, %s)
            """,
            (clinica_id, tipo, f"{max_codigo:04d}", descricao),
        )
        inseridos += 1
    return inseridos, atualizados


def migrate_target_lists() -> None:
    _print_header("Migrating Instituto Brana to SaaS")
    source = _load_source_materials()
    source_by_code = {item["codigo"]: item for item in source}
    source_codes = set(source_by_code)
    classificacoes = {item["classificacao"] for item in source if item["classificacao"]}
    unidades = {
        item["unidade_compra"]
        for item in source
        if item["unidade_compra"]
    } | {
        item["unidade_consumo"]
        for item in source
        if item["unidade_consumo"]
    }

    cn = _connect_pg()
    cur = cn.cursor()
    cur.execute(
        """
        SELECT c.id, COALESCE(c.nome, ''), l.id, COALESCE(l.nome, '')
        FROM lista_material l
        JOIN clinicas c ON c.id = l.clinica_id
        WHERE l.nome = ANY(%s)
        ORDER BY c.id, l.id
        """,
        (list(TARGET_LIST_NAMES),),
    )
    listas = cur.fetchall()
    if not listas:
        cn.close()
        raise RuntimeError("Nenhuma lista alvo encontrada no SaaS.")

    for clinica_id, clinica_nome, lista_id, lista_nome in listas:
        aux_tipo_ins, _ = _upsert_auxiliares(cur, int(clinica_id), "Tipos de material", classificacoes)
        aux_und_ins, _ = _upsert_auxiliares(cur, int(clinica_id), "Unidades de medida", unidades)

        cur.execute(
            """
            SELECT id, codigo, COALESCE(preco, 0)
            FROM material
            WHERE lista_id = %s
            ORDER BY id
            """,
            (lista_id,),
        )
        existentes = {
            str(codigo or "").strip(): {"id": int(material_id), "preco": float(preco or 0)}
            for material_id, codigo, preco in cur.fetchall()
            if str(codigo or "").strip()
        }

        inserted = 0
        updated = 0
        deleted = 0

        extras = sorted(set(existentes) - source_codes)
        if extras:
            cur.execute(
                """
                DELETE FROM material
                WHERE lista_id = %s AND codigo = ANY(%s)
                """,
                (lista_id, extras),
            )
            deleted = cur.rowcount or 0

        for codigo, item in source_by_code.items():
            if codigo in existentes:
                cur.execute(
                    """
                    UPDATE material
                    SET nome = %s,
                        relacao = %s,
                        custo = %s,
                        validade_dias = %s,
                        preferido = %s,
                        classificacao = %s,
                        unidade_compra = %s,
                        unidade_consumo = %s
                    WHERE id = %s
                    """,
                    (
                        item["nome"],
                        item["relacao"],
                        item["custo"],
                        item["validade_dias"],
                        item["preferido"],
                        item["classificacao"],
                        item["unidade_compra"],
                        item["unidade_consumo"],
                        existentes[codigo]["id"],
                    ),
                )
                updated += cur.rowcount or 0
            else:
                cur.execute(
                    """
                    INSERT INTO material (
                        codigo, nome, relacao, custo, preco,
                        unidade_compra, unidade_consumo, validade_dias,
                        preferido, classificacao, lista_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        item["codigo"],
                        item["nome"],
                        item["relacao"],
                        item["custo"],
                        0,
                        item["unidade_compra"],
                        item["unidade_consumo"],
                        item["validade_dias"],
                        item["preferido"],
                        item["classificacao"],
                        lista_id,
                    ),
                )
                inserted += cur.rowcount or 0

        cur.execute("SELECT COUNT(*) FROM material WHERE lista_id = %s", (lista_id,))
        total_final = int(cur.fetchone()[0] or 0)
        print(
            f"clinica_id={clinica_id} clinica={clinica_nome!r} lista_id={lista_id} lista={lista_nome!r} "
            f"aux_tipos_inseridos={aux_tipo_ins} aux_unidades_inseridas={aux_und_ins} "
            f"updated={updated} inserted={inserted} deleted={deleted} total_final={total_final}"
        )

    cn.commit()
    cn.close()


def rename_target_lists() -> None:
    _print_header("Renaming target lists")
    cn = _connect_pg()
    cur = cn.cursor()
    cur.execute(
        """
        UPDATE lista_material
        SET nome = %s
        WHERE nome = ANY(%s)
          AND nome <> %s
        """,
        (TARGET_PRIMARY_NAME, list(TARGET_LIST_NAMES), TARGET_PRIMARY_NAME),
    )
    print(f"listas_renomeadas={cur.rowcount or 0}")
    cn.commit()
    cn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspeciona origem/destino da migracao da lista Instituto Brana.")
    parser.add_argument("--inspect-sqlite", action="store_true")
    parser.add_argument("--inspect-source-sql", action="store_true")
    parser.add_argument("--list-source-candidates", action="store_true")
    parser.add_argument("--inspect-source-list", action="store_true")
    parser.add_argument("--inspect-target", action="store_true")
    parser.add_argument("--compare-target", action="store_true")
    parser.add_argument("--migrate", action="store_true")
    parser.add_argument("--rename-target-lists", action="store_true")
    parser.add_argument("--source-filter", action="append", default=[])
    args = parser.parse_args()

    source_filters = [x.strip().upper() for x in args.source_filter if x.strip()]

    if args.inspect_sqlite:
        inspect_sqlite_lists()
    if args.inspect_source_sql:
        inspect_source_sql(source_filters or None)
    if args.list_source_candidates:
        list_source_candidates(source_filters or None)
    if args.inspect_source_list:
        inspect_source_list()
    if args.inspect_target:
        inspect_target_lists()
    if args.compare_target:
        compare_target_with_source()
    if args.migrate:
        migrate_target_lists()
    if args.rename_target_lists:
        rename_target_lists()
    if not any(
        [
            args.inspect_sqlite,
            args.inspect_source_sql,
            args.list_source_candidates,
            args.inspect_source_list,
            args.inspect_target,
            args.compare_target,
            args.migrate,
            args.rename_target_lists,
        ]
    ):
        parser.error("informe ao menos uma opcao de inspecao")


if __name__ == "__main__":
    main()
