from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv

try:
    import pyodbc  # type: ignore
except Exception:  # pragma: no cover
    pyodbc = None

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal  # noqa: E402
from models.clinica import Clinica  # noqa: E402
from models.indice_financeiro import IndiceCotacao, IndiceFinanceiro  # noqa: E402
from models.usuario import Usuario  # noqa: E402
from services.indices_service import garantir_indices_padrao_clinica  # noqa: E402


DEFAULT_REPORT = PROJECT_DIR / "docs" / f"migracao_indices_financeiros_easy_{datetime.now().date().isoformat()}.md"
DEFAULT_CHANGES = PROJECT_DIR / "output" / "migracao_indices_financeiros_easy.csv"

RESERVADOS = {1, 2, 3, 255}


@dataclass
class EasyIndice:
    numero: int
    nome: str
    sigla: str


@dataclass
class EasyCotacao:
    numero: int
    data_iso: str
    valor: float


def _connect(server: str, database: str, user: str, password: str, trusted: bool):
    if pyodbc is None:
        raise RuntimeError("pyodbc nao instalado. Instale pyodbc para conectar ao EasyDental.")
    if trusted:
        conn_str = (
            "DRIVER=SQL Server;"
            f"SERVER={server};"
            f"DATABASE={database};"
            "Trusted_Connection=yes"
        )
    else:
        conn_str = (
            "DRIVER=SQL Server;"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={user};"
            f"PWD={password};"
            "Trusted_Connection=no"
        )
    return pyodbc.connect(conn_str, timeout=10)


def _clean_text(value: str | None) -> str:
    return str(value or "").replace("\x00", "").strip()


