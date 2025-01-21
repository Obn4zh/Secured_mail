
from PyQt5 import QtCore, QtGui
from standarditem import StandardItem
from configparser import ConfigParser

class TreeModel(QtGui.QStandardItemModel):
    def __init__(self, parent = None):
        super(QtGui.QStandardItemModel, self).__init__(parent)
        self.initialize()

    def initialize(self):
        self.setHorizontalHeaderLabels([f"{self.UserNameParse()}"])
        self.horizontalHeaderItem(0).setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignHCenter)
        self.setup()

    def UserNameParse(self):
        config_parser = ConfigParser()
        config_file_path = './MailClient-master/settings.ini'
        config_parser.read(config_file_path)
        user_email = config_parser.get("MAILSERVER", "mail")
        return user_email


    def setup(self):
        root = self.invisibleRootItem()
        item0 = self.createItem(root,  r"./MailClient-master/img/mail.png", "Письма", "root")
        # item1 = self.createItem(item0, r".\img\unread.png", "Не прочитанные" , "unread")
        item2 = self.createItem(item0, r"./MailClient-master/img/all.png", "Входящие", "all")
        item3 = self.createItem(item0, r"./MailClient-master/img/sended.png", "Отправленные", "sent")

        item3.setData("sent", QtCore.Qt.UserRole)

    def createItem(self, root, path, text, arg = str()):
        item = StandardItem(QtGui.QIcon(path), text, arg)
        root.appendRow(item)
        return item

    def dataForIndex(self, index):
        item = self.itemFromIndex(index)
        return item.value