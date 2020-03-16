=======
History
=======

0.0.9 (2020-03-16)
------------------

* allows to update / get global config of wpa_supplicant

0.0.8 (2020-03-16)
------------------

* set the country code in wpa_supplicant during install
* Can pass any wpa_supplicant param when adding a new network via --network-conf

0.0.7 (2019-12-21)
------------------

* Increase Timeout for service to start

0.0.6 (2019-12-20)
------------------

* Run as a daemon, allow use as non root user

0.0.5 (2019-12-16)
------------------

* bugfix: reset connection at startup

0.0.4 (2019-12-12)
------------------

* bugfix: remove use of "mv", causing dnsmasq conf file to be lost / removed

0.0.3 (2019-12-11)
------------------

* add service target

0.0.2 (2019-12-09)
------------------

* improve valid internet connection
* improve SSID parsing
* no sudo

0.0.1 (2019-09-13)
------------------

* First release on PyPI.
