import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger

from helpers import ClickHouseManager, ConnectionManager, MinifyMiddleware, Monitors, pre_checks, setup_logging
from routes import ApiManager, PageManager, WebsocketManager


class Application:
    def __init__(self):
        load_dotenv()
        if error := pre_checks():
            print(error)
            exit(1)
        self.log = logger
        self.app = FastAPI(lifespan=self._lifespan)
        self.manager = ConnectionManager()
        self.db = ClickHouseManager(
            parent=self,
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT")),
            username=os.getenv("DB_USERNAME"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_DATABASE"),
        )
        self.analytics_url = os.getenv("ANALYTICS_URL", None)
        self.analytics_uuid = os.getenv("ANALYTICS_UUID", None)
        self.templates = Jinja2Templates(directory="templates")
        self.app.mount("/static", StaticFiles(directory="static"), name="static")
        self.api_manager = ApiManager(parent=self)
        self.ws_manager = WebsocketManager(parent=self)
        self.page_manager = PageManager(parent=self)

        self._setup_middlewares()
        self._setup_routes()

    @asynccontextmanager
    async def _lifespan(self, _):
        monitor = Monitors(parent=self)
        await monitor.start()
        setup_logging()
        yield
        await monitor.stop()
        if self.db.client:
            await self.db.client.close()

    def _setup_middlewares(self):
        self.app.add_middleware(MinifyMiddleware)

    def _setup_routes(self):
        self.ws_manager.setup_routes()
        self.api_manager.setup_routes()
        self.page_manager.setup_routes()
        self.app.include_router(self.ws_manager.ws_router)
        self.app.include_router(self.api_manager.api_router)
        self.app.include_router(self.page_manager.pages_router)


server = Application()
app = server.app


if __name__ == "__main__":
    try:
        # uvicorn.run("webserver:app", host="0.0.0.0", port=18000,
        # log_level="info", reload=True, reload_excludes="templates/**")
        uvicorn.run(
            "webserver:app",
            host="0.0.0.0",
            port=int(os.getenv("CONTAINER_PORT", 25000)),
            log_level="info",
            workers=4,
            forwarded_allow_ips="*",
        )
    except Exception as e:
        print(e)
