#!/usr/bin/env python

import argparse
import smbus
import time
from openBMC.smbpbi import smbpbi_read
from openBMC.dbus_backend import Backend,dbus_sync_call_signal_wrapper,unwrap
from datetime import datetime
from datetime import timedelta
from threading import Thread
import logging
import dbus
import sys

##                ##
##Common Variables##
##                ##
SMPBI_MAX_GPUS = 2
I2C_BUS_NUM =1
TMP451_7bit_ADDR = 0x48
GPU0_7bit_ADDR = 0x4C
GPU1_7bit_ADDR = 0x4D
MAX31790_7bit_ADDR = 0x2C

gpu_temp_command = 0x80000002
hbm_temp_command = 0x80000502

def led_red_ylw_control():
    '''leverage from E4714 which need to validate on RPI'''
    pass

def interval_millis(start_time):
    dt = datetime.now() - start_time
    ms = (dt.days * 24 * 60 * 60 + dt.seconds) * 1000 + dt.microseconds/1000.0
    return ms

def tmp451_init(bus):
    #set TMP451 WARN and OVERT to 90+64C and 95+64C
    bus.write_byte_data(TMP451_7bit_ADDR, 0x0d, 0x9f)
    time.sleep(0.001)
    bus.write_byte_data(TMP451_7bit_ADDR, 0x19, 0x9a)
    time.sleep(0.001)
    bus.write_byte_data(TMP451_7bit_ADDR, 0x0b, 0x9f)
    time.sleep(0.001)
    bus.write_byte_data(TMP451_7bit_ADDR, 0x20, 0x9a)
    time.sleep(0.001)
    #set TMP451 range to -64 to 191 C
    bus.write_byte_data(TMP451_7bit_ADDR, 0x09, 0x04)
    time .sleep(0.001)

def get_temp(GPU_type,bus=None):
    if GPU_type == "GPU0_TEMP":
        temp,status = smbpbi_read(GPU0_7bit_ADDR,gpu_temp_command,bus)
    elif GPU_type == "GPU0_HBM":
        temp,status = smbpbi_read(GPU0_7bit_ADDR,hbm_temp_command,bus)
    elif GPU_type == "GPU1_TEMP":
        temp,status = smbpbi_read(GPU1_7bit_ADDR,gpu_temp_command,bus)
    elif GPU_type == "GPU1_HBM":
        temp,status = smbpbi_read(GPU1_7bit_ADDR,hbm_temp_command,bus)
    elif GPU_type == "LR_TEMP":
        temp = bus.read_byte_data(TMP451_7bit_ADDR,0x01)
        # minus the offset 60c because of extend mode
        temp = temp - 64
    else:
        print("the GPU type [{}] doesn't support".format(str(GPU_type)))
        temp = -1
    return temp

def max31790_set_pwm(slave_addr,offset,duty_cycle_percent,bus):
    # full-scale is 511, see at MAX31790 spec P.35.
    duty_cycle = duty_cycle_percent * 511 / 100
    duty_cycle_word = duty_cycle << 7
    bus.write_word_data(slave_addr,offset,duty_cycle_word)


def pwm_reqest_set(GPU_type,duty_cycle_percent,bus,dbus_iface):
    if GPU_type == 0:
        # set pwm out1
        max31790_set_pwm(MAX31790_7bit_ADDR, 0x40,duty_cycle_percent,bus)
        time.sleep(0.001)
        # set pwm out2
        max31790_set_pwm(MAX31790_7bit_ADDR, 0x42,duty_cycle_percent,bus)
        time.sleep(0.001)
        set_dbus_data(0,"percent",duty_cycle_percent,dbus_iface)
    elif GPU_type == 1:
        # set pwm out3
        max31790_set_pwm(MAX31790_7bit_ADDR, 0x44,duty_cycle_percent,bus)
        time.sleep(0.001)
        # set pwm out4
        max31790_set_pwm(MAX31790_7bit_ADDR, 0x46,duty_cycle_percent,bus)
        time.sleep(0.001)
        set_dbus_data(1,"percent",duty_cycle_percent,dbus_iface)
    elif GPU_type == 2:
        # set pwm out5
        max31790_set_pwm(MAX31790_7bit_ADDR, 0x48,duty_cycle_percent,bus)
        time.sleep(0.001)
        set_dbus_data(2,"percent",duty_cycle_percent,dbus_iface)
    elif GPU_tyepe == 3:
        # set pwm out1
        max31790_set_pwm(MAX31790_7bit_ADDR, 0x40,duty_cycle_percent,bus)
        time.sleep(0.001)
        # set pwm out2
        max31790_set_pwm(MAX31790_7bit_ADDR, 0x42,duty_cycle_percent,bus)
        time.sleep(0.001)
        # set pwm out3
        max31790_set_pwm(MAX31790_7bit_ADDR, 0x44,duty_cycle_percent,bus)
        time.sleep(0.001)
        # set pwm out4
        max31790_set_pwm(MAX31790_7bit_ADDR, 0x46,duty_cycle_percent,bus)
        time.sleep(0.001)
        # set pwm out5
        max31790_set_pwm(MAX31790_7bit_ADDR, 0x48,duty_cycle_percent,bus)
        time.sleep(0.001)
        for i in range(3):
            set_dbus_data(i,"percent",duty_cycle_percent,dbus_iface)


