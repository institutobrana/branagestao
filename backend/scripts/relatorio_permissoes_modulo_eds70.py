from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[3]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _user_label(user_id: int, apelido: str | None, nome: str | None) -> str:
    base = (apelido or "").strip() or (nome or "").strip() or "Usuario"
    return f"{base} ({user_id})"


def _format_list(items: list[str], max_items: int, fallback: str) -> str:
    if not items:
        return "nenhum"
    if len(items) <= max_items:
        return ", ".join(items)
    return f"{len(items)} ({fallback})"


def main() -> None:
    today = datetime.now().strftime("%Y%m%d")
    today_human = datetime.now().strftime("%Y-%m-%d")

    parser = argparse.ArgumentParser(description="Gera relatorio de permissoes por modulo (EDS70).")
    parser.add_argument("--csv-dir", type=Path, default=PROJECT_DIR)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_DIR / "docs" / f"permissoes_por_modulo_eds70_{today}.md",
    )
    parser.add_argument(
        "--module-csv",
        type=Path,
        default=PROJECT_DIR / "output" / f"permissoes_modulos_resumo_{today}.csv",
    )
    parser.add_argument(
        "--function-csv",
        type=Path,
        default=PROJECT_DIR / "output" / f"permissoes_funcoes_por_modulo_{today}.csv",
    )
    parser.add_argument("--max-list", type=int, default=20)
    args = parser.parse_args()

    csv_dir: Path = args.csv_dir
    max_list = args.max_list

    modules_csv = csv_dir / "sis_modulo_sql.csv"
    funcoes_csv = csv_dir / "sis_funcao_sql.csv"
    users_csv = csv_dir / "usuarios_sql.csv"
    usuario_modulo_csv = csv_dir / "usuario_modulo_map.csv"
    usuario_funcao_csv = csv_dir / "usuario_funcao_map.csv"

    missing = [p for p in [modules_csv, funcoes_csv, users_csv, usuario_modulo_csv, usuario_funcao_csv] if not p.exists()]
    if missing:
        missing_fmt = ", ".join(str(p) for p in missing)
        raise SystemExit(f"Arquivos CSV necessarios nao encontrados: {missing_fmt}")

    modules_rows = _read_csv(modules_csv)
    funcoes_rows = _read_csv(funcoes_csv)
    users_rows = _read_csv(users_csv)
    usuario_modulo_rows = _read_csv(usuario_modulo_csv)
    usuario_funcao_rows = _read_csv(usuario_funcao_csv)

    modules = {int(row["ID_MODULO"]): row["NOME_MODULO"] for row in modules_rows}
    module_ids = sorted(modules.keys())

    functions = {}
    functions_by_module: dict[int, list[int]] = defaultdict(list)
    for row in funcoes_rows:
        func_id = int(row["ID_FUNCAO"])
        mod_id = int(row["ID_MODULO"])
        functions[func_id] = {
            "id": func_id,
            "module_id": mod_id,
            "name": row["NOME_FUNCAO"],
        }
        functions_by_module[mod_id].append(func_id)

    users = {}
    user_ids: list[int] = []
    for row in users_rows:
        user_id = int(row["NROUSR"])
        users[user_id] = {
            "apelido": row.get("APELIDO") or None,
            "nome": row.get("NOME") or None,
        }
        user_ids.append(user_id)
    user_ids.sort()

    modulo_perm: dict[tuple[int, int], str] = {}
    for row in usuario_modulo_rows:
        user_id = int(row["ID_USUARIO"])
        mod_id = int(row["ID_MODULO"])
        label = (row.get("NIVEL_LABEL") or "").strip().lower() or "desabilitado"
        modulo_perm[(user_id, mod_id)] = label

    funcao_perm: dict[tuple[int, int], str] = {}
    for row in usuario_funcao_rows:
        user_id = int(row["ID_USUARIO"])
        func_id = int(row["ID_FUNCAO"])
        label = (row.get("NIVEL_LABEL") or "").strip().lower() or "desabilitado"
        funcao_perm[(user_id, func_id)] = label

    module_summary = []
    for mod_id in module_ids:
        counts = {"habilitado": 0, "protegido": 0, "desabilitado": 0}
        users_by_level: dict[str, list[str]] = {"habilitado": [], "protegido": [], "desabilitado": []}
        for user_id in user_ids:
            label = modulo_perm.get((user_id, mod_id), "desabilitado")
            counts[label] += 1
            user_label = _user_label(user_id, users[user_id]["apelido"], users[user_id]["nome"])
            users_by_level[label].append(user_label)
        module_summary.append(
            {
                "ID_MODULO": mod_id,
                "MODULO": modules[mod_id],
                "TOTAL_USUARIOS": len(user_ids),
                "HABILITADO": counts["habilitado"],
                "PROTEGIDO": counts["protegido"],
                "DESABILITADO": counts["desabilitado"],
                "USERS_BY_LEVEL": users_by_level,
            }
        )

    function_summary = []
    for func_id, meta in functions.items():
        counts = {"habilitado": 0, "protegido": 0, "desabilitado": 0}
        for user_id in user_ids:
            label = funcao_perm.get((user_id, func_id), "desabilitado")
            counts[label] += 1
        function_summary.append(
            {
                "ID_FUNCAO": func_id,
                "FUNCAO": meta["name"],
                "ID_MODULO": meta["module_id"],
                "MODULO": modules.get(meta["module_id"], f"Modulo {meta['module_id']}"),
                "TOTAL_USUARIOS": len(user_ids),
                "HABILITADO": counts["habilitado"],
                "PROTEGIDO": counts["protegido"],
                "DESABILITADO": counts["desabilitado"],
            }
        )

    function_summary_by_id = {row["ID_FUNCAO"]: row for row in function_summary}
    usuario_modulo_fallback = usuario_modulo_csv.name
    funcao_fallback = args.function_csv.name

    args.module_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.module_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["ID_MODULO", "MODULO", "TOTAL_USUARIOS", "HABILITADO", "PROTEGIDO", "DESABILITADO"],
        )
        writer.writeheader()
        for row in module_summary:
            writer.writerow(
                {
                    "ID_MODULO": row["ID_MODULO"],
                    "MODULO": row["MODULO"],
                    "TOTAL_USUARIOS": row["TOTAL_USUARIOS"],
                    "HABILITADO": row["HABILITADO"],
                    "PROTEGIDO": row["PROTEGIDO"],
                    "DESABILITADO": row["DESABILITADO"],
                }
            )

    with args.function_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "ID_FUNCAO",
                "FUNCAO",
                "ID_MODULO",
                "MODULO",
                "TOTAL_USUARIOS",
                "HABILITADO",
                "PROTEGIDO",
                "DESABILITADO",
            ],
        )
        writer.writeheader()
        for row in function_summary:
            writer.writerow(row)

    report_lines: list[str] = []
    report_lines.append(f"# Permissoes por modulo (SQL) - {today_human}\n")
    report_lines.append("Fonte: SQL Server DELL_SERVIDOR\\\\EDS70 / DB eds70\n")
    report_lines.append(
        "Arquivos base: sis_modulo_sql.csv, sis_funcao_sql.csv, usuario_modulo_map.csv, "
        "usuario_funcao_map.csv, usuarios_sql.csv\n"
    )
    report_lines.append(f"Total de usuarios considerados: {len(user_ids)}\n")

    report_lines.append("## Resumo por modulo\n")
    report_lines.append("| Modulo | Habilitado | Protegido | Desabilitado | Total usuarios |\n")
    report_lines.append("| --- | --- | --- | --- | --- |\n")
    for row in module_summary:
        report_lines.append(
            f"| {row['MODULO']} | {row['HABILITADO']} | {row['PROTEGIDO']} | "
            f"{row['DESABILITADO']} | {row['TOTAL_USUARIOS']} |\n"
        )

    for row in module_summary:
        mod_id = row["ID_MODULO"]
        module_name = row["MODULO"]
        report_lines.append(f"\n## Modulo {mod_id} - {module_name}\n")
        report_lines.append(
            f"- Usuarios: total {row['TOTAL_USUARIOS']} | habilitado {row['HABILITADO']} | "
            f"protegido {row['PROTEGIDO']} | desabilitado {row['DESABILITADO']}\n"
        )
        report_lines.append(
            f"- Protegidos: {_format_list(row['USERS_BY_LEVEL']['protegido'], max_list, f'ver {usuario_modulo_fallback}')}\n"
        )
        report_lines.append(
            f"- Desabilitados: {_format_list(row['USERS_BY_LEVEL']['desabilitado'], max_list, f'ver {usuario_modulo_fallback}')}\n"
        )

        module_functions = functions_by_module.get(mod_id, [])
        total_funcoes = len(module_functions)
        funcoes_com_protegido = []
        funcoes_com_desabilitado = []
        funcoes_total_habilitado = 0
        for func_id in module_functions:
            func_row = function_summary_by_id.get(func_id)
            if not func_row:
                continue
            if func_row["DESABILITADO"] > 0:
                funcoes_com_desabilitado.append(func_row["FUNCAO"])
            if func_row["PROTEGIDO"] > 0:
                funcoes_com_protegido.append(func_row["FUNCAO"])
            if func_row["DESABILITADO"] == 0 and func_row["PROTEGIDO"] == 0:
                funcoes_total_habilitado += 1

        report_lines.append(
            f"- Funcoes: total {total_funcoes} | todas habilitadas {funcoes_total_habilitado} | "
            f"com protegidos {len(funcoes_com_protegido)} | com desabilitados {len(funcoes_com_desabilitado)}\n"
        )
        report_lines.append(
            f"- Funcoes protegidas: {_format_list(funcoes_com_protegido, max_list, f'ver {funcao_fallback}')}\n"
        )
        report_lines.append(
            f"- Funcoes desabilitadas: {_format_list(funcoes_com_desabilitado, max_list, f'ver {funcao_fallback}')}\n"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(report_lines), encoding="utf-8")


if __name__ == "__main__":
    main()
