from sqlalchemy import Boolean, Column, Integer, String, Text

from database import Base


class SimboloGrafico(Base):
    __tablename__ = "simbolo_grafico_catalogo"

    id = Column(Integer, primary_key=True, index=True)
    legacy_id = Column(Integer, nullable=True, unique=True, index=True)
    codigo = Column(String(30), nullable=False, index=True)
    descricao = Column(String(120), nullable=False)
    especialidade = Column(Integer, nullable=True)
    tipo_marca = Column(Integer, nullable=True)
    tipo_simbolo = Column(Integer, nullable=True)
    bitmap1 = Column(String(30), nullable=True)
    bitmap2 = Column(String(30), nullable=True)
    bitmap3 = Column(String(30), nullable=True)
    icone = Column(String(30), nullable=True)
    imagem_custom = Column(Text, nullable=True)
    sobreposicao = Column(Integer, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
