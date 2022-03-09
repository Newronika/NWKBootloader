import time

import serial.serialutil
from PyQt5.QtWidgets import QGridLayout, QPushButton, QComboBox, QMessageBox, QLineEdit, QFileDialog, QProgressBar, \
    QLabel
from PyQt5.QtWidgets import QGroupBox, QHBoxLayout, QFrame, QCheckBox
from PyQt5 import QtCore
from PyQt5.QtCore import QThread, pyqtSignal, QObject
from PyQt5.QtGui import QPixmap, QIcon
from serial.tools import list_ports
from comm_UART import UART_functions
import numpy as np
import sys
import os
import hashlib
import threading


class QHLine(QFrame):
    def __init__(self):
        super(QHLine, self).__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)


class ProgressBar_class:
    def __init__(self, text):
        self.progress_group = QGroupBox()
        prog_layout = QHBoxLayout()
        self.progress_text = QLineEdit(text)
        self.progressBar = QProgressBar()
        self.resultLine = QLineEdit()
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(100)
        self.progressBar.setRange(0, 100)
        self.progressBar.setFixedSize(300, 30)
        prog_layout.addWidget(self.progress_text)
        prog_layout.addWidget(self.progressBar)
        prog_layout.addWidget(self.resultLine)
        self.progress_group.setLayout(prog_layout)
        self.hide()

    def init(self):
        self.progressBar.setValue(0)
        self.resultLine.setText("")
        self.hide()

    def set_perc(self, perc):
        self.progressBar.setValue(perc)

    def visible(self):
        self.progressBar.setVisible(True)
        self.progress_text.setVisible(True)
        self.resultLine.setVisible(False)

    def hide(self):
        self.progressBar.setVisible(False)
        self.progress_text.setVisible(False)
        self.resultLine.setVisible(False)

    def result(self, result):
        self.progressBar.setVisible(False)
        self.resultLine.setVisible(True)
        self.resultLine.setText(result)


class signals(QObject):
    percentage_signal = pyqtSignal(int)
    finished = pyqtSignal()
    complete = pyqtSignal()


class Thread_long_operation(QThread):
    def __init__(self):
        QThread.__init__(self)
        self.sig = signals()

    def define_options(self, com):
        self.com = com

    def __del__(self):
        self.wait()

    def run(self):
        # wait to receive completion percentage
        self.com.percentage = 0
        self.com.error = False
        self.com.completed = False
        while not self.com.completed and not self.com.error:
            self.com.get_progression_status()
            # print(self.com.percentage)
            # update progression status
            self.sig.percentage_signal.emit(self.com.percentage)
        if self.com.completed:
            # print("Completed")
            self.sig.percentage_signal.emit(100)
            dc = 1
        else:
            # print("Error")
            dc = 1

        # send ack/nack
        data = np.zeros(self.com.LEN_DATA)
        payload = np.zeros(self.com.LEN_PAYLOAD)
        cnt = self.com.cnt_id

        # send command through UART
        self.msg_to_send = self.com.msgTX(self.com.opErrorCommand, data, payload, cnt, dc)
        self.com.send_command(self.msg_to_send)
        # print("sent")
        self.sig.finished.emit()


class Thread_writing(QThread):
    def __init__(self):
        QThread.__init__(self)
        self.sig = signals()

    def define_options(self, mcu, file, length_file, com):
        self.mcu = mcu
        self.len_file = length_file
        self.file = file
        self.com = com

    def __del__(self):
        self.wait()

    def writeFirmware(self, buffer, data):
        # data[0] = 52
        payload = buffer
        # payload = np.arange(52)
        cnt = 0x00
        self.msg_to_send = self.com.msgTX(self.com.writeFRAMCommand, data, payload, cnt, 0x00)
        # send message and wait for ack/nack
        result = self.com.send_msg_wait_4_ack(self.msg_to_send)
        return result

    def run(self):
        data = np.zeros(self.com.LEN_DATA)
        self.address = 0
        # print("Start writing" + str(self.len_file))
        cnt = 0
        # send 52 bytes at time (wait everytime for the ACK)
        value_old = -1
        for i in range(0, self.len_file, self.com.LEN_PAYLOAD):
            # print(i)
            if (i + self.com.LEN_PAYLOAD) > self.len_file:
                buffer = bytearray(self.com.LEN_PAYLOAD)
                buffer[0: (self.len_file - i)] = self.file[i: self.len_file]
                data[0] = self.len_file - i

            else:
                data[0] = self.com.LEN_PAYLOAD
                buffer = self.file[i: i + self.com.LEN_PAYLOAD]

            add = self.address.to_bytes(3, 'big')
            data[1] = add[0]
            data[2] = add[1]
            data[3] = add[2]
            # (data)
            sent = self.writeFirmware(buffer, data)
            self.address = self.address + self.com.LEN_PAYLOAD
            value = int(((i + 52) * 100) / self.len_file)

            self.sig.percentage_signal.emit(value)
            # if buffer sending fails
            if sent == False:
                break

        if sent == False:
            self.sent_final = False
            # self.progWriting.result("Invalid Operation!")

            # if ACK
        elif sent == True:
            self.sent_final = True
            # self.progWriting.result("Completed")
        self.sig.finished.emit()


