from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


class Contato(Base):
    __tablename__ = "contato"

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id", ondelete="CASCADE"), nullable=False, index=True)
    protetico_id = Column(Integer, ForeignKey("protetico.id", ondelete="SET NULL"), nullable=True, index=True)

    nome = Column(String(180), nullable=False)
    tipo = Column(String(60), nullable=True)
    contato = Column(String(120), nullable=True)
    aniversario_dia = Column(Integer, nullable=True)
    aniversario_mes = Column(Integer, nullable=True)

    endereco = Column(String(180), nullable=True)
    complemento = Column(String(120), nullable=True)
    bairro = Column(String(120), nullable=True)
    cidade = Column(String(120), nullable=True)
    cep = Column(String(20), nullable=True)
    uf = Column(String(10), nullable=True)
    pais = Column(String(80), nullable=True)

    tel1_tipo = Column(String(40), nullable=True)
    tel1 = Column(String(40), nullable=True)
    tel2_tipo = Column(String(40), nullable=True)
    tel2 = Column(String(40), nullable=True)
    tel3_tipo = Column(String(40), nullable=True)
    tel3 = Column(String(40), nullable=True)
    tel4_tipo = Column(String(40), nullable=True)
    tel4 = Column(String(40), nullable=True)

    email = Column(String(180), nullable=True)
    homepage = Column(String(180), nullable=True)
    palavra_chave_1 = Column(String(120), nullable=True)
    palavra_chave_2 = Column(String(120), nullable=True)
    registro = Column(String(80), nullable=True)
    especialidade = Column(String(40), nullable=True)
    incluir_malas_diretas = Column(Boolean, nullable=False, default=True)
    incluir_preferidos = Column(Boolean, nullable=False, default=False)
    observacoes = Column(Text, nullable=True)

    protetico = relationship("Protetico", lazy="joined")