def set_dbus_data(GPU_index,type,data,dbus_iface):
    # set the data to dbus server database which can share with different threads
    dbus_data = dbus_sync_call_signal_wrapper(dbus_iface,"set_data",{},data,type,GPU_index)

def get_dbus_data(GPU_index,type,dbus_iface):
    # get the data from dbus server database which can share with different threads
    dbus_data = dbus_sync_call_signal_wrapper(dbus_iface,"get_data",{},type,GPU_index)
    if dbus_data:
        val = unwrap(dbus_data)
        # the return value is a list
        return val[0]


def check_sxm_master_pwr_good(bus):
    '''check_sxm_master_pwr_gd() is used to check whether Mother Board power and FPGA_MASTER_PWM_EN are on to avoid throw out error message even if sxm is not ready.
        Out: 
        -1 read FPGA failed.
         0 SXM is ready.
         1 SXM is not ready.
         2 FPGA_MASTER_PWM_EN is not ready.
    '''
    pwr_good_set = [0,0,0] # represents GPU0, GPU1 and LR's pwr_good_set status
    fpga_data = 0
    try:
        fpga_data = bus.read_byte_data(0x12,0x11)
    except Exception as err:
        print("Failed to read FPGA_MASTER_PWM_EN\n{}".format(str(err)))
    #FPGA_MASTER_PWM_EN is low
    FPGA_MASTER_PWM_EN = fpga_data & 0x01
    if not FPGA_MASTER_PWM_EN:
       return pwr_good_set[0],pwr_good_set[1],pwr_good_set[2]
    #Check LR_PRSNT
    lr_data = 0
    try:
        lr_data = bus.read_byte_data(0x12,0x0f)
    except Exception as err:
        print("Failed to read LR_PRSNT\n{}".format(str(err)))
    pwr_good_set[2] = lr_data & 0x04
    #Check GPU_PWR_GD
    sxm_data = 0
    try:
        sxm_data = bus.read_byte_data(0x12,0x0d)
    except Exception as err:
        print("Failed to read GPU_PWR_GD\n{}".format(str(err)))
    pwr_good_set[0] = sxm_data & 0x05
    pwr_good_set[1] = sxm_data & 0x0a

    return pwr_good_set[0],pwr_good_set[1],pwr_good_set[2]


def profile_get_value(temp):
    '''return the pwm percent based on input temperature'''
    percent = 90 # profile's max value
    if temp < 35:
        percent = 60 * temp / 100
        if percent > 90:
            percent = 90
        elif percent < 10:
            percent = 10
    else:
        if temp < 100:
            percent = 120 * temp / 100
            if percent > 90:
                percent = 90
            elif percent < 10:
                percent = 10
    return percent


def i2c1_init():
    return smbus.SMBus(I2C_BUS_NUM)

