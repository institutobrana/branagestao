import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal
from models.clinica import Clinica
from models.material import Material  # noqa: F401
from models.procedimento import Procedimento, ProcedimentoMaterial
from models.procedimento_generico import ProcedimentoGenerico  # noqa: F401
from models.procedimento_tabela import ProcedimentoTabela
from models.tiss_tipo_tabela import TissTipoTabela  # noqa: F401
from models.usuario import Usuario
from services.procedimentos_legado_service import _mapear_forma_cobranca_easy
from services.simbolos_service import carregar_mapa_simbolos_por_legacy_id

TARGET_EMAIL_DEFAULT = "gleissontel@gmail.com"
SOURCE_SERVER = r"DELL_SERVIDOR\EDS70"
SOURCE_DATABASE = "eds70"
SOURCE_UID = "easy"
SOURCE_PWD = "ysae"
OSQL_PATH = Path(r"D:\UTIL\EasyDental_7.6_BR\EDS75_Server\x86\Binn\OSQL.EXE")
DELIM = "|~|"

DEFAULT_TABLES = [
    "EASY - Particular",
    "Caixa Econ. Federal",
    "UNIMED-ODONTO",
]

TARGET_TABLE_MAP = {
    "EASY - PARTICULAR": {"codigo": 10, "nome": "EASY - Particular", "fonte_pagadora": "particular"},
    "CAIXA ECON. FEDERAL": {"codigo": 5, "nome": "Caixa Econ. Federal", "fonte_pagadora": "convenio"},
    "UNIMED-ODONTO": {"codigo": 11, "nome": "UNIMED-ODONTO", "fonte_pagadora": "convenio"},
}


@dataclass
class SourceTable:
    source_code: int
    source_name: str
    nro_indice: int
    inativo: bool
    target_code: int
    target_name: str
    fonte_pagadora: str


def _normalizar_nome_tabela(nome: str) -> str:
    return str(nome or "").strip().upper()


def _to_bool(value: str | int | None) -> bool:
    return str(value or "0").strip() not in {"", "0", "False", "false", "f", "F"}


def _to_int(value: str | int | None, default: int = 0) -> int:
    base = str(value or "").strip()
    if not base:
        return default
    try:
        return int(float(base.replace(",", ".")))
    except (TypeError, ValueError):
        return default


def _to_float(value: str | int | float | None, default: float = 0.0) -> float:
    base = str(value or "").strip().replace(",", ".")
    if not base:
        return default
    try:
        return float(base)
    except (TypeError, ValueError):
        return default


def _normalizar_texto(value: str | None) -> str:
    return " ".join(str(value or "").replace("\ufeff", "").split()).strip()


def _normalizar_especialidade(value: str | int | None) -> str | None:
    numero = _to_int(value, 0)
    if numero <= 0:
        return None
    return f"{numero:02d}"


def _run_osql_query(query: str) -> list[str]:
    if not OSQL_PATH.exists():
        raise RuntimeError(f"OSQL.EXE nao encontrado em: {OSQL_PATH}")
    cmd = [
        str(OSQL_PATH),
        "-S",
        SOURCE_SERVER,
        "-d",
        SOURCE_DATABASE,
        "-U",
        SOURCE_UID,
        "-P",
        SOURCE_PWD,
        "-h-1",
        "-w",
        "999",
        "-Q",
        f"SET NOCOUNT ON {query}",
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, encoding="latin-1", errors="ignore", check=True)
    lines: list[str] = []
    for raw in completed.stdout.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if DELIM not in line:
            continue
        lines.append(line.strip())
    return lines


def _carregar_tabelas_origem(table_names: list[str]) -> list[SourceTable]:
    rows = _run_osql_query(
        "SELECT CAST(NROTAB AS VARCHAR(20)) + '{d}' + "
        "ISNULL(REPLACE(REPLACE(NOME, CHAR(13), ' '), CHAR(10), ' '), '') + '{d}' + "
        "CAST(NROIND AS VARCHAR(20)) + '{d}' + CAST(ISNULL(INATIVO,0) AS VARCHAR(10)) "
        "FROM TAB_PRC ORDER BY NOME".format(d=DELIM)
    )
    wanted = {_normalizar_nome_tabela(x) for x in table_names}
    found: list[SourceTable] = []
    for row in rows:
        parts = [p.strip() for p in row.split(DELIM)]
        if len(parts) != 4:
            continue
        source_name = _normalizar_texto(parts[1])
        normalized = _normalizar_nome_tabela(source_name)
        if normalized not in wanted:
            continue
        target = TARGET_TABLE_MAP.get(normalized)
        if not target:
            raise RuntimeError(f"Tabela sem mapeamento seguro configurado: {source_name}")
        found.append(
            SourceTable(
                source_code=_to_int(parts[0]),
                source_name=source_name,
                nro_indice=_to_int(parts[2], 255),
                inativo=_to_bool(parts[3]),
                target_code=int(target["codigo"]),
                target_name=str(target["nome"]),
                fonte_pagadora=str(target["fonte_pagadora"]),
            )
        )
    missing = [name for name in table_names if _normalizar_nome_tabela(name) not in {_normalizar_nome_tabela(x.source_name) for x in found}]
    if missing:
        raise RuntimeError(f"Tabelas nao encontradas na origem: {missing}")
    return found


