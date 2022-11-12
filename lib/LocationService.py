import time
import socket
import googlemaps
import pywifi
from threading import Thread

# using google geolocation api for positioning
# might add a gps receiver and pynmea2 in future also, but mostly systems inside so no gps avail


class LocationService:
    def __init__(self, logger, notifier, CONFIG):

        self._logger = logger
        self._CONFIG = CONFIG
        self._notifier = notifier

        self._thread = Thread(target=self._thread_func, daemon=True)
        self._running = True

        # request data
        self._wifi_access_points = []

        # response data
        # stores geolocation response; None if no request was sent yet
        # https://developers.google.com/maps/documentation/geolocation/overview#responses
        self._geolocation_response = {}

        self._wifi = pywifi.PyWiFi()
        self._iface = self._wifi.interfaces(
        )[self._CONFIG.LOCATION_SERVICE_WIFI_INTERFACE_NO]
        self._client = googlemaps.Client(self._CONFIG.LOCATION_SERVICE_API_KEY)

    def start(self):
        self._thread.start()

    def stop(self):
        self._running = False
        self._thread.join(1)

    def _thread_func(self):
        CALC_EVERY = self._CONFIG.LOCATION_SERVICE_FORCED_UPDATE * \
            60  # update every x seconds only
        last_forced_update_time = time.time()  # last time force updated
        max_retries_high_frequency = self._CONFIG.LOCATION_SERVICE_HIGH_FREQ_UPDATE

        while self._running:
            # forced update by time
            if (time.time() > (last_forced_update_time+CALC_EVERY)):
                self._logger.info(
                    f"geolocation forced update by time triggered")

                self.updateGeolocation()

                # update last time
                last_forced_update_time = time.time()

            # higher frequency retry initial after bootup. if fails still forced update every hour or so above.
            elif (self.accuracy == None or self.accuracy > self._CONFIG.LOCATION_SERVICE_THRESHOLD_ACCURATE) and max_retries_high_frequency > 0:
                self._logger.info(
                    f"no or inaccurate location result, retry {max_retries_high_frequency} times again")

                self.updateGeolocation()

                max_retries_high_frequency -= 1

            else:
                pass

            # thread wait otherwise 100% load ;)
            time.sleep(10)

    @property
    def latitude(self):
        try:
            return self._geolocation_response['location']['lat']
        except KeyError:
            return None

    @property
    def longitude(self):
        try:
            return self._geolocation_response['location']['lng']
        except KeyError:
            return None

    @property
    def accuracy(self):
        try:
            return self._geolocation_response['accuracy']
        except KeyError:
            return None

    def decdeg2dms(self, dd):
        # 52.400561, 9.679484 converts to
        # 52°24'02.0"N 9°40'46.1"E
        is_positive = dd >= 0
        dd = abs(dd)
        minutes, seconds = divmod(dd*3600, 60)
        degrees, minutes = divmod(minutes, 60)
        degrees = degrees if is_positive else -degrees
        return (degrees, minutes, seconds)

    def is_connected(self):
        try:
            # connect to the host -- tells us if the host is actually
            # reachable
            socket.create_connection(("1.1.1.1", 53), timeout=2)
            return True
        except OSError:
            pass
        return False

    def requestGeolocation(self):
        # use api key to request via nearby wifis
        try:
            results = self._client.geolocate(
                consider_ip=self._CONFIG.LOCATION_SERVICE_CONSIDER_IP, wifi_access_points=self._wifi_access_points)

            self._logger.info(f"geolocation results: {results}")
            self._geolocation_response = (results)
        except:
            self._logger.info("no internet avail to request geolocation!")

    def gatherWifi(self):
        self._iface.scan()
        # time.sleep(0.5)
        scan_results = self._iface.scan_results()

        wifi_access_points = []
        for scan_result in scan_results:
            wifi_access_points.append(
                {"macAddress": scan_result.bssid, "signalStrength": scan_result.signal})

        self._logger.debug(wifi_access_points)
        self._logger.info(f"Found {len(scan_results)} WiFi for geolocation")

        self._wifi_access_points = wifi_access_points

    def updateGeolocation(self):
        # gather wifi
        self.gatherWifi()

        # send request
        self.requestGeolocation()
