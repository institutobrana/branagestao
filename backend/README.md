# 🦷 Brana Gestão

Sistema SaaS completo para gestão odontológica, com foco em controle financeiro, gestão clínica e multi-tenant (múltiplas clínicas).

---

## 🚀 Visão Geral

O **Brana Gestão** é um backend desenvolvido em Python com FastAPI, projetado para atender clínicas odontológicas com:

- Controle financeiro completo
- Gestão de pacientes e tratamentos
- Estrutura multi-clínicas (SaaS)
- Sistema de permissões e autenticação
- Integrações e migração de dados legados

---

## 🛠️ Tecnologias

- Python
- FastAPI
- PostgreSQL
- JWT Authentication
- Arquitetura modular (routes, services, models)

---

## 📁 Estrutura do Projeto

```text
backend/
│
├── main.py                # Ponto de entrada da aplicação
├── database.py            # Configuração do banco de dados
├── saas_app.py            # Inicialização do app SaaS
│
├── models/                # Modelos de dados (ORM)
├── routes/                # Rotas da API
├── services/              # Regras de negócio
├── schemas/               # Validações (Pydantic)
├── security/              # Autenticação, JWT e permissões
│
├── scripts/               # Scripts de migração e manutenção
├── backups/               # Backups do sistema (NÃO versionar)
│
└── .env                   # Variáveis de ambiente (NÃO versionar)