"""
The ska_oso_oet.ui package contains code that present the OET interface to the
outside world. In practical terms, this means the OET application's REST
interface
"""
import json
import multiprocessing
import os
from importlib.metadata import version
from typing import Any, Dict, Generator, Optional, Union

import flask
import jsonpickle
import prance
from connexion import App
from fastapi import FastAPI
from flask import Blueprint, current_app, stream_with_context
from pubsub import pub

from ska_oso_oet.activity.ui import activities_router
from ska_oso_oet.fastapi import sse_router
from ska_oso_oet.mptools import MPQueue
from ska_oso_oet.procedure.ui import procedures_router

KUBE_NAMESPACE = os.getenv("KUBE_NAMESPACE", "ska-oso-oet")
OET_MAJOR_VERSION = version("ska-oso-oet").split(".")[0]
# The base path includes the namespace which is known at runtime
# to avoid clashes in deployments, for example in CICD
API_PATH = f"/{KUBE_NAMESPACE}/oet/api/v{OET_MAJOR_VERSION}"



# def create_app(open_api_spec=None):
#     "Returns Flask App using Connexion"
#     if open_api_spec is None:
#         open_api_spec = get_openapi_spec()
#
#     connexion = App(__name__, specification_dir="openapi/")
#     connexion.add_api(
#         open_api_spec,
#         base_path=API_PATH,
#         arguments={"title": "OpenAPI OET"},
#         pythonic_params=True,
#     )
#
#     connexion.app.config.update(msg_src=__name__)
#     # TODO: Due to the limitation of Swagger Open API, we kept the same earlier blueprint approach for Stream API and couldn't include it in the open API spec, we can plan this work when full SSE support is available in OPEN API 3.0 or any latest version.
#     sse = ServerSentEventsBlueprint("sse", __name__)
#     sse.add_url_rule(rule="", endpoint="stream", view_func=sse.stream)
#     connexion.app.register_blueprint(sse, url_prefix=f"{API_PATH}/stream")
#
#     @connexion.app.errorhandler(400)
#     @connexion.app.errorhandler(404)
#     @connexion.app.errorhandler(504)
#     @connexion.app.errorhandler(500)
#     def server_error_response(cause):
#         """
#         Custom error handler for Procedure API.
#         This is overloaded for 400, 404, 500 and 504 and could conceivably be
#         extended for other errors by adding the appropriate errorhander decorator.
#
#         :param cause: root exception for failure (e.g., KeyError)
#         :return: HTTP Response
#         """
#         response = cause.get_response()
#         if isinstance(cause.description, dict):
#             response_data = {
#                 "error": f"{cause.code} {cause.name}",
#                 "type": cause.description["type"],
#                 "Message": cause.description["Message"],
#             }
#         else:
#             response_data = {
#                 "error": f"{cause.code} {cause.name}",
#                 "type": cause.name,
#                 "Message": cause.description,
#             }
#         response.content_type = "application/json"
#         response.data = json.dumps(response_data)
#         return response
#
#     return connexion.app


def create_app():
    app = FastAPI(
        openapi_url=f"{API_PATH}/openapi.json",
        docs_url=f"{API_PATH}/ui",
    )
    app.include_router(activities_router, prefix=API_PATH)
    app.include_router(procedures_router, prefix=API_PATH)
    app.include_router(sse_router, prefix=API_PATH)
    # TODO need CORS middleware, amongst other things
    return app