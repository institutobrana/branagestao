import os
import smtplib
from email.message import EmailMessage


class EmailDeliveryError(Exception):
    pass


def _smtp_settings():
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASS", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()
    use_tls = os.getenv("SMTP_TLS", "true").strip().lower() != "false"
    return host, port, user, password, sender, use_tls


def _split_mime_type(mime_type: str | None):
    raw = str(mime_type or "").strip()
    if "/" not in raw:
        return "application", "octet-stream"
    main, sub = raw.split("/", 1)
    main = main.strip() or "application"
    sub = sub.strip() or "octet-stream"
    return main, sub


def send_email(to_email: str, subject: str, body: str):
    host, port, user, password, sender, use_tls = _smtp_settings()

    if not host or not sender:
        raise EmailDeliveryError("SMTP nao configurado. Defina SMTP_HOST e SMTP_FROM.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            if use_tls:
                smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
    except Exception as exc:
        raise EmailDeliveryError(f"Falha ao enviar e-mail: {exc}") from exc


def send_email_with_attachment(
    *,
    to_email: str,
    subject: str,
    body: str,
    filename: str,
    content: bytes,
    mime_type: str | None = None,
):
    host, port, user, password, sender, use_tls = _smtp_settings()

    if not host or not sender:
        raise EmailDeliveryError("SMTP nao configurado. Defina SMTP_HOST e SMTP_FROM.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(body or "")

    main_type, sub_type = _split_mime_type(mime_type)
    safe_name = str(filename or "").strip() or "relatorio"
    msg.add_attachment(content, maintype=main_type, subtype=sub_type, filename=safe_name)

    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            if use_tls:
                smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
    except Exception as exc:
        raise EmailDeliveryError(f"Falha ao enviar e-mail: {exc}") from exc


def send_verification_code(to_email: str, code: str, purpose: str):
    signup_exp = max(1, int(os.getenv("SIGNUP_CODE_EXP_MINUTES", "10")))
    reset_exp = max(1, int(os.getenv("RESET_CODE_EXP_MINUTES", "10")))

    if purpose == "signup":
        subject = "Brana SaaS - Codigo de verificacao de cadastro"
        body = (
            "Seu codigo de verificacao para cadastro no Brana SaaS e:\n\n"
            f"{code}\n\n"
            f"O codigo expira em {signup_exp} minutos."
        )
    else:
        subject = "Brana SaaS - Codigo para redefinir senha"
        body = (
            "Seu codigo para redefinicao de senha no Brana SaaS e:\n\n"
            f"{code}\n\n"
            f"O codigo expira em {reset_exp} minutos."
        )

    send_email(to_email=to_email, subject=subject, body=body)
