import base64
from configparser import ConfigParser
import os
import re 
import requests
import imaplib
import time
from email import policy
from email.message import EmailMessage
from email.header import Header
from email.utils import formataddr
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QListWidgetItem
import subprocess
import tempfile
import json
import shutil
import logging
from email.utils import formatdate

from UiPy.UiNewMessage import Ui_Dialog
from Core.smtpclient import SMTPClient
import gost34122018_kuznechik as kuznezhik
import asimm_crypto
import find_key  


# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.FileHandler("mail_client.log"),  # Логирование в файл
        logging.StreamHandler()  # Логирование в консоль
    ]
)

class NewMessage(QtWidgets.QDialog):
    def __init__(self, config,parent=None):
        super(NewMessage, self).__init__(parent)
        self.config = config  
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)


        self.attached_files = []
        self.ui.pb_send.clicked.connect(self.send_email)
        self.ui.pushButton.clicked.connect(self.attach_file)
        self.ui.attachments_list.itemDoubleClicked.connect(self.remove_file)

    @QtCore.pyqtSlot(str)
    def showMessage(self, text):
        QtWidgets.QMessageBox.information(self, "Внимание", text, QtWidgets.QMessageBox.Ok)

    def is_valid_email(self, email):
        """Проверяет, является ли введённый адрес электронной почты корректным."""
        regex = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
        return re.match(regex, email) is not None

    def attach_file(self):
        """Открывает диалог для выбора файла и добавляет его в список вложений."""
        file_dialog = QtWidgets.QFileDialog(self)
        file_path, _ = file_dialog.getOpenFileName(self, "Выберите файл для прикрепления")
        
        if file_path:
            # Добавляем путь к файлу в список прикрепленных файлов
            self.attached_files.append(file_path)
            
            # Обновляем QListWidget с прикрепленными файлами
            list_item = QListWidgetItem(os.path.basename(file_path))  
            self.ui.attachments_list.addItem(list_item)
            
            logging.info(f"Файл {file_path} был прикреплён")

    def remove_file(self, item):
        """Удаляет выбранный файл из списка."""
        row = self.ui.attachments_list.row(item)
        del self.attached_files[row]  # Удаляем файл из списка прикрепленных
        self.ui.attachments_list.takeItem(row)  # Удаляем элемент из списка отображения
        logging.info(f"Файл {item.text()} был удалён из вложений")

    def find_sent_folder(self, mail):
        """
        Ищет папку "Отправленные" (или её аналог) сначала по флагу \Sent,
        а если не находит, то перебирает список популярных названий.
        Возвращает имя папки (str) или None.
        """
        try:
            typ, folder_list = mail.list()
            if typ != 'OK':
                logging.error(f"Не удалось получить список папок: {folder_list}")
                return None

            parsed_folders = []
            for raw_line in folder_list:
                line_str = raw_line.decode(errors='replace')
                flags_part = line_str.split(')')[0].replace('(', '').strip()
                flags = flags_part.split()
                
                # После '" "' идёт название
                # Сплитим по '"/"'
                parts = line_str.split('"/"')
                if len(parts) > 1:
                    folder_name_part = parts[-1].strip()
                    folder_name_part = folder_name_part.strip('"')
                else:
                    folder_name_part = None

                parsed_folders.append((flags, folder_name_part))

            # 1) Смотрим флаг \Sent
            for flags, folder_name in parsed_folders:
                if '\\Sent' in flags:  # ищем именно такую запись
                    logging.debug(f"Найдена папка с флагом \\Sent: {folder_name}")
                    return folder_name

            # 2) Если не нашли — перебираем известные названия
            candidates = [
                "Sent", "Sent Items", "Sent Mail", "Отправленные",
                "Sent Messages", "Отправленные сообщения", "Mail/Sent",
                "INBOX.Sent", "INBOX.Отправленные"
            ]
            
            # Собираем список всех имён папок
            folder_names = [folder_name for _, folder_name in parsed_folders if folder_name]

            for candidate in candidates:
                if candidate in folder_names:
                    logging.debug(f"Найдена стандартная папка: {candidate}")
                    return candidate

            logging.warning("Папка 'Отправленные' не найдена ни по флагу, ни по имени.")
            return None

        except Exception as e:
            logging.error(f"Ошибка при поиске папки 'Отправленные': {e}", exc_info=True)
            return None

        
    

    def save_to_sent(self, email_message):
        """
        Сохраняет отправленное письмо в папку "Отправленные" через IMAP.
        """

        config_parser = ConfigParser()
        config_file_path = './MailClient-master/settings.ini'
        config_parser.read(config_file_path)
        
        smtp_user = config_parser.get("MAILSERVER", "mail")
        imap_server = config_parser.get("MAILSERVER", "imap_server")
        imap_port = config_parser.get("MAILSERVER", "imap_port")
        smtp_password = self.config["pwd"]  
        


        try:
            # Подключаемся к IMAP-серверу
            with imaplib.IMAP4_SSL(imap_server, imap_port) as mail:
                # Логинимся
                mail.login(smtp_user, smtp_password)
                sent_folder = self.find_sent_folder(mail)
        
                if not sent_folder:
                    sent_folder = "Sent"  # Явно указываем папку "Sent", если не удалось найти
                
                # Выбираем папку "Sent"
                typ, data = mail.select(sent_folder)
                
                if typ != 'OK':
                    logging.error(f"Не удалось выбрать папку {sent_folder}: {data}")
                    return False
                
                raw_email = email_message.as_bytes()
                
                # Добавляем флаг \Seen
                typ, msg_data = mail.append(sent_folder, '\\Seen', imaplib.Time2Internaldate(time.time()), raw_email)
                
                if typ != 'OK':
                    logging.error(f"Не удалось сохранить письмо в папку {sent_folder}: {msg_data}")
                    return False
                
                logging.info(f"Письмо успешно сохранено в папку '{sent_folder}'.")
                return True
        except imaplib.IMAP4.error as e:
            logging.error(f"IMAP ошибка: {e}")
            return False
        except Exception as e:
            logging.error(f"Общая ошибка при сохранении письма в папку 'Отправленные': {e}")
            return False

    def show_message(self, text):
        QtWidgets.QMessageBox.information(self, "Информация", text, QtWidgets.QMessageBox.Ok)

    def find_private_key(self):
        """Позволяет пользователю выбрать устройство с приватным ключом и возвращает путь к нему."""
        # Получаем список подключенных устройств
        drives = find_key.get_all_drives()
    
        if not drives:
            self.show_message("Не найдено доступных устройств для поиска приватного ключа.")
            return None
    
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Выбор устройства с приватным ключом")
        dialog.setFixedSize(330, 260)
    
        list_widget = QtWidgets.QListWidget(dialog)
        list_widget.setGeometry(10, 10, 300, 200)  
    
        for drive, label, fstype in drives:
            list_widget.addItem(f"{drive} - {label} ({fstype})")
    
        button = QtWidgets.QPushButton("Выбрать", dialog)
        button.setGeometry(10, 220, 80, 30)
    
        selected_private_key_path = None
    
        def on_select():
            nonlocal selected_private_key_path
            selected_item = list_widget.currentItem()
            if selected_item:
                selected_device = selected_item.text().split(" ")[0]  # Получаем только путь устройства
                filename = "private_key.key"
                # Поиск файла на выбранном устройстве
                file_path = find_key.find_file_on_drive(selected_device, filename)
                if file_path:
                    self.show_message(f"Приватный ключ найден по пути: {file_path}")
                    selected_private_key_path = file_path
                else:
                    self.show_message("Приватный ключ не найден на выбранном устройстве.")
                dialog.accept()  
    
        button.clicked.connect(on_select)
    
        dialog.exec_()
    
        return selected_private_key_path

    def find_local_sym_key(self):
        """Позволяет пользователю выбрать устройство с локальным ключом и возвращает путь к нему."""
        # Получаем список подключенных устройств
        drives = find_key.get_all_drives()
    
        if not drives:
            self.show_message("Не найдено доступных устройств для поиска локального ключа.")
            return None
    
        # Создаем диалог для выбора устройства
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Выбор устройства с локальным ключом")
        dialog.setFixedSize(330, 260)
    
        list_widget = QtWidgets.QListWidget(dialog)
        list_widget.setGeometry(10, 10, 300, 200)  
    
        # Добавляем устройства в список
        for drive, label, fstype in drives:
            list_widget.addItem(f"{drive} - {label} ({fstype})")
    
        # Кнопка для подтверждения выбора
        button = QtWidgets.QPushButton("Выбрать", dialog)
        button.setGeometry(10, 220, 80, 30)
    
        # Переменная для хранения пути к выбранному локальному ключу
        selected_local_key_path = None
    
        def on_select_local_key():
            nonlocal selected_local_key_path
            # Получаем выбранный элемент из списка
            selected_item = list_widget.currentItem()
            if selected_item:
                selected_device = selected_item.text().split(" ")[0]  # Получаем только путь устройства
                filename = "local_symmetric.key"
                # Поиск файла на выбранном устройстве
                file_path = find_key.find_file_on_drive(selected_device, filename)
                if file_path:
                    self.show_message(f"Локальный ключ найден по пути: {file_path}")
                    selected_local_key_path = file_path
                else:
                    self.show_message("Локальный ключ не найден на выбранном устройстве.")
                dialog.accept()  
    
        button.clicked.connect(on_select_local_key)
    
        dialog.exec_()
    
        return selected_local_key_path

    def save_data_to_json(self, file_path: str, email: str, raw_bytes: bytes):
        """
        Добавляет строку и байты (закодированные в base64) в JSON-файл.
        Если файл не существует, он создается.
        :param file_path: путь к JSON-файлу
        :param email: строка
        :param raw_bytes: байтовые данные
        """
        new_entry = {
            "email": email,
            "bytes": base64.b64encode(raw_bytes).decode("utf-8")
        }

        try:
            # Если файл существует, читаем его содержимое
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                        # Проверяем, что это список; если нет, преобразуем в список
                        if not isinstance(data, list):
                            data = [data]
                    except json.JSONDecodeError:
                        logging.warning(f"Файл {file_path} поврежден или пуст. Будет создан новый файл.")
                        data = []
            else:
                data = []

            data.append(new_entry)

            # Перезаписываем файл с обновленными данными
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            logging.info(f"Запись для {email} добавлена в {file_path}.")
        except Exception as e:
            logging.error(f"Ошибка при сохранении данных в JSON-файл: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Ошибка",
                f"Произошла ошибка при сохранении данных: {e}",
                QtWidgets.QMessageBox.Ok
            )

    def send_email(self):
        check = self.ui.enc_check.isChecked()
        try:
            # Получаем тему, текст сообщения и прикрепленные файлы
            subject_text = self.ui.le_subject.text()
            if check:
                subject_text = 'enc/' + subject_text
            body = self.ui.te_content.toPlainText()

            recipient = self.ui.le_mail.text()

            # Валидация адреса электронной почты
            if not self.is_valid_email(recipient):
                QtWidgets.QMessageBox.warning(
                    self,
                    "Ошибка",
                    "Введён некорректный адрес электронной почты.",
                    QtWidgets.QMessageBox.Ok
                )
                return

            pub_key = None
            email_message = None  # Инициализируем переменную для сохранения копии письма

            if check:
                config_parser = ConfigParser()
                config_file_path = './MailClient-master/settings.ini'
                config_parser.read(config_file_path)
                my_email = config_parser.get("MAILSERVER", "mail")
                server_url=self.config["key_server"]
                jsn_folder_path = os.path.join('.', 'MailClient-master', 'local_secret', my_email)
                os.makedirs(jsn_folder_path, exist_ok=True)
                jsn_path = os.path.join(jsn_folder_path, 'contacts.json')
                print(f'\nпуть к json\n{jsn_path}\n')

                ca_cert_path = os.path.join('.', 'MailClient-master', 'CA', 'ca_certificate.crt')
                # Вычисляем хеш email получателя
                recipient_hash = asimm_crypto.hash_text(recipient)
                
                try:
                    # Получение сертификата с сервера
                    response = requests.get(f'{server_url}/get_user_cert', params={'email': recipient_hash})
                    if response.status_code == 200:
                        sender_pub_cert = base64.b64decode(response.json().get("public_key_cert"))
                        logging.debug(f'Сертификат получен: {sender_pub_cert}')
                        if not sender_pub_cert:
                            raise Exception("Публичный ключ не найден в ответе сервера.")
                    else:
                        error_message = response.json().get("error", "Неизвестная ошибка при получении публичного ключа.")
                        raise Exception(f"Не удалось получить публичный ключ: {error_message}")
                except Exception as e:
                    logging.error(f"Ошибка при получении сертификата: {str(e)}")
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Ошибка",
                        f"Не удалось получить сертификат получателя: {e}",
                        QtWidgets.QMessageBox.Ok
                    )
                    return

                try:
                    # Записываем сертификат во временный файл
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".crt") as cert_file:
                        temp_cert_path = cert_file.name
                        cert_file.write(sender_pub_cert)
                    logging.debug(f"Сертификат записан во временный файл: {temp_cert_path}")

                    # Извлекаем сертификат 
                    result = subprocess.run(
                        ["openssl", "x509", "-in", temp_cert_path, "-noout", "-text"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=True
                    )

                    # Проверяем сертификат на валидность
                    check_cert_from_CA = [
                        "openssl", 
                        "verify", 
                        "-CAfile", ca_cert_path, temp_cert_path
                    ]
                    result_check = subprocess.run(check_cert_from_CA, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

                    if result_check.returncode == 0:
                        logging.info(f"Сертификат успешно верифицирован: {result_check.stdout.strip()}")

                        # Ищем email-адрес в поле Subject или Subject Alternative Name
                        subject_email_found = False
                        san_email_found = False

                        for line in result.stdout.splitlines():
                            if "emailAddress=" in line:
                                if recipient in line:
                                    subject_email_found = True
                            elif "Subject Alternative Name" in line:
                                san_line_index = result.stdout.splitlines().index(line) + 1
                                if san_line_index < len(result.stdout.splitlines()):
                                    san_line = result.stdout.splitlines()[san_line_index]
                                    if recipient in san_line:
                                        san_email_found = True

                        if subject_email_found or san_email_found:
                            logging.info("Email найден в сертификате.") 

                            # Извлекаем публичный ключ из сертификата
                            cert_command = [
                                'openssl', 'x509',
                                '-in', temp_cert_path,
                                '-pubkey', '-noout'
                            ]

                            try:
                                result_pubkey = subprocess.run(cert_command, capture_output=True, text=True, check=True)
                                public_key_data = result_pubkey.stdout
                                logging.debug("Публичный ключ успешно извлечён.")
                                pub_key = asimm_crypto.parse_public_key_data(public_key_data)
                            except Exception as e:
                                logging.error(f"Ошибка при извлечении публичного ключа: {e}")
                                QtWidgets.QMessageBox.warning(
                                    self,
                                    "Ошибка",
                                    f"Ошибка при извлечении публичного ключа: {e}",
                                    QtWidgets.QMessageBox.Ok
                                )
                                return
                            finally:
                                # Удаляем временный файл сертификата
                                if os.path.exists(temp_cert_path):
                                    os.remove(temp_cert_path)
                                    logging.debug(f"Временный файл сертификата удалён: {temp_cert_path}")
                        else:
                            logging.warning("Email не найден в сертификате.")
                            # Удаляем временный файл сертификата
                            if os.path.exists(temp_cert_path):
                                os.remove(temp_cert_path)
                                logging.debug(f"Временный файл сертификата удалён: {temp_cert_path}")
                            self.showMessage("Публичный ключ не принадлежит получателю.")
                            return
                    else:
                        logging.error(f"Сертификат не прошёл верификацию: {result_check.stderr.strip()}")
                        self.showMessage(f"Сертификат не прошёл верификацию: {result_check.stderr.strip()}")
                        # Удаляем временный файл сертификата
                        if os.path.exists(temp_cert_path):
                            os.remove(temp_cert_path)
                        return
                except Exception as e:
                    logging.error(f"Общая ошибка при обработке сертификата: {e}")
                    self.showMessage(f"Общая ошибка при обработке сертификата: {e}")
                    # Удаляем временный файл сертификата, если он существует
                    if 'temp_cert_path' in locals() and os.path.exists(temp_cert_path):
                        os.remove(temp_cert_path)
                    return

                # Шифруем тело сообщения, если найден публичный ключ
                if pub_key:
                    private_key_path = self.find_private_key()
                    if not private_key_path:
                        logging.error("Приватный ключ не найден или выбор устройства отменён пользователем.")
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Ошибка",
                            "Приватный ключ не найден или выбор устройства отменён пользователем.",
                            QtWidgets.QMessageBox.Ok
                        )
                        return

                    # Чтение приватного ключа из выбранного файла
                    try:
                        private_key = asimm_crypto.extract_private_key_openssl_text(private_key_path)
                        logging.debug(f"Приватный ключ успешно извлечён из {private_key_path}")
                    except FileNotFoundError:
                        logging.error(f"Файл приватного ключа не найден: {private_key_path}")
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Ошибка",
                            f"Файл приватного ключа не найден: {private_key_path}",
                            QtWidgets.QMessageBox.Ok
                        )
                        return
                    except Exception as e:
                        logging.error(f"Ошибка при чтении приватного ключа: {e}")
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Ошибка",
                            f"Ошибка при чтении приватного ключа: {e}",
                            QtWidgets.QMessageBox.Ok
                        )
                        return

                    # Генерация симметричного ключа
                    try:
                        master_key = asimm_crypto.gen_sym(private_key, pub_key)
                        logging.debug(f"Сгенерированный симметричный ключ: {master_key.hex()}")
                    except Exception as e:
                        logging.error(f"Ошибка при генерации симметричного ключа: {e}")
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Ошибка",
                            f"Ошибка при генерации симметричного ключа: {e}",
                            QtWidgets.QMessageBox.Ok
                        )
                        return
                    
                    # Проверяем и создаем JSON-файл, если нужно
                    try:
                        if not os.path.exists(jsn_path):
                            os.makedirs(os.path.dirname(jsn_path), exist_ok=True)
                            with open(jsn_path, 'w', encoding='utf-8') as f:
                                json.dump([], f, ensure_ascii=False, indent=4)
                            logging.debug(f"Создан новый JSON-файл: {jsn_path}")
                    except Exception as e:
                        logging.error(f"Ошибка при создании JSON-файла: {e}")
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Ошибка",
                            f"Ошибка при создании JSON-файла: {e}",
                            QtWidgets.QMessageBox.Ok
                        )
                        return

                    # Чтение JSON-файла и проверка существования записи
                    try:
                        with open(jsn_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        # Убедимся, что данные — это список
                        if not isinstance(data, list):
                            data = [data]
                    except json.JSONDecodeError:
                        logging.warning(f"Файл {jsn_path} поврежден или пуст. Будет создан новый список.")
                        data = []
                    except Exception as e:
                        logging.error(f"Ошибка при чтении JSON-файла: {e}")
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Ошибка",
                            f"Ошибка при чтении JSON-файла: {e}",
                            QtWidgets.QMessageBox.Ok
                        )
                        return

                    existing_entry = next((entry for entry in data if entry.get("email") == recipient), None)

                    if existing_entry:
                        logging.info(f"Запись для {recipient} уже существует. Обновление не требуется.")
                    else:
                        # Выполняем шифрование только один раз
                        local_sym_key_path = self.find_local_sym_key()
                        if not local_sym_key_path:
                            logging.error("Локальный ключ не найден или выбор устройства отменён пользователем.")
                            QtWidgets.QMessageBox.warning(
                                self,
                                "Ошибка",
                                "Локальный ключ не найден или выбор устройства отменён пользователем.",
                                QtWidgets.QMessageBox.Ok
                            )
                            return  
                        
                        try:
                            process = subprocess.Popen(
                                ["openssl", "enc", "-kuznyechik-ctr", "-pass", f"file:{local_sym_key_path}"],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                            )
                            encrypted_secret, error = process.communicate(input=master_key)
                            
                            if process.returncode != 0:
                                logging.error(f"Ошибка шифрования: {error.decode()}")
                                QtWidgets.QMessageBox.critical(
                                    self,
                                    "Ошибка",
                                    f"Произошла ошибка при шифровании: {error.decode()}",
                                    QtWidgets.QMessageBox.Ok
                                )
                                return
                            
                            self.save_data_to_json(jsn_path, recipient, encrypted_secret)
                            
                            # Добавляем новую запись
                            new_entry = {
                                "email": recipient,
                                "bytes": base64.b64encode(encrypted_secret).decode('utf-8')  
                            }
                            data.append(new_entry)
                            
                            # Сохраняем обновленные данные обратно в JSON-файл
                            with open(jsn_path, "w", encoding="utf-8") as f:
                                json.dump(data, f, ensure_ascii=False, indent=4)
                            
                            logging.info(f"Добавлена новая запись для {recipient}.")
                        except Exception as e:
                            logging.error(f"Ошибка при шифровании или сохранении данных: {e}")
                            QtWidgets.QMessageBox.warning(
                                self,
                                "Ошибка",
                                f"Ошибка при шифровании или сохранении данных: {e}",
                                QtWidgets.QMessageBox.Ok
                            )
                            return

                    # Шифрование сообщения
                    try:
                        encrypted_body = kuznezhik.encrypt_message(body, master_key)
                        body = base64.b64encode(encrypted_body).decode('utf-8')
                        logging.debug("Тело сообщения успешно зашифровано.")
                    except Exception as e:
                        logging.error(f"Ошибка при шифровании сообщения: {e}")
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Ошибка",
                            f"Ошибка при шифровании сообщения: {e}",
                            QtWidgets.QMessageBox.Ok
                        )
                        return
                else:
                    logging.debug("Шифрование не выбрано. Продолжаем отправку без шифрования.")

            # Обработка вложений при шифровании
            if self.attached_files and check:
                encrypted_attachments = []
                temp_dir = os.path.join(os.getcwd(), "temp")

                # Проверяем и создаем папку temp, если её нет
                if not os.path.exists(temp_dir):
                    os.makedirs(temp_dir)
                    logging.debug(f"Создана временная папка для зашифрованных вложений: {temp_dir}")

                for file_path in self.attached_files:
                    file_name = os.path.basename(file_path)
                    encrypted_file_name = file_name + '.enc'  
                    encrypted_file_path = os.path.join(temp_dir, encrypted_file_name)
                    
                    # Шифруем файл и сохраняем по новому пути
                    try:
                        kuznezhik.encrypt_file(file_path, encrypted_file_path, master_key)
                        encrypted_attachments.append(encrypted_file_path)
                        logging.debug(f"Файл {file_path} зашифрован и сохранён как {encrypted_file_path}")
                    except Exception as e:
                        logging.error(f"Ошибка при шифровании файла {file_path}: {e}")
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Ошибка",
                            f"Ошибка при шифровании файла {file_path}: {e}",
                            QtWidgets.QMessageBox.Ok
                        )
                        return

                # Обновляем список прикрепленных файлов на зашифрованные файлы
                self.attached_files = encrypted_attachments

                # Обновляем GUI список вложений
                self.ui.attachments_list.clear()
                for encrypted_file_path in encrypted_attachments:
                    list_item = QListWidgetItem(os.path.basename(encrypted_file_path))
                    self.ui.attachments_list.addItem(list_item)

            config_parser = ConfigParser()
            config_file_path = './MailClient-master/settings.ini'
            config_parser.read(config_file_path)
            smtp_password = self.config["pwd"]
            smtp_user = config_parser.get("MAILSERVER", "mail")

            if not smtp_user or not smtp_password:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Ошибка",
                    "Отсутствуют данные для авторизации SMTP.",
                    QtWidgets.QMessageBox.Ok
                )
                return

            logging.info("Отправка письма начата...")

            # Формируем заголовок From с кодировкой
            from_addr = formataddr((str(Header(f'{smtp_user}', 'utf-8')), smtp_user))

            logging.debug(f"From: {from_addr} (type: {type(from_addr)})")
            logging.debug(f"To: {[recipient]} (type: {type([recipient])}, elements: {[type(addr) for addr in [recipient]]})")
            logging.debug(f"Subject: {subject_text} (type: {type(subject_text)})")
            logging.debug(f"Body: {body} (type: {type(body)})")
            logging.debug(f"Attached Files: {self.attached_files} (type: {type(self.attached_files)}, elements: {[type(f) for f in self.attached_files]})")

            # Создаём EmailMessage для сохранения копии в "Отправленные"
            email_message = EmailMessage(policy=policy.SMTPUTF8)
            email_message['From'] = from_addr
            email_message['To'] = recipient
            email_message['Subject'] = Header(subject_text, 'utf-8').encode()
            email_message.set_content(body, charset='utf-8')
            email_message['Date'] = formatdate(localtime=True)

            # Добавляем вложения
            for file_path in self.attached_files:
                try:
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                        file_name = os.path.basename(file_path)
                    email_message.add_attachment(file_data, maintype='application', subtype='octet-stream', filename=file_name)
                    logging.debug(f"Вложение {file_name} добавлено к EmailMessage.")
                except Exception as e:
                    logging.error(f"Ошибка при добавлении вложения {file_path} к EmailMessage: {e}")
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Ошибка",
                        f"Ошибка при добавлении вложения {file_path} к письму: {e}",
                        QtWidgets.QMessageBox.Ok
                    )
                    return

            # Отправляем письмо через SMTP-клиент
            smtp_client = SMTPClient(
                self.config["smtp_server"],
                self.config["smtp_port"],
                smtp_user,
                smtp_password,
                use_ssl=True
            )
            success = smtp_client.send_mail(from_addr, [recipient], subject_text, body, self.attached_files)

            if success:
                logging.info("Письмо успешно отправлено!")

                # Сохранение копии письма в папку "Отправленные" через IMAP
                save_success = self.save_to_sent(email_message)
                if save_success:
                    logging.info("Письмо успешно сохранено в папку 'Отправленные'.")
                else:
                    logging.error("Не удалось сохранить письмо в папку 'Отправленные'.")

                # Удаляем зашифрованные файлы из temp_dir
                if check and self.attached_files:
                    for encrypted_file in self.attached_files:
                        try:
                            os.remove(encrypted_file)
                            logging.debug(f"Удалён временный файл: {encrypted_file}")
                        except Exception as e:
                            logging.error(f"Ошибка при удалении файла {encrypted_file}: {e}")
                    # Удаляем папку temp_dir, если она пуста
                    try:
                        if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                            shutil.rmtree(temp_dir)
                    except Exception as e:
                        logging.error(f"Ошибка при удалении папки {temp_dir}: {e}")

                QtWidgets.QMessageBox.information(
                    self,
                    "Успех",
                    "Письмо успешно отправлено!",
                    QtWidgets.QMessageBox.Ok
                )
                self.close()
            else:
                logging.error("Не удалось отправить письмо через SMTP-клиент.")
                QtWidgets.QMessageBox.warning(
                    self,
                    "Ошибка",
                    "Не удалось отправить письмо.",
                    QtWidgets.QMessageBox.Ok
                )

        except Exception as e:
            logging.error(f"Произошла ошибка при отправке письма: {e}", exc_info=True)
            QtWidgets.QMessageBox.warning(
                self,
                "Ошибка",
                f"Произошла ошибка при отправке письма: {e}",
                QtWidgets.QMessageBox.Ok
            )
