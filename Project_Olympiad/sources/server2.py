import smtplib
from email.mime.text import MIMEText
from email.header import Header

def send_email(to_email, subject, body):
    # Конфигурация SMTP (замените на свои данные)
    SMTP_SERVER = "smtp.yandex.ru"
    SMTP_PORT = 465
    SMTP_USER = "your_email@yandex.ru"
    SMTP_PASSWORD = "your_password"
    
    try:
        # Создаем сообщение
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        
        # Отправляем через SSL
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"Ошибка отправки email: {str(e)}")
        return False

def send_confirmation_email(email, code):
    subject = "Код подтверждения для Tajik Fire"
    body = f"""
    Здравствуйте!
    
    Ваш код подтверждения для Tajik Fire: {code}
    
    Введите этот код в форме подтверждения на сайте.
    Код действителен в течение 3 минут.
    
    С уважением,
    Команда Tajik Fire
    """
    return send_email(email, subject, body)