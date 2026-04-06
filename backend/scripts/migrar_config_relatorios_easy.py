from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

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
from models.relatorio_config import RelatorioConfig  # noqa: E402
from models.usuario import Usuario  # noqa: E402


DEFAULT_REPORT = PROJECT_DIR / "docs" / f"migracao_config_relatorios_easy_{datetime.now().date().isoformat()}.md"
DEFAULT_CHANGES = PROJECT_DIR / "output" / "migracao_config_relatorios_easy.csv"


@dataclass
class EasyUsuarioPref:
    codigo: int
    nome: str
    pref: str


@dataclass
class EasyRelatorioColuna:
    codigo: int
    nome_rel: str
    seq: int
    coluna: str


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


def _to_int(value: object) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _to_float(value: object) -> float:
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return 0.0


def _colorref_to_hex(value: object) -> str:
    try:
        raw = int(value) & 0xFFFFFF
    except Exception:
        return "#111111"
    r = raw & 0xFF
    g = (raw >> 8) & 0xFF
    b = (raw >> 16) & 0xFF
    return f"#{r:02x}{g:02x}{b:02x}"


def _parse_style(value: str | None) -> dict:
    raw = str(value or "")
    tokens = {token.strip() for token in raw.split(",") if token.strip()}
    return {
        "bold": "fsBold" in tokens,
        "italic": "fsItalic" in tokens,
        "underline": "fsUnderline" in tokens,
        "strike": "fsStrikeOut" in tokens,
    }


def _parse_pref_text(pref: str | None) -> dict[str, str]:
    linhas = str(pref or "").replace("\r", "").split("\n")
    data: dict[str, str] = {}
    for linha in linhas:
        if "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        chave = chave.strip()
        if not chave:
            continue
        data[chave] = valor.strip()
    return data


def _montar_secao(pref: dict[str, str], prefixo: str) -> dict:
    fonte = _clean_text(pref.get(f"Fonte{prefixo}")) or "Tahoma"
    cor = _colorref_to_hex(pref.get(f"CorFonte{prefixo}"))
    tamanho = _to_int(pref.get(f"TamanhoFonte{prefixo}")) or 10
    estilos = _parse_style(pref.get(f"EstiloFonte{prefixo}"))
    return {
        "fontFamily": fonte,
        "fontSize": max(6, min(72, tamanho)),
        "bold": estilos["bold"],
        "italic": estilos["italic"],
        "underline": estilos["underline"],
        "strike": estilos["strike"],
        "color": cor,
    }


def _build_report_config(pref: str | None) -> dict:
    data = _parse_pref_text(pref)
    header = _clean_text(data.get("Titulo"))
    logo = _clean_text(data.get("Logotipo"))
    config = {
        "headerText": header,
        "printLogo": bool(logo),
        "logoPath": logo,
        "logoDataUrl": "",
        "printUser": data.get("ImpNomeUsuario") == "1",
        "printPage": data.get("ImpNroPagina") != "0",
        "printDateTime": data.get("ImpDataHora") != "0",
        "sectionId": "titulo",
        "sectionStyles": {
            "titulo": _montar_secao(data, "Titulo"),
            "cabecalho": _montar_secao(data, "Cabecalho"),
            "colunas": _montar_secao(data, "Header"),
            "corpo": _montar_secao(data, "Corpo"),
            "rodape": _montar_secao(data, "Rodape"),
        },
        "usePrinterPaper": True,
        "paperHeightCm": _to_float(data.get("AlturaPapel")) or 29.7,
        "paperWidthCm": _to_float(data.get("LarguraPapel")) or 21.0,
        "marginLeftCm": _to_float(data.get("MargemEsquerda")) or 1.0,
        "marginRightCm": _to_float(data.get("MargemDireita")) or 1.0,
        "marginTopCm": _to_float(data.get("MargemSuperior")) or 1.0,
        "marginBottomCm": _to_float(data.get("MargemInferior")) or 1.0,
        "printerName": "Escolher no navegador",
        "printerStatus": "Disponivel ao imprimir",
        "printerType": "Destino do navegador",
        "printerWhere": "Definido pelo sistema",
        "printerComment": "A impressora fisica e escolhida no dialogo final do navegador.",
        "paperSize": "A4",
        "paperSource": "Origem padrao",
        "printerOrientation": "retrato",
        "defaultOutput": _to_int(data.get("SaidaDefault")),
    }
    return config


def _fetch_pref_impressora(
    server: str,
    database: str,
    user: str,
    password: str,
    trusted: bool,
) -> list[EasyUsuarioPref]:
    conn = _connect(server, database, user, password, trusted)
    try:
        cur = conn.cursor()
        cur.execute("SELECT NROUSR, NOME, PREFIMPRESSORA FROM USUARIO")
        rows = cur.fetchall()
    finally:
        conn.close()
    items: list[EasyUsuarioPref] = []
    for row in rows:
        codigo = _to_int(getattr(row, "NROUSR", row[0] if len(row) > 0 else 0))
        nome = _clean_text(getattr(row, "NOME", row[1] if len(row) > 1 else ""))
        pref = str(getattr(row, "PREFIMPRESSORA", row[2] if len(row) > 2 else "") or "")
        items.append(EasyUsuarioPref(codigo=codigo, nome=nome, pref=pref))
    return items


