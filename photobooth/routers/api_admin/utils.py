import logging

from fastapi import APIRouter

from ...container import container
from ...services.backends.gphoto2 import Gphoto2Backend

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/utils",
    tags=["admin", "utils"],
)


@router.get("/gphoto2config")
def api_get_backend_gphoto2_config():
    """ """
    output = {}
    try:
        import gphoto2 as gp

        container.aquisition_service.stop()

        backend = Gphoto2Backend()
        backend.start()

        output["gphoto2-package-version"] = gp.__version__
        output["libgphoto2-version"] = gp.gp_library_version(gp.GP_VERSION_VERBOSE)
        output["libgphoto2_port"] = gp.gp_port_library_version(gp.GP_VERSION_VERBOSE)

        try:
            summary = str(backend._camera.get_summary())
            config = dict(backend._camera.list_config())
            # for n in range(len(config)):
            #     logger.debug(f"{config.get_name(n)}={config.get_value(n)}")
        except gp.Gphoto2Error as exc:
            raise RuntimeError(f"could not get device information, error {exc}") from exc

        backend.stop()
        container.aquisition_service.start()

        output = {"summary": summary, "config": config}

    except Exception as exc:
        error = f"Error: {exc}"

    return {"status": error, "output": output}
