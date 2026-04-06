from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, UniqueConstraint

from database import Base


class DoencaCid(Base):
    __tablename__ = "doenca_cid"
    __table_args__ = (
        UniqueConstraint("clinica_id", "legacy_registro", name="uq_doenca_cid_clinica_registro"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id", ondelete="CASCADE"), nullable=False, index=True)
    legacy_registro = Column(Integer, nullable=True, index=True)
    codigo = Column(String(20), nullable=False)
    descricao = Column(String(500), nullable=False)
    observacoes = Column(Text, nullable=True)
    preferido = Column(Boolean, nullable=False, default=False)
