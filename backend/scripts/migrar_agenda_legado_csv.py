from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path

from database import SessionLocal
import models.clinica  # noqa: F401
import models.usuario  # noqa: F401
from models.agenda_legado import AgendaLegadoBloqueio, AgendaLegadoEvento


def _clean_text(value: str | None) -> str:
    text = (value or "").replace("\x00", "").strip()
    while text and ord(text[0]) < 32:
        text = text[1:]
    return " ".join(text.split())


def _to_int(value: str | None) -> int | None:
    base = _clean_text(value or "")
    if not base:
        return None
    try:
        return int(float(base))
    except Exception:
        return None


def _to_datetime(value: str | None) -> datetime | None:
    base = _clean_text(value or "")
    if not base:
        return None
    try:
        return datetime.fromisoformat(base)
    except Exception:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(base, fmt)
            except Exception:
                continue
    return None


def _read_rows(path: Path, delimiter: str) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa agenda (legado) do EasyDental a partir de CSV.")
    parser.add_argument("--agenda-csv", required=True)
    parser.add_argument("--bloqueio-csv", required=True)
    parser.add_argument("--clinica-id", type=int, required=True)
    parser.add_argument("--delimiter", default=";")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    agenda_path = Path(args.agenda_csv)
    bloqueio_path = Path(args.bloqueio_csv)
    if not agenda_path.exists():
        raise FileNotFoundError(agenda_path)
    if not bloqueio_path.exists():
        raise FileNotFoundError(bloqueio_path)

    agenda_rows = _read_rows(agenda_path, args.delimiter)
    bloqueio_rows = _read_rows(bloqueio_path, args.delimiter)

    db = SessionLocal()
    try:
        if args.replace:
            db.query(AgendaLegadoBloqueio).filter(
                AgendaLegadoBloqueio.clinica_id == args.clinica_id
            ).delete()
            db.query(AgendaLegadoEvento).filter(
                AgendaLegadoEvento.clinica_id == args.clinica_id
            ).delete()

        eventos = []
        for row in agenda_rows:
            data = _to_datetime(row.get("DATA"))
            hora_inicio = _to_int(row.get("HORAINICIO"))
            if data is None or hora_inicio is None:
                continue
            eventos.append(
                AgendaLegadoEvento(
                    clinica_id=args.clinica_id,
                    id_prestador=_to_int(row.get("ID_PRESTADOR")) or 0,
                    id_unidade=_to_int(row.get("ID_UNIDADE")) or 0,
                    data=data,
                    hora_inicio=hora_inicio,
                    hora_fim=_to_int(row.get("HORAFIM")),
                    sala=_to_int(row.get("SALA")),
                    tipo=_to_int(row.get("TIPO")),
                    nro_pac=_to_int(row.get("NROPAC")),
                    nome=_clean_text(row.get("NOME")),
                    motivo=_clean_text(row.get("MOTIVO")),
                    status=_to_int(row.get("STATUS")),
                    observ=_clean_text(row.get("OBSERV")),
                    tip_fone1=_to_int(row.get("TIPFONE1")),
                    fone1=_clean_text(row.get("FONE1")),
                    tip_fone2=_to_int(row.get("TIPFONE2")),
                    fone2=_clean_text(row.get("FONE2")),
                    tip_fone3=_to_int(row.get("TIPFONE3")),
                    fone3=_clean_text(row.get("FONE3")),
                    palm_id=_to_int(row.get("PALM_ID")),
                    palm_upd=_to_int(row.get("PALM_UPD")),
                    myeasy_id=_to_int(row.get("MYEASY_ID")),
                    myeasy_upd=_to_int(row.get("MYEASY_UPD")),
                    user_stamp_ins=_to_int(row.get("USER_STAMP_INS")),
                    time_stamp_ins=_to_datetime(row.get("TIME_STAMP_INS")),
                    user_stamp_upd=_to_int(row.get("USER_STAMP_UPD")),
                    time_stamp_upd=_to_datetime(row.get("TIME_STAMP_UPD")),
                )
            )

        bloqueios = []
        for row in bloqueio_rows:
            data_ini = _to_datetime(row.get("DATA_INI"))
            hora_ini = _to_int(row.get("HORA_INI"))
            hora_fin = _to_int(row.get("HORA_FIN"))
            if data_ini is None or hora_ini is None or hora_fin is None:
                continue
            bloqueios.append(
                AgendaLegadoBloqueio(
                    clinica_id=args.clinica_id,
                    id_bloqueio=_to_int(row.get("ID_BLOQUEIO")) or 0,
                    id_prestador=_to_int(row.get("ID_PRESTADOR")) or 0,
                    id_unidade=_to_int(row.get("ID_UNIDADE")) or 0,
                    dia_sem=_to_int(row.get("DIA_SEM")) or 0,
                    data_ini=data_ini,
                    data_fin=_to_datetime(row.get("DATA_FIN")),
                    hora_ini=hora_ini,
                    hora_fin=hora_fin,
                    msg_agenda=_clean_text(row.get("MSG_AGENDA")),
                )
            )

        if eventos:
            db.bulk_save_objects(eventos)
        if bloqueios:
            db.bulk_save_objects(bloqueios)

        if args.dry_run:
            db.rollback()
        else:
            db.commit()
    finally:
        db.close()

    print(f"Eventos agenda importados: {len(eventos)}")
    print(f"Bloqueios agenda importados: {len(bloqueios)}")
    if args.dry_run:
        print("Dry-run: nenhuma alteração persistida.")


if __name__ == "__main__":
    main()
