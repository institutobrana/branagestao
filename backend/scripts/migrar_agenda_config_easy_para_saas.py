from __future__ import annotations

import argparse
import csv
import importlib
import json
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal  # noqa: E402
from models.clinica import Clinica  # noqa: E402
from models.prestador_odonto import PrestadorOdonto  # noqa: E402
from models.usuario import Usuario  # noqa: E402


DEFAULT_USERS_CSV = PROJECT_DIR / "output" / "easy_usuario_full_20260331.csv"
DEFAULT_REPORT = PROJECT_DIR / "docs" / f"migracao_agenda_config_{datetime.now().date().isoformat()}.md"
DEFAULT_CHANGES = PROJECT_DIR / "output" / "migracao_agenda_config_changes.csv"

VISUALIZACAO_FIELDS = [
    "N\u00famero do paciente",
    "N\u00famero do prontu\u00e1rio",
    "Nome do paciente",
    "Matr\u00edcula",
    "Conv\u00eanio",
    "Tabela",
    "Fone 1",
    "Fone 2",
    "Fone 3",
    "Sala",
]

VISUALIZACAO_DEFAULT = [
    "N\u00famero do paciente",
    "Nome do paciente",
    "Fone 1",
    "Fone 2",
    "Sala",
]

DIAS_SEMANA = [
    ("Segunda", 1),
    ("Terca", 2),
    ("Quarta", 3),
    ("Quinta", 4),
    ("Sexta", 5),
    ("Sabado", 6),
    ("Domingo", 7),
]


@dataclass
class EasyUserAgenda:
    user_id: int
    nome: str
    apelido: str
    prestador_id: int
    unidade_id: int | None
    pref_agenda: str


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        delimiter = ","
        if ";" in sample and sample.count(";") >= sample.count(","):
            delimiter = ";"
        return list(csv.DictReader(handle, delimiter=delimiter))


def _load_model_registry() -> None:
    models_dir = BACKEND_DIR / "models"
    for path in models_dir.glob("*.py"):
        if path.name.startswith("_"):
            continue
        importlib.import_module(f"models.{path.stem}")


def _normalize(text: str | None) -> str:
    base = str(text or "").strip().lower()
    if not base:
        return ""
    base = unicodedata.normalize("NFKD", base)
    return "".join(ch for ch in base if not unicodedata.combining(ch))


def _parse_prefagenda(raw: str | None) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in str(raw or "").replace("\r", "").split("\n"):
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _to_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except Exception:
        return None


def _normalize_hhmm(value: Any, fallback: str | None = None) -> str:
    txt = str(value or "").strip()
    if not txt:
        return fallback or ""
    parts = txt.split(":")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return fallback or ""
    h = int(parts[0])
    m = int(parts[1])
    if h < 0 or h > 23 or m < 0 or m > 59:
        return fallback or ""
    return f"{h:02d}:{m:02d}"


def _bool_from_pref(value: Any) -> bool:
    txt = str(value or "").strip().lower()
    return txt in {"1", "-1", "true", "sim", "s", "yes"}


def _bgr_to_hex(value: Any, fallback: str = "#000000") -> str:
    try:
        num = int(str(value).strip())
    except Exception:
        return fallback
    if num < 0:
        num = 0
    b = (num >> 16) & 0xFF
    g = (num >> 8) & 0xFF
    r = num & 0xFF
    return f"#{r:02x}{g:02x}{b:02x}"


def _decode_visualizacao(value: Any) -> list[str]:
    mask = _to_int(value) or 0
    selecionados: list[str] = []
    for idx, campo in enumerate(VISUALIZACAO_FIELDS):
        if mask & (1 << idx):
            selecionados.append(campo)
    return selecionados or VISUALIZACAO_DEFAULT[:]


def _parse_font_style(value: Any) -> dict[str, bool]:
    txt = _normalize(value)
    return {
        "bold": "bold" in txt,
        "italic": "italic" in txt,
        "underline": "underline" in txt,
        "strike": "strike" in txt or "strikeout" in txt,
    }


