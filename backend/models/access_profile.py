from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class AccessProfile(Base):
    __tablename__ = "access_profile"
    __table_args__ = (
        UniqueConstraint("clinica_id", "source_id", name="uq_access_profile_clinica_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    source_id = Column(Integer, nullable=True, index=True)
    nome = Column(String(160), nullable=False)
    reservado = Column(Boolean, nullable=False, default=False)

    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    clinica = relationship("Clinica")
