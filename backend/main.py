import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from database import Base, SessionLocal, engine
from models.access_profile import AccessProfile  # noqa: F401
from models.agenda_legado import AgendaLegadoBloqueio, AgendaLegadoEvento  # noqa: F401
from models.anamnese import AnamnesePergunta, AnamneseQuestionario  # noqa: F401
from models.anamnese_resposta import AnamneseResposta  # noqa: F401
from models.clinica import Clinica  # noqa: F401
from models.contato import Contato  # noqa: F401
from models.convenio_odonto import CalendarioFaturamentoOdonto, ConvenioOdonto, PlanoOdonto  # noqa: F401
from models.controle_protetico import ControleProtetico  # noqa: F401
from models.doenca_cid import DoencaCid  # noqa: F401
from models.etiqueta_modelo import EtiquetaModelo  # noqa: F401
from models.etiqueta_padrao import EtiquetaPadrao  # noqa: F401
from models.indice_financeiro import IndiceCotacao, IndiceFinanceiro  # noqa: F401
from models.modelo_documento import ModeloDocumento  # noqa: F401
from models.paciente import Paciente  # noqa: F401
from models.prestador_odonto import PrestadorComissaoOdonto, PrestadorCredenciamentoOdonto, PrestadorOdonto  # noqa: F401
from models.protetico import Protetico, ServicoProtetico  # noqa: F401
from models.procedimento_generico import (  # noqa: F401
    ProcedimentoGenerico,
    ProcedimentoGenericoFase,
    ProcedimentoGenericoMaterial,
)
from models.simbolo_grafico import SimboloGrafico  # noqa: F401
from models.procedimento_tabela import ProcedimentoTabela  # noqa: F401
from models.procedimento import ProcedimentoFase  # noqa: F401
from models.tratamento import Tratamento  # noqa: F401
from models.tiss_tipo_tabela import TissTipoTabela  # noqa: F401
from models.unidade_atendimento import UnidadeAtendimento  # noqa: F401
from models.usuario_perfil_acesso import UsuarioPerfilAcesso  # noqa: F401
from models.relatorio_config import RelatorioConfig  # noqa: F401
from routes.auth_routes import router as auth_router
from routes.cadastros_routes import router as cadastros_router
from routes.cenario_routes import router as cenario_router
from routes.convenios_planos_routes import router as convenios_planos_router
from routes.controle_proteticos_routes import router as controle_proteticos_router
from routes.prestadores_routes import router as prestadores_router
from routes.cid_routes import router as cid_router
from routes.agenda_contatos_routes import router as agenda_contatos_router
from routes.agenda_legado_routes import router as agenda_legado_router
from routes.anamnese_routes import router as anamnese_router
from routes.financeiro_routes import router as financeiro_router
from routes.indices_financeiros_routes import router as indices_financeiros_router
from routes.licenca_routes import router as licenca_router
from routes.materiais_routes import router as materiais_router
from routes.procedimentos_routes import router as procedimentos_router
from routes.relatorios_routes import router as relatorios_router
from routes.etiquetas_routes import router as etiquetas_router
from routes.editor_textos_routes import router as editor_textos_router
from routes.preferences_routes import router as preferences_router
from routes.system_options_routes import router as system_options_router
from routes.proteticos_routes import router as proteticos_router
from routes.tratamentos_routes import router as tratamentos_router
from routes.superadmin_routes import router as superadmin_router
from routes.user_admin_routes import router as user_admin_router
from routes.unidades_atendimento_routes import router as unidades_atendimento_router
from security.tenant import TenantMiddleware
from security.trial_middleware import TrialMiddleware
from services.runtime_profile_service import resolve_runtime_policy
from services.runtime_bootstrap_service import (
    is_http_runtime_bootstrap_allowed,
    run_runtime_bootstrap_global,
)

app = FastAPI(
    title="Brana SaaS",
    version="1.0.0",
)

BASE_DIR = Path(__file__).resolve().parent
SAAS_DIR = BASE_DIR.parent
PROJECT_DIR = SAAS_DIR.parent
FRONTEND_DIR = SAAS_DIR / "frontend"
DESKTOP_ASSETS_DIR = SAAS_DIR / "assets"
MODEL_STORAGE_DIR = SAAS_DIR / "storage" / "modelos"

MODELO_TIPOS_DIR = (
    "atestados",
    "receitas",
    "recibos",
    "etiquetas",
    "orcamentos",
    "email_agenda",
    "whatsapp_agenda",
    "outros",
)


