from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from database import Base


class EtiquetaModelo(Base):
    __tablename__ = "etiqueta_modelo"

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    padrao_id = Column(Integer, ForeignKey("etiqueta_padrao.id"), nullable=True)
    nome = Column(String(80), nullable=False)
    reservado = Column(Boolean, nullable=False, default=False)
    margem_esq = Column(Float, nullable=True)
    margem_sup = Column(Float, nullable=True)
    esp_horizontal = Column(Float, nullable=True)
    esp_vertical = Column(Float, nullable=True)
    nro_colunas = Column(Integer, nullable=True)
    nro_linhas = Column(Integer, nullable=True)
    modelo_documento_id = Column(Integer, ForeignKey("modelos_documento.id"), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    atualizado_em = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    clinica = relationship("Clinica")
    padrao = relationship("EtiquetaPadrao")
    modelo_documento = relationship("ModeloDocumento")