def _carregar_itens_origem(source_table: SourceTable) -> list[dict]:
    rows = _run_osql_query(
        "SELECT "
        "CAST(NROPROCTAB AS VARCHAR(20)) + '{d}' + "
        "ISNULL(CODCONV,'') + '{d}' + "
        "ISNULL(REPLACE(REPLACE(DESCRICAO, CHAR(13), ' '), CHAR(10), ' '), '') + '{d}' + "
        "CAST(ISNULL(ESPECIAL,0) AS VARCHAR(20)) + '{d}' + "
        "CAST(CONVERT(DECIMAL(18,2), ISNULL(VALOR_PACIENTE,0)) AS VARCHAR(50)) + '{d}' + "
        "CAST(ISNULL(ID_PRC_GEN,0) AS VARCHAR(20)) + '{d}' + "
        "CAST(ISNULL(NROSIM,0) AS VARCHAR(20)) + '{d}' + "
        "CAST(ISNULL(TIPOCOBR,0) AS VARCHAR(20)) + '{d}' + "
        "CAST(CONVERT(DECIMAL(18,2), ISNULL(VALOR_REPASSE,0)) AS VARCHAR(50)) + '{d}' + "
        "CAST(ISNULL(INATIVO,0) AS VARCHAR(10)) + '{d}' + "
        "CAST(ISNULL(MOSTRAR_SIMBOLO,0) AS VARCHAR(10)) + '{d}' + "
        "CAST(ISNULL(GARANTIA,0) AS VARCHAR(10)) + '{d}' + "
        "CAST(ISNULL(PREFERIDO,0) AS VARCHAR(10)) + '{d}' + "
        "ISNULL(REPLACE(REPLACE(CAST(OBSERV AS VARCHAR(4000)), CHAR(13), ' '), CHAR(10), ' '), '') "
        "FROM TAB_PRC_ITEM WHERE NROTAB = {nrotab} ORDER BY NROPROCTAB".format(d=DELIM, nrotab=source_table.source_code)
    )
    items: list[dict] = []
    seen_codes: set[int] = set()
    for row in rows:
        parts = [p.strip() for p in row.split(DELIM)]
        if len(parts) != 14:
            continue
        codigo = _to_int(parts[0], 0)
        if codigo <= 0 or codigo in seen_codes:
            continue
        seen_codes.add(codigo)
        descricao = _normalizar_texto(parts[2]) or f"Procedimento {codigo}"
        items.append(
            {
                "codigo": codigo,
                "codconv": _normalizar_texto(parts[1]) or None,
                "descricao": descricao,
                "especialidade": _normalizar_especialidade(parts[3]),
                "preco": _to_float(parts[4], 0.0),
                "id_prc_gen": _to_int(parts[5], 0),
                "nrosim": _to_int(parts[6], 0),
                "tipocobr": _to_int(parts[7], 0),
                "valor_repasse": _to_float(parts[8], 0.0),
                "inativo": _to_bool(parts[9]),
                "mostrar_simbolo": _to_bool(parts[10]),
                "garantia": _to_int(parts[11], 0),
                "preferido": _to_bool(parts[12]),
                "observacoes": _normalizar_texto(parts[13]) or None,
            }
        )
    return items


def _garantir_tabela_destino(db, clinica_id: int, source_table: SourceTable) -> ProcedimentoTabela:
    tabela = (
        db.query(ProcedimentoTabela)
        .filter(
            ProcedimentoTabela.clinica_id == clinica_id,
            ProcedimentoTabela.codigo == source_table.target_code,
        )
        .first()
    )
    if not tabela:
        tabela = ProcedimentoTabela(
            clinica_id=clinica_id,
            codigo=source_table.target_code,
            nome=source_table.target_name,
            nro_indice=source_table.nro_indice or 255,
            fonte_pagadora=source_table.fonte_pagadora,
            inativo=source_table.inativo,
            tipo_tiss_id=1,
        )
        db.add(tabela)
        return tabela

    tabela.nome = source_table.target_name
    tabela.nro_indice = source_table.nro_indice or tabela.nro_indice or 255
    tabela.fonte_pagadora = source_table.fonte_pagadora
    tabela.inativo = source_table.inativo
    return tabela


def _mapa_genericos_clinica(db, clinica_id: int) -> dict[str, int]:
    out: dict[str, int] = {}
    rows = db.query(ProcedimentoGenerico.id, ProcedimentoGenerico.codigo).filter(ProcedimentoGenerico.clinica_id == clinica_id).all()
    for generico_id, codigo in rows:
        code = str(codigo or "").strip()
        if not code:
            continue
        out[code] = int(generico_id)
    return out


