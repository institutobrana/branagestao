from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class ConvenioOdonto(Base):
    __tablename__ = "convenio_odonto"
    __table_args__ = (
        UniqueConstraint("clinica_id", "source_id", name="uq_convenio_odonto_clinica_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    source_id = Column(Integer, nullable=False, index=True)

    codigo = Column(String(20), nullable=True)
    codigo_ans = Column(String(20), nullable=True)
    nome = Column(String(120), nullable=False)
    razao_social = Column(String(160), nullable=True)
    tipo_logradouro = Column(Integer, nullable=True)
    endereco = Column(String(180), nullable=True)
    numero = Column(String(20), nullable=True)
    complemento = Column(String(120), nullable=True)
    bairro = Column(String(120), nullable=True)
    cep = Column(String(20), nullable=True)
    cnpj = Column(String(30), nullable=True)
    cidade = Column(String(120), nullable=True)
    uf = Column(String(10), nullable=True)
    tipo_fone1 = Column(Integer, nullable=True)
    telefone = Column(String(40), nullable=True)
    contato1 = Column(String(120), nullable=True)
    tipo_fone2 = Column(Integer, nullable=True)
    telefone2 = Column(String(40), nullable=True)
    contato2 = Column(String(120), nullable=True)
    tipo_fone3 = Column(Integer, nullable=True)
    telefone3 = Column(String(40), nullable=True)
    contato3 = Column(String(120), nullable=True)
    tipo_fone4 = Column(Integer, nullable=True)
    telefone4 = Column(String(40), nullable=True)
    contato4 = Column(String(120), nullable=True)
    email = Column(String(180), nullable=True)
    email_tecnico = Column(String(180), nullable=True)
    homepage = Column(String(180), nullable=True)
    inscricao_estadual = Column(String(40), nullable=True)
    inscricao_municipal = Column(String(40), nullable=True)
    tipo_faturamento = Column(Integer, nullable=True)
    historico_nf = Column(Text, nullable=True)
    aviso_tratamento = Column(Text, nullable=True)
    aviso_agenda = Column(Text, nullable=True)
    observacoes = Column(Text, nullable=True)
    inativo = Column(Boolean, nullable=False, default=False)
    data_inclusao = Column(String(30), nullable=True)
    data_alteracao = Column(String(30), nullable=True)

    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    clinica = relationship("Clinica")
    planos = relationship("PlanoOdonto", back_populates="convenio", cascade="all, delete-orphan")
    calendarios_faturamento = relationship(
        "CalendarioFaturamentoOdonto",
        back_populates="convenio",
        cascade="all, delete-orphan",
    )


class PlanoOdonto(Base):
    __tablename__ = "plano_odonto"
    __table_args__ = (
        UniqueConstraint("clinica_id", "source_id", name="uq_plano_odonto_clinica_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    convenio_id = Column(Integer, ForeignKey("convenio_odonto.id"), nullable=True, index=True)
    source_id = Column(Integer, nullable=False, index=True)
    convenio_source_id = Column(Integer, nullable=True, index=True)

    codigo = Column(String(20), nullable=True)
    nome = Column(String(120), nullable=False)
    cobertura = Column(Text, nullable=True)
    inativo = Column(Boolean, nullable=False, default=False)
    data_inclusao = Column(String(30), nullable=True)
    data_alteracao = Column(String(30), nullable=True)

    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    clinica = relationship("Clinica")
    convenio = relationship("ConvenioOdonto", back_populates="planos")


class CalendarioFaturamentoOdonto(Base):
    __tablename__ = "calendario_faturamento_odonto"
    __table_args__ = (
        UniqueConstraint("clinica_id", "source_id", name="uq_calendario_faturamento_odonto_clinica_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    convenio_id = Column(Integer, ForeignKey("convenio_odonto.id"), nullable=False, index=True)
    source_id = Column(Integer, nullable=False, index=True)
    convenio_source_id = Column(Integer, nullable=True, index=True)

    data_fechamento = Column(String(20), nullable=True)
    data_pagamento = Column(String(20), nullable=True)

    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    clinica = relationship("Clinica")
    convenio = relationship("ConvenioOdonto", back_populates="calendarios_faturamento")
