
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
from email.header import Header


class SMTPClient:
    def __init__(self, smtp_server, smtp_port, smtp_user, smtp_password, use_ssl=True):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.use_ssl = use_ssl

    def send_mail(self, from_addr, to_addrs, subject, body=None, attached_files=None):
        # Создаем контейнер для смешанного контента
        msg = MIMEMultipart()
        msg['From'] = from_addr
        msg['To'] = ', '.join(to_addrs)
        msg['Subject'] = Header(subject, 'utf-8').encode()

        # Если есть текстовое тело
        if body:
            text_part = MIMEText(body, 'plain', 'utf-8')
            msg.attach(text_part)
        else:
            # Если текста нет, добавим пустую текстовую часть
            text_part = MIMEText("", 'plain', 'utf-8')
            msg.attach(text_part)

        # Добавляем вложения, если они есть
        if attached_files:
            for file_path in attached_files:
                part = self.attach_file(file_path)
                if part:
                    msg.attach(part)

        try:
            if self.use_ssl:
                print(f"Устанавливаем SSL соединение с {self.smtp_server}:{self.smtp_port}")
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=10)
            else:
                print(f"Устанавливаем соединение с {self.smtp_server}:{self.smtp_port}")
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10)
                server.starttls()

            print("Авторизация на SMTP сервере...")
            server.login(self.smtp_user, self.smtp_password)
            print("Авторизация прошла успешно!")

            # Отправляем письмо
            print("Отправка письма...")
            server.sendmail(from_addr, to_addrs, msg.as_string())
            print("Письмо успешно отправлено!")
            server.quit()

        except smtplib.SMTPAuthenticationError as e:
            print(f"Ошибка аутентификации: {e}")
            return False
        except smtplib.SMTPException as e:
            print(f"Ошибка при отправке письма: {e}")
            return False
        except Exception as e:
            print(f"Общая ошибка: {e}")
            return False

        return True

    def attach_file(self, file_path):
        try:
            attachment = open(file_path, "rb")
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(file_path)}')
            attachment.close()
            return part
        except Exception as e:
            print(f"Не удалось прикрепить файл {file_path}: {e}")
            return None
