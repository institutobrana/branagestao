from sqlalchemy import Boolean, Column, Integer, String

from database import Base


class TissTipoTabela(Base):
    __tablename__ = "tiss_tipo_tabela"

    id = Column(Integer, primary_key=True, autoincrement=False)
    codigo = Column(String(15), nullable=False, unique=True, index=True)
    nome = Column(String(100), nullable=False)
    descricao = Column(String(150), nullable=True)
    reservado = Column(Boolean, nullable=False, default=True)
    ativo = Column(Boolean, nullable=False, default=True)
