from __future__ import annotations

import argparse
import csv
import importlib
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal  # noqa: E402
from models.clinica import Clinica  # noqa: E402
from models.prestador_odonto import PrestadorOdonto  # noqa: E402
from models.usuario import Usuario  # noqa: E402
from security.system_accounts import (  # noqa: E402
    SYSTEM_PRESTADOR_CODIGO,
    SYSTEM_PRESTADOR_SOURCE_ID,
    SYSTEM_PRESTADOR_TIPO,
    SYSTEM_USER_CODIGO,
    SYSTEM_USER_NOME,
    is_system_user,
)


DEFAULT_PREST_CSV = PROJECT_DIR / "output" / "easy_prestador_full_20260331.csv"
DEFAULT_TIPOS_CSV = PROJECT_DIR / "output" / "easy_tipo_prest_20260331.csv"
DEFAULT_REPORT = PROJECT_DIR / "docs" / f"migracao_prestadores_easy_{datetime.now().date().isoformat()}.md"
DEFAULT_CHANGES = PROJECT_DIR / "output" / "migracao_prestadores_easy_changes.csv"


@dataclass
class EasyPrestador:
    source_id: int
    codigo: str
    tipo_id: int
    nome: str
    apelido: str
    email: str
    homepage: str
    data_inicio: str
    data_fim: str
    inativo: bool
    executa: bool


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        delimiter = ","
        if ";" in sample and sample.count(";") >= sample.count(","):
            delimiter = ";"
        return list(csv.DictReader(handle, delimiter=delimiter))


def _normalize(text: str | None) -> str:
    base = str(text or "").strip().lower()
    if not base:
        return ""
    base = unicodedata.normalize("NFKD", base)
    return "".join(ch for ch in base if not unicodedata.combining(ch))


def _load_model_registry() -> None:
    models_dir = BACKEND_DIR / "models"
    for path in models_dir.glob("*.py"):
        if path.name.startswith("_"):
            continue
        importlib.import_module(f"models.{path.stem}")


def _load_tipo_prest_map(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}
    rows = _read_csv(path)
    mapping: dict[int, str] = {}
    for row in rows:
        try:
            codigo = int(row.get("REGISTRO") or 0)
        except Exception:
            codigo = 0
        if codigo <= 0:
            continue
        nome = str(row.get("NOME") or "").strip()
        if nome:
            mapping[codigo] = nome
    return mapping


