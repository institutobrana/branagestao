from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
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
from routes.preferences_routes import router as preferences_router
from routes.system_options_routes import router as system_options_router
from routes.proteticos_routes import router as proteticos_router
from routes.tratamentos_routes import router as tratamentos_router
from routes.superadmin_routes import router as superadmin_router
from routes.user_admin_routes import router as user_admin_router
from routes.unidades_atendimento_routes import router as unidades_atendimento_router
from security.tenant import TenantMiddleware
from security.trial_middleware import TrialMiddleware
from services.procedimentos_legado_service import garantir_metadados_tabela_particular
from services.modelos_service import sincronizar_catalogo_modelos_storage
from services.etiquetas_service import garantir_etiquetas_padrao_modelos
from services.signup_service import (
    DEFAULT_LIST_NAME,
    garantir_auxiliares_raw_todas_clinicas,
    garantir_anamnese_padrao_todas_clinicas,
    garantir_cid_padrao_todas_clinicas,
    garantir_especialidades_padrao_todas_clinicas,
    garantir_financeiro_padrao_todas_clinicas,
    garantir_lista_padrao_todas_clinicas,
    garantir_procedimentos_padrao_todas_clinicas,
    separar_tabela_exemplo_particular_todas_clinicas,
)
from services.simbolos_service import garantir_catalogo_simbolos
from services.indices_service import garantir_indices_padrao_todas_clinicas

TISS_TIPO_TABELA_PADRAO = [
    {"id": 1, "codigo": "00", "nome": "Outras Tabelas"},
    {"id": 2, "codigo": "01", "nome": "Lista de Procedimentos Medicos AMB 90"},
    {"id": 3, "codigo": "02", "nome": "Lista de Procedimentos Medicos AMB 92"},
    {"id": 4, "codigo": "03", "nome": "Lista de Procedimentos Medicos AMB 96"},
    {"id": 5, "codigo": "04", "nome": "Lista de Procedimentos Medicos AMB 99"},
    {"id": 6, "codigo": "05", "nome": "Tabela Brasindice"},
    {"id": 7, "codigo": "06", "nome": "Class.Bras.Hierarq.de Procedimentos Medicos"},
    {"id": 8, "codigo": "07", "nome": "Tabela CIEFAS-93"},
    {"id": 9, "codigo": "08", "nome": "Rol de Procedimentos ANS"},
    {"id": 10, "codigo": "09", "nome": "Tabela de Procedimentos Ambulatoriais SUS"},
    {"id": 11, "codigo": "10", "nome": "Tabela de Procedimentos Hospitalares SUS"},
    {"id": 12, "codigo": "11", "nome": "Tabela SIMPRO"},
    {"id": 13, "codigo": "12", "nome": "Tabela TUNEP"},
    {"id": 14, "codigo": "13", "nome": "Tabela VRPO"},
    {"id": 15, "codigo": "14", "nome": "Tabela de Intercambio Sistema Uniodonto"},
    {"id": 16, "codigo": "94", "nome": "Tabela Propria Procedimentos"},
    {"id": 17, "codigo": "95", "nome": "Tabela Propria Materiais"},
    {"id": 18, "codigo": "96", "nome": "Tabela Propria Medicamentos"},
    {"id": 19, "codigo": "97", "nome": "Tabela Propria de Taxas Hospitalares"},
    {"id": 20, "codigo": "98", "nome": "Tabela Propria de Pacotes"},
    {"id": 21, "codigo": "99", "nome": "Tabela Propria de Gases Medicinais"},
]

LISTA_MATERIAL_ALIASES_SQL = (
    "'Tabela Brana',"
    "'Tabela modelo',"
    "'LISTA PADRÃO',"
    "'LISTA PADRAO'"
)


