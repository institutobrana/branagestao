import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.runtime_bootstrap_service import run_runtime_bootstrap_global


def main() -> int:
    print("[runtime-bootstrap] Executando jobs globais de runtime em modo manual...")
    try:
        summary = run_runtime_bootstrap_global(source="manual_script")
    except Exception as exc:
        print(f"[runtime-bootstrap] Falha: {exc}")
        return 1

    print("[runtime-bootstrap] Resultado:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
