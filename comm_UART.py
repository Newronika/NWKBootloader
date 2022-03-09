import numpy as np
import serial
import threading
import time

class UART_functions:
    def __init__(self):
        ## TX CMD ##
        self.bootVersionCommandTX = 0x31
        self.appVersionCommandTX = 0x32
        self.testPacketCommandTX = 0x33
        self.readFRAMCommandTX = 0x34
        self.writeFRAMCommandTX = 0x35
        self.programL1CommandTX = 0x36
        self.EraseL1CommandTX = 0x37
        self.programL4CommandTX = 0x38
        self.EraseL4CommandTX = 0x39
        self.runAppCommandTX = 0x3A
        self.prepareFRAMCommandTX = 0x3B
        self.opErrorCommandTX = 0x92

        ## RX CMD ##
        self.bootVersionCommandRX = 0x51
        self.appVersionCommandRX = 0x52
        self.testPacketCommandRX = 0x53
        self.readFRAMCommandRX = 0x54
        self.writeFRAMCommandRX = 0x55
        self.programL1CommandRX = 0x56
        self.EraseL1CommandRX = 0x57
        self.programL4CommandRX = 0x58
        self.EraseL4CommandRX = 0x59
        self.runAppCommandRX = 0x5A
        self.prepareFRAMCommandRX = 0x5B
        self.percCompletionCommand = 0x71
        self.opErrorCommandRX = 0x72


        self.bootVersionCommand = [0x31, 0x51]
        self.appVersionCommand = [0x32, 0x52]
        self.testPacketCommand = [0x33, 0x53]
        self.readFRAMCommand = [0x34, 0x54]
        self.writeFRAMCommand = [0x35, 0x55]
        self.programL1Command = [0x36, 0x56]
        self.EraseL1Command = [0x37, 0x57]
        self.programL4Command = [0x38, 0x58]
        self.EraseL4Command = [0x39, 0x59]
        self.runAppCommand = [0x3A, 0x5A]
        self.prepareFRAMCommand = [0x3B, 0x5B]
        self.opErrorCommand = [0x92, 0x72]
        self.TX = 0
        self.RX = 1

        ## message format ##
        self.buffLen = 64
        self.crc_index = 61
        self.cnt_index = 2
        self.cmd_index = 3
        self.ack_index = 4
        self.SRC_Tx = 0x10
        self.DST_Tx = 0x11
        self.LEN_DATA = 4
        self.LEN_PAYLOAD = 52
        self.LEN_HASH = 16
        self.SRC_Rx = 0x11
        self.DST_Rx = 0x10

        #UART communication features
        self.open = 0
        self.baudrate = 38400
        self.ACK = 0x01
        self.IPG_NACK = 0x02
        self.IPG_CRC_NACK = 0x03
        self.IPG_TIMEOUT_NACK = 0X04
        self.SERIAL_NACK = 0x05
        self.SERIAL_TIMEOUT_NACK = 0X06
        self.counter_IPG_NACK = 0
        self.counter_IPG_CRC_NACK = 0
        self.counter_IPG_TIMEOUT_NACK = 0
        self.counter_SERIAL_NACK = 0
        self.counter_SERIAL_TIMEOUT_NACK = 0
        self.nack_list = [self.IPG_NACK, self.IPG_CRC_NACK, self.IPG_TIMEOUT_NACK, self.SERIAL_NACK, self.SERIAL_TIMEOUT_NACK]
        self.counter_list = [self.counter_IPG_NACK, self.counter_IPG_CRC_NACK, self.counter_IPG_TIMEOUT_NACK,
                             self.counter_SERIAL_NACK, self.counter_SERIAL_TIMEOUT_NACK]
        self.MAX_COUNTER = 5
        self.max_retries_flag = 0
        self.timeout = 40

    ## CRC is a method like checksum to verify that a message is correct
    def CRC8_calculation(self, buffer):
        crc = 0x00
        len = self.buffLen - 3
        cnt = 0
        while cnt < len:
            extract = buffer[cnt]
            for i in range(8):
                #XOR operation
                sum = (crc ^ extract) & 0x01
                crc = crc >> 1
                if sum:
                     crc = crc ^ 0x8C
                extract = extract >> 1
            cnt = cnt + 1

        return crc

    def msgTX(self, cmd, data, payload, cnt, dc):
        self.CNT = cnt
        self.CMD_Tx = cmd[self.TX]
        self.CMD_Rx = cmd[self.RX]
        self.writeBuffer = bytearray()
        self.writeBuffer.append(self.SRC_Tx)
        self.writeBuffer.append(self.DST_Tx)
        self.writeBuffer.append(self.CNT)
        self.writeBuffer.append(self.CMD_Tx)
        self.writeBuffer.append(dc)
        for i in range(self.LEN_DATA):
            self.writeBuffer.append(int(data[i]))
        for i in range(self.LEN_PAYLOAD):
            self.writeBuffer.append(int(payload[i]))
        crc = self.CRC8_calculation(self.writeBuffer)
        self.writeBuffer.append(crc)

        #self.writeBuffer.append(0x00)
        #print(len(self.writeBuffer))
        #self.writeBuffer.append(0x00)
        return self.writeBuffer


    def open_comm(self, port):
        self.NWK_SerialCon = serial.Serial(port, self.baudrate, bytesize=8, parity=serial.PARITY_NONE,
                                           stopbits=serial.STOPBITS_ONE)
        self.thread_send = 0
        self.thread_receive = 0

        #self.t1 = threading.Thread(target=self.Task1, args=[self.NWK_SerialCon])
        #self.t1.start()
        self.open = 1

    def send_command(self, msg):
        self.thread_send = 1
        self.writeBuffer = msg
        #self.t2 = threading.Thread(target=self.Task2, args=[self.NWK_SerialCon])
        #self.t2.start()
        self.send_signal()

    def Task2(self, *kwargs):
        while self.NWK_SerialCon.out_waiting:
            self.NWK_SerialCon.flushOutput()
        while self.thread_send:
            self.send_signal()

    def send_signal(self):
        self.NWK_SerialCon.flushInput()
        b = self.NWK_SerialCon.write(self.writeBuffer)
        print("sending")
        self.thread_send = 0

    def StartSerialAcquisition(self):
        self.time_expired = False
        self.cnt = 0
        self.FillBuffer = 0
        self.start_time = time.time()
        self.end_time = time.time()
        self.thread_receive = 1
        self.ReceivedBuffer = np.zeros(self.buffLen - 2, dtype='i')
        while self.thread_receive and (self.end_time - self.start_time) <= self.timeout:
            self.Fill_and_Process_Signal()
        self.NWK_SerialCon.flushInput()
        if (self.end_time - self.start_time) >= self.timeout:
            print("timeout")
            self.time_expired = True
            self.thread_receive = 0


    def Task1(self, *kwargs):
        while self.thread_receive and (self.end_time - self.start_time) <= self.timeout:
            self.Fill_and_Process_Signal()

        if (self.end_time - self.start_time) >= self.timeout:
            print("timeout")
            self.time_expired = True
            self.thread_receive = 0


    def Fill_and_Process_Signal(self):
        self.end_time = time.time()
        if self.NWK_SerialCon.inWaiting() > 0:
            NWKString = self.NWK_SerialCon.read(size=1)
            self.Int2Store = ord(NWKString)
            if self.FillBuffer == 1:
                self.ReceivedBuffer[self.cnt] = self.Int2Store
                self.cnt += 1

            if self.Int2Store == self.SRC_Rx and self.cnt == 0:
                self.ReceivedBuffer[self.cnt] = self.Int2Store
                self.cnt += 1

            if self.Int2Store == self.DST_Rx and self.cnt == 1:
                self.ReceivedBuffer[self.cnt] = self.Int2Store
                self.cnt += 1
                self.FillBuffer = 1

            if self.cnt == self.buffLen - 2:
                self.cnt = 0
                self.FillBuffer = 0
                self.thread_receive = 0


    def get_data_rx(self):
        #if a NACK is received do not verify the content but send the nack type
        if self.ReceivedBuffer[self.ack_index] in self.nack_list:

            self.result_communication = self.ReceivedBuffer[self.ack_index]
            self.NWK_SerialCon.flushInput()
            print("qui")
            print(self.ReceivedBuffer[self.ack_index])
            self.update_counter_nack(self.result_communication)
            return False
        #if ACK get data
        else:
            for i in range(len(self.counter_list)):
                self.counter_list[i] = 0
            #return version of the firware
            if self.CMD_Tx == self.bootVersionCommand[self.TX]:
                self.result_communication = (str(self.ReceivedBuffer[5]) + "." + str(self.ReceivedBuffer[6]))
            #return version of the app
            elif self.CMD_Tx == self.appVersionCommand[self.TX]:
                self.result_communication = (str(self.ReceivedBuffer[5]) + "." + str(self.ReceivedBuffer[6]))
            #return test packets
            elif self.CMD_Tx == self.testPacketCommand[self.TX]:
                self.result_communication = self.ReceivedBuffer[5: 37]
            elif self.CMD_Tx == self.readFRAMCommand[self.TX]:
                self.result_communication = self.ReceivedBuffer[5: 61]
            #resturn ACK
            #elif self.CMD_Tx == self.prepareFRAMCommand[self.TX] or self.CMD_Tx == self.writeFRAMCommand[self.TX]:
             #   if self.ReceivedBuffer[4] == self.ACK:
              #      self.result_communication = True
               # else:
                #    self.result_communication = False

            else:
                self.result_communication = True

            return True

    #verify rightness of the message
    def verify_msg_rx(self):
        crc_calc = self.CRC8_calculation(self.ReceivedBuffer[0: self.crc_index])
        print(crc_calc)
        #verify crc value, cmd key and cnt and ack
        #if crc_calc == self.ReceivedBuffer[self.crc_index] and self.ReceivedBuffer[self.cnt_index] == self.CNT and self.ReceivedBuffer[self.cmd_index] == self.CMD_Rx:
        if crc_calc == self.ReceivedBuffer[self.crc_index]:
            result = self.get_data_rx()
        else:
            self.result_communication = self.SERIAL_NACK
            self.update_counter_nack(self.result_communication)
            result = False
        return result


    #verify rightness of the message regarding the operation status
    def verify_op_status_message(self):
        crc_calc = self.CRC8_calculation(self.ReceivedBuffer[0: self.crc_index])
        #verify crc value, cmd key and cnt and ack
        if crc_calc == self.ReceivedBuffer[self.crc_index]:
            print("ACK")
            return self.ACK
        else:
            return self.SERIAL_NACK

    def send_msg_wait_4_ack(self, msg):
        #send formatted message
        self.send_command(msg)
        result = None
        while result == None:
            #wait to receive ACK/NACK
            self.StartSerialAcquisition()
            if not self.thread_receive:
                if self.time_expired:
                    self.result_communication = self.counter_SERIAL_TIMEOUT_NACK
                    self.update_counter_nack(self.result_communication)
                    return False
                else:
                    print(self.ReceivedBuffer)
                    result = self.verify_msg_rx()
                    #if message was decoded correctly:
                    if result:
                        return self.result_communication
                    else:
                        return False


    def get_progression_status(self):
            self.StartSerialAcquisition()
            #if a command of percentage completion is received
            print(self.ReceivedBuffer)
            if self.ReceivedBuffer[self.cmd_index] == self.percCompletionCommand:
                self.percentage = self.ReceivedBuffer[5]
                print(self.percentage)
            elif self.ReceivedBuffer[self.cmd_index] == self.opErrorCommand[self.RX]:
                self.cnt_id = self.ReceivedBuffer[self.cnt_index]
                self.correct_status = self.verify_op_status_message()
                if self.ReceivedBuffer[5] == self.ACK:
                    self.completed = True
                else:
                    self.error = True




    def update_counter_nack(self, nack):
        index = np.where(np.array(self.nack_list) == nack)[0][0]
        print(index)
        # update NACK counter
        self.counter_list[index] = self.counter_list[index] + 1
        # if counter reaches the maximum update flag
        if self.counter_list[index] == self.MAX_COUNTER:
            self.max_retries_flag = 1
            for i in range(len(self.counter_list)):
                self.counter_list[i] = 0
