import requests

UNISENDER_API_KEY = "67iasjtbnx369bjo74bxu7kgtwcuusswcr7s8r5y"
UNISENDER_EMAIL_FROM = "aeram.gazarian@yandex.ru"
UNISENDER_SENDER_NAME = "TrustStaff"

def send_verification_email(email: str, token: str) -> bool:
    link = f"https://truststaff.onrender.com/verify?token={token}"
    body = f"""
    Здравствуйте!<br><br>
    Чтобы подтвердить почту, перейдите по ссылке:<br>
    <a href="{link}">{link}</a><br><br>
    Если вы не регистрировались, просто проигнорируйте это письмо.
    """
    response = requests.post(
        "https://api.unisender.com/ru/api/sendEmail",
        data={
            "format": "json",
            "api_key": UNISENDER_API_KEY,
            "email": email,
            "sender_name": UNISENDER_SENDER_NAME,
            "sender_email": UNISENDER_EMAIL_FROM,
            "subject": "Подтвердите вашу почту",
            "body": body,
            "lang": "ru"
        }
    )
    print("📤 UniSender ответ:", response.status_code)
    print("🔍 Ответ от API:", response.text)

    return response.status_code == 200
