from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class Paciente(Base):
    __tablename__ = "pacientes"
    __table_args__ = (
        UniqueConstraint("clinica_id", "codigo", name="uq_paciente_clinica_codigo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    codigo = Column(Integer, nullable=False, index=True)

    nome = Column(String(150), nullable=False)
    sobrenome = Column(String(150), nullable=True)
    nome_completo = Column(String(300), nullable=True, index=True)
    apelido = Column(String(120), nullable=True)

    sexo = Column(String(20), nullable=True)
    data_nascimento = Column(String(20), nullable=True)
    data_cadastro = Column(String(20), nullable=True)
    status = Column(String(40), nullable=True)
    inativo = Column(Boolean, nullable=False, default=False)

    cpf = Column(String(20), nullable=True)
    rg = Column(String(30), nullable=True)
    cns = Column(String(30), nullable=True)

    correspondencia = Column(String(60), nullable=True)
    endereco = Column(String(180), nullable=True)
    complemento = Column(String(120), nullable=True)
    bairro = Column(String(120), nullable=True)
    cidade = Column(String(120), nullable=True)
    uf = Column(String(10), nullable=True)
    cep = Column(String(20), nullable=True)
    email = Column(String(180), nullable=True)

    tipo_fone1 = Column(String(40), nullable=True)
    fone1 = Column(String(40), nullable=True)
    tipo_fone2 = Column(String(40), nullable=True)
    fone2 = Column(String(40), nullable=True)
    tipo_fone3 = Column(String(40), nullable=True)
    fone3 = Column(String(40), nullable=True)
    tipo_fone4 = Column(String(40), nullable=True)
    fone4 = Column(String(40), nullable=True)

    tipo_indicacao = Column(String(80), nullable=True)
    indicado_por = Column(String(150), nullable=True)
    anotacoes = Column(Text, nullable=True)

    id_convenio = Column(Integer, nullable=True)
    id_plano = Column(Integer, nullable=True)
    id_unidade = Column(Integer, nullable=True)
    tabela_codigo = Column(Integer, nullable=True)
    cod_prontuario = Column(String(40), nullable=True)
    matricula = Column(String(80), nullable=True)
    data_validade_plano = Column(String(20), nullable=True)

    source_payload = Column(JSONB, nullable=True)

    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    clinica = relationship("Clinica")
