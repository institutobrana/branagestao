from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class UnidadeAtendimento(Base):
    __tablename__ = "unidade_atendimento"
    __table_args__ = (
        UniqueConstraint("clinica_id", "source_id", name="uq_unidade_atendimento_clinica_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    source_id = Column(Integer, nullable=False, index=True)

    codigo = Column(String(20), nullable=True)
    nome = Column(String(180), nullable=False)

    logradouro_tipo = Column(String(60), nullable=True)
    endereco = Column(String(180), nullable=True)
    numero = Column(String(30), nullable=True)
    complemento = Column(String(120), nullable=True)
    bairro = Column(String(120), nullable=True)
    cidade = Column(String(120), nullable=True)
    cep = Column(String(20), nullable=True)
    uf = Column(String(10), nullable=True)

    fone1_tipo = Column(String(40), nullable=True)
    fone1 = Column(String(40), nullable=True)
    contato1 = Column(String(120), nullable=True)
    fone2_tipo = Column(String(40), nullable=True)
    fone2 = Column(String(40), nullable=True)
    contato2 = Column(String(120), nullable=True)
    fone3_tipo = Column(String(40), nullable=True)
    fone3 = Column(String(40), nullable=True)
    contato3 = Column(String(120), nullable=True)
    fone4_tipo = Column(String(40), nullable=True)
    fone4 = Column(String(40), nullable=True)
    contato4 = Column(String(120), nullable=True)

    qtd_sala = Column(Integer, nullable=False, default=0)
    inativo = Column(Boolean, nullable=False, default=False)
    data_inclusao = Column(String(30), nullable=True)
    data_alteracao = Column(String(30), nullable=True)

    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    clinica = relationship("Clinica")
