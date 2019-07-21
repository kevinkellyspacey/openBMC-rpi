#!usr/bin/env python

import argparse
import smbus
import time

#Define i2c bus
bus_no = 1

def main():
    parser = argparse.ArgumentParser(description="Smbpbi command")
    parser.add_argument('address',type=lambda x: int(x,0), help='Slave Device address(7bits). For example: 0x4f')
    parser.add_argument('datain',type=lambda x: int(x,0),help='Data(32bits) to write in 0x5d register. For example: 0x00000000')
    parser.add_argument('command',type=lambda x: int(x,0),help='Command(32bits) to write in 0x5c register. For example: 0x80000002 for GPU temp read')
    args = parser.parse_args()
    #print args.address , args.datain ,args.command
    datain_list=[0x04]
    datain_list.append(int(args.datain & 0xff))
    datain_list.append(int((args.datain & 0xff00)>> 8))
    datain_list.append(int((args.datain & 0xff0000) >> 16))
    datain_list.append(int((args.datain & 0xff000000) >> 24))
    
    command_list=[0x04]
    command_list.append(int(args.command & 0xff))
    command_list.append(int((args.command & 0xff00)>> 8))
    command_list.append(int((args.command & 0xff0000) >> 16))
    command_list.append(int((args.command & 0xff000000) >> 24))
 
    #print datain_list
    #print command_list
    bus = smbus.SMBus(bus_no)
    #Write 5D data
    bus.write_i2c_block_data(args.address,0x5d,datain_list)
    #Write 5C command
    bus.write_i2c_block_data(args.address,0x5c,command_list)
    time.sleep(0.1)
    #Read 5C reg
    status= bus.read_i2c_block_data(args.address,0x5c,5)
    if(status[4] == 0x1f):
    #Read 5D data
        data_back = bus.read_i2c_block_data(args.address,0x5d,5)
    elif(status[4] == 0x1e):
        bus.write_i2c_block_data(args.address,0x5c,command_list)
        time.sleep(0.1)
        status= bus.read_i2c_block_data(args.address,0x5c,5)
        data_back = bus.read_i2c_block_data(args.address,0x5d,5)
    #print status
    print "SMBPBI readback: 0x{0:02x}, status: 0x{1:02x}".format(data_back[2],status[4])
    #print data_back
    
main()
