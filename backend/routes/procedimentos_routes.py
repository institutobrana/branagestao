import json
import unicodedata
from datetime import datetime
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import get_db
from models.cenario import Cenario
from models.clinica import Clinica
from models.financeiro import ItemAuxiliar
from models.material import Material
from models.procedimento import Procedimento, ProcedimentoFase, ProcedimentoMaterial
from models.procedimento_generico import (
    ProcedimentoGenerico,
    ProcedimentoGenericoFase,
    ProcedimentoGenericoMaterial,
)
from models.procedimento_tabela import ProcedimentoTabela
from models.tiss_tipo_tabela import TissTipoTabela
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access
from services.indices_service import (
    DEFAULT_INDICE_NUMERO,
    dados_indice_por_numero,
    listar_indices,
    resolver_numero_indice,
)

router = APIRouter(
    prefix="/procedimentos",
    tags=["procedimentos"],
    dependencies=[Depends(require_module_access("procedimentos"))],
)
PRIVATE_TABLE_CODE = 4
PRIVATE_TABLE_NAME = "PARTICULAR"

TISS_TIPOS_FALLBACK = [
    {"id": 1, "codigo": "00", "nome": "Outras Tabelas"},
]
PROC_RELATORIO_CAMPOS = [
    "Tabela",
    "Código",
    "Intervenção",
    "Especialidade",
    "Tempo",
    "Índice",
    "Val paciente",
    "Val paciente (R$)",
    "Val convênio %",
    "Val convênio (R$)",
    "Val inter (R$)",
    "Cst fixo (R$)",
    "Cst fixo %",
    "Cst mat (R$)",
    "Cst mat %",
    "Cst prot (R$)",
    "Cst prot %",
    "Imp. diretos (R$)",
    "Lucro (R$)",
    "Lucro mens (R$)",
]
FORMAS_COBRANCA_PADRAO = {
    "INTERVENCAO": "Intervenção",
    "ELEMENTO_FACE": "Elemento / Face",
}


FORMAS_COBRANCA_PADRAO = {
    "INTERVENCAO": "Intervenção",
    "ELEMENTO_FACE": "Elemento / Face",
}


_GENERICO_CUSTO_MATERIAL_CANONICO = None


class ProcedimentoPayload(BaseModel):
    codigo: int
    nome: str
    tempo: int = 0
    preco: float = 0
    custo: float = 0
    custo_lab: float = 0
    tabela_id: str = "1"
    especialidade: str | None = None
    procedimento_generico_id: int | None = None
    simbolo_grafico: str | None = None
    simbolo_grafico_legacy_id: int | None = None
    mostrar_simbolo: bool | None = None
    garantia_meses: int = 0
    forma_cobranca: str | None = None
    valor_repasse: float = 0
    preferido: bool = False
    inativo: bool = False
    observacoes: str | None = None


class TabelaProcedimentoPayload(BaseModel):
    nome: str
    copiar_de_tabela_id: str | None = None
    nro_indice: int | str | None = None
    fonte_pagadora: str | None = None
    nro_credenciamento: str | None = None
    inativo: bool | None = None
    tipo_tiss_id: int | str | None = None


class VinculoPayload(BaseModel):
    material_id: int
    quantidade: float


class VinculoUpdatePayload(BaseModel):
    quantidade: float


def _chave_ordenacao(texto: str) -> str:
    base = (texto or "").strip().lower()
    base = unicodedata.normalize("NFD", base)
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def _normalizar_especialidade(valor: str | int | None) -> str:
    base = str(valor or "").strip()
    if not base:
        return ""
    if base.isdigit():
        numero = int(base)
        if numero <= 0:
            return ""
        return f"{numero:02d}"
    return base[:20]


def _normalizar_fonte_pagadora(valor: str | None) -> str:
    base = str(valor or "").strip().lower()
    if base in {"2", "convenio", "convênio"}:
        return "convenio"
    return "particular"


def _normalizar_forma_cobranca(valor: str | None) -> str | None:
    base = _chave_ordenacao(str(valor or ""))
    if not base:
        return None
    if base in {"intervencao", "intervenção"}:
        return "INTERVENCAO"
    if base in {"elemento/face", "elemento / face", "elementoface", "elemento face"}:
        return "ELEMENTO_FACE"
    if str(valor or "").strip().upper() in FORMAS_COBRANCA_PADRAO:
        return str(valor or "").strip().upper()
    return str(valor or "").strip() or None


def _normalizar_fonte_pagadora(valor: str | None) -> str:
    base = str(valor or "").strip().lower()
    if base in {"2", "convenio", "convênio"}:
        return "convenio"
    return "particular"


def _normalizar_forma_cobranca(valor: str | None) -> str | None:
    base = _chave_ordenacao(str(valor or ""))
    if not base:
        return None
    if base in {"intervencao", "intervenção"}:
        return "INTERVENCAO"
    if base in {"elemento/face", "elemento / face", "elementoface", "elemento face"}:
        return "ELEMENTO_FACE"
    valor_limpo = str(valor or "").strip().upper()
    if valor_limpo in FORMAS_COBRANCA_PADRAO:
        return valor_limpo
    return str(valor or "").strip() or None


def _indice_default_id_por_fonte(fonte_pagadora: str | None) -> int:
    return 3 if _normalizar_fonte_pagadora(fonte_pagadora) == "convenio" else DEFAULT_INDICE_NUMERO


def _resolver_nro_indice(
    db: Session,
    clinica_id: int,
    valor: int | str | None,
    fonte_pagadora: str | None,
    default: int | None = None,
) -> int:
    fallback = int(default or _indice_default_id_por_fonte(fonte_pagadora))
    return resolver_numero_indice(db, clinica_id, valor, default=fallback)


def _dados_indice_por_id(db: Session, clinica_id: int, nro_indice: int | str | None) -> dict:
    return dados_indice_por_numero(db, clinica_id, nro_indice)


def _listar_indices_moeda(db: Session, clinica_id: int) -> list[dict]:
    return listar_indices(db, clinica_id, include_inativos=True)


def _carregar_custo_material_canonico_genericos() -> dict[str, float]:
    global _GENERICO_CUSTO_MATERIAL_CANONICO
    if _GENERICO_CUSTO_MATERIAL_CANONICO is not None:
        return _GENERICO_CUSTO_MATERIAL_CANONICO
    path = Path(__file__).resolve().parents[3] / "scripts" / "easy_genericos_canonicos_snapshot.json"
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _GENERICO_CUSTO_MATERIAL_CANONICO = {}
        return _GENERICO_CUSTO_MATERIAL_CANONICO
    mapa = {}
    for row in rows if isinstance(rows, list) else []:
        codigo = str((row or {}).get("codigo") or "").strip()
        if not codigo:
            continue
        try:
            mapa[codigo.zfill(4)] = float((row or {}).get("custo_material") or 0.0)
        except (TypeError, ValueError):
            continue
    _GENERICO_CUSTO_MATERIAL_CANONICO = mapa
    return _GENERICO_CUSTO_MATERIAL_CANONICO


def _tipo_tiss_default_id(db: Session, prefer: int = 1) -> int:
    alvo = int(prefer or 1)
    try:
        existe = db.query(TissTipoTabela.id).filter(TissTipoTabela.id == alvo).first()
        if existe:
            return alvo
        primeiro = db.query(TissTipoTabela.id).order_by(TissTipoTabela.id.asc()).first()
        if primeiro:
            return int(primeiro[0])
    except SQLAlchemyError:
        pass
    return alvo


