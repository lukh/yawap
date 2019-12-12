# -*- coding: utf-8 -*-

import yawap.wpasupplicantconf as wsc

import os
import shutil
import time
import subprocess
import argparse
from signal import signal, SIGPIPE, SIG_DFL
signal(SIGPIPE, SIG_DFL)


WIFI_NETWORK_LIST_FOLDER = "/var/lib/yawap/"
WIFI_NETWORK_LIST_FILE = WIFI_NETWORK_LIST_FOLDER + "scanned_networks"


def popen(cmd):
    ret = subprocess.run(cmd, capture_output=True)
    return (ret.returncode, ret.stdout)


def install(ap_name, ap_passwd, interface="wlan0"):
    popen(["systemctl", "unmask", "hostapd"])

    popen(["systemctl", "enable", "dnsmasq"])
    popen(["systemctl", "enable", "hostapd"])
    time.sleep(2)

    popen(["systemctl", "stop", "dnsmasq"])
    popen(["systemctl", "stop", "hostapd"])
    time.sleep(2)

    # dhcpcd
    if not os.path.isfile("/etc/dhcpcd.conf.source"):
        with open('/etc/dhcpcd.conf', 'r') as fp_dhcpcd:
            dhcpcd = fp_dhcpcd.read()

        dhcpcd += "\n" \
                  "noarp\n" \
                  "timeout 2\n" \
                  "retry 5\n" \

        with open('/etc/dhcpcd.conf.source', 'w') as fp_dhcpcd_source:
            fp_dhcpcd_source.write(dhcpcd)

    # dnsmasq
    if not os.path.isfile("/etc/dnsmasq.conf.orig"):
        shutil.copy("/etc/dnsmasq.conf", "/etc/dnsmasq.conf.orig")

    with open('/etc/dnsmasq.conf', "w") as dnsmasq:
        dnsmasq.write("interface={}\n".format(interface))
        dnsmasq.write("dhcp-range="
                      "192.168.4.2,192.168.4.20,255.255.255.0,24h\n")

    # popen(["systemctl reload dnsmasq')

    # "echo 'nickw444  ALL=(ALL:ALL) ALL' >> /etc/sudoers"


    # hostapd
    with open('/etc/hostapd/hostapd.conf', "w") as hostapd:
        hostapd.write("""\
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
rsn_pairwise=CCMP""".format(interface, ap_name, ap_passwd))

    with open('/etc/default/hostapd', 'r') as hostapd_default:
        had = hostapd_default.read()

    had = had.replace('#DAEMON_CONF=""',
                      'DAEMON_CONF="/etc/hostapd/hostapd.conf"')
    with open('/etc/default/hostapd', 'w') as hostapd_default:
        hostapd_default.write(had)



    # ssid list dir
    if not os.path.isdir(WIFI_NETWORK_LIST_FOLDER):
        os.makedirs(WIFI_NETWORK_LIST_FOLDER)


    # service
    service_file_data = """\
[Unit]
Description=Yet Another Wifi Access Point Daemon
After=multi-user.target
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/yawap

[Install]
WantedBy=multi-user.target

"""

    with open('/etc/systemd/system/yawap.service', 'w') as service_file:
        service_file.write(service_file_data)


    popen(["systemctl", "enable", "yawap"])


def scan_networks(interface="wlan0"):
    print("Scanning available networks")
    command = """iwlist {} scan | grep -ioE 'SSID:"(.*)"'""".format(interface)
    result = os.popen(command)  # keep it easy for now
    result = list(result)
    ssid_list = []

    if "Device or resource busy" not in result:
        ssid_list = [item.lstrip('SSID:').strip('\n').strip('"') for item in result]

    return [i for i in set(ssid_list) if i != ""]


def turn_on_ap():
    print("Starting AP")
    popen(["systemctl", "stop", "dhcpcd"])

    with open("/etc/dhcpcd.conf.source") as dhcpcd_fd:
        dhcpcd_src = dhcpcd_fd.read()

    with open("/etc/dhcpcd.conf", 'w') as dhcpcd_fd:
        dhcpcd_fd.write(dhcpcd_src)
        lines = "interface wlan0\n    static ip_address=192.168.4.1/24\n    nohook wpa_supplicant\n"
        dhcpcd_fd.write(lines)

    # popen(["systemctl daemon-reload")
    popen(["systemctl", "start", "dhcpcd"])

    popen(["systemctl", "start", "dnsmasq"])
    popen(["systemctl", "start", "hostapd"])


def turn_off_ap():
    print("[Stoping AP]")
    popen(["systemctl", "stop", "hostapd"])
    popen(["systemctl", "stop", "dnsmasq"])

    popen(["ip", "addr", "flush", "dev", "wlan0"])
    popen(["ip", "link", "set", "dev", "wlan0", "up"])

    popen(["systemctl", "stop", "dhcpcd"])
    popen(["cp", "/etc/dhcpcd.conf.source", "/etc/dhcpcd.conf"])
    # popen(["systemctl daemon-reload"])

    popen(["systemctl", "start", "dhcpcd"])


def is_connected_to_internet():
    print("Checking Internet Connection")
    # ping google gateway
    cmd = "ping -q -w 1 -c 1 8.8.8.8 > /dev/null && echo ok || echo error"
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=None, shell=True)
    output, _ = process.communicate()

    return output.find(b"ok") != -1


def add_network(ssid, passwd):
    conf = wsc.WpaSupplicantConf("/etc/wpa_supplicant/wpa_supplicant.conf")
    conf.add_network(ssid, psk='"{}"'.format(passwd), key_mgmt="WPA-PSK")
    conf.write("/etc/wpa_supplicant/wpa_supplicant.conf")


def main():
    parser = argparse.ArgumentParser(
        description="Check internet connectivity and manage access point. "
                "If started without arguments, and a internet connection is not available, "
                "then it scans wifi networks and starts in AP mode"
                "It is possible to manually turn on or off the AP. "
                "And it is possible to add Wifi network or get the list of available network found.")
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

    if args.install is not None:
        install(args.install[1], args.install[2], interface=args.install[0])

    elif args.on:
        turn_on_ap()

    elif args.off:
        turn_off_ap()

    elif args.list:
        # if ap mode started
        with open(WIFI_NETWORK_LIST_FILE) as f:
            print(f.read())

    elif args.add is not None:
        add_network(args.add[0], args.add[1])
        turn_off_ap()

    else:
        if not is_connected_to_internet():
            print("Not connected to internet, started the AP")

            networks = scan_networks()

            with open(WIFI_NETWORK_LIST_FILE, 'w') as fp:
                fp.write(";".join(networks))

            turn_on_ap()

        else:
            print("Connected :) ! Leaving")
