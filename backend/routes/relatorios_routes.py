import os
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access
from services.email_service import EmailDeliveryError, send_email_with_attachment


router = APIRouter(
    prefix="/relatorios",
    tags=["relatorios"],
    dependencies=[Depends(require_module_access("relatorios"))],
)


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def _sanitize_filename(value: str) -> str:
    name = str(value or "").strip()
    if not name:
        return "relatorio"
    name = re.sub(r"[^\w\-. ]", "_", name)
    name = name.strip("._ ")
    return name or "relatorio"


def _max_attachment_bytes() -> int:
    raw = str(os.getenv("EMAIL_ATTACHMENT_MAX_MB", "10")).strip()
    try:
        mb = max(1, int(float(raw)))
    except Exception:
        mb = 10
    return mb * 1024 * 1024


@router.post("/enviar-email")
async def enviar_email_relatorio(
    to_email: str = Form(...),
    subject: str = Form("Relatorio do sistema"),
    body: str = Form(""),
    filename: str = Form("relatorio"),
    file: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_user),
):
    email = _normalize_email(to_email)
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Informe um e-mail valido.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    max_bytes = _max_attachment_bytes()
    if len(data) > max_bytes:
        limite_mb = max(1, int(max_bytes / 1024 / 1024))
        raise HTTPException(
            status_code=400,
            detail=f"Arquivo excede o limite de {limite_mb} MB.",
        )

    safe_name = _sanitize_filename(filename or file.filename or "relatorio")
    content_type = file.content_type or "application/octet-stream"
    assunto = str(subject or "").strip() or "Relatorio do sistema"
    corpo = str(body or "").strip()

    try:
        send_email_with_attachment(
            to_email=email,
            subject=assunto,
            body=corpo,
            filename=safe_name,
            content=data,
            mime_type=content_type,
        )
    except EmailDeliveryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"detail": "E-mail enviado com sucesso."}
