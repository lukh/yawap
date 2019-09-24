# -*- coding: utf-8 -*-

import os
import subprocess
import argparse
import wpasupplicantconf as wsc

WIFI_NETWORK_LIST_FOLDER = "/var/lib/yawap/"
WIFI_NETWORK_LIST_FILE = WIFI_NETWORK_LIST_FOLDER + "scanned_networks"

def popen(cmd):
    print(cmd)
    return os.popen(cmd)


def install(ap_name, ap_passwd, interface="wlan0"):
    popen("apt install dnsmasq hostapd -y")

    popen('systemctl stop dnsmasq')
    popen('systemctl stop hostapd')

    popen('cp /etc/dhcpcd.conf /etc/dhcpcd.conf.source')
    popen('mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig')

    with open('/etc/dnsmasq.conf', "w") as dnsmasq:
        dnsmasq.write(
            "interface={}"
            "dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h".format(interface)
        )

    popen('systemctl reload dnsmasq')

    # "echo 'nickw444  ALL=(ALL:ALL) ALL' >> /etc/sudoers"

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

    popen('echo "DAEMON_CONF="/etc/hostapd/hostapd.conf" >> /etc/default/hostapd')

    if not os.path.isdir(WIFI_NETWORK_LIST_FOLDER):
        os.makedirs(WIFI_NETWORK_LIST_FOLDER)


def scan_networks(interface="wlan0"):
    print("Scanning available networks")
    command = """iwlist {} scan | grep -ioE 'SSID:"(.*)"'""".format(interface)
    result = popen(command)
    result = list(result)
    ssid_list = []

    if "Device or resource busy" not in result:
        ssid_list = [item.lstrip('SSID:').strip('"') for item in result]

    return [i for i in set(ssid_list) if i != ""]



def turn_on_ap():
    print ("Starting AP")
    popen("systemctl stop dhcpcd")

    popen("cp /etc/dhcpcd.conf.source /etc/dhcpcd.conf")
    popen('echo "interface wlan0" >> /etc/dhcpcd.conf')
    popen('echo "    static ip_address=192.168.4.1/24" >> /etc/dhcpcd.conf')
    popen('echo "    nohook wpa_supplicant" >> /etc/dhcpcd.conf')
    # popen("systemctl daemon-reload")
    popen("systemctl start dhcpcd")
    
    popen("systemctl start dnsmasq")
    popen("systemctl start hostapd")




def turn_off_ap():
    print("[Stoping AP]")
    popen("systemctl stop hostapd")
    popen("systemctl stop dnsmasq")

    popen("ip addr flush dev wlan0")
    popen("ip link set dev wlan0 up")


    popen("systemctl stop dhcpcd")
    popen("cp /etc/dhcpcd.conf.source /etc/dhcpcd.conf")
    # popen("systemctl daemon-reload")

    popen("systemctl start dhcpcd")





def is_connected_to_internet():
    print ("Checking Internet Connection")
    # ping gateway
    cmd = "ping -q -w 1 -c 1 `ip r | grep default | cut -d ' ' -f 3` > /dev/null && echo ok || echo error"
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=None, shell=True)
    output, err = process.communicate()
    
    return output == "ok"


def add_network(ssid, passwd):
    conf = wsc.WpaSupplicantConf("/etc/wpa_supplicant/wpa_supplicant.conf")
    conf.add_network(ssid, psk='"{}"'.format(passwd), key_mgmt="WPA-PSK")
    conf.write("/etc/wpa_supplicant/wpa_supplicant.conf")



def main():
    parser = argparse.ArgumentParser(description="Check internet connectivity and manage access point. When no options are given, the script checks the internet connectivity. If it can't connect to internet, it scans the wifi networks and starts the AP")
    parser.add_argument('--on', action='store_true', help='Start the access point')
    parser.add_argument('--off', action='store_true', help='Stop the access point and try to connect to Wifi')
    parser.add_argument('--scan', action='store_true', help='Return the scanned Wifi Networks')
    parser.add_argument('--connect', nargs=2, help='Connect to the network given. Usage: --connect SSID Key')

    args = parser.parse_args()

    if args.on:
        turn_on_ap()

    elif args.off:
        turn_off_ap()

    elif args.scan:
        # if ap mode started
        with open(WIFI_NETWORK_LIST_FILE) as f:
            print (f.read())

        # else:
        #   networks = scan_networks()
        #   print ("\n".join(networks))

    elif args.connect is not None:
        add_network(args.connect[0], args.connect[0])
        turn_off_ap()

    else:
        if not is_connected_to_internet():
            networks = scan_networks()

            with open(WIFI_NETWORK_LIST_FILE, 'w') as fp:
                fp.write("".join(networks))

            turn_on_ap()

