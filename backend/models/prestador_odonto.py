from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class PrestadorOdonto(Base):
    __tablename__ = "prestador_odonto"
    __table_args__ = (
        UniqueConstraint("clinica_id", "source_id", name="uq_prestador_odonto_clinica_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    source_id = Column(Integer, nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)

    codigo = Column(String(20), nullable=True)
    nome = Column(String(160), nullable=False)
    apelido = Column(String(120), nullable=True)
    tipo_prestador = Column(String(80), nullable=True)
    data_inicio = Column(String(20), nullable=True)
    data_termino = Column(String(20), nullable=True)
    inativo = Column(Boolean, nullable=False, default=False)
    executa_procedimento = Column(Boolean, nullable=False, default=True)
    is_system_prestador = Column(Boolean, nullable=False, default=False)

    cro = Column(String(40), nullable=True)
    uf_cro = Column(String(10), nullable=True)
    cpf = Column(String(20), nullable=True)
    rg = Column(String(30), nullable=True)
    inss = Column(String(40), nullable=True)
    ccm = Column(String(40), nullable=True)
    contrato = Column(String(40), nullable=True)
    cnes = Column(String(40), nullable=True)
    cbos = Column(String(120), nullable=True)
    nascimento = Column(String(20), nullable=True)
    sexo = Column(String(20), nullable=True)
    estado_civil = Column(String(40), nullable=True)
    prefixo = Column(String(40), nullable=True)
    data_inclusao = Column(String(30), nullable=True)
    data_alteracao = Column(String(30), nullable=True)
    id_interno = Column(String(40), nullable=True)

    fone1_tipo = Column(String(40), nullable=True)
    fone1 = Column(String(40), nullable=True)
    fone2_tipo = Column(String(40), nullable=True)
    fone2 = Column(String(40), nullable=True)
    email = Column(String(180), nullable=True)
    homepage = Column(String(180), nullable=True)

    logradouro_tipo = Column(String(40), nullable=True)
    endereco = Column(String(180), nullable=True)
    numero = Column(String(20), nullable=True)
    complemento = Column(String(120), nullable=True)
    bairro = Column(String(120), nullable=True)
    cidade = Column(String(120), nullable=True)
    cep = Column(String(20), nullable=True)
    uf = Column(String(10), nullable=True)

    banco = Column(String(120), nullable=True)
    agencia = Column(String(40), nullable=True)
    conta = Column(String(40), nullable=True)
    nome_conta = Column(String(160), nullable=True)
    modo_pagamento = Column(String(80), nullable=True)
    faculdade = Column(String(180), nullable=True)
    formatura = Column(String(20), nullable=True)
    alerta_agendamentos = Column(String(255), nullable=True)
    especialidade = Column(String(80), nullable=True)
    especialidades_json = Column(Text, nullable=True)
    agenda_config_json = Column(Text, nullable=True)
    observacoes = Column(Text, nullable=True)

    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    clinica = relationship("Clinica")
    usuario = relationship("Usuario", foreign_keys=[usuario_id])
    credenciamentos = relationship(
        "PrestadorCredenciamentoOdonto",
        back_populates="prestador",
        cascade="all, delete-orphan",
    )
    comissoes = relationship(
        "PrestadorComissaoOdonto",
        back_populates="prestador",
        cascade="all, delete-orphan",
    )


class PrestadorCredenciamentoOdonto(Base):
    __tablename__ = "prestador_credenciamento_odonto"
    __table_args__ = (
        UniqueConstraint("clinica_id", "source_id", name="uq_prestador_cred_odonto_clinica_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    prestador_id = Column(Integer, ForeignKey("prestador_odonto.id"), nullable=True, index=True)
    convenio_id = Column(Integer, ForeignKey("convenio_odonto.id"), nullable=False, index=True)
    source_id = Column(Integer, nullable=False, index=True)
    prestador_source_id = Column(Integer, nullable=True, index=True)
    convenio_source_id = Column(Integer, nullable=True, index=True)

    codigo = Column(String(20), nullable=True)
    inicio = Column(String(20), nullable=True)
    fim = Column(String(20), nullable=True)
    valor_us = Column(String(30), nullable=True)
    aviso = Column(Text, nullable=True)
    observacoes = Column(Text, nullable=True)
    data_inclusao = Column(String(30), nullable=True)
    data_alteracao = Column(String(30), nullable=True)

    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    clinica = relationship("Clinica")
    prestador = relationship("PrestadorOdonto", back_populates="credenciamentos")
    convenio = relationship("ConvenioOdonto")


class PrestadorComissaoOdonto(Base):
    __tablename__ = "prestador_comissao_odonto"
    __table_args__ = (
        UniqueConstraint("clinica_id", "source_id", name="uq_prestador_comissao_odonto_clinica_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    prestador_id = Column(Integer, ForeignKey("prestador_odonto.id"), nullable=True, index=True)
    convenio_id = Column(Integer, ForeignKey("convenio_odonto.id"), nullable=False, index=True)
    procedimento_generico_id = Column(Integer, ForeignKey("procedimento_generico.id"), nullable=True, index=True)
    source_id = Column(Integer, nullable=False, index=True)
    prestador_source_id = Column(Integer, nullable=True, index=True)
    convenio_source_id = Column(Integer, nullable=True, index=True)

    vigencia = Column(String(20), nullable=True)
    especialidade_row_id = Column(Integer, nullable=True, index=True)
    especialidade = Column(String(80), nullable=True)
    procedimento_generico_nome = Column(String(180), nullable=True)
    tipo_repasse_codigo = Column(Integer, nullable=True)
    tipo_repasse = Column(String(40), nullable=True)
    repasse = Column(String(30), nullable=True)
    data_inclusao = Column(String(30), nullable=True)
    data_alteracao = Column(String(30), nullable=True)

    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    clinica = relationship("Clinica")
    prestador = relationship("PrestadorOdonto", back_populates="comissoes")
    convenio = relationship("ConvenioOdonto")
    procedimento_generico = relationship("ProcedimentoGenerico")
