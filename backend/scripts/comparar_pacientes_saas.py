from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pyodbc


SOURCE_SERVER = r"DELL_SERVIDOR\EDS70"
SOURCE_DATABASE = "eds70"
SOURCE_UID = "easy"
SOURCE_PWD = "ysae"

BACKEND_ENV = Path("saas/backend/.env")
OUT_DIR = Path("output")
OUT_FILE = OUT_DIR / "comparativo_pacientes_saas.txt"

TABLE_PRIORITY = [
    "pacientes",
    "paciente",
    "pessoal",
    "ficha_pessoal",
]
TABLE_KEYWORDS = ["pac", "pessoal", "ficha", "prontuario", "prontuario", "cliente"]
ID_CANDIDATES = [
    "nropac",
    "numero_cadastro",
    "codigo_cadastro",
    "codigo",
    "registro",
    "id_externo",
    "cod_prontuario",
    "prontuario",
]
NAME_CANDIDATES = [
    "nome",
    "prinome",
    "prinom",
]
LAST_NAME_CANDIDATES = [
    "sobrenome",
    "segnom",
    "segnom",
]


@dataclass
class SourcePatient:
    nropac: int
    nome: str
    sobrenome: str

    @property
    def nome_completo(self) -> str:
        return " ".join(x for x in [self.nome.strip(), self.sobrenome.strip()] if x).strip()


def _read_database_url() -> str:
    content = BACKEND_ENV.read_text(encoding="utf-8")
    for line in content.splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL não encontrado em saas/backend/.env")


def _connect_pg():
    url = _read_database_url()
    parsed = urlparse(url)
    return psycopg2.connect(
        dbname=parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
    )


def _connect_source():
    return pyodbc.connect(
        "DRIVER={SQL Server};"
        f"SERVER={SOURCE_SERVER};"
        f"DATABASE={SOURCE_DATABASE};"
        f"UID={SOURCE_UID};"
        f"PWD={SOURCE_PWD};"
        "Connection Timeout=15;"
    )


def _load_source_patients() -> list[SourcePatient]:
    cn = _connect_source()
    cur = cn.cursor()
    cur.execute(
        "SELECT NROPAC, LTRIM(RTRIM(PRINOM)), LTRIM(RTRIM(SEGNOM)) "
        "FROM PESSOAL "
        "WHERE NROPAC IS NOT NULL AND NROPAC > 0 "
        "ORDER BY NROPAC"
    )
    rows = cur.fetchall()
    cn.close()
    out: list[SourcePatient] = []
    for nropac, nome, sobrenome in rows:
        out.append(
            SourcePatient(
                nropac=int(nropac),
                nome=str(nome or "").strip(),
                sobrenome=str(sobrenome or "").strip(),
            )
        )
    return out


