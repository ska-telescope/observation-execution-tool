from os import getenv

from fastapi import APIRouter, FastAPI

KUBE_NAMESPACE = getenv("KUBE_NAMESPACE", "ska-oso-oet")
API_PREFIX = f"/{KUBE_NAMESPACE}/oet/fastapi"

router = APIRouter()


@router.get("/")
async def root():
    return {"message": "Hello World"}


def create_app():
    app = FastAPI(openapi_url=f"{API_PREFIX}/openapi.json", docs_url=f"{API_PREFIX}/ui")
    app.include_router(router, prefix=API_PREFIX)
    return app
