from calendar import monthrange
from datetime import date, datetime
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.financeiro import CategoriaFinanceira, GrupoFinanceiro, ItemAuxiliar, Lancamento
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access

router = APIRouter(
    prefix="/financeiro",
    tags=["financeiro"],
    dependencies=[Depends(require_module_access("financeiro"))],
)

CONTA_CLINICA = "CLINICA"
CONTA_CIRURGIAO = "CIRURGIAO"


class LancamentoPayload(BaseModel):
    categoria_id: int
    historico: str
    valor: float
    tipo: str
    conta: str
    situacao: str = "Aberto"
    forma_pagamento: str | None = None
    documento: str | None = None
    referencia: str | None = None
    complemento: str | None = None
    tributavel: int = 0
    data_lancamento: str
    data_vencimento: str
    data_pagamento: str | None = None
    parcelas: int = 1


def _normalizar_conta(valor: str | None, default: str = CONTA_CLINICA) -> str:
    base = _norm(valor or "")
    if base in ("clinica", "empresarial"):
        return CONTA_CLINICA
    if base in ("cirurgiao", "pessoal"):
        return CONTA_CIRURGIAO
    return default


def _conta_variantes(valor: str | None) -> list[str]:
    canon = _normalizar_conta(valor)
    if canon == CONTA_CIRURGIAO:
        return [CONTA_CIRURGIAO, "CIRURGIÃO", "PESSOAL"]
    return [CONTA_CLINICA, "CLÍNICA", "EMPRESARIAL"]


def _parse_iso_date(texto: str) -> date:
    try:
        return datetime.strptime((texto or "").strip(), "%Y-%m-%d").date()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Data invalida. Use YYYY-MM-DD.") from exc


def _parse_iso_date_optional(texto: str | None) -> str | None:
    valor = (texto or "").strip()
    if not valor:
        return None
    return _parse_iso_date(valor).strftime("%Y-%m-%d")


def _parse_mixed_date_optional(texto: str | None) -> date | None:
    valor = (texto or "").strip()
    if not valor:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(valor, fmt).date()
        except Exception:
            continue
    return None


def _add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, monthrange(year, month)[1])
    return date(year, month, day)


def _categoria_da_clinica_or_404(db: Session, clinica_id: int, categoria_id: int) -> CategoriaFinanceira:
    categoria = (
        db.query(CategoriaFinanceira)
        .filter(
            CategoriaFinanceira.id == categoria_id,
            CategoriaFinanceira.clinica_id == clinica_id,
        )
        .first()
    )
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria nao encontrada.")
    return categoria


def _lancamento_da_clinica_or_404(db: Session, clinica_id: int, lancamento_id: int) -> Lancamento:
    lanc = (
        db.query(Lancamento)
        .filter(
            Lancamento.id == lancamento_id,
            Lancamento.clinica_id == clinica_id,
        )
        .first()
    )
    if not lanc:
        raise HTTPException(status_code=404, detail="Lancamento nao encontrado.")
    return lanc


