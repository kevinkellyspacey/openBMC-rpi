#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging, os, signal

from gi.repository import GLib

import dbus
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
        self._timeout = False
        self.dbus_name = None

        # cached D-BUS interfaces for _check_polkit_privilege()
        self.dbus_info = None
        self.polkit = None
        self.enforce_polkit = True

        # e4700_board instance
        self.e4700_board = e4700_board(1.0,)


    def run_dbus_service(self, timeout=None, send_usr1=False):
        '''Run D-BUS server.

        If no timeout is given, the server will run forever, otherwise it will
        return after the specified number of seconds.

        If send_usr1 is True, this will send a SIGUSR1 to the parent process
        once the server is ready to take requests.
        '''
        dbus.service.Object.__init__(self, self.bus, '/RPI')
        self.main_loop = GLib.MainLoop()
        self._timeout = False
        if timeout:
            def _quit():
                """This function is ran at the end of timeout"""
                self.main_loop.quit()
                return True
            GLib.timeout_add(timeout * 1000, _quit)

        # send parent process a signal that we are ready now
        if send_usr1:
            os.kill(os.getppid(), signal.SIGUSR1)

        # run until we time out
        while not self._timeout:
            if timeout:
                self._timeout = True
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
            backend.enforce_polkit = True
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
    # Internal methods
    #

    def _reset_timeout(self):
        '''Reset the D-BUS server timeout.'''

        self._timeout = False

    def _check_polkit_privilege(self, sender, conn, privilege):
        '''Verify that sender has a given PolicyKit privilege.

        sender is the sender's (private) D-BUS name, such as ":1:42"
        (sender_keyword in @dbus.service.methods). conn is
        the dbus.Connection object (connection_keyword in
        @dbus.service.methods). privilege is the PolicyKit privilege string.

        This method returns if the caller is privileged, and otherwise throws a
        PermissionDeniedByPolicy exception.
        '''
        if sender is None and conn is None:
            # called locally, not through D-BUS
            return
        if not self.enforce_polkit:
            # that happens for testing purposes when running on the session
            # bus, and it does not make sense to restrict operations here
            return

        # get peer PID
        if self.dbus_info is None:
            self.dbus_info = dbus.Interface(conn.get_object('org.freedesktop.DBus',
                '/org/freedesktop/DBus/Bus', False), 'org.freedesktop.DBus')
        pid = self.dbus_info.GetConnectionUnixProcessID(sender)

        # query PolicyKit
        if self.polkit is None:
            self.polkit = dbus.Interface(dbus.SystemBus().get_object(
                'org.freedesktop.PolicyKit1', '/org/freedesktop/PolicyKit1/Authority', False),
                'org.freedesktop.PolicyKit1.Authority')
        try:
            # we don't need is_challenge return here, since we call with AllowUserInteraction
            (is_auth, unused, details) = self.polkit.CheckAuthorization(
                    ('unix-process', {'pid': dbus.UInt32(pid, variant_level=1),
                        'start-time': dbus.UInt64(0, variant_level=1)}),
                    privilege, {'': ''}, dbus.UInt32(1), '', timeout=600)
        except dbus.DBusException as msg:
            if msg.get_dbus_name() == \
                                    'org.freedesktop.DBus.Error.ServiceUnknown':
                # polkitd timed out, connect again
                self.polkit = None
                return self._check_polkit_privilege(sender, conn, privilege)
            else:
                raise

        if not is_auth:
            logging.debug('_check_polkit_privilege: sender %s on connection %s pid %i is not authorized for %s: %s',
                    sender, conn, pid, privilege, str(details))
            raise PermissionDeniedByPolicy(privilege)
        return is_auth
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
        except Exception as e:
            logging.error("[get_data]ERROR is {}".format(str(e)))
        return (data)


    @dbus.service.method(DBUS_INTERFACE_NAME,
                         in_signature='nsy', out_signature='', sender_keyword='sender',
                         connection_keyword='conn')
    def set_data(self, data, type, index, sender=None, conn=None):
        try:
            if type == "percent":
                self.e4700_board.get_percent(index,data)
            elif type == "temp":
                self.e4700_board.get_temp(index,data)
            elif type == "power":
                self.e4700_board.get_power(index,data)
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
        self.temperature = [None,None,None]
        # group(GPU0,GPU1,LR) current power
        self.power = [-1,-1,-1]

    def set_percent(self,index,percent):
        self.duty_cycle_percent[index] = percent

    def set_temp(self,index,temp):
        self.temperature[index] = temp

    def set_power(self,index,power):
        self.power[index] = power

    def get_percent(self,index):
        return self.duty_cycle_percent[index]

    def get_temp(self,index):
        return self.temperature[index]

    def get_power(self,index):
        return self.power[index]

    
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