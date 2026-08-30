from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Callable
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.templating import Jinja2Templates

from .application import (
    DeadlineService,
    SynchronizationService,
    SyncResult,
    TrackingQueryService,
    WorkTagService,
)
from .config import AppConfig
from .dashboard import DashboardService
from .deadline_application import DeadlineExtractionResult, DeadlineExtractionService
from .deadline_dates import normalize_due_at
from .deadline_ics import DeadlineIcsService
from .deadline_workflow import DeadlineWorkflowService
from .models import DeadlineCreatedBy
from .normal_workflow import NormalWorkflowCompletionService
from .record_store import RecordStore
from .work_tags import WORK_TAGS
from . import __version__


_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))


def _mid_value(message_id: str) -> str:
    value = message_id.strip()
    if value.startswith("<") and value.endswith(">"):
        return value[1:-1]
    return value


_TEMPLATES.env.filters["mid_value"] = _mid_value


def create_app(
    config: AppConfig,
    *,
    synchronization_service: SynchronizationService | None = None,
    query_service: TrackingQueryService | None = None,
    work_tag_service: WorkTagService | None = None,
    deadline_service: DeadlineService | None = None,
    deadline_extraction_service: DeadlineExtractionService | None = None,
    deadline_workflow_service: DeadlineWorkflowService | None = None,
    deadline_ics_service: DeadlineIcsService | None = None,
    normal_workflow_service: NormalWorkflowCompletionService | None = None,
    record_store: RecordStore | None = None,
    dashboard_service: DashboardService | None = None,
) -> FastAPI:
    sync_service = synchronization_service or SynchronizationService(config)
    tracking_service = query_service or TrackingQueryService(config)
    tag_service = work_tag_service or WorkTagService(config)
    deadline_data_service = deadline_service or DeadlineService(config)
    deadline_ai_service = deadline_extraction_service or DeadlineExtractionService(config)
    deadline_flow_service = deadline_workflow_service or DeadlineWorkflowService(
        deadline_data_service,
        tag_service,
    )
    deadline_calendar_service = deadline_ics_service or DeadlineIcsService(deadline_data_service)
    normal_completion_service = normal_workflow_service or NormalWorkflowCompletionService(config)
    records = record_store or RecordStore(config.database.path)
    dashboard = dashboard_service or DashboardService(config, record_store=records)
    sync_lock = Lock()

    app = FastAPI(title="WorkInBox")

    def common_view_flags(
        *,
        dashboard_view: bool = False,
        active: bool = False,
        pending: bool = False,
        deadlines: bool = False,
        schedules: bool = False,
    ) -> dict[str, bool]:
        return {
            "dashboard_view": dashboard_view,
            "active_view": active,
            "pending_view": pending,
            "deadlines_view": deadlines,
            "schedules_view": schedules,
        }

    def render_dashboard(
        request: Request,
        *,
        dashboard_failure: str | None = None,
    ):
        snapshot = None
        if dashboard_failure is None:
            try:
                snapshot = dashboard.snapshot()
            except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
                dashboard_failure = str(exc)
        return _TEMPLATES.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "snapshot": snapshot,
                "dashboard_failure": dashboard_failure,
                **common_view_flags(dashboard_view=True),
            },
        )

    def render_mail_list(
        request: Request,
        *,
        active: bool,
        sync_result: SyncResult | None = None,
        sync_failure: str | None = None,
        tag_message: str | None = None,
        tag_failure: str | None = None,
    ):
        emails = tracking_service.active_emails() if active else tracking_service.inactive_emails()
        tagged_emails = tag_service.read_for_emails(emails)
        return _TEMPLATES.TemplateResponse(
            request=request,
            name="emails.html",
            context={
                "emails": tagged_emails,
                "work_tags": WORK_TAGS,
                **common_view_flags(active=active),
                "sync_result": sync_result,
                "sync_failure": sync_failure,
                "tag_message": tag_message,
                "tag_failure": tag_failure,
            },
        )

    def render_pending(request: Request, *, message: str | None = None, failure: str | None = None):
        return _TEMPLATES.TemplateResponse(
            request=request,
            name="pending.html",
            context={
                "emails": tag_service.pending_emails(),
                **common_view_flags(pending=True),
                "message": message,
                "failure": failure,
            },
        )

    def render_deadlines(
        request: Request,
        *,
        extraction_result: DeadlineExtractionResult | None = None,
        extraction_failure: str | None = None,
        action_message: str | None = None,
        action_failure: str | None = None,
    ):
        items: list[dict[str, object]] = []
        for tagged in tag_service.read_for_emails(tracking_service.active_emails()):
            if tagged.error is not None:
                continue
            keys = {tag.key for tag in tagged.tags}
            if "wib-deadline" not in keys or "wib-deadline-done" in keys:
                continue
            message = deadline_data_service.database.email_message(tagged.email.message_id)
            items.append({
                "email": tagged.email,
                "tags": tagged.tags,
                "body": message.body if message is not None else None,
                "candidates": deadline_data_service.candidates(tagged.email.message_id),
            })
        return _TEMPLATES.TemplateResponse(
            request=request,
            name="deadlines.html",
            context={
                "items": items,
                **common_view_flags(deadlines=True),
                "extraction_result": extraction_result,
                "extraction_failure": extraction_failure,
                "action_message": action_message,
                "action_failure": action_failure,
            },
        )

    def render_deadline_detail(
        request: Request,
        deadline_id: int,
        *,
        action_message: str | None = None,
        action_failure: str | None = None,
    ):
        deadline = deadline_data_service.deadline(deadline_id)
        email = None
        if deadline is not None:
            email = deadline_data_service.database.email_message(
                deadline.source_message_id,
            )
        return _TEMPLATES.TemplateResponse(
            request=request,
            name="deadline_detail.html",
            context={
                "deadline": deadline,
                "email": email,
                "action_message": action_message,
                "action_failure": action_failure,
                **common_view_flags(deadlines=True),
            },
            status_code=404 if deadline is None else 200,
        )

    def render_schedules(
        request: Request,
        *,
        action_message: str | None = None,
        action_failure: str | None = None,
    ):
        items: list[dict[str, object]] = []
        for tagged in tag_service.read_for_emails(tracking_service.active_emails()):
            if tagged.error is not None:
                continue
            keys = {tag.key for tag in tagged.tags}
            if "wib-schedule" not in keys or "wib-schedule-done" in keys:
                continue
            message = deadline_data_service.database.email_message(tagged.email.message_id)
            items.append({
                "email": tagged.email,
                "tags": tagged.tags,
                "body": message.body if message is not None else None,
            })
        return _TEMPLATES.TemplateResponse(
            request=request,
            name="schedules.html",
            context={
                "items": items,
                "supporters": config.schedule_support.supporters,
                "self_cc": config.identity.mailbox_address if config.identity else "",
                **common_view_flags(schedules=True),
                "action_message": action_message,
                "action_failure": action_failure,
            },
        )

    async def read_urlencoded_form(request: Request) -> dict[str, str]:
        body = (await request.body()).decode("utf-8")
        parsed = parse_qs(body, keep_blank_values=True)
        return {key: values[-1] for key, values in parsed.items() if values}

    def run_sync(request: Request, operation: Callable[[], SyncResult]):
        if not sync_lock.acquire(blocking=False):
            logging.warning("Synchronization request ignored because another sync is running")
            return render_mail_list(request, active=True, sync_failure="同期処理は既に実行中です。完了後にもう一度実行してください。")
        try:
            try:
                result = operation()
            except (OSError, RuntimeError, sqlite3.Error) as exc:
                return render_mail_list(request, active=True, sync_failure=str(exc))
            return render_mail_list(request, active=True, sync_result=result)
        finally:
            sync_lock.release()

    @app.get("/")
    def index(request: Request):
        return render_dashboard(request)

    @app.get("/active")
    def active_emails(request: Request):
        return render_mail_list(request, active=True)

    @app.get("/inactive")
    def inactive_emails(request: Request):
        return render_mail_list(request, active=False)

    @app.get("/records")
    def record_list(request: Request):
        return _TEMPLATES.TemplateResponse(
            request=request,
            name="records.html",
            context={"records": records.list(), **common_view_flags()},
        )

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

    @app.get("/schedules")
    def schedule_adjustments(request: Request):
        return render_schedules(request)

    @app.get("/api/thunderbird/imap-target")
    def thunderbird_imap_target() -> dict[str, object]:
        return {
            "host": config.imap.host,
            "port": config.imap.port,
            "username": config.imap.username,
            "mailbox": config.imap.mailbox,
        }

    def database_health() -> tuple[str, str | None]:
        try:
            database_uri = f"{config.database.path.resolve().as_uri()}?mode=ro"
            with sqlite3.connect(database_uri, uri=True) as connection:
                row = connection.execute(
                    "SELECT MAX(synchronized_at) FROM emails"
                ).fetchone()
        except (OSError, sqlite3.Error) as exc:
            logging.warning("WorkInBox health check could not access the database: %s", exc)
            return "unavailable", None
        return "ok", row[0] if row and row[0] else None

    @app.get("/api/health")
    def health() -> dict[str, object]:
        database_status, last_sync_at = database_health()
        return {
            "status": "ok" if database_status == "ok" else "degraded",
            "version": __version__,
            "api_version": 1,
            "database": database_status,
            "last_sync_at": last_sync_at,
        }

    @app.get("/api/extension/bootstrap")
    def extension_bootstrap() -> dict[str, object]:
        return {
            "api_version": 1,
            "version": __version__,
            "new_mail_lookback_days": config.imap.new_mail_lookback_days,
            "imap_target": thunderbird_imap_target(),
        }

    @app.get("/deadlines.ics", response_class=PlainTextResponse)
    def deadline_calendar(request: Request) -> PlainTextResponse:
        try:
            content = deadline_calendar_service.render(
                source_base_url=str(request.base_url),
            )
        except (RuntimeError, ValueError, sqlite3.Error) as exc:
            return PlainTextResponse(str(exc), status_code=500)
        return PlainTextResponse(
            content,
            media_type="text/calendar; charset=utf-8",
            headers={"Content-Disposition": 'inline; filename="deadlines.ics"'},
        )

    @app.get("/deadlines/{deadline_id}/source-message")
    def deadline_source_message(request: Request, deadline_id: int):
        deadline = deadline_data_service.deadline(deadline_id)
        if deadline is None:
            return _TEMPLATES.TemplateResponse(
                request=request,
                name="deadline_source_message.html",
                context={
                    "deadline": None,
                    "email": None,
                    **common_view_flags(deadlines=True),
                },
                status_code=404,
            )
        email = deadline_data_service.database.email_message(
            deadline.source_message_id,
        )
        return _TEMPLATES.TemplateResponse(
            request=request,
            name="deadline_source_message.html",
            context={
                "deadline": deadline,
                "email": email,
                **common_view_flags(deadlines=True),
            },
        )

    @app.get("/deadlines/{deadline_id}")
    def deadline_detail(request: Request, deadline_id: int):
        return render_deadline_detail(request, deadline_id)

    @app.post("/deadlines/{deadline_id}")
    async def revise_registered_deadline(request: Request, deadline_id: int):
        try:
            form = await read_urlencoded_form(request)
            deadline_data_service.revise_deadline(
                deadline_id,
                title=form.get("title", ""),
                due_at=form.get("due_at", ""),
                description=form.get("description", ""),
            )
        except (OSError, RuntimeError, ValueError, sqlite3.Error, UnicodeDecodeError) as exc:
            return render_deadline_detail(
                request,
                deadline_id,
                action_failure=str(exc),
            )
        return render_deadline_detail(
            request,
            deadline_id,
            action_message="締切を更新しました。ThunderbirdのToDoにも次回の再読み込みで反映されます。",
        )

    @app.post("/normal-workflow/complete")
    def complete_normal_workflow(request: Request, message_id: str):
        try:
            normal_completion_service.complete(message_id)
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            return render_mail_list(request, active=True, tag_failure=str(exc))
        return render_mail_list(request, active=True, tag_message="通常ワークフローを終了しました。")

    @app.post("/normal-workflow/record")
    async def record_and_complete_normal_workflow(request: Request):
        try:
            form = await read_urlencoded_form(request)
            normal_completion_service.save_record_and_complete(
                form.get("message_id", "").strip(),
                title=form.get("title", ""),
                summary=form.get("summary", ""),
                note=form.get("note", ""),
            )
        except (OSError, RuntimeError, ValueError, sqlite3.Error, UnicodeDecodeError) as exc:
            return render_mail_list(request, active=True, tag_failure=str(exc))
        return render_mail_list(request, active=True, tag_message="Record に保存して通常ワークフローを終了しました。")

    @app.post("/deadlines/add")
    async def add_deadline_candidate(request: Request):
        try:
            form = await read_urlencoded_form(request)
            message_id = form.get("message_id", "").strip()
            due_value = form.get("due_at", "").strip()
            due_at = normalize_due_at(due_value) if due_value else None
            deadline_data_service.add_candidate(
                message_id,
                form.get("title", ""),
                due_at=due_at,
                source_text=form.get("source_text", "").strip() or None,
                created_by=DeadlineCreatedBy.USER,
                needs_review=due_at is None,
            )
        except (OSError, RuntimeError, ValueError, sqlite3.Error, UnicodeDecodeError) as exc:
            return render_deadlines(request, action_failure=str(exc))
        return render_deadlines(request, action_message="締切候補を手動で追加しました。")

    @app.post("/deadlines/no-deadline")
    def dismiss_no_deadline(request: Request, message_id: str):
        try:
            deadline_flow_service.dismiss_no_deadline(message_id)
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            return render_deadlines(request, action_failure=str(exc))
        return render_deadlines(
            request,
            action_message="締切なしとして締切登録支援を終了しました。",
        )

    @app.post("/deadlines/{candidate_id}/register")
    def register_deadline_candidate(request: Request, candidate_id: int):
        try:
            _, completion = deadline_flow_service.register_candidate(candidate_id)
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            return render_deadlines(request, action_failure=str(exc))
        if completion.completed:
            return render_deadlines(request, action_message="締切を正式登録し、このメールの締切判断を完了しました。")
        return render_deadlines(request, action_message="締切を正式登録しました。")

    @app.post("/deadlines/{candidate_id}/reject")
    def reject_deadline_candidate(request: Request, candidate_id: int):
        try:
            _, completion = deadline_flow_service.reject_candidate(candidate_id)
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            return render_deadlines(request, action_failure=str(exc))
        if completion.completed:
            if completion.registered_count > 0:
                message = "締切候補を登録しないと判断し、このメールの締切判断を完了しました。"
            else:
                message = "すべての締切候補を登録しないと判断し、締切ありタグを外しました。"
            return render_deadlines(request, action_message=message)
        return render_deadlines(request, action_message="締切候補を登録しないと判断しました。")

    @app.post("/deadlines/{candidate_id}/revise")
    async def revise_deadline_candidate(request: Request, candidate_id: int):
        try:
            form = await read_urlencoded_form(request)
            deadline_data_service.revise_candidate(
                candidate_id,
                title=form.get("title", ""),
                due_at=form.get("due_at", "").strip() or None,
                source_text=form.get("source_text", "").strip() or None,
                needs_review="needs_review" in form,
            )
        except (OSError, RuntimeError, ValueError, sqlite3.Error, UnicodeDecodeError) as exc:
            return render_deadlines(request, action_failure=str(exc))
        return render_deadlines(request, action_message="締切候補を修正しました。")

    @app.post("/schedules/complete")
    def complete_schedule_adjustment(request: Request, message_id: str):
        try:
            tag_service.set_tag(message_id, "wib-schedule-done", enabled=True)
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            return render_schedules(request, action_failure=str(exc))
        return render_schedules(request, action_message="スケジュール対応済みとして記録しました。")

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
    def update_tag(request: Request, key: str, operation: str, message_id: str, view: str = "active"):
        active = view != "inactive"
        if operation not in {"add", "remove"}:
            return render_mail_list(request, active=active, tag_failure=f"Unknown tag operation: {operation}")
        try:
            tag_service.set_tag(message_id, key, enabled=operation == "add")
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            return render_mail_list(request, active=active, tag_failure=str(exc))
        return render_mail_list(request, active=active, tag_message="IMAP タグを更新しました。")

    return app


def cli() -> None:
    # Keep the historical module entry point working, but always use the
    # runtime wrapper that runs synchronization in a child process and exposes
    # structured progress through /api/sync-status.
    from .web_runtime import cli as runtime_cli

    runtime_cli()


if __name__ == "__main__":
    cli()
