from __future__ import annotations

from database import SessionLocal
import models.tiss_tipo_tabela  # noqa: F401
from models.clinica import Clinica
from models.procedimento import Procedimento
from models.procedimento_generico import ProcedimentoGenerico
from models.procedimento_tabela import ProcedimentoTabela
from services.procedimentos_legado_service import PARTICULAR_ID_PRC_GEN_CANONICO_SEGURO


PRIVATE_TABLE_CODE = 4

PARTICULAR_CODIGO_PARA_GENERICO_CANONICO = {
    9000: "00203",  # Micro agulhamento
    9010: "00205",  # Botox
    9020: "00204",  # Preenchimento
    9030: "00200",  # Lipo de papada
    9050: "00201",  # Bichectomia
}


def main() -> None:
    db = SessionLocal()
    try:
        clinicas = db.query(Clinica).order_by(Clinica.id.asc()).all()
        total_atualizados = 0
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
                continue

            genericos = {
                str(g.codigo or "").strip(): g
                for g in db.query(ProcedimentoGenerico)
                .filter(ProcedimentoGenerico.clinica_id == int(clinica.id))
                .all()
                if str(g.codigo or "").strip()
            }

            atualizados_clinica = 0
            procedimentos = (
                db.query(Procedimento)
                .filter(
                    Procedimento.clinica_id == int(clinica.id),
                    Procedimento.tabela_id == int(tabela.id),
                    Procedimento.codigo.in_(tuple(PARTICULAR_CODIGO_PARA_GENERICO_CANONICO.keys())),
                )
                .order_by(Procedimento.codigo.asc())
                .all()
            )
            for proc in procedimentos:
                codigo_generico = PARTICULAR_CODIGO_PARA_GENERICO_CANONICO.get(int(proc.codigo or 0), "")
                generico = genericos.get(codigo_generico)
                if generico is None:
                    continue
                mudou = False
                if int(proc.procedimento_generico_id or 0) != int(generico.id):
                    proc.procedimento_generico_id = int(generico.id)
                    mudou = True
                if int(proc.tempo or 0) <= 0 and int(generico.tempo or 0) > 0:
                    proc.tempo = int(generico.tempo or 0)
                    mudou = True
                if float(proc.custo_lab or 0) <= 0 and float(getattr(generico, "custo_lab", 0) or 0) > 0:
                    proc.custo_lab = float(getattr(generico, "custo_lab", 0) or 0)
                    mudou = True
                if not str(proc.especialidade or "").strip() and str(generico.especialidade or "").strip():
                    proc.especialidade = str(generico.especialidade or "").strip()
                    mudou = True
                if not str(proc.simbolo_grafico or "").strip() and str(generico.simbolo_grafico or "").strip():
                    proc.simbolo_grafico = str(generico.simbolo_grafico or "").strip()
                    mudou = True
                if bool(getattr(generico, "mostrar_simbolo", False)) and not bool(proc.mostrar_simbolo):
                    proc.mostrar_simbolo = True
                    mudou = True
                if mudou:
                    atualizados_clinica += 1

            total_atualizados += atualizados_clinica
            print(f"Clinica {clinica.id}: {atualizados_clinica} procedimentos seguros atualizados.")

        db.commit()
        print(f"Total atualizado: {total_atualizados}")
        print(f"Mapa seguro aplicado: {PARTICULAR_ID_PRC_GEN_CANONICO_SEGURO}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
