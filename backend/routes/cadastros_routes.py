import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, object_session

from database import get_db
from models.financeiro import CategoriaFinanceira, GrupoFinanceiro, ItemAuxiliar, Lancamento
from models.material import Material
from models.paciente import Paciente
from models.procedimento import Procedimento
from models.procedimento_generico import (
    ProcedimentoGenerico,
    ProcedimentoGenericoFase,
    ProcedimentoGenericoMaterial,
)
from models.procedimento_tabela import ProcedimentoTabela
from models.simbolo_grafico import SimboloGrafico
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access
from services.procedimentos_legado_service import carregar_metadados_genericos_legado
from services.signup_service import garantir_auxiliares_raw_clinica
from services.simbolos_service import (
    carregar_codigos_catalogo_oficial,
    carregar_codigos_genericos,
    carregar_legacy_ids_catalogo_oficial,
    carregar_codigos_procedimentos,
)

router = APIRouter(prefix="/cadastros", tags=["cadastros"])
DEP_PROCEDIMENTOS = Depends(require_module_access("procedimentos"))
DEP_FINANCEIRO = Depends(require_module_access("financeiro"))
DEP_CONFIGURACAO = Depends(require_module_access("configuracao"))
PROJECT_DIR = Path(__file__).resolve().parents[3]
TAB_GEN_ITEM_PATH = PROJECT_DIR / "Dados" / "Dist" / "TAB_GEN_ITEM.raw"

AUX_TIPOS_VISIVEIS = [
    "Bairro",
    "Bancos",
    "Cidade",
    "Especialidade",
    "Estado civil",
    "Fabricantes",
    "Fase procedimento",
    "Grupo de medicamento",
    "Motivo de atestado",
    "Motivo de retorno",
    "Palavra chave",
    "Prefixo pessoais",
    "Situação do agendamento",
    "Situação do paciente",
    "Tipos de apresentação",
    "Tipos de cobrança",
    "Tipos de contato",
    "Tipos de indicação",
    "Tipos de material",
    "Tipos de pagamento",
    "Tipos de uso",
    "Tipos de usuário",
    "Unidades de medida",
]

AUX_TIPOS_OCULTOS = [
    "Índices de moeda",
    "CBO-S",
    "Símbolo gráfico",
    "Tipos de logradouro",
    "Tipos de prestador",
    "Unidade de atendimento",
]
TIPOS_PRESTADOR_PADRAO = [
    ("01", "Cirurgião dentista"),
    ("02", "Clínica odontológica"),
    ("03", "Clínica ortodôntica"),
    ("04", "Clínica radiológica"),
    ("05", "Perito"),
]

AUX_TIPO_STORAGE_ALIASES = {
    "Índices de moeda": ["Índices de moeda", "Indices de moeda"],
    "CBO-S": ["CBO-S", "CBOS", "Cbos"],
}

SIMBOLO_TIPO_MARCA_LABELS = {
    1: "Face (ex: Restauração)",
    2: "Dente (ex: Coroa)",
    3: "Grupo (ex: Prótese-fixa)",
    4: "Arcada (ex: Prótese-total)",
    5: "Geral (ex: Profilaxia)",
    6: "Segmento [ex: Bracket]",
}


class GrupoPayload(BaseModel):
    nome: str
    tipo: str


class CategoriaPayload(BaseModel):
    nome: str
    tipo: str
    grupo_id: int
    tributavel: bool = False


class MigrarCategoriaPayload(BaseModel):
    categoria_destino_id: int


class AuxPayload(BaseModel):
    tipo: str
    codigo: str
    descricao: str
    ordem: int | None = None
    imagem_indice: int | None = None
    inativo: bool = False
    cor_apresentacao: str | None = None
    exibir_anotacao_historico: bool = False
    mensagem_alerta: str | None = None
    desativar_paciente_sistema: bool = False


class SimboloPayload(BaseModel):
    descricao: str
    legacy_id: int | None = None
    codigo: str | None = None
    especialidade: int | None = None
    tipo_simbolo: int | None = None
    tipo_marca: int | None = None
    sobreposicao: int | None = None
    icone: str | None = None
    bitmap1: str | None = None
    bitmap2: str | None = None
    bitmap3: str | None = None
    imagem_custom: str | None = None


class ProcedimentoGenericoPayload(BaseModel):
    codigo: str
    descricao: str
    especialidade: str | None = None
    tempo: int = 0
    custo_lab: float = 0
    peso: float = 0.0
    simbolo_grafico: str | None = None
    mostrar_simbolo: bool = False
    inativo: bool = False
    observacoes: str | None = None
    fases: list["ProcedimentoGenericoFasePayload"] = Field(default_factory=list)
    materiais: list["ProcedimentoGenericoMaterialPayload"] = Field(default_factory=list)


class ProcedimentoGenericoFasePayload(BaseModel):
    codigo: str | None = None
    descricao: str
    sequencia: int = 1
    tempo: int = 0


class ProcedimentoGenericoMaterialPayload(BaseModel):
    material_id: int
    quantidade: float = 1.0


class PacientePayload(BaseModel):
    codigo: int | None = None
    nome: str
    sobrenome: str | None = None
    sexo: str | None = None
    data_nascimento: str | None = None
    data_cadastro: str | None = None
    status: str | None = None
    cpf: str | None = None
    rg: str | None = None
    tipo_indicacao: str | None = None
    indicado_por: str | None = None
    correspondencia: str | None = None
    endereco: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    cep: str | None = None
    uf: str | None = None
    email: str | None = None
    tipo_fone1: str | None = None
    fone1: str | None = None
    tipo_fone2: str | None = None
    fone2: str | None = None
    tipo_fone3: str | None = None
    fone3: str | None = None
    tipo_fone4: str | None = None
    fone4: str | None = None
    id_convenio: int | None = None
    id_plano: int | None = None
    cod_prontuario: str | None = None
    matricula: str | None = None
    data_validade_plano: str | None = None
    tabela_codigo: int | None = None
    cns: str | None = None
    anotacoes: str | None = None
    inativo: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)


def _norm(texto: str) -> str:
    base = (texto or "").strip().lower()
    base = unicodedata.normalize("NFD", base)
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def _aux_tipo_variantes(tipo: str) -> list[str]:
    base = str(tipo or "").strip()
    if not base:
        return []
    vistos: set[str] = set()
    variantes: list[str] = []
    for item in [base, *AUX_TIPO_STORAGE_ALIASES.get(base, [])]:
        txt = str(item or "").strip()
        if txt and txt not in vistos:
            variantes.append(txt)
            vistos.add(txt)
    return variantes


def _aux_tipo_canonico(tipo: str) -> str:
    variantes = _aux_tipo_variantes(tipo)
    return variantes[0] if variantes else ""


def _norm_codigo_procedimento_generico(codigo: str) -> str:
    base = (codigo or "").strip()
    if not base:
        return ""
    if base.isdigit():
        numero = int(base)
        if numero <= 0:
            return ""
        return f"{numero:04d}"
    return base


def _proximo_codigo_procedimento_generico(db: Session, clinica_id: int) -> str:
    max_codigo = 0
    for row in db.query(ProcedimentoGenerico.codigo).filter(ProcedimentoGenerico.clinica_id == int(clinica_id)).all():
        codigo = str(row[0] or "").strip()
        if codigo.isdigit():
            max_codigo = max(max_codigo, int(codigo))
    return f"{max_codigo + 1:04d}"


