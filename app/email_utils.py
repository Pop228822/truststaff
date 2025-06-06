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
    link = f"https://app.truststaff.ru/verify?token={token}"
    body_html = f"""
    <html>
    <head>
      <meta charset="UTF-8"/>
    </head>
    <body style="margin:0; padding:0; font-family: Arial, sans-serif; font-size: 14px; color: #333;">
      <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <p>Здравствуйте!</p>
        <p>Чтобы подтвердить вашу почту, нажмите на кнопку ниже или откройте ссылку в браузере:</p>

        <div style="margin: 20px 0;">
          <a href="{link}"
             style="
                display: inline-block;
                text-decoration: none;
                background: #0052cc;
                color: #fff;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
             "
          >
            Подтвердить почту
          </a>
        </div>

        <p style="word-wrap:break-word;">
          <a href="{link}" style="color:#0052cc;">{link}</a>
        </p>

        <p>Если вы не регистрировались в TrustStaff, просто проигнорируйте письмо.</p>
        <br>
        <p style="font-size:12px; color:#999;">
          С уважением,<br>
          Команда TrustStaff
        </p>
      </div>
    </body>
    </html>
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
        print("❌ Ошибка отправки письма:", repr(exc))
        return False


def send_password_reset_email(to_addr: str, token: str) -> bool:
    """Отправляет письмо для восстановления пароля."""
    link = f"https://app.truststaff.ru/reset-password?token={token}"
    body_html = f"""
    <html>
    <head>
      <meta charset="UTF-8"/>
    </head>
    <body style="margin:0; padding:0; font-family: Arial, sans-serif; font-size: 14px; color: #333;">
      <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <p>Здравствуйте!</p>
        <p>Поступил запрос на восстановление пароля в TrustStaff.</p>
        <p>Чтобы сбросить пароль, нажмите на кнопку ниже или откройте ссылку в браузере:</p>

        <div style="margin: 20px 0;">
          <a href="{link}"
             style="
                display: inline-block;
                text-decoration: none;
                background: #0052cc;
                color: #fff;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
             "
          >
            Сбросить пароль
          </a>
        </div>

        <p style="word-wrap:break-word;">
          <a href="{link}" style="color:#0052cc;">{link}</a>
        </p>

        <p>Если вы не делали этот запрос, просто проигнорируйте письмо.</p>
        <br>
        <p style="font-size:12px; color:#999;">
          С уважением,<br>
          Команда TrustStaff
        </p>
      </div>
    </body>
    </html>
    """

    msg = MIMEText(body_html, "html", "utf-8")
    msg["Subject"] = "Восстановление пароля TrustStaff"
    msg["From"] = formataddr((SENDER_NAME, SMTP_USER))
    msg["To"] = to_addr

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [to_addr], msg.as_string())

        print("📤 Email отправлен через sm17.hosting.reg.ru")
        return True

    except Exception as exc:
        print("❌ Ошибка отправки письма:", repr(exc))
        return False


def send_2fa_code(to_addr: str, code: str) -> bool:
    """Отправляет на почту пользователю 6-значный код."""
    body_html = f"""
    <html>
    <head>
      <meta charset="UTF-8">
    </head>
    <body style="font-family: Arial, sans-serif; font-size: 14px; color: #333; margin: 0; padding: 0;">
      <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <p>Здравствуйте!</p>
        <p>Ваш код для входа в TrustStaff:</p>
        <div style="
             margin: 20px 0; 
             border: 2px solid #ccc; 
             border-radius: 8px; 
             text-align: center; 
             font-size: 28px; 
             font-weight: bold; 
             padding: 15px 0;
        ">
          {code}
        </div>
        <p>Действует 5 минут.<br>
        Если вы не запрашивали код, просто проигнорируйте это письмо.</p>
      </div>
    </body>
    </html>
    """

    msg = MIMEText(body_html, "html", "utf-8")
    msg["Subject"] = "Код для входа в TrustStaff"
    msg["From"] = formataddr((SENDER_NAME, SMTP_USER))
    msg["To"] = to_addr

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [to_addr], msg.as_string())
        print("2FA код отправлен на email:", to_addr)
        return True
    except Exception as exc:
        print("Ошибка отправки 2FA-кода:", repr(exc))
        return False