def _fetch_config_report(
    server: str,
    database: str,
    user: str,
    password: str,
    trusted: bool,
) -> list[EasyRelatorioColuna]:
    conn = _connect(server, database, user, password, trusted)
    try:
        cur = conn.cursor()
        cur.execute("SELECT NROUSR, NOME_REL, SEQ, NOME_COLUNA FROM CONFIG_REPORT")
        rows = cur.fetchall()
    finally:
        conn.close()
    items: list[EasyRelatorioColuna] = []
    for row in rows:
        codigo = _to_int(getattr(row, "NROUSR", row[0] if len(row) > 0 else 0))
        nome_rel = _clean_text(getattr(row, "NOME_REL", row[1] if len(row) > 1 else ""))
        seq = _to_int(getattr(row, "SEQ", row[2] if len(row) > 2 else 0))
        coluna = _clean_text(getattr(row, "NOME_COLUNA", row[3] if len(row) > 3 else ""))
        if not nome_rel or not coluna:
            continue
        items.append(EasyRelatorioColuna(codigo=codigo, nome_rel=nome_rel, seq=seq, coluna=coluna))
    return items


def _normalize_name(value: str | None) -> str:
    return " ".join(str(value or "").lower().split())


def main() -> None:
    parser = argparse.ArgumentParser(description="Migra configuracao de relatorios do EasyDental para SaaS.")
    parser.add_argument("--email", default="gleissontel@gmail.com", help="E-mail do dono da clinica SaaS.")
    parser.add_argument("--clinica-id", type=int, default=0, help="ID da clinica SaaS.")
    parser.add_argument("--server", default=r"DELL_SERVIDOR\\EDS70")
    parser.add_argument("--database", default="eds70")
    parser.add_argument("--user", default="easy")
    parser.add_argument("--password", default="ysae")
    parser.add_argument("--trusted", action="store_true", help="Usa autenticacao integrada do Windows.")
    parser.add_argument("--apply", action="store_true", help="Aplica a migracao no banco.")
    parser.add_argument("--reset-config", action="store_true", help="Limpa configuracoes de relatorio existentes.")
    parser.add_argument("--reset-config-report", action="store_true", help="Remove colunas existentes antes de migrar.")
    args = parser.parse_args()

    load_dotenv(BACKEND_DIR / ".env")

    prefs = _fetch_pref_impressora(args.server, args.database, args.user, args.password, args.trusted)
    colunas = _fetch_config_report(args.server, args.database, args.user, args.password, args.trusted)

    db = SessionLocal()
    try:
        RelatorioConfig.__table__.create(bind=db.get_bind(), checkfirst=True)
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
            .all()
        )
        by_codigo = {int(u.codigo): u for u in usuarios if u.codigo}
        by_nome = {_normalize_name(u.nome): u for u in usuarios}

        if args.reset_config:
            for user in usuarios:
                user.preferencias_impressora_json = None

        atualizados = 0
        ignorados = 0
        config_report_add = 0
        config_report_skip = 0

        for item in prefs:
            usuario = by_codigo.get(item.codigo) or by_nome.get(_normalize_name(item.nome))
            if not usuario:
                ignorados += 1
                continue
            if not item.pref.strip():
                continue
            config = _build_report_config(item.pref)
            usuario.preferencias_impressora_json = json.dumps(config, ensure_ascii=False, separators=(",", ":"))
            atualizados += 1

        if args.reset_config_report:
            db.query(RelatorioConfig).filter(RelatorioConfig.clinica_id == clinica.id).delete(synchronize_session=False)

        for item in colunas:
            usuario = by_codigo.get(item.codigo) or by_nome.get(_normalize_name(next((p.nome for p in prefs if p.codigo == item.codigo), "")))
            if not usuario:
                config_report_skip += 1
                continue
            db.add(
                RelatorioConfig(
                    clinica_id=clinica.id,
                    usuario_id=usuario.id,
                    nome_rel=item.nome_rel,
                    seq=item.seq or 0,
                    nome_coluna=item.coluna,
                )
            )
            config_report_add += 1

        if args.apply:
            db.commit()
        else:
            db.rollback()

        report_lines = []
        report_lines.append(f"# Migracao configuracao de relatorios Easy -> SaaS ({datetime.now().date().isoformat()})\n")
        report_lines.append(f"- Clinica: {clinica.id} - {clinica.nome}\n")
        report_lines.append(f"- Modo: {'APLICADO' if args.apply else 'DRY-RUN'}\n")
        report_lines.append(f"- Usuarios Easy analisados: {len(prefs)}\n")
        report_lines.append(f"- Configuracoes atualizadas: {atualizados}\n")
        report_lines.append(f"- Usuarios ignorados (nao encontrados): {ignorados}\n")
        report_lines.append(f"- CONFIG_REPORT importadas: {config_report_add}\n")
        report_lines.append(f"- CONFIG_REPORT ignoradas: {config_report_skip}\n\n")
        report_lines.append("| Codigo | Usuario | Configuracao |\n")
        report_lines.append("| --- | --- | --- |\n")
        for item in prefs:
            status = "Ok" if item.pref.strip() else "Sem pref"
            report_lines.append(f"| {item.codigo} | {item.nome} | {status} |\n")

        DEFAULT_REPORT.write_text("".join(report_lines), encoding="utf-8")
        DEFAULT_CHANGES.parent.mkdir(parents=True, exist_ok=True)
        with DEFAULT_CHANGES.open("w", encoding="utf-8", newline="") as handle:
            handle.write("codigo;usuario;status\n")
            for item in prefs:
                status = "ok" if item.pref.strip() else "sem_pref"
                handle.write(f"{item.codigo};{item.nome};{status}\n")

        print(f"Report: {DEFAULT_REPORT}")
        print(f"Changes: {DEFAULT_CHANGES}")
        print(
            f"Usuarios: {len(prefs)} | Atualizados: {atualizados} | Ignorados: {ignorados} | "
            f"CONFIG_REPORT: {config_report_add} (skip {config_report_skip})"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
