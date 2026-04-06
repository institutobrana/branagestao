from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class AnamneseQuestionario(Base):
    __tablename__ = "anamnese_questionarios"
    __table_args__ = (
        UniqueConstraint("clinica_id", "nome", name="uq_anamnese_questionario_clinica_nome"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    nome = Column(String(120), nullable=False)
    ativo = Column(Boolean, nullable=False, default=True)
    ordem = Column(Integer, nullable=False, default=1)
    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    perguntas = relationship("AnamnesePergunta", back_populates="questionario")


class AnamnesePergunta(Base):
    __tablename__ = "anamnese_perguntas"
    __table_args__ = (
        UniqueConstraint(
            "clinica_id",
            "questionario_id",
            "numero",
            name="uq_anamnese_pergunta_clinica_questionario_numero",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    questionario_id = Column(Integer, ForeignKey("anamnese_questionarios.id"), nullable=False, index=True)
    numero = Column(Integer, nullable=False)
    texto = Column(String(400), nullable=False)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    questionario = relationship("AnamneseQuestionario", back_populates="perguntas")
