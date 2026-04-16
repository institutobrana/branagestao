from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship

from database import Base
from models.clinica import Clinica   # 👈 IMPORTA A CLINICA


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(Integer, index=True, nullable=True)

    nome = Column(String, nullable=False)
    apelido = Column(String(60), nullable=True)
    tipo_usuario = Column(String(80), nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    senha_hash = Column(String, nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)
    online = Column(Boolean, default=False, nullable=False)
    forcar_troca_senha = Column(Boolean, default=False, nullable=False)
    setup_completed = Column(Boolean, default=False, nullable=False)
    is_system_user = Column(Boolean, default=False, nullable=False)

    is_admin = Column(Boolean, default=False)
    prestador_id = Column(Integer, ForeignKey("prestador_odonto.id"), nullable=True)
    unidade_atendimento_id = Column(Integer, ForeignKey("unidade_atendimento.id"), nullable=True)
    preferencias_usuario_json = Column(Text, nullable=True)
    preferencias_agenda_json = Column(Text, nullable=True)
    preferencias_impressora_json = Column(Text, nullable=True)
    preferencias_etiqueta_json = Column(Text, nullable=True)
    permissoes_json = Column(Text, nullable=True)

    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False)

    clinica = relationship(
        "Clinica",
        back_populates="usuarios"
    )
    prestador = relationship("PrestadorOdonto", foreign_keys=[prestador_id])
    unidade_atendimento = relationship("UnidadeAtendimento", foreign_keys=[unidade_atendimento_id])
