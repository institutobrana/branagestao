from __future__ import annotations

import csv
import datetime as dt
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import func

try:
    import pyodbc
except ModuleNotFoundError:  # pragma: no cover - fallback local sem driver SQL
    pyodbc = None

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = Path(__file__).resolve().parents[3]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import Base, SessionLocal, engine
from models.clinica import Clinica
from models.paciente import Paciente
from models.usuario import Usuario

TARGET_EMAIL = "gleissontel@gmail.com"
SOURCE_SERVER = r"DELL_SERVIDOR\EDS70"
SOURCE_DATABASE = "eds70"
SOURCE_UID = "easy"
SOURCE_PWD = "ysae"
SOURCE_CSV_FALLBACK = PROJECT_DIR / "output" / "eds70_pacientes.csv"

SEXO_MAP = {
    "1": "Masculino",
    "2": "Feminino",
}
CORRESPONDENCIA_MAP = {
    "1": "Residencial",
    "2": "Comercial",
}
TIPO_FONE_MAP = {
    "1": "Residencial",
    "2": "Comercial",
    "3": "Fax",
    "4": "Celular",
    "5": "Recado",
}

PACIENTE_FIELDS = [
    "codigo",
    "nome",
    "sobrenome",
    "nome_completo",
    "apelido",
    "sexo",
    "data_nascimento",
    "data_cadastro",
    "status",
    "inativo",
    "cpf",
    "rg",
    "cns",
    "correspondencia",
    "endereco",
    "complemento",
    "bairro",
    "cidade",
    "uf",
    "cep",
    "email",
    "tipo_fone1",
    "fone1",
    "tipo_fone2",
    "fone2",
    "tipo_fone3",
    "fone3",
    "tipo_fone4",
    "fone4",
    "tipo_indicacao",
    "indicado_por",
    "anotacoes",
    "id_convenio",
    "id_plano",
    "id_unidade",
    "tabela_codigo",
    "cod_prontuario",
    "matricula",
    "data_validade_plano",
    "source_payload",
]


def _connect_source() -> Any:
    if pyodbc is None:
        raise RuntimeError("pyodbc indisponivel no ambiente.")
    return pyodbc.connect(
        "DRIVER={SQL Server};"
        f"SERVER={SOURCE_SERVER};"
        f"DATABASE={SOURCE_DATABASE};"
        f"UID={SOURCE_UID};"
        f"PWD={SOURCE_PWD};"
        "Connection Timeout=15;"
    )


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    try:
        return int(float(text))
    except Exception:
        return None


