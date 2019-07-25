import serial

class ushell(object):
    def __init__(self, port='/dev/serial0', baudrate=115200,):
        # cmd sample:cmd_name:[cmd_function,max_args_length,description]
        self.cmd_list ={}
        self.port = port
        self.baudrate = baudrate
        self.ser = self.uart_init()

    def add_cmd(self,cmd_name,*args):
        pass

    def remove_cmd(self,cmd_name):
        pass

    def update_cmd(self,cmd_name,*args):
        pass

    def search_cmd(self,cmd_name):
        pass

    def apply_cmd(self,cmd_name,*args):
        pass

    def print_command_list(self,):
        cmd_list = ""
        for key in self.cmd_list:
            cmd_list += "{0}:{1}\n".format(key,self.cmd_list[key][2])
        #print(cmd_list)
        return cmd_list

    def help_command(self,cmd_name=None):
        if not cmd_name:
            self.print_command_list()
            return 

        if cmd in self.cmd_list.keys():
            print("{0}:{1}\n".format(cmd,self.cmd_list[cmd][2]))
            return "{0}:{1}\n".format(cmd,self.cmd_list[cmd][2])
        else:
            print("this {} is not in the commad list".format(cmd_name))

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
            self.apply_cmd(recv_str)

if __name__ == '__main__':
    pass
        
        



