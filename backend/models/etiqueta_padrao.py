from sqlalchemy import Boolean, Column, Float, Integer, String

from database import Base


class EtiquetaPadrao(Base):
    __tablename__ = "etiqueta_padrao"

    id = Column(Integer, primary_key=True, autoincrement=False)
    nome = Column(String(80), nullable=False)
    reservado = Column(Boolean, nullable=False, default=True)
    margem_esq = Column(Float, nullable=True)
    margem_sup = Column(Float, nullable=True)
    esp_horizontal = Column(Float, nullable=True)
    esp_vertical = Column(Float, nullable=True)
    nro_colunas = Column(Integer, nullable=True)
    nro_linhas = Column(Integer, nullable=True)
