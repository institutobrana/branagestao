from sqlalchemy import Column, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class Protetico(Base):
    __tablename__ = "protetico"
    __table_args__ = (
        UniqueConstraint("clinica_id", "nome", name="uq_protetico_clinica_nome"),
    )

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(150), nullable=False)
    clinica_id = Column(Integer, ForeignKey("clinicas.id", ondelete="CASCADE"), nullable=False, index=True)

    servicos = relationship(
        "ServicoProtetico",
        back_populates="protetico",
        cascade="all, delete-orphan",
        order_by="ServicoProtetico.nome.asc()",
    )


class ServicoProtetico(Base):
    __tablename__ = "servico_protetico"
    __table_args__ = (
        UniqueConstraint("protetico_id", "nome", name="uq_servico_protetico_nome"),
    )

    id = Column(Integer, primary_key=True, index=True)
    protetico_id = Column(Integer, ForeignKey("protetico.id", ondelete="CASCADE"), nullable=False, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id", ondelete="CASCADE"), nullable=False, index=True)
    nome = Column(String(180), nullable=False)
    indice = Column(String(10), nullable=False, default="R$")
    preco = Column(Float, nullable=False, default=0)
    prazo = Column(Integer, nullable=False, default=0)

    protetico = relationship("Protetico", back_populates="servicos")
