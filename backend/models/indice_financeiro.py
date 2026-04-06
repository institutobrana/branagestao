from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class IndiceFinanceiro(Base):
    __tablename__ = "indice_financeiro"
    __table_args__ = (
        UniqueConstraint("clinica_id", "numero", name="uq_indice_financeiro_clinica_numero"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    numero = Column(Integer, nullable=False)
    sigla = Column(String(20), nullable=False)
    nome = Column(String(120), nullable=False)
    reservado = Column(Boolean, nullable=False, default=False)
    ativo = Column(Boolean, nullable=False, default=True)

    clinica = relationship("Clinica")
    cotacoes = relationship(
        "IndiceCotacao",
        back_populates="indice",
        cascade="all, delete-orphan",
    )


class IndiceCotacao(Base):
    __tablename__ = "indice_cotacao"

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    indice_id = Column(Integer, ForeignKey("indice_financeiro.id", ondelete="CASCADE"), nullable=False, index=True)
    data = Column(String(20), nullable=False)
    valor = Column(Float, nullable=False, default=1.0)

    clinica = relationship("Clinica")
    indice = relationship("IndiceFinanceiro", back_populates="cotacoes")
