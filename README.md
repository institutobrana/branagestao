# Brana SaaS Web

Sistema SaaS web com backend em FastAPI e frontend em HTML/CSS/JS puro.

## Estrutura do projeto

```text
saas/
├─ assets/                 # imagens e ícones servidos em /desktop-assets
├─ backend/                # API FastAPI
│  ├─ main.py              # aplicação principal
│  ├─ database.py          # conexão com banco
│  └─ requirements.txt     # dependências do backend web
├─ frontend/               # frontend estático servido pelo backend
└─ storage/                # armazenamento de modelos/documentos
```

## Como funciona no runtime

- O frontend **não** usa build Vite/React.
- O backend FastAPI serve:
  - `GET /app` -> `frontend/index.html`
  - `GET /frontend/*` -> arquivos estáticos do frontend
  - `GET /desktop-assets/*` -> arquivos de `saas/assets`

## Requisitos

- Python 3.10+
- Banco PostgreSQL acessível via `DATABASE_URL`

## Execução local

1. Criar e ativar ambiente virtual.
2. Instalar dependências:

```bash
pip install -r backend/requirements.txt
```

3. Configurar variáveis (copie `.env.example` para `backend/.env` e ajuste valores).
4. Subir aplicação:

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

5. Acessar:
- App: `http://127.0.0.1:8000/app`
- Docs: `http://127.0.0.1:8000/docs`

## Deploy (Render)

- Tipo: `Web Service`
- Root directory: `saas`
- Build command:

```bash
pip install -r backend/requirements.txt
```

- Start command:

```bash
cd backend && uvicorn main:app --host 0.0.0.0 --port ${PORT}
```

## Variáveis de ambiente

Obrigatórias:
- `DATABASE_URL`

Recomendadas/funcionais:
- `BRANA_SKIP_BOOTSTRAP`
- `SIGNUP_CODE_EXP_MINUTES`
- `RESET_CODE_EXP_MINUTES`
- `PROTECTED_GRANT_EXPIRE_MINUTES`
- `OWNER_BYPASS_EMAILS` ou `OWNER_MASTER_EMAIL`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASS`
- `SMTP_FROM`
- `SMTP_TLS`
- `EMAIL_ATTACHMENT_MAX_MB`
- `LICENCA_SUPORTE_EMAIL`
- `MERCADOPAGO_ACCESS_TOKEN`
- `MERCADOPAGO_USE_SANDBOX`
- `MERCADOPAGO_API_BASE`
- `MERCADOPAGO_WEBHOOK_URL`
- `MERCADOPAGO_BACK_URL`
- `PAGAMENTO_MENSAL_URL`
- `PAGAMENTO_ANUAL_URL`
- `PLANO_MENSAL_VALOR`
- `PLANO_ANUAL_VALOR`
