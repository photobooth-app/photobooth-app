import json

from fastapi.openapi.utils import get_openapi

from ..application import app

with open("openapi.json", "w") as file:
    json.dump(
        get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            description=app.description,
            routes=app.routes,
            # openapi_prefix=app.openapi_prefix,
        ),
        file,
    )
