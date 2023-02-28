""" 

Gather location based on IP and WiFi to embed in Exif data

"""
import time
import logging
from threading import Thread
from fractions import Fraction
import googlemaps
import pywifi
from src.configsettings import settings

logger = logging.getLogger(__name__)
# using google geolocation api for positioning
# might add a gps receiver and pynmea2 in future also, but mostly systems inside so no gps avail


class LocationService:
    """_summary_"""

    def __init__(self):
        self._thread = Thread(
            name="LocationServiceThread", target=self._thread_func, daemon=True
        )
        self._running = True

        # request data
        self._wifi_access_points = []

        # response data
        # stores geolocation response; {} if no request was sent yet
        # https://developers.google.com/maps/documentation/geolocation/overview#responses
        self._geolocation_response = {}

        self._init_successful = False  # thread cannot be enabled.
        if settings.locationservice.LOCATION_SERVICE_ENABLED:
            logger.debug("geolocation api enabled, trying to setup")
            try:
                self._wifi = pywifi.PyWiFi()
                self._iface = self._wifi.interfaces()[
                    settings.locationservice.LOCATION_SERVICE_WIFI_INTERFACE_NO
                ]
                self._client = googlemaps.Client(
                    settings.locationservice.LOCATION_SERVICE_API_KEY
                )
                self._init_successful = True
            except Exception as exc:
                logger.error(f"geolocation setup failed, stopping thread, error: {exc}")
        else:
            logger.debug("geolocation api disabled, skipping setup")

    def start(self):
        """_summary_"""
        if settings.locationservice.LOCATION_SERVICE_ENABLED:
            if self._init_successful:
                self._running = True
                self._thread.start()
            else:
                logger.error(
                    "LocationService enabled but cannot be started since not initialized properly!"
                )
        else:
            logger.info("LocationService started but not actually enabled in config")

    def stop(self):
        """_summary_"""
        self._running = False
        self._thread.join(1)

    def _thread_func(self):
        """_summary_"""
        calc_every = (
            settings.locationservice.LOCATION_SERVICE_FORCED_UPDATE * 60
        )  # update every x seconds only
        last_forced_update_time = time.time()  # last time force updated
        max_retries_high_frequency = (
            settings.locationservice.LOCATION_SERVICE_HIGH_FREQ_UPDATE
        )

        while self._running:
            # forced update by time
            if time.time() > (last_forced_update_time + calc_every):
                logger.info("geolocation forced update by time triggered")

                self.update_geolocation()

                # update last time
                last_forced_update_time = time.time()

            # higher frequency retry initial after bootup.
            # if fails still forced update every hour or so above.
            elif (
                self.accuracy is None
                or self.accuracy
                > settings.locationservice.LOCATION_SERVICE_THRESHOLD_ACCURATE
            ) and max_retries_high_frequency > 0:
                logger.info(
                    f"no or inaccurate result, retry {max_retries_high_frequency} times again"
                )

                self.update_geolocation()

                max_retries_high_frequency -= 1

            else:
                pass

            # thread wait otherwise 100% load ;)
            time.sleep(10)

    @property
    def latitude(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        try:
            return self._geolocation_response["location"]["lat"]
        except KeyError:
            return None

    @property
    def longitude(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        try:
            return self._geolocation_response["location"]["lng"]
        except KeyError:
            return None

    @property
    def accuracy(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        try:
            return self._geolocation_response["accuracy"]
        except KeyError:
            return None

    @property
    def latitude_dms(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        try:
            return self._decdeg2dms(self._geolocation_response["location"]["lat"])
        except KeyError:
            return None

    @property
    def longitude_dms(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        try:
            return self._decdeg2dms(self._geolocation_response["location"]["lng"])
        except KeyError:
            return None

    @property
    def latitude_ref(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        if self.latitude is not None:
            return "S" if self.latitude < 0 else "N"
        else:
            return None

    @property
    def longitude_ref(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        if self.longitude is not None:
            return "W" if self.longitude < 0 else "E"
        else:
            return None

    def _decdeg2dms(self, decdeg):
        """_summary_

        Args:
            decdeg (_type_): _description_

        Returns:
            _type_: _description_
        """
        # 52.400561, 9.679484 converts to
        # 52°24'02.0"N 9°40'46.1"E
        is_positive = decdeg >= 0
        decdeg = abs(decdeg)
        minutes, seconds = divmod(decdeg * 3600, 60)
        degrees, minutes = divmod(minutes, 60)
        degrees = degrees if is_positive else -degrees

        return (
            Fraction(degrees).as_integer_ratio(),
            Fraction(minutes).as_integer_ratio(),
            Fraction(seconds).limit_denominator(100000).as_integer_ratio(),
        )

    def request_geolocation(self):
        """_summary_"""
        # use api key to request via nearby wifis
        try:
            results = self._client.geolocate(
                consider_ip=settings.locationservice.LOCATION_SERVICE_CONSIDER_IP,
                wifi_access_points=self._wifi_access_points,
            )

            logger.info(f"geolocation results: {results}")

            self._geolocation_response = results
        except Exception as exc:
            logger.exception(exc)
            logger.error(f"geolocation request failed, error {exc}")

    def gather_wifi(self):
        """_summary_"""
        self._iface.scan()
        # time.sleep(0.5)
        scan_results = self._iface.scan_results()

        wifi_access_points = []
        for scan_result in scan_results:
            wifi_access_points.append(
                {"macAddress": scan_result.bssid, "signalStrength": scan_result.signal}
            )

        logger.debug(wifi_access_points)
        logger.info(f"Found {len(scan_results)} WiFi for geolocation")

        self._wifi_access_points = wifi_access_points

    def update_geolocation(self):
        """_summary_"""
        # gather wifi
        self.gather_wifi()

        # send request
        self.request_geolocation()
