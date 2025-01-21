import sys
from PyQt5.QtCore    import QUrl
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView


class MainWindow(QMainWindow):
    def __init__(self ):
        super(QMainWindow, self).__init__()
        self.setWindowTitle('Vitus total')

        self.browser = QWebEngineView()  


        url = 'https://www.virustotal.com/gui/home/upload'
        self.browser.load(QUrl( url ))  
        self.setCentralWidget(self.browser)

if __name__ == '__main__':
    app = QApplication(sys.argv)       
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())