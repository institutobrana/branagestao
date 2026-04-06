from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class ProcedimentoTabela(Base):
    __tablename__ = "procedimento_tabela"
    __table_args__ = (
        UniqueConstraint("clinica_id", "codigo", name="uq_proc_tabela_clinica_codigo"),
    )

    id = Column(Integer, primary_key=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    codigo = Column(Integer, nullable=False, index=True)
    nome = Column(String(120), nullable=False)
    nro_indice = Column(Integer, nullable=False, default=255)
    fonte_pagadora = Column(String(20), nullable=False, default="particular")
    nro_credenciamento = Column(String(30), nullable=True)
    inativo = Column(Boolean, nullable=False, default=False)
    tipo_tiss_id = Column(Integer, ForeignKey("tiss_tipo_tabela.id"), nullable=False, default=1)

    clinica = relationship("Clinica")
    tipo_tiss = relationship("TissTipoTabela")