RUNTIME_POLICY = resolve_runtime_policy()
RUN_SCHEMA_BOOTSTRAP = RUNTIME_POLICY.enable_schema_bootstrap
RUN_RUNTIME_BOOTSTRAP = RUNTIME_POLICY.enable_runtime_bootstrap
print(
    f"[startup] policy profile={RUNTIME_POLICY.profile} "
    f"schema_bootstrap={RUN_SCHEMA_BOOTSTRAP} "
    f"runtime_bootstrap={RUN_RUNTIME_BOOTSTRAP}"
)


def _garantir_diretorios_modelos() -> None:
    (MODEL_STORAGE_DIR / "base").mkdir(parents=True, exist_ok=True)
    (MODEL_STORAGE_DIR / "clinicas").mkdir(parents=True, exist_ok=True)
    for tipo in MODELO_TIPOS_DIR:
        (MODEL_STORAGE_DIR / "base" / tipo).mkdir(parents=True, exist_ok=True)


def _garantir_diretorios_modelos_clinicas_existentes() -> None:
    db = SessionLocal()
    try:
        clinica_ids = [int(item[0]) for item in db.query(Clinica.id).all() if item and item[0]]
    finally:
        db.close()
    for clinica_id in clinica_ids:
        base_clinica_dir = MODEL_STORAGE_DIR / "clinicas" / str(clinica_id)
        for tipo in MODELO_TIPOS_DIR:
            (base_clinica_dir / tipo).mkdir(parents=True, exist_ok=True)

# Criar tabelas no banco (uso local/desenvolvimento)
if RUN_SCHEMA_BOOTSTRAP:
    Base.metadata.create_all(bind=engine)
    _garantir_diretorios_modelos()
    _garantir_diretorios_modelos_clinicas_existentes()
else:
    print("[startup] BRANA_ENABLE_SCHEMA_BOOTSTRAP=0 -> bootstrap de schema/dados desativado no import")

# Compatibilidade com bancos ja existentes sem migrations
# Fase 2: bloco extraido para execucao manual versionada.
# Execute quando necessario: python scripts/aplicar_compatibilidade_schema.py

def _run_runtime_bootstrap_in_thread() -> None:
    try:
        summary = run_runtime_bootstrap_global(source="startup_http")
        status = "ok" if summary.get("ok") else "falhou"
        print(f"[startup] runtime bootstrap ({status}) em {summary.get('duration_ms', 0)} ms")
    except Exception as exc:
        print(f"[startup] runtime bootstrap falhou: {exc}")


def _garantir_colunas_criticas_usuarios() -> None:
    """Hotfix seguro para ambientes sem shell (Render).

    Garante colunas exigidas pelo fluxo atual de autenticacao sem
    reintroduzir bootstrap pesado de schema no startup HTTP.
    """
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE IF EXISTS usuarios "
                    "ADD COLUMN IF NOT EXISTS setup_completed BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE IF EXISTS usuarios "
                    "ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
    except Exception as exc:
        # Nao bloquear subida da API por causa do hotfix.
        print(f"[startup] aviso: nao foi possivel garantir colunas criticas de usuarios: {exc}")