def _normalizar_listas_materiais_padrao(conn) -> None:
    conn.execute(
        text(
            f"""
            WITH listas_alvo AS (
                SELECT
                    l.id,
                    l.clinica_id,
                    l.nome,
                    CASE
                        WHEN l.nome = '{DEFAULT_LIST_NAME}' THEN 0
                        WHEN l.nome = 'Tabela modelo' THEN 1
                        WHEN l.nome = 'LISTA PADRÃO' THEN 2
                        WHEN l.nome = 'LISTA PADRAO' THEN 3
                        ELSE 9
                    END AS prioridade
                FROM lista_material l
                WHERE l.nome IN ({LISTA_MATERIAL_ALIASES_SQL})
            ),
            canonicas AS (
                SELECT DISTINCT ON (clinica_id)
                    clinica_id,
                    id AS canonical_list_id
                FROM listas_alvo
                ORDER BY clinica_id, prioridade, id
            )
            UPDATE lista_material l
            SET nome = '{DEFAULT_LIST_NAME}'
            FROM canonicas c
            WHERE l.id = c.canonical_list_id
              AND l.nome <> '{DEFAULT_LIST_NAME}'
            """
        )
    )
    conn.execute(
        text(
            f"""
            WITH listas_alvo AS (
                SELECT
                    l.id,
                    l.clinica_id,
                    l.nome,
                    CASE
                        WHEN l.nome = '{DEFAULT_LIST_NAME}' THEN 0
                        WHEN l.nome = 'Tabela modelo' THEN 1
                        WHEN l.nome = 'LISTA PADRÃO' THEN 2
                        WHEN l.nome = 'LISTA PADRAO' THEN 3
                        ELSE 9
                    END AS prioridade
                FROM lista_material l
                WHERE l.nome IN ({LISTA_MATERIAL_ALIASES_SQL})
            ),
            canonicas AS (
                SELECT DISTINCT ON (clinica_id)
                    clinica_id,
                    id AS canonical_list_id
                FROM listas_alvo
                ORDER BY clinica_id, prioridade, id
            ),
            materiais_ranked AS (
                SELECT
                    la.clinica_id,
                    m.codigo,
                    m.id AS material_id,
                    la.id AS lista_id,
                    c.canonical_list_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY la.clinica_id, m.codigo
                        ORDER BY
                            CASE WHEN la.id = c.canonical_list_id THEN 0 ELSE 1 END,
                            la.prioridade,
                            la.id,
                            m.id
                    ) AS rn
                FROM material m
                JOIN listas_alvo la ON la.id = m.lista_id
                JOIN canonicas c ON c.clinica_id = la.clinica_id
            ),
            sobreviventes AS (
                SELECT
                    clinica_id,
                    codigo,
                    material_id AS survivor_material_id,
                    canonical_list_id
                FROM materiais_ranked
                WHERE rn = 1
            )
            UPDATE material m
            SET lista_id = s.canonical_list_id
            FROM sobreviventes s
            WHERE m.id = s.survivor_material_id
              AND m.lista_id <> s.canonical_list_id
            """
        )
    )
    conn.execute(
        text(
            f"""
            WITH listas_alvo AS (
                SELECT
                    l.id,
                    l.clinica_id,
                    l.nome,
                    CASE
                        WHEN l.nome = '{DEFAULT_LIST_NAME}' THEN 0
                        WHEN l.nome = 'Tabela modelo' THEN 1
                        WHEN l.nome = 'LISTA PADRÃO' THEN 2
                        WHEN l.nome = 'LISTA PADRAO' THEN 3
                        ELSE 9
                    END AS prioridade
                FROM lista_material l
                WHERE l.nome IN ({LISTA_MATERIAL_ALIASES_SQL})
            ),
            canonicas AS (
                SELECT DISTINCT ON (clinica_id)
                    clinica_id,
                    id AS canonical_list_id
                FROM listas_alvo
                ORDER BY clinica_id, prioridade, id
            ),
            materiais_ranked AS (
                SELECT
                    la.clinica_id,
                    m.codigo,
                    m.id AS material_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY la.clinica_id, m.codigo
                        ORDER BY
                            CASE WHEN la.id = c.canonical_list_id THEN 0 ELSE 1 END,
                            la.prioridade,
                            la.id,
                            m.id
                    ) AS rn
                FROM material m
                JOIN listas_alvo la ON la.id = m.lista_id
                JOIN canonicas c ON c.clinica_id = la.clinica_id
            ),
            sobreviventes AS (
                SELECT clinica_id, codigo, material_id AS survivor_material_id
                FROM materiais_ranked
                WHERE rn = 1
            ),
            duplicados AS (
                SELECT
                    mr.material_id AS old_material_id,
                    s.survivor_material_id
                FROM materiais_ranked mr
                JOIN sobreviventes s
                  ON s.clinica_id = mr.clinica_id
                 AND s.codigo = mr.codigo
                WHERE mr.rn > 1
            ),
            agregados AS (
                SELECT
                    pm.procedimento_id,
                    d.survivor_material_id,
                    SUM(pm.quantidade) AS total_quantidade
                FROM procedimento_material pm
                JOIN duplicados d ON d.old_material_id = pm.material_id
                JOIN procedimento_material destino
                  ON destino.procedimento_id = pm.procedimento_id
                 AND destino.material_id = d.survivor_material_id
                GROUP BY pm.procedimento_id, d.survivor_material_id
            )
            UPDATE procedimento_material destino
            SET quantidade = COALESCE(destino.quantidade, 0) + COALESCE(a.total_quantidade, 0)
            FROM agregados a
            WHERE destino.procedimento_id = a.procedimento_id
              AND destino.material_id = a.survivor_material_id
            """
        )
    )
    conn.execute(
        text(
            f"""
            WITH listas_alvo AS (
                SELECT
                    l.id,
                    l.clinica_id,
                    l.nome,
                    CASE
                        WHEN l.nome = '{DEFAULT_LIST_NAME}' THEN 0
                        WHEN l.nome = 'Tabela modelo' THEN 1
                        WHEN l.nome = 'LISTA PADRÃO' THEN 2
                        WHEN l.nome = 'LISTA PADRAO' THEN 3
                        ELSE 9
                    END AS prioridade
                FROM lista_material l
                WHERE l.nome IN ({LISTA_MATERIAL_ALIASES_SQL})
            ),
            canonicas AS (
                SELECT DISTINCT ON (clinica_id)
                    clinica_id,
                    id AS canonical_list_id
                FROM listas_alvo
                ORDER BY clinica_id, prioridade, id
            ),
            materiais_ranked AS (
                SELECT
                    la.clinica_id,
                    m.codigo,
                    m.id AS material_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY la.clinica_id, m.codigo
                        ORDER BY
                            CASE WHEN la.id = c.canonical_list_id THEN 0 ELSE 1 END,
                            la.prioridade,
                            la.id,
                            m.id
                    ) AS rn
                FROM material m
                JOIN listas_alvo la ON la.id = m.lista_id
                JOIN canonicas c ON c.clinica_id = la.clinica_id
            ),
            sobreviventes AS (
                SELECT clinica_id, codigo, material_id AS survivor_material_id
                FROM materiais_ranked
                WHERE rn = 1
            ),
            duplicados AS (
                SELECT
                    mr.material_id AS old_material_id,
                    s.survivor_material_id
                FROM materiais_ranked mr
                JOIN sobreviventes s
                  ON s.clinica_id = mr.clinica_id
                 AND s.codigo = mr.codigo
                WHERE mr.rn > 1
            )
            UPDATE procedimento_material pm
            SET material_id = d.survivor_material_id
            FROM duplicados d
            WHERE pm.material_id = d.old_material_id
              AND NOT EXISTS (
                    SELECT 1
                    FROM procedimento_material destino
                    WHERE destino.procedimento_id = pm.procedimento_id
                      AND destino.material_id = d.survivor_material_id
                )
            """
        )
    )
    conn.execute(
        text(
            f"""
            WITH listas_alvo AS (
                SELECT
                    l.id,
                    l.clinica_id,
                    l.nome,
                    CASE
                        WHEN l.nome = '{DEFAULT_LIST_NAME}' THEN 0
                        WHEN l.nome = 'Tabela modelo' THEN 1
                        WHEN l.nome = 'LISTA PADRÃO' THEN 2
                        WHEN l.nome = 'LISTA PADRAO' THEN 3
                        ELSE 9
                    END AS prioridade
                FROM lista_material l
                WHERE l.nome IN ({LISTA_MATERIAL_ALIASES_SQL})
            ),
            canonicas AS (
                SELECT DISTINCT ON (clinica_id)
                    clinica_id,
                    id AS canonical_list_id
                FROM listas_alvo
                ORDER BY clinica_id, prioridade, id
            ),
            materiais_ranked AS (
                SELECT
                    la.clinica_id,
                    m.codigo,
                    m.id AS material_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY la.clinica_id, m.codigo
                        ORDER BY
                            CASE WHEN la.id = c.canonical_list_id THEN 0 ELSE 1 END,
                            la.prioridade,
                            la.id,
                            m.id
                    ) AS rn
                FROM material m
                JOIN listas_alvo la ON la.id = m.lista_id
                JOIN canonicas c ON c.clinica_id = la.clinica_id
            ),
            sobreviventes AS (
                SELECT clinica_id, codigo, material_id AS survivor_material_id
                FROM materiais_ranked
                WHERE rn = 1
            ),
            duplicados AS (
                SELECT
                    mr.material_id AS old_material_id,
                    s.survivor_material_id
                FROM materiais_ranked mr
                JOIN sobreviventes s
                  ON s.clinica_id = mr.clinica_id
                 AND s.codigo = mr.codigo
                WHERE mr.rn > 1
            ),
            agregados AS (
                SELECT
                    pm.procedimento_generico_id,
                    d.survivor_material_id,
                    SUM(pm.quantidade) AS total_quantidade
                FROM procedimento_generico_material pm
                JOIN duplicados d ON d.old_material_id = pm.material_id
                JOIN procedimento_generico_material destino
                  ON destino.procedimento_generico_id = pm.procedimento_generico_id
                 AND destino.material_id = d.survivor_material_id
                GROUP BY pm.procedimento_generico_id, d.survivor_material_id
            )
            UPDATE procedimento_generico_material destino
            SET quantidade = COALESCE(destino.quantidade, 0) + COALESCE(a.total_quantidade, 0)
            FROM agregados a
            WHERE destino.procedimento_generico_id = a.procedimento_generico_id
              AND destino.material_id = a.survivor_material_id
            """
        )
    )
    conn.execute(
        text(
            f"""
            WITH listas_alvo AS (
                SELECT
                    l.id,
                    l.clinica_id,
                    l.nome,
                    CASE
                        WHEN l.nome = '{DEFAULT_LIST_NAME}' THEN 0
                        WHEN l.nome = 'Tabela modelo' THEN 1
                        WHEN l.nome = 'LISTA PADRÃO' THEN 2
                        WHEN l.nome = 'LISTA PADRAO' THEN 3
                        ELSE 9
                    END AS prioridade
                FROM lista_material l
                WHERE l.nome IN ({LISTA_MATERIAL_ALIASES_SQL})
            ),
            canonicas AS (
                SELECT DISTINCT ON (clinica_id)
                    clinica_id,
                    id AS canonical_list_id
                FROM listas_alvo
                ORDER BY clinica_id, prioridade, id
            ),
            materiais_ranked AS (
                SELECT
                    la.clinica_id,
                    m.codigo,
                    m.id AS material_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY la.clinica_id, m.codigo
                        ORDER BY
                            CASE WHEN la.id = c.canonical_list_id THEN 0 ELSE 1 END,
                            la.prioridade,
                            la.id,
                            m.id
                    ) AS rn
                FROM material m
                JOIN listas_alvo la ON la.id = m.lista_id
                JOIN canonicas c ON c.clinica_id = la.clinica_id
            ),
            sobreviventes AS (
                SELECT clinica_id, codigo, material_id AS survivor_material_id
                FROM materiais_ranked
                WHERE rn = 1
            ),
            duplicados AS (
                SELECT
                    mr.material_id AS old_material_id,
                    s.survivor_material_id
                FROM materiais_ranked mr
                JOIN sobreviventes s
                  ON s.clinica_id = mr.clinica_id
                 AND s.codigo = mr.codigo
                WHERE mr.rn > 1
            )
            UPDATE procedimento_generico_material pm
            SET material_id = d.survivor_material_id
            FROM duplicados d
            WHERE pm.material_id = d.old_material_id
              AND NOT EXISTS (
                    SELECT 1
                    FROM procedimento_generico_material destino
                    WHERE destino.procedimento_generico_id = pm.procedimento_generico_id
                      AND destino.material_id = d.survivor_material_id
                )
            """
        )
    )
    conn.execute(
        text(
            f"""
            WITH listas_alvo AS (
                SELECT
                    l.id,
                    l.clinica_id,
                    l.nome,
                    CASE
                        WHEN l.nome = '{DEFAULT_LIST_NAME}' THEN 0
                        WHEN l.nome = 'Tabela modelo' THEN 1
                        WHEN l.nome = 'LISTA PADRÃO' THEN 2
                        WHEN l.nome = 'LISTA PADRAO' THEN 3
                        ELSE 9
                    END AS prioridade
                FROM lista_material l
                WHERE l.nome IN ({LISTA_MATERIAL_ALIASES_SQL})
            ),
            canonicas AS (
                SELECT DISTINCT ON (clinica_id)
                    clinica_id,
                    id AS canonical_list_id
                FROM listas_alvo
                ORDER BY clinica_id, prioridade, id
            ),
            materiais_ranked AS (
                SELECT
                    la.clinica_id,
                    m.codigo,
                    m.id AS material_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY la.clinica_id, m.codigo
                        ORDER BY
                            CASE WHEN la.id = c.canonical_list_id THEN 0 ELSE 1 END,
                            la.prioridade,
                            la.id,
                            m.id
                    ) AS rn
                FROM material m
                JOIN listas_alvo la ON la.id = m.lista_id
                JOIN canonicas c ON c.clinica_id = la.clinica_id
            ),
            sobreviventes AS (
                SELECT clinica_id, codigo, material_id AS survivor_material_id
                FROM materiais_ranked
                WHERE rn = 1
            ),
            duplicados AS (
                SELECT
                    mr.material_id AS old_material_id,
                    s.survivor_material_id
                FROM materiais_ranked mr
                JOIN sobreviventes s
                  ON s.clinica_id = mr.clinica_id
                 AND s.codigo = mr.codigo
                WHERE mr.rn > 1
            )
            DELETE FROM material m
            USING duplicados d
            WHERE m.id = d.old_material_id
            """
        )
    )
    conn.execute(
        text(
            f"""
            WITH listas_alvo AS (
                SELECT
                    l.id,
                    l.clinica_id,
                    l.nome,
                    CASE
                        WHEN l.nome = '{DEFAULT_LIST_NAME}' THEN 0
                        WHEN l.nome = 'Tabela modelo' THEN 1
                        WHEN l.nome = 'LISTA PADRÃO' THEN 2
                        WHEN l.nome = 'LISTA PADRAO' THEN 3
                        ELSE 9
                    END AS prioridade
                FROM lista_material l
                WHERE l.nome IN ({LISTA_MATERIAL_ALIASES_SQL})
            ),
            canonicas AS (
                SELECT DISTINCT ON (clinica_id)
                    clinica_id,
                    id AS canonical_list_id
                FROM listas_alvo
                ORDER BY clinica_id, prioridade, id
            )
            DELETE FROM lista_material l
            USING canonicas c
            WHERE l.clinica_id = c.clinica_id
              AND l.id <> c.canonical_list_id
              AND l.nome IN ({LISTA_MATERIAL_ALIASES_SQL})
            """
        )
    )


