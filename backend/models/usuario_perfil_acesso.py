from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class UsuarioPerfilAcesso(Base):
    __tablename__ = "usuario_perfil_acesso"
    __table_args__ = (
        UniqueConstraint(
            "clinica_id",
            "usuario_id",
            "prestador_id",
            "perfil_id",
            name="uq_usuario_perfil_acesso",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    prestador_id = Column(Integer, ForeignKey("prestador_odonto.id"), nullable=False, index=True)
    perfil_id = Column(Integer, ForeignKey("access_profile.id"), nullable=False, index=True)

    usuario = relationship("Usuario")
    prestador = relationship("PrestadorOdonto")
    perfil = relationship("AccessProfile")
