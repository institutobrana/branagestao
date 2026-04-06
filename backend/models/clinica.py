from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class Clinica(Base):
    __tablename__ = "clinicas"

    id = Column(Integer, primary_key=True, index=True)

    nome = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)

    cnpj = Column(String(20), nullable=True)
    tipo_conta = Column(String(20), nullable=False, default="DEMO 7 dias")
    licenca_usuario = Column(String, nullable=True)
    chave_licenca = Column(String, nullable=True)
    data_ativacao = Column(DateTime(timezone=True), nullable=True)
    nome_tabela_procedimentos = Column(String(120), nullable=False, default="Tabela Exemplo")
    opcoes_sistema_json = Column(Text, nullable=True)

    trial_ate = Column(DateTime, nullable=False)
    ativo = Column(Boolean, default=True)

    criado_em = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    usuarios = relationship(
        "Usuario",
        back_populates="clinica"
    )
