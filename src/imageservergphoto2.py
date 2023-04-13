"""
Gphoto2 backend implementation

"""
from threading import Condition, Event
import time
import dataclasses
import logging
from pymitter import EventEmitter

try:
    import gphoto2 as gp
except ImportError as import_exc:
    raise OSError("gphoto2 not supported on windows platform") from import_exc
from turbojpeg import TurboJPEG
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

        # jpeg data as bytes
        data: bytes = None
        # signal to producer that requesting thread is ready to be notified
        request_ready: Event = None
        # condition when frame is avail
        condition: Condition = None

    def __init__(self, evtbus: EventEmitter, enableStream):
        super().__init__(evtbus, enableStream)
        # public props (defined in abstract class also)
        self.metadata = {}

        # private props
        self._camera = gp.Camera()
        self._camera_context = gp.Context()
        self._evtbus = evtbus

        self._hires_data: ImageServerGphoto2.Gphoto2DataBytes = (
            ImageServerGphoto2.Gphoto2DataBytes(
                data=None, request_ready=Event(), condition=Condition()
            )
        )

        self._lores_data: ImageServerGphoto2.Gphoto2DataBytes = (
            ImageServerGphoto2.Gphoto2DataBytes(data=None, condition=Condition())
        )

        self._camera_connected = False
        self._count = 0
        self._fps = 0

        # worker threads
        self._generate_images_thread = StoppableThread(
            name="_generateImagesThread", target=self._generate_images_fun, daemon=True
        )
        self._stats_thread = StoppableThread(
            name="_statsThread", target=self._stats_fun, daemon=True
        )

        logger.info(f"python-gphoto2: {gp.__version__}")
        logger.info(f"libgphoto2: {gp.gp_library_version(gp.GP_VERSION_VERBOSE)}")
        logger.info(
            f"libgphoto2_port: {gp.gp_port_library_version(gp.GP_VERSION_VERBOSE)}"
        )
        self._gp_list_cameras()

    def start(self):
        """To start the FrameServer, you will also need to start the Picamera2 object."""
        # start camera
        try:
            self._camera.init()
        except gp.GPhoto2Error as exc:
            logger.critical("camera failed to initialize. no power? no connection?")
            logger.exception(exc)
        else:
            self._camera_connected = True
            logger.debug(f"{self.__module__} started")

        self._generate_images_thread.start()
        self._stats_thread.start()

    def stop(self):
        """To stop the FrameServer, first stop any client threads (that might be
        blocked in wait_for_frame), then call this stop method. Don't stop the
        Picamera2 object until the FrameServer has been stopped."""

        self._generate_images_thread.stop()
        self._stats_thread.stop()

        self._generate_images_thread.join(1)
        self._stats_thread.join(1)

        self._camera.exit()

        logger.debug(f"{self.__module__} stopped")

    def wait_for_hq_image(self):
        """
        for other threads to receive a hq JPEG image
        mode switches are handled internally automatically, no separate trigger necessary
        this function blocks until frame is received
        raise TimeoutError if no frame was received
        """
        with self._hires_data.condition:
            self._hires_data.request_ready.set()

            if not self._hires_data.condition.wait(timeout=4):
                raise TimeoutError("timeout receiving frames")

        self._hires_data.request_ready.clear()
        return self._hires_data.data

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
        if self._generate_images_thread.stopped():
            raise RuntimeError("shutdown already in progress, abort early")

        with self._lores_data.condition:
            if not self._lores_data.condition.wait(timeout=4):
                raise TimeoutError("timeout receiving frames")
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

    def _gp_list_cameras(self):
        camera_list = gp.Camera.autodetect()
        if len(camera_list) == 0:
            logger.error("autodetect camera failed! check camera!")
            return

        for index, (name, addr) in enumerate(camera_list):
            logger.info(f"{index}:  {addr}  {name}")

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
            if not self._hires_data.request_ready.is_set():
                if self._enable_stream:
                    capture = self._camera.capture_preview()
                    img_bytes = memoryview(capture.get_data_and_size()).tobytes()

                    with self._lores_data.condition:
                        self._lores_data.data = img_bytes
                        self._lores_data.condition.notify_all()
                else:
                    time.sleep(0.1)
            else:
                # only capture one pic and return to lores streaming afterwards
                self._hires_data.request_ready.clear()

                # disable viewfinder;
                # allows camera to autofocus fast in native mode not contrast mode
                self._viewfinder(0)

                logger.info("taking hq picture")

                self._evtbus.emit("frameserver/onCapture")

                # capture hq picture
                file_path = self._camera.capture(gp.GP_CAPTURE_IMAGE)
                # refresh images on camera
                self._camera.wait_for_event(1000)
                logger.info(f"Camera file path: {file_path.folder}/{file_path.name}")
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
