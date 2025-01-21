from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(691, 558)
        self.verticalLayout = QtWidgets.QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.gridLayout = QtWidgets.QGridLayout()
        self.gridLayout.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
        self.gridLayout.setObjectName("gridLayout")
        self.le_subject = QtWidgets.QLineEdit(Dialog)
        self.le_subject.setObjectName("le_subject")
        self.gridLayout.addWidget(self.le_subject, 2, 0, 1, 1)
        self.te_content = QtWidgets.QTextEdit(Dialog)
        self.te_content.setObjectName("te_content")
        self.gridLayout.addWidget(self.te_content, 4, 0, 1, 1)
        self.le_mail = QtWidgets.QLineEdit(Dialog)
        self.le_mail.setObjectName("le_mail")
        self.gridLayout.addWidget(self.le_mail, 1, 0, 1, 1)

        self.horizontalLayout_enc = QtWidgets.QHBoxLayout()
        self.horizontalLayout_enc.setObjectName("horizontalLayout_enc")
        self.enc_check = QtWidgets.QCheckBox(Dialog)
        self.enc_check.setObjectName("enc_check")
        self.horizontalLayout_enc.addWidget(self.enc_check)

        self.gridLayout.addLayout(self.horizontalLayout_enc, 3, 0, 1, 1)

        self.verticalLayout.addLayout(self.gridLayout)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setContentsMargins(0, -1, 0, 0)
        self.horizontalLayout.setSpacing(7)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.pushButton = QtWidgets.QPushButton(Dialog)
        self.pushButton.setObjectName("pushButton")
        self.horizontalLayout.addWidget(self.pushButton)
        self.attachments_list = QtWidgets.QListWidget(Dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Ignored)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.attachments_list.sizePolicy().hasHeightForWidth())
        self.attachments_list.setSizePolicy(sizePolicy)
        self.attachments_list.setObjectName("attachments_list")
        self.horizontalLayout.addWidget(self.attachments_list)
        spacerItem = QtWidgets.QSpacerItem(208, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.pb_send = QtWidgets.QPushButton(Dialog)
        self.pb_send.setObjectName("pb_send")
        self.horizontalLayout.addWidget(self.pb_send)
        self.verticalLayout.addLayout(self.horizontalLayout)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Новое письмо"))
        self.le_subject.setPlaceholderText(_translate("Dialog", "Тема письма"))
        self.le_mail.setPlaceholderText(_translate("Dialog", "Адрес электронной почты получателя"))
        self.enc_check.setText(_translate("Dialog", "Шифровать"))
        self.pushButton.setText(_translate("Dialog", "Файл.."))
        self.pb_send.setText(_translate("Dialog", "Отправить"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    Dialog = QtWidgets.QDialog()
    ui = Ui_Dialog()
    ui.setupUi(Dialog)
    Dialog.show()
    sys.exit(app.exec_())




