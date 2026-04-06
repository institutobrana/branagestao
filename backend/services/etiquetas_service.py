from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from models.clinica import Clinica
from models.etiqueta_modelo import EtiquetaModelo
from models.etiqueta_padrao import EtiquetaPadrao
from models.modelo_documento import ModeloDocumento


@dataclass(frozen=True)
class EtiquetaPadraoSeed:
    id: int
    nome: str
    margem_esq: float
    margem_sup: float
    esp_horizontal: float
    esp_vertical: float
    nro_colunas: int
    nro_linhas: int
    reservado: bool = True


@dataclass(frozen=True)
class EtiquetaModeloSeed:
    nome: str
    padrao_id: int | None
    margem_esq: float
    margem_sup: float
    esp_horizontal: float
    esp_vertical: float
    nro_colunas: int
    nro_linhas: int
    nome_arquivo: str
    reservado: bool = False


PADROES_EASY = [
    EtiquetaPadraoSeed(1, "Envelope1", 5.0, 5.0, 0.0, 0.0, 1, 1, True),
    EtiquetaPadraoSeed(2, "Envelope2", 10.0, 10.0, 0.0, 0.0, 1, 1, True),
    EtiquetaPadraoSeed(3, "Envelope3", 60.0, 35.0, 0.0, 0.0, 1, 1, True),
    EtiquetaPadraoSeed(4, "Pimaco 6080/6180/6280/62580", 4.8, 12.7, 3.1, 0.0, 3, 10, True),
    EtiquetaPadraoSeed(5, "Pimaco 6081/6181/6281/62581", 4.0, 12.7, 5.2, 0.0, 2, 10, True),
    EtiquetaPadraoSeed(6, "Pimaco A4254/A4354", 4.7, 8.8, 2.6, 0.0, 2, 11, True),
    EtiquetaPadraoSeed(7, "Pimaco A4255/A4355", 7.2, 9.0, 2.6, 0.0, 3, 9, True),
    EtiquetaPadraoSeed(8, "Pimaco A4256/A4356", 7.2, 8.8, 2.6, 0.0, 3, 11, True),
]


MODELOS_EASY = [
    EtiquetaModeloSeed("Envelope1", 1, 5.0, 5.0, 0.0, 0.0, 1, 1, "Envelope.mod", False),
    EtiquetaModeloSeed("Envelope2", 2, 10.0, 10.0, 0.0, 0.0, 1, 1, "Envelope.mod", False),
    EtiquetaModeloSeed("Envelope3", 3, 60.0, 35.0, 0.0, 0.0, 1, 1, "Envelope.mod", False),
    EtiquetaModeloSeed("Pimaco completo (6080)", 4, 4.8, 12.7, 3.1, 0.0, 3, 10, "Pimaco6080.mod", False),
    EtiquetaModeloSeed("Pimaco completo (6081)", 5, 4.0, 12.7, 5.2, 0.0, 2, 10, "Pimaco6081.mod", False),
    EtiquetaModeloSeed("Pimaco completo (A4254)", 6, 4.7, 8.8, 2.6, 0.0, 2, 11, "PimacoA4254.mod", False),
    EtiquetaModeloSeed("Pimaco completo (A4255)", 7, 7.2, 9.0, 2.6, 0.0, 3, 9, "PimacoA4255.mod", False),
    EtiquetaModeloSeed("Pimaco completo (A4256)", 8, 7.2, 8.8, 2.6, 0.0, 3, 11, "PimacoA4256.mod", False),
    EtiquetaModeloSeed("ETIQUETA PRONTUÁRIO", None, 5.0, 15.0, 2.0, 0.0, 2, 5, "ETIQUETA-pimaco6083.mod", False),
]


def _resolver_modelo_documento_id(db: Session, clinica_id: int, nome_arquivo: str) -> int | None:
    arquivo = (nome_arquivo or "").strip()
    if not arquivo:
        return None
    row = (
        db.query(ModeloDocumento)
        .filter(
            ModeloDocumento.tipo_modelo == "etiquetas",
            ModeloDocumento.nome_arquivo == arquivo,
            ModeloDocumento.clinica_id == clinica_id,
            ModeloDocumento.ativo.is_(True),
        )
        .first()
    )
    if row:
        return int(row.id)
    row = (
        db.query(ModeloDocumento)
        .filter(
            ModeloDocumento.tipo_modelo == "etiquetas",
            ModeloDocumento.nome_arquivo == arquivo,
            ModeloDocumento.clinica_id.is_(None),
            ModeloDocumento.ativo.is_(True),
        )
        .first()
    )
    return int(row.id) if row else None


def garantir_padroes_etiqueta(db: Session) -> None:
    existentes = {int(p.id): p for p in db.query(EtiquetaPadrao).all()}
    for item in PADROES_EASY:
        row = existentes.get(item.id)
        if row is None:
            db.add(
                EtiquetaPadrao(
                    id=item.id,
                    nome=item.nome,
                    reservado=bool(item.reservado),
                    margem_esq=item.margem_esq,
                    margem_sup=item.margem_sup,
                    esp_horizontal=item.esp_horizontal,
                    esp_vertical=item.esp_vertical,
                    nro_colunas=item.nro_colunas,
                    nro_linhas=item.nro_linhas,
                )
            )
            continue
        row.nome = item.nome
        row.reservado = bool(item.reservado)
        row.margem_esq = item.margem_esq
        row.margem_sup = item.margem_sup
        row.esp_horizontal = item.esp_horizontal
        row.esp_vertical = item.esp_vertical
        row.nro_colunas = item.nro_colunas
        row.nro_linhas = item.nro_linhas


def garantir_modelos_etiqueta_clinica(db: Session, clinica_id: int) -> None:
    existentes = (
        db.query(EtiquetaModelo)
        .filter(EtiquetaModelo.clinica_id == clinica_id)
        .all()
    )
    por_nome = {str(item.nome or "").strip().lower(): item for item in existentes}
    for seed in MODELOS_EASY:
        chave = seed.nome.strip().lower()
        if chave in por_nome:
            continue
        modelo_doc_id = _resolver_modelo_documento_id(db, clinica_id, seed.nome_arquivo)
        if modelo_doc_id is None:
            continue
        db.add(
            EtiquetaModelo(
                clinica_id=clinica_id,
                padrao_id=seed.padrao_id,
                nome=seed.nome,
                reservado=bool(seed.reservado),
                margem_esq=seed.margem_esq,
                margem_sup=seed.margem_sup,
                esp_horizontal=seed.esp_horizontal,
                esp_vertical=seed.esp_vertical,
                nro_colunas=seed.nro_colunas,
                nro_linhas=seed.nro_linhas,
                modelo_documento_id=modelo_doc_id,
                ativo=True,
            )
        )


def garantir_modelos_etiqueta_todas_clinicas(db: Session) -> None:
    clinica_ids = [int(item[0]) for item in db.query(Clinica.id).all() if item and item[0]]
    for clinica_id in clinica_ids:
        garantir_modelos_etiqueta_clinica(db, clinica_id)


def garantir_etiquetas_padrao_modelos(db: Session) -> None:
    garantir_padroes_etiqueta(db)
    garantir_modelos_etiqueta_todas_clinicas(db)
