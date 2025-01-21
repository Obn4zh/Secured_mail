# imapclient.py

import ssl
import traceback
from imap_tools import MailBox, AND

class IMAPClient:

    def __init__(self, hostname, port=None, use_ssl=False):
        """
        :param hostname: Адрес сервера (напр. 'imap.mail.ru' или 'imap.yandex.ru')
        :param port: Порт (int). Если None, берём 993 при ssl=True, 143 иначе.
        :param ssl: Логический флаг — использовать ли SSL.
                    В imap-tools вместо ssl=True нужно ssl_context=...
        """
        self.hostname = hostname
        self.use_ssl = use_ssl  
        self.port = port

        # Если порт не задан — выбираем дефолтный
        if self.use_ssl and not self.port:
            self.port = 993
        elif not self.use_ssl and not self.port:
            self.port = 143

        # Создаём SSL-контекст, если нужно
        if self.use_ssl:
            self.ssl_context = ssl.create_default_context()
        else:
            self.ssl_context = None

        # Создаём MailBox
        self.mailbox = MailBox(self.hostname, port=self.port, ssl_context=self.ssl_context)

    def login(self, username, password):
        """
        Логинимся через MailBox. Возвращаем True, если успех
        """
        try:
            self.mailbox.login(username, password)
            return True
        except Exception as e:
            print("IMAP login error:", e)
            traceback.print_exc()
            return False

    def logout(self):
        """
        Завершение работы с сервером (MailBox)
        """
        self.mailbox.logout()

    def select_folder(self, folder_name):
        """
        Устанавливаем текущую папку
        """
        try:
            self.mailbox.folder.set(folder_name)
            return True
        except Exception as e:
            print("Не удалось выбрать папку:", folder_name, e)
            return False
        
    def find_sent_folder_any(self):
        """
        Сначала пытается найти папку, у которой есть флаг '\\Sent'.
        Если не находит, перебирает список известных названий ('Sent', 'Отправленные', ...).
        Возвращает имя папки (str) или None, если ничего не нашлось
        """
        folder_list = self.mailbox.folder.list()  

        # 1) Смотрим флаг \Sent
        for folder_info in folder_list:
            # У folder_info.flags обычно тип ( '\\HasNoChildren', '\\Unmarked', '\\Sent' ) и т.п.
            if '\\Sent' in folder_info.flags:
                return folder_info.name

        # 2) Если не нашли — перебираем названия
        candidates = ["Sent", "Отправленные", "Sent Messages", "INBOX.Sent"]
        folder_names = [f.name for f in folder_list]
        for candidate in candidates:
            if candidate in folder_names:
                return candidate

        return None  # не нашли ничего подходящего


    def list_folders(self):
        """
        Возвращаем список папок в формате [(flags, delim, name), ...]
        чтобы было похоже на старый imapclient.list_folders()
        """
        folder_list = []
        for f in self.mailbox.folder.list():
            # f — это объект FolderInfo(name='INBOX', delim='.', flags='...')
            folder_list.append((f.flags, f.delim, f.name))
        return folder_list

    def count(self, unread=False):
        """
        Считает письма в текущей папке
        :param unread: если True, считаем только непрочитанные
        """
        if unread:
            msgs = self.mailbox.fetch(AND(seen=False))
        else:
            msgs = self.mailbox.fetch()
        return sum(1 for _ in msgs)

    def headers(self, unread=False, folder=None):
        """
        Возвращаем список (uid, header_dict) для писем в указанной (или текущей) папке
        header_dict: {
            "sent_from": [{"email": ...}],
            "sent_to":   [{"email": ...}],
            "subject":   ...,
            "date":      ...
        }
        """
        if folder is not None:
            ok = self.select_folder(folder)
            if not ok:
                return []

        if unread:
            msgs = self.mailbox.fetch(AND(seen=False), headers_only=True)
        else:
            msgs = self.mailbox.fetch(headers_only=True)

        results = []
        for msg in msgs:
            header_info = {
                "sent_from": [{"email": msg.from_}],
                "sent_to":   [{"email": (msg.to[0] if msg.to else None)}],
                "subject":   msg.subject,
                "date":      msg.date_str
            }
            results.append((msg.uid, header_info))
        return results

    def fetch_body_and_attachments_by_uid(self, uid):
        """
        Возвращает (body, attachments) для письма с данным UID (в текущей папке)
        attachments = [(filename, binary_data), ...]
        """

        msgs = list(self.mailbox.fetch(AND(uid=uid)))
        if not msgs:
            return "", []

        msg = msgs[0]
        body = msg.text or msg.html or ""
        attachments = []
        for att in msg.attachments:
            attachments.append((att.filename, att.payload))

        return body, attachments

    def mark_seen(self, uid):
        """
        Ставим флаг \\Seen (прочитано) для письма с данным UID
        """
        try:
            self.mailbox.flag([uid], MailBox.FLAG_SEEN, True)
            return True
        except Exception as e:
            print("Ошибка mark_seen:", e)
            return False


    def copy(self, uid, destination_folder):
        """
        Копируем письмо в другую папку.
        """
        try:
            self.mailbox.copy([uid], destination_folder)
            return True
        except Exception as e:
            print("Ошибка copy:", e)
            return False

    def move(self, uid, destination_folder):
        """
        Перемещаем письмо в другую папку.
        """
        try:
            self.mailbox.move([uid], destination_folder)
            return True
        except Exception as e:
            print("Ошибка move:", e)
            return False
