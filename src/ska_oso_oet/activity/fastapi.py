from os import getenv

from fastapi import APIRouter, FastAPI
from pubsub import pub
from ska_oso_scripting.event import user_topics
KUBE_NAMESPACE = getenv("KUBE_NAMESPACE", "ska-oso-oet")
API_PREFIX = f"/{KUBE_NAMESPACE}/oet/fastapi"

router = APIRouter()


@router.get("/")
async def root():
    pub.sendMessage(
        user_topics.script.announce, msg_src='fastapi worker', msg='fastapi message'
    )

    return {"message": "Hello World"}


def create_app():
    app = FastAPI(openapi_url=f"{API_PREFIX}/openapi.json", docs_url=f"{API_PREFIX}/ui")
    app.include_router(router, prefix=API_PREFIX)
    return app