def _build_bloqueios(pref: dict[str, str]) -> list[dict[str, Any]]:
    itens: list[dict[str, Any]] = []
    for idx, (dia, dia_sem) in enumerate(DIAS_SEMANA, start=1):
        flag = _bool_from_pref(pref.get(f"Bloqueio.{dia}"))
        inicio = _normalize_hhmm(pref.get(f"Bloqueio.{dia}.Inicio"))
        fim = _normalize_hhmm(pref.get(f"Bloqueio.{dia}.Fim"))
        if not flag and not inicio and not fim:
            continue
        if not inicio and not fim:
            continue
        itens.append(
            {
                "id": int(datetime.now().timestamp() * 1000) + idx,
                "unidade": "",
                "unidade_id": None,
                "unidade_row_id": None,
                "dia": dia,
                "dia_sem": dia_sem,
                "vigencia_inicio": "",
                "vigencia_fim": "",
                "data_ini": "",
                "data_fin": "",
                "inicio": inicio,
                "final": fim,
                "hora_ini": inicio,
                "hora_fin": fim,
                "hora_ini_ms": None,
                "hora_fin_ms": None,
                "mensagem": "",
                "msg_agenda": "",
            }
        )
    return itens


def _build_agenda_config(pref: dict[str, str]) -> dict[str, Any]:
    manha_inicio = _normalize_hhmm(pref.get("InicioManha"), "07:00")
    manha_fim = _normalize_hhmm(pref.get("FimManha"), "13:00")
    tarde_inicio = _normalize_hhmm(pref.get("InicioTarde"), "13:00")
    tarde_fim = _normalize_hhmm(pref.get("FimTarde"), "20:00")
    duracao = str(_to_int(pref.get("Intervalo")) or 5)
    semana = str(_to_int(pref.get("HorariosPagSemana")) or 12)
    dia = str(_to_int(pref.get("HorariosPagDia")) or 12)

    fonte_nome = str(pref.get("Fonte") or "MS Sans Serif").strip() or "MS Sans Serif"
    fonte_tamanho = _to_int(pref.get("TamanhoFonte")) or 8
    estilo = _parse_font_style(pref.get("EstiloFonte"))
    cor_fonte = _bgr_to_hex(pref.get("CorFonte"), "#000000")

    cfg: dict[str, Any] = {
        "manha_inicio": manha_inicio,
        "manha_fim": manha_fim,
        "tarde_inicio": tarde_inicio,
        "tarde_fim": tarde_fim,
        "duracao": duracao,
        "semana_horarios": semana,
        "dia_horarios": dia,
        "apresentacao_particular_cor": _bgr_to_hex(pref.get("CorParticular"), "#ffff00"),
        "apresentacao_convenio_cor": _bgr_to_hex(pref.get("CorConvenio"), "#0000ff"),
        "apresentacao_compromisso_cor": _bgr_to_hex(pref.get("CorCompromisso"), "#00e5ef"),
        "apresentacao_fonte": {
            "family": fonte_nome,
            "size": fonte_tamanho,
            "bold": estilo["bold"],
            "italic": estilo["italic"],
            "underline": estilo["underline"],
            "strike": estilo["strike"],
            "color": cor_fonte,
            "script": "Ocidental",
        },
        "visualizacao_campos": _decode_visualizacao(pref.get("Visualizacao")),
    }
    bloqueios = _build_bloqueios(pref)
    if bloqueios:
        cfg["bloqueios_itens"] = bloqueios
    return cfg


def _merge_config(existing: dict[str, Any], incoming: dict[str, Any], *, force: bool) -> dict[str, Any]:
    if force or not existing:
        return dict(incoming)
    merged = dict(existing)
    for key, value in incoming.items():
        if key not in merged or merged[key] in (None, "", [], {}):
            merged[key] = value
            continue
        if key == "apresentacao_fonte" and isinstance(value, dict):
            base = dict(merged.get(key) or {})
            for sub_key, sub_val in value.items():
                if sub_key not in base or base[sub_key] in (None, "", 0):
                    base[sub_key] = sub_val
            merged[key] = base
            continue
        if key in {"visualizacao_campos", "bloqueios_itens"} and not merged.get(key):
            merged[key] = value
    return merged


