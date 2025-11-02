# mailer.py
import os, smtplib, ssl
from email.message import EmailMessage

def send_email(subject: str, body_text: str, body_html: str | None = None) -> None:
    """
    Envía email con texto plano y, si se proporciona, versión HTML.
    Variables de entorno:
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_FROM, EMAIL_TO
    """
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd  = os.getenv("SMTP_PASS")
    from_addr = os.getenv("EMAIL_FROM", user or "")
    to_addr = os.getenv("EMAIL_TO")

    if not (host and user and pwd and from_addr and to_addr):
        print("[mailer] SMTP no configurado; omitido.")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    # Parte de texto (fallback)
    msg.set_content(body_text)

    # Parte HTML opcional
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.starttls(context=context)
        server.login(user, pwd)
        server.send_message(msg)
    print("[mailer] Email enviado a", to_addr)