def _resolver_tipo_tiss_id(db: Session, valor: int | str | None, default: int = 1) -> int:
    default_id = _tipo_tiss_default_id(db, default)
    base = str(valor or "").strip()
    if not base:
        return default_id

    legado = base.lower()
    if legado in {"consulta", "procedimento", "diaria", "taxa", "pacote"}:
        return default_id

    try:
        tipo_id: int | None = None
        if base.isdigit():
            tipo_id = int(base)
        else:
            por_codigo = (
                db.query(TissTipoTabela.id)
                .filter(func.lower(TissTipoTabela.codigo) == legado)
                .first()
            )
            if por_codigo:
                tipo_id = int(por_codigo[0])

        if tipo_id is None:
            return default_id

        existe = db.query(TissTipoTabela.id).filter(TissTipoTabela.id == int(tipo_id)).first()
        return int(tipo_id) if existe else default_id
    except SQLAlchemyError:
        return default_id


def _listar_tipos_tiss(db: Session) -> list[dict]:
    rows: list[TissTipoTabela] = []
    try:
        rows = (
            db.query(TissTipoTabela)
            .filter(TissTipoTabela.ativo.is_(True))
            .order_by(TissTipoTabela.nome.asc())
            .all()
        )
        if not rows:
            rows = db.query(TissTipoTabela).order_by(TissTipoTabela.nome.asc()).all()
    except SQLAlchemyError:
        rows = []

    payload = [
        {
            "id": int(x.id),
            "codigo": (x.codigo or "").strip(),
            "nome": (x.nome or "").strip(),
        }
        for x in rows
    ]
    return payload if payload else [dict(x) for x in TISS_TIPOS_FALLBACK]


def _listar_especialidades(db: Session, clinica_id: int) -> list[dict]:
    rows = (
        db.query(ItemAuxiliar)
        .filter(
            ItemAuxiliar.clinica_id == clinica_id,
            ItemAuxiliar.tipo.ilike("Especialidade"),
            or_(ItemAuxiliar.inativo.is_(False), ItemAuxiliar.inativo.is_(None)),
        )
        .order_by(
            func.coalesce(ItemAuxiliar.ordem, 999999).asc(),
            ItemAuxiliar.descricao.asc(),
            ItemAuxiliar.id.asc(),
        )
        .all()
    )

    especiais: list[dict] = []
    vistos: set[str] = set()
    for row in rows:
        nome = (row.descricao or "").strip()
        if not nome:
            continue
        chave = _chave_ordenacao(nome)
        if not chave or chave in vistos:
            continue
        vistos.add(chave)
        codigo = str(row.codigo or "").strip()
        especiais.append({"codigo": codigo, "nome": nome})

    return especiais


def _mapa_especialidades(db: Session, clinica_id: int) -> dict[str, str]:
    return {
        str(item.get("codigo") or "").strip(): str(item.get("nome") or "").strip()
        for item in _listar_especialidades(db, clinica_id)
        if str(item.get("codigo") or "").strip()
    }


def _mapa_tabelas_por_id(db: Session, clinica_id: int) -> dict[int, ProcedimentoTabela]:
    rows = (
        db.query(ProcedimentoTabela)
        .filter(ProcedimentoTabela.clinica_id == clinica_id)
        .all()
    )
    return {int(x.id): x for x in rows}


def _mapa_custo_material_por_proc(db: Session, clinica_id: int, proc_ids: list[int]) -> dict[int, float]:
    if not proc_ids:
        return {}

    rows = (
        db.query(
            ProcedimentoMaterial.procedimento_id,
            func.coalesce(func.sum(ProcedimentoMaterial.quantidade * Material.custo), 0.0),
        )
        .join(Material, Material.id == ProcedimentoMaterial.material_id)
        .filter(
            ProcedimentoMaterial.clinica_id == clinica_id,
            ProcedimentoMaterial.procedimento_id.in_(proc_ids),
        )
        .group_by(ProcedimentoMaterial.procedimento_id)
        .all()
    )
    return {int(proc_id): float(total or 0.0) for proc_id, total in rows}


def _mapa_custo_material_por_generico(db: Session, clinica_id: int, generico_ids: list[int]) -> dict[int, float]:
    if not generico_ids:
        return {}

    rows = (
        db.query(
            ProcedimentoGenericoMaterial.procedimento_generico_id,
            func.coalesce(func.sum(ProcedimentoGenericoMaterial.quantidade * Material.custo), 0.0),
        )
        .join(Material, Material.id == ProcedimentoGenericoMaterial.material_id)
        .filter(
            ProcedimentoGenericoMaterial.clinica_id == clinica_id,
            ProcedimentoGenericoMaterial.procedimento_generico_id.in_(generico_ids),
        )
        .group_by(ProcedimentoGenericoMaterial.procedimento_generico_id)
        .all()
    )
    return {int(generico_id): float(total or 0.0) for generico_id, total in rows}


def _mapa_preco_particular_por_chave(
    db: Session,
    clinica_id: int,
    tabela_particular_id: int,
) -> dict[tuple[str, int | str], float]:
    if tabela_particular_id <= 0:
        return {}

    rows = (
        db.query(Procedimento)
        .filter(
            Procedimento.clinica_id == clinica_id,
            Procedimento.tabela_id == tabela_particular_id,
        )
        .all()
    )

    mapa: dict[tuple[str, int | str], float] = {}
    for proc in rows:
        generico_id = int(proc.procedimento_generico_id or 0)
        preco = float(proc.preco or 0)
        if generico_id > 0:
            mapa[("generico", generico_id)] = preco
        mapa[("codigo", int(proc.codigo or 0))] = preco
    return mapa


def _resolver_preco_particular(
    proc: Procedimento,
    tabela_codigo: int,
    mapa_preco_particular: dict[tuple[str, int | str], float],
) -> float:
    if tabela_codigo == PRIVATE_TABLE_CODE:
        return float(proc.preco or 0)

    generico_id = int(proc.procedimento_generico_id or 0)
    if generico_id > 0 and ("generico", generico_id) in mapa_preco_particular:
        return float(mapa_preco_particular[("generico", generico_id)] or 0)

    return float(mapa_preco_particular.get(("codigo", int(proc.codigo or 0)), 0) or 0)


def _pct(valor: float, base: float) -> float:
    valor = float(valor or 0)
    base = float(base or 0)
    return (valor * 100 / base) if base > 0 else 0.0


def _ordenar_relatorio_proc(rows: list[dict], ordem: str) -> list[dict]:
    campo = str(ordem or "").strip() or "Intervenção"
    numericos = {
        "Código",
        "Tempo",
        "Val paciente",
        "Val paciente (R$)",
        "Val convênio %",
        "Val convênio (R$)",
        "Val inter (R$)",
        "Cst fixo (R$)",
        "Cst fixo %",
        "Cst mat (R$)",
        "Cst mat %",
        "Cst prot (R$)",
        "Cst prot %",
        "Imp. diretos (R$)",
        "Lucro (R$)",
        "Lucro mens (R$)",
    }

    if campo in numericos:
        return sorted(rows, key=lambda x: (float(x.get(campo) or 0), _chave_ordenacao(str(x.get("Intervenção") or ""))))
    return sorted(rows, key=lambda x: _chave_ordenacao(str(x.get(campo) or "")))


def _codigo_tabela_do_procedimento(db: Session, proc: Procedimento) -> int:
    tabela = (
        db.query(ProcedimentoTabela.codigo)
        .filter(
            ProcedimentoTabela.id == int(proc.tabela_id or 0),
            ProcedimentoTabela.clinica_id == int(proc.clinica_id or 0),
        )
        .first()
    )
    if tabela:
        return int(tabela[0] or 1)
    return int(proc.tabela_id or 1)