def _load_easy_agenda_users(path: Path) -> list[EasyUserAgenda]:
    rows = _read_csv(path)
    users: list[EasyUserAgenda] = []
    for row in rows:
        try:
            user_id = int(row.get("NROUSR") or 0)
        except Exception:
            user_id = 0
        if user_id <= 0:
            continue
        try:
            prest_id = int(row.get("ID_PRESTADOR") or 0)
        except Exception:
            prest_id = 0
        if prest_id <= 0:
            continue
        try:
            unidade_id = int(row.get("ID_UNIDADE") or 0)
        except Exception:
            unidade_id = None
        users.append(
            EasyUserAgenda(
                user_id=user_id,
                nome=str(row.get("NOME") or "").strip(),
                apelido=str(row.get("APELIDO") or "").strip(),
                prestador_id=prest_id,
                unidade_id=unidade_id if unidade_id and unidade_id > 0 else None,
                pref_agenda=str(row.get("PREFAGENDA") or ""),
            )
        )
    return users


def main() -> None:
    parser = argparse.ArgumentParser(description="Migra configuracao de agenda (PREFAGENDA) do Easy para SaaS.")
    parser.add_argument("--email", help="E-mail do dono da clinica SaaS (ex: gleissontel@gmail.com).")
    parser.add_argument("--clinica-id", type=int, default=0, help="ID da clinica SaaS.")
    parser.add_argument("--csv", default=str(DEFAULT_USERS_CSV), help="CSV com usuarios do Easy (easy_usuario_full_*.csv).")
    parser.add_argument("--apply", action="store_true", help="Aplica a migracao no banco.")
    parser.add_argument("--force", action="store_true", help="Sobrescreve agenda_config existente.")
    args = parser.parse_args()

    load_dotenv(BACKEND_DIR / ".env")
    _load_model_registry()

    users_csv = Path(args.csv)
    if not users_csv.exists():
        raise RuntimeError(f"CSV de usuarios nao encontrado: {users_csv}")

    easy_users = _load_easy_agenda_users(users_csv)

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

        prestadores = (
            db.query(PrestadorOdonto)
            .filter(PrestadorOdonto.clinica_id == clinica.id)
            .all()
        )
        by_source = {int(item.source_id): item for item in prestadores if item.source_id is not None}

        report_lines = []
        report_lines.append(f"# Migracao configuracao de agenda (PREFAGENDA) ({datetime.now().date().isoformat()})\n")
        report_lines.append(f"- Clinica: {clinica.id} - {clinica.nome}\n")
        report_lines.append(f"- Modo: {'APLICADO' if args.apply else 'DRY-RUN'}\n\n")
        report_lines.append("| Easy User | Prestador ID | Nome | Acao | Visualizacao |\n")
        report_lines.append("| --- | --- | --- | --- | --- |\n")

        changes: list[dict[str, str]] = []
        updated = 0

        for easy_user in easy_users:
            prestador = by_source.get(int(easy_user.prestador_id))
            if not prestador:
                continue
            pref_map = _parse_prefagenda(easy_user.pref_agenda)
            if not pref_map:
                continue

            incoming = _build_agenda_config(pref_map)
            existing_cfg = {}
            if str(prestador.agenda_config_json or "").strip():
                try:
                    existing_cfg = json.loads(prestador.agenda_config_json or "{}")
                except Exception:
                    existing_cfg = {}

            merged = _merge_config(existing_cfg, incoming, force=args.force)
            if merged != existing_cfg:
                updated += 1
                if args.apply:
                    prestador.agenda_config_json = json.dumps(merged, ensure_ascii=False)

            vis = ", ".join(merged.get("visualizacao_campos") or incoming.get("visualizacao_campos") or [])
            action = "atualizado" if merged != existing_cfg else "mantido"
            report_lines.append(
                f"| {easy_user.user_id} | {easy_user.prestador_id} | {easy_user.apelido or easy_user.nome} | {action} | {vis} |\n"
            )
            changes.append(
                {
                    "easy_user": str(easy_user.user_id),
                    "prestador_id": str(easy_user.prestador_id),
                    "nome": easy_user.apelido or easy_user.nome,
                    "acao": action,
                    "visualizacao": vis,
                }
            )

        if args.apply:
            db.commit()

        report_lines.append(f"\n- Prestadores atualizados: {updated}\n")
        DEFAULT_REPORT.write_text("".join(report_lines), encoding="utf-8")

        with DEFAULT_CHANGES.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["easy_user", "prestador_id", "nome", "acao", "visualizacao"])
            writer.writeheader()
            writer.writerows(changes)

        print(f"Relatorio salvo em: {DEFAULT_REPORT}")
        print(f"Arquivo de mudancas: {DEFAULT_CHANGES}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
