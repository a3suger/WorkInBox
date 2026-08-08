from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from .application import SynchronizationService, SyncResult, TrackingQueryService
from .config import AppConfig, load_config


_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))


def create_app(
    config: AppConfig,
    *,
    synchronization_service: SynchronizationService | None = None,
    query_service: TrackingQueryService | None = None,
) -> FastAPI:
    sync_service = synchronization_service or SynchronizationService(config)
    tracking_service = query_service or TrackingQueryService(config)

    app = FastAPI(title="WorkInBox")

    def render_mail_list(
        request: Request,
        *,
        active: bool,
        sync_result: SyncResult | None = None,
        sync_failure: str | None = None,
    ):
        emails = (
            tracking_service.active_emails()
            if active
            else tracking_service.inactive_emails()
        )
        return _TEMPLATES.TemplateResponse(
            request=request,
            name="emails.html",
            context={
                "emails": emails,
                "active_view": active,
                "sync_result": sync_result,
                "sync_failure": sync_failure,
            },
        )

    @app.get("/")
    def index() -> RedirectResponse:
        return RedirectResponse(url="/active", status_code=303)

    @app.get("/active")
    def active_emails(request: Request):
        return render_mail_list(request, active=True)

    @app.get("/inactive")
    def inactive_emails(request: Request):
        return render_mail_list(request, active=False)

    @app.post("/sync")
    def normal_sync(request: Request):
        try:
            result = sync_service.normal_sync()
        except (OSError, RuntimeError, sqlite3.Error) as exc:
            return render_mail_list(
                request,
                active=True,
                sync_failure=str(exc),
            )
        return render_mail_list(request, active=True, sync_result=result)

    @app.post("/full-recheck")
    def full_recheck(request: Request):
        try:
            result = sync_service.full_recheck()
        except (OSError, RuntimeError, sqlite3.Error) as exc:
            return render_mail_list(
                request,
                active=True,
                sync_failure=str(exc),
            )
        return render_mail_list(request, active=True, sync_result=result)

    return app


def cli() -> None:
    parser = argparse.ArgumentParser(description="Run the WorkInBox web UI")
    parser.add_argument("--config", default="config.yaml", help="YAML configuration path")
    parser.add_argument("--host", default="127.0.0.1", help="Web server bind address")
    parser.add_argument("--port", type=int, default=8000, help="Web server port")
    args = parser.parse_args()

    config = load_config(args.config)
    uvicorn.run(create_app(config), host=args.host, port=args.port)


if __name__ == "__main__":
    cli()
