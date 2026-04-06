from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class GrupoFinanceiro(Base):
    __tablename__ = "grupo_financeiro"

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    nome = Column(String, nullable=False)
    tipo = Column(String(20), nullable=False)

    clinica = relationship("Clinica")
    categorias = relationship("CategoriaFinanceira", back_populates="grupo")


class CategoriaFinanceira(Base):
    __tablename__ = "categoria_financeira"

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    grupo_id = Column(Integer, ForeignKey("grupo_financeiro.id"), nullable=False, index=True)
    nome = Column(String, nullable=False)
    tipo = Column(String(20), nullable=False)
    tributavel = Column(Boolean, default=False)

    clinica = relationship("Clinica")
    grupo = relationship("GrupoFinanceiro", back_populates="categorias")
    lancamentos = relationship("Lancamento", back_populates="categoria")


class Lancamento(Base):
    __tablename__ = "lancamento"

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    categoria_id = Column(Integer, ForeignKey("categoria_financeira.id"), nullable=False, index=True)

    historico = Column(String, nullable=True)
    valor = Column(Float, default=0)

    data_lancamento = Column(String, nullable=True)
    data_pagamento = Column(String, nullable=True)

    tipo = Column(String(20), nullable=False, default="debito")
    conta = Column(String(20), nullable=False, default="CLINICA")
    situacao = Column(String(20), nullable=True, default="Aberto")
    forma_pagamento = Column(String, nullable=True)
    data_vencimento = Column(String, nullable=True)
    data_inclusao = Column(String, nullable=True)
    data_alteracao = Column(String, nullable=True)
    documento = Column(String, nullable=True)
    referencia = Column(String, nullable=True)
    complemento = Column(String, nullable=True)
    tributavel = Column(Integer, default=0)
    parcelado = Column(Integer, default=0)
    qtd_parcelas = Column(Integer, default=1)
    parcela_atual = Column(Integer, default=1)

    clinica = relationship("Clinica")
    categoria = relationship("CategoriaFinanceira", back_populates="lancamentos")


class ItemAuxiliar(Base):
    __tablename__ = "item_auxiliar"

    id = Column(Integer, primary_key=True, index=True)
    clinica_id = Column(Integer, ForeignKey("clinicas.id"), nullable=False, index=True)
    tipo = Column(String, nullable=False)
    codigo = Column(String, nullable=False)
    descricao = Column(String, nullable=False)
    ordem = Column(Integer, nullable=True)
    imagem_indice = Column(Integer, nullable=True)
    inativo = Column(Boolean, nullable=False, default=False)
    cor_apresentacao = Column(String, nullable=True)
    exibir_anotacao_historico = Column(Boolean, nullable=False, default=False)
    mensagem_alerta = Column(String, nullable=True)
    desativar_paciente_sistema = Column(Boolean, nullable=False, default=False)

    clinica = relationship("Clinica")
