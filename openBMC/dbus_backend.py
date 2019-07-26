#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging, os, signal

import glib
import gobject

import dbus
import dbus.glib
import dbus.service
import dbus.mainloop.glib
import subprocess

import sys

DBUS_BUS_NAME = 'com.openBMC.RPI'
DBUS_INTERFACE_NAME = 'com.openBMC.RPI'

class Backend(dbus.service.Object):
    '''Backend manager.

    This encapsulates all services calls of the backend. It
    is implemented as a dbus.service.Object, so that it can be called through
    D-BUS as well (on the /RPI object path).
    '''

    #
    # D-BUS control API
    #

    def __init__(self,):
        dbus.service.Object.__init__(self)

        #initialize variables that will be used during create and run
        self.bus = None
        self.main_loop = None
        self.dbus_name = None

        # e4700_board instance
        self.e4700_board = e4700_board(1.0,)


    def run_dbus_service(self, timeout=None, send_usr1=False):
        '''Run D-BUS server.

        If no timeout is given, the server will run forever, otherwise it will
        return after the specified number of seconds.

        If send_usr1 is True, this will send a SIGUSR1 to the parent process
        once the server is ready to take requests.
        '''
        gobject.threads_init()
        dbus.glib.init_threads()

        dbus.service.Object.__init__(self, self.bus, '/RPI')
        self.main_loop = glib.MainLoop()

        # send parent process a signal that we are ready now
        if send_usr1:
            os.kill(os.getppid(), signal.SIGUSR1)

        while True:
            # logging.debug("check session bus server is running!")
            self.main_loop.run()

    @classmethod
    def create_dbus_server(cls, session_bus=False):
        '''Return a D-BUS server backend instance.

        Normally this connects to the system bus. Set session_bus to True to
        connect to the session bus (for testing).

        '''
        backend = Backend()
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        if session_bus:
            backend.bus = dbus.SessionBus()
        else:
            backend.bus = dbus.SystemBus()
        try:
            backend.dbus_name = dbus.service.BusName(DBUS_BUS_NAME, backend.bus)
            logging.debug("get the dbus service ,it is {}".format(backend))
        except dbus.exceptions.DBusException as msg:
            logging.error("Exception when spawning dbus service")
            logging.error(msg)
            return None
        return backend


    #
    # Client API (through D-BUS)
    #
    @dbus.service.method(DBUS_INTERFACE_NAME,
                         in_signature='sy', out_signature='n', sender_keyword='sender',
                         connection_keyword='conn')
    def get_data(self, request, index,sender=None, conn=None):
        """return the share data based on request"""
        #need root privillege to get info
        data = -1
        try:
            if request == "percent":
                data = self.e4700_board.get_percent(index)
            elif request == "temp":
                data = self.e4700_board.get_temp(index)
            elif request == "power":
                data = self.e4700_board.get_power(index)
            elif request == "user":
                data = self.e4700_board.get_user_set(index)
        except Exception as e:
            logging.error("[get_data]ERROR is {}".format(str(e)))
        return (data)


    @dbus.service.method(DBUS_INTERFACE_NAME,
                         in_signature='nsy', out_signature='', sender_keyword='sender',
                         connection_keyword='conn')
    def set_data(self, data, type, index, sender=None, conn=None):
        try:
            if type == "percent":
                self.e4700_board.set_percent(index,data)
            elif type == "temp":
                self.e4700_board.set_temp(index,data)
            elif type == "power":
                self.e4700_board.set_power(index,data)
            elif type == "user":
                self.e4700_board.set_user_set(index,data)
        except Exception as e:
            logging.error("[set_data]ERROR is {}".format(str(e)))