def _list_tables_and_columns(pg) -> dict[str, list[str]]:
    cur = pg.cursor()
    cur.execute(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
        """
    )
    data: dict[str, list[str]] = {}
    for table_name, column_name in cur.fetchall():
        data.setdefault(str(table_name), []).append(str(column_name))
    return data


def _pick_table(table_cols: dict[str, list[str]]) -> str | None:
    for t in TABLE_PRIORITY:
        if t in table_cols:
            return t
    for t, cols in table_cols.items():
        t_norm = t.lower()
        if not any(k in t_norm for k in TABLE_KEYWORDS):
            continue
        cols_set = {c.lower() for c in cols}
        has_name = any(c in cols_set for c in NAME_CANDIDATES)
        has_clinic = "clinica_id" in cols_set
        if has_name and has_clinic:
            return t
    return None


def _pick_col(cols: list[str], candidates: list[str]) -> str | None:
    by_lower = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand in by_lower:
            return by_lower[cand]
    return None


def _load_clinics_and_users(pg) -> tuple[list[tuple[int, str, str]], list[tuple[int, str, str, int]]]:
    cur = pg.cursor()
    cur.execute("SELECT id, COALESCE(nome,''), COALESCE(email,'') FROM clinicas ORDER BY id")
    clinics = [(int(r[0]), str(r[1]), str(r[2])) for r in cur.fetchall()]
    cur.execute("SELECT id, COALESCE(nome,''), COALESCE(email,''), clinica_id FROM usuarios ORDER BY id")
    users = [(int(r[0]), str(r[1]), str(r[2]), int(r[3])) for r in cur.fetchall()]
    return clinics, users


def _normalize(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _run_compare() -> str:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    source = _load_source_patients()
    source_ids = {p.nropac for p in source}
    source_names = {_normalize(p.nome_completo) for p in source if p.nome_completo}

    pg = _connect_pg()
    table_cols = _list_tables_and_columns(pg)
    clinics, users = _load_clinics_and_users(pg)

    lines: list[str] = []
    lines.append(f"Origem EasyDental: {SOURCE_SERVER}/{SOURCE_DATABASE}")
    lines.append(f"Total origem (PESSOAL): {len(source)}")
    lines.append(f"Faixa origem NROPAC: {min(source_ids) if source_ids else '-'} .. {max(source_ids) if source_ids else '-'}")
    lines.append("")
    lines.append("Clinicas SaaS:")
    for cid, nome, email in clinics:
        lines.append(f" - {cid}: {nome} <{email}>")
    lines.append("")
    lines.append("Usuarios SaaS:")
    for uid, nome, email, cid in users:
        lines.append(f" - id={uid} clinica={cid} nome={nome} email={email}")
    lines.append("")

    chosen_table = _pick_table(table_cols)
    if not chosen_table:
        lines.append("Nao encontrei tabela de pacientes no SaaS para comparar.")
        lines.append("Tabelas existentes no schema public:")
        for t in sorted(table_cols):
            lines.append(f" - {t}")
        pg.close()
        return "\n".join(lines)

    cols = table_cols[chosen_table]
    id_col = _pick_col(cols, ID_CANDIDATES)
    name_col = _pick_col(cols, NAME_CANDIDATES)
    last_name_col = _pick_col(cols, LAST_NAME_CANDIDATES)
    has_clinica = any(c.lower() == "clinica_id" for c in cols)

    lines.append(f"Tabela alvo escolhida: {chosen_table}")
    lines.append(f"Colunas: {', '.join(cols)}")
    lines.append(f"Mapeamento: id_col={id_col or '-'} name_col={name_col or '-'} last_name_col={last_name_col or '-'} clinica_id={'sim' if has_clinica else 'nao'}")
    lines.append("")

    cur = pg.cursor()
    if has_clinica:
        cur.execute(f"SELECT DISTINCT clinica_id FROM {chosen_table} ORDER BY clinica_id")
        clinic_ids_target = [int(r[0]) for r in cur.fetchall() if r[0] is not None]
    else:
        clinic_ids_target = []

    lines.append("Comparativo por clinica:")
    if has_clinica and clinic_ids_target:
        for cid in clinic_ids_target:
            cur.execute(f"SELECT COUNT(*) FROM {chosen_table} WHERE clinica_id = %s", (cid,))
            total_target = int(cur.fetchone()[0] or 0)

            ids_present: set[int] = set()
            names_present: set[str] = set()

            if id_col:
                cur.execute(
                    f"SELECT {id_col} FROM {chosen_table} WHERE clinica_id = %s AND {id_col} IS NOT NULL",
                    (cid,),
                )
                for (val,) in cur.fetchall():
                    try:
                        ids_present.add(int(val))
                    except Exception:
                        pass

            if name_col and last_name_col:
                cur.execute(
                    f"SELECT {name_col}, {last_name_col} FROM {chosen_table} WHERE clinica_id = %s",
                    (cid,),
                )
                for n, s in cur.fetchall():
                    full = f"{str(n or '').strip()} {str(s or '').strip()}".strip()
                    if full:
                        names_present.add(_normalize(full))
            elif name_col:
                cur.execute(f"SELECT {name_col} FROM {chosen_table} WHERE clinica_id = %s", (cid,))
                for (n,) in cur.fetchall():
                    if n:
                        names_present.add(_normalize(str(n)))

            if ids_present:
                missing_ids = sorted(source_ids - ids_present)
                present_ids = len(source_ids & ids_present)
                lines.append(
                    f" - clinica {cid}: total_tabela={total_target}, "
                    f"ids_em_comum={present_ids}, ids_faltando={len(missing_ids)}"
                )
                if missing_ids:
                    lines.append("   amostra_ids_faltando: " + ", ".join(str(x) for x in missing_ids[:30]))
            elif names_present:
                missing_names = sorted(x for x in source_names if x not in names_present)
                common_names = len(source_names & names_present)
                lines.append(
                    f" - clinica {cid}: total_tabela={total_target}, "
                    f"nomes_em_comum={common_names}, nomes_faltando={len(missing_names)}"
                )
                if missing_names:
                    lines.append("   amostra_nomes_faltando: " + ", ".join(missing_names[:15]))
            else:
                lines.append(f" - clinica {cid}: total_tabela={total_target}, sem colunas mapeaveis para comparar")
    else:
        cur.execute(f"SELECT COUNT(*) FROM {chosen_table}")
        total_target = int(cur.fetchone()[0] or 0)
        lines.append(f" - sem clinica_id (comparacao global), total_tabela={total_target}")

    pg.close()
    return "\n".join(lines)


def main() -> None:
    report = _run_compare()
    OUT_FILE.write_text(report, encoding="utf-8")
    print(f"Relatorio: {OUT_FILE}")
    print(report)


if __name__ == "__main__":
    main()
