from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from database import Base


class PlataformaAssinatura(Base):
    __tablename__ = "plataforma_assinaturas"

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, unique=True, index=True)

    plano = Column(String(20), nullable=False, default="DEMO")
    status = Column(String(20), nullable=False, default="trial")

    inicio_em = Column(DateTime(timezone=True), nullable=True)
    fim_em = Column(DateTime(timezone=True), nullable=True)
    proxima_cobranca_em = Column(DateTime(timezone=True), nullable=True)

    bloqueada = Column(Boolean, nullable=False, default=False)

    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PlataformaCobranca(Base):
    __tablename__ = "plataforma_cobrancas"

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)

    payment_id = Column(String(80), nullable=True, unique=True, index=True)
    external_reference = Column(String(120), nullable=True, index=True)

    plano = Column(String(20), nullable=True)
    status = Column(String(30), nullable=False, default="checkout_open")
    valor = Column(Float, nullable=True)
    moeda = Column(String(10), nullable=True, default="BRL")
    origem = Column(String(30), nullable=False, default="checkout")

    payload_json = Column(Text, nullable=True)

    criado_em = Column(DateTime(timezone=True), server_default=func.now())
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PlataformaAuditoria(Base):
    __tablename__ = "plataforma_auditoria"

    id = Column(Integer, primary_key=True, index=True)

    actor_user_id = Column(Integer, nullable=True, index=True)
    actor_email = Column(String(255), nullable=True, index=True)

    acao = Column(String(80), nullable=False)
    alvo_tipo = Column(String(40), nullable=False)
    alvo_id = Column(String(80), nullable=True)

    detalhes_json = Column(Text, nullable=True)
    ip = Column(String(64), nullable=True)

    criado_em = Column(DateTime(timezone=True), server_default=func.now())