class e4700_board(object):
    def __init__(self, version, bus=None,**kwargs):
        # board version
        self.version = version 
        # default I2C bus is i2c1 
        self.i2c_bus = bus
        ## store current BMC's ip
        #self.ip = None
        # user set group(GPU0,GPU1,LR) from uart input, -1 represent there's no uart request which is also the intial default otherwise 0-100
        self.duty_cycle_percent = [-1,-1,-1]
        # group(GPU0,GPU1,LR) current temperatue
        self.temperature = [-1,-1,-1]
        # group(GPU0,GPU1,LR) current power
        self.power = [-1,-1,-1]
        # group(GPU0,GPU1,LR) user set status : 0 is not set while 1 is set
        self.user_set = [0,0,0]

    def set_percent(self,index,percent):
        self.duty_cycle_percent[index] = percent

    def set_temp(self,index,temp):
        self.temperature[index] = temp

    def set_power(self,index,power):
        self.power[index] = power

    def set_user_set(self,index,status):
        self.user_set[index] = status

    def get_percent(self,index):
        return self.duty_cycle_percent[index]

    def get_temp(self,index):
        return self.temperature[index]

    def get_power(self,index):
        return self.power[index]

    def get_user_set(self,index):
        return self.user_set[index]

    
##                ##
## Common Classes ##
##                ##

class RestoreFailed(dbus.DBusException):
    """Exception Raised if the restoration process failed for any reason"""
    _dbus_error_name = 'com.openBMC.RPI.RestoreFailedException'

class CreateFailed(dbus.DBusException):
    """Exception Raised if the media creation process failed for any reason"""
    _dbus_error_name = 'com.openBMC.RPI.CreateFailedException'

class PermissionDeniedByPolicy(dbus.DBusException):
    """Exception Raised if policy kit denied the user access"""
    _dbus_error_name = 'com.openBMC.RPI.PermissionDeniedByPolicy'

class BackendCrashError(SystemError):
    """Exception Raised if the backend crashes"""
    pass



def dbus_sync_call_signal_wrapper(dbus_iface, func, handler_map, *args, **kwargs):
    '''Run a D-BUS method call while receiving signals.
    This function is an Ugly Hack™, since a normal synchronous dbus_iface.fn()
    call does not cause signals to be received until the method returns. Thus
    it calls func asynchronously and sets up a temporary main loop to receive
    signals and call their handlers; these are assigned in handler_map (signal
    name → signal handler).
    '''
    if not hasattr(dbus_iface, 'connect_to_signal'):
        # not a D-BUS object
        return getattr(dbus_iface, func)(*args, **kwargs)

    def _h_reply(*args, **kwargs):
        """protected method to send a reply"""
        global _h_reply_result
        _h_reply_result = args
        loop.quit()

    def _h_error(exception=None):
        """protected method to send an error"""
        global _h_exception_exc
        _h_exception_exc = exception
        loop.quit()

    loop = glib.MainLoop()
    global _h_reply_result, _h_exception_exc
    _h_reply_result = None
    _h_exception_exc = None
    kwargs['reply_handler'] = _h_reply
    kwargs['error_handler'] = _h_error
    kwargs['timeout'] = 86400
    for signame, sighandler in handler_map.items():
        dbus_iface.connect_to_signal(signame, sighandler)
    dbus_iface.get_dbus_method(func)(*args, **kwargs)
    loop.run()
    if _h_exception_exc:
        raise _h_exception_exc
    return _h_reply_result

def unwrap(val):
    if isinstance(val, dbus.ByteArray):
        return "".join([str(x) for x in val])
    if isinstance(val, (dbus.Array, list, tuple)):
        return [unwrap(x) for x in val]
    if isinstance(val, (dbus.Dictionary, dict)):
        return dict([(unwrap(x), unwrap(y)) for x, y in val.items()])
    if isinstance(val, (dbus.Signature, dbus.String)):
        return unicode(val)
    if isinstance(val, dbus.Boolean):
        return bool(val)
    if isinstance(val, (dbus.Int16, dbus.UInt16, dbus.Int32, dbus.UInt32, dbus.Int64, dbus.UInt64)):
        return int(val)
    if isinstance(val, dbus.Byte):
        return bytes([int(val)])
    return val 

if __name__ == '__main__':
    svr = Backend.create_dbus_server()
    sys.stdout.write("dbus_listener thread is running!")
    logging.debug("the svr is {}".format(svr))
    if not svr:
        logging.error("Error spawning DBUS server")
        sys.exit(10)
    logging.debug("dbus session server is running")
    svr.run_dbus_service()