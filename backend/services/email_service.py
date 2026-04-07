import os
import smtplib
from html import escape
from email.message import EmailMessage

import requests


class EmailDeliveryError(Exception):
    pass


def _email_provider():
    return os.getenv("EMAIL_PROVIDER", "smtp").strip().lower()


def _resend_settings():
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    sender = os.getenv("EMAIL_FROM", "").strip()
    return api_key, sender


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


def _send_email_smtp(to_email: str, subject: str, body: str):
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


def enviar_email(destinatario, assunto, html, texto):
    provider = _email_provider()

    if provider == "resend":
        api_key, sender = _resend_settings()
        if not api_key or not sender:
            raise EmailDeliveryError("Resend nao configurado. Defina RESEND_API_KEY e EMAIL_FROM.")

        payload = {
            "from": sender,
            "to": [destinatario],
            "subject": assunto,
            "html": html or "",
            "text": texto or "",
        }

        try:
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=20,
            )
        except requests.RequestException as exc:
            raise EmailDeliveryError(f"Falha ao enviar e-mail via Resend: {exc}") from exc

        if response.status_code >= 400:
            detalhes = response.text.strip() or f"status={response.status_code}"
            raise EmailDeliveryError(f"Falha ao enviar e-mail via Resend: {detalhes}")
        return

    # Compatibilidade com ambientes legados.
    _send_email_smtp(to_email=destinatario, subject=assunto, body=texto or "")


def send_email(to_email: str, subject: str, body: str):
    texto = body or ""
    html = f"<pre style=\"font-family:Arial,sans-serif;white-space:pre-wrap\">{escape(texto)}</pre>"
    enviar_email(destinatario=to_email, assunto=subject, html=html, texto=texto)


def send_email_with_attachment(
    *,
    to_email: str,
    subject: str,
    body: str,
    filename: str,
    content: bytes,
    mime_type: str | None = None,
):
    # Mantido para compatibilidade com o fluxo atual de anexos.
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


def _build_verification_template(code: str, purpose: str, exp_minutes: int):
    if purpose == "signup":
        subject = "Brana SaaS - Codigo de verificacao de cadastro"
        titulo = "Verificacao de cadastro"
        mensagem = "Use o codigo abaixo para concluir seu cadastro no Brana SaaS."
    else:
        subject = "Brana SaaS - Codigo para redefinir senha"
        titulo = "Redefinicao de senha"
        mensagem = "Use o codigo abaixo para redefinir sua senha no Brana SaaS."

    texto = (
        f"{titulo}\n\n"
        f"{mensagem}\n\n"
        f"Codigo: {code}\n\n"
        f"O codigo expira em {exp_minutes} minutos.\n\n"
        "Instituto Brana"
    )

    html = f"""
<html>
  <body style="margin:0;padding:0;background:#f7f7f9;font-family:Arial,sans-serif;color:#1f2937;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#ffffff;border:1px solid #e5e7eb;border-radius:8px;">
            <tr>
              <td style="padding:24px;">
                <h1 style="margin:0 0 12px;font-size:22px;line-height:1.3;color:#111827;">{escape(titulo)}</h1>
                <p style="margin:0 0 18px;font-size:15px;line-height:1.6;color:#374151;">{escape(mensagem)}</p>
                <div style="margin:0 0 18px;padding:14px 16px;background:#f3f4f6;border:1px dashed #9ca3af;border-radius:6px;font-size:28px;font-weight:700;letter-spacing:4px;text-align:center;color:#111827;">
                  {escape(code)}
                </div>
                <p style="margin:0 0 20px;font-size:14px;line-height:1.5;color:#4b5563;">
                  O codigo expira em {exp_minutes} minutos.
                </p>
                <p style="margin:0;font-size:13px;line-height:1.5;color:#6b7280;">
                  Instituto Brana
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
""".strip()

    return subject, html, texto


def send_verification_code(to_email: str, code: str, purpose: str):
    signup_exp = max(1, int(os.getenv("SIGNUP_CODE_EXP_MINUTES", "10")))
    reset_exp = max(1, int(os.getenv("RESET_CODE_EXP_MINUTES", "10")))

    exp = signup_exp if purpose == "signup" else reset_exp
    subject, html, texto = _build_verification_template(code=code, purpose=purpose, exp_minutes=exp)
    enviar_email(destinatario=to_email, assunto=subject, html=html, texto=texto)