def _garantir_colunas_criticas_simbolos() -> None:
    """Hotfix de compatibilidade para schema legado de simbolos no Render."""
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE IF EXISTS simbolo_grafico_catalogo "
                    "ADD COLUMN IF NOT EXISTS clinica_id INTEGER"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE IF EXISTS simbolo_grafico_catalogo "
                    "ADD COLUMN IF NOT EXISTS legacy_id INTEGER"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE IF EXISTS simbolo_grafico_catalogo "
                    "ADD COLUMN IF NOT EXISTS especialidade INTEGER"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE IF EXISTS simbolo_grafico_catalogo "
                    "ADD COLUMN IF NOT EXISTS tipo_marca INTEGER"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE IF EXISTS simbolo_grafico_catalogo "
                    "ADD COLUMN IF NOT EXISTS tipo_simbolo INTEGER"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE IF EXISTS simbolo_grafico_catalogo "
                    "ADD COLUMN IF NOT EXISTS bitmap1 VARCHAR(30)"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE IF EXISTS simbolo_grafico_catalogo "
                    "ADD COLUMN IF NOT EXISTS bitmap2 VARCHAR(30)"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE IF EXISTS simbolo_grafico_catalogo "
                    "ADD COLUMN IF NOT EXISTS bitmap3 VARCHAR(30)"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE IF EXISTS simbolo_grafico_catalogo "
                    "ADD COLUMN IF NOT EXISTS icone VARCHAR(30)"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE IF EXISTS simbolo_grafico_catalogo "
                    "ADD COLUMN IF NOT EXISTS imagem_custom TEXT"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE IF EXISTS simbolo_grafico_catalogo "
                    "ADD COLUMN IF NOT EXISTS sobreposicao INTEGER"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE IF EXISTS simbolo_grafico_catalogo "
                    "ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT TRUE"
                )
            )
            conn.execute(
                text(
                    "UPDATE simbolo_grafico_catalogo "
                    "SET ativo = TRUE "
                    "WHERE ativo IS NULL"
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE simbolo_grafico_catalogo
                    SET clinica_id = (SELECT id FROM clinicas ORDER BY id LIMIT 1)
                    WHERE clinica_id IS NULL
                    """
                )
            )
    except Exception as exc:
        # Nao bloquear subida da API por causa do hotfix.
        print(f"[startup] aviso: nao foi possivel garantir colunas criticas de simbolos: {exc}")


@app.on_event("startup")
def _iniciar_bootstrap():
    import threading

    _garantir_colunas_criticas_usuarios()
    _garantir_colunas_criticas_simbolos()

    if str(os.getenv("BRANA_SKIP_BOOTSTRAP", "")).strip().lower() in {"1", "true", "yes", "sim"}:
        return

    if not RUN_RUNTIME_BOOTSTRAP:
        print("[startup] BRANA_ENABLE_RUNTIME_BOOTSTRAP=0 -> thread de bootstrap desativada")
        return

    if not is_http_runtime_bootstrap_allowed():
        print(
            "[startup] runtime bootstrap global bloqueado no startup HTTP. "
            "Execute manualmente: python scripts/executar_bootstrap_runtime_global.py"
        )
        return

    thread = threading.Thread(target=_run_runtime_bootstrap_in_thread, daemon=True)
    thread.start()

# Rotas API
app.include_router(auth_router)
app.include_router(cadastros_router)
app.include_router(unidades_atendimento_router)
app.include_router(cenario_router)
app.include_router(convenios_planos_router)
app.include_router(controle_proteticos_router)
app.include_router(prestadores_router)
app.include_router(cid_router)
app.include_router(agenda_contatos_router)
app.include_router(agenda_legado_router)
app.include_router(anamnese_router)
app.include_router(financeiro_router)
app.include_router(indices_financeiros_router)
app.include_router(relatorios_router)
app.include_router(licenca_router)
app.include_router(materiais_router)
app.include_router(procedimentos_router)
app.include_router(etiquetas_router)
app.include_router(editor_textos_router)
app.include_router(preferences_router)
app.include_router(system_options_router)
app.include_router(proteticos_router)
app.include_router(tratamentos_router)
app.include_router(superadmin_router)
app.include_router(user_admin_router)

# CORS para ambiente local
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware SaaS (ordem importa)
app.add_middleware(TenantMiddleware)
app.add_middleware(TrialMiddleware)


@app.middleware("http")
async def disable_frontend_cache(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path or ""
    if path == "/app" or path.startswith("/frontend"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.middleware("http")
async def enforce_utf8_charset(request: Request, call_next):
    response = await call_next(request)
    ctype = response.headers.get("content-type", "")
    ctype_lower = ctype.lower()
    if "charset=" in ctype_lower:
        return response
    if ctype_lower.startswith("text/"):
        response.headers["Content-Type"] = f"{ctype}; charset=utf-8" if ctype else "text/plain; charset=utf-8"
    elif "application/json" in ctype_lower:
        response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response

if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")

if DESKTOP_ASSETS_DIR.exists():
    app.mount("/desktop-assets", StaticFiles(directory=str(DESKTOP_ASSETS_DIR)), name="desktop-assets")


@app.get("/app", include_in_schema=False)
def frontend_app():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    icon = DESKTOP_ASSETS_DIR / "brana.png"
    if icon.exists():
        return FileResponse(icon)
    return Response(status_code=404)


@app.get("/")
def home():
    return RedirectResponse(url="/app", status_code=307)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "brana-saas",
        "runtime_profile": RUNTIME_POLICY.profile,
        "schema_bootstrap_enabled": RUN_SCHEMA_BOOTSTRAP,
        "runtime_bootstrap_enabled": RUN_RUNTIME_BOOTSTRAP,
    }

