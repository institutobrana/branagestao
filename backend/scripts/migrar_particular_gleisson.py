import re
import sys
from collections import Counter
from pathlib import Path

import pyodbc
from sqlalchemy import func

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = Path(__file__).resolve().parents[3]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal
from models.clinica import Clinica
from models.material import Material  # noqa: F401
from models.procedimento import Procedimento, ProcedimentoMaterial
from models.procedimento_tabela import ProcedimentoTabela
from models.tiss_tipo_tabela import TissTipoTabela  # noqa: F401
from models.usuario import Usuario

TARGET_EMAIL = "gleissontel@gmail.com"
SOURCE_SERVER = "DELL_SERVIDOR\\EDS70"
SOURCE_DATABASE = "eds70"
SOURCE_UID = "easy"
SOURCE_PWD = "ysae"
SOURCE_TABELA_NOME = "PARTICULAR"


def _normalizar_codigo_especialidade(valor: int | str | None) -> str:
    base = str(valor or "").strip()
    if not base:
        return ""
    if base.isdigit():
        numero = int(base)
        if numero <= 0:
            return ""
        return f"{numero:02d}"
    return base[:20]


def _normalizar_descricao(texto: str) -> str:
    base = str(texto or "").replace("\ufeff", "").strip()
    base = re.sub(r"\s+", " ", base)
    return base.strip()


def _carregar_particular_origem_sql() -> list[dict]:
    cn = pyodbc.connect(
        "DRIVER={SQL Server};"
        f"SERVER={SOURCE_SERVER};"
        f"DATABASE={SOURCE_DATABASE};"
        f"UID={SOURCE_UID};"
        f"PWD={SOURCE_PWD};"
        "Connection Timeout=15;"
    )
    cur = cn.cursor()
    cur.execute(
        "SELECT TOP 1 NROTAB "
        "FROM TAB_PRC "
        "WHERE UPPER(LTRIM(RTRIM(NOME))) = ? "
        "ORDER BY NROTAB",
        (SOURCE_TABELA_NOME,),
    )
    row_tab = cur.fetchone()
    if not row_tab:
        cn.close()
        raise RuntimeError("Tabela PARTICULAR nao encontrada na origem SQL.")
    nrotab = int(row_tab[0])
    cur.execute(
        "SELECT NROPROCTAB, CODCONV, DESCRICAO, ESPECIAL "
        "FROM TAB_PRC_ITEM "
        "WHERE NROTAB = ? "
        "ORDER BY NROPROCTAB",
        (nrotab,),
    )
    rows = cur.fetchall()
    cn.close()

    vistos = set()
    final = []
    for row in rows:
        codigo = int(row[0] or 0)
        if codigo <= 0 or codigo in vistos:
            continue
        vistos.add(codigo)
        descricao = _normalizar_descricao(row[2] or "")
        if not descricao:
            descricao = f"Procedimento {codigo:03d}"
        especialidade = _normalizar_codigo_especialidade(row[3])
        final.append(
            {
                "codigo": codigo,
                "descricao": descricao,
                "especialidade": especialidade or None,
            }
        )
    return final


def _garantir_tabelas_clinica(db, clinica_id: int):
    tab1 = (
        db.query(ProcedimentoTabela)
        .filter(ProcedimentoTabela.clinica_id == clinica_id, ProcedimentoTabela.codigo == 1)
        .first()
    )
    if not tab1:
        db.add(ProcedimentoTabela(clinica_id=clinica_id, codigo=1, nome="Tabela Exemplo"))
    else:
        tab1.nome = "Tabela Exemplo"

    tab10 = (
        db.query(ProcedimentoTabela)
        .filter(ProcedimentoTabela.clinica_id == clinica_id, ProcedimentoTabela.codigo == 10)
        .first()
    )
    if not tab10:
        db.add(ProcedimentoTabela(clinica_id=clinica_id, codigo=10, nome="PARTICULAR"))
    else:
        tab10.nome = "PARTICULAR"


def migrar():
    procedimentos = _carregar_particular_origem_sql()
    if not procedimentos:
        raise RuntimeError("Nenhum procedimento da tabela PARTICULAR foi carregado.")

    db = SessionLocal()
    try:
        usuario = (
            db.query(Usuario)
            .filter(func.lower(Usuario.email) == TARGET_EMAIL.lower())
            .first()
        )
        if not usuario:
            raise RuntimeError(f"Usuario alvo nao encontrado: {TARGET_EMAIL}")

        clinica = db.query(Clinica).filter(Clinica.id == usuario.clinica_id).first()
        if not clinica:
            raise RuntimeError("Clinica do usuario alvo nao encontrada.")

        _garantir_tabelas_clinica(db, clinica.id)
        clinica.nome_tabela_procedimentos = "PARTICULAR"

        precos_existentes = {
            int(p.codigo): float(p.preco or 0)
            for p in db.query(Procedimento)
            .filter(
                Procedimento.clinica_id == clinica.id,
                Procedimento.tabela_id == 10,
            )
            .all()
        }

        proc_ids_tabela10 = [
            int(x[0])
            for x in db.query(Procedimento.id)
            .filter(
                Procedimento.clinica_id == clinica.id,
                Procedimento.tabela_id == 10,
            )
            .all()
        ]
        if proc_ids_tabela10:
            (
                db.query(ProcedimentoMaterial)
                .filter(ProcedimentoMaterial.procedimento_id.in_(proc_ids_tabela10))
                .delete(synchronize_session=False)
            )
            (
                db.query(Procedimento)
                .filter(
                    Procedimento.clinica_id == clinica.id,
                    Procedimento.tabela_id == 10,
                )
                .delete(synchronize_session=False)
            )

        for item in procedimentos:
            codigo = int(item["codigo"])
            db.add(
                Procedimento(
                    codigo=codigo,
                    nome=item["descricao"],
                    tempo=0,
                    preco=float(precos_existentes.get(codigo, 0.0)),
                    custo=0.0,
                    custo_lab=0.0,
                    lucro_hora=0.0,
                    tabela_id=10,
                    especialidade=_normalizar_codigo_especialidade(item["especialidade"]) or None,
                    clinica_id=clinica.id,
                )
            )

        db.commit()

        contagem_por_esp = Counter([str(x["especialidade"] or "").strip() for x in procedimentos if x["especialidade"]])
        print(
            "OK:",
            f"clinica_id={clinica.id}",
            f"usuario={TARGET_EMAIL}",
            f"procedimentos_inseridos={len(procedimentos)}",
            f"especialidades={dict(sorted(contagem_por_esp.items()))}",
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrar()