class fan_control(object):
    def __init__(self, bus=None,polling=True):
        self.polling = polling
        self.bus = bus
        self.thredhold = 900 # 900 ms to finish one 
        # dbus client instance
        self._dbus_iface = dbus.Interface(dbus.SystemBus().get_object('com.openBMC.RPI','/RPI'),'com.openBMC.RPI')


    def fan_ctrl_loop(self,):
        start_point = datetime.now()
        fail_times = [0,0,0] # GPU0 GPU1 LR fail time counter
        while self.polling:
            if interval_millis(start_point) >= 900:
                GPU0_pwr_good_set,GPU1_pwr_good_set,LR_pwr_good_set = check_sxm_master_pwr_good(self.bus)
                #print(GPU0_pwr_good_set,GPU1_pwr_good_set,LR_pwr_good_set)
                ## GPU0 fan control ###########################################
                duty_cycle_percent = get_dbus_data(0,"percent",self._dbus_iface) 
                if GPU0_pwr_good_set == 0 :
                    duty_cycle_percent = 20
                elif get_dbus_data(0,"user",self._dbus_iface) == 0:
                    # get GPU0 temp
                    gpu = get_temp("GPU0_TEMP",self.bus)
                    # get GPU0 HBM
                    hbm = get_temp("GPU0_HBM",self.bus)
                    if (gpu == -1) and (hbm == -1):
                        fail_times[0] = fail_times[0] + 1
                        if fail_times[0] == 5:
                            print("GPU0 reading failed 5 times, set fan speed to 80%\n")
                            duty_cycle_percent = 80
                    else:
                        temp = gpu if gpu >= hbm else hbm
                        print("GPU0 temp is {}".format(temp))
                        duty_cycle_percent = profile_get_value(temp)
                        if fail_times[0] > 0:
                            fail_times[0] = 0
                            print("GPU0 reading recovered, and fan control enabled again!\n")
                print("GPU0 duty percent is {}".format(duty_cycle_percent))
                # update the percent to dbus server
                pwm_reqest_set(0,duty_cycle_percent,self.bus,self._dbus_iface)

                ## GPU1 fan control ############################################
                duty_cycle_percent = get_dbus_data(1,"percent",self._dbus_iface) 
                if GPU1_pwr_good_set == 0 :
                    duty_cycle_percent = 20
                elif get_dbus_data(1,"user",self._dbus_iface) == 0:
                    # get GPU1 temp
                    gpu = get_temp("GPU1_TEMP",self.bus)
                    # get GPU1 HBM
                    hbm = get_temp("GPU1_HBM",self.bus)
                    if (gpu == -1) and (hbm == -1):
                        fail_times[1] = fail_times[1] + 1
                        if fail_times[1] == 5:
                            print("GPU1 reading failed 5 times, set fan speed to 80%\n")
                            duty_cycle_percent = 80
                    else:
                        temp = gpu if gpu >= hbm else hbm
                        print("GPU1 temp is {}".format(temp))
                        duty_cycle_percent = profile_get_value(temp)
                        if fail_times[1] > 0:
                            fail_times[1] = 0
                            print("GPU1 reading recovered, and fan control enabled again!\n")
                print("GPU1 duty percent is {}".format(duty_cycle_percent))
                # update the percent to dbus server
                pwm_reqest_set(1,duty_cycle_percent,self.bus,self._dbus_iface)
                
                ## LR fan control ##############################################
                duty_cycle_percent = get_dbus_data(2,"percent",self._dbus_iface) 
                if LR_pwr_good_set == 0 :
                    duty_cycle_percent = 20
                elif get_dbus_data(2,"user",self._dbus_iface) == 0:
                    # get LR temp
                    gpu = get_temp("LR_TEMP",self.bus)
                    if (gpu == -1):
                        fail_times[2] = fail_times[2] + 1
                        if fail_times[2] == 5:
                            print("LR reading failed 5 times, set fan speed to 80%\n")
                            duty_cycle_percent = 80
                    else:
                        temp = gpu
                        print("LR temp is {}".format(temp))
                        duty_cycle_percent = profile_get_value(temp)
                        if fail_times[2] > 0:
                            fail_times[2] = 0
                            print("LR reading recovered, and fan control enabled again!\n")
                print("LR duty percent is {}".format(duty_cycle_percent))
                # update the percent to dbus server
                pwm_reqest_set(2,duty_cycle_percent,self.bus,self._dbus_iface)
                
                #update start point
                start_point = datetime.now()



if __name__ == '__main__':
    i2c1 = i2c1_init()
    tmp451_init(i2c1)
    loop_task = fan_control(i2c1)
    loop_task.fan_ctrl_loop()
   