@router.get("/categorias")
def listar_categorias(
    tipo: str = Query(default=""),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(CategoriaFinanceira).filter(CategoriaFinanceira.clinica_id == current_user.clinica_id)
    tipo_norm = (tipo or "").strip().lower()
    if tipo_norm:
        if tipo_norm in ("entrada", "credito", "crédito"):
            query = query.filter(CategoriaFinanceira.tipo == "Entrada")
        elif tipo_norm in ("saida", "saída", "debito", "débito"):
            query = query.filter(CategoriaFinanceira.tipo == "Saída")
    itens = query.order_by(CategoriaFinanceira.nome.asc()).all()
    return [
        {
            "id": c.id,
            "nome": c.nome,
            "tipo": c.tipo,
            "tributavel": bool(c.tributavel),
            "grupo_id": c.grupo_id,
        }
        for c in itens
    ]


@router.get("/formas-pagamento")
def listar_formas_pagamento(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    itens = (
        db.query(ItemAuxiliar)
        .filter(
            ItemAuxiliar.clinica_id == current_user.clinica_id,
            ItemAuxiliar.tipo == "Tipos de pagamento",
        )
        .order_by(ItemAuxiliar.descricao.asc())
        .all()
    )
    return [{"codigo": x.codigo, "descricao": x.descricao} for x in itens]


@router.get("/formas-pagamento-usadas")
def listar_formas_pagamento_usadas(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    itens = (
        db.query(Lancamento.forma_pagamento)
        .filter(
            Lancamento.clinica_id == current_user.clinica_id,
            Lancamento.forma_pagamento.isnot(None),
            Lancamento.forma_pagamento != "",
        )
        .distinct()
        .all()
    )
    valores = sorted({(x[0] or "").strip() for x in itens if (x[0] or "").strip()})
    return [{"descricao": v} for v in valores]


@router.get("/situacoes")
def listar_situacoes():
    return ["Aberto", "Efetivado"]


@router.get("/lancamentos")
def listar_lancamentos(
    mes: int,
    ano: int,
    conta: str = Query(default=CONTA_CLINICA),
    filtro: str = Query(default="Todos os lançamentos"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prefixo_data = f"{ano:04d}-{mes:02d}-"
    conta_var = _conta_variantes(conta)
    query = (
        db.query(Lancamento)
        .join(CategoriaFinanceira, CategoriaFinanceira.id == Lancamento.categoria_id)
        .join(GrupoFinanceiro, GrupoFinanceiro.id == CategoriaFinanceira.grupo_id)
        .filter(
            Lancamento.clinica_id == current_user.clinica_id,
            Lancamento.conta.in_(conta_var),
            Lancamento.data_lancamento.like(f"{prefixo_data}%"),
        )
    )

    filtro_norm = _norm(filtro)
    if "tributave" in filtro_norm:
        query = query.filter(Lancamento.tributavel == 1)
    elif "debitos" in filtro_norm or "debito" in filtro_norm:
        query = query.filter(Lancamento.tipo == "debito")
    elif "creditos" in filtro_norm or "credito" in filtro_norm:
        query = query.filter(Lancamento.tipo == "credito")
    elif "despesas pessoais" in filtro_norm or "despesas do cirurgiao" in filtro_norm:
        query = query.filter(GrupoFinanceiro.tipo == "Pessoal")

    itens = query.order_by(Lancamento.data_lancamento.asc(), Lancamento.id.asc()).all()

    total_entrada = 0.0
    total_saida = 0.0
    rows = []
    for l in itens:
        if (l.tipo or "").lower() == "debito":
            total_saida += float(l.valor or 0)
        else:
            total_entrada += float(l.valor or 0)
        rows.append(
            {
                "id": l.id,
                "categoria_id": l.categoria_id,
                "categoria_nome": l.categoria.nome if l.categoria else "",
                "grupo_nome": l.categoria.grupo.nome if l.categoria and l.categoria.grupo else "",
                "historico": l.historico or "",
                "valor": float(l.valor or 0),
                "tipo": l.tipo or "",
                "conta": _normalizar_conta(l.conta),
                "situacao": l.situacao or "Aberto",
                "forma_pagamento": l.forma_pagamento,
                "documento": l.documento,
                "referencia": l.referencia,
                "complemento": l.complemento,
                "tributavel": int(l.tributavel or 0),
                "data_lancamento": l.data_lancamento,
                "data_vencimento": l.data_vencimento,
                "data_pagamento": l.data_pagamento,
                "data_inclusao": l.data_inclusao,
                "data_alteracao": l.data_alteracao,
                "parcelado": int(l.parcelado or 0),
                "qtd_parcelas": int(l.qtd_parcelas or 1),
                "parcela_atual": int(l.parcela_atual or 1),
            }
        )
    return {
        "itens": rows,
        "total_entrada": total_entrada,
        "total_saida": total_saida,
        "saldo": total_entrada - total_saida,
    }


@router.get("/relatorio-cc")
def relatorio_conta_corrente(
    conta: str = Query(default=""),
    tipo_lancamento: str = Query(default=""),
    grupo: str = Query(default=""),
    tipo_grupo: str = Query(default=""),
    categoria: str = Query(default=""),
    situacao: str = Query(default=""),
    forma_pagamento: str = Query(default=""),
    referencia: str = Query(default=""),
    complemento: str = Query(default=""),
    documento: str = Query(default=""),
    data_venc_ini: str = Query(default=""),
    data_venc_fim: str = Query(default=""),
    data_lanc_ini: str = Query(default=""),
    data_lanc_fim: str = Query(default=""),
    tributavel: str = Query(default="todos"),
    ordem: str = Query(default="Data"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Lancamento)
        .join(CategoriaFinanceira, CategoriaFinanceira.id == Lancamento.categoria_id)
        .join(GrupoFinanceiro, GrupoFinanceiro.id == CategoriaFinanceira.grupo_id)
        .filter(Lancamento.clinica_id == current_user.clinica_id)
    )

    if (conta or "").strip():
        query = query.filter(Lancamento.conta.in_(_conta_variantes(conta)))

    if (tipo_lancamento or "").strip():
        tipo_norm = _norm(tipo_lancamento)
        if "credito" in tipo_norm:
            query = query.filter(Lancamento.tipo == "credito")
        elif "debito" in tipo_norm:
            query = query.filter(Lancamento.tipo == "debito")

    if (grupo or "").strip():
        query = query.filter(GrupoFinanceiro.nome == (grupo or "").strip())

    if (tipo_grupo or "").strip():
        query = query.filter(GrupoFinanceiro.tipo == (tipo_grupo or "").strip())

    if (categoria or "").strip():
        query = query.filter(CategoriaFinanceira.nome == (categoria or "").strip())

    if (situacao or "").strip():
        query = query.filter(Lancamento.situacao == (situacao or "").strip())

    if (forma_pagamento or "").strip():
        query = query.filter(Lancamento.forma_pagamento == (forma_pagamento or "").strip())

    if (referencia or "").strip():
        query = query.filter(Lancamento.referencia.contains((referencia or "").strip()))

    if (complemento or "").strip():
        query = query.filter(Lancamento.complemento.contains((complemento or "").strip()))

    if (documento or "").strip():
        query = query.filter(Lancamento.documento.contains((documento or "").strip()))

    venc_ini = _parse_iso_date_optional(data_venc_ini)
    venc_fim = _parse_iso_date_optional(data_venc_fim)
    if venc_ini and venc_fim:
        query = query.filter(Lancamento.data_vencimento.between(venc_ini, venc_fim))
    elif venc_ini:
        query = query.filter(Lancamento.data_vencimento >= venc_ini)
    elif venc_fim:
        query = query.filter(Lancamento.data_vencimento <= venc_fim)

    lanc_ini = _parse_iso_date_optional(data_lanc_ini)
    lanc_fim = _parse_iso_date_optional(data_lanc_fim)
    if lanc_ini and lanc_fim:
        query = query.filter(Lancamento.data_lancamento.between(lanc_ini, lanc_fim))
    elif lanc_ini:
        query = query.filter(Lancamento.data_lancamento >= lanc_ini)
    elif lanc_fim:
        query = query.filter(Lancamento.data_lancamento <= lanc_fim)

    trib_norm = _norm(tributavel)
    if trib_norm in ("1", "sim", "tributavel", "tributaveis"):
        query = query.filter(Lancamento.tributavel == 1)
    elif trib_norm in ("0", "nao", "nao_tributavel", "nao_tributaveis"):
        query = query.filter(Lancamento.tributavel == 0)

    ordem_norm = _norm(ordem)
    mapa_ordem = {
        "data": Lancamento.data_lancamento,
        "historico": Lancamento.historico,
        "categoria": CategoriaFinanceira.nome,
        "grupo": GrupoFinanceiro.nome,
        "valor": Lancamento.valor,
    }
    coluna_ordem = mapa_ordem.get(ordem_norm, Lancamento.data_lancamento)
    itens = query.order_by(coluna_ordem.asc(), Lancamento.id.asc()).all()

    total_credito = 0.0
    total_debito = 0.0
    saldo = 0.0
    rows = []
    for l in itens:
        valor = float(l.valor or 0)
        eh_debito = (l.tipo or "").lower() == "debito"
        if eh_debito:
            total_debito += valor
            saldo -= valor
        else:
            total_credito += valor
            saldo += valor

        rows.append(
            {
                "id": l.id,
                "conta": _normalizar_conta(l.conta),
                "categoria_nome": l.categoria.nome if l.categoria else "",
                "grupo_nome": l.categoria.grupo.nome if l.categoria and l.categoria.grupo else "",
                "historico": l.historico or "",
                "tipo": l.tipo or "",
                "tipo_descricao": "Saída" if eh_debito else "Entrada",
                "valor": valor,
                "debito": valor if eh_debito else 0.0,
                "credito": valor if not eh_debito else 0.0,
                "saldo": saldo,
                "situacao": l.situacao or "",
                "forma_pagamento": l.forma_pagamento or "",
                "documento": l.documento or "",
                "referencia": l.referencia or "",
                "complemento": l.complemento or "",
                "tributavel": int(l.tributavel or 0),
                "data_lancamento": l.data_lancamento or "",
                "data_vencimento": l.data_vencimento or "",
                "data_pagamento": l.data_pagamento or "",
                "data_inclusao": l.data_inclusao or "",
                "data_alteracao": l.data_alteracao or "",
            }
        )

    return {
        "itens": rows,
        "total_credito": total_credito,
        "total_debito": total_debito,
        "saldo_final": saldo,
    }


@router.get("/fluxo-caixa")
def analise_fluxo_caixa(
    conta: str = Query(default=CONTA_CLINICA),
    mes_inicio: int = Query(default=1, ge=1, le=12),
    mes_fim: int = Query(default=12, ge=1, le=12),
    ano_inicio: int = Query(default=datetime.now().year),
    ano_fim: int = Query(default=datetime.now().year),
    tipo_grupo: str = Query(default="CRÉDITO"),
    tipo_categoria: str = Query(default="CRÉDITO"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conta_norm = _normalizar_conta(conta)
    conta_var = _conta_variantes(conta_norm)
    tipo_grupo_norm = _norm(tipo_grupo)
    tipo_categoria_norm = _norm(tipo_categoria)

    lancamentos = (
        db.query(Lancamento)
        .join(CategoriaFinanceira, CategoriaFinanceira.id == Lancamento.categoria_id)
        .join(GrupoFinanceiro, GrupoFinanceiro.id == CategoriaFinanceira.grupo_id)
        .filter(
            Lancamento.clinica_id == current_user.clinica_id,
            Lancamento.conta.in_(conta_var),
            Lancamento.data_pagamento.isnot(None),
            Lancamento.data_pagamento != "",
        )
        .all()
    )

    registros: list[tuple[Lancamento, date]] = []
    for lanc in lancamentos:
        data_pag = _parse_mixed_date_optional(lanc.data_pagamento)
        if not data_pag:
            continue
        if not (ano_inicio <= data_pag.year <= ano_fim):
            continue
        registros.append((lanc, data_pag))

    meses_nome = [
        "Janeiro",
        "Fevereiro",
        "Março",
        "Abril",
        "Maio",
        "Junho",
        "Julho",
        "Agosto",
        "Setembro",
        "Outubro",
        "Novembro",
        "Dezembro",
    ]

    evolucao = []
    for mes in range(mes_inicio, mes_fim + 1):
        total_entrada = 0.0
        total_saida = 0.0
        for lanc, data_pag in registros:
            if data_pag.month != mes:
                continue
            tipo_cat = _norm((lanc.categoria.tipo if lanc.categoria else "") or "")
            valor = float(lanc.valor or 0)
            if tipo_cat == "entrada":
                total_entrada += valor
            elif tipo_cat in ("saida", "saidas"):
                total_saida += valor
        evolucao.append(
            {
                "mes": mes,
                "mes_nome": meses_nome[mes - 1],
                "entrada": total_entrada,
                "saida": total_saida,
            }
        )

    def _filtra_tipo(tipo_norm: str, lanc_tipo: str) -> bool:
        if "credito" in tipo_norm:
            return lanc_tipo == "credito"
        if "debito" in tipo_norm:
            return lanc_tipo == "debito"
        return True

    comparativo_grupo: dict[str, float] = {}
    comparativo_categoria: dict[str, float] = {}

    for lanc, data_pag in registros:
        if not (mes_inicio <= data_pag.month <= mes_fim):
            continue
        lanc_tipo = _norm((lanc.tipo or "").strip())
        valor = float(lanc.valor or 0)
        if valor <= 0:
            continue

        if _filtra_tipo(tipo_grupo_norm, lanc_tipo):
            nome_grupo = (
                ((lanc.categoria.grupo.nome if lanc.categoria and lanc.categoria.grupo else "") or "OUTROS")
                .strip()
                .upper()
            )
            comparativo_grupo[nome_grupo] = comparativo_grupo.get(nome_grupo, 0.0) + valor

        if _filtra_tipo(tipo_categoria_norm, lanc_tipo):
            nome_categoria = (((lanc.categoria.nome if lanc.categoria else "") or "OUTROS").strip().upper())
            comparativo_categoria[nome_categoria] = comparativo_categoria.get(nome_categoria, 0.0) + valor

    return {
        "conta": conta_norm,
        "periodo": {
            "mes_inicio": mes_inicio,
            "mes_fim": mes_fim,
            "ano_inicio": ano_inicio,
            "ano_fim": ano_fim,
        },
        "tipo_grupo": "CRÉDITO" if "credito" in tipo_grupo_norm else ("DÉBITO" if "debito" in tipo_grupo_norm else ""),
        "tipo_categoria": "CRÉDITO" if "credito" in tipo_categoria_norm else ("DÉBITO" if "debito" in tipo_categoria_norm else ""),
        "evolucao": evolucao,
        "comparativo_grupo": [
            {"nome": nome, "valor": valor}
            for nome, valor in comparativo_grupo.items()
            if valor > 0
        ],
        "comparativo_categoria": [
            {"nome": nome, "valor": valor}
            for nome, valor in comparativo_categoria.items()
            if valor > 0
        ],
    }


@router.post("/lancamentos")
def criar_lancamento(
    payload: LancamentoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _categoria_da_clinica_or_404(db, current_user.clinica_id, payload.categoria_id)
    historico = (payload.historico or "").strip()
    if not historico:
        raise HTTPException(status_code=400, detail="Informe o histórico.")
    if float(payload.valor or 0) <= 0:
        raise HTTPException(status_code=400, detail="Informe um valor válido.")

    base_lanc = _parse_iso_date(payload.data_lancamento)
    base_venc = _parse_iso_date(payload.data_vencimento)
    hoje = datetime.utcnow().strftime("%Y-%m-%d")
    parcelas = max(1, int(payload.parcelas or 1))

    for i in range(parcelas):
        d_lanc = _add_months(base_lanc, i)
        d_venc = _add_months(base_venc, i)
        db.add(
            Lancamento(
                clinica_id=current_user.clinica_id,
                categoria_id=int(payload.categoria_id),
                historico=historico,
                valor=float(payload.valor or 0),
                tipo=(payload.tipo or "").strip().lower(),
                conta=_normalizar_conta(payload.conta),
                situacao=(payload.situacao or "Aberto").strip(),
                forma_pagamento=payload.forma_pagamento,
                documento=payload.documento,
                referencia=payload.referencia,
                complemento=payload.complemento,
                tributavel=1 if int(payload.tributavel or 0) else 0,
                parcelado=1 if parcelas > 1 else 0,
                qtd_parcelas=parcelas,
                parcela_atual=i + 1,
                data_lancamento=d_lanc.strftime("%Y-%m-%d"),
                data_vencimento=d_venc.strftime("%Y-%m-%d"),
                data_pagamento=(payload.data_pagamento or d_lanc.strftime("%Y-%m-%d")),
                data_inclusao=hoje,
            )
        )

    db.commit()
    return {"detail": "Lancamento salvo."}


@router.put("/lancamentos/{lancamento_id}")
def atualizar_lancamento(
    lancamento_id: int,
    payload: LancamentoPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _categoria_da_clinica_or_404(db, current_user.clinica_id, payload.categoria_id)
    lanc = _lancamento_da_clinica_or_404(db, current_user.clinica_id, lancamento_id)
    historico = (payload.historico or "").strip()
    if not historico:
        raise HTTPException(status_code=400, detail="Informe o histórico.")
    if float(payload.valor or 0) <= 0:
        raise HTTPException(status_code=400, detail="Informe um valor válido.")

    lanc.categoria_id = int(payload.categoria_id)
    lanc.historico = historico
    lanc.valor = float(payload.valor or 0)
    lanc.tipo = (payload.tipo or "").strip().lower()
    lanc.conta = _normalizar_conta(payload.conta)
    lanc.situacao = (payload.situacao or "Aberto").strip()
    lanc.forma_pagamento = payload.forma_pagamento
    lanc.documento = payload.documento
    lanc.referencia = payload.referencia
    lanc.complemento = payload.complemento
    lanc.tributavel = 1 if int(payload.tributavel or 0) else 0
    lanc.data_lancamento = _parse_iso_date(payload.data_lancamento).strftime("%Y-%m-%d")
    lanc.data_vencimento = _parse_iso_date(payload.data_vencimento).strftime("%Y-%m-%d")
    lanc.data_pagamento = (
        _parse_iso_date(payload.data_pagamento).strftime("%Y-%m-%d")
        if payload.data_pagamento
        else lanc.data_lancamento
    )
    lanc.data_alteracao = datetime.utcnow().strftime("%Y-%m-%d")
    lanc.parcelado = 0
    lanc.qtd_parcelas = 1
    lanc.parcela_atual = 1

    db.commit()
    return {"detail": "Lancamento atualizado."}


@router.delete("/lancamentos/{lancamento_id}")
def excluir_lancamento(
    lancamento_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lanc = _lancamento_da_clinica_or_404(db, current_user.clinica_id, lancamento_id)
    db.delete(lanc)
    db.commit()
    return {"detail": "Lancamento excluido."}
def _norm(texto: str) -> str:
    base = (texto or "").strip().lower()
    base = unicodedata.normalize("NFD", base)
    return "".join(c for c in base if unicodedata.category(c) != "Mn")
