import os
import sys
import csv
import pyqtgraph as pg
import ctypes
import time, threading
from waiting import wait

from PyQt5 import uic, QtWidgets, QtSerialPort, QtCore, QtGui
from PyQt5.QtSerialPort import QSerialPortInfo
from pyqtgraph import PlotWidget

UI_VERSION = "1.00"
SAMPLERATE = 1000000
PROGRAM_MODE = 0xFEFE
SYNC_CHANNELS = 0xFEFD
START_OUTPUT = 0xFEFC
STOP_OUTPUT = 0xFEFB
GET_INFO = 0xFDFA
PROGRAM_READY = 0xFDFD
CHAN_A_DATA = 0xFE01
CHAN_B_DATA = 0xFE02
END_OF_DATA = 0xFEF0
CHANNEL_A = 'A'
CHANNEL_B = 'B'

myappid = 'AmyInstrumentation.WaveWriter.1.00'
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)


class MainWindow(QtWidgets.QMainWindow):
    channelAData = []
    channelBData = []
    channelToLoad = CHANNEL_A

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        uic.loadUi(r'J:\Project Documentation\Cooks\30869_Szalwinski - Waveform Generator\Code\User Interface\WaveWriter.ui', self)
        self.setWindowTitle("Wave Writer v" + UI_VERSION)
        app_icon = QtGui.QIcon()
        #app_icon.addFile(self.resource_path('16.png'), QtCore.QSize(16,16))
        #app_icon.addFile(self.resource_path('24.png'), QtCore.QSize(24,24))
        #app_icon.addFile(self.resource_path('32.png'), QtCore.QSize(32,32))
        #app_icon.addFile(self.resource_path('48.png'), QtCore.QSize(48,48))
        #app_icon.addFile(self.resource_path('96.png'), QtCore.QSize(96,96))
        app_icon.addFile(self.resource_path('WaveWriter.ico'), QtCore.QSize(96,96))
        self.setWindowIcon(app_icon)
        
        self.initializeSerialSettings();  
        self.assignWidgets()
        self.show()

    def assignWidgets(self):
        self.button_ConnectToPort.clicked.connect(self.connectToSerialPort)
        self.button_clearConsole.clicked.connect(self.clearConsole)
        self.button_SyncChannels.clicked.connect(self.syncChannels)
        self.button_StartOutput.clicked.connect(self.startOutput)
        self.button_StopOutput.clicked.connect(self.stopOutput)
        
        self.button_ConnectToPort.setCheckable(True)
        self.button_ConnectToPort.setText("Connect")
        
        self.button_LoadCSV_ChanA.clicked.connect(lambda: self.loadCsv(CHANNEL_A))
        self.button_LoadCSV_ChanB.clicked.connect(lambda: self.loadCsv(CHANNEL_B))
        
        self.button_writeData_ChanA.clicked.connect(lambda: self.beginProgramMode(CHANNEL_A))
        self.button_writeData_ChanB.clicked.connect(lambda: self.beginProgramMode(CHANNEL_B))

        self.tableWidget_ChanA.setColumnWidth(0,100)
        self.tableWidget_ChanA.setColumnWidth(1,100)
        self.tableWidget_ChanB.setColumnWidth(0,100)
        self.tableWidget_ChanB.setColumnWidth(1,100)
        
        channelParameters = [{"param" : "Length", "value" : 0},
                {"param" : "Repeat Rate (Hz)", "value" : 0},
                {"param" : "Minimum Value", "value" : 0},
                {"param" : "Maximum Value", "value" : 0}
            ]
        header = self.tableWidget_ChanA.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header = self.tableWidget_ChanB.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header = self.tableWidget_Device.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        delegate = AlignDelegate(self.tableWidget_ChanA)
        self.tableWidget_ChanA.setItemDelegateForColumn(1, delegate)
        self.tableWidget_ChanA.setRowCount(len(channelParameters))
        self.tableWidget_ChanB.setItemDelegateForColumn(1, delegate)
        self.tableWidget_ChanB.setRowCount(len(channelParameters))
        self.populateParameterTable(self.tableWidget_ChanA, channelParameters)
        self.populateParameterTable(self.tableWidget_ChanB, channelParameters)
        
    def initializeSerialSettings(self):
        portname = "COM1"
        self.serial = QtSerialPort.QSerialPort(
            portname,
            baudRate=QtSerialPort.QSerialPort.Baud115200,
            readyRead=self.receive)
        self.combo_SerialPort.clear()
        self.combo_BaudRate.clear()
        info_list = QSerialPortInfo()
        serial_list = info_list.availablePorts()
        serial_ports = [port.portName() for port in serial_list]
        if(len(serial_ports)> 0):
            for port in serial_ports:
                self.combo_SerialPort.addItem(port)
        else:
            self.combo_SerialPort.addItem("-------")
        self.combo_BaudRate.addItem("115200")

    def beginProgramMode(self, channel):
        self.serial.write(PROGRAM_MODE.to_bytes(2, 'big'))
        self.channelToLoad = channel
        
    def receive(self):
        while self.serial.canReadLine():
            text = self.serial.readLine().data().decode().rstrip('\r\n')
            try:
                incomingWord = int(text)
                if (incomingWord == PROGRAM_READY):
                    self.printToConsole("Response received from device.")
                    print(incomingWord)
                    self.writeCSVtoARB()
            except:
                if (text[:5] == "PARAM"):
                    row, A, B = text[6:].split(':')
                    self.tableWidget_Device.setItem(int(row), 0, QtWidgets.QTableWidgetItem(A))
                    self.tableWidget_Device.setItem(int(row), 1, QtWidgets.QTableWidgetItem(B))
                else:
                    self.printToConsole(text)
                

    def writeCSVtoARB(self):
        channelData = []
        if self.channelToLoad == CHANNEL_A:
            self.serial.write(CHAN_A_DATA.to_bytes(2, 'big'))
            channelData = self.channelAData.copy()
        elif self.channelToLoad == CHANNEL_B:
            self.serial.write(CHAN_B_DATA.to_bytes(2, 'big'))
            channelData = self.channelBData.copy()

        self.printToConsole("Sending data...")
        for dataPoint in channelData:
            print(dataPoint)
            #wait(lambda: self.isDeviceReady(self.deviceReady), timeout_seconds=2, waiting_for="Device respose")
            #self.deviceReady = 0
            #print("writing datapoint")
            self.serial.write(dataPoint.to_bytes(2, 'big'))
        
        self.serial.write(END_OF_DATA.to_bytes(2, 'big'))
        self.printToConsole("Write complete.")
        
    def syncChannels(self):
        self.serial.write(SYNC_CHANNELS.to_bytes(2, 'big'))
        
    def startOutput(self):
        self.serial.write(START_OUTPUT.to_bytes(2, 'big'))
        self.printToConsole("Starting waveform output...")
        
    def stopOutput(self):
        self.serial.write(STOP_OUTPUT.to_bytes(2, 'big'))
        self.printToConsole("Stopping waveform output...")

    @QtCore.pyqtSlot(bool)
    def connectToSerialPort(self, checked):
        self.button_ConnectToPort.setText("Disconnect" if checked else "Connect")
        if checked:
            if not self.serial.isOpen():
                print(self.combo_SerialPort.currentText())
                self.serial.setPortName(self.combo_SerialPort.currentText())
                self.serial.open(QtCore.QIODevice.ReadWrite)
                self.textEdit_ReceivedData.append("Connected to " + self.combo_SerialPort.currentText())
                self.serial.write(GET_INFO.to_bytes(2, 'big'))
                if not self.serial.isOpen():
                    self.button_ConnectToPort.setChecked(False)
                    self.textEdit_ReceivedData.append("Disconnected")
            else:
                self.button_ConnectToPort.setChecked(False)
        else:
            self.serial.close()

    def loadCsv(self, channel):
        channelData = []
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open CSV",
                (QtCore.QDir.currentPath() + "/"), "CSV (*.csv *.txt)")
        if fileName:
            with open(fileName, newline='') as f:
                channelData = []
                reader = csv.reader(f)
                for row in reader:
                    for item in row:
                        channelData.append(int(item))

            length = len(channelData)
            repeatRate = round(SAMPLERATE/length, 2)
            
            clipFlag = 0
            for i in range(len(channelData)):
                if channelData[i] > 16383:
                    channelData[i] = 16383
                    clipFlag = 1
                elif channelData[i] < 0:
                    channelData[i] = 0
                    clipFlag = 1
            if clipFlag:
                self.printToConsole("Data points exceed limits.  Values clipped.")

            minValue = min(channelData)
            maxValue = max(channelData)
                
            dataRange = list(range(0, len(channelData)))
            self.plot(channel, dataRange, channelData)
            print(channelData)
            
            channelParameters = [{"param" : "Length", "value" : str(length)},
                {"param" : "Repeat Rate (Hz)", "value" : str(repeatRate)},
                {"param" : "Minimum Value", "value" : str(minValue)},
                {"param" : "Maximum Value", "value" : str(maxValue)}
            ]
            
            self.populateParameterTable(channel, channelParameters)
            
            if length > 1: 
                if channel == CHANNEL_A:
                    self.channelAData = channelData.copy()
                    self.button_writeData_ChanA.setEnabled(True)
                    self.printToConsole("Channel A data loaded.")
                if channel == CHANNEL_B:
                    self.channelBData = channelData.copy()
                    self.button_writeData_ChanB.setEnabled(True)
                    self.printToConsole("Channel B data loaded.")

    def plot(self, channel, xdata, ydata):
        pg.setConfigOption('background', 'w')
        if channel == CHANNEL_A:
            self.graphChannelA.clear()
            self.graphChannelA.plot(xdata, ydata)
        elif channel == CHANNEL_B:
            self.graphChannelB.clear()
            self.graphChannelB.plot(xdata, ydata)
    
    def populateParameterTable(self, channel, data):
        row = 0
        for parameter in data:
            if channel == CHANNEL_A:
                self.tableWidget_ChanA.setItem(row, 0, QtWidgets.QTableWidgetItem(parameter["param"]))
                self.tableWidget_ChanA.setItem(row, 1, QtWidgets.QTableWidgetItem(parameter["value"]))
            elif channel == CHANNEL_B:
                self.tableWidget_ChanB.setItem(row, 0, QtWidgets.QTableWidgetItem(parameter["param"]))
                self.tableWidget_ChanB.setItem(row, 1, QtWidgets.QTableWidgetItem(parameter["value"]))
            row = row + 1

    def clearConsole(self):
        self.textEdit_ReceivedData.clear()

    def printToConsole(self, text):
        self.textEdit_ReceivedData.append(text)
    
    def checkSerialPort(self):
        if not self.serial.isOpen():
            self.textEdit_ReceivedData.append("Serial port disconnected.")
            self.button_ConnectToPort.setChecked(False)
            self.button_writeData_ChanA.setEnabled(False)
            self.button_writeData_ChanB.setEnabled(False)
    def resource_path(self, relative_path):
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)


class AlignDelegate(QtWidgets.QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super(AlignDelegate, self).initStyleOption(option, index)
        option.displayAlignment = QtCore.Qt.AlignCenter


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()