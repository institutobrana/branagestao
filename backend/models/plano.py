from sqlalchemy import Column, Integer, String, Float
from database import Base


class Plano(Base):
    __tablename__ = "planos"

    id = Column(Integer, primary_key=True)

    nome = Column(String, nullable=False)  # mensal / anual
    preco = Column(Float, nullable=False)
    duracao_dias = Column(Integer, nullable=False)