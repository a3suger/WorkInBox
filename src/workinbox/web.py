from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from .application import (
    SynchronizationService,
    SyncResult,
    TrackingQueryService,
    WorkTagService,
)
from .config import AppConfig, load_config
from .work_tags import WORK_TAGS


_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))


def create_app(
    config: AppConfig,
    *,
    synchronization_service: SynchronizationService | None = None,
    query_service: TrackingQueryService | None = None,
    work_tag_service: WorkTagService | None = None,
) -> FastAPI:
    sync_service = synchronization_service or SynchronizationService(config)
    tracking_service = query_service or TrackingQueryService(config)
    tag_service = work_tag_service or WorkTagService(config)

    app = FastAPI(title="WorkInBox")

    def render_mail_list(
        request: Request,
        *,
        active: bool,
        sync_result: SyncResult | None = None,
        sync_failure: str | None = None,
        tag_message: str | None = None,
        tag_failure: str | None = None,
    ):
        emails = (
            tracking_service.active_emails()
            if active
            else tracking_service.inactive_emails()
        )
        tagged_emails = tag_service.read_for_emails(emails)
        return _TEMPLATES.TemplateResponse(
            request=request,
            name="emails.html",
            context={
                "emails": tagged_emails,
                "work_tags": WORK_TAGS,
                "active_view": active,
                "sync_result": sync_result,
                "sync_failure": sync_failure,
                "tag_message": tag_message,
                "tag_failure": tag_failure,
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

    @app.post("/tags/{key}/{operation}")
    def update_tag(
        request: Request,
        key: str,
        operation: str,
        message_id: str,
        view: str = "active",
    ):
        active = view != "inactive"
        if operation not in {"add", "remove"}:
            return render_mail_list(
                request,
                active=active,
                tag_failure=f"Unknown tag operation: {operation}",
            )
        try:
            tag_service.set_tag(
                message_id,
                key,
                enabled=operation == "add",
            )
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            return render_mail_list(
                request,
                active=active,
                tag_failure=str(exc),
            )
        return render_mail_list(
            request,
            active=active,
            tag_message="IMAP タグを更新しました。",
        )

    return app


def cli() -> None:
    parser = argparse.ArgumentParser(description="Run the WorkInBox web UI")
    parser.add_argument("--config", default="config.yaml", help="YAML configuration path")
    parser.add_argument("--host", default="127.0.0.1", help="Web server bind address")
    parser.add_argument("--port", type=int, default=8000, help="Web server port")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = load_config(args.config)
    uvicorn.run(create_app(config), host=args.host, port=args.port)


if __name__ == "__main__":
    cli()
