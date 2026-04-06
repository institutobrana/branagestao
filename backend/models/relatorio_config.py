from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint

from database import Base


class RelatorioConfig(Base):
    __tablename__ = "relatorio_config"

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    nome_rel = Column(String(160), nullable=False)
    seq = Column(Integer, nullable=False)
    nome_coluna = Column(String(160), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "clinica_id",
            "usuario_id",
            "nome_rel",
            "seq",
            name="ux_relatorio_config_usuario_rel_seq",
        ),
    )