def _material_clinica_or_404(db: Session, clinica_id: int, material_id: int) -> Material:
    item = (
        db.query(Material)
        .join(Material.lista)
        .filter(
            Material.id == int(material_id),
            Material.lista.has(clinica_id=clinica_id),
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Material não encontrado para esta clínica.")
    return item


def _parse_tab_gen_item(raw_bytes: bytes) -> list[tuple[str, str]]:
    starts: list[int] = []
    total = len(raw_bytes)
    for pos in range(0, total - 12):
        registro_id = int.from_bytes(raw_bytes[pos : pos + 4], "little", signed=False)
        if not (1 <= registro_id <= 9999):
            continue
        codigo_utf16 = f"{registro_id:04d}".encode("utf-16le")
        if raw_bytes[pos + 4 : pos + 12] == codigo_utf16:
            starts.append(pos)

    registros: list[tuple[str, str]] = []
    codigos_vistos: set[str] = set()

    for idx, inicio in enumerate(starts):
        fim = starts[idx + 1] if idx + 1 < len(starts) else total
        bloco = raw_bytes[inicio:fim]
        texto = bloco[4:].decode("utf-16le", errors="ignore")

        m = re.match(r"^\s*(\d{4})\s+(.*?)\s{2,}.*$", texto, re.S)
        if m:
            codigo = m.group(1)
            descricao = m.group(2).strip()
        else:
            m2 = re.match(r"^\s*(\d{4})\s+(.*)$", texto, re.S)
            codigo = m2.group(1) if m2 else ""
            descricao = (m2.group(2) if m2 else texto).strip()

        if not codigo or not descricao or codigo in codigos_vistos:
            continue
        codigos_vistos.add(codigo)
        registros.append((codigo, descricao))

    return registros


def _procedimento_generico_to_dict(
    item: ProcedimentoGenerico,
    clinica_id: int | None = None,
    detalhado: bool = False,
) -> dict[str, Any]:
    fases_rows = list(item.fases or [])
    mats_rows = list(item.materiais_vinculados or [])
    if clinica_id:
        fases_rows = [x for x in fases_rows if int(x.clinica_id or 0) == int(clinica_id)]
        mats_rows = [x for x in mats_rows if int(x.clinica_id or 0) == int(clinica_id)]

    especialidade = str(getattr(item, "especialidade", "") or "").strip()
    data = {
        "id": int(item.id),
        "codigo": str(item.codigo or "").strip(),
        "descricao": str(item.descricao or "").strip(),
        "especialidade": especialidade,
        "tempo": int(item.tempo or 0),
        "custo_lab": float(getattr(item, "custo_lab", 0) or 0),
        "peso": float(getattr(item, "peso", 0) or 0),
        "simbolo_grafico": str(item.simbolo_grafico or "").strip(),
        "mostrar_simbolo": bool(item.mostrar_simbolo),
        "inativo": bool(getattr(item, "inativo", False)),
        "observacoes": item.observacoes or "",
        "data_inclusao": item.data_inclusao or "",
        "data_alteracao": item.data_alteracao or "",
        "total_fases": len(fases_rows),
        "total_materiais": len(mats_rows),
        "status": "Inativo" if bool(getattr(item, "inativo", False)) else "Ativo",
    }
    if not detalhado:
        return data

    fases = [
        {
            "id": int(f.id),
            "codigo": str(f.codigo or "").strip(),
            "descricao": str(f.descricao or "").strip(),
            "sequencia": int(f.sequencia or 0),
            "tempo": int(f.tempo or 0),
        }
        for f in sorted(fases_rows, key=lambda x: (int(x.sequencia or 0), int(x.id or 0)))
    ]
    materiais = []
    total_custo = 0.0
    for vinc in mats_rows:
        material = vinc.material
        custo_und = float((material.custo if material else 0) or 0)
        quantidade = float(vinc.quantidade or 0)
        custo_total = custo_und * quantidade
        total_custo += custo_total
        materiais.append(
            {
                "id": int(vinc.id),
                "material_id": int(vinc.material_id),
                "codigo": str((material.codigo if material else "") or "").strip(),
                "nome": str((material.nome if material else "") or "").strip(),
                "quantidade": quantidade,
                "relacao": float((material.relacao if material else 0) or 0),
                "preco": float((material.preco if material else 0) or 0),
                "custo_und": custo_und,
                "custo_total": custo_total,
            }
        )
    data["fases"] = fases
    data["materiais"] = materiais
    data["materiais_resumo"] = {
        "total_materiais": len(materiais),
        "total_custo": total_custo,
    }
    tabelas_por_id: dict[int, str] = {}
    db_session = object_session(item)
    if db_session is not None and clinica_id:
        tabelas_rows = (
            db_session.query(ProcedimentoTabela)
            .filter(ProcedimentoTabela.clinica_id == int(clinica_id))
            .all()
        )
        tabelas_por_id = {int(row.id): str(row.nome or "").strip() for row in tabelas_rows}

    vinculados = (
        db_session.query(Procedimento)
        .filter(
            Procedimento.procedimento_generico_id == item.id,
            Procedimento.clinica_id == int(clinica_id or 0),
        )
        .order_by(Procedimento.tabela_id.asc(), Procedimento.codigo.asc(), Procedimento.id.asc())
        .all()
        if db_session is not None
        else []
    )
    data["vinculos"] = [
        {
            "id": int(proc.id),
            "tabela_id": int(proc.tabela_id or 0),
            "tabela_nome": tabelas_por_id.get(int(proc.tabela_id or 0), ""),
            "codigo": int(proc.codigo or 0),
            "nome": str(proc.nome or "").strip(),
        }
        for proc in vinculados
    ]
    return data


def _sync_procedimento_generico_fases(
    db: Session,
    item: ProcedimentoGenerico,
    clinica_id: int,
    fases_payload: list[ProcedimentoGenericoFasePayload],
) -> None:
    (
        db.query(ProcedimentoGenericoFase)
        .filter(
            ProcedimentoGenericoFase.procedimento_generico_id == item.id,
            ProcedimentoGenericoFase.clinica_id == int(clinica_id),
        )
        .delete(synchronize_session=False)
    )
    sequencia = 1
    for fase in fases_payload or []:
        descricao = str(fase.descricao or "").strip()
        if not descricao:
            continue
        db.add(
            ProcedimentoGenericoFase(
                procedimento_generico_id=item.id,
                clinica_id=int(clinica_id),
                codigo=str(fase.codigo or "").strip() or None,
                descricao=descricao,
                sequencia=max(1, int(fase.sequencia or sequencia)),
                tempo=max(0, int(fase.tempo or 0)),
            )
        )
        sequencia += 1


def _sync_procedimento_generico_materiais(
    db: Session,
    item: ProcedimentoGenerico,
    clinica_id: int,
    materiais_payload: list[ProcedimentoGenericoMaterialPayload],
) -> None:
    (
        db.query(ProcedimentoGenericoMaterial)
        .filter(
            ProcedimentoGenericoMaterial.procedimento_generico_id == item.id,
            ProcedimentoGenericoMaterial.clinica_id == int(clinica_id),
        )
        .delete(synchronize_session=False)
    )
    for mat in materiais_payload or []:
        qtd = float(mat.quantidade or 0)
        if qtd <= 0:
            continue
        material = _material_clinica_or_404(db, int(clinica_id), int(mat.material_id))
        db.add(
            ProcedimentoGenericoMaterial(
                procedimento_generico_id=item.id,
                material_id=int(material.id),
                quantidade=qtd,
                clinica_id=int(clinica_id),
            )
        )


def _propagar_campos_generico_para_procedimentos(
    db: Session,
    clinica_id: int,
    procedimento_generico_id: int,
    tempo: int,
    custo_lab: float,
) -> None:
    (
        db.query(Procedimento)
        .filter(
            Procedimento.clinica_id == int(clinica_id),
            Procedimento.procedimento_generico_id == int(procedimento_generico_id),
        )
        .update(
            {
                "tempo": max(0, int(tempo or 0)),
                "custo_lab": float(custo_lab or 0),
            },
            synchronize_session=False,
        )
    )


def _grupo_or_404(db: Session, clinica_id: int, grupo_id: int) -> GrupoFinanceiro:
    grupo = (
        db.query(GrupoFinanceiro)
        .filter(
            GrupoFinanceiro.id == grupo_id,
            GrupoFinanceiro.clinica_id == clinica_id,
        )
        .first()
    )
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo não encontrado.")
    return grupo


def _categoria_or_404(db: Session, clinica_id: int, categoria_id: int) -> CategoriaFinanceira:
    cat = (
        db.query(CategoriaFinanceira)
        .filter(
            CategoriaFinanceira.id == categoria_id,
            CategoriaFinanceira.clinica_id == clinica_id,
        )
        .first()
    )
    if not cat:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    return cat


def _aux_or_404(db: Session, clinica_id: int, item_id: int) -> ItemAuxiliar:
    item = (
        db.query(ItemAuxiliar)
        .filter(
            ItemAuxiliar.id == item_id,
            ItemAuxiliar.clinica_id == clinica_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    return item


def _ensure_auxiliares_padrao(db: Session, clinica_id: int, tipo: str) -> None:
    tipo_canonico = _aux_tipo_canonico(tipo)
    if tipo_canonico == "Tipos de logradouro":
        qtd = (
            db.query(ItemAuxiliar)
            .filter(
                ItemAuxiliar.clinica_id == clinica_id,
                ItemAuxiliar.tipo == tipo_canonico,
            )
            .count()
        )
        if qtd == 0:
            garantir_auxiliares_raw_clinica(db, clinica_id)
            db.commit()
        return
    if tipo_canonico != "Tipos de prestador":
        return
    rows = (
        db.query(ItemAuxiliar)
        .filter(
            ItemAuxiliar.clinica_id == clinica_id,
            ItemAuxiliar.tipo == tipo_canonico,
        )
        .all()
    )
    by_codigo = {str(item.codigo or "").strip(): item for item in rows}
    changed = False
    for codigo, descricao in TIPOS_PRESTADOR_PADRAO:
        item = by_codigo.get(codigo)
        if item is None:
            db.add(
                    ItemAuxiliar(
                        clinica_id=clinica_id,
                        tipo=tipo_canonico,
                        codigo=codigo,
                        descricao=descricao,
                    )
            )
            changed = True
            continue
        if (item.descricao or "").strip() != descricao:
            item.descricao = descricao
            changed = True
    if changed:
        db.commit()


def _clean_text(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _clean_date(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", text)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return text


def _clean_int(value: int | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _merge_extra_payload(paciente: Paciente, extra: dict[str, Any] | None) -> dict[str, Any] | None:
    base = dict(paciente.source_payload or {})
    if not isinstance(extra, dict):
        return base or None
    for key, val in extra.items():
        k = str(key or "").strip()
        if not k:
            continue
        if val is None:
            base.pop(k, None)
            continue
        if isinstance(val, str):
            base[k] = val.strip()
        else:
            base[k] = val
    return base or None


@router.get("/simbolos-graficos", dependencies=[DEP_PROCEDIMENTOS])
def listar_simbolos_graficos(
    q: str = Query(default=""),
    scope: str = Query(default="catalogo"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = current_user.clinica_id
    termo = _norm(q)
    scope_norm = (scope or "").strip().lower()
    legacy_catalogo: set[int] = set()
    catalogo: set[str] = set()
    if scope_norm in {"biblioteca", "todos", "amplo"}:
        pass
    elif scope_norm == "genericos":
        catalogo = carregar_codigos_genericos() or carregar_codigos_catalogo_oficial()
    elif scope_norm == "procedimentos":
        catalogo = carregar_codigos_procedimentos() or carregar_codigos_catalogo_oficial()
    else:
        legacy_catalogo = carregar_legacy_ids_catalogo_oficial()
    rows = (
        db.query(SimboloGrafico)
        .filter(SimboloGrafico.ativo.is_(True))
        .order_by(SimboloGrafico.descricao.asc(), SimboloGrafico.codigo.asc(), SimboloGrafico.id.asc())
        .all()
    )

    itens: list[dict[str, Any]] = []
    vistos_codigo: set[str] = set()
    for row in rows:
        codigo = str(row.codigo or "").strip()
        descricao = str(row.descricao or "").strip()
        if not codigo or not descricao:
            continue
        if scope_norm == "catalogo":
            legacy_id = int(getattr(row, "legacy_id", 0) or 0)
            if legacy_catalogo and legacy_id not in legacy_catalogo and int(row.tipo_simbolo or 2) == 1:
                continue
        else:
            if catalogo and codigo.lower() not in catalogo:
                continue
            if scope_norm == "genericos":
                codigo_key = codigo.lower()
                if codigo_key in vistos_codigo:
                    continue
                vistos_codigo.add(codigo_key)
        if termo and termo not in _norm(f"{codigo} {descricao}"):
            continue
        imagem_custom = str(getattr(row, "imagem_custom", "") or "").strip()
        imagem = str(row.icone or row.bitmap1 or row.bitmap2 or row.bitmap3 or "").strip()
        itens.append(
            {
                "id": int(row.id),
                "legacy_id": int(getattr(row, "legacy_id", 0) or 0) or None,
                "codigo": codigo,
                "descricao": descricao,
                "especialidade": row.especialidade,
                "tipo_marca": row.tipo_marca,
                "tipo_marca_label": SIMBOLO_TIPO_MARCA_LABELS.get(int(row.tipo_marca or 0)),
                "tipo_simbolo": 1 if _simbolo_eh_oficial(row) else int(row.tipo_simbolo or 2),
                "icone": imagem,
                "imagem_custom": imagem_custom or None,
                "imagem_url": imagem_custom or (f"/desktop-assets/easy/{imagem}" if imagem else ""),
            }
        )
    return itens


def _simbolo_or_404(db: Session, simbolo_id: int) -> SimboloGrafico:
    item = db.query(SimboloGrafico).filter(SimboloGrafico.id == simbolo_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Simbolo grafico nao encontrado.")
    return item


def _simbolo_eh_oficial(item: SimboloGrafico) -> bool:
    legacy_id = int(getattr(item, "legacy_id", 0) or 0)
    if legacy_id <= 0:
        return False
    legacy_catalogo = carregar_legacy_ids_catalogo_oficial()
    return not legacy_catalogo or legacy_id in legacy_catalogo


def _simbolo_nome_ativo_existe(db: Session, descricao: str, exclude_id: int | None = None) -> bool:
    query = db.query(SimboloGrafico.id).filter(
        func.lower(SimboloGrafico.descricao) == descricao.lower(),
        SimboloGrafico.ativo.is_(True),
    )
    if exclude_id:
        query = query.filter(SimboloGrafico.id != int(exclude_id))
    return query.first() is not None


@router.post("/simbolos-graficos", dependencies=[DEP_PROCEDIMENTOS])
def criar_simbolo_grafico(
    payload: SimboloPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    descricao = str(payload.descricao or "").strip()
    codigo = str(payload.codigo or payload.icone or payload.bitmap1 or "").strip()
    if not descricao:
        raise HTTPException(status_code=400, detail="Informe o nome do simbolo.")
    if not codigo:
        raise HTTPException(status_code=400, detail="Informe o codigo do simbolo.")
    if descricao.lower() == codigo.lower() or descricao.lower().endswith(".bmp"):
        raise HTTPException(status_code=400, detail="Informe um nome proprio para o simbolo, diferente do arquivo base.")
    if int(payload.legacy_id or 0) > 0:
        raise HTTPException(status_code=400, detail="Simbolos oficiais do sistema nao podem ser recriados manualmente.")
    if _simbolo_nome_ativo_existe(db, descricao):
        raise HTTPException(status_code=400, detail="Ja existe simbolo com este nome.")
    existe = (
        db.query(SimboloGrafico.id)
        .filter(
            func.lower(SimboloGrafico.codigo) == codigo.lower(),
            func.lower(SimboloGrafico.descricao) == descricao.lower(),
            SimboloGrafico.ativo.is_(True),
        )
        .first()
    )
    if existe:
        raise HTTPException(status_code=400, detail="Ja existe simbolo com este nome usando este bitmap.")
    item = SimboloGrafico(
        legacy_id=None,
        codigo=codigo,
        descricao=descricao[:120],
        especialidade=payload.especialidade,
        tipo_simbolo=2,
        tipo_marca=payload.tipo_marca,
        sobreposicao=payload.sobreposicao,
        icone=str(payload.icone or codigo).strip() or None,
        bitmap1=str(payload.bitmap1 or codigo).strip() or None,
        bitmap2=str(payload.bitmap2 or "").strip() or None,
        bitmap3=str(payload.bitmap3 or "").strip() or None,
        imagem_custom=str(payload.imagem_custom or "").strip() or None,
        ativo=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": int(item.id), "codigo": item.codigo, "descricao": item.descricao}


@router.put("/simbolos-graficos/{simbolo_id}", dependencies=[DEP_PROCEDIMENTOS])
def atualizar_simbolo_grafico(
    simbolo_id: int,
    payload: SimboloPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _simbolo_or_404(db, simbolo_id)
    descricao = str(payload.descricao or "").strip()
    if not descricao:
        raise HTTPException(status_code=400, detail="Informe o nome do simbolo.")
    if _simbolo_eh_oficial(item):
        raise HTTPException(status_code=409, detail="Simbolos de sistema nao podem ser sobrescritos.")
    if _simbolo_nome_ativo_existe(db, descricao, exclude_id=item.id):
        raise HTTPException(status_code=400, detail="Ja existe simbolo com este nome.")
    novo_codigo = str(payload.codigo or item.codigo or "").strip()
    if not novo_codigo:
        raise HTTPException(status_code=400, detail="Informe o codigo do simbolo.")
    if descricao.lower() == novo_codigo.lower() or descricao.lower().endswith(".bmp"):
        raise HTTPException(status_code=400, detail="Informe um nome proprio para o simbolo, diferente do arquivo base.")
    existe = (
        db.query(SimboloGrafico.id)
        .filter(
            SimboloGrafico.id != item.id,
            func.lower(SimboloGrafico.codigo) == novo_codigo.lower(),
            func.lower(SimboloGrafico.descricao) == descricao.lower(),
            SimboloGrafico.ativo.is_(True),
        )
        .first()
    )
    if existe:
        raise HTTPException(status_code=400, detail="Ja existe simbolo com este nome usando este bitmap.")
    item.codigo = novo_codigo
    item.descricao = descricao[:120]
    item.especialidade = payload.especialidade
    if payload.tipo_simbolo is not None:
        item.tipo_simbolo = 2
    if payload.tipo_marca is not None:
        item.tipo_marca = payload.tipo_marca
    if payload.sobreposicao is not None:
        item.sobreposicao = payload.sobreposicao
    if payload.icone is not None:
        item.icone = str(payload.icone or "").strip() or None
    if payload.bitmap1 is not None:
        item.bitmap1 = str(payload.bitmap1 or "").strip() or None
    if payload.bitmap2 is not None:
        item.bitmap2 = str(payload.bitmap2 or "").strip() or None
    if payload.bitmap3 is not None:
        item.bitmap3 = str(payload.bitmap3 or "").strip() or None
    if payload.imagem_custom is not None:
        item.imagem_custom = str(payload.imagem_custom or "").strip() or None
    db.commit()
    return {"detail": "Simbolo atualizado.", "id": int(item.id), "codigo": item.codigo, "descricao": item.descricao}


@router.delete("/simbolos-graficos/{simbolo_id}", dependencies=[DEP_PROCEDIMENTOS])
def excluir_simbolo_grafico(
    simbolo_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _simbolo_or_404(db, simbolo_id)
    if _simbolo_eh_oficial(item) or int(item.tipo_simbolo or 0) == 1:
        raise HTTPException(status_code=409, detail="Simbolos de sistema nao podem ser excluidos.")
    db.delete(item)
    db.commit()
    return {"detail": "Simbolo excluido."}


def _proximo_codigo_paciente(db: Session, clinica_id: int) -> int:
    max_codigo = (
        db.query(func.max(Paciente.codigo))
        .filter(Paciente.clinica_id == clinica_id)
        .scalar()
    )
    return int(max_codigo or 0) + 1


def _paciente_or_404(db: Session, clinica_id: int, paciente_id: int) -> Paciente:
    item = (
        db.query(Paciente)
        .filter(
            Paciente.id == paciente_id,
            Paciente.clinica_id == clinica_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")
    return item


def _paciente_to_dict(p: Paciente) -> dict[str, Any]:
    return {
        "id": p.id,
        "codigo": p.codigo,
        "nome": p.nome or "",
        "sobrenome": p.sobrenome or "",
        "nome_completo": p.nome_completo or "",
        "sexo": p.sexo or "",
        "data_nascimento": p.data_nascimento or "",
        "data_cadastro": p.data_cadastro or "",
        "status": p.status or "",
        "cpf": p.cpf or "",
        "rg": p.rg or "",
        "tipo_indicacao": p.tipo_indicacao or "",
        "indicado_por": p.indicado_por or "",
        "correspondencia": p.correspondencia or "",
        "endereco": p.endereco or "",
        "complemento": p.complemento or "",
        "bairro": p.bairro or "",
        "cidade": p.cidade or "",
        "cep": p.cep or "",
        "uf": p.uf or "",
        "email": p.email or "",
        "tipo_fone1": p.tipo_fone1 or "",
        "fone1": p.fone1 or "",
        "tipo_fone2": p.tipo_fone2 or "",
        "fone2": p.fone2 or "",
        "tipo_fone3": p.tipo_fone3 or "",
        "fone3": p.fone3 or "",
        "tipo_fone4": p.tipo_fone4 or "",
        "fone4": p.fone4 or "",
        "id_convenio": p.id_convenio,
        "id_plano": p.id_plano,
        "cod_prontuario": p.cod_prontuario or "",
        "matricula": p.matricula or "",
        "data_validade_plano": p.data_validade_plano or "",
        "tabela_codigo": p.tabela_codigo,
        "cns": p.cns or "",
        "anotacoes": p.anotacoes or "",
        "inativo": bool(p.inativo),
        "extra": dict(p.source_payload or {}),
        "criado_em": p.criado_em.isoformat() if p.criado_em else None,
        "atualizado_em": p.atualizado_em.isoformat() if p.atualizado_em else None,
    }


def _apply_paciente_payload(p: Paciente, payload: PacientePayload) -> None:
    nome = (payload.nome or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome do paciente.")

    sobrenome = _clean_text(payload.sobrenome)

    p.nome = nome
    p.sobrenome = sobrenome
    p.nome_completo = " ".join(x for x in [nome, sobrenome or ""] if x).strip() or nome
    p.sexo = _clean_text(payload.sexo)
    p.data_nascimento = _clean_date(payload.data_nascimento)
    p.data_cadastro = _clean_date(payload.data_cadastro)
    p.status = _clean_text(payload.status)
    p.cpf = _clean_text(payload.cpf)
    p.rg = _clean_text(payload.rg)
    p.tipo_indicacao = _clean_text(payload.tipo_indicacao)
    p.indicado_por = _clean_text(payload.indicado_por)
    p.correspondencia = _clean_text(payload.correspondencia)
    p.endereco = _clean_text(payload.endereco)
    p.complemento = _clean_text(payload.complemento)
    p.bairro = _clean_text(payload.bairro)
    p.cidade = _clean_text(payload.cidade)
    p.cep = _clean_text(payload.cep)
    p.uf = _clean_text(payload.uf)
    p.email = _clean_text(payload.email)
    p.tipo_fone1 = _clean_text(payload.tipo_fone1)
    p.fone1 = _clean_text(payload.fone1)
    p.tipo_fone2 = _clean_text(payload.tipo_fone2)
    p.fone2 = _clean_text(payload.fone2)
    p.tipo_fone3 = _clean_text(payload.tipo_fone3)
    p.fone3 = _clean_text(payload.fone3)
    p.tipo_fone4 = _clean_text(payload.tipo_fone4)
    p.fone4 = _clean_text(payload.fone4)
    p.id_convenio = _clean_int(payload.id_convenio)
    p.id_plano = _clean_int(payload.id_plano)
    p.cod_prontuario = _clean_text(payload.cod_prontuario)
    p.matricula = _clean_text(payload.matricula)
    p.data_validade_plano = _clean_date(payload.data_validade_plano)
    p.tabela_codigo = _clean_int(payload.tabela_codigo)
    p.cns = _clean_text(payload.cns)
    p.anotacoes = _clean_text(payload.anotacoes)
    p.inativo = bool(payload.inativo)
    p.source_payload = _merge_extra_payload(p, payload.extra)


@router.get("/grupos", dependencies=[DEP_FINANCEIRO])
def listar_grupos(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    grupos = (
        db.query(GrupoFinanceiro)
        .filter(GrupoFinanceiro.clinica_id == current_user.clinica_id)
        .order_by(GrupoFinanceiro.nome.asc())
        .all()
    )
    out = []
    for g in grupos:
        categorias = (
            db.query(CategoriaFinanceira)
            .filter(
                CategoriaFinanceira.clinica_id == current_user.clinica_id,
                CategoriaFinanceira.grupo_id == g.id,
            )
            .order_by(CategoriaFinanceira.nome.asc())
            .all()
        )
        out.append(
            {
                "id": g.id,
                "nome": g.nome,
                "tipo": g.tipo,
                "categorias": [
                    {
                        "id": c.id,
                        "nome": c.nome,
                        "tipo": c.tipo,
                        "tributavel": bool(c.tributavel),
                        "grupo_id": c.grupo_id,
                    }
                    for c in categorias
                ],
            }
        )
    return out


@router.post("/grupos", dependencies=[DEP_FINANCEIRO])
def criar_grupo(
    payload: GrupoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nome = (payload.nome or "").strip()
    tipo = (payload.tipo or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome do grupo.")
    existe = (
        db.query(GrupoFinanceiro.id)
        .filter(
            GrupoFinanceiro.clinica_id == current_user.clinica_id,
            GrupoFinanceiro.nome == nome,
        )
        .first()
    )
    if existe:
        raise HTTPException(status_code=400, detail="Já existe um grupo com este nome.")
    g = GrupoFinanceiro(clinica_id=current_user.clinica_id, nome=nome, tipo=tipo)
    db.add(g)
    db.commit()
    db.refresh(g)
    return {"id": g.id, "nome": g.nome, "tipo": g.tipo, "categorias": []}


@router.put("/grupos/{grupo_id}", dependencies=[DEP_FINANCEIRO])
def editar_grupo(
    grupo_id: int,
    payload: GrupoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    grupo = _grupo_or_404(db, current_user.clinica_id, grupo_id)
    nome = (payload.nome or "").strip()
    tipo = (payload.tipo or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome do grupo.")
    existe = (
        db.query(GrupoFinanceiro.id)
        .filter(
            GrupoFinanceiro.clinica_id == current_user.clinica_id,
            GrupoFinanceiro.nome == nome,
            GrupoFinanceiro.id != grupo.id,
        )
        .first()
    )
    if existe:
        raise HTTPException(status_code=400, detail="Já existe um grupo com este nome.")
    grupo.nome = nome
    grupo.tipo = tipo
    db.commit()
    return {"detail": "Grupo atualizado."}


@router.delete("/grupos/{grupo_id}", dependencies=[DEP_FINANCEIRO])
def excluir_grupo(
    grupo_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    grupo = _grupo_or_404(db, current_user.clinica_id, grupo_id)
    qtd_cat = (
        db.query(CategoriaFinanceira.id)
        .filter(
            CategoriaFinanceira.clinica_id == current_user.clinica_id,
            CategoriaFinanceira.grupo_id == grupo.id,
        )
        .count()
    )
    if qtd_cat > 0:
        raise HTTPException(status_code=400, detail="Este grupo possui categorias vinculadas.")
    db.delete(grupo)
    db.commit()
    return {"detail": "Grupo excluído."}


@router.post("/categorias", dependencies=[DEP_FINANCEIRO])
def criar_categoria(
    payload: CategoriaPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nome = (payload.nome or "").strip()
    tipo = (payload.tipo or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome da categoria.")
    _grupo_or_404(db, current_user.clinica_id, int(payload.grupo_id))
    existe = (
        db.query(CategoriaFinanceira.id)
        .filter(
            CategoriaFinanceira.clinica_id == current_user.clinica_id,
            CategoriaFinanceira.grupo_id == int(payload.grupo_id),
            CategoriaFinanceira.nome == nome,
        )
        .first()
    )
    if existe:
        raise HTTPException(status_code=400, detail="Categoria já existe neste grupo.")
    c = CategoriaFinanceira(
        clinica_id=current_user.clinica_id,
        nome=nome,
        tipo=tipo,
        grupo_id=int(payload.grupo_id),
        tributavel=bool(payload.tributavel),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return {
        "id": c.id,
        "nome": c.nome,
        "tipo": c.tipo,
        "tributavel": bool(c.tributavel),
        "grupo_id": c.grupo_id,
    }


@router.put("/categorias/{categoria_id}", dependencies=[DEP_FINANCEIRO])
def editar_categoria(
    categoria_id: int,
    payload: CategoriaPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cat = _categoria_or_404(db, current_user.clinica_id, categoria_id)
    _grupo_or_404(db, current_user.clinica_id, int(payload.grupo_id))
    nome = (payload.nome or "").strip()
    tipo = (payload.tipo or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome da categoria.")
    existe = (
        db.query(CategoriaFinanceira.id)
        .filter(
            CategoriaFinanceira.clinica_id == current_user.clinica_id,
            CategoriaFinanceira.grupo_id == int(payload.grupo_id),
            CategoriaFinanceira.nome == nome,
            CategoriaFinanceira.id != cat.id,
        )
        .first()
    )
    if existe:
        raise HTTPException(status_code=400, detail="Já existe outra categoria com este nome.")
    cat.nome = nome
    cat.tipo = tipo
    cat.grupo_id = int(payload.grupo_id)
    cat.tributavel = bool(payload.tributavel)
    db.commit()
    return {"detail": "Categoria atualizada."}


@router.get("/categorias/{categoria_id}/em-uso", dependencies=[DEP_FINANCEIRO])
def categoria_em_uso(
    categoria_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _categoria_or_404(db, current_user.clinica_id, categoria_id)
    em_uso = (
        db.query(Lancamento.id)
        .filter(
            Lancamento.clinica_id == current_user.clinica_id,
            Lancamento.categoria_id == categoria_id,
        )
        .first()
        is not None
    )
    return {"em_uso": em_uso}


@router.delete("/categorias/{categoria_id}", dependencies=[DEP_FINANCEIRO])
def excluir_categoria(
    categoria_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cat = _categoria_or_404(db, current_user.clinica_id, categoria_id)
    em_uso = (
        db.query(Lancamento.id)
        .filter(
            Lancamento.clinica_id == current_user.clinica_id,
            Lancamento.categoria_id == categoria_id,
        )
        .first()
        is not None
    )
    if em_uso:
        raise HTTPException(status_code=409, detail="Categoria em uso por lançamentos.")
    db.delete(cat)
    db.commit()
    return {"detail": "Categoria excluída."}


@router.post("/categorias/{categoria_id}/migrar-e-excluir", dependencies=[DEP_FINANCEIRO])
def migrar_e_excluir_categoria(
    categoria_id: int,
    payload: MigrarCategoriaPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    origem = _categoria_or_404(db, current_user.clinica_id, categoria_id)
    destino = _categoria_or_404(db, current_user.clinica_id, int(payload.categoria_destino_id))
    if origem.id == destino.id:
        raise HTTPException(status_code=400, detail="Selecione uma categoria destino diferente.")

    (
        db.query(Lancamento)
        .filter(
            Lancamento.clinica_id == current_user.clinica_id,
            Lancamento.categoria_id == origem.id,
        )
        .update({"categoria_id": destino.id}, synchronize_session=False)
    )
    db.delete(origem)
    db.commit()
    return {"detail": "Categoria migrada e excluída."}


@router.get("/auxiliares/tipos", dependencies=[DEP_CONFIGURACAO])
def listar_tipos_auxiliares():
    return AUX_TIPOS_VISIVEIS


@router.get("/auxiliares", dependencies=[DEP_CONFIGURACAO])
def listar_auxiliares(
    tipo: str = Query(default=""),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_auxiliares_padrao(db, current_user.clinica_id, tipo)
    query = db.query(ItemAuxiliar).filter(ItemAuxiliar.clinica_id == current_user.clinica_id)
    if (tipo or "").strip():
        variantes = _aux_tipo_variantes(tipo)
        if variantes:
            query = query.filter(ItemAuxiliar.tipo.in_(variantes))
    itens = query.order_by(ItemAuxiliar.codigo.asc()).all()
    return [
        {
            "id": x.id,
            "tipo": x.tipo,
            "codigo": x.codigo,
            "descricao": x.descricao,
            "ordem": x.ordem,
            "imagem_indice": x.imagem_indice,
            "inativo": bool(getattr(x, "inativo", False)),
            "cor_apresentacao": x.cor_apresentacao or "",
            "exibir_anotacao_historico": bool(getattr(x, "exibir_anotacao_historico", False)),
            "mensagem_alerta": x.mensagem_alerta or "",
            "desativar_paciente_sistema": bool(getattr(x, "desativar_paciente_sistema", False)),
        }
        for x in itens
    ]


@router.get("/auxiliares/especialidades-ativas", dependencies=[DEP_CONFIGURACAO])
def listar_especialidades_ativas(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_auxiliares_padrao(db, current_user.clinica_id, "Especialidade")
    itens = (
        db.query(ItemAuxiliar)
        .filter(
            ItemAuxiliar.clinica_id == current_user.clinica_id,
            ItemAuxiliar.tipo.in_(_aux_tipo_variantes("Especialidade")),
            or_(ItemAuxiliar.inativo.is_(False), ItemAuxiliar.inativo.is_(None)),
        )
        .order_by(
            func.coalesce(ItemAuxiliar.ordem, 999999).asc(),
            ItemAuxiliar.descricao.asc(),
            ItemAuxiliar.id.asc(),
        )
        .all()
    )
    return [
        {
            "id": int(item.id),
            "codigo": str(item.codigo or "").strip(),
            "nome": str(item.descricao or "").strip(),
            "ordem": int(item.ordem or 0) if item.ordem is not None else None,
            "imagem_indice": int(item.imagem_indice or 0) if item.imagem_indice is not None else None,
        }
        for item in itens
        if str(item.descricao or "").strip()
    ]


@router.post("/auxiliares", dependencies=[DEP_CONFIGURACAO])
def criar_auxiliar(
    payload: AuxPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tipo = _aux_tipo_canonico(payload.tipo)
    codigo = (payload.codigo or "").strip()
    descricao = (payload.descricao or "").strip()
    if not tipo or not codigo or not descricao:
        raise HTTPException(status_code=400, detail="Informe tipo, código e descrição.")
    existe = (
        db.query(ItemAuxiliar.id)
        .filter(
            ItemAuxiliar.clinica_id == current_user.clinica_id,
            ItemAuxiliar.tipo.in_(_aux_tipo_variantes(tipo)),
            ItemAuxiliar.codigo == codigo,
        )
        .first()
    )
    if existe:
        raise HTTPException(status_code=400, detail="Já existe um item com este código.")
    item = ItemAuxiliar(
        clinica_id=current_user.clinica_id,
        tipo=tipo,
        codigo=codigo,
        descricao=descricao,
        ordem=payload.ordem,
        imagem_indice=payload.imagem_indice,
        inativo=bool(payload.inativo),
        cor_apresentacao=(payload.cor_apresentacao or "").strip() or None,
        exibir_anotacao_historico=bool(payload.exibir_anotacao_historico),
        mensagem_alerta=(payload.mensagem_alerta or "").strip() or None,
        desativar_paciente_sistema=bool(payload.desativar_paciente_sistema),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "tipo": item.tipo,
        "codigo": item.codigo,
        "descricao": item.descricao,
        "ordem": item.ordem,
        "imagem_indice": item.imagem_indice,
        "inativo": bool(item.inativo),
        "cor_apresentacao": item.cor_apresentacao or "",
        "exibir_anotacao_historico": bool(item.exibir_anotacao_historico),
        "mensagem_alerta": item.mensagem_alerta or "",
        "desativar_paciente_sistema": bool(item.desativar_paciente_sistema),
    }


@router.put("/auxiliares/{item_id}", dependencies=[DEP_CONFIGURACAO])
def editar_auxiliar(
    item_id: int,
    payload: AuxPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _aux_or_404(db, current_user.clinica_id, item_id)
    tipo = _aux_tipo_canonico(payload.tipo)
    codigo = (payload.codigo or "").strip()
    descricao = (payload.descricao or "").strip()
    if not tipo or not codigo or not descricao:
        raise HTTPException(status_code=400, detail="Informe tipo, código e descrição.")
    existe = (
        db.query(ItemAuxiliar.id)
        .filter(
            ItemAuxiliar.clinica_id == current_user.clinica_id,
            ItemAuxiliar.tipo.in_(_aux_tipo_variantes(tipo)),
            ItemAuxiliar.codigo == codigo,
            ItemAuxiliar.id != item.id,
        )
        .first()
    )
    if existe:
        raise HTTPException(status_code=400, detail="Já existe um item com este código.")
    item.tipo = tipo
    item.codigo = codigo
    item.descricao = descricao
    item.ordem = payload.ordem
    item.imagem_indice = payload.imagem_indice
    item.inativo = bool(payload.inativo)
    item.cor_apresentacao = (payload.cor_apresentacao or "").strip() or None
    item.exibir_anotacao_historico = bool(payload.exibir_anotacao_historico)
    item.mensagem_alerta = (payload.mensagem_alerta or "").strip() or None
    item.desativar_paciente_sistema = bool(payload.desativar_paciente_sistema)
    db.commit()
    return {"detail": "Item atualizado."}


@router.delete("/auxiliares/{item_id}", dependencies=[DEP_CONFIGURACAO])
def excluir_auxiliar(
    item_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _aux_or_404(db, current_user.clinica_id, item_id)
    db.delete(item)
    db.commit()
    return {"detail": "Item excluído."}


@router.get("/pacientes", dependencies=[DEP_PROCEDIMENTOS])
def listar_pacientes(
    q: str = Query(default=""),
    limit: int = Query(default=80),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    termo = (q or "").strip()
    limite = max(1, min(int(limit or 80), 5000))

    query = db.query(Paciente).filter(Paciente.clinica_id == current_user.clinica_id)
    if termo:
        like = f"%{termo}%"
        filtros = [
            Paciente.nome.ilike(like),
            Paciente.sobrenome.ilike(like),
            Paciente.nome_completo.ilike(like),
            Paciente.cpf.ilike(like),
            Paciente.fone1.ilike(like),
            Paciente.fone2.ilike(like),
            Paciente.fone3.ilike(like),
            Paciente.fone4.ilike(like),
            Paciente.cidade.ilike(like),
        ]
        if termo.isdigit():
            filtros.append(Paciente.codigo == int(termo))
        query = query.filter(or_(*filtros))

    itens = query.order_by(Paciente.codigo.asc(), Paciente.id.asc()).limit(limite).all()
    return [
        {
            "id": x.id,
            "codigo": x.codigo,
            "nome": x.nome or "",
            "sobrenome": x.sobrenome or "",
            "nome_completo": x.nome_completo or "",
            "cpf": x.cpf or "",
            "fone1": x.fone1 or "",
            "cidade": x.cidade or "",
            "status": x.status or "",
            "inativo": bool(x.inativo),
        }
        for x in itens
    ]


@router.get("/pacientes/proximo-codigo", dependencies=[DEP_PROCEDIMENTOS])
def proximo_codigo_paciente(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"codigo": _proximo_codigo_paciente(db, current_user.clinica_id)}


@router.get("/pacientes/navegar", dependencies=[DEP_PROCEDIMENTOS])
def navegar_pacientes(
    atual_id: int | None = Query(default=None),
    sentido: str = Query(default="first"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base = db.query(Paciente).filter(Paciente.clinica_id == current_user.clinica_id)
    sentido_norm = (sentido or "").strip().lower()
    if sentido_norm not in {"first", "prev", "next", "last"}:
        raise HTTPException(status_code=400, detail="Sentido inválido. Use: first, prev, next ou last.")

    if sentido_norm == "first":
        item = base.order_by(Paciente.codigo.asc(), Paciente.id.asc()).first()
        return _paciente_to_dict(item) if item else None

    if sentido_norm == "last":
        item = base.order_by(Paciente.codigo.desc(), Paciente.id.desc()).first()
        return _paciente_to_dict(item) if item else None

    atual = _paciente_or_404(db, current_user.clinica_id, int(atual_id)) if atual_id else None
    if not atual:
        fallback = base.order_by(Paciente.codigo.asc(), Paciente.id.asc()).first()
        return _paciente_to_dict(fallback) if fallback else None

    if sentido_norm == "prev":
        item = (
            base.filter(
                or_(
                    Paciente.codigo < atual.codigo,
                    and_(Paciente.codigo == atual.codigo, Paciente.id < atual.id),
                )
            )
            .order_by(Paciente.codigo.desc(), Paciente.id.desc())
            .first()
        )
        return _paciente_to_dict(item or atual)

    item = (
        base.filter(
            or_(
                Paciente.codigo > atual.codigo,
                and_(Paciente.codigo == atual.codigo, Paciente.id > atual.id),
            )
        )
        .order_by(Paciente.codigo.asc(), Paciente.id.asc())
        .first()
    )
    return _paciente_to_dict(item or atual)


@router.get("/pacientes/por-codigo/{codigo}", dependencies=[DEP_PROCEDIMENTOS])
def obter_paciente_por_codigo(
    codigo: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(Paciente)
        .filter(
            Paciente.clinica_id == current_user.clinica_id,
            Paciente.codigo == codigo,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")
    return _paciente_to_dict(item)


@router.get("/pacientes/{paciente_id}", dependencies=[DEP_PROCEDIMENTOS])
def obter_paciente(
    paciente_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _paciente_or_404(db, current_user.clinica_id, paciente_id)
    return _paciente_to_dict(item)


@router.post("/pacientes", dependencies=[DEP_PROCEDIMENTOS])
def criar_paciente(
    payload: PacientePayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    codigo = int(payload.codigo or _proximo_codigo_paciente(db, current_user.clinica_id))
    if codigo <= 0:
        raise HTTPException(status_code=400, detail="Código inválido.")

    existe = (
        db.query(Paciente.id)
        .filter(
            Paciente.clinica_id == current_user.clinica_id,
            Paciente.codigo == codigo,
        )
        .first()
    )
    if existe:
        raise HTTPException(status_code=400, detail="Já existe paciente com este código.")

    item = Paciente(
        clinica_id=current_user.clinica_id,
        codigo=codigo,
        nome="TEMP",
    )
    _apply_paciente_payload(item, payload)
    if not item.data_cadastro:
        item.data_cadastro = date.today().isoformat()

    db.add(item)
    db.commit()
    db.refresh(item)
    return _paciente_to_dict(item)


@router.put("/pacientes/{paciente_id}", dependencies=[DEP_PROCEDIMENTOS])
def editar_paciente(
    paciente_id: int,
    payload: PacientePayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _paciente_or_404(db, current_user.clinica_id, paciente_id)

    novo_codigo = int(payload.codigo or item.codigo)
    if novo_codigo <= 0:
        raise HTTPException(status_code=400, detail="Código inválido.")
    if novo_codigo != item.codigo:
        existe = (
            db.query(Paciente.id)
            .filter(
                Paciente.clinica_id == current_user.clinica_id,
                Paciente.codigo == novo_codigo,
                Paciente.id != item.id,
            )
            .first()
        )
        if existe:
            raise HTTPException(status_code=400, detail="Já existe paciente com este código.")
        item.codigo = novo_codigo

    _apply_paciente_payload(item, payload)
    db.commit()
    db.refresh(item)
    return _paciente_to_dict(item)


@router.delete("/pacientes/{paciente_id}", dependencies=[DEP_PROCEDIMENTOS])
def excluir_paciente(
    paciente_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _paciente_or_404(db, current_user.clinica_id, paciente_id)
    db.delete(item)
    db.commit()
    return {"detail": "Paciente excluído."}


@router.get("/procedimentos-genericos", dependencies=[DEP_PROCEDIMENTOS])
def listar_procedimentos_genericos(
    q: str = Query(default=""),
    especialidade: str = Query(default=""),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = current_user.clinica_id
    termo = (q or "").strip()
    esp = str(especialidade or "").strip()
    query = db.query(ProcedimentoGenerico).filter(ProcedimentoGenerico.clinica_id == clinica_id)
    if termo:
        like = f"%{termo}%"
        query = query.filter(
            or_(
                ProcedimentoGenerico.codigo.ilike(like),
                ProcedimentoGenerico.descricao.ilike(like),
            )
        )
    if esp:
        query = query.filter(ProcedimentoGenerico.especialidade == esp)
    itens = query.order_by(ProcedimentoGenerico.codigo.asc(), ProcedimentoGenerico.id.asc()).all()
    return [_procedimento_generico_to_dict(x, clinica_id=clinica_id, detalhado=False) for x in itens]


@router.get("/procedimentos-genericos/_legacy/{item_id}", dependencies=[DEP_PROCEDIMENTOS])
def detalhar_procedimento_generico(
    item_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(ProcedimentoGenerico)
        .filter(
            ProcedimentoGenerico.id == item_id,
            ProcedimentoGenerico.clinica_id == current_user.clinica_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Procedimento genérico não encontrado.")
    return _procedimento_generico_to_dict(item, clinica_id=current_user.clinica_id, detalhado=True)


@router.get("/procedimentos-genericos/proximo-codigo", dependencies=[DEP_PROCEDIMENTOS])
def proximo_codigo_procedimento_generico(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"codigo": _proximo_codigo_procedimento_generico(db, current_user.clinica_id)}


@router.get("/procedimentos-genericos/detalhe/{item_id}", dependencies=[DEP_PROCEDIMENTOS])
def detalhar_procedimento_generico_v2(
    item_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(ProcedimentoGenerico)
        .filter(
            ProcedimentoGenerico.id == item_id,
            ProcedimentoGenerico.clinica_id == current_user.clinica_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Procedimento genérico não encontrado.")
    return _procedimento_generico_to_dict(item, clinica_id=current_user.clinica_id, detalhado=True)


@router.post("/procedimentos-genericos/migrar", dependencies=[DEP_PROCEDIMENTOS])
def migrar_procedimentos_genericos(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = current_user.clinica_id
    if not TAB_GEN_ITEM_PATH.exists():
        raise HTTPException(status_code=404, detail=f"Arquivo não encontrado: {TAB_GEN_ITEM_PATH}")

    try:
        registros = _parse_tab_gen_item(TAB_GEN_ITEM_PATH.read_bytes())
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao ler arquivo RAW: {exc}") from exc

    if not registros:
        raise HTTPException(status_code=400, detail="Nenhum procedimento genérico foi encontrado no arquivo RAW.")

    metadados = carregar_metadados_genericos_legado()
    existentes = {
        x.codigo: x
        for x in db.query(ProcedimentoGenerico)
        .filter(ProcedimentoGenerico.clinica_id == clinica_id)
        .all()
    }
    inseridos = 0
    atualizados = 0
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    for codigo, descricao in registros:
        meta = metadados.get(codigo) or {}
        especialidade = str(meta.get("especialidade") or "").strip()
        simbolo_grafico = str(meta.get("simbolo_grafico") or "").strip()
        mostrar_simbolo = bool(meta.get("mostrar_simbolo"))
        atual = existentes.get(codigo)
        if atual is None:
            db.add(
                ProcedimentoGenerico(
                    clinica_id=clinica_id,
                    codigo=codigo,
                    descricao=descricao,
                    especialidade=especialidade or None,
                    simbolo_grafico=simbolo_grafico or None,
                    mostrar_simbolo=mostrar_simbolo,
                    data_inclusao=agora,
                )
            )
            inseridos += 1
            continue
        mudou = False
        if (atual.descricao or "") != descricao:
            atual.descricao = descricao
            mudou = True
        if especialidade and not str(atual.especialidade or "").strip():
            atual.especialidade = especialidade
            mudou = True
        if simbolo_grafico and not str(atual.simbolo_grafico or "").strip():
            atual.simbolo_grafico = simbolo_grafico
            mudou = True
        if mostrar_simbolo and not bool(atual.mostrar_simbolo):
            atual.mostrar_simbolo = True
            mudou = True
        if mudou:
            atual.data_alteracao = agora
            atualizados += 1

    db.commit()
    total_tabela = db.query(ProcedimentoGenerico.id).filter(ProcedimentoGenerico.clinica_id == clinica_id).count()
    detail = (
        f"Migração concluída: {len(registros)} lidos, "
        f"{inseridos} inseridos, {atualizados} atualizados."
    )
    return {
        "detail": detail,
        "arquivo": str(TAB_GEN_ITEM_PATH),
        "total_registros": len(registros),
        "inseridos": inseridos,
        "atualizados": atualizados,
        "total_tabela": total_tabela,
    }


@router.post("/procedimentos-genericos", dependencies=[DEP_PROCEDIMENTOS])
def criar_procedimento_generico(
    payload: ProcedimentoGenericoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = current_user.clinica_id
    codigo = _norm_codigo_procedimento_generico(payload.codigo)
    descricao = (payload.descricao or "").strip()
    if not codigo or not descricao:
        raise HTTPException(status_code=400, detail="Informe código e descrição.")

    existe = (
        db.query(ProcedimentoGenerico.id)
        .filter(
            ProcedimentoGenerico.clinica_id == clinica_id,
            ProcedimentoGenerico.codigo == codigo,
        )
        .first()
    )
    if existe:
        raise HTTPException(status_code=400, detail="Já existe um procedimento genérico com este código.")

    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    item = ProcedimentoGenerico(
        clinica_id=clinica_id,
        codigo=codigo,
        descricao=descricao,
        especialidade=(payload.especialidade or "").strip() or None,
        tempo=max(0, int(payload.tempo or 0)),
        custo_lab=float(payload.custo_lab or 0),
        peso=max(0.0, float(payload.peso or 0)),
        simbolo_grafico=(payload.simbolo_grafico or "").strip() or None,
        mostrar_simbolo=bool(payload.mostrar_simbolo or (payload.simbolo_grafico or "").strip()),
        inativo=bool(payload.inativo),
        observacoes=(payload.observacoes or "").strip() or None,
        data_inclusao=agora,
        data_alteracao="",
    )
    db.add(item)
    db.flush()
    _sync_procedimento_generico_fases(db, item, clinica_id, payload.fases)
    _sync_procedimento_generico_materiais(db, item, clinica_id, payload.materiais)
    db.commit()
    db.refresh(item)
    return _procedimento_generico_to_dict(item, clinica_id=clinica_id, detalhado=True)


@router.put("/procedimentos-genericos/{item_id}", dependencies=[DEP_PROCEDIMENTOS])
def editar_procedimento_generico(
    item_id: int,
    payload: ProcedimentoGenericoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = current_user.clinica_id
    item = (
        db.query(ProcedimentoGenerico)
        .filter(
            ProcedimentoGenerico.id == item_id,
            ProcedimentoGenerico.clinica_id == clinica_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Procedimento genérico não encontrado.")

    codigo = _norm_codigo_procedimento_generico(payload.codigo)
    descricao = (payload.descricao or "").strip()
    if not codigo or not descricao:
        raise HTTPException(status_code=400, detail="Informe código e descrição.")

    existe = (
        db.query(ProcedimentoGenerico.id)
        .filter(
            ProcedimentoGenerico.codigo == codigo,
            ProcedimentoGenerico.clinica_id == clinica_id,
            ProcedimentoGenerico.id != item.id,
        )
        .first()
    )
    if existe:
        raise HTTPException(status_code=400, detail="Já existe outro procedimento genérico com este código.")

    item.codigo = codigo
    item.descricao = descricao
    item.especialidade = (payload.especialidade or "").strip() or None
    item.tempo = max(0, int(payload.tempo or 0))
    item.custo_lab = float(payload.custo_lab or 0)
    item.peso = max(0.0, float(payload.peso or 0))
    item.simbolo_grafico = (payload.simbolo_grafico or "").strip() or None
    item.mostrar_simbolo = bool(payload.mostrar_simbolo or item.simbolo_grafico)
    item.inativo = bool(payload.inativo)
    item.observacoes = (payload.observacoes or "").strip() or None
    item.data_alteracao = datetime.now().strftime("%d/%m/%Y %H:%M")
    if not (item.data_inclusao or "").strip():
        item.data_inclusao = item.data_alteracao
    _sync_procedimento_generico_fases(db, item, clinica_id, payload.fases)
    _sync_procedimento_generico_materiais(db, item, clinica_id, payload.materiais)
    _propagar_campos_generico_para_procedimentos(db, clinica_id, int(item.id), item.tempo, item.custo_lab)
    db.commit()
    db.refresh(item)
    return _procedimento_generico_to_dict(item, clinica_id=clinica_id, detalhado=True)


@router.delete("/procedimentos-genericos/{item_id}", dependencies=[DEP_PROCEDIMENTOS])
def excluir_procedimento_generico(
    item_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = current_user.clinica_id
    item = (
        db.query(ProcedimentoGenerico)
        .filter(
            ProcedimentoGenerico.id == item_id,
            ProcedimentoGenerico.clinica_id == clinica_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Procedimento genérico não encontrado.")
    em_uso = (
        db.query(Procedimento.id)
        .filter(
            Procedimento.clinica_id == clinica_id,
            Procedimento.procedimento_generico_id == item.id,
        )
        .first()
    )
    if em_uso:
        raise HTTPException(status_code=409, detail="Este procedimento genÃ©rico estÃ¡ vinculado a procedimentos da tabela.")
    db.delete(item)
    db.commit()
    return {"detail": "Procedimento genérico excluído."}
