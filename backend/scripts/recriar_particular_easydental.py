from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from database import SessionLocal
import models.tiss_tipo_tabela  # noqa: F401
from models.clinica import Clinica
from models.procedimento import Procedimento
from models.procedimento_generico import ProcedimentoGenerico
from models.procedimento_tabela import ProcedimentoTabela
from services.procedimentos_legado_service import (
    _mapear_forma_cobranca_easy,
    resolver_codigo_generico_particular_snapshot,
)
from services.simbolos_service import carregar_mapa_simbolos_por_legacy_id


PROJECT_DIR = Path(__file__).resolve().parents[3]
PARTICULAR_SQL_SNAPSHOT_PATH = PROJECT_DIR / "scripts" / "easy_particular_atual_snapshot.json"
PRIVATE_TABLE_CODE = 4
PRIVATE_TABLE_NAME = "PARTICULAR"


def _limpa_texto(txt: str | None) -> str:
    base = str(txt or "").replace("\ufeff", "").replace("\x00", "").strip()
    return " ".join(base.split())


def _to_int(valor, default=0) -> int:
    try:
        txt = str(valor or "").strip()
        if not txt:
            return default
        return int(float(txt))
    except Exception:
        return default


def _to_float(valor, default=0.0) -> float:
    try:
        txt = str(valor or "").strip()
        if not txt:
            return default
        return float(txt)
    except Exception:
        return default


def _carregar_snapshot() -> list[dict]:
    if not PARTICULAR_SQL_SNAPSHOT_PATH.exists():
        return []
    try:
        data = json.loads(PARTICULAR_SQL_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def main() -> None:
    snapshot = _carregar_snapshot()
    if not snapshot:
        print("Snapshot da PARTICULAR nao encontrado.")
        return

    simbolos_por_legacy = carregar_mapa_simbolos_por_legacy_id()

    db = SessionLocal()
    try:
        clinicas = db.query(Clinica).order_by(Clinica.id.asc()).all()
        for clinica in clinicas:
            tabela = (
                db.query(ProcedimentoTabela)
                .filter(
                    ProcedimentoTabela.clinica_id == int(clinica.id),
                    ProcedimentoTabela.codigo == PRIVATE_TABLE_CODE,
                )
                .first()
            )
            if tabela is None:
                nome = (clinica.nome_tabela_procedimentos or "").strip() or PRIVATE_TABLE_NAME
                tabela = ProcedimentoTabela(
                    clinica_id=int(clinica.id),
                    codigo=PRIVATE_TABLE_CODE,
                    nome=nome,
                    nro_indice=255,
                    fonte_pagadora="particular",
                    inativo=False,
                    tipo_tiss_id=1,
                )
                db.add(tabela)
                db.flush()

            tabela_id = int(tabela.id)
            db.execute(
                text("DELETE FROM procedimento WHERE clinica_id = :cid AND tabela_id = :tid"),
                {"cid": int(clinica.id), "tid": tabela_id},
            )

            genericos = {
                str(g.codigo or "").strip(): int(g.id)
                for g in db.query(ProcedimentoGenerico)
                .filter(ProcedimentoGenerico.clinica_id == int(clinica.id))
                .all()
                if str(g.codigo or "").strip()
            }

            payload = []
            missing_symbols = 0
            for row in snapshot:
                if not isinstance(row, dict):
                    continue
                codconv = _limpa_texto(row.get("codconv"))
                codigo = _to_int(codconv, 0) if codconv else 0
                if codigo <= 0:
                    codigo = _to_int(row.get("nroproctab"), 0)
                if codigo <= 0:
                    continue
                descricao = _limpa_texto(row.get("descricao")) or f"Procedimento {codigo:03d}"
                especial = _to_int(row.get("especial"), 0)
                especialidade = f"{especial:02d}" if especial > 0 else None
                nrosim = _to_int(row.get("nrosim"), 0)
                simbolo_grafico = simbolos_por_legacy.get(nrosim, "")
                simbolo_grafico_legacy_id = nrosim if simbolo_grafico and nrosim > 0 else None
                mostrar_simbolo = True if simbolo_grafico else bool(row.get("mostrar_simbolo"))
                if not simbolo_grafico:
                    missing_symbols += 1
                id_prc_gen = _to_int(row.get("id_prc_gen"), 0)
                generico_codigo = resolver_codigo_generico_particular_snapshot(id_prc_gen)
                generico_id = (
                    genericos.get(generico_codigo)
                    or genericos.get(generico_codigo.zfill(4))
                    or genericos.get(generico_codigo.zfill(5))
                )
                payload.append(
                    {
                        "codigo": codigo,
                        "nome": descricao,
                        "tempo": 0,
                        "preco": _to_float(row.get("valor_paciente"), 0.0),
                        "custo": 0.0,
                        "custo_lab": 0.0,
                        "lucro_hora": 0.0,
                        "tabela_id": tabela_id,
                        "especialidade": especialidade,
                        "procedimento_generico_id": int(generico_id) if generico_id else None,
                        "simbolo_grafico": simbolo_grafico or None,
                        "simbolo_grafico_legacy_id": simbolo_grafico_legacy_id,
                        "mostrar_simbolo": bool(mostrar_simbolo),
                        "garantia_meses": _to_int(row.get("garantia"), 0),
                        "forma_cobranca": _mapear_forma_cobranca_easy(_to_int(row.get("tipocobr"), 0)) or None,
                        "valor_repasse": _to_float(row.get("valor_repasse"), 0.0),
                        "preferido": bool(_to_int(row.get("preferido"), 0)),
                        "inativo": bool(row.get("inativo")),
                        "observacoes": None,
                        "data_inclusao": _limpa_texto(row.get("data_inclusao")) or None,
                        "data_alteracao": _limpa_texto(row.get("data_alteracao")) or None,
                        "clinica_id": int(clinica.id),
                    }
                )

            if payload:
                db.execute(
                    text(
                        """
                        INSERT INTO procedimento (
                            codigo, nome, tempo, preco, custo, custo_lab, lucro_hora,
                            tabela_id, especialidade, procedimento_generico_id, simbolo_grafico,
                            simbolo_grafico_legacy_id,
                            mostrar_simbolo, garantia_meses, forma_cobranca, valor_repasse,
                            preferido, inativo, observacoes, data_inclusao, data_alteracao,
                            clinica_id
                        ) VALUES (
                            :codigo, :nome, :tempo, :preco, :custo, :custo_lab, :lucro_hora,
                            :tabela_id, :especialidade, :procedimento_generico_id, :simbolo_grafico,
                            :simbolo_grafico_legacy_id,
                            :mostrar_simbolo, :garantia_meses, :forma_cobranca, :valor_repasse,
                            :preferido, :inativo, :observacoes, :data_inclusao, :data_alteracao,
                            :clinica_id
                        )
                        """
                    ),
                    payload,
                )

            print(
                f"Clinica {clinica.id}: {len(payload)} procedimentos da PARTICULAR recriados "
                f"(sem simbolo: {missing_symbols})."
            )

        # Remover tabela 4 quando vazia
        removidos = db.execute(
            text(
                """
                DELETE FROM procedimento_tabela t
                WHERE t.codigo = 4
                  AND NOT EXISTS (
                    SELECT 1 FROM procedimento p WHERE p.tabela_id = t.id
                  )
                """
            )
        ).rowcount
        if removidos:
            print(f"Tabelas codigo=4 removidas: {removidos}")

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
