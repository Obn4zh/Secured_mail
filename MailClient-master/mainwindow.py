from email.header import decode_header
import base64
import logging
import os
from configparser import ConfigParser
import requests
import asimm_crypto
from PyQt5 import QtCore, QtGui, QtWidgets
from UiPy.UiMainWindow import Ui_MainWindow
from loadsettings import Settings
from settingsdialog import SettingsDialog
from newmessage import NewMessage
from threading import Thread
import tablemodel
from gost34122018_kuznechik import decrypt_message, decrypt_file
import shutil
import find_key
import subprocess
import tempfile
import json


class CertificateDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(CertificateDialog, self).__init__(parent)
        self.setWindowTitle("Информация для сертификата(вводить на английском)")
        self.resize(550, 400)

        layout = QtWidgets.QVBoxLayout(self)
        config_parser = ConfigParser()
        config_file_path = './MailClient-master/settings.ini'
        config_parser.read(config_file_path)
        user_email = config_parser.get("MAILSERVER", "mail")

        self.fields = {
            "C": QtWidgets.QLineEdit(self),
            "ST": QtWidgets.QLineEdit(self),
            "L": QtWidgets.QLineEdit(self),
            "O": QtWidgets.QLineEdit(self),
            "OU": QtWidgets.QLineEdit(self),
            "CN": QtWidgets.QLineEdit(self),
            "emailAddress": QtWidgets.QLineEdit(self),
        }

        self.labels = {
            "C": QtWidgets.QLabel("Страна (C)⎵⎵:", self),
            "ST": QtWidgets.QLabel("Регион (ST):", self),
            "L": QtWidgets.QLabel("Город (L):", self),
            "O": QtWidgets.QLabel("Организация (O):", self),
            "OU": QtWidgets.QLabel("Подразделение (OU):", self),
            "CN": QtWidgets.QLabel("ФИО (CN):", self),
            "emailAddress": QtWidgets.QLabel("Email (E):", self),
        }

        self.fields["emailAddress"].setText(user_email)
        self.fields["emailAddress"].setReadOnly(True)

        for field_key, line_edit in self.fields.items():
            layout.addWidget(self.labels[field_key])
            layout.addWidget(line_edit)

        self.ok_button = QtWidgets.QPushButton("OK", self)
        # self.cancel_button = QtWidgets.QPushButton("Отмена", self)

        self.ok_button.clicked.connect(self.accept)
        # self.cancel_button.clicked.connect(self.reject)

        layout.addWidget(self.ok_button)
        # layout.addWidget(self.cancel_button)

    def get_certificate_data(self):
        return {key: field.text() for key, field in self.fields.items()}


class MailHeader:
    def __init__(self, uid=None, send_from=None, send_to=None, subject=None, date=None):
        self.uid = uid
        self.send_from = send_from
        self.send_to = send_to
        self.subject = subject
        self.date = date


