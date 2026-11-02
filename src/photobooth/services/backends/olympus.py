import logging
import queue
import threading
import time
from pathlib import Path
from typing import Optional

from olympuswifi.camera import OlympusCamera
from olympuswifi.liveview import LiveViewReceiver
from pydantic import BaseModel, Field

from ..config.groups.cameras import GroupCameraOlympus
from .abstractbackend import AbstractBackend

logger = logging.getLogger(__name__)



class OlympusBackend(AbstractBackend):
    def __init__(self, config: GroupCameraOlympus):
        super().__init__(config)
        self._config: GroupCameraOlympus = config
        self._camera: Optional[OlympusCamera] = None
        self._receiver: Optional[LiveViewReceiver] = None
        self._receiver_thread: Optional[threading.Thread] = None
        self._frame_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._run_flag: bool = False

    def _device_connect(self):
        """Initialise la communication avec l'appareil."""
        logger.info(f"Connexion à l'appareil Olympus sur {self._config.device_ip}...")
        try:
            self._camera = OlympusCamera(server=self._config.device_ip)
            # Met l'appareil en mode télécommande (rec/standalone) si nécessaire
            model_info = self._camera.get_camera_info()
            logger.info(f"Appareil Olympus connecté : {model_info}")
        except Exception as exc:
            logger.critical(f"Impossible de joindre l'appareil Olympus : {exc}")
            raise ConnectionError(f"Échec de connexion Olympus : {exc}") from exc

    def _device_disconnect(self):
        """Arrête la prévisualisation et ferme la connexion."""
        self._run_flag = False
        if self._camera:
            try:
                self._camera.stop_liveview()
            except Exception as exc:
                logger.debug(f"Erreur lors de l'arrêt du liveview: {exc}")
            self._camera = None

    def _device_start(self):
        """Démarre le flux vidéo temps réel (RTP over UDP)."""
        if not self._camera:
            self._device_connect()

        self._run_flag = True
        self._frame_queue = queue.SimpleQueue()

        # Démarrage du récepteur RTP LiveView
        self._receiver = LiveViewReceiver(self._frame_queue, port=self._config.liveview_port)
        self._receiver_thread = threading.Thread(
            target=self._receiver.receive_packets,
            daemon=True,
            name="OlympusLiveViewReceiver",
        )
        self._receiver_thread.start()

        # Commande à l'appareil d'envoyer le flux vers notre port UDP
        self._camera.start_liveview(port=self._config.liveview_port)
        logger.info(f"Liveview Olympus démarré sur le port UDP {self._config.liveview_port}")

    def _device_stop(self):
        """Arrête le worker de réception vidéo."""
        self._run_flag = False
        if self._receiver:
            self._receiver.shut_down()
        if self._receiver_thread and self._receiver_thread.is_alive():
            self._receiver_thread.join(timeout=2.0)
        self._device_disconnect()

    def _wait_for_lores_frame(self) -> bytes:
        """
        Appelé en boucle par le service d'acquisition pour alimenter le stream MJPEG
        de l'interface web.
        """
        try:
            # Récupère l'image JPEG la plus récente de la file
            # Timeout court pour ne pas bloquer le thread si des paquets sont perdus
            frame_item = self._frame_queue.get(block=True, timeout=1.0)
            # L'objet retourné par LiveViewReceiver contient l'attribut .jpeg (bytes JPEG)
            return frame_item.jpeg
        except queue.Empty:
            raise TimeoutError("Délai dépassé lors de l'attente d'une frame LiveView Olympus.")

    def _wait_for_still_file(self) -> Path:
        """
        Déclenche la prise de vue, télécharge l'image haute définition
        et renvoie le chemin vers le fichier local.
        """
        if not self._camera:
            raise RuntimeError("L'appareil Olympus n'est pas initialisé.")

        logger.info("Déclenchement de la prise de vue sur l'appareil Olympus...")

        # 1. Lister les photos existantes pour identifier le nouveau fichier
        existing_images = self._camera.list_images()
        last_known_image = existing_images[-1] if existing_images else None

        # 2. Prendre la photo
        self._camera.take_picture()

        # 3. Attendre l'apparition du nouveau fichier sur la carte SD
        start_time = time.time()
        new_image_name = None

        while (time.time() - start_time) < self._config.capture_timeout:
            time.sleep(0.5)
            updated_images = self._camera.list_images()
            if updated_images and updated_images[-1] != last_known_image:
                new_image_name = updated_images[-1]
                break

        if not new_image_name:
            raise TimeoutError("L'appareil Olympus n'a pas enregistré de nouvelle image dans le temps imparti.")

        # 4. Télécharger l'image dans le dossier temporaire du photobooth
        tmp_target_dir = Path("/tmp/photobooth_olympus")
        tmp_target_dir.mkdir(parents=True, exist_ok=True)
        local_filepath = tmp_target_dir / Path(new_image_name).name

        logger.info(f"Téléchargement de {new_image_name} vers {local_filepath}...")
        self._camera.download_image(new_image_name, str(local_filepath))

        return local_filepath