def _procedimento_to_dict(db: Session, proc: Procedimento) -> dict:
    return {
        "id": proc.id,
        "codigo": int(proc.codigo or 0),
        "nome": proc.nome or "",
        "tabela_id": _codigo_tabela_do_procedimento(db, proc),
        "especialidade": str(proc.especialidade or "").strip(),
        "procedimento_generico_id": proc.procedimento_generico_id,
        "simbolo_grafico": str(proc.simbolo_grafico or "").strip(),
        "simbolo_grafico_legacy_id": int(proc.simbolo_grafico_legacy_id or 0) or None,
        "mostrar_simbolo": bool(proc.mostrar_simbolo),
        "garantia_meses": int(proc.garantia_meses or 0),
        "forma_cobranca": str(_normalizar_forma_cobranca(proc.forma_cobranca) or "").strip(),
        "valor_repasse": float(proc.valor_repasse or 0),
        "preferido": bool(proc.preferido),
        "inativo": bool(proc.inativo),
        "observacoes": proc.observacoes or "",
        "data_inclusao": proc.data_inclusao or "",
        "data_alteracao": proc.data_alteracao or "",
        "tempo": int(proc.tempo or 0),
        "preco": float(proc.preco or 0),
        "custo": float(proc.custo or 0),
        "custo_lab": float(proc.custo_lab or 0),
        "lucro_hora": float(proc.lucro_hora or 0),
    }


def _listar_fases_vinculadas(db: Session, procedimento_id: int) -> list[dict]:
    rows = (
        db.query(ProcedimentoFase)
        .filter(ProcedimentoFase.procedimento_id == procedimento_id)
        .order_by(ProcedimentoFase.sequencia.asc(), ProcedimentoFase.id.asc())
        .all()
    )
    return [
        {
            "id": int(x.id),
            "codigo": str(x.codigo or "").strip(),
            "descricao": str(x.descricao or "").strip(),
            "sequencia": int(x.sequencia or 0),
            "tempo": int(x.tempo or 0),
        }
        for x in rows
    ]


def _procedimento_com_vinculos(db: Session, proc: Procedimento) -> dict:
    data = _procedimento_to_dict(db, proc)
    data["materiais_vinculados"] = _listar_materiais_vinculados(db, int(proc.id))
    data["fases_vinculadas"] = _listar_fases_vinculadas(db, int(proc.id))
    return data


def _aplicar_heranca_procedimento_generico(
    db: Session,
    clinica_id: int,
    proc: Procedimento,
    sobrescrever_vinculos: bool,
) -> None:
    generico_id = int(proc.procedimento_generico_id or 0)
    if generico_id <= 0:
        return

    generico = (
        db.query(ProcedimentoGenerico)
        .filter(
            ProcedimentoGenerico.id == generico_id,
            ProcedimentoGenerico.clinica_id == clinica_id,
        )
        .first()
    )
    if not generico:
        return

    if not (proc.especialidade or "").strip() and (generico.especialidade or "").strip():
        proc.especialidade = str(generico.especialidade or "").strip()
    if not (proc.simbolo_grafico or "").strip() and (generico.simbolo_grafico or "").strip():
        proc.simbolo_grafico = str(generico.simbolo_grafico or "").strip()
    if not int(proc.simbolo_grafico_legacy_id or 0) and int(getattr(generico, "simbolo_grafico_legacy_id", 0) or 0) > 0:
        proc.simbolo_grafico_legacy_id = int(getattr(generico, "simbolo_grafico_legacy_id", 0) or 0)
    if not int(proc.tempo or 0) and int(generico.tempo or 0) > 0:
        proc.tempo = int(generico.tempo or 0)
    if not float(proc.custo_lab or 0) and float(getattr(generico, "custo_lab", 0) or 0) > 0:
        proc.custo_lab = float(getattr(generico, "custo_lab", 0) or 0)
    if not (proc.observacoes or "").strip() and (generico.observacoes or "").strip():
        proc.observacoes = generico.observacoes
    if not bool(proc.mostrar_simbolo) and bool(generico.mostrar_simbolo):
        proc.mostrar_simbolo = True

    (
        db.query(ProcedimentoFase)
        .filter(ProcedimentoFase.procedimento_id == int(proc.id))
        .delete(synchronize_session=False)
    )
    fases = (
        db.query(ProcedimentoGenericoFase)
        .filter(
            ProcedimentoGenericoFase.procedimento_generico_id == generico_id,
            ProcedimentoGenericoFase.clinica_id == clinica_id,
        )
        .order_by(ProcedimentoGenericoFase.sequencia.asc(), ProcedimentoGenericoFase.id.asc())
        .all()
    )
    for fase in fases:
        db.add(
            ProcedimentoFase(
                procedimento_id=int(proc.id),
                clinica_id=clinica_id,
                codigo=str(fase.codigo or "").strip() or None,
                descricao=str(fase.descricao or "").strip(),
                sequencia=int(fase.sequencia or 0),
                tempo=int(fase.tempo or 0),
            )
        )

    if not sobrescrever_vinculos:
        return

    (
        db.query(ProcedimentoMaterial)
        .filter(ProcedimentoMaterial.procedimento_id == int(proc.id))
        .delete(synchronize_session=False)
    )
    mats = (
        db.query(ProcedimentoGenericoMaterial)
        .join(Material, Material.id == ProcedimentoGenericoMaterial.material_id)
        .filter(
            ProcedimentoGenericoMaterial.procedimento_generico_id == generico_id,
            ProcedimentoGenericoMaterial.clinica_id == clinica_id,
            Material.lista.has(clinica_id=clinica_id),
        )
        .order_by(ProcedimentoGenericoMaterial.id.asc())
        .all()
    )
    for vinc in mats:
        db.add(
            ProcedimentoMaterial(
                procedimento_id=int(proc.id),
                material_id=int(vinc.material_id),
                quantidade=float(vinc.quantidade or 0),
                clinica_id=clinica_id,
            )
        )


def _sincronizar_generico_com_procedimento(
    db: Session,
    clinica_id: int,
    proc: Procedimento,
) -> None:
    generico_id = int(proc.procedimento_generico_id or 0)
    if generico_id <= 0:
        return
    generico = (
        db.query(ProcedimentoGenerico)
        .filter(
            ProcedimentoGenerico.id == generico_id,
            ProcedimentoGenerico.clinica_id == clinica_id,
        )
        .first()
    )
    if not generico:
        return
    tempo = max(0, int(proc.tempo or 0))
    custo_lab = float(proc.custo_lab or 0)
    generico.tempo = tempo
    if hasattr(generico, "custo_lab"):
        generico.custo_lab = custo_lab
    (
        db.query(Procedimento)
        .filter(
            Procedimento.clinica_id == clinica_id,
            Procedimento.procedimento_generico_id == generico_id,
        )
        .update(
            {
                "tempo": tempo,
                "custo_lab": custo_lab,
            },
            synchronize_session=False,
        )
    )


def _load_proc_or_404(db: Session, clinica_id: int, procedimento_id: int) -> Procedimento:
    proc = (
        db.query(Procedimento)
        .filter(
            Procedimento.id == procedimento_id,
            Procedimento.clinica_id == clinica_id,
        )
        .first()
    )
    if not proc:
        raise HTTPException(status_code=404, detail="Procedimento nao encontrado.")
    return proc


def _load_material_or_404(db: Session, clinica_id: int, material_id: int) -> Material:
    mat = (
        db.query(Material)
        .join(Material.lista)
        .filter(
            Material.id == material_id,
            Material.lista.has(clinica_id=clinica_id),
        )
        .first()
    )
    if not mat:
        raise HTTPException(status_code=404, detail="Material nao encontrado.")
    return mat


def _proc_codigo_em_uso(
    db: Session,
    clinica_id: int,
    tabela_id: int,
    codigo: int,
    ignore_id: int | None = None,
) -> bool:
    query = db.query(Procedimento).filter(
        Procedimento.clinica_id == clinica_id,
        Procedimento.tabela_id == tabela_id,
        Procedimento.codigo == codigo,
    )
    if ignore_id:
        query = query.filter(Procedimento.id != ignore_id)
    return db.query(query.exists()).scalar()


