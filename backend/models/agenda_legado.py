from sqlalchemy import Column, DateTime, ForeignKey, Integer, SmallInteger, String, Text

from database import Base


class AgendaLegadoEvento(Base):
    __tablename__ = "agenda_legado_evento"

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id", ondelete="CASCADE"), nullable=False, index=True)

    id_prestador = Column(Integer, nullable=False, index=True)
    id_unidade = Column(Integer, nullable=False, index=True)
    data = Column(DateTime, nullable=False, index=True)
    hora_inicio = Column(Integer, nullable=False)
    hora_fim = Column(Integer, nullable=True)
    sala = Column(SmallInteger, nullable=True)
    tipo = Column(Integer, nullable=True)
    nro_pac = Column(Integer, nullable=True)
    nome = Column(String(120), nullable=True)
    motivo = Column(Text, nullable=True)
    status = Column(Integer, nullable=True)
    observ = Column(Text, nullable=True)

    tip_fone1 = Column(SmallInteger, nullable=True)
    fone1 = Column(String(40), nullable=True)
    tip_fone2 = Column(SmallInteger, nullable=True)
    fone2 = Column(String(40), nullable=True)
    tip_fone3 = Column(SmallInteger, nullable=True)
    fone3 = Column(String(40), nullable=True)

    palm_id = Column(Integer, nullable=True)
    palm_upd = Column(Integer, nullable=True)
    myeasy_id = Column(Integer, nullable=True)
    myeasy_upd = Column(Integer, nullable=True)
    user_stamp_ins = Column(Integer, nullable=True)
    time_stamp_ins = Column(DateTime, nullable=True)
    user_stamp_upd = Column(Integer, nullable=True)
    time_stamp_upd = Column(DateTime, nullable=True)


class AgendaLegadoBloqueio(Base):
    __tablename__ = "agenda_legado_bloqueio"

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id", ondelete="CASCADE"), nullable=False, index=True)

    id_bloqueio = Column(Integer, nullable=False)
    id_prestador = Column(Integer, nullable=False, index=True)
    id_unidade = Column(Integer, nullable=False, index=True)
    dia_sem = Column(SmallInteger, nullable=False)
    data_ini = Column(DateTime, nullable=False)
    data_fin = Column(DateTime, nullable=True)
    hora_ini = Column(Integer, nullable=False)
    hora_fin = Column(Integer, nullable=False)
    msg_agenda = Column(Text, nullable=True)
