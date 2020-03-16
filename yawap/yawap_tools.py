# -*- coding: utf-8 -*-

import yawap.wpasupplicantconf as wsc

import os
import shutil
import time
import subprocess
from signal import signal, SIGPIPE, SIG_DFL
import Pyro4

from yawap import iso_country_codes as icc

signal(SIGPIPE, SIG_DFL)

WIFI_NETWORK_LIST_FOLDER = "/var/lib/yawap/"
WIFI_NETWORK_LIST_FILE = WIFI_NETWORK_LIST_FOLDER + "scanned_networks"

WPA_SUPPLICANT_FILE = "/etc/wpa_supplicant/wpa_supplicant.conf"


@Pyro4.expose
class Yawap(object):
    def __init__(self, logger):
        self.logger = logger

    def popen(self, cmd):
        self.logger.info(f'RUN > "{" ".join(cmd)}"')
        ret = subprocess.run(cmd, capture_output=True)
        return (ret.returncode, ret.stdout)

    def install(
        self, ap_name, ap_passwd, interface="wlan0", iso_country_code="EN"
    ):
        self.popen(["systemctl", "unmask", "hostapd"])

        self.popen(["systemctl", "disable", "dnsmasq"])
        self.popen(["systemctl", "disable", "hostapd"])
        time.sleep(2)

        self.popen(["systemctl", "stop", "dnsmasq"])
        self.popen(["systemctl", "stop", "hostapd"])
        time.sleep(2)

        # dhcpcd
        if not os.path.isfile("/etc/dhcpcd.conf.source"):
            with open("/etc/dhcpcd.conf", "r") as fp_dhcpcd:
                dhcpcd = fp_dhcpcd.read()

            dhcpcd += "\n" "noarp\n" "timeout 2\n" "retry 5\n"
            with open("/etc/dhcpcd.conf.source", "w") as fp_dhcpcd_source:
                fp_dhcpcd_source.write(dhcpcd)

        # wpa_supplicant
        if iso_country_code in icc.CC:
            wpa = wsc.WpaSupplicantConf(WPA_SUPPLICANT_FILE)
            wpa.fields()["country"] = iso_country_code

            wpa.write(WPA_SUPPLICANT_FILE)

        # dnsmasq
        if not os.path.isfile("/etc/dnsmasq.conf.orig"):
            shutil.copy("/etc/dnsmasq.conf", "/etc/dnsmasq.conf.orig")

        with open("/etc/dnsmasq.conf", "w") as dnsmasq:
            dnsmasq.write("interface={}\n".format(interface))
            dnsmasq.write(
                "dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h\n"
            )

        # self.popen(["systemctl reload dnsmasq')

        # "echo 'nickw444  ALL=(ALL:ALL) ALL' >> /etc/sudoers"

        # hostapd
        with open("/etc/hostapd/hostapd.conf", "w") as hostapd:
            hostapd.write(
                """\
interface={}
driver=nl80211
ssid={}
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP""".format(
                    interface, ap_name, ap_passwd
                )
            )

        with open("/etc/default/hostapd", "r") as hostapd_default:
            had = hostapd_default.read()

        had = had.replace(
            '#DAEMON_CONF=""', 'DAEMON_CONF="/etc/hostapd/hostapd.conf"'
        )
        with open("/etc/default/hostapd", "w") as hostapd_default:
            hostapd_default.write(had)

        # ssid list dir
        if not os.path.isdir(WIFI_NETWORK_LIST_FOLDER):
            os.makedirs(WIFI_NETWORK_LIST_FOLDER)

        # service
        service_file_data = """\
[Unit]
Description=Yet Another Wifi Access Point Daemon
After=network-online.target

[Service]
Type=forking
ExecStart=/usr/local/bin/yawap --service start
ExecStop=/usr/local/bin/yawap --service stop

[Install]
WantedBy=multi-user.target

    """

        with open("/etc/systemd/system/yawap.service", "w") as service_file:
            service_file.write(service_file_data)

        self.popen(["systemctl", "enable", "yawap"])

    def scan_networks(self, interface="wlan0"):
        self.logger.info("Scanning available networks")
        cmd = """iwlist {} scan | grep -ioE 'SSID:"(.*)"'""".format(interface)
        result = os.popen(cmd)  # keep it easy for now
        result = list(result)
        ssid_list = []

        if "Device or resource busy" not in result:
            ssid_list = [
                item.lstrip("SSID:").strip("\n").strip('"') for item in result
            ]

        return [i for i in set(ssid_list) if i != ""]

    def turn_on_ap(self):
        self.logger.info("Starting AP")
        self.popen(["systemctl", "stop", "dhcpcd"])

        with open("/etc/dhcpcd.conf.source") as dhcpcd_fd:
            dhcpcd_src = dhcpcd_fd.read()

        with open("/etc/dhcpcd.conf", "w") as dhcpcd_fd:
            dhcpcd_fd.write(dhcpcd_src)
            lines = (
                "interface wlan0\n"
                "    static ip_address=192.168.4.1/24\n"
                "    nohook wpa_supplicant\n"
            )
            dhcpcd_fd.write(lines)

        # self.popen(["systemctl daemon-reload")
        self.popen(["systemctl", "start", "dhcpcd"])

        self.popen(["systemctl", "start", "dnsmasq"])
        self.popen(["systemctl", "start", "hostapd"])

    def turn_off_ap(self):
        self.logger.info("[Stoping AP]")
        self.popen(["systemctl", "stop", "hostapd"])
        self.popen(["systemctl", "stop", "dnsmasq"])

        self.popen(["ip", "addr", "flush", "dev", "wlan0"])
        self.popen(["ip", "link", "set", "dev", "wlan0", "up"])

        self.popen(["systemctl", "stop", "dhcpcd"])
        self.popen(["cp", "/etc/dhcpcd.conf.source", "/etc/dhcpcd.conf"])
        # self.popen(["systemctl daemon-reload"])

        self.popen(["systemctl", "start", "dhcpcd"])

    def is_connected_to_internet(self):
        cmd = "ping -q -w 1 -c 1 8.8.8.8 > /dev/null && echo ok || echo error"

        self.logger.info("Checking Internet Connection")
        t = time.time()
        connected = False
        while time.time() - t < 10:
            # ping google gateway
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=None, shell=True
            )
            output, _ = process.communicate()

            connected = output.find(b"ok") != -1
            if connected:
                break

        return connected

    def add_network(self, ssid, passwd, **extra_conf):
        if "key_mgmt" not in extra_conf:
            extra_conf["key_mgmt"] = "WPA-PSK"

        conf = wsc.WpaSupplicantConf(WPA_SUPPLICANT_FILE)

        conf.add_network(ssid, psk='"{}"'.format(passwd), **extra_conf)

        conf.write(WPA_SUPPLICANT_FILE)

    def del_network(self, ssid):
        conf = wsc.WpaSupplicantConf(WPA_SUPPLICANT_FILE)
        conf.remove_network(ssid)
        conf.write(WPA_SUPPLICANT_FILE)

    def list_saved(self):
        try:
            conf = wsc.WpaSupplicantConf(WPA_SUPPLICANT_FILE)
            networks = conf.networks().keys()
        except (wsc.ParseError, IOError) as e:
            self.logger.error(str(e))
            networks = []

        return networks