def _to_int(value: str | int | None) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _to_float(value: str | float | None) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _format_date(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    raw = str(value or "").strip()
    if not raw:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return ""


def _load_model_registry() -> None:
    models_dir = BACKEND_DIR / "models"
    for path in models_dir.glob("*.py"):
        if path.name.startswith("_"):
            continue
        __import__(f"models.{path.stem}")


def _fetch_indices(
    server: str,
    database: str,
    user: str,
    password: str,
    trusted: bool,
) -> list[EasyIndice]:
    conn = _connect(server, database, user, password, trusted)
    try:
        cur = conn.cursor()
        cur.execute("SELECT NROIND, NOME, SIGLA FROM _INDICE")
        rows = cur.fetchall()
    finally:
        conn.close()
    itens: list[EasyIndice] = []
    for row in rows:
        numero = _to_int(getattr(row, "NROIND", row[0] if len(row) > 0 else 0))
        nome = _clean_text(getattr(row, "NOME", row[1] if len(row) > 1 else ""))
        sigla = _clean_text(getattr(row, "SIGLA", row[2] if len(row) > 2 else "")).upper()
        if numero <= 0:
            continue
        if not nome:
            nome = sigla or f"Indice {numero}"
        if not sigla:
            sigla = "R$" if numero == 255 else f"I{numero}"
        itens.append(EasyIndice(numero=numero, nome=nome, sigla=sigla))
    return itens


def _fetch_cotacoes(
    server: str,
    database: str,
    user: str,
    password: str,
    trusted: bool,
) -> list[EasyCotacao]:
    conn = _connect(server, database, user, password, trusted)
    try:
        cur = conn.cursor()
        cur.execute("SELECT NROIND, DATA, VALOR FROM COTACAO")
        rows = cur.fetchall()
    finally:
        conn.close()
    itens: list[EasyCotacao] = []
    for row in rows:
        numero = _to_int(getattr(row, "NROIND", row[0] if len(row) > 0 else 0))
        data_iso = _format_date(getattr(row, "DATA", row[1] if len(row) > 1 else ""))
        valor = _to_float(getattr(row, "VALOR", row[2] if len(row) > 2 else 0))
        if numero <= 0 or not data_iso:
            continue
        itens.append(EasyCotacao(numero=numero, data_iso=data_iso, valor=valor))
    return itens


def _index_by_numero(items: Iterable[EasyIndice]) -> dict[int, EasyIndice]:
    out: dict[int, EasyIndice] = {}
    for item in items:
        out[item.numero] = item
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Migra indices financeiros do EasyDental para SaaS.")
    parser.add_argument("--email", default="gleissontel@gmail.com", help="E-mail do dono da clinica SaaS.")
    parser.add_argument("--clinica-id", type=int, default=0, help="ID da clinica SaaS.")
    parser.add_argument("--server", default=r"DELL_SERVIDOR\EDS70")
    parser.add_argument("--database", default="eds70")
    parser.add_argument("--user", default="easy")
    parser.add_argument("--password", default="ysae")
    parser.add_argument("--trusted", action="store_true", help="Usa autenticacao integrada do Windows.")
    parser.add_argument("--apply", action="store_true", help="Aplica a migracao no banco.")
    parser.add_argument("--reset-cotacoes", action="store_true", help="Remove cotações existentes antes de migrar.")
    args = parser.parse_args()

    load_dotenv(BACKEND_DIR / ".env")
    _load_model_registry()

    easy_indices = _fetch_indices(args.server, args.database, args.user, args.password, args.trusted)
    easy_cotacoes = _fetch_cotacoes(args.server, args.database, args.user, args.password, args.trusted)
    easy_idx_map = _index_by_numero(easy_indices)

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

        garantir_indices_padrao_clinica(db, clinica.id)

        existentes = {
            int(item.numero): item
            for item in db.query(IndiceFinanceiro)
            .filter(IndiceFinanceiro.clinica_id == clinica.id)
            .all()
        }

        criados = 0
        atualizados = 0

        for item in easy_indices:
            reservado = item.numero in RESERVADOS
            idx = existentes.get(item.numero)
            if idx:
                idx.nome = item.nome
                idx.sigla = item.sigla
                idx.reservado = reservado
                idx.ativo = True
                db.add(idx)
                atualizados += 1
            else:
                idx = IndiceFinanceiro(
                    clinica_id=clinica.id,
                    numero=item.numero,
                    nome=item.nome,
                    sigla=item.sigla,
                    reservado=reservado,
                    ativo=True,
                )
                db.add(idx)
                existentes[item.numero] = idx
                criados += 1

        cotacoes_importadas = 0
        cotacoes_removidas = 0
        cotacoes_map: dict[int, list[EasyCotacao]] = {}
        for cot in easy_cotacoes:
            cotacoes_map.setdefault(cot.numero, []).append(cot)

        for numero, cot_list in cotacoes_map.items():
            idx = existentes.get(numero)
            if not idx:
                continue
            if args.reset_cotacoes:
                removed = (
                    db.query(IndiceCotacao)
                    .filter(
                        IndiceCotacao.clinica_id == clinica.id,
                        IndiceCotacao.indice_id == idx.id,
                    )
                    .delete(synchronize_session=False)
                )
                cotacoes_removidas += int(removed or 0)
            for cot in cot_list:
                db.add(
                    IndiceCotacao(
                        clinica_id=clinica.id,
                        indice_id=idx.id,
                        data=cot.data_iso,
                        valor=cot.valor,
                    )
                )
                cotacoes_importadas += 1

        if args.apply:
            db.commit()
        else:
            db.rollback()

        report_lines = []
        report_lines.append(f"# Migração de índices financeiros Easy -> SaaS ({datetime.now().date().isoformat()})\n")
        report_lines.append(f"- Clínica: {clinica.id} - {clinica.nome}\n")
        report_lines.append(f"- Modo: {'APLICADO' if args.apply else 'DRY-RUN'}\n")
        report_lines.append(f"- Índices Easy: {len(easy_indices)}\n")
        report_lines.append(f"- Cotações Easy: {len(easy_cotacoes)}\n")
        report_lines.append(f"- Índices criados: {criados}\n")
        report_lines.append(f"- Índices atualizados: {atualizados}\n")
        report_lines.append(f"- Cotações removidas: {cotacoes_removidas}\n")
        report_lines.append(f"- Cotações importadas: {cotacoes_importadas}\n\n")
        report_lines.append("| Número | Nome | Sigla | Reservado | Cotações |\n")
        report_lines.append("| --- | --- | --- | --- | --- |\n")
        for numero in sorted(easy_idx_map.keys()):
            item = easy_idx_map[numero]
            reservado = "Sim" if numero in RESERVADOS else "Não"
            total_cot = len(cotacoes_map.get(numero, []))
            report_lines.append(
                f"| {numero} | {item.nome} | {item.sigla} | {reservado} | {total_cot} |\n"
            )

        DEFAULT_REPORT.write_text("".join(report_lines), encoding="utf-8")
        DEFAULT_CHANGES.parent.mkdir(parents=True, exist_ok=True)
        with DEFAULT_CHANGES.open("w", encoding="utf-8", newline="") as handle:
            handle.write("numero;nome;sigla;reservado;cotacoes\n")
            for numero in sorted(easy_idx_map.keys()):
                item = easy_idx_map[numero]
                reservado = "1" if numero in RESERVADOS else "0"
                total_cot = len(cotacoes_map.get(numero, []))
                handle.write(f"{numero};{item.nome};{item.sigla};{reservado};{total_cot}\n")

        print(f"Report: {DEFAULT_REPORT}")
        print(f"Changes: {DEFAULT_CHANGES}")
        print(
            f"Indices: {len(easy_indices)} | Criados: {criados} | Atualizados: {atualizados} | "
            f"Cotacoes: {len(easy_cotacoes)} | Removidas: {cotacoes_removidas} | Importadas: {cotacoes_importadas}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
