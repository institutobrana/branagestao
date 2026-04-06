from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class ProcedimentoGenerico(Base):
    __tablename__ = "procedimento_generico"
    __table_args__ = (
        UniqueConstraint("clinica_id", "codigo", name="uq_procedimento_generico_clinica_codigo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    codigo = Column(String, nullable=False, index=True)
    descricao = Column(String, nullable=False)
    especialidade = Column(String(20), nullable=True)
    tempo = Column(Integer, nullable=False, default=0)
    custo_lab = Column(Float, nullable=False, default=0)
    peso = Column(Float, nullable=False, default=0)
    simbolo_grafico = Column(String(30), nullable=True)
    mostrar_simbolo = Column(Boolean, nullable=False, default=False)
    inativo = Column(Boolean, nullable=False, default=False)
    observacoes = Column(Text, nullable=True)
    data_inclusao = Column(String(30), nullable=True)
    data_alteracao = Column(String(30), nullable=True)
    clinica = relationship("Clinica")

    fases = relationship(
        "ProcedimentoGenericoFase",
        back_populates="procedimento_generico",
        cascade="all, delete-orphan",
        order_by="ProcedimentoGenericoFase.sequencia.asc()",
    )
    materiais_vinculados = relationship(
        "ProcedimentoGenericoMaterial",
        back_populates="procedimento_generico",
        cascade="all, delete-orphan",
        order_by="ProcedimentoGenericoMaterial.id.asc()",
    )


class ProcedimentoGenericoFase(Base):
    __tablename__ = "procedimento_generico_fase"

    id = Column(Integer, primary_key=True, index=True)
    procedimento_generico_id = Column(
        Integer,
        ForeignKey("procedimento_generico.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    codigo = Column(String(20), nullable=True)
    descricao = Column(String(255), nullable=False)
    sequencia = Column(Integer, nullable=False, default=1)
    tempo = Column(Integer, nullable=False, default=0)

    procedimento_generico = relationship("ProcedimentoGenerico", back_populates="fases")
    clinica = relationship("Clinica")


class ProcedimentoGenericoMaterial(Base):
    __tablename__ = "procedimento_generico_material"

    id = Column(Integer, primary_key=True, index=True)
    procedimento_generico_id = Column(
        Integer,
        ForeignKey("procedimento_generico.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    material_id = Column(Integer, ForeignKey("material.id", ondelete="CASCADE"), nullable=False, index=True)
    quantidade = Column(Float, nullable=False, default=1)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)

    procedimento_generico = relationship("ProcedimentoGenerico", back_populates="materiais_vinculados")
    material = relationship("Material")
    clinica = relationship("Clinica")