def _listar_materiais_vinculados(db: Session, procedimento_id: int):
    vinculos = (
        db.query(ProcedimentoMaterial)
        .filter(ProcedimentoMaterial.procedimento_id == procedimento_id)
        .order_by(ProcedimentoMaterial.id.asc())
        .all()
    )

    itens = []
    total_materiais = 0
    total_custo_und = 0.0
    total_custo = 0.0
    for v in vinculos:
        mat = v.material
        custo_total = float(mat.custo or 0) * float(v.quantidade or 0)
        itens.append(
            {
                "vinculo_id": v.id,
                "material_id": mat.id,
                "codigo": mat.codigo,
                "nome": mat.nome,
                "relacao": float(mat.relacao or 0),
                "preco": float(mat.preco or 0),
                "custo_und": float(mat.custo or 0),
                "quantidade": float(v.quantidade or 0),
                "custo_total": float(custo_total or 0),
            }
        )
        total_materiais += 1
        total_custo_und += float(mat.custo or 0)
        total_custo += float(custo_total or 0)

    return {
        "itens": itens,
        "total_materiais": total_materiais,
        "total_custo_und": total_custo_und,
        "total_custo": total_custo,
    }


def _calcular_financeiro_dashboard(proc: Procedimento, cenario: Cenario | None, custo_material: float) -> dict:
    preco = float(proc.preco or 0)
    tempo = float(proc.tempo or 0)
    lab = float(proc.custo_lab or 0)

    cfpm = float(cenario.cfpm or 0) if cenario else 0.0
    ir_pct = float(cenario.ir or 0) if cenario else 0.0
    cd_pct = float(cenario.cd or 0) if cenario else 0.0
    cartao_pct = float(cenario.cartao or 0) if cenario else 0.0

    custo_fph = cfpm * tempo
    custo_proc = custo_fph + float(custo_material or 0) + lab

    valor_ir = preco * ir_pct / 100
    valor_cd = preco * cd_pct / 100
    valor_cartao = preco * cartao_pct / 100

    lucro_bruto = preco - custo_proc
    lucro_liquido = lucro_bruto - (valor_ir + valor_cd + valor_cartao)

    rendimento_proc = (lucro_bruto * 100 / custo_proc) if custo_proc > 0 else 0.0
    rendimento_3040 = (lucro_bruto * 100 / preco) if preco > 0 else 0.0
    rendimento_1020 = (lucro_liquido * 100 / preco) if preco > 0 else 0.0

    lucro_hora = (lucro_liquido * 60 / tempo) if tempo > 0 else 0.0
    valor_minimo = custo_proc + valor_ir + valor_cd + valor_cartao + (custo_proc * 10 / 100)

    return {
        "id": proc.id,
        "codigo": int(proc.codigo or 0),
        "nome": proc.nome or "",
        "preco": preco,
        "tempo": tempo,
        "tempo_grafico": max(tempo, 30.0),
        "lab": lab,
        "custo_material": float(custo_material or 0),
        "custo_fph": custo_fph,
        "custo_proc": custo_proc,
        "ir": valor_ir,
        "cd": valor_cd,
        "cartao": valor_cartao,
        "lucro_bruto": lucro_bruto,
        "lucro_liquido": lucro_liquido,
        "valor_minimo": valor_minimo,
        "rendimento_proc": rendimento_proc,
        "rendimento_3040": rendimento_3040,
        "rendimento_1020": rendimento_1020,
        "rendimento": rendimento_1020,
        "lucro_hora": lucro_hora,
    }


def _nome_tabela_extra_clinica(db: Session, clinica_id: int) -> str:
    row = (
        db.query(Clinica.nome_tabela_procedimentos)
        .filter(Clinica.id == clinica_id)
        .first()
    )
    nome = (row[0] if row else "") or ""
    return nome.strip()


def _garantir_tabelas_clinica(db: Session, clinica_id: int):
    tabelas = (
        db.query(ProcedimentoTabela)
        .filter(ProcedimentoTabela.clinica_id == clinica_id)
        .order_by(ProcedimentoTabela.codigo.asc())
        .all()
    )
    por_codigo = {int(t.codigo): t for t in tabelas if int(t.codigo or 0) > 0}
    alterou = False

    if 1 not in por_codigo:
        t = ProcedimentoTabela(
            clinica_id=clinica_id,
            codigo=1,
            nome="Tabela Exemplo",
            nro_indice=255,
            fonte_pagadora="particular",
            inativo=False,
            tipo_tiss_id=1,
        )
        db.add(t)
        por_codigo[1] = t
        alterou = True

    nome_extra = _nome_tabela_extra_clinica(db, clinica_id)
    if PRIVATE_TABLE_CODE not in por_codigo:
        db.add(
            ProcedimentoTabela(
                clinica_id=clinica_id,
                codigo=PRIVATE_TABLE_CODE,
                nome=nome_extra or PRIVATE_TABLE_NAME,
                nro_indice=255,
                fonte_pagadora="particular",
                inativo=False,
                tipo_tiss_id=1,
            )
        )
        alterou = True

    if alterou:
        db.commit()


def _resolver_tabela_id(valor: str | int | None, default: int = 1) -> int:
    base = str(valor or "").strip()
    if not base or base in {"1", "__padrao__"}:
        return 1
    if base == "__todos__":
        return 0
    if base.isdigit():
        numero = int(base)
        return numero if numero > 0 else default
    return default


def _load_tabela_or_404(db: Session, clinica_id: int, codigo: int) -> ProcedimentoTabela:
    tabela = (
        db.query(ProcedimentoTabela)
        .filter(
            ProcedimentoTabela.clinica_id == clinica_id,
            ProcedimentoTabela.codigo == codigo,
        )
        .first()
    )
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela de procedimentos nao encontrada.")
    return tabela


def _tabela_id_por_codigo(db: Session, clinica_id: int, codigo: int) -> int:
    tabela = _load_tabela_or_404(db, clinica_id, codigo)
    return int(tabela.id)


def _validar_tabela_ativa(tabela: ProcedimentoTabela):
    if bool(tabela.inativo):
        raise HTTPException(status_code=400, detail="Tabela inativa. Reative a tabela para alterar procedimentos.")


def _listar_tabelas_procedimentos(db: Session, clinica_id: int) -> list[dict]:
    _garantir_tabelas_clinica(db, clinica_id)
    tipos_por_id: dict[int, TissTipoTabela] = {}
    try:
        tipos = db.query(TissTipoTabela).all()
        tipos_por_id = {int(t.id): t for t in tipos}
    except SQLAlchemyError:
        tipos_por_id = {}
    tabelas = (
        db.query(ProcedimentoTabela)
        .filter(ProcedimentoTabela.clinica_id == clinica_id)
        .order_by(ProcedimentoTabela.codigo.asc())
        .all()
    )
    payload: list[dict] = []
    for t in tabelas:
        try:
            tipo_tiss_id = int(t.tipo_tiss_id or 1)
        except (TypeError, ValueError):
            tipo_tiss_id = 1
        if tipo_tiss_id <= 0:
            tipo_tiss_id = 1
        if tipos_por_id and tipo_tiss_id not in tipos_por_id:
            tipo_tiss_id = sorted(tipos_por_id.keys())[0]
        tipo_tiss = tipos_por_id.get(tipo_tiss_id)
        fonte_pagadora = _normalizar_fonte_pagadora(t.fonte_pagadora)
        indice_id = _resolver_nro_indice(db, clinica_id, t.nro_indice, fonte_pagadora)
        indice_item = _dados_indice_por_id(db, clinica_id, indice_id)
        payload.append(
            {
                "id": str(int(t.codigo)),
                "nome": (t.nome or "").strip() or f"Tabela {int(t.codigo)}",
                "indice": int(indice_id),
                "indice_id": int(indice_item["id"]),
                "indice_sigla": str(indice_item["sigla"]),
                "indice_nome": str(indice_item["nome"]),
                "fonte_pagadora": fonte_pagadora,
                "nro_credenciamento": (t.nro_credenciamento or "").strip(),
                "inativo": bool(t.inativo),
                "tipo_tiss_id": tipo_tiss_id,
                "tipo_tiss_codigo": (tipo_tiss.codigo or "").strip() if tipo_tiss else "",
                "tipo_tiss_nome": (tipo_tiss.nome or "").strip() if tipo_tiss else "",
            }
        )
    return payload