class Ui_bootloader(object):
    def setup(self, MainWindow):
        grid = QGridLayout()
        ## widgets ###
        # buttons
        self.deviceButton = QPushButton("COM")
        self.comBox = QComboBox()
        self.bootVersionButton = QPushButton("Boot Version")
        self.appVersionButton = QPushButton("App Version")
        self.writeL1Button = QPushButton("Write L1")
        self.eraseL1Button = QPushButton("Erase L1 flash")
        self.programL1Button = QPushButton("Program L1 flash")
        self.FlashL1Button = QPushButton("Program L1")
        self.writeL4Button = QPushButton("Write L4")
        self.eraseL4Button = QPushButton("Erase L4 flash")
        self.programL4Button = QPushButton("Program L4 flash")
        self.FlashL4Button = QPushButton("Program L4")
        self.runAppButton = QPushButton("Jump to App")
        # line edit
        self.versionLine = QLineEdit()
        self.appVersionLine = QLineEdit()
        # progress bar
        self.progWriting = ProgressBar_class("Writing FRAM: ")
        self.progErasing = ProgressBar_class("Erasing Flash: ")
        self.progProgramming = ProgressBar_class("Programming Flash: ")
        # message
        self.msg_to_display = QMessageBox()
        self.msg_to_display.setWindowTitle("Warning")
        # text
        self.text = QLabel("")
        self.text.setVisible(False)
        # check box
        self.hashL1Check = QCheckBox("Wrong Hash L1")
        self.hashL4Check = QCheckBox("Wrong Hash L4")
        # button list
        self.button_list = [self.bootVersionButton, self.appVersionButton,
                            self.writeL1Button, self.writeL4Button, self.programL1Button, self.eraseL1Button,
                            self.programL4Button,
                            self.eraseL4Button, self.runAppButton, self.FlashL1Button, self.FlashL4Button]
        self.progressBarList = [self.progWriting, self.progErasing, self.progProgramming]
        ## layout ##
        # title
        sub_title = QGroupBox()
        lay_title = QHBoxLayout()
        icon = QLabel()
        icon.setAlignment(QtCore.Qt.AlignLeft)
        # icon.setGeometry(QtCore.QRect(0, 0, 51, 51))
        icon.setPixmap(QPixmap(self.resource_path("newronika.png")))
        lay_title.addWidget(icon)
        # lay_title.addWidget(QLabel(""))
        label = QLabel("NWK Bootloader")
        label.setStyleSheet("font-weight:bold;""font-size:17pt;""color:rgb(43,43,43)")
        label.setIndent(QtCore.Qt.AlignLeft)
        label.setAlignment(QtCore.Qt.AlignLeft)
        lay_title.addWidget(label)
        lay_title.addWidget(QLabel(""))
        sub_title.setLayout(lay_title)
        button_group = QGroupBox()
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.FlashL1Button)
        button_layout.addWidget(self.FlashL4Button)
        button_group.setLayout(button_layout)
        ### positioning widgets ###
        grid.addWidget(sub_title, 0, 0, 1, -1)
        grid.addWidget(self.deviceButton, 1, 0)
        grid.addWidget(self.comBox, 1, 1)
        grid.addWidget(self.bootVersionButton, 2, 0)
        grid.addWidget(self.versionLine, 2, 1)
        grid.addWidget(self.appVersionButton, 3, 0)
        grid.addWidget(self.appVersionLine, 3, 1)
        #grid.addWidget(self.hashL1Check, 4, 0)
        #grid.addWidget(self.hashL4Check, 4, 1)
        #grid.addWidget(self.writeL1Button, 5, 0)
        #grid.addWidget(self.writeL4Button, 5, 1)
        #grid.addWidget(self.eraseL1Button, 6, 0)
        #grid.addWidget(self.eraseL4Button, 6, 1)
        #grid.addWidget(self.programL1Button, 7, 0)
        #grid.addWidget(self.programL4Button, 7, 1)
        grid.addWidget(self.FlashL1Button, 8, 0)
        grid.addWidget(self.FlashL4Button, 8, 1)
        grid.addWidget(self.runAppButton, 9, 0, 1, -1)
        grid.addWidget(QHLine(), 10, 0, 1, -1)
        grid.addWidget(self.text, 11, 0, 1, -1)
        grid.addWidget(self.progWriting.progress_group, 12, 0, 1, -1)
        grid.addWidget(self.progErasing.progress_group, 13, 0, 1, -1)
        grid.addWidget(self.progProgramming.progress_group, 14, 0, 1, -1)

        # initial condition: all buttons are disabled
        for elem in self.button_list:
            elem.setEnabled(False)
        self.FlashL1Button.setStyleSheet(
            "background-color: lightgray;""width: 100px;""height:90px;""font-weight: bold;""color:darkgrey;")
        self.FlashL4Button.setStyleSheet(
            "background-color: lightgray;""width: 100px;""height:90px;""font-weight: bold;""color:darkgrey;")

        ##variables##
        self.process = None
        self.all_process = False
        ##commands to send##
        self.com = UART_functions()
        self.thread_writing = Thread_writing()
        self.thread_erasing = Thread_long_operation()
        self.thread_programming = Thread_long_operation()
        MainWindow.setLayout(grid)
        self.retranslateUi()

    def retranslateUi(self):
        self.deviceButton.clicked.connect(self.displayPorts)
        self.comBox.currentIndexChanged.connect(self.selectCOM)
        self.bootVersionButton.clicked.connect(self.getBootVersion)
        self.appVersionButton.clicked.connect(self.getAppVersion)
        self.writeL1Button.clicked.connect(lambda: self.writeFRAM(1))
        self.eraseL1Button.clicked.connect(lambda: self.eraseFlash(1))
        self.programL1Button.clicked.connect(lambda: self.programFlash(1))
        self.FlashL1Button.clicked.connect(lambda: self.programMCU(1))
        self.writeL4Button.clicked.connect(lambda: self.writeFRAM(4))
        self.eraseL4Button.clicked.connect(lambda: self.eraseFlash(4))
        self.programL4Button.clicked.connect(lambda: self.programFlash(4))
        self.FlashL4Button.clicked.connect(lambda: self.programMCU(4))
        self.runAppButton.clicked.connect(self.runApp)
        self.thread_writing.sig.percentage_signal.connect(self.update_bar)
        self.thread_writing.sig.finished.connect(self.end_of_process)
        self.thread_erasing.sig.percentage_signal.connect(self.update_bar)
        self.thread_erasing.sig.finished.connect(self.end_of_process)
        self.thread_programming.sig.percentage_signal.connect(self.update_bar)
        self.thread_programming.sig.finished.connect(self.end_of_process)
        self.thread_writing.sig.complete.connect(self.switch_operation)
        self.thread_erasing.sig.complete.connect(self.switch_operation)

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    def writeFRAM(self, mcu):
        self.process = 0
        uploaded = False
        prepared = False
        self.address = 0
        data = np.zeros(self.com.LEN_DATA)
        self.msg_old = []
        # import .bin file to be write on the FRAM
        uploaded = self.openBinFile()
        # if file is uploaded
        if uploaded:
            # prepare the FRAM to write on L1
            prepared = self.prepareFRAM(mcu)
            # send firmware
            if prepared:
                self.progWriting.visible()
                self.thread_writing.define_options(mcu, self.firmwareFile, self.len_firmware, self.com)
                self.thread_writing.start()
            else:
                uploaded = False
                text = self.decode_message()
                self.msg_to_display.setText(text)
                self.msg_to_display.exec()

    def eraseFlash(self, mcu):
        self.process = 1
        if mcu == 1:
            cmd = self.com.EraseL1Command
        elif mcu == 4:
            cmd = self.com.EraseL4Command
        # check for data
        data = np.zeros(self.com.LEN_DATA)
        payload = np.zeros(self.com.LEN_PAYLOAD)
        cnt = 0x00
        if self.all_process == False:
            self.progErasing.visible()
        # send command through UART
        self.msg_to_send = self.com.msgTX(cmd, data, payload, cnt, 0x00)
        # send message and wait for ack/nack
        result = self.com.send_msg_wait_4_ack(self.msg_to_send)
        # print("result: " + str(result))
        # if NACK
        if result == False:
            text = self.decode_message()
            self.progErasing.result(text)
            # self.msg_to_display.setText(text)
            # self.msg_to_display.exec()
        # if ACK
        elif result == True:
            # print("erasing")
            self.thread_erasing.define_options(self.com)
            self.thread_erasing.start()

    def programFlash(self, mcu):
        self.process = 2
        if mcu == 1:
            cmd = self.com.programL1Command
        elif mcu == 4:
            cmd = self.com.programL4Command
        # check for data
        data = np.zeros(self.com.LEN_DATA)
        payload = np.zeros(self.com.LEN_PAYLOAD)
        cnt = 0x00
        # send command through UART
        self.msg_to_send = self.com.msgTX(cmd, data, payload, cnt, 0x00)
        # send message and wait for ack/nack
        result = self.com.send_msg_wait_4_ack(self.msg_to_send)
        if self.all_process == False:
            self.progProgramming.visible()
        # if NACK
        if result == False:
            text = self.decode_message()
            self.progProgramming.result(text)
        # if ACK
        elif result == True:
            # print("Programming")
            self.thread_programming.define_options(self.com)
            self.thread_programming.start()

    def programMCU(self, mcu):
        self.text.setText("Programming L" + str(mcu) + str("..."))
        self.text.setVisible(True)
        for elem in self.progressBarList:
            elem.init()
        self.all_process = False
        self.all_process = mcu
        self.writeFRAM(mcu)

    def end_of_process(self):
        if self.process == 0:
            if self.thread_writing.sent_final == True:
                # print("Ok")
                self.progWriting.result("Completed")
                # self.thread_writing.__del__()
                if self.all_process:
                    self.thread_writing.sig.complete.emit()
            else:
                text = self.decode_message()
                self.progWriting.result(text)
                # self.thread_writing.__del__()

        elif self.process == 1:
            if self.thread_erasing.com.completed:
                # print("Ok")
                self.progErasing.result("Completed")
                # self.thread_erasing.__del__()
                if self.all_process:
                    self.thread_erasing.sig.complete.emit()
            else:
                self.progErasing.result("Invalid Operation!")
                # self.thread_erasing.__del__()

        elif self.process == 2:
            if self.thread_programming.com.completed:
                # print("Ok")
                self.progProgramming.result("Completed")
                # self.thread_programming.__del__()
                if self.all_process:
                    self.msg_to_display.setText("L" + str(self.all_process) + " programmed successfully!")
                    self.msg_to_display.exec()
                else:
                    self.msg_to_display.setText("Flash programmed successfully!")
                    self.msg_to_display.exec()

            else:
                self.progProgramming.result("Invalid Operation!")
                # self.thread_programming.__del__()
                if self.all_process:
                    self.msg_to_display.setText("L" + str(self.all_process) + " not programmed!")
                    self.msg_to_display.exec()
                else:
                    self.msg_to_display.setText("Flash not programmed")
                    self.msg_to_display.exec()

            for elem in self.progressBarList:
                elem.init()
            self.all_process = False
            self.text.setText("")
            self.text.setVisible(False)
            self.thread_writing.__del__()
            self.thread_erasing.__del__()
            self.thread_programming.__del__()

    def switch_operation(self):
        # print("process " + str(self.process))
        if self.process == 0:
            time.sleep(2)
            self.progErasing.visible()
            self.eraseFlash(self.all_process)
        elif self.process == 1:
            time.sleep(2)
            self.progProgramming.visible()
            self.programFlash(self.all_process)

    def update_bar(self, value):
        if self.process == 0:
            self.progWriting.set_perc(value)
        elif self.process == 1:
            self.progErasing.set_perc(value)
        elif self.process == 2:
            self.progProgramming.set_perc(value)

    def displayPorts(self):
        self.added_device = 0
        self.comBox.clear()
        PList = list_ports.comports(include_links=True)

        for i in range(0, len(PList)):
            self.comBox.addItem(PList[i].device)


        if len(PList) == 0:
            self.msg_to_display.setText("Device cannot be found!\nConnect the NWKStation.")
            self.msg_to_display.exec()
        else:
            self.added_device = 1
            self.selectCOM()

    def selectCOM(self):
        if self.com.open:
            self.com.NWK_SerialCon.close()
        # print("com")
        if self.added_device:
            # self.comBox.currentIndex()
            try:
                self.COMport = self.comBox.currentText()
                self.com.open_comm(self.COMport)
                self.connectIPG()
                ''' 
                for elem in self.button_list:
                    elem.setEnabled(True)
                    self.FlashL1Button.setStyleSheet(
                        "QPushButton{background-color: rgb(231,73,31);""width: 90px;""height:80px;""font-weight: bold;""color:white;}"
                        " QPushButton:hover{background-color: rgb(219,60,21)}")
                    self.FlashL4Button.setStyleSheet(
                                "QPushButton{background-color: rgb(231,73,31);""width: 90px;""height:80px;""font-weight: bold;""color:white;}"
                        " QPushButton:hover{background-color: rgb(219,60,21)}")
'''
            except BaseException:
                for elem in self.button_list:
                    elem.setEnabled(False)
                self.FlashL1Button.setStyleSheet(
                    "background-color: lightgray;""width: 100px;""height:90px;""font-weight: bold;""color:darkgrey;")
                self.FlashL4Button.setStyleSheet(
                    "background-color: lightgray;""width: 100px;""height:90px;""font-weight: bold;""color:darkgrey;")

    def connectIPG(self):
        data = np.zeros(self.com.LEN_DATA)
        payload = np.zeros(self.com.LEN_PAYLOAD)
        cnt = 0x00
        # send command through UART
        self.msg_to_send = self.com.msgTX(self.com.bootVersionCommand, data, payload, cnt, 0x00)
        start = time.time()
        end = time.time()
        answer = False
        # for 3 mins send boot version command: when an answer is received enable all the buttons, otherwise error msg
        while int(end - start) < 10 * 60 and not answer:
            answer = self.com.send_msg_wait_4_ack(self.msg_to_send)
            end = time.time()
            print(answer)
        if answer == self.com.counter_SERIAL_TIMEOUT_NACK:
            answer = False
        if answer:
            for elem in self.button_list:
                elem.setEnabled(True)
                self.FlashL1Button.setStyleSheet(
                    "background-color: rgb(231,73,31);""width: 90px;""height:80px;""font-weight: bold;""color:white;")
                self.FlashL4Button.setStyleSheet(
                    "background-color: rgb(231,73,31);""width: 90px;""height:80px;""font-weight: bold;""color:white;")
        else:
            self.msg_to_display.setText("Connection to the IPG was not successful!")
            self.msg_to_display.exec()

    def getBootVersion(self):
        self.versionLine.setText("")
        data = np.zeros(self.com.LEN_DATA)
        payload = np.zeros(self.com.LEN_PAYLOAD)
        cnt = 0x00
        # send command through UART
        self.msg_to_send = self.com.msgTX(self.com.bootVersionCommand, data, payload, cnt, 0x00)
        # send message and wait for ack/nack
        self.versionLine.setStyleSheet("font-weight:bold;")
        result = self.com.send_msg_wait_4_ack(self.msg_to_send)
        # if NACK
        if result == False:
            text = self.decode_message()
            self.versionLine.setText(text)
        else:
            self.versionLine.setText(str(result))

    def getAppVersion(self):
        self.appVersionLine.setText("")
        data = np.zeros(self.com.LEN_DATA)
        payload = np.zeros(self.com.LEN_PAYLOAD)
        cnt = 0x00
        # send command through UART
        self.msg_to_send = self.com.msgTX(self.com.appVersionCommand, data, payload, cnt, 0x00)
        # send message and wait for ack/nack
        result = self.com.send_msg_wait_4_ack(self.msg_to_send)
        # if NACK
        self.appVersionLine.setStyleSheet("font-weight:bold;")
        if result == False:
            text = self.decode_message()
            self.appVersionLine.setText(text)
        # if ACK
        else:
            self.appVersionLine.setText(result)

    def runApp(self):
        data = np.zeros(self.com.LEN_DATA)
        payload = np.zeros(self.com.LEN_PAYLOAD)
        cnt = 0x00
        # send command through UART
        self.msg_to_send = self.com.msgTX(self.com.runAppCommand, data, payload, cnt, 0x00)
        # send message and wait for ack/nack
        result = self.com.send_msg_wait_4_ack(self.msg_to_send)
        # if NACK
        if result == False:
            text = self.decode_message()
            self.msg_to_display.setText(text)
        # if ACK
        else:
            self.msg_to_display.setText("Jumped to app!")
        self.msg_to_display.exec()

    def openBinFile(self):
        fname = QFileDialog.getOpenFileName()
        path = fname[0]
        # delete all rows containing an error
        raw = []
        if len(path) == 0:
            self.msg_to_display.setText("No file selected!\n", )
            self.msg_to_display.exec()
            return False
        elif not path.endswith(".bin"):
            self.msg_to_display.setText("File selected does not have the correct format!\n Please select a .txt file.")
            self.msg_to_display.exec()
            return False
        else:
            with open(path, "rb") as f:
                #self.firmwareFile = bytearray()
                # Do stuff with byte.
                #self.firmwareFile = bytearray(f.read(1000))
                self.firmwareFile = bytearray(f.read())
                self.firmwareFile[4096] = 62
                self.firmwareFile[4097] = 0
                self.firmwareFile[4098] = 1
                self.firmwareFile[4099] = 21
                self.firmwareFile[4100] = 0
                self.firmwareFile[4101] = 0

            # concatenate hash value
            if self.hashL1Check.isChecked() or self.hashL4Check.isChecked():
                l_hash = []
                for i in range(16):
                    l_hash.append(i)
                hash_msg = bytearray(l_hash)
            else:
                hash_msg = self.hashDecode(self.firmwareFile)
            # for elem in hash_msg:
            # print(hex(elem))
            self.firmwareFile = self.firmwareFile + hash_msg
            # print("len" + str(len(self.firmwareFile)))
            # print(self.firmwareFile)
            return True

    def hashDecode(self, file):
        h = hashlib.md5()
        if len(file) % 64 != 0:
            res = (int(np.ceil(len(file) / 64))) * 64 - len(file)
            hash_file = file + bytearray(res)
        h.update(hash_file)
        hash = h.digest()
        # print(hash)
        hash = bytearray(hash)
        return hash

    def prepareFRAM(self, mcu):
        self.len_firmware = len(self.firmwareFile)
        # self.len_firmware = 1000
        data = self.len_firmware.to_bytes(self.com.LEN_DATA, 'little')
        payload = np.zeros(self.com.LEN_PAYLOAD)
        cnt = 0x00
        self.msg_to_send = self.com.msgTX(self.com.prepareFRAMCommand, data, payload, cnt, mcu)
        # send message and wait for ack/nack
        result = self.com.send_msg_wait_4_ack(self.msg_to_send)
        # if NACK
        return result

    def decode_message(self):
        # print("res" + str(self.com.result_communication))
        if self.com.result_communication == self.com.IPG_NACK:
            text = "IPG NACK"
        elif self.com.result_communication == self.com.IPG_CRC_NACK:
            text = "IPG CRC NACK"
        elif self.com.result_communication == self.com.IPG_TIMEOUT_NACK:
            text = "IPG TIMEOUT"
        elif self.com.result_communication == self.com.SERIAL_NACK:
            text = "PC-NWK error"
        # if a counter reach the maximum of the trials, display an error message
        if self.com.max_retries_flag:
            self.com.max_retries_flag = 0
            if self.com.result_communication == self.com.IPG_NACK:
                self.msg_to_display.setText("Too many retries went wrong.\nRestart the operations from the beginning")
            elif self.com.result_communication == self.com.IPG_CRC_NACK:
                self.msg_to_display.setText("Too many retries went wrong.\nTry to reset the IPG and retry.")
            elif self.com.result_communication == self.com.IPG_TIMEOUT_NACK:
                self.msg_to_display.setText("No response from the IPG.\nTry to reset it and retry.")
            elif self.com.result_communication == self.com.counter_SERIAL_NACK:
                self.msg_to_display.setText(
                    "Too many retries went wrong.\nTry to close App and disconnect the NWKstation.")
            self.msg_to_display.exec()
        return text
