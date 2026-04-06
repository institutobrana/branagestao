from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


class Cenario(Base):
    __tablename__ = "cenario"

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, unique=True, index=True)

    meses_trabalhados = Column(Float, default=0)
    dias_uteis_mes = Column(Integer, default=0)
    dias_uteis_ano = Column(Integer, default=0)
    horas_atendimento_dia = Column(Float, default=0)
    num_consultorios = Column(Integer, default=0)
    num_consultorios_flex = Column(Integer, default=0)

    horas_ano = Column(Float, default=0)
    modo_horas = Column(String(20), default="Perfil Fixo")

    gasto_anual_particular = Column(Float, default=0)
    gasto_anual_empresa = Column(Float, default=0)

    custo_ano = Column(Float, default=0)
    cfph = Column(Float, default=0)
    cfpm = Column(Float, default=0)

    cartao = Column(Float, default=0)
    ir = Column(Float, default=0)
    cd = Column(Float, default=0)

    total_horas_fixo = Column(Float, default=0)
    total_minutos_fixo = Column(Float, default=0)
    total_turnos_fixo = Column(Float, default=0)

    total_horas_flex = Column(Float, default=0)
    total_minutos_flex = Column(Float, default=0)
    total_turnos_flex = Column(Float, default=0)

    turnos_flex = Column(Text, default="{}")

    clinica = relationship("Clinica")
