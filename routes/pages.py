from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

if TYPE_CHECKING:
    from helpers import ClickHouseManager, ConnectionManager
    from webserver import Application


class PageManager:
    def __init__(self, parent: Application):
        self.parent: Application = parent
        self.manager: ConnectionManager = parent.manager
        self.db: ClickHouseManager = parent.db
        self.templates: Jinja2Templates = parent.templates
        self.pages_router = APIRouter()

    def setup_routes(self):
        self.pages_router.add_api_route("/", self.index, methods=["GET"])
        self.pages_router.add_api_route("/item/{item_id}", self.individual_item, methods=["GET"])
        self.pages_router.add_api_route("/items", self.items_table, methods=["GET"])
        self.pages_router.add_api_route("/alchemy", self.alchemy_table, methods=["GET"])
        self.pages_router.add_api_route("/favicon.ico", self.favicon, methods=["GET"])

    async def index(self, request: Request):
        return self.templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "analytics_url": self.parent.analytics_url,
                "analytics_uuid": self.parent.analytics_uuid,
            },
        )

    async def individual_item(self, request: Request, item_id: str):
        return self.templates.TemplateResponse(
            "item_id.html",
            {
                "request": request,
                "item_id": item_id,
                "analytics_url": self.parent.analytics_url,
                "analytics_uuid": self.parent.analytics_uuid,
            },
        )

    async def items_table(self, request: Request):
        return self.templates.TemplateResponse(
            "items.html",
            {
                "request": request,
                "analytics_url": self.parent.analytics_url,
                "analytics_uuid": self.parent.analytics_uuid,
            },
        )

    async def alchemy_table(self, request: Request):
        return self.templates.TemplateResponse(
            "alchemy.html",
            {
                "request": request,
                "analytics_url": self.parent.analytics_url,
                "analytics_uuid": self.parent.analytics_uuid,
            },
        )

    async def favicon(self, request: Request):
        return self.templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "analytics_url": self.parent.analytics_url,
                "analytics_uuid": self.parent.analytics_uuid,
            },
        )