def _bool_from_easy(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    txt = str(value).strip().lower()
    if txt in {"1", "-1", "true", "sim", "s", "yes"}:
        return True
    if txt in {"0", "", "false", "nao", "não", "n", "no"}:
        return False
    return default


def _load_easy_prestadores(path: Path) -> list[EasyPrestador]:
    rows = _read_csv(path)
    prestadores: list[EasyPrestador] = []
    for row in rows:
        try:
            source_id = int(row.get("ID_PRESTADOR") or 0)
        except Exception:
            source_id = 0
        if source_id <= 0:
            continue
        codigo = str(row.get("COD_PRESTADOR") or "").strip()
        try:
            tipo_id = int(row.get("ID_TIPO_PREST") or 0)
        except Exception:
            tipo_id = 0
        nome = str(row.get("NOME") or "").strip()
        apelido = str(row.get("APELIDO") or "").strip()
        email = str(row.get("EMAIL") or "").strip()
        homepage = str(row.get("HOMEPAGE") or "").strip()
        data_inicio = str(row.get("DATA_INI") or "").strip()
        data_fim = str(row.get("DATA_FIN") or "").strip()
        inativo = _bool_from_easy(row.get("INATIVO"), default=False)
        executa = _bool_from_easy(row.get("EXECUTA_PROCEDIMENTO"), default=True)
        prestadores.append(
            EasyPrestador(
                source_id=source_id,
                codigo=codigo,
                tipo_id=tipo_id,
                nome=nome,
                apelido=apelido,
                email=email,
                homepage=homepage,
                data_inicio=data_inicio,
                data_fim=data_fim,
                inativo=inativo,
                executa=executa,
            )
        )
    return prestadores


def _find_usuario_para_prestador(
    usuarios: list[Usuario],
    prestador: EasyPrestador,
) -> int | None:
    if prestador.source_id == SYSTEM_PRESTADOR_SOURCE_ID:
        sys_user = next((u for u in usuarios if is_system_user(u)), None)
        return int(sys_user.id) if sys_user else None
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Migra prestadores do EasyDental (CSV) para SaaS.")
    parser.add_argument("--email", help="E-mail do dono da clinica SaaS (ex: gleissontel@gmail.com).")
    parser.add_argument("--clinica-id", type=int, default=0, help="ID da clinica SaaS.")
    parser.add_argument("--csv", default=str(DEFAULT_PREST_CSV), help="CSV com prestadores do Easy.")
    parser.add_argument("--tipos-csv", default=str(DEFAULT_TIPOS_CSV), help="CSV com tipos de prestador do Easy.")
    parser.add_argument("--prune", action="store_true", help="Remove prestadores que nao existem no CSV.")
    parser.add_argument("--apply", action="store_true", help="Aplica a migracao no banco.")
    args = parser.parse_args()

    load_dotenv(BACKEND_DIR / ".env")
    _load_model_registry()

    prest_csv = Path(args.csv)
    if not prest_csv.exists():
        raise RuntimeError(f"CSV de prestadores nao encontrado: {prest_csv}")

    tipo_map = _load_tipo_prest_map(Path(args.tipos_csv))
    easy_prestadores = _load_easy_prestadores(prest_csv)

    db = SessionLocal()
    try:
        clinica = None
        if args.clinica_id:
            clinica = db.query(Clinica).filter(Clinica.id == int(args.clinica_id)).first()
        if clinica is None and args.email:
            owner = db.query(Usuario).filter(Usuario.email == args.email).first()
            if owner:
                clinica = db.query(Clinica).filter(Clinica.id == owner.clinica_id).first()
        if not clinica:
            raise RuntimeError("Clinica alvo nao encontrada. Informe --email ou --clinica-id.")

        usuarios = (
            db.query(Usuario)
            .filter(Usuario.clinica_id == clinica.id)
            .order_by(Usuario.id.asc())
            .all()
        )
        existing = (
            db.query(PrestadorOdonto)
            .filter(PrestadorOdonto.clinica_id == clinica.id)
            .all()
        )
        by_source = {int(item.source_id): item for item in existing if item.source_id is not None}

        report_lines = []
        report_lines.append(f"# Migracao de prestadores Easy -> SaaS ({datetime.now().date().isoformat()})\n")
        report_lines.append(f"- Clinica: {clinica.id} - {clinica.nome}\n")
        report_lines.append(f"- Modo: {'APLICADO' if args.apply else 'DRY-RUN'}\n\n")
        report_lines.append("| Easy ID | Nome | Codigo | Tipo | Acao | Usuario vinculado |\n")
        report_lines.append("| --- | --- | --- | --- | --- | --- |\n")

        changes: list[dict[str, str]] = []
        seen_source_ids: set[int] = set()

        for prest in easy_prestadores:
            seen_source_ids.add(prest.source_id)
            tipo_nome = tipo_map.get(prest.tipo_id, "") or (SYSTEM_PRESTADOR_TIPO if prest.source_id == SYSTEM_PRESTADOR_SOURCE_ID else "")
            row = by_source.get(prest.source_id)
            action = "criado"
            if row:
                action = "atualizado"
            else:
                row = PrestadorOdonto(
                    clinica_id=clinica.id,
                    source_id=prest.source_id,
                )
                db.add(row)

            row.codigo = prest.codigo or (SYSTEM_PRESTADOR_CODIGO if prest.source_id == SYSTEM_PRESTADOR_SOURCE_ID else row.codigo)
            row.nome = prest.nome or row.nome
            row.apelido = prest.apelido or row.apelido
            row.tipo_prestador = tipo_nome or row.tipo_prestador
            row.data_inicio = prest.data_inicio or row.data_inicio
            row.data_termino = prest.data_fim or row.data_termino
            row.inativo = bool(prest.inativo)
            row.executa_procedimento = bool(prest.executa)
            row.is_system_prestador = prest.source_id == SYSTEM_PRESTADOR_SOURCE_ID
            row.email = prest.email or row.email
            row.homepage = prest.homepage or row.homepage
            row.id_interno = str(prest.source_id)

            usuario_id = _find_usuario_para_prestador(usuarios, prest)
            if usuario_id is not None:
                row.usuario_id = usuario_id
            elif prest.source_id != SYSTEM_PRESTADOR_SOURCE_ID:
                row.usuario_id = None

            report_lines.append(
                f"| {prest.source_id} | {prest.nome} | {prest.codigo} | {tipo_nome} | {action} | {row.usuario_id or ''} |\n"
            )
            changes.append(
                {
                    "easy_id": str(prest.source_id),
                    "nome": prest.nome,
                    "codigo": prest.codigo,
                    "tipo": tipo_nome,
                    "acao": action,
                    "usuario_id": str(row.usuario_id or ""),
                }
            )

        removidos = []
        if args.prune:
            for item in existing:
                if int(item.source_id or 0) in seen_source_ids:
                    continue
                removidos.append(item)
                db.delete(item)

        if removidos:
            report_lines.append("\n## Removidos (nao estavam no CSV)\n")
            for item in removidos:
                report_lines.append(f"- {item.id} | {item.nome} | source_id={item.source_id}\n")

        if args.apply:
            db.commit()
        else:
            db.rollback()

        DEFAULT_REPORT.write_text("".join(report_lines), encoding="utf-8")
        DEFAULT_CHANGES.parent.mkdir(parents=True, exist_ok=True)
        with DEFAULT_CHANGES.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["easy_id", "nome", "codigo", "tipo", "acao", "usuario_id"],
            )
            writer.writeheader()
            writer.writerows(changes)
        print(f"Report: {DEFAULT_REPORT}")
        print(f"Changes: {DEFAULT_CHANGES}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
