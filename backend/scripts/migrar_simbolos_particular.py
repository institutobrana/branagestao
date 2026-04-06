from __future__ import annotations

from typing import Any

from sqlalchemy import text

from database import SessionLocal
import models.tiss_tipo_tabela  # noqa: F401
from models.procedimento import Procedimento
from models.procedimento_tabela import ProcedimentoTabela
from services.procedimentos_legado_service import _carregar_particular_sql_snapshot, _norm
from services.simbolos_service import carregar_mapa_simbolos_por_legacy_id

PRIVATE_TABLE_CODE = 4


def _resolver_simbolo_snapshot(
    proc: Procedimento,
    snapshot: dict[str, dict[str, Any]],
    simbolos_por_legacy: dict[int, str],
) -> str:
    por_codconv = snapshot.get("por_codconv", {})
    por_desc = snapshot.get("por_desc", {})
    codigo_txt = str(getattr(proc, "codigo", "") or "").strip()
    meta = None
    if codigo_txt:
        meta = por_codconv.get(codigo_txt)
        if meta is None:
            meta = por_codconv.get(codigo_txt.zfill(4))
        if meta is None:
            meta = por_codconv.get(codigo_txt.zfill(5))
    if meta is None:
        meta = por_desc.get(_norm(getattr(proc, "nome", "") or ""))
    if not meta:
        return ""
    try:
        nrosim = int(meta.get("nrosim") or 0)
    except Exception:
        nrosim = 0
    if nrosim <= 0:
        return ""
    return simbolos_por_legacy.get(nrosim, "")


def main() -> None:
    db = SessionLocal()
    try:
        snapshot = _carregar_particular_sql_snapshot()
        simbolos_por_legacy = carregar_mapa_simbolos_por_legacy_id()
        tabelas = (
            db.query(ProcedimentoTabela.id, ProcedimentoTabela.clinica_id)
            .filter(ProcedimentoTabela.codigo == PRIVATE_TABLE_CODE)
            .all()
        )
        tabela_ids = [int(t.id) for t in tabelas if int(t.id or 0) > 0]
        if not tabela_ids:
            print("Nenhuma tabela PARTICULAR encontrada.")
            return

        db.execute(text("SET LOCAL lock_timeout = '5s'"))
        procedimentos = (
            db.query(Procedimento)
            .filter(Procedimento.tabela_id.in_(tabela_ids))
            .order_by(Procedimento.clinica_id.asc(), Procedimento.codigo.asc(), Procedimento.id.asc())
            .all()
        )

        alterados = 0
        for proc in procedimentos:
            if str(getattr(proc, "simbolo_grafico", "") or "").strip():
                continue
            simbolo = _resolver_simbolo_snapshot(proc, snapshot, simbolos_por_legacy)
            if not simbolo:
                continue
            proc.simbolo_grafico = simbolo
            if not bool(getattr(proc, "mostrar_simbolo", False)):
                proc.mostrar_simbolo = True
            alterados += 1

        if alterados:
            db.flush()
        db.commit()
        print(f"Atualizados {alterados} procedimentos da PARTICULAR.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
