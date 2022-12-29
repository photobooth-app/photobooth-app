import json
from fractions import Fraction
import time
import googlemaps
import pywifi
from threading import Thread
import logging
from lib.ConfigSettings import settings
logger = logging.getLogger(__name__)
# using google geolocation api for positioning
# might add a gps receiver and pynmea2 in future also, but mostly systems inside so no gps avail


class LocationService:
    def __init__(self, ee):
        self._ee = ee

        self._thread = Thread(name="LocationServiceThread",
                              target=self._thread_func, daemon=True)
        self._running = True

        # request data
        self._wifi_access_points = []

        # response data
        # stores geolocation response; {} if no request was sent yet
        # https://developers.google.com/maps/documentation/geolocation/overview#responses
        self._setGeolocation({})

        self._init_successful = False   # thread cannot be enabled.
        if (settings.locationservice.LOCATION_SERVICE_ENABLED):
            logger.debug("geolocation api enabled, trying to setup")
            try:
                self._wifi = pywifi.PyWiFi()
                self._iface = self._wifi.interfaces(
                )[settings.locationservice.LOCATION_SERVICE_WIFI_INTERFACE_NO]
                self._client = googlemaps.Client(
                    settings.locationservice.LOCATION_SERVICE_API_KEY)
                self._init_successful = True
            except Exception as e:
                logger.error(
                    f"geolocation setup failed, stopping thread, error: {e}")
        else:
            logger.debug("geolocation api disabled, skipping setup")

        self._ee.on("publishSSE/initial", self._publishSSEInitial)

    def start(self):
        if (settings.locationservice.LOCATION_SERVICE_ENABLED):
            if (self._init_successful):
                self._running = True
                self._thread.start()
            else:
                logger.error(
                    "LocationService enabled but cannot be started since not initialized properly!")
        else:
            logger.info(
                "LocationService started but not actually enabled in config")

    def stop(self):
        self._running = False
        self._thread.join(1)

    def _thread_func(self):
        CALC_EVERY = settings.locationservice.LOCATION_SERVICE_FORCED_UPDATE * \
            60  # update every x seconds only
        last_forced_update_time = time.time()  # last time force updated
        max_retries_high_frequency = settings.locationservice.LOCATION_SERVICE_HIGH_FREQ_UPDATE

        while self._running:
            # forced update by time
            if (time.time() > (last_forced_update_time+CALC_EVERY)):
                logger.info(
                    f"geolocation forced update by time triggered")

                self.updateGeolocation()

                # update last time
                last_forced_update_time = time.time()

            # higher frequency retry initial after bootup. if fails still forced update every hour or so above.
            elif (self.accuracy == None or self.accuracy > settings.locationservice.LOCATION_SERVICE_THRESHOLD_ACCURATE) and max_retries_high_frequency > 0:
                logger.info(
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

    @property
    def latitudeDMS(self):
        try:
            return self._decdeg2dms(self._geolocation_response['location']['lat'])
        except KeyError:
            return None

    @property
    def longitudeDMS(self):
        try:
            return self._decdeg2dms(self._geolocation_response['location']['lng'])
        except KeyError:
            return None

    @property
    def latitudeRef(self):
        if (self.latitude != None):
            return 'S' if self.latitude < 0 else 'N'
        else:
            return None

    @property
    def longitudeRef(self):
        if (self.longitude != None):
            return 'W' if self.longitude < 0 else 'E'
        else:
            return None

    def _decdeg2dms(self, dd):
        # 52.400561, 9.679484 converts to
        # 52°24'02.0"N 9°40'46.1"E
        is_positive = dd >= 0
        dd = abs(dd)
        minutes, seconds = divmod(dd*3600, 60)
        degrees, minutes = divmod(minutes, 60)
        degrees = degrees if is_positive else -degrees

        return (Fraction(degrees).as_integer_ratio(), Fraction(minutes).as_integer_ratio(), Fraction(seconds).limit_denominator(100000).as_integer_ratio())

    def requestGeolocation(self):
        # use api key to request via nearby wifis
        try:
            results = self._client.geolocate(
                consider_ip=settings.locationservice.LOCATION_SERVICE_CONSIDER_IP, wifi_access_points=self._wifi_access_points)

            logger.info(f"geolocation results: {results}")

            self._setGeolocation(results)
        except Exception as e:
            logger.exception(e)
            logger.error(f"geolocation request failed, error {e}")

    def gatherWifi(self):
        self._iface.scan()
        # time.sleep(0.5)
        scan_results = self._iface.scan_results()

        wifi_access_points = []
        for scan_result in scan_results:
            wifi_access_points.append(
                {"macAddress": scan_result.bssid, "signalStrength": scan_result.signal})

        logger.debug(wifi_access_points)
        logger.info(f"Found {len(scan_results)} WiFi for geolocation")

        self._wifi_access_points = wifi_access_points

    def updateGeolocation(self):
        # gather wifi
        self.gatherWifi()

        # send request
        self.requestGeolocation()

    def _setGeolocation(self, results):
        self._geolocation_response = results
        self._publishSSE_geolocation()

    def _publishSSEInitial(self):
        self._publishSSE_geolocation()

    def _publishSSE_geolocation(self):
        self._ee.emit("publishSSE", sse_event="locationservice/geolocation",
                      sse_data=json.dumps(self._geolocation_response))
