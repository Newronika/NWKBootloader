from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5 import QtCore
from PyQt5.QtGui import QIcon
import os
import sys
from GUI_interface import Ui_bootloader

app = QApplication(sys.argv)
bootloader = Ui_bootloader()

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

with open(resource_path('custom_style.css'), 'r') as f:
    style = f.read()
    # Set the stylesheet of the application
    app.setStyleSheet(style)

interface = QWidget()
interface.setGeometry(700, 150, 500, 600)
interface.setWindowTitle("NWK Bootloader")
interface.setWindowIcon(QIcon(resource_path("icon.png")))
bootloader.setup(interface)
interface.show()

if __name__ == '__main__':

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        app.instance().exec_()

    sys.exit(0)
# See PyCharm help at https://www.jetbrains.com/help/pycharm/
