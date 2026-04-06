from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class ListaMaterial(Base):
    __tablename__ = "lista_material"
    __table_args__ = (
        UniqueConstraint("clinica_id", "nome", name="uq_lista_material_clinica_nome"),
    )

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    nro_indice = Column(Integer, nullable=False, default=255)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)

    clinica = relationship("Clinica")
    materiais = relationship(
        "Material",
        back_populates="lista",
        cascade="all, delete-orphan",
    )


class Material(Base):
    __tablename__ = "material"
    __table_args__ = (
        UniqueConstraint("lista_id", "codigo", name="uq_material_lista_codigo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, nullable=False)
    nome = Column(String, nullable=False)
    relacao = Column(Float, default=0)
    custo = Column(Float, default=0)
    preco = Column(Float, default=0)
    unidade_compra = Column(String, nullable=True, default="")
    unidade_consumo = Column(String, nullable=True, default="")
    validade_dias = Column(Integer, nullable=False, default=0)
    preferido = Column(Boolean, nullable=False, default=False)
    classificacao = Column(String, nullable=True, default="")
    lista_id = Column(Integer, ForeignKey("lista_material.id", ondelete="CASCADE"), nullable=False, index=True)

    lista = relationship("ListaMaterial", back_populates="materiais")