app = FastAPI(
    title="Brana SaaS",
    version="1.0.0",
)

BASE_DIR = Path(__file__).resolve().parent
SAAS_DIR = BASE_DIR.parent
PROJECT_DIR = SAAS_DIR.parent
FRONTEND_DIR = SAAS_DIR / "frontend"
DESKTOP_ASSETS_DIR = PROJECT_DIR / "assets"
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
Base.metadata.create_all(bind=engine)
_garantir_diretorios_modelos()
_garantir_diretorios_modelos_clinicas_existentes()

# Compatibilidade com bancos ja existentes sem migrations
with engine.begin() as conn:
    conn.execute(text("ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS cod_prontuario VARCHAR(40)"))
    conn.execute(
        text(
            """
            UPDATE pacientes
            SET cod_prontuario = NULLIF(BTRIM(source_payload ->> 'COD_PRONTUARIO'), '')
            WHERE (cod_prontuario IS NULL OR BTRIM(cod_prontuario) = '')
              AND source_payload IS NOT NULL
              AND NULLIF(BTRIM(source_payload ->> 'COD_PRONTUARIO'), '') IS NOT NULL
            """
        )
    )
    conn.execute(text("ALTER TABLE unidade_atendimento ADD COLUMN IF NOT EXISTS qtd_sala INTEGER NOT NULL DEFAULT 0"))
    conn.execute(text("UPDATE unidade_atendimento SET qtd_sala = 0 WHERE qtd_sala IS NULL"))
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT TRUE"))
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS codigo INTEGER"))
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS apelido VARCHAR(60)"))
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS tipo_usuario VARCHAR(80)"))
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS online BOOLEAN NOT NULL DEFAULT FALSE"))
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS forcar_troca_senha BOOLEAN NOT NULL DEFAULT FALSE"))
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS is_system_user BOOLEAN NOT NULL DEFAULT FALSE"))
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS prestador_id INTEGER"))
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS unidade_atendimento_id INTEGER"))
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS preferencias_usuario_json TEXT"))
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS preferencias_agenda_json TEXT"))
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS preferencias_impressora_json TEXT"))
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS preferencias_etiqueta_json TEXT"))
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS permissoes_json TEXT"))
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS modelos_documento (
                id SERIAL PRIMARY KEY,
                clinica_id INTEGER REFERENCES clinicas(id) ON DELETE CASCADE,
                tipo_modelo VARCHAR(40) NOT NULL,
                codigo VARCHAR(80),
                nome_exibicao VARCHAR(180) NOT NULL,
                nome_arquivo VARCHAR(255) NOT NULL,
                extensao VARCHAR(20),
                caminho_arquivo TEXT NOT NULL,
                ativo BOOLEAN NOT NULL DEFAULT TRUE,
                padrao_clinica BOOLEAN NOT NULL DEFAULT FALSE,
                origem VARCHAR(30) NOT NULL DEFAULT 'base',
                criado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                atualizado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_modelos_documento_clinica_id ON modelos_documento (clinica_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_modelos_documento_tipo_modelo ON modelos_documento (tipo_modelo)"))
    conn.execute(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_modelos_documento_escopo_tipo_nome
            ON modelos_documento (
                COALESCE(clinica_id, 0),
                tipo_modelo,
                nome_arquivo
            )
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS etiqueta_padrao (
                id INTEGER PRIMARY KEY,
                nome VARCHAR(80) NOT NULL,
                reservado BOOLEAN NOT NULL DEFAULT TRUE,
                margem_esq DOUBLE PRECISION,
                margem_sup DOUBLE PRECISION,
                esp_horizontal DOUBLE PRECISION,
                esp_vertical DOUBLE PRECISION,
                nro_colunas INTEGER,
                nro_linhas INTEGER
            )
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS etiqueta_modelo (
                id SERIAL PRIMARY KEY,
                clinica_id INTEGER NOT NULL REFERENCES clinicas(id),
                padrao_id INTEGER REFERENCES etiqueta_padrao(id),
                nome VARCHAR(80) NOT NULL,
                reservado BOOLEAN NOT NULL DEFAULT FALSE,
                margem_esq DOUBLE PRECISION,
                margem_sup DOUBLE PRECISION,
                esp_horizontal DOUBLE PRECISION,
                esp_vertical DOUBLE PRECISION,
                nro_colunas INTEGER,
                nro_linhas INTEGER,
                modelo_documento_id INTEGER REFERENCES modelos_documento(id),
                ativo BOOLEAN NOT NULL DEFAULT TRUE,
                criado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                atualizado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_etiqueta_modelo_clinica_id ON etiqueta_modelo (clinica_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_etiqueta_modelo_padrao_id ON etiqueta_modelo (padrao_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_etiqueta_modelo_documento_id ON etiqueta_modelo (modelo_documento_id)"))
    conn.execute(text("ALTER TABLE clinicas ADD COLUMN IF NOT EXISTS tipo_conta VARCHAR(20) NOT NULL DEFAULT 'DEMO 7 dias'"))
    conn.execute(text("ALTER TABLE clinicas ADD COLUMN IF NOT EXISTS licenca_usuario VARCHAR"))
    conn.execute(text("ALTER TABLE clinicas ADD COLUMN IF NOT EXISTS chave_licenca VARCHAR"))
    conn.execute(text("ALTER TABLE clinicas ADD COLUMN IF NOT EXISTS data_ativacao TIMESTAMP"))
    conn.execute(text("ALTER TABLE clinicas ADD COLUMN IF NOT EXISTS nome_tabela_procedimentos VARCHAR(120) NOT NULL DEFAULT 'Tabela Exemplo'"))
    conn.execute(text("ALTER TABLE clinicas ADD COLUMN IF NOT EXISTS opcoes_sistema_json TEXT"))
    conn.execute(text("ALTER TABLE lancamento ADD COLUMN IF NOT EXISTS situacao VARCHAR(20) DEFAULT 'Aberto'"))
    conn.execute(text("ALTER TABLE lancamento ADD COLUMN IF NOT EXISTS forma_pagamento VARCHAR"))
    conn.execute(text("ALTER TABLE lancamento ADD COLUMN IF NOT EXISTS data_vencimento VARCHAR"))
    conn.execute(text("ALTER TABLE lancamento ADD COLUMN IF NOT EXISTS data_inclusao VARCHAR"))
    conn.execute(text("ALTER TABLE lancamento ADD COLUMN IF NOT EXISTS data_alteracao VARCHAR"))
    conn.execute(text("ALTER TABLE lancamento ADD COLUMN IF NOT EXISTS documento VARCHAR"))
    conn.execute(text("ALTER TABLE lancamento ADD COLUMN IF NOT EXISTS referencia VARCHAR"))
    conn.execute(text("ALTER TABLE lancamento ADD COLUMN IF NOT EXISTS complemento VARCHAR"))
    conn.execute(text("ALTER TABLE lancamento ADD COLUMN IF NOT EXISTS tributavel INTEGER NOT NULL DEFAULT 0"))
    conn.execute(text("ALTER TABLE lancamento ADD COLUMN IF NOT EXISTS parcelado INTEGER NOT NULL DEFAULT 0"))
    conn.execute(text("ALTER TABLE lancamento ADD COLUMN IF NOT EXISTS qtd_parcelas INTEGER NOT NULL DEFAULT 1"))
    conn.execute(text("ALTER TABLE lancamento ADD COLUMN IF NOT EXISTS parcela_atual INTEGER NOT NULL DEFAULT 1"))
    conn.execute(text("ALTER TABLE lancamento ALTER COLUMN conta SET DEFAULT 'CLINICA'"))
    conn.execute(
        text(
            """
            UPDATE lancamento
            SET conta = 'CLINICA'
            WHERE conta IS NULL
               OR btrim(conta) = ''
               OR upper(btrim(conta)) IN ('EMPRESARIAL', 'CLÍNICA')
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE lancamento
            SET conta = 'CIRURGIAO'
            WHERE upper(btrim(conta)) IN ('PESSOAL', 'CIRURGIAO', 'CIRURGIÃO')
            """
        )
    )
    conn.execute(text("ALTER TABLE lista_material ADD COLUMN IF NOT EXISTS nro_indice INTEGER NOT NULL DEFAULT 255"))
    conn.execute(text("ALTER TABLE lista_material ALTER COLUMN nro_indice SET DEFAULT 255"))
    conn.execute(text("UPDATE lista_material SET nro_indice = 255 WHERE nro_indice IS NULL OR nro_indice <= 0"))
    _normalizar_listas_materiais_padrao(conn)
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS protetico (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(150) NOT NULL,
                clinica_id INTEGER NOT NULL REFERENCES clinicas(id) ON DELETE CASCADE
            )
            """
        )
    )
    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_protetico_clinica_nome ON protetico (clinica_id, nome)"))
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS servico_protetico (
                id SERIAL PRIMARY KEY,
                protetico_id INTEGER NOT NULL REFERENCES protetico(id) ON DELETE CASCADE,
                clinica_id INTEGER NOT NULL REFERENCES clinicas(id) ON DELETE CASCADE,
                nome VARCHAR(180) NOT NULL,
                indice VARCHAR(10) NOT NULL DEFAULT 'R$',
                preco DOUBLE PRECISION NOT NULL DEFAULT 0,
                prazo INTEGER NOT NULL DEFAULT 0
            )
            """
        )
    )
    conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_servico_protetico_nome ON servico_protetico (protetico_id, nome)"
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS contato (
                id SERIAL PRIMARY KEY,
                clinica_id INTEGER NOT NULL REFERENCES clinicas(id) ON DELETE CASCADE,
                protetico_id INTEGER REFERENCES protetico(id) ON DELETE SET NULL,
                nome VARCHAR(180) NOT NULL,
                tipo VARCHAR(60),
                contato VARCHAR(120),
                aniversario_dia INTEGER,
                aniversario_mes INTEGER,
                endereco VARCHAR(180),
                complemento VARCHAR(120),
                bairro VARCHAR(120),
                cidade VARCHAR(120),
                cep VARCHAR(20),
                uf VARCHAR(10),
                pais VARCHAR(80),
                tel1_tipo VARCHAR(40),
                tel1 VARCHAR(40),
                tel2_tipo VARCHAR(40),
                tel2 VARCHAR(40),
                tel3_tipo VARCHAR(40),
                tel3 VARCHAR(40),
                tel4_tipo VARCHAR(40),
                tel4 VARCHAR(40),
                email VARCHAR(180),
                homepage VARCHAR(180),
                palavra_chave_1 VARCHAR(120),
                palavra_chave_2 VARCHAR(120),
                registro VARCHAR(80),
                especialidade VARCHAR(40),
                incluir_malas_diretas BOOLEAN NOT NULL DEFAULT TRUE,
                incluir_preferidos BOOLEAN NOT NULL DEFAULT FALSE,
                observacoes TEXT
            )
            """
        )
    )
    conn.execute(text("ALTER TABLE contato ADD COLUMN IF NOT EXISTS palavra_chave_1 VARCHAR(120)"))
    conn.execute(text("ALTER TABLE contato ADD COLUMN IF NOT EXISTS palavra_chave_2 VARCHAR(120)"))
    conn.execute(text("ALTER TABLE contato ADD COLUMN IF NOT EXISTS registro VARCHAR(80)"))
    conn.execute(text("ALTER TABLE contato ADD COLUMN IF NOT EXISTS especialidade VARCHAR(40)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contato_clinica_id ON contato (clinica_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contato_tipo ON contato (tipo)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contato_nome ON contato (nome)"))
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS doenca_cid (
                id SERIAL PRIMARY KEY,
                clinica_id INTEGER NOT NULL REFERENCES clinicas(id) ON DELETE CASCADE,
                legacy_registro INTEGER,
                codigo VARCHAR(20) NOT NULL,
                descricao VARCHAR(200) NOT NULL,
                observacoes TEXT,
                preferido BOOLEAN NOT NULL DEFAULT FALSE
            )
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_doenca_cid_clinica_id ON doenca_cid (clinica_id)"))
    conn.execute(text("ALTER TABLE doenca_cid ADD COLUMN IF NOT EXISTS legacy_registro INTEGER"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_doenca_cid_legacy_registro ON doenca_cid (legacy_registro)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_doenca_cid_codigo ON doenca_cid (codigo)"))
    conn.execute(text("ALTER TABLE simbolo_grafico_catalogo ADD COLUMN IF NOT EXISTS legacy_id INTEGER"))
    conn.execute(text("ALTER TABLE simbolo_grafico_catalogo ADD COLUMN IF NOT EXISTS imagem_custom TEXT"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_simbolo_grafico_catalogo_legacy_id ON simbolo_grafico_catalogo (legacy_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_simbolo_grafico_catalogo_codigo ON simbolo_grafico_catalogo (codigo)"))
    conn.execute(
        text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'simbolo_grafico_catalogo_codigo_key'
                ) THEN
                    ALTER TABLE simbolo_grafico_catalogo
                    DROP CONSTRAINT simbolo_grafico_catalogo_codigo_key;
                END IF;
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_simbolo_grafico_catalogo_codigo'
                ) THEN
                    ALTER TABLE simbolo_grafico_catalogo
                    DROP CONSTRAINT uq_simbolo_grafico_catalogo_codigo;
                END IF;
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_simbolo_grafico_catalogo_legacy_id'
                ) THEN
                    ALTER TABLE simbolo_grafico_catalogo
                    ADD CONSTRAINT uq_simbolo_grafico_catalogo_legacy_id
                    UNIQUE (legacy_id);
                END IF;
            END$$;
            """
        )
    )
    conn.execute(
        text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_doenca_cid_clinica_codigo'
                ) THEN
                    ALTER TABLE doenca_cid
                    DROP CONSTRAINT uq_doenca_cid_clinica_codigo;
                END IF;
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_doenca_cid_clinica_registro'
                ) THEN
                    ALTER TABLE doenca_cid
                    ADD CONSTRAINT uq_doenca_cid_clinica_registro
                    UNIQUE (clinica_id, legacy_registro);
                END IF;
            END$$;
            """
        )
    )
    conn.execute(text("ALTER TABLE material ADD COLUMN IF NOT EXISTS unidade_compra VARCHAR"))
    conn.execute(text("ALTER TABLE material ADD COLUMN IF NOT EXISTS unidade_consumo VARCHAR"))
    conn.execute(text("ALTER TABLE material ADD COLUMN IF NOT EXISTS validade_dias INTEGER NOT NULL DEFAULT 0"))
    conn.execute(text("ALTER TABLE material ADD COLUMN IF NOT EXISTS preferido BOOLEAN NOT NULL DEFAULT FALSE"))
    conn.execute(text("ALTER TABLE material ADD COLUMN IF NOT EXISTS classificacao VARCHAR"))
    conn.execute(text("ALTER TABLE prestador_credenciamento_odonto ADD COLUMN IF NOT EXISTS aviso TEXT"))
    conn.execute(text("ALTER TABLE prestador_comissao_odonto ADD COLUMN IF NOT EXISTS especialidade_row_id INTEGER"))
    conn.execute(text("ALTER TABLE prestador_comissao_odonto ADD COLUMN IF NOT EXISTS tipo_repasse_codigo INTEGER"))
    conn.execute(text("ALTER TABLE prestador_odonto ADD COLUMN IF NOT EXISTS is_system_prestador BOOLEAN NOT NULL DEFAULT FALSE"))
    conn.execute(text("ALTER TABLE procedimento ADD COLUMN IF NOT EXISTS tabela_id INTEGER NOT NULL DEFAULT 1"))
    conn.execute(text("ALTER TABLE procedimento ADD COLUMN IF NOT EXISTS especialidade VARCHAR(20)"))
    conn.execute(text("ALTER TABLE procedimento ADD COLUMN IF NOT EXISTS procedimento_generico_id INTEGER"))
    conn.execute(text("ALTER TABLE procedimento ADD COLUMN IF NOT EXISTS simbolo_grafico VARCHAR(30)"))
    conn.execute(text("ALTER TABLE procedimento ADD COLUMN IF NOT EXISTS simbolo_grafico_legacy_id INTEGER"))
    conn.execute(text("ALTER TABLE procedimento ADD COLUMN IF NOT EXISTS mostrar_simbolo BOOLEAN NOT NULL DEFAULT FALSE"))
    conn.execute(text("ALTER TABLE procedimento ADD COLUMN IF NOT EXISTS garantia_meses INTEGER NOT NULL DEFAULT 0"))
    conn.execute(text("ALTER TABLE procedimento ADD COLUMN IF NOT EXISTS forma_cobranca VARCHAR(50)"))
    conn.execute(text("ALTER TABLE procedimento ADD COLUMN IF NOT EXISTS valor_repasse DOUBLE PRECISION NOT NULL DEFAULT 0"))
    conn.execute(text("ALTER TABLE procedimento ADD COLUMN IF NOT EXISTS preferido BOOLEAN NOT NULL DEFAULT FALSE"))
    conn.execute(text("ALTER TABLE procedimento ADD COLUMN IF NOT EXISTS inativo BOOLEAN NOT NULL DEFAULT FALSE"))
    conn.execute(text("ALTER TABLE procedimento ADD COLUMN IF NOT EXISTS observacoes TEXT"))
    conn.execute(text("ALTER TABLE procedimento ADD COLUMN IF NOT EXISTS data_inclusao VARCHAR(30)"))
    conn.execute(text("ALTER TABLE procedimento ADD COLUMN IF NOT EXISTS data_alteracao VARCHAR(30)"))
    conn.execute(text("ALTER TABLE procedimento_generico ADD COLUMN IF NOT EXISTS clinica_id INTEGER"))
    conn.execute(text("UPDATE procedimento_generico SET clinica_id = 1 WHERE clinica_id IS NULL"))
    conn.execute(text("ALTER TABLE procedimento_generico ADD COLUMN IF NOT EXISTS especialidade VARCHAR(20)"))
    conn.execute(text("ALTER TABLE procedimento_generico ADD COLUMN IF NOT EXISTS tempo INTEGER NOT NULL DEFAULT 0"))
    conn.execute(text("ALTER TABLE procedimento_generico ADD COLUMN IF NOT EXISTS custo_lab DOUBLE PRECISION NOT NULL DEFAULT 0"))
    conn.execute(text("ALTER TABLE procedimento_generico ADD COLUMN IF NOT EXISTS peso DOUBLE PRECISION NOT NULL DEFAULT 0"))
    conn.execute(text("ALTER TABLE procedimento_generico ADD COLUMN IF NOT EXISTS simbolo_grafico VARCHAR(30)"))
    conn.execute(text("ALTER TABLE procedimento_generico ADD COLUMN IF NOT EXISTS mostrar_simbolo BOOLEAN NOT NULL DEFAULT FALSE"))
    conn.execute(text("ALTER TABLE procedimento_generico ADD COLUMN IF NOT EXISTS inativo BOOLEAN NOT NULL DEFAULT FALSE"))
    conn.execute(text("ALTER TABLE procedimento_generico ADD COLUMN IF NOT EXISTS observacoes TEXT"))
    conn.execute(text("ALTER TABLE procedimento_generico ADD COLUMN IF NOT EXISTS data_inclusao VARCHAR(30)"))
    conn.execute(text("ALTER TABLE procedimento_generico ADD COLUMN IF NOT EXISTS data_alteracao VARCHAR(30)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_procedimento_generico_clinica_id ON procedimento_generico (clinica_id)"))
    conn.execute(text("ALTER TABLE procedimento_generico DROP CONSTRAINT IF EXISTS uq_procedimento_generico_codigo"))
    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_procedimento_generico_clinica_codigo ON procedimento_generico (clinica_id, codigo)"))
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS procedimento_generico_fase (
                id SERIAL PRIMARY KEY,
                procedimento_generico_id INTEGER NOT NULL REFERENCES procedimento_generico(id) ON DELETE CASCADE,
                clinica_id INTEGER NOT NULL REFERENCES clinicas(id),
                codigo VARCHAR(20),
                descricao VARCHAR(255) NOT NULL,
                sequencia INTEGER NOT NULL DEFAULT 1,
                tempo INTEGER NOT NULL DEFAULT 0
            )
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_proc_gen_fase_proc_id ON procedimento_generico_fase (procedimento_generico_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_proc_gen_fase_clinica_id ON procedimento_generico_fase (clinica_id)"))
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS procedimento_generico_material (
                id SERIAL PRIMARY KEY,
                procedimento_generico_id INTEGER NOT NULL REFERENCES procedimento_generico(id) ON DELETE CASCADE,
                material_id INTEGER NOT NULL REFERENCES material(id) ON DELETE CASCADE,
                quantidade DOUBLE PRECISION NOT NULL DEFAULT 1,
                clinica_id INTEGER NOT NULL REFERENCES clinicas(id)
            )
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_proc_gen_mat_proc_id ON procedimento_generico_material (procedimento_generico_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_proc_gen_mat_clinica_id ON procedimento_generico_material (clinica_id)"))
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS procedimento_fase (
                id SERIAL PRIMARY KEY,
                procedimento_id INTEGER NOT NULL REFERENCES procedimento(id) ON DELETE CASCADE,
                clinica_id INTEGER NOT NULL REFERENCES clinicas(id),
                codigo VARCHAR(20),
                descricao VARCHAR(255) NOT NULL,
                sequencia INTEGER NOT NULL DEFAULT 1,
                tempo INTEGER NOT NULL DEFAULT 0
            )
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_procedimento_fase_proc_id ON procedimento_fase (procedimento_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_procedimento_fase_clinica_id ON procedimento_fase (clinica_id)"))
    conn.execute(text("UPDATE procedimento SET tabela_id = 1 WHERE tabela_id IS NULL"))
    conn.execute(text("ALTER TABLE procedimento DROP CONSTRAINT IF EXISTS uq_procedimento_clinica_codigo"))
    conn.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_procedimento_clinica_tabela_codigo'
                ) THEN
                    ALTER TABLE procedimento
                    ADD CONSTRAINT uq_procedimento_clinica_tabela_codigo
                    UNIQUE (clinica_id, tabela_id, codigo);
                END IF;
            END$$;
            """
        )
    )
    conn.execute(
        text(
            "UPDATE clinicas "
            "SET nome_tabela_procedimentos = 'Tabela Exemplo' "
            "WHERE nome_tabela_procedimentos IS NULL OR btrim(nome_tabela_procedimentos) = '' OR nome_tabela_procedimentos = 'Tabela padrão'"
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS tiss_tipo_tabela (
                id INTEGER PRIMARY KEY,
                codigo VARCHAR(15) NOT NULL UNIQUE,
                nome VARCHAR(100) NOT NULL,
                descricao VARCHAR(150),
                reservado BOOLEAN NOT NULL DEFAULT TRUE,
                ativo BOOLEAN NOT NULL DEFAULT TRUE
            )
            """
        )
    )
    for item in TISS_TIPO_TABELA_PADRAO:
        conn.execute(
            text(
                """
                INSERT INTO tiss_tipo_tabela (id, codigo, nome, descricao, reservado, ativo)
                VALUES (:id, :codigo, :nome, NULL, TRUE, TRUE)
                ON CONFLICT (id) DO UPDATE SET
                    codigo = EXCLUDED.codigo,
                    nome = EXCLUDED.nome,
                    ativo = TRUE
                """
            ),
            item,
        )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS procedimento_tabela (
                id SERIAL PRIMARY KEY,
                clinica_id INTEGER NOT NULL REFERENCES clinicas(id),
                codigo INTEGER NOT NULL,
                nome VARCHAR(120) NOT NULL,
                nro_indice INTEGER NOT NULL DEFAULT 255,
                fonte_pagadora VARCHAR(20) NOT NULL DEFAULT 'particular',
                nro_credenciamento VARCHAR(30),
                inativo BOOLEAN NOT NULL DEFAULT FALSE,
                tipo_tiss_id INTEGER NOT NULL DEFAULT 1 REFERENCES tiss_tipo_tabela(id)
            )
            """
        )
    )
    conn.execute(text("ALTER TABLE procedimento_tabela ADD COLUMN IF NOT EXISTS nro_indice INTEGER NOT NULL DEFAULT 255"))
    conn.execute(text("ALTER TABLE procedimento_tabela ALTER COLUMN nro_indice SET DEFAULT 255"))
    conn.execute(text("ALTER TABLE procedimento_tabela ADD COLUMN IF NOT EXISTS fonte_pagadora VARCHAR(20) NOT NULL DEFAULT 'particular'"))
    conn.execute(text("ALTER TABLE procedimento_tabela ADD COLUMN IF NOT EXISTS nro_credenciamento VARCHAR(30)"))
    conn.execute(text("ALTER TABLE procedimento_tabela ADD COLUMN IF NOT EXISTS inativo BOOLEAN NOT NULL DEFAULT FALSE"))
    conn.execute(text("ALTER TABLE procedimento_tabela ADD COLUMN IF NOT EXISTS tipo_tiss_id INTEGER NOT NULL DEFAULT 1"))
    conn.execute(text("ALTER TABLE item_auxiliar ADD COLUMN IF NOT EXISTS ordem INTEGER"))
    conn.execute(text("ALTER TABLE item_auxiliar ADD COLUMN IF NOT EXISTS imagem_indice INTEGER"))
    conn.execute(text("ALTER TABLE item_auxiliar ADD COLUMN IF NOT EXISTS inativo BOOLEAN NOT NULL DEFAULT FALSE"))
    conn.execute(text("ALTER TABLE item_auxiliar ADD COLUMN IF NOT EXISTS cor_apresentacao VARCHAR(40)"))
    conn.execute(text("ALTER TABLE item_auxiliar ADD COLUMN IF NOT EXISTS exibir_anotacao_historico BOOLEAN NOT NULL DEFAULT FALSE"))
    conn.execute(text("ALTER TABLE item_auxiliar ADD COLUMN IF NOT EXISTS mensagem_alerta VARCHAR(255)"))
    conn.execute(text("ALTER TABLE item_auxiliar ADD COLUMN IF NOT EXISTS desativar_paciente_sistema BOOLEAN NOT NULL DEFAULT FALSE"))
    conn.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'fk_proc_tabela_tiss_tipo'
                ) THEN
                    ALTER TABLE procedimento_tabela
                    ADD CONSTRAINT fk_proc_tabela_tiss_tipo
                    FOREIGN KEY (tipo_tiss_id) REFERENCES tiss_tipo_tabela(id);
                END IF;
            END$$;
            """
        )
    )
    conn.execute(
        text(
            "UPDATE procedimento_tabela "
            "SET nro_indice = CASE WHEN nro_indice IS NULL OR nro_indice <= 0 THEN 255 ELSE nro_indice END, "
            "fonte_pagadora = CASE WHEN fonte_pagadora IS NULL OR btrim(fonte_pagadora) = '' THEN 'particular' ELSE lower(fonte_pagadora) END, "
            "inativo = COALESCE(inativo, FALSE), "
            "tipo_tiss_id = CASE WHEN tipo_tiss_id IS NULL THEN 1 ELSE tipo_tiss_id END"
        )
    )
    conn.execute(
        text(
            "UPDATE procedimento_tabela "
            "SET nro_indice = 255 "
            "WHERE fonte_pagadora = 'particular' AND nro_indice = 1"
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_procedimento_tabela_clinica_id ON procedimento_tabela (clinica_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_procedimento_tabela_codigo ON procedimento_tabela (codigo)"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS tipo_logradouro INTEGER"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS endereco VARCHAR(180)"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS numero VARCHAR(20)"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS complemento VARCHAR(120)"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS bairro VARCHAR(120)"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS cep VARCHAR(20)"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS tipo_fone1 INTEGER"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS contato1 VARCHAR(120)"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS tipo_fone2 INTEGER"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS telefone2 VARCHAR(40)"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS contato2 VARCHAR(120)"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS tipo_fone3 INTEGER"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS telefone3 VARCHAR(40)"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS contato3 VARCHAR(120)"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS tipo_fone4 INTEGER"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS telefone4 VARCHAR(40)"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS contato4 VARCHAR(120)"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS email_tecnico VARCHAR(180)"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS homepage VARCHAR(180)"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS inscricao_estadual VARCHAR(40)"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS inscricao_municipal VARCHAR(40)"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS historico_nf TEXT"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS aviso_tratamento TEXT"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS aviso_agenda TEXT"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS data_inclusao VARCHAR(30)"))
    conn.execute(text("ALTER TABLE convenio_odonto ADD COLUMN IF NOT EXISTS data_alteracao VARCHAR(30)"))
    conn.execute(text("ALTER TABLE plano_odonto ADD COLUMN IF NOT EXISTS data_inclusao VARCHAR(30)"))
    conn.execute(text("ALTER TABLE plano_odonto ADD COLUMN IF NOT EXISTS data_alteracao VARCHAR(30)"))
    conn.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_proc_tabela_clinica_codigo'
                ) THEN
                    ALTER TABLE procedimento_tabela
                    ADD CONSTRAINT uq_proc_tabela_clinica_codigo
                    UNIQUE (clinica_id, codigo);
                END IF;
            END$$;
            """
        )
    )
    PRIVATE_TABLE_CODE = 4
    PRIVATE_TABLE_NAME = "PARTICULAR"

    conn.execute(
        text(
            """
            INSERT INTO procedimento_tabela (clinica_id, codigo, nome, nro_indice, fonte_pagadora, inativo, tipo_tiss_id)
            SELECT c.id, 1, 'Tabela Exemplo', 255, 'particular', FALSE, 1
            FROM clinicas c
            WHERE NOT EXISTS (
                SELECT 1
                FROM procedimento_tabela t
                WHERE t.clinica_id = c.id
                  AND t.codigo = 1
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO procedimento_tabela (clinica_id, codigo, nome, nro_indice, fonte_pagadora, inativo, tipo_tiss_id)
            SELECT c.id, :codigo,
                CASE
                    WHEN c.nome_tabela_procedimentos IS NULL OR btrim(c.nome_tabela_procedimentos) = '' THEN :nome_padrao
                    ELSE c.nome_tabela_procedimentos
                END,
                255,
                'particular',
                FALSE,
                1
            FROM clinicas c
            WHERE EXISTS (
                SELECT 1
                FROM procedimento p
                WHERE p.clinica_id = c.id
                  AND p.tabela_id = :codigo
            )
              AND NOT EXISTS (
                SELECT 1
                FROM procedimento_tabela t
                WHERE t.clinica_id = c.id
                  AND t.codigo = :codigo
            )
            """
        ),
        {"codigo": PRIVATE_TABLE_CODE, "nome_padrao": PRIVATE_TABLE_NAME},
    )
    conn.execute(
        text(
            """
            UPDATE procedimento_tabela
            SET nome = 'Tabela Exemplo'
            WHERE codigo = 1
              AND (nome IS NULL OR btrim(nome) = '')
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE procedimento_tabela t
            SET nome = c.nome_tabela_procedimentos
            FROM clinicas c
            WHERE t.clinica_id = c.id
              AND t.codigo = :codigo
              AND c.nome_tabela_procedimentos IS NOT NULL
              AND btrim(c.nome_tabela_procedimentos) <> ''
              AND (t.nome IS NULL OR btrim(t.nome) = '')
            """
        ),
        {"codigo": PRIVATE_TABLE_CODE},
    )

def _bootstrap_dados_iniciais():
    db = SessionLocal()
    try:
        sincronizar_catalogo_modelos_storage(db)
        garantir_etiquetas_padrao_modelos(db)
        garantir_catalogo_simbolos(db)
        garantir_lista_padrao_todas_clinicas(db)
        garantir_procedimentos_padrao_todas_clinicas(db)
        separar_tabela_exemplo_particular_todas_clinicas(db)
        garantir_metadados_tabela_particular(db)
        garantir_financeiro_padrao_todas_clinicas(db)
        garantir_indices_padrao_todas_clinicas(db)
        garantir_especialidades_padrao_todas_clinicas(db)
        garantir_auxiliares_raw_todas_clinicas(db)
        garantir_cid_padrao_todas_clinicas(db)
        garantir_anamnese_padrao_todas_clinicas(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@app.on_event("startup")
def _iniciar_bootstrap():
    import os
    import threading

    if str(os.getenv("BRANA_SKIP_BOOTSTRAP", "")).strip().lower() in {"1", "true", "yes", "sim"}:
        return

    thread = threading.Thread(target=_bootstrap_dados_iniciais, daemon=True)
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
    return {"status": "Brana SaaS conectado ao banco"}
