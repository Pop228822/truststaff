import smtplib, ssl
from email.mime.text import MIMEText
from email.utils import formataddr

SMTP_HOST = "smtp.hosting.reg.ru"   # общий SMTP REG.RU
SMTP_PORT = 465                     # SSL
SMTP_USER = "noreply@truststaff.ru"
SMTP_PASSWORD = "123321123@Aram"
SENDER_NAME = "TrustStaff"

def send_verification_email(to_address: str, token: str) -> bool:
    link = f"https://truststaff.onrender.com/verify?token={token}"
    html = f"""<html><body>
    Здравствуйте!<br><br>
    Чтобы подтвердить почту, перейдите по ссылке:<br>
    <a href="{link}">{link}</a><br><br>
    Если вы не регистрировались, просто проигнорируйте это письмо.
    </body></html>"""

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = "Подтвердите вашу почту"
    msg["From"] = formataddr((SENDER_NAME, SMTP_USER))
    msg["To"] = to_address

    try:
        ctx = ssl.create_default_context()          # доверяет GlobalSign
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as s:
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.sendmail(SMTP_USER, [to_address], msg.as_string())
        print("📤 письмо отправлено")
        return True
    except Exception as e:
        print("❌ SMTP-ошибка:", e)
        return False
