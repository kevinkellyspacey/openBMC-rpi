#!/usr/bin/env python

import argparse
import smbus
import time


def smbpbi_read(address,command,bus=None,datain=0x0):
    # parse datain list
    datain_list=[0x04]
    datain_list.append(int(datain & 0xff))
    datain_list.append(int((datain & 0xff00)>> 8))
    datain_list.append(int((datain & 0xff0000) >> 16))
    datain_list.append(int((datain & 0xff000000) >> 24))
    # parse command list
    command_list=[0x04]
    command_list.append(int(command & 0xff))
    command_list.append(int((command & 0xff00)>> 8))
    command_list.append(int((command & 0xff0000) >> 16))
    command_list.append(int((command & 0xff000000) >> 24))

#    print("command list:",command_list)
    try:
        if not bus:
            # init I2C1
            bus = smbus.SMBus(1)
        #Write 5D data
        bus.write_i2c_block_data(address,0x5d,datain_list)
        #Write 5C command
        bus.write_i2c_block_data(address,0x5c,command_list)
        time.sleep(0.002)
        #Read 5C reg
        status= bus.read_i2c_block_data(address,0x5c,5)
#        print(status)
        if(status[4] == 0x1f):
        #Read 5D data
            data_back = bus.read_i2c_block_data(address,0x5d,5)
        elif(status[4] == 0x1e):
            for _ in range(4):
                time.sleep(0.002)
                bus.write_i2c_block_data(address,0x5c,command_list)
                time.sleep(0.002)
                status= bus.read_i2c_block_data(address,0x5c,5)
                if status[4] == 0x1f :
                    break
                elif status[4] == 0x1e:
                    continue
                else:
                    return -1,status[4]
            time.sleep(0.01)
            data_back = bus.read_i2c_block_data(address,0x5d,5)
        else:
            return -1,status[4]
        return data_back[2],status[4]
    except Exception as err:
        print("smbpbi read failed, the error info is as follows:\n{}".format(str(err)))
        return -1,-1

def main():
    parser = argparse.ArgumentParser(description="Smbpbi command")
    parser.add_argument('address',type=lambda x: int(x,0), help='Slave Device address(7bits). For example: 0x4f')
    parser.add_argument('datain',type=lambda x: int(x,0),help='Data(32bits) to write in 0x5d register. For example: 0x00000000')
    parser.add_argument('command',type=lambda x: int(x,0),help='Command(32bits) to write in 0x5c register. For example: 0x80000002 for GPU temp read')
    args = parser.parse_args()
    data_back,status = smbpbi_read(args.address,args.command,None,args.datain)   
    #print status
    print("SMBPBI readback: {0}, status: 0x{1:02x}".format(data_back,status))
    #print data_back

if __name__ == '__main__':
  	main()  
