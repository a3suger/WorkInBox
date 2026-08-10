from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Callable

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from .application import (
    DeadlineService,
    SynchronizationService,
    SyncResult,
    TrackingQueryService,
    WorkTagService,
)
from .config import AppConfig, load_config
from .deadline_application import DeadlineExtractionResult, DeadlineExtractionService
from .work_tags import WORK_TAGS


_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))


def create_app(
    config: AppConfig,
    *,
    synchronization_service: SynchronizationService | None = None,
    query_service: TrackingQueryService | None = None,
    work_tag_service: WorkTagService | None = None,
    deadline_service: DeadlineService | None = None,
    deadline_extraction_service: DeadlineExtractionService | None = None,
) -> FastAPI:
    sync_service = synchronization_service or SynchronizationService(config)
    tracking_service = query_service or TrackingQueryService(config)
    tag_service = work_tag_service or WorkTagService(config)
    deadline_data_service = deadline_service or DeadlineService(config)
    deadline_ai_service = deadline_extraction_service or DeadlineExtractionService(config)
    sync_lock = Lock()

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
                "pending_view": False,
                "deadlines_view": False,
                "sync_result": sync_result,
                "sync_failure": sync_failure,
                "tag_message": tag_message,
                "tag_failure": tag_failure,
            },
        )

    def render_pending(
        request: Request,
        *,
        message: str | None = None,
        failure: str | None = None,
    ):
        return _TEMPLATES.TemplateResponse(
            request=request,
            name="pending.html",
            context={
                "emails": tag_service.pending_emails(),
                "active_view": False,
                "pending_view": True,
                "deadlines_view": False,
                "message": message,
                "failure": failure,
            },
        )

    def render_deadlines(
        request: Request,
        *,
        extraction_result: DeadlineExtractionResult | None = None,
        extraction_failure: str | None = None,
    ):
        items: list[dict[str, object]] = []
        for tagged in tag_service.read_for_emails(tracking_service.active_emails()):
            if tagged.error is not None:
                continue
            keys = {tag.key for tag in tagged.tags}
            if "wib-deadline" not in keys or "wib-deadline-done" in keys:
                continue
            message = deadline_data_service.database.email_message(tagged.email.message_id)
            items.append(
                {
                    "email": tagged.email,
                    "tags": tagged.tags,
                    "body": message.body if message is not None else None,
                    "candidates": deadline_data_service.candidates(tagged.email.message_id),
                }
            )
        return _TEMPLATES.TemplateResponse(
            request=request,
            name="deadlines.html",
            context={
                "items": items,
                "active_view": False,
                "pending_view": False,
                "deadlines_view": True,
                "extraction_result": extraction_result,
                "extraction_failure": extraction_failure,
            },
        )

    def run_sync(request: Request, operation: Callable[[], SyncResult]):
        if not sync_lock.acquire(blocking=False):
            logging.warning("Synchronization request ignored because another sync is running")
            return render_mail_list(
                request,
                active=True,
                sync_failure=(
                    "同期処理は既に実行中です。完了後にもう一度実行してください。"
                ),
            )
        try:
            try:
                result = operation()
            except (OSError, RuntimeError, sqlite3.Error) as exc:
                return render_mail_list(
                    request,
                    active=True,
                    sync_failure=str(exc),
                )
            return render_mail_list(request, active=True, sync_result=result)
        finally:
            sync_lock.release()

    @app.get("/")
    def index() -> RedirectResponse:
        return RedirectResponse(url="/active", status_code=303)

    @app.get("/active")
    def active_emails(request: Request):
        return render_mail_list(request, active=True)

    @app.get("/inactive")
    def inactive_emails(request: Request):
        return render_mail_list(request, active=False)

    @app.get("/pending")
    def pending_emails(request: Request):
        return render_pending(request)

    @app.get("/deadlines")
    def deadline_candidates(request: Request):
        try:
            result = deadline_ai_service.extract_pending()
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            return render_deadlines(request, extraction_failure=str(exc))
        return render_deadlines(request, extraction_result=result)

    @app.post("/pending/resolve")
    def resolve_pending(request: Request, message_id: str, resolution: str):
        try:
            tag_service.resolve_pending(message_id, resolution)
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            return render_pending(request, failure=str(exc))
        return render_pending(request, message="判定保留を解消しました。")

    @app.post("/sync")
    def normal_sync(request: Request):
        return run_sync(request, sync_service.normal_sync)

    @app.post("/full-recheck")
    def full_recheck(request: Request):
        return run_sync(request, sync_service.full_recheck)

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
