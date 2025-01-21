
from PyQt5 import QtCore, QtWidgets
from UiPy.UiSettings import Ui_Dialog

class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, config, parent=None):
        super(SettingsDialog, self).__init__(parent)
        self.config = config
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.MSWindowsFixedSizeDialogHint)

        # Инициализация полей значениями из конфигурации
        self.ui.le_imap_server.setText(self.config["imap_server"])
        self.ui.le_smtp_server.setText(self.config["smtp_server"])
        self.ui.sp_imap_port.setValue(self.config["imap_port"])
        self.ui.sp_smtp_port.setValue(self.config["smtp_port"])
        self.ui.cb_ssl.setChecked(self.config["ssl"])
        self.ui.CAserver.setText(self.config.settings.get("ca_server", ""))
        self.ui.keyServer.setText(self.config.settings.get("key_server", ""))

        # Привязка кнопок "ОК" и "Отмена" к методам
        self.ui.pb_ok.clicked.connect(self.saveSettings)
        self.ui.pb_cancel.clicked.connect(self.close)

    @QtCore.pyqtSlot()
    def saveSettings(self):

        try:
            # Считываем данные из полей ввода
            imap_server = self.ui.le_imap_server.text()
            smtp_server = self.ui.le_smtp_server.text()
            imap_port = str(self.ui.sp_imap_port.value())
            smtp_port = str(self.ui.sp_smtp_port.value())
            ssl = "Yes" if self.ui.cb_ssl.isChecked() else "No"
            ca_server = self.ui.CAserver.text()
            key_server = self.ui.keyServer.text()

            # Устанавливаем значения в конфигурацию
            self.config.set("imap_server", imap_server)
            self.config.set("smtp_server", smtp_server)
            self.config.set("imap_port", imap_port)
            self.config.set("smtp_port", smtp_port)
            self.config.set("ssl", ssl)
            self.config.set("ca_server", ca_server)
            self.config.set("key_server", key_server)

            # Сохраняем изменения в файл
            self.config.save()

            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Ошибка",
                f"Произошла ошибка при сохранении настроек: {e}",
                QtWidgets.QMessageBox.Ok
            )

    @QtCore.pyqtSlot()
    def close(self):
        self.reject()
