from sqlalchemy import Column, Integer, DateTime, Boolean, ForeignKey, String
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class Assinatura(Base):
    __tablename__ = "assinaturas"

    id = Column(Integer, primary_key=True)

    clinica_id = Column(Integer, ForeignKey("clinicas.id"))
    plano_id = Column(Integer, ForeignKey("planos.id"))

    status = Column(String, default="trial")

    trial_ate = Column(DateTime)
    vencimento = Column(DateTime)

    ativo = Column(Boolean, default=True)

    clinica = relationship("Clinica")
    plano = relationship("Plano")
