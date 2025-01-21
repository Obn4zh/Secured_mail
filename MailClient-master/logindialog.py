
from PyQt5 import QtCore, QtGui, QtWidgets
from UiPy.UiLogin import Ui_Dialog

from loadsettings import Settings
from settingsdialog import SettingsDialog
from Core.imapclient import *

class LoginDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(QtWidgets.QDialog, self).__init__(parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.MSWindowsFixedSizeDialogHint)
        self.isWork = 0
        self.config = Settings()
        self.config.load()
        self.settingsDlg = SettingsDialog(self.config)
        self.ui.le_mail.setText(self.config["mail"])
        self.ui.pb_settings.clicked.connect(self.showSettings)
        self.ui.pb_cancel.clicked.connect(self.closeMethod)
        self.ui.pb_ok.clicked.connect(self.acceptMethod)

        # Подключаем обработчики для фильтрации недопустимых символов
        self.ui.le_mail.textChanged.connect(self.validateEmailInput)
        self.ui.le_passwd.textChanged.connect(self.validatePasswordInput)

    @QtCore.pyqtSlot(str)
    def validateEmailInput(self, text):
        # Удаляем русские буквы из текста
        filtered_text = ''.join(char for char in text if not ('\u0400' <= char <= '\u04FF'))
        if text != filtered_text:
            cursor_position = self.ui.le_mail.cursorPosition()
            self.ui.le_mail.setText(filtered_text)
            self.ui.le_mail.setCursorPosition(cursor_position - (len(text) - len(filtered_text)))

    @QtCore.pyqtSlot(str)
    def validatePasswordInput(self, text):
        # Удаляем русские буквы из текста
        filtered_text = ''.join(char for char in text if not ('\u0400' <= char <= '\u04FF'))
        if text != filtered_text:
            cursor_position = self.ui.le_passwd.cursorPosition()
            self.ui.le_passwd.setText(filtered_text)
            self.ui.le_passwd.setCursorPosition(cursor_position - (len(text) - len(filtered_text)))

    @QtCore.pyqtSlot()
    def acceptMethod(self):
        email = self.ui.le_mail.text()
        password = self.ui.le_passwd.text()

        # Проверяем email на недопустимые символы
        if not self.isEmailValid(email):
            QtWidgets.QMessageBox.warning(
                self,
                "Ошибка",
                "Email содержит недопустимые символы. Используйте только латинские буквы, цифры и символы @, ., _, -.",
                QtWidgets.QMessageBox.Ok
            )
            return

        # Проверяем пароль на недопустимые символы
        if not self.isPasswordValid(password):
            QtWidgets.QMessageBox.warning(
                self,
                "Ошибка",
                "Пароль содержит недопустимые символы. Используйте только латинские буквы, цифры и символы.",
                QtWidgets.QMessageBox.Ok
            )
            return

        self.settingsDlg.config.set("mail", email)
        self.settingsDlg.config.save()

        self.config["smtp_user"] = email  
        self.config.load()
        self.config["pwd"] = password 

        # Логинимся через IMAP
        self.imap = IMAPClient(
        hostname=self.config["imap_server"],
        port=self.config["imap_port"],
        use_ssl=self.config["ssl"]  
        )

        try:
            if self.imap.login(email, password):
                self.isWork = 1
            else:
                self.isWork = 2
                QtWidgets.QMessageBox.warning(
                    self,
                    "Ошибка",
                    "Некорректная аутентификация",
                    QtWidgets.QMessageBox.Ok
                )
        except UnicodeEncodeError:
            QtWidgets.QMessageBox.critical(
                self,
                "Ошибка",
                "Email или пароль содержат недопустимые символы. Проверьте введенные данные.",
                QtWidgets.QMessageBox.Ok
            )
        self.accept()

    @QtCore.pyqtSlot()
    def showDialog(self):
        self.exec_()
        return self.isWork

    def isEmailValid(self, email):
        # Проверяем, содержит ли email только латинские символы, цифры и допустимые спецсимволы
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def isPasswordValid(self, password):
        # Проверяем, что пароль не содержит русских букв
        return not any('\u0400' <= char <= '\u04FF' for char in password)

    @QtCore.pyqtSlot()
    def closeMethod(self):
        self.isWork = 0
        self.close()

    @QtCore.pyqtSlot()
    def showSettings(self):
        self.settingsDlg.exec_()

    @property
    def connection(self):
        pass

    @connection.getter
    def connection(self):
        return self.imap

    @property
    def configure(self):
        pass

    @configure.getter
    def configure(self):
        return self.config
