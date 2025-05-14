import smtplib
import os
from dotenv import load_dotenv
import ssl
from email.mime.text import MIMEText
from email.utils import formataddr

load_dotenv()

SMTP_USER = "noreply@truststaff.ru"
SENDER_NAME = "TrustStaff"
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = os.getenv("SMTP_PORT")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# ----------------------------------------------------------
def send_verification_email(to_addr: str, token: str) -> bool:
    link = f"https://truststaff.onrender.com/verify?token={token}"
    body_html = f"""
    <html><body>
    Здравствуйте!<br><br>
    Чтобы подтвердить почту, перейдите по ссылке:<br>
    <a href="{link}">{link}</a><br><br>
    Если вы не регистрировались, просто проигнорируйте это письмо.
    </body></html>
    """

    # Формируем MIME-письмо
    msg = MIMEText(body_html, "html", "utf-8")
    msg["Subject"] = "Подтвердите вашу почту"
    msg["From"] = formataddr((SENDER_NAME, SMTP_USER))
    msg["To"] = to_addr

    try:
        # Безопасный TLS-контекст — проверка сертификата включена
        ctx = ssl.create_default_context()

        # ➜ подключение, авторизация, отправка
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [to_addr], msg.as_string())

        print("📤 Email отправлен через sm17.hosting.reg.ru")
        return True

    except Exception as exc:
        # Логируем причину — удобно видеть в Render-логах
        print("❌ Ошибка отправки письма:", repr(exc))
        return False
