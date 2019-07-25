#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging, os, signal

from gi.repository import GLib
import dbus
import dbus.service
import dbus.mainloop.glib
import subprocess


#Translation support
from gettext import gettext as _
from gettext import bindtextdomain, textdomain

import sys
from SummerPalace.queue_message_client import QueueMessageClient
from SummerPalace.telemetry_common import DOMAIN,LOCALEDIR
from SummerPalace import profile_helper

DBUS_BUS_NAME = 'com.dell.SummerPalace'
DBUS_INTERFACE_NAME = 'com.dell.SummerPalace'


class Backend(dbus.service.Object):
    '''Backend manager.

    This encapsulates all services calls of the backend. It
    is implemented as a dbus.service.Object, so that it can be called through
    D-BUS as well (on the /SummerPalace object path).
    '''

    #
    # D-BUS control API
    #

    def __init__(self,config=None,scheduler=None):
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

        # summer palace variables
        self.config = config
        self.scheduler = scheduler


        #Enable translation for strings used
        bindtextdomain(DOMAIN, LOCALEDIR)
        textdomain(DOMAIN)

    def run_dbus_service(self, timeout=None, send_usr1=False):
        '''Run D-BUS server.

        If no timeout is given, the server will run forever, otherwise it will
        return after the specified number of seconds.

        If send_usr1 is True, this will send a SIGUSR1 to the parent process
        once the server is ready to take requests.
        '''
        dbus.service.Object.__init__(self, self.bus, '/SummerPalace')
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
    def create_dbus_server(cls, config=None,scheduler=None, session_bus=False):
        '''Return a D-BUS server backend instance.

        Normally this connects to the system bus. Set session_bus to True to
        connect to the session bus (for testing).

        '''
        backend = Backend(config,scheduler)
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
                         in_signature='', out_signature='ssssssssss', sender_keyword='sender',
                         connection_keyword='conn')
    def get_HW_info(self, sender=None, conn=None):
        """collect local HW info for UI to show"""
        try:
            bios_version = profile_helper.get_bios_version()
        except Exception as e:
            logging.error("[get_HW_info]ERROR is {}".format(str(e)))
            bios_version = "unknow"
        try:
            kernel = profile_helper.get_kernel_version()
        except Exception as e:
            logging.error("[get_HW_info]ERROR is {}".format(str(e)))
            kernel = "unknow"
        try:
            product_name = profile_helper.get_productname()
        except Exception as e:
            logging.error("[get_HW_info]ERROR is {}".format(str(e)))
            product_name = "unknow"
        try:
            cpu = profile_helper.get_cpu()
        except Exception as e:
            logging.error("[get_HW_info]ERROR is {}".format(str(e)))
            cpu = "unknow"
        try:
            mem = profile_helper.get_mem()
        except Exception as e:
            logging.error("[get_HW_info]ERROR is {}".format(str(e)))
            mem = "unknow"
        try:
            graphic = profile_helper.get_graphic()
        except Exception as e:
            logging.error("[get_HW_info]ERROR is {}".format(str(e)))
            graphic = "unknow"
        try:
            disk = profile_helper.get_disk()
        except Exception as e:
            logging.error("[get_HW_info]ERROR is {}".format(str(e)))
            disk = "unknow"
        try:
            ethernet,wireless = profile_helper.get_network()
        except Exception as e:
            logging.error("[get_HW_info]ERROR is {}".format(str(e)))
            ethernet, wireless = "unknow","unknow"
        #need root privillege to get info
        try:
            serialnumber = profile_helper.get_SN()
        except Exception as e:
            logging.error("[get_HW_info]ERROR is {}".format(str(e)))
            serialnumber = "unknow"
        return (serialnumber, bios_version, kernel, product_name, cpu, mem, graphic, disk, ethernet, wireless)


    @dbus.service.method(DBUS_INTERFACE_NAME,
                         in_signature='s', out_signature='', sender_keyword='sender',
                         connection_keyword='conn')
    def deal_message(self, message, sender=None, conn=None):
        if not self._check_polkit_privilege(sender, conn, 'com.dell.SummerPalace.deal_message'):
            return
        if message.startswith('button'):
            QueueMessageClient(self.config, self.scheduler).LogLogMetricEvent("BUTTON CLICK", "[{}] button click".format(message.split("button",maxsplit=1)[1]))
        elif message == 'start':
            QueueMessageClient(self.config, self.scheduler).LogLogMetricEvent("UI", "Dell Linux Assistant launchs!")
        elif message == 'stop':
            QueueMessageClient(self.config, self.scheduler).LogLogMetricEvent("UI", "Dell Linux Assistant closes!")

    @dbus.service.method(DBUS_INTERFACE_NAME,
                         in_signature='b', out_signature='', sender_keyword='sender',
                         connection_keyword='conn')
    def request_exit(self, Uninstall, sender=None, conn=None):
        if not self._check_polkit_privilege(sender, conn, 'com.dell.SummerPalace.request_exit'):
            return
        if not Uninstall:
            try:
                QueueMessageClient(self.config, self.scheduler).LogLogMetricEvent("BACKEND",
                                                                                  "the service is stopping", False)
            except Exception as e:
                logging.error("[stop]ERROR:{}".format(str(e)))
                # add to schedule pipeline
                QueueMessageClient(self.config, self.scheduler).LogLogMetricEvent("BACKEND",
                                                                                  "the service is stopping")
        else:
            QueueMessageClient(self.config, self.scheduler).LogLogMetricEvent("APPLICATION",
                                                                              "application is going to uninstall!",
                                                                              False)
            #send the backend server's PID to shutdown
            self._timeout = True
            self.main_loop.quit()
        self.scheduler.shutdown()



##                ##
## Common Classes ##
##                ##

class RestoreFailed(dbus.DBusException):
    """Exception Raised if the restoration process failed for any reason"""
    _dbus_error_name = 'com.dell.SummerPalace.RestoreFailedException'

class CreateFailed(dbus.DBusException):
    """Exception Raised if the media creation process failed for any reason"""
    _dbus_error_name = 'com.dell.SummerPalace.CreateFailedException'

class PermissionDeniedByPolicy(dbus.DBusException):
    """Exception Raised if policy kit denied the user access"""
    _dbus_error_name = 'com.dell.SummerPalace.PermissionDeniedByPolicy'

class BackendCrashError(SystemError):
    """Exception Raised if the backend crashes"""
    pass