def _aplicar_tabela(db, clinica_id: int, source_table: SourceTable, items: list[dict], apply_changes: bool) -> dict:
    tabela_existente = (
        db.query(ProcedimentoTabela)
        .filter(
            ProcedimentoTabela.clinica_id == clinica_id,
            ProcedimentoTabela.codigo == source_table.target_code,
        )
        .first()
    )
    tabela_destino_id = int(tabela_existente.id) if tabela_existente else 0
    current_proc_ids = [
        int(row[0])
        for row in db.query(Procedimento.id)
        .filter(
            Procedimento.clinica_id == clinica_id,
            Procedimento.tabela_id == tabela_destino_id,
        )
        .all()
    ] if tabela_destino_id > 0 else []

    summary = {
        "source_name": source_table.source_name,
        "target_name": source_table.target_name,
        "target_code": source_table.target_code,
        "items": len(items),
        "existing_rows": len(current_proc_ids),
    }
    if not apply_changes:
        return summary

    tabela_destino = _garantir_tabela_destino(db, clinica_id, source_table)
    db.flush()
    tabela_destino_id = int(tabela_destino.id)
    genericos = _mapa_genericos_clinica(db, clinica_id)
    simbolos_por_legacy = carregar_mapa_simbolos_por_legacy_id()
    if current_proc_ids:
        (
            db.query(ProcedimentoMaterial)
            .filter(ProcedimentoMaterial.procedimento_id.in_(current_proc_ids))
            .delete(synchronize_session=False)
        )
        (
            db.query(Procedimento)
            .filter(
                Procedimento.clinica_id == clinica_id,
                Procedimento.tabela_id == tabela_destino_id,
            )
            .delete(synchronize_session=False)
        )

    for item in items:
        id_prc_gen = int(item["id_prc_gen"] or 0)
        codigo4 = f"{id_prc_gen:04d}" if id_prc_gen > 0 else ""
        codigo5 = f"{id_prc_gen:05d}" if id_prc_gen > 0 else ""
        generico_id = genericos.get(codigo5) or genericos.get(codigo4)
        legacy_id = int(item["nrosim"] or 0)
        simbolo_codigo = str(simbolos_por_legacy.get(legacy_id) or "").strip() or None
        db.add(
            Procedimento(
                clinica_id=clinica_id,
                tabela_id=tabela_destino_id,
                codigo=int(item["codigo"]),
                nome=str(item["descricao"]),
                tempo=0,
                preco=float(item["preco"] or 0.0),
                custo=0.0,
                custo_lab=0.0,
                lucro_hora=0.0,
                especialidade=item["especialidade"],
                procedimento_generico_id=int(generico_id) if generico_id else None,
                simbolo_grafico=simbolo_codigo,
                simbolo_grafico_legacy_id=legacy_id or None,
                mostrar_simbolo=bool(item["mostrar_simbolo"] or simbolo_codigo),
                garantia_meses=int(item["garantia"] or 0),
                forma_cobranca=_mapear_forma_cobranca_easy(int(item["tipocobr"] or 0)) or None,
                valor_repasse=float(item["valor_repasse"] or 0.0),
                preferido=bool(item["preferido"]),
                inativo=bool(item["inativo"]),
                observacoes=item["observacoes"],
            )
        )
    return summary


def migrar(target_email: str, table_names: list[str], apply_changes: bool) -> None:
    source_tables = _carregar_tabelas_origem(table_names)
    payload = [(source_table, _carregar_itens_origem(source_table)) for source_table in source_tables]

    db = SessionLocal()
    try:
        usuario = db.query(Usuario).filter(func.lower(Usuario.email) == target_email.lower()).first()
        if not usuario:
            raise RuntimeError(f"Usuario alvo nao encontrado: {target_email}")
        clinica = db.query(Clinica).filter(Clinica.id == usuario.clinica_id).first()
        if not clinica:
            raise RuntimeError("Clinica do usuario alvo nao encontrada.")

        print(f"Clinica alvo: id={clinica.id} usuario={target_email}")
        for source_table, items in payload:
            summary = _aplicar_tabela(db, clinica.id, source_table, items, apply_changes)
            print(
                f"- {summary['source_name']} -> codigo {summary['target_code']} / "
                f"{summary['target_name']} | itens={summary['items']} | existentes={summary['existing_rows']}"
            )

        if apply_changes:
            db.commit()
            print("Migracao aplicada com sucesso.")
        else:
            db.rollback()
            print("Dry-run concluido. Nenhuma alteracao foi gravada.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Migra tabelas de procedimentos do EasyDental para uma clinica do SaaS."
    )
    parser.add_argument("--email", default=TARGET_EMAIL_DEFAULT, help="Email do usuario alvo.")
    parser.add_argument(
        "--tables",
        nargs="+",
        default=DEFAULT_TABLES,
        help="Nomes das tabelas de origem a migrar.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica a migracao. Sem isso, executa apenas dry-run.",
    )
    args = parser.parse_args()
    migrar(args.email, list(args.tables), bool(args.apply))


if __name__ == "__main__":
    main()