def _copiar_procedimentos_entre_tabelas(
    db: Session,
    clinica_id: int,
    tabela_origem_id: int,
    tabela_destino_id: int,
) -> int:
    origem = (
        db.query(Procedimento)
        .filter(
            Procedimento.clinica_id == clinica_id,
            Procedimento.tabela_id == tabela_origem_id,
        )
        .order_by(Procedimento.codigo.asc(), Procedimento.id.asc())
        .all()
    )
    if not origem:
        return 0

    mapa_ids: dict[int, int] = {}
    for proc in origem:
        novo = Procedimento(
            codigo=int(proc.codigo or 0),
            nome=(proc.nome or "").strip(),
            tempo=int(proc.tempo or 0),
            preco=float(proc.preco or 0),
            custo=float(proc.custo or 0),
            custo_lab=float(proc.custo_lab or 0),
            lucro_hora=float(proc.lucro_hora or 0),
            tabela_id=tabela_destino_id,
            especialidade=_normalizar_especialidade(proc.especialidade) or None,
            procedimento_generico_id=proc.procedimento_generico_id,
            simbolo_grafico=(proc.simbolo_grafico or "").strip() or None,
            mostrar_simbolo=bool(proc.mostrar_simbolo),
            garantia_meses=int(proc.garantia_meses or 0),
            forma_cobranca=_normalizar_forma_cobranca(proc.forma_cobranca),
            valor_repasse=float(proc.valor_repasse or 0),
            preferido=bool(proc.preferido),
            inativo=bool(proc.inativo),
            observacoes=(proc.observacoes or "").strip() or None,
            data_inclusao=proc.data_inclusao or "",
            data_alteracao=proc.data_alteracao or "",
            clinica_id=clinica_id,
        )
        db.add(novo)
        db.flush()
        mapa_ids[int(proc.id)] = int(novo.id)

    if not mapa_ids:
        return 0

    vinculos = (
        db.query(ProcedimentoMaterial)
        .filter(ProcedimentoMaterial.procedimento_id.in_(list(mapa_ids.keys())))
        .order_by(ProcedimentoMaterial.id.asc())
        .all()
    )
    for vinc in vinculos:
        novo_proc_id = mapa_ids.get(int(vinc.procedimento_id or 0))
        if not novo_proc_id:
            continue
        db.add(
            ProcedimentoMaterial(
                procedimento_id=novo_proc_id,
                material_id=int(vinc.material_id),
                quantidade=float(vinc.quantidade or 0),
                clinica_id=clinica_id,
            )
        )
    return len(mapa_ids)


