import functools
import logging
import sys

import minify_html
from fastapi import Request
from fastapi.responses import Response
from loguru import logger
from rcssmin import cssmin
from rjsmin import jsmin
from starlette.middleware.base import BaseHTTPMiddleware


@functools.lru_cache(maxsize=1024)
def get_cached_minified(content, content_type):
    if "text/html" in content_type:
        return minify_html.minify(
            content,
            minify_js=True,
            minify_css=True,
            remove_processing_instructions=True,
            keep_closing_tags=False,
            keep_comments=False,
            keep_html_and_head_opening_tags=False,
        )
    elif "text/css" in content_type:
        return cssmin(content)
    elif "application/javascript" in content_type or "text/javascript" in content_type:
        return jsmin(content)
    return content


class MinifyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        content_type = response.headers.get("Content-Type", "").lower()
        force_refresh = request.headers.get("X-Force-Minify") == "true"

        if all(
            t not in content_type
            for t in (
                "text/html",
                "text/css",
                "application/javascript",
                "text/javascript",
            )
        ):
            return response

        body = b""
        async for chunk in response.body_iterator:  # NOQA
            body += chunk

        try:
            content = body.decode("utf-8")

            if force_refresh:
                minified = get_cached_minified.__wrapped__(content, content_type)
            else:
                minified = get_cached_minified(content, content_type)

            headers = dict(response.headers)
            headers.pop("content-length", None)

            return Response(
                content=minified,
                status_code=response.status_code,
                headers=headers,
                media_type=content_type,
            )

        except Exception:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=content_type,
            )


class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging():
    logger.remove()
    logger.add(
        sys.stdout,
        colorize=True,
    )
    loggers = ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi")
    for logger_name in loggers:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [InterceptHandler()]

    logging.getLogger("uvicorn").propagate = False
