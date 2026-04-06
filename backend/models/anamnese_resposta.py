from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.sql import func

from database import Base


class AnamneseResposta(Base):
    __tablename__ = "anamnese_respostas"
    __table_args__ = (
        UniqueConstraint(
            "clinica_id",
            "paciente_id",
            "pergunta_id",
            name="uq_anamnese_resposta_clinica_paciente_pergunta",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False, index=True)
    questionario_id = Column(Integer, ForeignKey("anamnese_questionarios.id"), nullable=False, index=True)
    pergunta_id = Column(Integer, ForeignKey("anamnese_perguntas.id"), nullable=False, index=True)
    resposta = Column(Text, nullable=True)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
