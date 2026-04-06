from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from database import Base


class ModeloDocumento(Base):
    __tablename__ = "modelos_documento"

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=True, index=True)
    tipo_modelo = Column(String(40), nullable=False, index=True)
    codigo = Column(String(80), nullable=True)
    nome_exibicao = Column(String(180), nullable=False)
    nome_arquivo = Column(String(255), nullable=False)
    extensao = Column(String(20), nullable=True)
    caminho_arquivo = Column(Text, nullable=False)
    ativo = Column(Boolean, nullable=False, default=True)
    padrao_clinica = Column(Boolean, nullable=False, default=False)
    origem = Column(String(30), nullable=False, default="base")
    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    atualizado_em = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    clinica = relationship("Clinica")
