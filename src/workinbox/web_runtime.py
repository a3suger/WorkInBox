from __future__ import annotations

import argparse
import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, RedirectResponse

from .config import AppConfig, load_config
from .main import _configured_log_level
from .sync_process import SyncProcessManager
from .web import create_app as create_base_app


def _remove_post_route(app: FastAPI, path: str) -> None:
    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) == path
            and "POST" in (getattr(route, "methods", None) or set())
        )
    ]


def create_app(
    config: AppConfig,
    *,
    config_path: str | Path = "config.yaml",
    sync_process_manager: SyncProcessManager | None = None,
) -> FastAPI:
    app = create_base_app(config)
    manager = sync_process_manager or SyncProcessManager(config_path)

    # Replace the synchronous routes installed by the base application. Other
    # UI routes remain unchanged.
    _remove_post_route(app, "/sync")
    _remove_post_route(app, "/full-recheck")

    @app.get("/api/sync-status")
    def sync_status() -> dict[str, object]:
        return {
            "running": manager.is_running,
            "pid": manager.pid,
        }

    def start_sync(*, full_recheck: bool) -> RedirectResponse | PlainTextResponse:
        try:
            started = manager.start(full_recheck=full_recheck)
        except OSError as exc:
            logging.exception("Unable to start synchronization process")
            return PlainTextResponse(
                f"同期処理を開始できませんでした: {exc}",
                status_code=500,
            )
        if not started:
            logging.warning("Synchronization request ignored because another sync is running")
        return RedirectResponse(url="/active", status_code=303)

    @app.post("/sync")
    def normal_sync() -> RedirectResponse | PlainTextResponse:
        return start_sync(full_recheck=False)

    @app.post("/full-recheck")
    def full_recheck() -> RedirectResponse | PlainTextResponse:
        return start_sync(full_recheck=True)

    return app


def cli() -> None:
    parser = argparse.ArgumentParser(description="Run the WorkInBox web UI")
    parser.add_argument("--config", default="config.yaml", help="YAML configuration path")
    parser.add_argument("--host", default="127.0.0.1", help="Web server bind address")
    parser.add_argument("--port", type=int, default=8000, help="Web server port")
    args = parser.parse_args()

    logging.basicConfig(
        level=_configured_log_level(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    config = load_config(args.config)
    uvicorn.run(
        create_app(config, config_path=args.config),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    cli()
