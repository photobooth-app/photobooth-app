"""
Gphoto2 backend implementation

"""
from threading import Condition
import time
import dataclasses
import logging
from pymitter import EventEmitter

try:
    import gphoto2 as gp
except ImportError as import_exc:
    raise OSError("gphoto2 not supported on windows platform") from import_exc
from turbojpeg import TurboJPEG
from src.configsettings import settings, EnumFocuserModule
from src.stoppablethread import StoppableThread
from src.imageserverabstract import ImageServerAbstract, BackendStats


logger = logging.getLogger(__name__)
turbojpeg = TurboJPEG()


class ImageServerGphoto2(ImageServerAbstract):
    """
    The backend implementation using picam2
    """

    @dataclasses.dataclass
    class Gphoto2DataBytes:
        """
        bundle data bytes and it's condition.
        1) save some instance attributes and
        2) bundle as it makes sense
        """

        data: bytes = None
        condition: Condition = None

    def __init__(self, evtbus: EventEmitter, enableStream):
        super().__init__(evtbus, enableStream)
        # public props (defined in abstract class also)
        self.exif_make = "Photobooth Gphoto2 Integration"
        self.exif_model = "Custom"
        self.metadata = {}

        # private props
        self._camera = gp.Camera()
        self._camera_context = gp.Context()
        self._evtbus = evtbus

        self._hires_data: ImageServerGphoto2.Gphoto2DataBytes = (
            ImageServerGphoto2.Gphoto2DataBytes(data=None, condition=Condition())
        )

        self._lores_data: ImageServerGphoto2.Gphoto2DataBytes = (
            ImageServerGphoto2.Gphoto2DataBytes(data=None, condition=Condition())
        )

        self._trigger_hq_capture = False
        self._currentmode = None
        self._lastmode = None
        self._count = 0
        self._fps = 0

        # worker threads
        self._generate_images_thread = StoppableThread(
            name="_generateImagesThread", target=self._generate_images_fun, daemon=True
        )
        self._stats_thread = StoppableThread(
            name="_statsThread", target=self._stats_fun, daemon=True
        )

        # config HQ mode (used for picture capture and live preview on countdown)
        self._capture_config = {}

        # config preview mode (used for permanent live view)
        self._preview_config = {}

        # activate preview mode on init
        ##self._on_preview_mode()
        ##self._camera.configure(self._currentmode)

        logger.info(f"python-gphoto2: {gp.__version__}")
        logger.info(f"libgphoto2: {gp.gp_library_version(gp.GP_VERSION_VERBOSE)}")
        logger.info(
            f"libgphoto2_port: {gp.gp_port_library_version(gp.GP_VERSION_VERBOSE)}"
        )

    def start(self):
        """To start the FrameServer, you will also need to start the Picamera2 object."""
        # start camera
        ##self._camera.start()

        self._generate_images_thread.start()
        self._stats_thread.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        """To stop the FrameServer, first stop any client threads (that might be
        blocked in wait_for_frame), then call this stop method. Don't stop the
        Picamera2 object until the FrameServer has been stopped."""

        self._generate_images_thread.stop()
        self._stats_thread.stop()

        self._generate_images_thread.join(1)
        self._stats_thread.join(1)

        ##self._camera.stop()

        logger.debug(f"{self.__module__} stopped")

    def wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""
        with self._hires_data.condition:
            while True:
                if not self._hires_data.condition.wait(5):
                    raise RuntimeError("timeout receiving frames")

                return self._hires_data.data

    def trigger_hq_capture(self):
        self._trigger_hq_capture = True

    def stats(self) -> BackendStats:
        return BackendStats(
            backend_name=__name__,
            fps=int(round(self._fps, 0)),
        )

    #
    # INTERNAL FUNCTIONS
    #

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""
        with self._lores_data.condition:
            while True:
                if not self._lores_data.condition.wait(5):
                    raise RuntimeError("timeout receiving frames")
                return self._lores_data.data

    def _wait_for_lores_frame(self):
        """function not existant"""
        raise NotImplementedError

    def _on_capture_mode(self):
        # nothing to do for this backend
        pass

    def _on_preview_mode(self):
        # nothing to do for this backend
        pass

    def _gp_set_config(self, name, val):
        config = self._camera.get_config(self._camera_context)
        node = config.get_child_by_name(name)
        node.set_value(val)
        self._camera.set_config(config, self._camera_context)

    def _viewfinder(self, val=0):
        self._gp_set_config("viewfinder", val)

    #
    # INTERNAL IMAGE GENERATOR
    #

    def _stats_fun(self):
        # FPS = 1 / time to process loop
        last_calc_time = time.time()  # start time of the loop

        # to calc frames per second every second
        while not self._stats_thread.stopped():
            self._fps = round(
                float(self._count) / (time.time() - last_calc_time),
                1,
            )

            # reset
            self._count = 0
            last_calc_time = time.time()

            # thread wait
            time.sleep(0.2)

    def _generate_images_fun(self):
        while not self._generate_images_thread.stopped():  # repeat until stopped
            if not self._trigger_hq_capture:
                capture = self._camera.capture_preview()
                img_bytes = memoryview(capture.get_data_and_size()).tobytes()

                with self._lores_data.condition:
                    self._lores_data.data = img_bytes
                    self._lores_data.condition.notify_all()
            else:
                # only capture one pic and return to lores streaming afterwards
                self._trigger_hq_capture = False

                # disable viewfinder; allows camera to autofocus fast in native mode not contrast mode
                self._viewfinder(0)

                logger.info("taking hq picture")

                self._evtbus.emit("frameserver/onCapture")

                # capture hq picture
                file_path = self._camera.capture(gp.GP_CAPTURE_IMAGE)
                # refresh images on camera
                self._camera.wait_for_event(1000)
                logger.info(
                    "Camera file path: {0}/{1}".format(file_path.folder, file_path.name)
                )
                camera_file = gp.check_result(
                    gp.gp_camera_file_get(
                        self._camera,
                        file_path.folder,
                        file_path.name,
                        gp.GP_FILE_TYPE_NORMAL,
                    )
                )
                file_data = gp.check_result(gp.gp_file_get_data_and_size(camera_file))
                img_bytes = memoryview(file_data).tobytes()

                ##logger.info(self.metadata)

                self._evtbus.emit("frameserver/onCaptureFinished")

                with self._hires_data.condition:
                    self._hires_data.data = img_bytes

                    self._hires_data.condition.notify_all()

            self._count += 1
