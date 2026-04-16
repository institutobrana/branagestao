import json
import importlib
import getpass
import os
import pkgutil
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from sqlalchemy import text

from database import SessionLocal
from services.runtime_profile_service import resolve_runtime_policy
from services.etiquetas_service import garantir_etiquetas_padrao_modelos
from services.indices_service import garantir_indices_padrao_todas_clinicas
from services.modelos_service import sincronizar_catalogo_modelos_storage
from services.procedimentos_legado_service import garantir_metadados_tabela_particular
from services.signup_service import (
    garantir_anamnese_padrao_todas_clinicas,
    garantir_auxiliares_raw_todas_clinicas,
    garantir_cid_padrao_todas_clinicas,
    garantir_especialidades_padrao_todas_clinicas,
    garantir_financeiro_padrao_todas_clinicas,
    garantir_lista_padrao_todas_clinicas,
    garantir_procedimentos_padrao_todas_clinicas,
    separar_tabela_exemplo_particular_todas_clinicas,
)
from services.simbolos_service import garantir_catalogo_simbolos

_RUNTIME_BOOTSTRAP_LOCK = threading.Lock()
_DB_ADVISORY_LOCK_KEY = 7304202601


def _import_all_model_modules() -> None:
    import models as models_pkg

    for module in pkgutil.iter_modules(models_pkg.__path__):
        if module.ispkg or module.name.startswith("__"):
            continue
        importlib.import_module(f"models.{module.name}")


# Garante todos os mapeamentos ORM registrados em execucao manual (fora do main.py).
_import_all_model_modules()


def is_http_runtime_bootstrap_allowed() -> bool:
    return resolve_runtime_policy().allow_http_runtime_bootstrap


def _audit_log_path() -> Path:
    configured = str(os.getenv("BRANA_RUNTIME_BOOTSTRAP_AUDIT_PATH", "")).strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent.parent / "backups" / "runtime_bootstrap_audit.jsonl"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_audit_log(entry: Dict[str, Any]) -> None:
    path = _audit_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


RUNTIME_BOOTSTRAP_JOBS: List[Tuple[str, Any]] = [
    ("sincronizar_catalogo_modelos_storage", sincronizar_catalogo_modelos_storage),
    ("garantir_etiquetas_padrao_modelos", garantir_etiquetas_padrao_modelos),
    ("garantir_catalogo_simbolos", garantir_catalogo_simbolos),
    ("garantir_lista_padrao_todas_clinicas", garantir_lista_padrao_todas_clinicas),
    ("garantir_procedimentos_padrao_todas_clinicas", garantir_procedimentos_padrao_todas_clinicas),
    ("separar_tabela_exemplo_particular_todas_clinicas", separar_tabela_exemplo_particular_todas_clinicas),
    ("garantir_metadados_tabela_particular", garantir_metadados_tabela_particular),
    ("garantir_financeiro_padrao_todas_clinicas", garantir_financeiro_padrao_todas_clinicas),
    ("garantir_indices_padrao_todas_clinicas", garantir_indices_padrao_todas_clinicas),
    ("garantir_especialidades_padrao_todas_clinicas", garantir_especialidades_padrao_todas_clinicas),
    ("garantir_auxiliares_raw_todas_clinicas", garantir_auxiliares_raw_todas_clinicas),
    ("garantir_cid_padrao_todas_clinicas", garantir_cid_padrao_todas_clinicas),
    ("garantir_anamnese_padrao_todas_clinicas", garantir_anamnese_padrao_todas_clinicas),
]


def run_runtime_bootstrap_global(source: str = "manual_script") -> Dict[str, Any]:
    policy = resolve_runtime_policy()
    actor = f"{getpass.getuser()}@{socket.gethostname()}"

    if not _RUNTIME_BOOTSTRAP_LOCK.acquire(blocking=False):
        summary = {
            "source": source,
            "actor": actor,
            "profile": policy.profile,
            "ok": False,
            "skipped": True,
            "reason": "already_running",
            "started_at": _utc_now_iso(),
            "finished_at": _utc_now_iso(),
            "duration_ms": 0,
            "jobs": [],
        }
        _append_audit_log(summary)
        return summary

    started_at = _utc_now_iso()
    started_perf = time.perf_counter()
    db = SessionLocal()
    jobs: List[Dict[str, Any]] = []
    db_lock_acquired = False
    try:
        db_lock_acquired = bool(
            db.execute(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": _DB_ADVISORY_LOCK_KEY},
            ).scalar()
        )
        if not db_lock_acquired:
            summary = {
                "source": source,
                "actor": actor,
                "profile": policy.profile,
                "ok": False,
                "skipped": True,
                "reason": "already_running_db_lock",
                "started_at": started_at,
                "finished_at": _utc_now_iso(),
                "duration_ms": int((time.perf_counter() - started_perf) * 1000),
                "jobs": [],
            }
            _append_audit_log(summary)
            return summary
        for job_name, job_func in RUNTIME_BOOTSTRAP_JOBS:
            t0 = time.perf_counter()
            if source == "manual_script":
                print(f"[runtime-bootstrap] Iniciando job: {job_name}", flush=True)
            job_func(db)
            duration_ms = int((time.perf_counter() - t0) * 1000)
            jobs.append({"job": job_name, "duration_ms": duration_ms})
            if source == "manual_script":
                print(f"[runtime-bootstrap] Concluido job: {job_name} ({duration_ms} ms)", flush=True)
        db.commit()
        summary = {
            "source": source,
            "actor": actor,
            "profile": policy.profile,
            "ok": True,
            "skipped": False,
            "reason": "",
            "started_at": started_at,
            "finished_at": _utc_now_iso(),
            "duration_ms": int((time.perf_counter() - started_perf) * 1000),
            "jobs": jobs,
        }
        _append_audit_log(summary)
        return summary
    except Exception as exc:
        db.rollback()
        summary = {
            "source": source,
            "actor": actor,
            "profile": policy.profile,
            "ok": False,
            "skipped": False,
            "reason": str(exc),
            "started_at": started_at,
            "finished_at": _utc_now_iso(),
            "duration_ms": int((time.perf_counter() - started_perf) * 1000),
            "jobs": jobs,
        }
        _append_audit_log(summary)
        raise
    finally:
        if db_lock_acquired:
            try:
                db.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": _DB_ADVISORY_LOCK_KEY},
                )
            except Exception:
                pass
        db.close()
        _RUNTIME_BOOTSTRAP_LOCK.release()
