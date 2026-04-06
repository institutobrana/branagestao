from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class Tratamento(Base):
    __tablename__ = "tratamento"

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False, index=True)
    nrotra = Column(Integer, nullable=False, default=1, index=True)

    data_inicio = Column(String(20), nullable=True)
    data_finalizacao = Column(String(20), nullable=True)
    situacao = Column(String(40), nullable=False, default="Aberto")

    tabela_codigo = Column(Integer, nullable=False, default=1)
    indice = Column(Integer, nullable=False, default=255)

    cirurgiao_responsavel_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    cirurgiao_responsavel_nome = Column(String(120), nullable=True)
    unidade_atendimento = Column(String(160), nullable=True)
    observacoes = Column(Text, nullable=True)

    arcada_predominante = Column(String(80), nullable=True)
    copiar_de = Column(String(80), nullable=True)
    copiar_intervencoes = Column(Boolean, nullable=False, default=False)

    convenio_nome = Column(String(160), nullable=True)
    id_convenio = Column(Integer, nullable=True)
    tipo_atendimento_tiss_id = Column(Integer, nullable=True)
    tipo_atendimento_tiss_nome = Column(String(160), nullable=True)

    cirurgiao_contratado_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    cirurgiao_contratado_nome = Column(String(120), nullable=True)
    cirurgiao_solicitante_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    cirurgiao_solicitante_nome = Column(String(120), nullable=True)
    cirurgiao_executante_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    cirurgiao_executante_nome = Column(String(120), nullable=True)

    sinais_doenca_periodontal = Column(Integer, nullable=False, default=3)
    alteracao_tecidos = Column(Integer, nullable=False, default=3)
    numero_guia = Column(String(80), nullable=True)
    data_autorizacao = Column(String(20), nullable=True)
    senha_autorizacao = Column(String(120), nullable=True)
    validade_senha = Column(String(20), nullable=True)

    source_payload = Column(JSONB, nullable=True)

    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    clinica = relationship("Clinica")
    paciente = relationship("Paciente")
    cirurgiao_responsavel = relationship("Usuario", foreign_keys=[cirurgiao_responsavel_id])
    cirurgiao_contratado = relationship("Usuario", foreign_keys=[cirurgiao_contratado_id])
    cirurgiao_solicitante = relationship("Usuario", foreign_keys=[cirurgiao_solicitante_id])
    cirurgiao_executante = relationship("Usuario", foreign_keys=[cirurgiao_executante_id])