@router.get("/tabelas")
def listar_tabelas_procedimentos(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _listar_tabelas_procedimentos(db, current_user.clinica_id)


@router.post("/tabelas")
def criar_tabela_procedimentos(
    payload: TabelaProcedimentoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = current_user.clinica_id
    _garantir_tabelas_clinica(db, clinica_id)

    nome = (payload.nome or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome da tabela.")

    tabelas = db.query(ProcedimentoTabela).filter(ProcedimentoTabela.clinica_id == clinica_id).all()
    if any(_chave_ordenacao(t.nome) == _chave_ordenacao(nome) for t in tabelas):
        raise HTTPException(status_code=400, detail="Ja existe uma tabela com esse nome.")

    max_codigo = db.query(func.max(ProcedimentoTabela.codigo)).filter(ProcedimentoTabela.clinica_id == clinica_id).scalar()
    novo_codigo = int(max_codigo or 0) + 1
    if novo_codigo <= 1:
        novo_codigo = 2

    copiar_de = _resolver_tabela_id(payload.copiar_de_tabela_id, default=0)
    if copiar_de > 0:
        _load_tabela_or_404(db, clinica_id, copiar_de)
    fonte_pagadora = _normalizar_fonte_pagadora(payload.fonte_pagadora)
    tipo_tiss_id = _resolver_tipo_tiss_id(db, payload.tipo_tiss_id, default=1)
    nro_indice = _resolver_nro_indice(
        db,
        current_user.clinica_id,
        payload.nro_indice,
        fonte_pagadora,
        default=_indice_default_id_por_fonte(fonte_pagadora),
    )
    nro_credenciamento = (payload.nro_credenciamento or "").strip() or None
    if fonte_pagadora != "convenio":
        nro_credenciamento = None

    tabela = ProcedimentoTabela(
        clinica_id=clinica_id,
        codigo=novo_codigo,
        nome=nome,
        nro_indice=nro_indice,
        fonte_pagadora=fonte_pagadora,
        nro_credenciamento=nro_credenciamento,
        inativo=bool(payload.inativo),
        tipo_tiss_id=tipo_tiss_id,
    )
    db.add(tabela)
    db.flush()

    total_copiados = 0
    if copiar_de > 0:
        tabela_origem = _load_tabela_or_404(db, clinica_id, copiar_de)
        total_copiados = _copiar_procedimentos_entre_tabelas(db, clinica_id, int(tabela_origem.id), int(tabela.id))

    db.commit()
    indice_item = _dados_indice_por_id(db, current_user.clinica_id, tabela.nro_indice)
    return {
        "id": str(novo_codigo),
        "nome": tabela.nome,
        "copiados": total_copiados,
        "indice": int(indice_item["id"]),
        "indice_id": int(indice_item["id"]),
        "indice_sigla": str(indice_item["sigla"]),
        "indice_nome": str(indice_item["nome"]),
        "fonte_pagadora": _normalizar_fonte_pagadora(tabela.fonte_pagadora),
        "nro_credenciamento": (tabela.nro_credenciamento or "").strip(),
        "inativo": bool(tabela.inativo),
        "tipo_tiss_id": int(tabela.tipo_tiss_id or 1),
    }


@router.patch("/tabelas/{codigo}")
def renomear_tabela_procedimentos(
    codigo: int,
    payload: TabelaProcedimentoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = current_user.clinica_id
    _garantir_tabelas_clinica(db, clinica_id)

    nome = (payload.nome or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o novo nome da tabela.")

    tabela = _load_tabela_or_404(db, clinica_id, int(codigo))
    conflitante = (
        db.query(ProcedimentoTabela.id)
        .filter(
            ProcedimentoTabela.clinica_id == clinica_id,
            ProcedimentoTabela.codigo != int(codigo),
        )
        .all()
    )
    ids = [int(x[0]) for x in conflitante]
    if ids:
        tabelas = db.query(ProcedimentoTabela).filter(ProcedimentoTabela.id.in_(ids)).all()
        if any(_chave_ordenacao(x.nome) == _chave_ordenacao(nome) for x in tabelas):
            raise HTTPException(status_code=400, detail="Ja existe uma tabela com esse nome.")

    fonte_pagadora = _normalizar_fonte_pagadora(payload.fonte_pagadora)
    tipo_tiss_id = _resolver_tipo_tiss_id(db, payload.tipo_tiss_id, default=int(tabela.tipo_tiss_id or 1))
    indice_atual = _resolver_nro_indice(
        db,
        current_user.clinica_id,
        tabela.nro_indice,
        fonte_pagadora,
        default=_indice_default_id_por_fonte(fonte_pagadora),
    )
    nro_indice = _resolver_nro_indice(
        db,
        current_user.clinica_id,
        payload.nro_indice,
        fonte_pagadora,
        default=indice_atual,
    )
    nro_credenciamento = (payload.nro_credenciamento or "").strip() or None
    if fonte_pagadora != "convenio":
        nro_credenciamento = None

    tabela.nome = nome
    tabela.nro_indice = nro_indice
    tabela.fonte_pagadora = fonte_pagadora
    tabela.nro_credenciamento = nro_credenciamento
    if payload.inativo is not None:
        tabela.inativo = bool(payload.inativo)
    tabela.tipo_tiss_id = tipo_tiss_id
    if int(codigo) == PRIVATE_TABLE_CODE:
        clinica = db.query(Clinica).filter(Clinica.id == clinica_id).first()
        if clinica:
            clinica.nome_tabela_procedimentos = nome
    db.commit()
    indice_item = _dados_indice_por_id(db, current_user.clinica_id, tabela.nro_indice)
    return {
        "id": str(int(codigo)),
        "nome": tabela.nome,
        "indice": int(indice_item["id"]),
        "indice_id": int(indice_item["id"]),
        "indice_sigla": str(indice_item["sigla"]),
        "indice_nome": str(indice_item["nome"]),
        "fonte_pagadora": _normalizar_fonte_pagadora(tabela.fonte_pagadora),
        "nro_credenciamento": (tabela.nro_credenciamento or "").strip(),
        "inativo": bool(tabela.inativo),
        "tipo_tiss_id": int(tabela.tipo_tiss_id or 1),
    }


@router.delete("/tabelas/{codigo}")
def excluir_tabela_procedimentos(
    codigo: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = current_user.clinica_id
    _garantir_tabelas_clinica(db, clinica_id)

    tabela = _load_tabela_or_404(db, clinica_id, int(codigo))
    total_tabelas = (
        db.query(ProcedimentoTabela)
        .filter(ProcedimentoTabela.clinica_id == clinica_id)
        .count()
    )
    if total_tabelas <= 1:
        raise HTTPException(status_code=400, detail="Nao e possivel excluir a unica tabela existente.")

    proc_ids = [
        int(x[0])
        for x in (
            db.query(Procedimento.id)
            .filter(
                Procedimento.clinica_id == clinica_id,
                Procedimento.tabela_id == int(tabela.id),
            )
            .all()
        )
    ]
    if proc_ids:
        (
            db.query(ProcedimentoMaterial)
            .filter(ProcedimentoMaterial.procedimento_id.in_(proc_ids))
            .delete(synchronize_session=False)
        )
        (
            db.query(Procedimento)
            .filter(
                Procedimento.clinica_id == clinica_id,
                Procedimento.tabela_id == int(tabela.id),
            )
            .delete(synchronize_session=False)
        )

    db.delete(tabela)
    if int(codigo) == PRIVATE_TABLE_CODE:
        clinica = db.query(Clinica).filter(Clinica.id == clinica_id).first()
        if clinica:
            clinica.nome_tabela_procedimentos = "Tabela Exemplo"
    db.commit()
    return {"detail": "Tabela excluida com sucesso."}


@router.get("")
def listar_procedimentos(
    q: str = Query(default=""),
    tabela_id: str = Query(default="1"),
    especialidade: str = Query(default=""),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = current_user.clinica_id
    _garantir_tabelas_clinica(db, clinica_id)
    tabela_resolvida = _resolver_tabela_id(tabela_id, default=1)
    especialidade_filtro = _normalizar_especialidade(especialidade)

    query = db.query(Procedimento).filter(Procedimento.clinica_id == clinica_id)
    if tabela_resolvida > 0:
        tabela = _load_tabela_or_404(db, clinica_id, tabela_resolvida)
        query = query.filter(Procedimento.tabela_id == int(tabela.id))
    if especialidade_filtro:
        query = query.filter(Procedimento.especialidade == especialidade_filtro)
    termo = (q or "").strip()
    if termo:
        like = f"%{termo}%"
        query = query.filter(Procedimento.nome.ilike(like))
    itens = query.all()
    itens.sort(key=lambda x: _chave_ordenacao(x.nome))
    return [_procedimento_to_dict(db, x) for x in itens]


@router.get("/proximo-codigo")
def proximo_codigo(
    tabela_id: str = Query(default="1"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = current_user.clinica_id
    _garantir_tabelas_clinica(db, clinica_id)
    tabela_resolvida = _resolver_tabela_id(tabela_id, default=1)
    tabela = _load_tabela_or_404(db, clinica_id, tabela_resolvida)
    _validar_tabela_ativa(tabela)
    codigos = (
        db.query(Procedimento.codigo)
        .filter(
            Procedimento.clinica_id == clinica_id,
            Procedimento.tabela_id == int(tabela.id),
        )
        .order_by(Procedimento.codigo.asc())
        .all()
    )
    esperado = 1
    for (codigo,) in codigos:
        if int(codigo or 0) != esperado:
            break
        esperado += 1
    return {"codigo": esperado}


@router.get("/dashboard")
def dashboard_lucratividade(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = current_user.clinica_id
    cenario = db.query(Cenario).filter(Cenario.clinica_id == clinica_id).first()

    procedimentos = (
        db.query(Procedimento)
        .filter(Procedimento.clinica_id == clinica_id)
        .all()
    )

    custo_material_por_proc: dict[int, float] = defaultdict(float)
    vinculos = (
        db.query(ProcedimentoMaterial)
        .join(Material, Material.id == ProcedimentoMaterial.material_id)
        .filter(ProcedimentoMaterial.clinica_id == clinica_id)
        .all()
    )
    for vinc in vinculos:
        custo_material_por_proc[int(vinc.procedimento_id)] += float(vinc.quantidade or 0) * float(
            (vinc.material.custo if vinc.material else 0) or 0
        )

    itens = [
        _calcular_financeiro_dashboard(proc, cenario, custo_material_por_proc.get(int(proc.id), 0.0))
        for proc in procedimentos
    ]
    itens.sort(key=lambda x: _chave_ordenacao(x["nome"]))

    grafico = sorted(itens, key=lambda x: float(x["lucro_liquido"] or 0), reverse=True)

    return {
        "itens": itens,
        "grafico": grafico,
    }


@router.get("/relatorio-tabela")
def relatorio_tabela_procedimentos(
    tabela_id: str = Query(...),
    especialidade: str = Query(default=""),
    ordem: str = Query(default="Intervenção"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = int(current_user.clinica_id)
    _garantir_tabelas_clinica(db, clinica_id)
    tabela_codigo_param = _resolver_tabela_id(tabela_id, default=1)
    tabela_atual = _load_tabela_or_404(db, clinica_id, tabela_codigo_param)
    tabela_id_real = int(tabela_atual.id or 0)

    tabela_codigo = int(tabela_atual.codigo or 0)
    tabela_nome = str(tabela_atual.nome or "").strip()
    indice_sigla = str(
        (dados_indice_por_numero(db, clinica_id, tabela_atual.nro_indice) or {}).get("sigla") or "R$"
    )
    especialidades_por_codigo = _mapa_especialidades(db, clinica_id)
    especialidade_filtro = _normalizar_especialidade(especialidade)

    query = (
        db.query(Procedimento)
        .filter(
            Procedimento.clinica_id == clinica_id,
            Procedimento.tabela_id == tabela_id_real,
        )
    )
    if especialidade_filtro:
        query = query.filter(Procedimento.especialidade == especialidade_filtro)
    procedimentos = query.order_by(Procedimento.nome.asc(), Procedimento.id.asc()).all()

    proc_ids = [int(x.id) for x in procedimentos]
    generico_ids = [int(x.procedimento_generico_id or 0) for x in procedimentos if int(x.procedimento_generico_id or 0) > 0]
    generico_codigo_por_id = {
        int(gid): str(codigo or "").strip().zfill(4)
        for gid, codigo in (
            db.query(ProcedimentoGenerico.id, ProcedimentoGenerico.codigo)
            .filter(
                ProcedimentoGenerico.clinica_id == clinica_id,
                ProcedimentoGenerico.id.in_(generico_ids or [0]),
            )
            .all()
        )
        if int(gid or 0) > 0 and str(codigo or "").strip()
    }
    custo_material_por_proc = _mapa_custo_material_por_proc(db, clinica_id, proc_ids)
    custo_material_por_generico = _mapa_custo_material_por_generico(db, clinica_id, generico_ids)
    custo_material_canonico = _carregar_custo_material_canonico_genericos()

    tabela_particular = (
        db.query(ProcedimentoTabela)
        .filter(
            ProcedimentoTabela.clinica_id == clinica_id,
            ProcedimentoTabela.codigo == PRIVATE_TABLE_CODE,
        )
        .first()
    )
    tabela_particular_id = int(getattr(tabela_particular, "id", 0) or 0)
    mapa_preco_particular = _mapa_preco_particular_por_chave(db, clinica_id, tabela_particular_id)

    cenario = (
        db.query(Cenario)
        .filter(Cenario.clinica_id == clinica_id)
        .order_by(Cenario.id.asc())
        .first()
    )
    cfph = float(getattr(cenario, "cfph", 0) or 0)
    cfpm = float(getattr(cenario, "cfpm", 0) or 0)
    cfpm_relatorio = (cfph / 60.0) if cfph > 0 else cfpm
    ir_pct = float(getattr(cenario, "ir", 0) or 0)
    cd_pct = float(getattr(cenario, "cd", 0) or 0)
    cartao_pct = float(getattr(cenario, "cartao", 0) or 0)

    itens: list[dict] = []
    for proc in procedimentos:
        preco_interv = float(proc.preco or 0)
        preco_particular = _resolver_preco_particular(proc, tabela_codigo, mapa_preco_particular)
        tempo = float(proc.tempo or 0)
        custo_fixo = cfpm_relatorio * tempo
        generico_id = int(proc.procedimento_generico_id or 0)
        custo_mat = float(custo_material_por_proc.get(int(proc.id), 0.0) or 0.0)
        codigo_generico = generico_codigo_por_id.get(generico_id, "")
        custo_mat_canonico = float(custo_material_canonico.get(codigo_generico, 0.0) or 0.0) if codigo_generico else 0.0
        if custo_mat_canonico > 0:
            custo_mat = custo_mat_canonico
        elif custo_mat <= 0 and generico_id > 0:
            custo_mat = float(custo_material_por_generico.get(generico_id, 0.0) or 0.0)
        custo_prot = float(proc.custo_lab or 0)
        imp_diretos = 0.0
        custo_total = custo_fixo + custo_mat + custo_prot
        lucro_bruto = preco_interv - custo_total
        lucro_liquido = lucro_bruto
        especialidade_codigo = str(proc.especialidade or "").strip()

        itens.append(
            {
                "Tabela": tabela_nome,
                "Código": int(proc.codigo or 0),
                "Intervenção": str(proc.nome or "").strip(),
                "Especialidade": str(especialidades_por_codigo.get(especialidade_codigo) or especialidade_codigo or "").strip(),
                "Tempo": int(proc.tempo or 0),
                "Índice": indice_sigla,
                "Val paciente": preco_particular,
                "Val paciente (R$)": preco_particular,
                "Val convênio %": 0.0,
                "Val convênio (R$)": float(proc.valor_repasse or 0),
                "Val inter (R$)": preco_interv,
                "Cst fixo (R$)": custo_fixo,
                "Cst fixo %": _pct(custo_fixo, preco_interv),
                "Cst mat (R$)": custo_mat,
                "Cst mat %": _pct(custo_mat, preco_interv),
                "Cst prot (R$)": custo_prot,
                "Cst prot %": _pct(custo_prot, preco_interv),
                "Imp. diretos (R$)": imp_diretos,
                "Lucro (R$)": lucro_liquido,
                "Lucro mens (R$)": 0.0,
            }
        )

    itens = _ordenar_relatorio_proc(itens, ordem)
    return {
        "itens": itens,
        "metadados": {
            "tabela_id": tabela_id_real,
            "tabela_codigo": tabela_codigo,
            "tabela_nome": tabela_nome,
            "especialidade": especialidade_filtro,
            "indice": indice_sigla,
            "ordem": str(ordem or "").strip() or "Intervenção",
            "campos": PROC_RELATORIO_CAMPOS,
            "usa_formula_candidata": True,
                "observacao": (
                    "Val inter foi tratado como valor da tabela selecionada; "
                    "Val paciente como valor correspondente da tabela PARTICULAR; "
                    "Cst mat usa vínculo direto do procedimento e, quando vazio, herda materiais do procedimento genérico; "
                    "Imp. diretos permanece zerado nesta visualização para seguir o padrão observado no Easy; "
                    "Cst fixo deriva de CFPH/60 quando CFPH estiver preenchido para reduzir divergência por arredondamento do CFPM."
                ),
        },
    }


@router.get("/filtros")
def listar_filtros(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _garantir_tabelas_clinica(db, current_user.clinica_id)
    return {
        "tabelas": _listar_tabelas_procedimentos(db, current_user.clinica_id),
        "especialidades": _listar_especialidades(db, current_user.clinica_id),
        "tipos_tiss": _listar_tipos_tiss(db),
        "indices": _listar_indices_moeda(db, current_user.clinica_id),
    }


@router.get("/{procedimento_id}")
def detalhar_procedimento(
    procedimento_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    proc = _load_proc_or_404(db, current_user.clinica_id, procedimento_id)
    return _procedimento_com_vinculos(db, proc)


@router.post("")
def criar_procedimento(
    payload: ProcedimentoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = current_user.clinica_id
    _garantir_tabelas_clinica(db, clinica_id)
    tabela_resolvida = _resolver_tabela_id(payload.tabela_id, default=1)
    tabela = _load_tabela_or_404(db, clinica_id, tabela_resolvida)
    _validar_tabela_ativa(tabela)
    nome = (payload.nome or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome.")
    if _proc_codigo_em_uso(db, clinica_id, int(tabela.id), int(payload.codigo)):
        raise HTTPException(status_code=400, detail="O codigo informado ja esta em uso.")

    especialidade = _normalizar_especialidade(payload.especialidade) or None
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    generico_id = int(payload.procedimento_generico_id or 0) or None
    tem_vinculos_generico = False
    if generico_id:
        generico_existe = (
            db.query(ProcedimentoGenerico.id)
            .filter(
                ProcedimentoGenerico.id == generico_id,
                ProcedimentoGenerico.clinica_id == clinica_id,
            )
            .first()
        )
        if not generico_existe:
            raise HTTPException(status_code=404, detail="Procedimento genérico não encontrado para esta clínica.")
        tem_vinculos_generico = (
            db.query(ProcedimentoGenericoMaterial.id)
            .filter(
                ProcedimentoGenericoMaterial.procedimento_generico_id == generico_id,
                ProcedimentoGenericoMaterial.clinica_id == clinica_id,
            )
            .first()
            is not None
        )
    proc = Procedimento(
        codigo=int(payload.codigo),
        nome=nome,
        tempo=int(payload.tempo or 0),
        preco=float(payload.preco or 0),
        custo=float(payload.custo or 0),
        custo_lab=float(payload.custo_lab or 0),
        tabela_id=int(tabela.id),
        especialidade=especialidade,
        procedimento_generico_id=generico_id,
        simbolo_grafico=(payload.simbolo_grafico or "").strip() or None,
        simbolo_grafico_legacy_id=int(payload.simbolo_grafico_legacy_id or 0) or None,
        mostrar_simbolo=bool(payload.mostrar_simbolo if payload.mostrar_simbolo is not None else (payload.simbolo_grafico or "").strip()),
        garantia_meses=int(payload.garantia_meses or 0),
        forma_cobranca=_normalizar_forma_cobranca(payload.forma_cobranca),
        valor_repasse=float(payload.valor_repasse or 0),
        preferido=bool(payload.preferido),
        inativo=bool(payload.inativo),
        observacoes=(payload.observacoes or "").strip() or None,
        data_inclusao=agora,
        data_alteracao="",
        clinica_id=clinica_id,
    )
    db.add(proc)
    db.flush()
    if generico_id:
        _aplicar_heranca_procedimento_generico(db, clinica_id, proc, sobrescrever_vinculos=tem_vinculos_generico)
        _sincronizar_generico_com_procedimento(db, clinica_id, proc)
    db.commit()
    db.refresh(proc)
    return _procedimento_com_vinculos(db, proc)


@router.put("/{procedimento_id}")
def atualizar_procedimento(
    procedimento_id: int,
    payload: ProcedimentoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinica_id = current_user.clinica_id
    _garantir_tabelas_clinica(db, clinica_id)
    proc = _load_proc_or_404(db, clinica_id, procedimento_id)
    tabela_atual = (
        db.query(ProcedimentoTabela)
        .filter(
            ProcedimentoTabela.id == int(proc.tabela_id or 0),
            ProcedimentoTabela.clinica_id == clinica_id,
        )
        .first()
    )
    tabela_resolvida = _resolver_tabela_id(payload.tabela_id, default=int(tabela_atual.codigo if tabela_atual else 1))
    tabela = _load_tabela_or_404(db, clinica_id, tabela_resolvida)
    _validar_tabela_ativa(tabela)
    nome = (payload.nome or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome.")
    if _proc_codigo_em_uso(
        db,
        clinica_id,
        int(tabela.id),
        int(payload.codigo),
        ignore_id=proc.id,
    ):
        raise HTTPException(status_code=400, detail="O codigo informado ja esta em uso.")

    generico_anterior = int(proc.procedimento_generico_id or 0)
    generico_novo = int(payload.procedimento_generico_id or 0)
    mudou_generico = generico_anterior != generico_novo
    if generico_novo:
        generico_existe = (
            db.query(ProcedimentoGenerico.id)
            .filter(
                ProcedimentoGenerico.id == generico_novo,
                ProcedimentoGenerico.clinica_id == clinica_id,
            )
            .first()
        )
        if not generico_existe:
            raise HTTPException(status_code=404, detail="Procedimento genérico não encontrado para esta clínica.")
    proc.codigo = int(payload.codigo)
    proc.nome = nome
    proc.tabela_id = int(tabela.id)
    proc.tempo = int(payload.tempo or 0)
    proc.preco = float(payload.preco or 0)
    proc.custo = float(payload.custo or 0)
    proc.custo_lab = float(payload.custo_lab or 0)
    if payload.especialidade is not None:
        proc.especialidade = _normalizar_especialidade(payload.especialidade) or None
    proc.procedimento_generico_id = generico_novo or None
    proc.simbolo_grafico = (payload.simbolo_grafico or "").strip() or None
    proc.simbolo_grafico_legacy_id = int(payload.simbolo_grafico_legacy_id or 0) or None
    proc.mostrar_simbolo = bool(payload.mostrar_simbolo if payload.mostrar_simbolo is not None else proc.simbolo_grafico)
    proc.garantia_meses = int(payload.garantia_meses or 0)
    proc.forma_cobranca = _normalizar_forma_cobranca(payload.forma_cobranca)
    proc.valor_repasse = float(payload.valor_repasse or 0)
    proc.preferido = bool(payload.preferido)
    proc.inativo = bool(payload.inativo)
    proc.observacoes = (payload.observacoes or "").strip() or None
    proc.data_alteracao = datetime.now().strftime("%d/%m/%Y %H:%M")
    if not (proc.data_inclusao or "").strip():
        proc.data_inclusao = proc.data_alteracao
    if generico_novo:
        _aplicar_heranca_procedimento_generico(db, clinica_id, proc, sobrescrever_vinculos=mudou_generico)
        _sincronizar_generico_com_procedimento(db, clinica_id, proc)
    elif mudou_generico:
        (
            db.query(ProcedimentoFase)
            .filter(ProcedimentoFase.procedimento_id == int(proc.id))
            .delete(synchronize_session=False)
        )
    db.commit()
    db.refresh(proc)
    return _procedimento_com_vinculos(db, proc)


@router.delete("/{procedimento_id}")
def excluir_procedimento(
    procedimento_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    proc = _load_proc_or_404(db, current_user.clinica_id, procedimento_id)
    tabela = _load_tabela_or_404(db, current_user.clinica_id, int(proc.tabela_id or 1))
    _validar_tabela_ativa(tabela)
    db.delete(proc)
    db.commit()
    return {"detail": "Procedimento excluido."}


@router.post("/{procedimento_id}/materiais-vinculados")
def vincular_material(
    procedimento_id: int,
    payload: VinculoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    proc = _load_proc_or_404(db, current_user.clinica_id, procedimento_id)
    tabela = _load_tabela_or_404(db, current_user.clinica_id, int(proc.tabela_id or 1))
    _validar_tabela_ativa(tabela)
    mat = _load_material_or_404(db, current_user.clinica_id, payload.material_id)
    qtd = float(payload.quantidade or 0)
    if qtd <= 0:
        raise HTTPException(status_code=400, detail="Informe uma quantidade valida.")

    vinc = ProcedimentoMaterial(
        procedimento_id=proc.id,
        material_id=mat.id,
        quantidade=qtd,
        clinica_id=current_user.clinica_id,
    )
    db.add(vinc)
    db.commit()
    return {"detail": "Material vinculado com sucesso."}


@router.put("/{procedimento_id}/materiais-vinculados/por-codigo/{codigo}")
def atualizar_vinculo_por_codigo(
    procedimento_id: int,
    codigo: str,
    payload: VinculoUpdatePayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    proc = _load_proc_or_404(db, current_user.clinica_id, procedimento_id)
    tabela = _load_tabela_or_404(db, current_user.clinica_id, int(proc.tabela_id or 1))
    _validar_tabela_ativa(tabela)
    qtd = float(payload.quantidade or 0)
    if qtd <= 0:
        raise HTTPException(status_code=400, detail="Informe uma quantidade valida.")

    mat_ids = [
        x[0]
        for x in (
            db.query(Material.id)
            .join(Material.lista)
            .filter(
                Material.codigo == codigo,
                Material.lista.has(clinica_id=current_user.clinica_id),
            )
            .all()
        )
    ]
    if not mat_ids:
        raise HTTPException(status_code=404, detail="Material nao encontrado.")

    vinc = (
        db.query(ProcedimentoMaterial)
        .filter(
            ProcedimentoMaterial.procedimento_id == proc.id,
            ProcedimentoMaterial.material_id.in_(mat_ids),
        )
        .order_by(ProcedimentoMaterial.id.asc())
        .first()
    )
    if not vinc:
        raise HTTPException(status_code=404, detail="Vinculo nao encontrado.")

    vinc.quantidade = qtd
    db.commit()
    return {"detail": "Vinculo atualizado com sucesso."}


@router.delete("/{procedimento_id}/materiais-vinculados/por-codigo/{codigo}")
def desvincular_por_codigo(
    procedimento_id: int,
    codigo: str,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    proc = _load_proc_or_404(db, current_user.clinica_id, procedimento_id)
    tabela = _load_tabela_or_404(db, current_user.clinica_id, int(proc.tabela_id or 1))
    _validar_tabela_ativa(tabela)
    mats_ids = [
        x[0]
        for x in (
            db.query(Material.id)
            .join(Material.lista)
            .filter(
                Material.codigo == codigo,
                Material.lista.has(clinica_id=current_user.clinica_id),
            )
            .all()
        )
    ]
    if not mats_ids:
        return {"detail": "Nenhum material para remover."}

    (
        db.query(ProcedimentoMaterial)
        .filter(
            ProcedimentoMaterial.procedimento_id == proc.id,
            ProcedimentoMaterial.material_id.in_(mats_ids),
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"detail": "Material desvinculado."}
