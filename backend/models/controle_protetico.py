from sqlalchemy import Boolean, Column, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


class ControleProtetico(Base):
    __tablename__ = "controle_protetico"

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id", ondelete="CASCADE"), nullable=False, index=True)

    protetico_id = Column(Integer, ForeignKey("protetico.id", ondelete="RESTRICT"), nullable=False, index=True)
    servico_protetico_id = Column(Integer, ForeignKey("servico_protetico.id", ondelete="SET NULL"), nullable=True, index=True)
    cirurgiao_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id", ondelete="SET NULL"), nullable=True, index=True)

    data_envio = Column(Date, nullable=True, index=True)
    data_entrega = Column(Date, nullable=True, index=True)

    indice = Column(String(20), nullable=True)
    valor = Column(Float, nullable=False, default=0)
    numero_elementos = Column(Integer, nullable=True)
    cor = Column(String(40), nullable=True)
    escala = Column(String(60), nullable=True)
    material = Column(String(120), nullable=True)
    pago = Column(Boolean, nullable=False, default=False)
    situacao = Column(Integer, nullable=True)
    observacoes = Column(Text, nullable=True)

    protetico = relationship("Protetico")
    servico = relationship("ServicoProtetico")
    cirurgiao = relationship("Usuario")
    paciente = relationship("Paciente")