class MainWindow(QtWidgets.QMainWindow):

    threadInfoText = QtCore.pyqtSignal()
    threadInfoStatus = QtCore.pyqtSignal(str)
    threadInfoMessage = QtCore.pyqtSignal(str)
    threadInfoAttachments = QtCore.pyqtSignal()

    def __init__(self, connection, config, parent=None):
        super(MainWindow, self).__init__(parent)
        self.config = config
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.receiver_private_key_path = None
        self.attached_files = []
        self.ui.attachments_list.itemDoubleClicked.connect(self.download_attachment)

        self.isWork = 0
        self.connection = connection
        self.typeView = None
        self.body = None
        self.attachments = []
        self.selected_mail = None

        self.ui.exitAct.triggered.connect(self.exitMethod, QtCore.Qt.QueuedConnection)
        self.ui.newMail.triggered.connect(self.showDialogNewMessage, QtCore.Qt.QueuedConnection)
        self.ui.settingsAct.triggered.connect(self.showSettingsDialog, QtCore.Qt.QueuedConnection)
        self.ui.updateAct.triggered.connect(self.updateModel, QtCore.Qt.QueuedConnection)
        self.ui.keygenAct.triggered.connect(self.keygenAct, QtCore.Qt.QueuedConnection)
        self.ui.decrypt_button.clicked.connect(self.decrypt_email)

        self.threadInfoText.connect(self.showBody, QtCore.Qt.QueuedConnection)
        self.threadInfoStatus[str].connect(self.showStatus, QtCore.Qt.QueuedConnection)
        self.threadInfoMessage[str].connect(self.showMessage, QtCore.Qt.QueuedConnection)
        self.threadInfoAttachments.connect(self.updateAttachmentsList, QtCore.Qt.QueuedConnection)

        self.ui.tv_mailbox.selectObject.connect(self.showModel)
        self.ui.tv_mailbox.expandAll()
        self.ui.tv_maillist.clicked.connect(self.getBody)

        self.model = tablemodel.TableModel(self)
        self.ui.tv_maillist.setModel(self.model)

        self.threadLoadHeader = Thread()
        self.threadLoadBody = Thread()

        self.exitThread = False
        self.exit = False

    def hideDecryptButton(self):
        self.ui.decrypt_button.setVisible(False)
        self.ui.decrypt_placeholder.setVisible(True)

    def closeEvent(self, event=QtGui.QCloseEvent()):
        self.exitThread = True
        if not self.exit:
            self.connection.logout()
        event.accept()

    @QtCore.pyqtSlot()
    def closeMethod(self):
        self.exitThread = True
        self.exit = True
        self.connection.logout()
        self.isWork = 0
        self.close()

    @QtCore.pyqtSlot()
    def exitMethod(self):
        self.exitThread = True
        self.exit = True
        self.connection.logout()
        self.isWork = 2
        self.close()

    def windowStatus(self):
        return self.isWork

    @QtCore.pyqtSlot(str)
    def showModel(self, typeView):
        self.typeView = typeView
        self.clear_table()
        self.initTable()
        self.hideDecryptButton()

    def clear_table(self):
        self.model.clear_data()
        self.ui.te_content.clear()

    @QtCore.pyqtSlot()
    def updateModel(self):
        self.clear_table()
        self.initTable()

    @QtCore.pyqtSlot()
    def keygenAct(self):
        config_parser = ConfigParser()
        config_file_path = './MailClient-master/settings.ini'
        config_parser.read(config_file_path) 
        key_server = config_parser.get("MAILSERVER", "key_server")
        user_email = config_parser.get("MAILSERVER", "mail")
        user_email_hash = asimm_crypto.hash_text(user_email)
        smtp_password = self.config["pwd"]

        # Проверяем наличие записи на сервере
        try:
            response = requests.get(f"{key_server}/check_user", params={"email": user_email_hash})
            if response.status_code == 200 and response.json().get("exists"):
                # Запись существует, показываем предупреждение
                confirm = QtWidgets.QMessageBox.question(
                    self,
                    "Предупреждение",
                    "Если вы сгенерируете новые ключи, доступ к старым зашифрованным письмам будет утрачен. Вы действительно хотите продолжить?",
                    QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel,
                    QtWidgets.QMessageBox.Cancel
                )
                if confirm == QtWidgets.QMessageBox.Cancel:
                    return  # Отменяем генерацию
            
                # Окно ввода пароля
                password_dialog = QtWidgets.QInputDialog(self)
                password_dialog.setWindowTitle("Введите пароль")
                password_dialog.setLabelText("Для продолжения введите пароль:")
                password_dialog.setTextEchoMode(QtWidgets.QLineEdit.Password)
                
                if password_dialog.exec_() == QtWidgets.QDialog.Accepted:
                    entered_password = password_dialog.textValue()

                    if entered_password != smtp_password:
                        QtWidgets.QMessageBox.critical(self, "Ошибка", "Пароль введен неверно!")
                        return  # Останавливаем процесс
                else:
                    return  

        except requests.RequestException as e:
            print(f"Ошибка проверки на сервере: {e}")
            QtWidgets.QMessageBox.critical(self, "Ошибка", "Ошибка соединения с сервером.")
            return

        jsn_folder_path = f'./MailClient-master/local_secret/{user_email}'
        jsn_path = f'{jsn_folder_path}/contacts.json'

        # Если подтверждение получено или записи нет, выполняем генерацию ключей
        try:
            # Убедимся, что директория для файла существует
            os.makedirs(os.path.dirname(jsn_path), exist_ok=True)

            # Записываем пустой список в JSON-файл
            with open(jsn_path, 'w', encoding='utf-8') as f:
                json.dump([], f)
            print(f"Файл {jsn_path} успешно очищен.")
        except Exception as e:
            print(f"Ошибка при очистке файла {jsn_path}: {e}")

        # Генерация ключей
        self.generate_keys()


    def initTable(self):
        if not self.threadLoadHeader.is_alive():
            if self.threadLoadHeader.is_alive():
                self.threadLoadHeader.join()
            del self.threadLoadHeader
            self.threadLoadHeader = Thread(target=self.loadHeader, args=(self.typeView,), daemon=True)
            self.threadLoadHeader.start()
        self.ui.te_content.setHtml("")
        self.ui.tv_maillist.setColumnWidth(0, 150)
        self.ui.tv_maillist.setColumnWidth(1, 150)
        self.ui.tv_maillist.setColumnWidth(2, 270)
        self.ui.tv_maillist.setColumnWidth(3, 120)

    @QtCore.pyqtSlot(QtCore.QModelIndex)
    def getBody(self, index):
        if not self.threadLoadBody.is_alive():
            if self.threadLoadBody.is_alive():
                self.threadLoadBody.join()
            del self.threadLoadBody
            self.threadLoadBody = Thread(target=self.loadBody, args=(index,), daemon=True)
            self.threadLoadBody.start()
        self.showStatus("Количество писем: " + str(self.model.rowCount()))

        mail_header = self.model.mail[index.row()]
        self.selected_mail = mail_header

        subject = mail_header.subject if mail_header.subject else ""

        if subject.startswith("enc/"):
            self.ui.decrypt_placeholder.setVisible(False)
            self.ui.decrypt_button.setVisible(True)
        else:
            self.hideDecryptButton()

    def loadBody(self, index):
        self.body = "Загрузка содержания письма..."
        self.threadInfoText.emit()

        uid = self.model.uid(index)

        try:
            body, attachments = self.connection.fetch_body_and_attachments_by_uid(uid)
            self.body = body
            self.attachments = attachments
        except Exception as e:
            print(f"Ошибка при загрузке тела письма: {e}")
            self.threadInfoStatus.emit("Ошибка при загрузке письма.")
            return

        self.threadInfoText.emit()
        self.threadInfoAttachments.emit()

        if self.typeView == "unread":
            try:
                self.connection.mark_seen(uid)
            except Exception as e:
                print(f"Ошибка при отметке письма как прочитанного: {e}")

    @QtCore.pyqtSlot()
    def updateAttachmentsList(self):
        self.ui.attachments_list.clear()
        if self.attachments:
            for filename, _ in self.attachments:
                list_item = QtWidgets.QListWidgetItem(filename)
                self.ui.attachments_list.addItem(list_item)

    def download_attachment(self, item):
        filename = item.text()

        # Сначала проверяем расшифрованные вложения
        for decrypted_path in self.attached_files:
            if os.path.basename(decrypted_path) == filename:
                save_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Сохранить файл", filename)
                if save_path:
                    try:
                        shutil.copy(decrypted_path, save_path)
                        print(f"Файл сохранён: {save_path}")
                        self.showMessage(f"Файл сохранён: {save_path}")

                        # Удаляем временный расшифрованный файл после успешного копирования
                        os.remove(decrypted_path)
                        print(f"Временный файл удалён: {decrypted_path}")

                        # Удаляем путь из списка расшифрованных файлов
                        self.attached_files.remove(decrypted_path)

                        # Удаляем элемент из списка виджетов
                        row = self.ui.attachments_list.row(item)
                        self.ui.attachments_list.takeItem(row)

                    except Exception as e:
                        print(f"Ошибка при сохранении файла {filename}: {e}")
                        self.showMessage(f"Ошибка при сохранении файла {filename}: {e}")
                return  

        # Если не найдено среди расшифрованных, ищем в исходных вложениях
        for fname, data in self.attachments:
            if fname == filename:
                save_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Сохранить файл", fname)

                if save_path:
                    try:
                        with open(save_path, 'wb') as f:
                            f.write(data)
                        print(f"Файл сохранён: {save_path}")
                        self.showMessage(f"Файл сохранён: {save_path}")
                    except Exception as e:
                        print(f"Ошибка при сохранении файла {fname}: {e}")
                        self.showMessage(f"Ошибка при сохранении файла {fname}: {e}")
                break

    def decode_subject(self, subject):
        """Декодирует тему письма из base64/quoted-printable в строку"""
        if not subject:
            return ""
        decoded_fragments = decode_header(subject)
        decoded_subject = ''
        for fragment, encoding in decoded_fragments:
            if isinstance(fragment, bytes):
                encoding = encoding or 'utf-8'
                try:
                    decoded_subject += fragment.decode(encoding, errors='replace')
                except Exception as e:
                    decoded_subject += "?"
            else:
                decoded_subject += fragment
        return decoded_subject



    def loadHeader(self, view):
        typeView = view
        recursive = False
        self.threadInfoStatus.emit("Запрос получения писем из почтового ящика...")
        rowCountMail = 0
        mail = []
        headers = []

        try:

            if typeView == "unread":
                # Выбираем INBOX и считаем непрочитанные
                self.connection.select_folder("INBOX")
                rowCountMail = self.connection.count(unread=True)
                headers = self.connection.headers(unread=True)
                if rowCountMail == 0:
                    self.threadInfoStatus.emit("Непрочитанных писем нет.")
                self.model.updateModel(headers, rowCountMail)

            elif typeView == "all":
                self.connection.select_folder("INBOX")
                rowCountMail = self.connection.count()
                headers = self.connection.headers()
                
            elif typeView == "sent":
                print("Папки на сервере:")
                self.connection.select_folder("Отправленные")

                folder_name = self.connection.find_sent_folder_any()  
                if not folder_name:
                    self.threadInfoStatus.emit("Не найдена папка для исходящих (\\Sent)!")
                    return
                
                # Если папка найдена, выбираем её
                self.connection.select_folder(folder_name)


                rowCountMail = self.connection.count()
                headers = self.connection.headers()

            else:
                # По умолчанию INBOX
                self.connection.select_folder("INBOX")
                rowCountMail = self.connection.count()
                headers = self.connection.headers()

        except Exception as e:
            print(f"Ошибка IMAP соединения: {e}")
            self.threadInfoStatus.emit("Ошибка подключения к серверу.")
            return

        # Теперь формируем список mail[]
        for item in headers:
            if self.exitThread:
                return
            if typeView != self.typeView:
                recursive = True
                break

            uid = item[0]       # msg.uid
            header_data = item[1]  # { "sent_from": [...], ... }
            sent_from = header_data["sent_from"][0]["email"] if header_data.get("sent_from") else None
            sent_to = header_data["sent_to"][0]["email"] if header_data.get("sent_to") else None
            subject = header_data.get("subject", None)
            subject = self.decode_subject(subject)  
            date = header_data.get("date", None)

            mail.append(MailHeader(uid, sent_from, sent_to, subject, date))

        if not recursive:
            mail.reverse()
            self.model.updateModel(mail, rowCountMail)
            self.threadInfoStatus.emit("Готово.")
        else:
            self.threadInfoStatus.emit("Стоп.")
            self.threadInfoMessage.emit("Смена папки во время загрузки. Обновите почтовый ящик.")



    @QtCore.pyqtSlot()
    def showBody(self):
        if self.body:
            self.ui.te_content.setPlainText(self.body)
        else:
            self.ui.te_content.setPlainText("Содержимое письма отсутствует.")

    @QtCore.pyqtSlot(str)
    def showStatus(self, text):
        self.ui.statusbar.showMessage(text)

    @QtCore.pyqtSlot(str)
    def showMessage(self, text):
        QtWidgets.QMessageBox.information(self, "Внимание", text, QtWidgets.QMessageBox.Ok)

    @QtCore.pyqtSlot()
    def showDialogNewMessage(self):
        dialog = NewMessage(self.config)
        dialog.exec_()

    @QtCore.pyqtSlot()
    def showSettingsDialog(self):
        self.settingsDlg = SettingsDialog(self.config)
        self.settingsDlg.exec_()

    def generate_keys(self):
       
        try:
            config_parser = ConfigParser()
            config_file_path = './MailClient-master/settings.ini'
            config_parser.read(config_file_path)
            key_server = config_parser.get("MAILSERVER", "key_server")


            try:
                user_email = config_parser.get("MAILSERVER", "mail")
                user_email_hash = asimm_crypto.hash_text(user_email)
                print(f"Отладка: Получен email пользователя: {user_email}")
            except Exception as e:
                print("Ошибка: Не удалось прочитать почтовый адрес из файла настроек.", e)
                QtWidgets.QMessageBox.critical(self, "Ошибка", "Не удалось прочитать почтовый адрес из файла настроек.")
                return

            # Предлагаем пользователю выбрать устройство для сохранения приватного ключа
            selected_device = self.select_device_for_key()
            if not selected_device:
                self.showMessage("Сохранение ключа отменено пользователем.")
                return

            user_dir = os.path.join(selected_device, user_email)
            os.makedirs(user_dir, exist_ok=True)
            priv_key_path = os.path.join(user_dir, "private_key.key")
            csr_path = os.path.join(user_dir, 'request.csr')
            cert_path = os.path.join(user_dir, 'certificate.crt')


            subprocess.run([
            'openssl', 'rand',
            '-provider', 'gost',
            '-out', os.path.join(user_dir, 'local_symmetric.key'), '32'
        ], check=True)


            # Открыть диалог для ввода данных сертификата
            cert_dialog = CertificateDialog(self)
            if cert_dialog.exec_() == QtWidgets.QDialog.Accepted:
                cert_data = cert_dialog.get_certificate_data()
            else:
                self.showMessage("Создание сертификата отменено.")
                return


            asimm_crypto.generate_key_pair(priv_key_path,csr_path,cert_data,user_dir)
            print(f"Отладка: Сертификат успешно создан: {cert_path}")

            #Пуш сертификата на сервер
            with open(cert_path, 'rb') as cert_file:
                cert_data = base64.b64encode(cert_file.read()).decode('utf-8')
            try:
                response = requests.post(f"{key_server}/add_user_cert", json={
                    "email": user_email_hash,
                    "public_key_cert": cert_data,
                    
                })
                if response.status_code == 200:
                    print("Отладка: Публичный ключ успешно отправлен на сервер.")
                    QtWidgets.QMessageBox.information(self, "Генерация ключей",
                                                    f"Ключевая пара успешно сгенерирована.\nПриватный ключ сохранен по пути: {priv_key_path}")
                else:
                    print("Ошибка сервера:", response.json())
                    QtWidgets.QMessageBox.critical(self, "Ошибка", "Не удалось сохранить публичный ключ на сервере.")

            except requests.RequestException as e:
                    print("Ошибка соединения с сервером:", e)
                    QtWidgets.QMessageBox.critical(self, "Ошибка", "Ошибка соединения с сервером.")
        except Exception as e:
            print("Ошибка: Не удалось сгенерировать ключевую пару.", e)
            QtWidgets.QMessageBox.critical(self, "Ошибка", "Не удалось сгенерировать ключевую пару.")
            return


    def show_message(self, text):
        QtWidgets.QMessageBox.information(self, "Информация", text, QtWidgets.QMessageBox.Ok)

    def select_device_for_key(self):    
        # Получаем список подключенных устройств
        drives = find_key.get_all_drives()

        if not drives:
            self.showMessage("Не найдено доступных устройств для сохранения ключа.")
            return None

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Выбор устройства для сохранения ключа")

        list_widget = QtWidgets.QListWidget(dialog)
        list_widget.setGeometry(10, 10, 300, 200)

        for drive, label, fstype in drives:
            list_widget.addItem(f"{drive} - {label} ({fstype})")

        button = QtWidgets.QPushButton("Выбрать", dialog)
        button.setGeometry(10, 220, 80, 30)

        selected_device = None

        def on_select():
            selected_item = list_widget.currentItem()
            if selected_item:
                selected_device_path = selected_item.text().split(" ")[0]
                nonlocal selected_device
                selected_device = selected_device_path
            dialog.accept()

        button.clicked.connect(on_select)

        dialog.exec_()
        return selected_device

    def find_key(self):
        drives = find_key.get_all_drives()

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Выбор устройства")

        list_widget = QtWidgets.QListWidget(dialog)
        list_widget.setGeometry(10, 10, 300, 200)

        for drive, label, fstype in drives:
            list_widget.addItem(f"{drive} - {label} ({fstype})")

        button = QtWidgets.QPushButton("Выбрать", dialog)
        button.setGeometry(10, 220, 80, 30)

        selected_private_key_path = None

        def on_select():
            selected_item = list_widget.currentItem()
            if selected_item:
                selected_device = selected_item.text().split(" ")[0]
                filename = "private_key.key"
                file_path = find_key.find_file_on_drive(selected_device, filename)
                if file_path:
                    self.showMessage(f"Приватный ключ найден по пути: {file_path}")
                    nonlocal selected_private_key_path
                    selected_private_key_path = file_path
                else:
                    self.showMessage("Приватный ключ не найден.")
            dialog.accept()

        button.clicked.connect(on_select)

        dialog.exec_()
        return selected_private_key_path

    def process_selected_device(self, device_path):

        filename = "private_key.key"
        file_path = find_key.find_file_on_drive(device_path, filename)

        if file_path:
            self.showMessage(f"Приватный ключ найден по пути: {file_path}")
            return file_path
        else:
            self.showMessage("Приватный ключ не найден.")
            return None
        
    
    def find_local_sym_key(self):
            """Позволяет пользователю выбрать устройство с приватным ключом и возвращает путь к нему."""
            # Получаем список подключенных устройств
            drives = find_key.get_all_drives()
        
            if not drives:
                self.show_message("Не найдено доступных устройств для поиска приватного ключа.")
                return None
        
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("Выбор устройства с локальным ключом")
        
            # Создаем QListWidget для отображения списка устройств
            list_widget = QtWidgets.QListWidget(dialog)
            list_widget.setGeometry(10, 10, 300, 200)  
        
            # Добавляем устройства в список
            for drive, label, fstype in drives:
                list_widget.addItem(f"{drive} - {label} ({fstype})")
        
            button = QtWidgets.QPushButton("Выбрать", dialog)
            button.setGeometry(10, 220, 80, 30)
        
            selected_private_key_path = None
        
            def on_select_local_key():
                selected_item = list_widget.currentItem()
                if selected_item:
                    selected_device = selected_item.text().split(" ")[0]  # Получаем только путь устройства
                    filename = "local_symmetric.key"
                    # Поиск файла на выбранном устройстве
                    file_path = find_key.find_file_on_drive(selected_device, filename)
                    if file_path:
                        self.show_message(f"Локальный ключ найден по пути: {file_path}")
                        nonlocal selected_private_key_path  
                        selected_private_key_path = file_path
                    else:
                        self.show_message("Локальный ключ не найден на выбранном устройстве.")
                    dialog.accept()  
        
            button.clicked.connect(on_select_local_key)
        
            dialog.exec_()
        
            return selected_private_key_path

    def decrypt_self_mail(self, jsn_path, recivier_email):
        """
        Дешифрует письмо и его вложения для указанного отправителя из JSON-файла.

        :param jsn_path: Путь к JSON-файлу с зашифрованными данными.
        :param sender_email: Email отправителя, для которого необходимо выполнить дешифрование.
        """
        logging.info("Начало процесса дешифрования письма.")
        logging.debug(f"Путь к JSON-файлу: {jsn_path}, Email отправителя: {recivier_email}")

        try:
            # Чтение JSON-файла
            logging.debug("Чтение JSON-файла.")
            with open(jsn_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logging.debug(f"Загруженные данные: {data}")

            # Убедимся, что данные — это список
            if not isinstance(data, list):
                logging.debug("Данные не являются списком. Преобразование в список.")
                data = [data]
            else:
                logging.debug("Данные уже являются списком.")

            # Поиск записи с указанным email
            logging.info(f"Поиск записи для email: {recivier_email}")
            for entry in data:
                if entry.get("email") == recivier_email:
                    logging.info(f"Найдена запись для email: {recivier_email}")
                    
                    encrypted_base64 = entry.get("bytes")
                    if not encrypted_base64:
                        logging.error(f"Отсутствует поле 'bytes' для email: {recivier_email}")
                        self.showMessage(f"Отсутствуют зашифрованные данные для email: {recivier_email}.")
                        return

                    try:
                        encrypted_secret = base64.b64decode(encrypted_base64)
                        logging.debug(f"Расшифрованные байты секрета: {encrypted_secret.hex()}")
                    except base64.binascii.Error as e:
                        logging.error(f"Ошибка декодирования base64: {e}")
                        self.showMessage(f"Ошибка декодирования зашифрованного секрета: {e}")
                        return

                    # Поиск локального симметричного ключа
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

                    logging.debug(f"Путь к локальному симметричному ключу: {local_sym_key_path}")

                    try:
                        logging.info("Начало дешифрования секрета с помощью OpenSSL.")
                        process = subprocess.Popen(
                            ["openssl", "enc", "-d", "-kuznyechik-ctr", "-pass", f"file:{local_sym_key_path}"],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                        secret, error = process.communicate(input=encrypted_secret)
                        logging.debug(f"Возвращаемое значение секрета: {secret.hex()}")

                        if process.returncode != 0:
                            logging.error(f"Ошибка OpenSSL: {error.decode().strip()}")
                            self.showMessage(f"Ошибка дешифрования секрета: {error.decode().strip()}")
                            return

                        logging.info("Секрет успешно дешифрован.")
                    except Exception as e:
                        logging.exception("Не удалось выполнить дешифрование секрета с помощью OpenSSL.")
                        self.showMessage(f"Ошибка при дешифровании секрета: {e}")
                        return

                    # Дешифрование тела письма и вложений
                    try:
                        decrypted_text = ""
                        if self.body:
                            logging.info("Начало дешифрования тела письма.")
                            try:
                                encrypted_body = base64.b64decode(self.body)
                                decrypted_text = decrypt_message(encrypted_body, secret)
                                logging.debug("Тело письма успешно дешифровано.")
                            except Exception as e:
                                logging.error(f"Ошибка при дешифровании тела письма: {e}")
                                self.showMessage(f"Ошибка при дешифровании тела письма: {e}")
                                return
                        else:
                            logging.info("Тело письма отсутствует для дешифрования.")

                        # Дешифрование вложений
                        decrypted_attachments = []
                        temp_dir = os.path.join(os.getcwd(), "temp")
                        os.makedirs(temp_dir, exist_ok=True)
                        logging.debug(f"Временная директория для файлов: {temp_dir}")

                        if self.attachments:
                            logging.info(f"Начало дешифрования {len(self.attachments)} вложений.")
                            for idx, (filename, encrypted_data) in enumerate(self.attachments, start=1):
                                logging.debug(f"Дешифрование вложения {idx}: {filename}")
                                try:
                                    encrypted_file_path = os.path.join(temp_dir, filename)
                                    with open(encrypted_file_path, 'wb') as f:
                                        f.write(encrypted_data)
                                    logging.debug(f"Зашифрованный файл сохранён по пути: {encrypted_file_path}")

                                    decrypted_filename = filename[:-4] if filename.endswith('.enc') else filename
                                    decrypted_file_path = os.path.join(temp_dir, decrypted_filename)

                                    decrypt_file(encrypted_file_path, decrypted_file_path, secret)
                                    logging.debug(f"Вложение успешно дешифровано: {decrypted_file_path}")
                                    decrypted_attachments.append((filename, decrypted_file_path))

                                    os.remove(encrypted_file_path)
                                    logging.debug(f"Зашифрованный файл удалён: {encrypted_file_path}")
                                except Exception as e:
                                    logging.error(f"Ошибка при дешифровании вложения {filename}: {e}")
                                    self.showMessage(f"Ошибка при дешифровании вложения {filename}: {e}")
                        else:
                            logging.info("Вложения отсутствуют для дешифрования.")

                        logging.info("Обновление интерфейса с расшифрованными данными.")
                        self.ui.te_content.setPlainText(decrypted_text)
                        self.ui.attachments_list.clear()

                        for filename, decrypted_file_path in decrypted_attachments:
                            self.attached_files.append(decrypted_file_path)
                            list_item = QtWidgets.QListWidgetItem(os.path.basename(decrypted_file_path))
                            self.ui.attachments_list.addItem(list_item)
                            logging.debug(f"Вложение добавлено в интерфейс: {decrypted_file_path}")

                        self.showMessage("Дешифрование завершено успешно.")
                        logging.info("Процесс дешифрования завершён успешно.")
                    except Exception as e:
                        logging.exception("Не удалось дешифровать тело письма или вложения.")
                        self.showMessage(f"Ошибка при дешифровании письма: {e}")
                    return  

            # Если запись для указанного email не найдена
            logging.warning(f"Запись для email {recivier_email} не найдена в файле {jsn_path}.")
            self.showMessage(f"Запись для email {recivier_email} не найдена.")
        except FileNotFoundError:
            logging.exception(f"Файл не найден: {jsn_path}")
            self.showMessage(f"Файл не найден: {jsn_path}")
        except json.JSONDecodeError as e:
            logging.exception(f"Ошибка декодирования JSON: {e}")
            self.showMessage(f"Ошибка декодирования JSON: {e}")
        except Exception as e:
            logging.exception("Произошла непредвиденная ошибка при дешифровании письма.")
            self.showMessage(f"Произошла ошибка: {e}")


    def decrypt_email(self):

        sender_email = self.selected_mail.send_from
        receiver_email = self.selected_mail.send_to

        config_parser = ConfigParser()
        config_file_path = './MailClient-master/settings.ini'
        config_parser.read(config_file_path)
        user_email = config_parser.get("MAILSERVER", "mail")
        key_server = config_parser.get("MAILSERVER", "key_server")

        
        jsn_folder_path=f'./MailClient-master/local_secret/{user_email}'
        os.makedirs(jsn_folder_path, exist_ok=True)
        jsn_path=f'{jsn_folder_path}/contacts.json'
        
        if user_email==sender_email:
            print("сам себе")
            self.decrypt_self_mail(jsn_path,receiver_email)
            return
        
        else:
            try:
                ca_cert_path = './MailClient-master/CA/ca_certificate.crt'
                if not self.selected_mail:
                    self.showMessage("Пожалуйста, выберите письмо для дешифрования.")
                    return

                

                if not sender_email or not receiver_email:
                    self.showMessage("Не удалось получить адреса отправителя или получателя.")
                    return

                sender_hash = asimm_crypto.hash_text(sender_email)
                try:
                    # Получение сертификата с сервера
                    response = requests.get(f'{key_server}/get_user_cert', params={'email': sender_hash})
                    if response.status_code == 200:
                        sender_pub_cert = base64.b64decode(response.json().get("public_key_cert"))
                        print('Сертификат: ', sender_pub_cert)
                        print(type(sender_pub_cert))
                        if not sender_pub_cert:
                            raise Exception("Публичный ключ не найден в ответе сервера.")
                    else:
                        error_message = response.json().get("error", "Неизвестная ошибка при получении публичного ключа.")
                        raise Exception(f"Не удалось получить публичный ключ: {error_message}")
                except Exception as e:
                    print(f"Ошибка: {str(e)}")
                    self.showMessage(f"Ошибка при загрузке сертификата отправителя: {e}")
                    return

                try:
                    # Записываем сертификат во временный файл
                    cert_file = tempfile.NamedTemporaryFile(delete=False, suffix=".crt")
                    temp_cert_path = cert_file.name
                    with cert_file:
                        cert_file.write(sender_pub_cert)
                    print(f"Сертификат записан во временный файл: {temp_cert_path}")

                    # Извлекаем текстовую информацию о сертификате
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
                        "-CAfile", ca_cert_path,
                        temp_cert_path
                    ]
                    result_check = subprocess.run(check_cert_from_CA, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

                    if result_check.returncode == 0:
                        print(f"Certificate verified successfully: {result_check.stdout.strip()}")
                        # Ищем email-адрес в поле Subject или Subject Alternative Name
                        subject_email_found = False
                        san_email_found = False

                        lines = result.stdout.splitlines()
                        for line_index, line_text in enumerate(lines):
                            if "emailAddress=" in line_text:
                                # Проверяем email в Subject
                                if sender_email in line_text:
                                    subject_email_found = True
                            elif "Subject Alternative Name" in line_text:
                                # Проверяем email в SAN
                                # Может быть многострочным, поэтому смотрим несколько строк подряд
                                for subline in lines[line_index + 1 : line_index + 5]:
                                    if sender_email in subline:
                                        san_email_found = True
                                        break

                        if subject_email_found or san_email_found:
                            print("Email найден в сертификате.")  

                            # Извлекаем публичный ключ 
                            cert_command = [
                                'openssl', 'x509',
                                '-in', temp_cert_path,
                                '-pubkey', '-noout'
                            ]

                            try:
                                result_pubkey = subprocess.run(
                                    cert_command, 
                                    capture_output=True, 
                                    text=True, 
                                    check=True
                                )
                                public_key_data = result_pubkey.stdout
                                print("Публичный ключ успешно извлечён и сохранён в переменную")

                                # Парсим публичный ключ
                                sender_pub_key = asimm_crypto.parse_public_key_data(public_key_data)

                            except Exception as e:
                                print(f"Ошибка при извлечении/парсинге публичного ключа: {e}")
                                self.showMessage("Ошибка при извлечении публичного ключа")
                                return

                            finally:
                                # Удаляем временный файл
                                if os.path.exists(temp_cert_path):
                                    os.remove(temp_cert_path)

                        else:
                            print("Email не найден в сертификате.")
                            if os.path.exists(temp_cert_path):
                                os.remove(temp_cert_path)
                            self.showMessage("Публичный ключ не принадлежит отправителю")
                            return

                    else:
                        # Сертификат не прошел валидацию
                        if os.path.exists(temp_cert_path):
                            os.remove(temp_cert_path)
                        print(f"Verification failed: {result_check.stderr.strip()}")
                        self.showMessage("Публичный ключ не принадлежит отправителю")
                        return

                except Exception as e:
                    self.showMessage(f"Ошибка: {str(e)}")
                    return


                receiver_private_key_path = self.find_key()
                if not receiver_private_key_path:
                    self.showMessage("Не удалось найти приватный ключ.")
                    return

                try:
                    receiver_private_key = asimm_crypto.extract_private_key_openssl_text(receiver_private_key_path)
                except Exception as e:
                    self.showMessage(f"Ошибка при чтении приватного ключа: {e}")
                    return

                try:
                    shared_secret = asimm_crypto.gen_sym(receiver_private_key, sender_pub_key)
                except Exception as e:
                    self.showMessage(f"Ошибка при генерации общего секрета: {str(e)}")
                    return

                # Дешифрование тела письма
                decrypted_text = ""
                if self.body:
                    try:
                        encrypted_body = base64.b64decode(self.body)
                        decrypted_text = decrypt_message(encrypted_body, shared_secret)
                    except Exception as e:
                        self.showMessage(f"Ошибка при дешифровании тела письма: {e}")
                        return

                # Дешифрование вложений
                decrypted_attachments = []
                temp_dir = os.path.join(os.getcwd(), "temp")
                os.makedirs(temp_dir, exist_ok=True)

                if self.attachments:
                    for filename, encrypted_data in self.attachments:
                        try:
                            encrypted_file_path = os.path.join(temp_dir, filename)
                            with open(encrypted_file_path, 'wb') as f:
                                f.write(encrypted_data)

                            decrypted_filename = filename[:-4] if filename.endswith('.enc') else filename
                            decrypted_file_path = os.path.join(temp_dir, decrypted_filename)

                            decrypt_file(encrypted_file_path, decrypted_file_path, shared_secret)
                            decrypted_attachments.append((filename, decrypted_file_path))

                            os.remove(encrypted_file_path)
                        except Exception as e:
                            self.showMessage(f"Ошибка при дешифровании вложения {filename}: {str(e)}")

                # Обновляем интерфейс
                self.ui.te_content.setPlainText(decrypted_text)
                self.ui.attachments_list.clear()

                for filename, decrypted_file_path in decrypted_attachments:
                    self.attached_files.append(decrypted_file_path)
                    list_item = QtWidgets.QListWidgetItem(os.path.basename(decrypted_file_path))
                    self.ui.attachments_list.addItem(list_item)

                self.showMessage("Дешифрование завершено.")
            except Exception as e:
                self.showMessage(f"Ошибка при дешифровании письма: {e}")

        