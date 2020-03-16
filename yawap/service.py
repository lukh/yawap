# -*- coding: utf-8 -*-

import os
import sys
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
        self.logger.addHandler(
            SysLogHandler(
                address=find_syslog(), facility=SysLogHandler.LOG_DAEMON
            )
        )
        self.logger.setLevel(logging.INFO)

    def run(self):
        self.logger.info("Start Daemon")
        if os.path.exists(UDS_YAWAP):
            os.unlink(UDS_YAWAP)
        daemon = Pyro4.Daemon(unixsocket=UDS_YAWAP)

        yawap_instance = yawap_tools.Yawap(self.logger)
        daemon.register(yawap_instance, objectId=PYRO_OBJ_ID)

        daemon.requestLoop(loopCondition=lambda: not self.got_sigterm())

        self.logger.info("Stop Daemon")


def parse():
    parser = argparse.ArgumentParser(
        description="Check internet connectivity and manage access point. "
        "If started without arguments, "
        "and a internet connection is not available, "
        "then it scans wifi networks and starts in AP mode"
        "It is possible to manually turn on or off the AP. "
        "And it is possible to add Wifi network or get the list "
        "of available network found."
    )
    parser.add_argument("--service", nargs=1)
    parser.add_argument(
        "--install",
        nargs=4,
        help="Install hostapd, dnsmasq. "
        "Usage: --install INTERFACE SSID PASSWD COUNTRYCODE",
    )
    parser.add_argument(
        "--on", action="store_true", help="Start the access point"
    )
    parser.add_argument(
        "--off",
        action="store_true",
        help="Stop the access point " "and try to connect to Wifi",
    )
    parser.add_argument(
        "--list", action="store_true", help="Return the scanned Wifi Networks"
    )
    parser.add_argument(
        "--list-saved",
        action="store_true",
        help="Return the Saved Wifi Networks",
    )
    parser.add_argument(
        "--add",
        nargs=2,
        help="Connect to the network given." "Usage: --add SSID Key",
    ),
    parser.add_argument(
        "--network-conf",
        nargs=2,
        action="append",
        help="Extra network configuration for wpa_supplicant."
        "Usage: --network-conf KEY VALUE"
        "KEY and VALUE are valid wpa_supplicant params",
    ),
    parser.add_argument(
        "--delete",
        nargs=1,
        help="Delete the network given." "Usage: --del SSID",
    )

    return parser.parse_args()


def main():
    args = parse()

    service = YawapService("yawap", pid_dir="/tmp")

    if args.service is not None:
        if args.service[0] == "start" and not service.is_running():
            logging.info("starting...")
            service.start()

            # Waiting for the service to start
            # and create the communication channel
            t = time.time()
            while (time.time() - t) < 20:
                if service.is_running():
                    break
                time.sleep(0.2)
            else:
                logging.error("Can't start the service")
                service.kill()
                sys.exit(-1)

            t = time.time()
            while (time.time() - t) < 5:
                if os.path.exists(UDS_YAWAP):
                    break
                time.sleep(0.2)
            else:
                logging.error("Can't communicate with the service")
                service.kill()
                sys.exit(-1)

            yawap_make = Pyro4.Proxy(
                "PYRO:" + PYRO_OBJ_ID + "@./u:" + UDS_YAWAP
            )

            yawap_make.turn_off_ap()
            if not yawap_make.is_connected_to_internet():
                logging.info("Not connected to internet, started the AP")

                networks = yawap_make.scan_networks()

                with open(WIFI_NETWORK_LIST_FILE, "w") as fp:
                    fp.write(";".join(networks))

                yawap_make.turn_on_ap()

            else:
                logging.info("Connected :) ! Leaving")

        elif args.service[0] == "stop" and service.is_running():
            logging.info("stoping...")
            service.stop()
        elif args.service[0] == "status":
            if service.is_running():
                logging.info("Service is running.")
            else:
                logging.info("Service is not running.")

    else:
        yawap_make = Pyro4.Proxy("PYRO:" + PYRO_OBJ_ID + "@./u:" + UDS_YAWAP)

        if args.install is not None:
            yawap_instance = yawap_tools.Yawap(
                logging.getLogger("Yawap Installer")
            )
            yawap_instance.install(
                args.install[1],
                args.install[2],
                interface=args.install[0],
                iso_country_code=args.install[3],
            )

        elif args.on:
            yawap_make.turn_on_ap()

        elif args.off:
            yawap_make.turn_off_ap()

        elif args.list:
            # if ap mode started
            with open(WIFI_NETWORK_LIST_FILE) as f:
                print(f.read())

        elif args.list_saved:
            networks = yawap_make.list_saved()
            print(";".join(networks))

        elif args.add is not None:
            logging.info(f"Adding network: {args.add[0]}")
            extra_conf = (
                {el[0]: el[1] for el in args.network_conf}
                if args.network_conf is not None
                else {}
            )
            yawap_make.add_network(args.add[0], args.add[1], **extra_conf)
            yawap_make.turn_off_ap()

        elif args.delete is not None:
            logging.info(f"Deleting network: {args.delete[0]}")
            yawap_make.del_network(args.delete[0])
