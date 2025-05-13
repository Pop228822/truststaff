import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

SMTP_HOST = "mail.truststaff.ru"
SMTP_PORT = 465
SMTP_USER = "noreply@truststaff.ru"
SMTP_PASSWORD = "123321123@Aram"

SENDER_NAME = "TrustStaff"


def send_verification_email(email: str, token: str) -> bool:
    link = f"https://truststaff.onrender.com/verify?token={token}"
    body_html = f"""
    <html><body>
    Здравствуйте!<br><br>
    Чтобы подтвердить почту, перейдите по ссылке:<br>
    <a href="{link}">{link}</a><br><br>
    Если вы не регистрировались, просто проигнорируйте это письмо.
    </body></html>
    """

    msg = MIMEText(body_html, "html", "utf-8")
    msg["Subject"] = "Подтвердите вашу почту"
    msg["From"] = formataddr((SENDER_NAME, SMTP_USER))
    msg["To"] = email

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [email], msg.as_string())

        print("📤 Email отправлено через SMTP")
        return True

    except Exception as e:
        print("❌ Ошибка отправки:", e)
        return False
