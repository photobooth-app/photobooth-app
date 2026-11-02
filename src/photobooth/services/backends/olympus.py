import logging
import queue
import threading
import time
from pathlib import Path
from typing import Optional

from olympuswifi.camera import OlympusCamera
from olympuswifi.liveview import LiveViewReceiver

from ..config.groups.cameras import GroupCameraOlympus, Orientation
from .abstractbackend import AbstractBackend

logger = logging.getLogger(__name__)

class OlympusBackend(AbstractBackend):
    def __init__(self, config1: GroupCameraOlympus):
        # On transmet num_subdevices=1 et idle_timeout attendus par AbstractBackend
        num_subdevices: int = 1
        idle_timeout: float = getattr(config1, "idle_timeout", 30.0)
        super().__init__(
            num_subdevices=num_subdevices,
            idle_timeout=idle_timeout,
            orientation="1: 0°", 
        )

        self._config: GroupCameraOlympus = config1
        self._camera: Optional[OlympusCamera] = None
        self._receiver: Optional[LiveViewReceiver] = None
        self._receiver_thread: Optional[threading.Thread] = None
        self._frame_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # -------------------------------------------------------------------------
    # Gestion de la connexion avec tolérance de panne
    # -------------------------------------------------------------------------
    def _connect_camera(self) -> bool:
        """Tente d'établir la connexion avec l'appareil sans lever d'exception bloquante."""
        if self._camera is not None:
            return True

        try:
            logger.info(f"Tentative de détection Olympus sur {self._config.device_ip}...")
            cam = OlympusCamera(server=self._config.device_ip)
            # Teste si la caméra répond effectivement
            cam.get_camera_info()
            self._camera = cam
            logger.info("Appareil Olympus détecté et connecté avec succès.")
            return True
        except Exception as exc:
            logger.warning(
                f"Appareil Olympus non joignable ({self._config.device_ip}) : {exc}. "
                "L'application continue, tentative de reconnexion en arrière-plan."
            )
            self._camera = None
            return False

    # -------------------------------------------------------------------------
    # Cycle de vie et ressources
    # -------------------------------------------------------------------------
    def setup_resource(self):
        """Initialise la mémoire sans faire planter Photobooth si la caméra est éteinte."""
        self._frame_queue = queue.SimpleQueue()
        self._receiver = LiveViewReceiver(self._frame_queue)

        # On tente une première connexion, mais sans bloquer si elle échoue
        self._connect_camera()

    def teardown_resource(self):
        """Nettoie proprement toutes les connexions."""
        if self._receiver:
            try:
                self._receiver.shut_down()
            except Exception as exc:
                logger.debug(f"Erreur arrêt receiver : {exc}")
            self._receiver = None

        if self._camera:
            try:
                self._camera.stop_liveview()
            except Exception as exc:
                logger.debug(f"Erreur coupure liveview : {exc}")
            self._camera = None

    def start(self):
        self._stop_event.clear()
        self.setup_resource()
        self._worker_thread = threading.Thread(
            target=self.run_service,
            name="OlympusBackendWorker",
            daemon=True,
        )
        self._worker_thread.start()
        logger.info("Service OlympusBackend prêt.")

    def stop(self):
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3.0)
        self.teardown_resource()
        logger.info("Service OlympusBackend arrêté.")

    # -------------------------------------------------------------------------
    # Boucle de streaming et reconnexion automatique
    # -------------------------------------------------------------------------
    def run_service(self):
        logger.info("Boucle de surveillance Olympus active.")
        last_reconnect_try = 0.0

        while not self._stop_event.is_set():
            # Si la caméra n'est pas connectée, réessaie toutes les 5 secondes
            if self._camera is None:
                now = time.time()
                if (now - last_reconnect_try) > 5.0:
                    last_reconnect_try = now
                    if self._connect_camera() and self._is_video_mode_requested:
                        # Si le liveview avait déjà été demandé par l'IHM, on le lance
                        self._handle_switchmode_video_mode()
                time.sleep(0.5)
                continue

            try:
                # Lecture des trames UDP LiveView
                frame = self._frame_queue.get(block=True, timeout=0.5)
                jpeg_bytes = frame.jpeg

                if hasattr(self, "_publish_lores_frame"):
                    self._publish_lores_frame(jpeg_bytes)
                elif hasattr(self, "_pub_lores_frame"):
                    self._pub_lores_frame(jpeg_bytes)

            except queue.Empty:
                continue
            except Exception as exc:
                logger.debug(f"Perte temporaire de flux liveview : {exc}")
                time.sleep(0.1)

    # -------------------------------------------------------------------------
    # Transitions de mode
    # -------------------------------------------------------------------------
    def _handle_switchmode_init(self):
        logger.debug("Olympus: transition INIT")

    def _handle_switchmode_standby(self):
        self._is_video_mode_requested = False
        if self._camera:
            try:
                self._camera.stop_liveview()
            except Exception as exc:
                logger.debug(f"Erreur arrêt liveview : {exc}")

    def _handle_switchmode_video_mode(self):
        self._is_video_mode_requested = True
        if self._camera is None:
            if not self._connect_camera():
                return

        try:
            # Démarre le thread de réception UDP s'il n'est pas actif
            if self._receiver and (self._receiver_thread is None or not self._receiver_thread.is_alive()):
                self._receiver_thread = threading.Thread(
                    target=self._receiver.receive_packets,
                    name="OlympusLiveViewUDP",
                    daemon=True,
                )
                self._receiver_thread.start()

            self._camera.start_liveview(port=self._config.liveview_port)
            logger.info("Olympus: flux LiveView démarré.")
        except Exception as exc:
            logger.warning(f"Impossible de démarrer le liveview Olympus : {exc}")
            self._camera = None  # Marque la caméra comme déconnectée pour retenter

    def _handle_switchmode_still_mode(self):
        logger.info("Olympus: préparation déclenchement (still mode)")
        if self._camera:
            try:
                self._camera.stop_liveview()
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Prise de vue
    # -------------------------------------------------------------------------
    def _wait_for_still_file(self) -> Path:
        """Déclenche la capture. Si l'appareil est éteint, lève une erreur gérée par l'IHM."""
        if self._camera is None and not self._connect_camera():
            raise ConnectionError("L'appareil photo Olympus n'est pas joignable (éteint ou Wi-Fi déconnecté).")

        logger.info("Déclenchement de la photo Olympus...")
        try:
            existing_images = self._camera.list_images()
            last_image = existing_images[-1] if existing_images else None

            self._camera.take_picture()

            start_time = time.time()
            new_file = None
            while (time.time() - start_time) < self._config.capture_timeout:
                time.sleep(0.5)
                images = self._camera.list_images()
                if images and images[-1] != last_image:
                    new_file = images[-1]
                    break

            if not new_file:
                raise TimeoutError("Délai dépassé : aucune nouvelle photo trouvée sur l'Olympus.")

            dest_dir = Path("/tmp/photobooth_olympus")
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_file = dest_dir / Path(new_file).name

            logger.info(f"Téléchargement de {new_file} vers {dest_file}...")
            self._camera.download_image(new_file, str(dest_file))
            return dest_file

        except Exception as exc:
            # Marque la caméra déconnectée en cas de coupure brutale (batterie vide, etc.)
            self._camera = None
            raise RuntimeError(f"Erreur durant la capture Olympus : {exc}") from exc