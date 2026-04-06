from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class Procedimento(Base):
    __tablename__ = "procedimento"
    __table_args__ = (
        UniqueConstraint("clinica_id", "tabela_id", "codigo", name="uq_procedimento_clinica_tabela_codigo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(Integer, nullable=False)
    nome = Column(String, nullable=False)
    tempo = Column(Integer, default=0)
    preco = Column(Float, default=0)
    custo = Column(Float, default=0)
    custo_lab = Column(Float, default=0)
    lucro_hora = Column(Float, default=0)
    tabela_id = Column(Integer, nullable=False, default=1, index=True)
    especialidade = Column(String(20), nullable=True)
    procedimento_generico_id = Column(Integer, ForeignKey("procedimento_generico.id"), nullable=True)
    simbolo_grafico = Column(String(30), nullable=True)
    simbolo_grafico_legacy_id = Column(Integer, nullable=True)
    mostrar_simbolo = Column(Boolean, nullable=False, default=False)
    garantia_meses = Column(Integer, default=0)
    forma_cobranca = Column(String(50), nullable=True)
    valor_repasse = Column(Float, default=0)
    preferido = Column(Boolean, nullable=False, default=False)
    inativo = Column(Boolean, nullable=False, default=False)
    observacoes = Column(Text, nullable=True)
    data_inclusao = Column(String(30), nullable=True)
    data_alteracao = Column(String(30), nullable=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)

    clinica = relationship("Clinica")
    materiais_vinculados = relationship(
        "ProcedimentoMaterial",
        back_populates="procedimento",
        cascade="all, delete-orphan",
    )
    fases_vinculadas = relationship(
        "ProcedimentoFase",
        back_populates="procedimento",
        cascade="all, delete-orphan",
    )


class ProcedimentoMaterial(Base):
    __tablename__ = "procedimento_material"

    id = Column(Integer, primary_key=True, index=True)
    procedimento_id = Column(Integer, ForeignKey("procedimento.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id = Column(Integer, ForeignKey("material.id", ondelete="CASCADE"), nullable=False, index=True)
    quantidade = Column(Float, default=1)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)

    procedimento = relationship("Procedimento", back_populates="materiais_vinculados")
    material = relationship("Material")
    clinica = relationship("Clinica")


class ProcedimentoFase(Base):
    __tablename__ = "procedimento_fase"

    id = Column(Integer, primary_key=True, index=True)
    procedimento_id = Column(Integer, ForeignKey("procedimento.id", ondelete="CASCADE"), nullable=False, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    codigo = Column(String(20), nullable=True)
    descricao = Column(String(255), nullable=False)
    sequencia = Column(Integer, nullable=False, default=1)
    tempo = Column(Integer, nullable=False, default=0)

    procedimento = relationship("Procedimento", back_populates="fases_vinculadas")
    clinica = relationship("Clinica")
