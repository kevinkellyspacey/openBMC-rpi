#!/usr/bin/env python
# -*- coding: utf-8 -*-
import serial
from openBMC.terminal_cmd import CMDManager

class ushell(object):
    def __init__(self, port='/dev/serial0', baudrate=115200,):
        self.port = port
        self.baudrate = baudrate
        self.cmd = CMDManager()
        self.ser = self.uart_init()


    def uart_init(self,):
        return serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
        )

    def show_banner():
        self.ser.write("\r\n")
        self.ser.write("     '##::: ##'##::::'##'####'########:'####:::'###::::\r\n");
        self.ser.write("      ###:: ##:##:::: ##. ##::##.... ##. ##:::'## ##:::\r\n");
        self.ser.write("      ####: ##:##:::: ##: ##::##:::: ##: ##::'##:. ##::\r\n");
        self.ser.write("      ## ## ##:##:::: ##: ##::##:::: ##: ##:'##:::. ##:\r\n");
        self.ser.write("      ##. ####. ##:: ##:: ##::##:::: ##: ##::#########:\r\n");
        self.ser.write("      ##:. ###:. ## ##::: ##::##:::: ##: ##::##.... ##:\r\n");
        self.ser.write("      ##::. ##::. ###:::'####:########:'####:##:::: ##:\r\n");
        self.ser.write("     ..::::..::::...::::....:........::....:..:::::..::\r\n");

        self.ser.write("          _____ _                 _____ _____ _____\r\n");
        self.ser.write("        |_   _| |_ ___ ___ _____| __  |     |_   _|\r\n");
        self.ser.write("          | | |   | -_|  _|     | __ -|  |  | | |\r\n");
        self.ser.write("          |_| |_|_|___|_| |_|_|_|_____|_____| |_|\r\n\r\n");
        self.ser.write("                        Version 1.0\r\n");
        self.ser.write("                Oregon (Amberwood) Edition\r\n\r\n");
        self.ser.write("Please enter a command or type \"help\" to list available commands\r\n\r\n")


    def run(self,):
        self.ser.isOpen()
        self.show_banner()
        while True:
            self.ser.write('\r\nuart>')
            recv_str = self.ser.read_until("\r")
            self.ser.write(cmd)
            # deal with the cmd
            cmd_name = recv_str.split()[0]
            args = tuple(recv_str.split()[1:])
            self.cmd.apply_cmd(cmd_name,self.ser,*args)

if __name__ == '__main__':
    serial_shell = ushell()
    serial_shell.run()
        
        