def _as_date_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        value = value.date()
    if isinstance(value, dt.date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = dt.datetime.strptime(text[:19], fmt)
            return parsed.date().isoformat()
        except Exception:
            continue
    return text


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dt.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"<bytes:{len(bytes(value))}>"
    return str(value)


def _full_name(nome: str | None, sobrenome: str | None) -> str | None:
    joined = " ".join(x for x in [nome or "", sobrenome or ""] if x.strip()).strip()
    return joined or None


def _to_row_dict(columns: list[str], row: Any) -> dict[str, Any]:
    return {columns[idx]: row[idx] for idx in range(len(columns))}


def _load_source_rows() -> list[dict[str, Any]]:
    if pyodbc is not None:
        try:
            cn = _connect_source()
            cur = cn.cursor()
            cur.execute(
                "SELECT * FROM PESSOAL "
                "WHERE NROPAC IS NOT NULL AND NROPAC > 0 "
                "ORDER BY NROPAC"
            )
            columns = [str(x[0]).strip().upper() for x in cur.description]
            rows = [_to_row_dict(columns, row) for row in cur.fetchall()]
            cn.close()
            return rows
        except Exception:
            pass

    if not SOURCE_CSV_FALLBACK.exists():
        raise RuntimeError(
            "Nao foi possivel ler PESSOAL via SQL Server e o arquivo fallback nao existe: "
            f"{SOURCE_CSV_FALLBACK}"
        )
    with SOURCE_CSV_FALLBACK.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = []
        for row in reader:
            rows.append({str(k or "").strip().upper(): v for k, v in row.items()})
    rows.sort(key=lambda x: int((x.get("NROPAC") or "0") or 0))
    return rows


def _map_source_row(row: dict[str, Any]) -> dict[str, Any] | None:
    codigo = _as_int(row.get("NROPAC"))
    if not codigo or codigo <= 0:
        return None

    nome = _as_text(row.get("PRINOM")) or f"Paciente {codigo}"
    sobrenome = _as_text(row.get("SEGNOM"))

    sexo_raw = _as_text(row.get("SEXO"))
    correspondencia_raw = _as_text(row.get("CORRESPONDENCIA"))
    tip_fone1_raw = _as_text(row.get("TIPFONE1"))
    tip_fone2_raw = _as_text(row.get("TIPFONE2"))
    tip_fone3_raw = _as_text(row.get("TIPFONE3"))
    tip_fone4_raw = _as_text(row.get("TIPFONE4"))

    status_raw = _as_text(row.get("STATUS"))
    status_norm = (status_raw or "").strip().lower()
    inativo = status_norm in {"0", "i", "inativo", "inactive"}

    payload = {
        "codigo": codigo,
        "nome": nome,
        "sobrenome": sobrenome,
        "nome_completo": _full_name(nome, sobrenome),
        "apelido": _as_text(row.get("APELIDO")),
        "sexo": SEXO_MAP.get(sexo_raw or "", sexo_raw),
        "data_nascimento": _as_date_text(row.get("DATNAS")),
        "data_cadastro": _as_date_text(row.get("DATCAD")),
        "status": status_raw,
        "inativo": inativo,
        "cpf": _as_text(row.get("CIC")),
        "rg": _as_text(row.get("RG")),
        "cns": _as_text(row.get("CD_CNS")),
        "correspondencia": CORRESPONDENCIA_MAP.get(correspondencia_raw or "", correspondencia_raw),
        "endereco": _as_text(row.get("ENDRES")),
        "complemento": _as_text(row.get("COMRES")),
        "bairro": _as_text(row.get("BAIRES")),
        "cidade": _as_text(row.get("CIDRES")),
        "uf": _as_text(row.get("ESTRES")),
        "cep": _as_text(row.get("CEPRES")),
        "email": _as_text(row.get("EMAIL")),
        "tipo_fone1": TIPO_FONE_MAP.get(tip_fone1_raw or "", tip_fone1_raw),
        "fone1": _as_text(row.get("FONE1")),
        "tipo_fone2": TIPO_FONE_MAP.get(tip_fone2_raw or "", tip_fone2_raw),
        "fone2": _as_text(row.get("FONE2")),
        "tipo_fone3": TIPO_FONE_MAP.get(tip_fone3_raw or "", tip_fone3_raw),
        "fone3": _as_text(row.get("FONE3")),
        "tipo_fone4": TIPO_FONE_MAP.get(tip_fone4_raw or "", tip_fone4_raw),
        "fone4": _as_text(row.get("FONE4")),
        "tipo_indicacao": _as_text(row.get("TIPO_INDICA")),
        "indicado_por": _as_text(row.get("INDICADOPOR")),
        "anotacoes": _as_text(row.get("ANOTAC")),
        "id_convenio": _as_int(row.get("ID_CONVENIO")),
        "id_plano": _as_int(row.get("ID_PLANO")),
        "id_unidade": _as_int(row.get("ID_UNIDADE")),
        "tabela_codigo": _as_int(row.get("NROTAB")),
        "cod_prontuario": _as_text(row.get("COD_PRONTUARIO")),
        "matricula": _as_text(row.get("MATRICULA")),
        "data_validade_plano": _as_date_text(row.get("DT_VALIDADE_PLANO")),
        "source_payload": {k: _json_value(v) for k, v in row.items()},
    }
    return payload


def migrar() -> None:
    Base.metadata.create_all(bind=engine)
    source_rows = _load_source_rows()
    if not source_rows:
        raise RuntimeError("Nenhum paciente encontrado em PESSOAL na origem.")

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

        existentes = {
            int(p.codigo): p
            for p in db.query(Paciente).filter(Paciente.clinica_id == clinica.id).all()
        }

        inseridos = 0
        atualizados = 0
        ignorados = 0

        for row in source_rows:
            payload = _map_source_row(row)
            if payload is None:
                ignorados += 1
                continue

            codigo = int(payload["codigo"])
            atual = existentes.get(codigo)
            if atual is None:
                db.add(Paciente(clinica_id=clinica.id, **payload))
                inseridos += 1
                continue

            houve_alteracao = False
            for field in PACIENTE_FIELDS:
                novo_valor = payload[field]
                if getattr(atual, field) != novo_valor:
                    setattr(atual, field, novo_valor)
                    houve_alteracao = True
            if houve_alteracao:
                atualizados += 1

        db.commit()

        total_clinica = (
            db.query(Paciente.id)
            .filter(Paciente.clinica_id == clinica.id)
            .count()
        )
        outras_clinicas = (
            db.query(Paciente.clinica_id, func.count(Paciente.id))
            .filter(Paciente.clinica_id != clinica.id)
            .group_by(Paciente.clinica_id)
            .all()
        )

        print(
            "OK:",
            f"usuario={TARGET_EMAIL}",
            f"clinica_id={clinica.id}",
            f"origem_lidos={len(source_rows)}",
            f"inseridos={inseridos}",
            f"atualizados={atualizados}",
            f"ignorados={ignorados}",
            f"total_clinica={total_clinica}",
        )
        if outras_clinicas:
            resumo = ", ".join(f"clinica {int(cid)}={int(qtd)}" for cid, qtd in outras_clinicas)
            print("AVISO: outras clinicas com pacientes:", resumo)
        else:
            print("Validacao: nenhuma outra clinica recebeu pacientes.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrar()
