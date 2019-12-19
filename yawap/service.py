# -*- coding: utf-8 -*-

import os
import argparse
from signal import signal, SIGPIPE, SIG_DFL

import logging
from logging.handlers import SysLogHandler
import time

import Pyro4
from service import find_syslog, Service

from . import yawap_tools

signal(SIGPIPE, SIG_DFL)

PYRO_OBJ_ID = "yawap"
UDS_YAWAP = "/tmp/yawap.s"

WIFI_NETWORK_LIST_FOLDER = "/var/lib/yawap/"
WIFI_NETWORK_LIST_FILE = WIFI_NETWORK_LIST_FOLDER + "scanned_networks"


class YawapService(Service):
    def __init__(self, *args, **kwargs):
        super(YawapService, self).__init__(*args, **kwargs)
        self.logger.addHandler(SysLogHandler(address=find_syslog(),
                               facility=SysLogHandler.LOG_DAEMON))
        self.logger.setLevel(logging.INFO)

    def run(self):
        self.logger.info('Start Daemon')
        if os.path.exists(UDS_YAWAP):
            os.unlink(UDS_YAWAP)
        daemon = Pyro4.Daemon(unixsocket=UDS_YAWAP)

        yawap_instance = yawap_tools.Yawap(self.logger)
        daemon.register(yawap_instance, objectId=PYRO_OBJ_ID)

        daemon.requestLoop(loopCondition=lambda : not self.got_sigterm())

        self.logger.info('Stop Daemon')



def main():
    parser = argparse.ArgumentParser(
        description="Check internet connectivity and manage access point. "
                "If started without arguments, and a internet connection is not available, "
                "then it scans wifi networks and starts in AP mode"
                "It is possible to manually turn on or off the AP. "
                "And it is possible to add Wifi network or get the list of available network found.")
    parser.add_argument('--service',
                        nargs=1)
    parser.add_argument('--install',
                        nargs=3,
                        help='Install hostapd, dnsmasq. '
                             'Usage: --install INTERFACE SSID PASSWD')
    parser.add_argument('--on',
                        action='store_true', help='Start the access point')
    parser.add_argument('--off',
                        action='store_true', help='Stop the access point '
                                                  'and try to connect to Wifi')
    parser.add_argument('--list',
                        action='store_true',
                        help='Return the scanned Wifi Networks')
    parser.add_argument('--add',
                        nargs=2,
                        help='Connect to the network given.'
                             'Usage: --add SSID Key')

    args = parser.parse_args()

    service = YawapService('yawap', pid_dir='/tmp')

    if args.service is not None:
        if args.service[0] == "start" and not service.is_running():
            print("starting...")
            service.start()
        elif args.service[0] == "stop" and service.is_running():
            print("stoping...")
            service.stop()
        elif args.service[0] == "status":
            if service.is_running():
                print("Service is running.")
            else:
                print("Service is not running.")

    else:
        yawap_make = Pyro4.Proxy("PYRO:" + PYRO_OBJ_ID + "@./u:" + UDS_YAWAP)

        if args.install is not None:
            yawap_make.install(args.install[1], args.install[2], interface=args.install[0])

        elif args.on:
            print(yawap_make.turn_on_ap())

        elif args.off:
            yawap_make.turn_off_ap()

        elif args.list:
            # if ap mode started
            with open(WIFI_NETWORK_LIST_FILE) as f:
                print(f.read())

        elif args.add is not None:
            yawap_make.add_network(args.add[0], args.add[1])
            yawap_make.turn_off_ap()

        else:
            yawap_make.turn_off_ap()
            if not is_connected_to_internet():
                print("Not connected to internet, started the AP")

                networks = yawap_make.scan_networks()

                with open(WIFI_NETWORK_LIST_FILE, 'w') as fp:
                    fp.write(";".join(networks))

                yawap_make.turn_on_ap()

            else:
                print("Connected :) ! Leaving")
