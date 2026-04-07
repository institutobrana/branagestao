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


def _build_email_html_base(*, subtitle: str, message: str, code: str, notice: str):
    return f"""
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,sans-serif;color:#111827;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:28px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;">
            <tr>
              <td style="padding:32px 28px;">
                <p style="margin:0 0 18px;font-size:22px;line-height:1.2;font-weight:700;color:#0f172a;">
                  Brana Gestão Odontológica
                </p>
                <h1 style="margin:0 0 12px;font-size:24px;line-height:1.3;font-weight:700;color:#111827;">
                  {escape(subtitle)}
                </h1>
                <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#374151;">
                  {escape(message)}
                </p>
                <div style="margin:0 0 18px;padding:16px 20px;background:#eaf2ff;border-radius:12px;text-align:center;">
                  <span style="display:inline-block;font-size:34px;line-height:1;font-weight:700;letter-spacing:6px;color:#1e3a8a;">
                    {escape(code)}
                  </span>
                </div>
                <p style="margin:0 0 24px;font-size:13px;line-height:1.5;color:#6b7280;">
                  {escape(notice)}
                </p>
                <p style="margin:0;padding-top:18px;border-top:1px solid #e5e7eb;font-size:12px;line-height:1.5;color:#6b7280;">
                  Instituto Brana • Sistema de Gestão Odontológica
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


def _build_reset_password_template(code: str):
    subject = "Brana Gestão Odontológica - Código para redefinir senha"
    subtitle = "Redefinição de senha"
    message = "Use o código abaixo para redefinir sua senha."
    notice = "Este código expira em poucos minutos."
    text = (
        "Brana Gestão Odontológica\n\n"
        "Seu código para redefinir senha é:\n\n"
        f"{code}\n\n"
        "Este código expira em poucos minutos."
    )
    html = _build_email_html_base(subtitle=subtitle, message=message, code=code, notice=notice)
    return subject, html, text


def _build_signup_verification_template(code: str):
    subject = "Brana Gestão Odontológica - Código de verificação"
    subtitle = "Verificação de cadastro"
    message = "Use o código abaixo para concluir seu cadastro."
    notice = "Este código expira em poucos minutos."
    text = (
        "Brana Gestão Odontológica\n\n"
        "Seu código de verificação é:\n\n"
        f"{code}\n\n"
        "Este código expira em poucos minutos."
    )
    html = _build_email_html_base(subtitle=subtitle, message=message, code=code, notice=notice)
    return subject, html, text


def _build_verification_template(code: str, purpose: str, exp_minutes: int):
    _ = exp_minutes  # Mantido para compatibilidade com a assinatura atual.
    if purpose == "signup":
        return _build_signup_verification_template(code)
    return _build_reset_password_template(code)


def send_verification_code(to_email: str, code: str, purpose: str):
    signup_exp = max(1, int(os.getenv("SIGNUP_CODE_EXP_MINUTES", "10")))
    reset_exp = max(1, int(os.getenv("RESET_CODE_EXP_MINUTES", "10")))

    exp = signup_exp if purpose == "signup" else reset_exp
    subject, html, texto = _build_verification_template(code=code, purpose=purpose, exp_minutes=exp)
    enviar_email(destinatario=to_email, assunto=subject, html=html, texto=texto)
