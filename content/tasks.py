"""Creator Task OS. ContinuityRuntime remains the composition root."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from content.models import (
    PRODUCTION_CHAIN,
    TASK_PRIORITIES,
    AccountOperatingState,
    CreatorTask,
    IsolationError,
    utcnow,
)
from content.store import ContinuityStore


OPEN_STATUSES = ("TODO", "READY", "IN_PROGRESS", "WAITING_OPERATOR", "WAITING_EXTERNAL", "BLOCKED")
OPERATOR_TYPES = {"CREATIVE_EXECUTION"}


def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def due_iso(days: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()


def next_type(task_type: str) -> str | None:
    if task_type not in PRODUCTION_CHAIN:
        return None
    index = PRODUCTION_CHAIN.index(task_type)
    if index + 1 >= len(PRODUCTION_CHAIN):
        return None
    return PRODUCTION_CHAIN[index + 1]


def _priority_rank(priority: str) -> int:
    return TASK_PRIORITIES.index(priority) if priority in TASK_PRIORITIES else 9


class TaskOS:
    def __init__(self, store: ContinuityStore) -> None:
        self.store = store

    def create_production_chain(
        self,
        *,
        account_id: str,
        platform: str,
        title: str,
        description: str = "",
        episode_id: str | None = None,
        series_id: str | None = None,
        due_at: str | None = None,
        priority: str = "HIGH",
        production_run_id: str | None = None,
    ) -> list[CreatorTask]:
        account = self.store.get_account(account_id)
        if account is None:
            raise IsolationError(f"unknown platform account: {account_id}")
        if account.platform != platform:
            raise IsolationError(f"account {account_id} is {account.platform}, not {platform}")
        existing = [
            item for item in self.store.list_tasks(account_id=account_id, episode_id=episode_id, open_only=True)
            if item.task_type in PRODUCTION_CHAIN and episode_id and item.episode_id == episode_id
        ]
        if existing:
            return self.store.list_tasks(account_id=account_id, episode_id=episode_id)
        due = due_at or due_iso(0)
        created: list[CreatorTask] = []
        parent_id = None
        for index, task_type in enumerate(PRODUCTION_CHAIN):
            task = CreatorTask(
                task_id=uuid4().hex,
                account_id=account_id,
                platform=platform,
                task_type=task_type,
                title=f"{task_type}: {title}"[:120],
                description=description or title,
                priority=priority if index <= 2 else "NORMAL",
                status="READY" if index == 0 else "TODO",
                due_at=due,
                episode_id=episode_id,
                series_id=series_id,
                production_run_id=production_run_id,
                parent_task_id=parent_id,
                next_task_type=next_type(task_type),
                dependencies=() if parent_id is None else (parent_id,),
            )
            saved = self.store.save_task(task)
            if parent_id:
                parent = self.store.get_task(parent_id)
                if parent is not None:
                    self.store.save_task(CreatorTask(**{**parent.__dict__, "next_task_id": saved.task_id, "updated_at": utcnow()}))
            created.append(saved)
            parent_id = saved.task_id
        return created

    def transition(self, task_id: str, *, to_status: str, notes: str = "", blocked_reason: str = "") -> CreatorTask:
        task = self.store.get_task(task_id)
        if task is None:
            raise IsolationError(f"unknown task: {task_id}")
        completed = utcnow() if to_status == "DONE" else None
        saved = self.store.save_task(CreatorTask(**{
            **task.__dict__,
            "status": to_status,
            "operator_notes": notes or task.operator_notes,
            "blocked_reason": blocked_reason if to_status == "BLOCKED" else "",
            "completed_at": completed if to_status == "DONE" else task.completed_at,
            "updated_at": utcnow(),
        }))
        if to_status == "DONE" and saved.next_task_id:
            nxt = self.store.get_task(saved.next_task_id)
            if nxt is not None and nxt.status == "TODO":
                ready_status = "WAITING_OPERATOR" if nxt.task_type in OPERATOR_TYPES else "READY"
                self.store.save_task(CreatorTask(**{**nxt.__dict__, "status": ready_status, "updated_at": utcnow()}))
        return saved

    def complete_type(self, *, account_id: str, episode_id: str | None, task_type: str, **fields: Any) -> CreatorTask | None:
        tasks = self.store.list_tasks(account_id=account_id, episode_id=episode_id, open_only=True)
        match = next((item for item in tasks if item.task_type == task_type), None)
        if match is None:
            return None
        payload = {**match.__dict__, **{key: value for key, value in fields.items() if value is not None}}
        self.store.save_task(CreatorTask(**payload))
        return self.transition(match.task_id, to_status="DONE")

    def waiting_operator(self, *, account_id: str, episode_id: str | None, task_type: str = "CREATIVE_EXECUTION") -> CreatorTask | None:
        tasks = self.store.list_tasks(account_id=account_id, episode_id=episode_id)
        match = next((item for item in tasks if item.task_type == task_type), None)
        if match is None:
            return None
        return self.transition(match.task_id, to_status="WAITING_OPERATOR")

    def get_today_tasks(self, *, account_id: str | None = None, platform: str | None = None) -> list[CreatorTask]:
        today = today_iso()
        rows = self.store.list_tasks(account_id=account_id, platform=platform, open_only=True)
        return [item for item in rows if not item.due_at or item.due_at <= today or item.status in OPEN_STATUSES]

    def get_blocked_tasks(self, *, account_id: str | None = None, platform: str | None = None) -> list[CreatorTask]:
        return [item for item in self.store.list_tasks(account_id=account_id, platform=platform) if item.status == "BLOCKED"]

    def get_next_action(self, *, account_id: str | None = None, platform: str | None = None) -> CreatorTask | None:
        rows = self.store.list_tasks(account_id=account_id, platform=platform, open_only=True)
        actionable = [item for item in rows if item.status in {"READY", "IN_PROGRESS", "WAITING_OPERATOR", "WAITING_EXTERNAL"}]
        overdue = [item for item in rows if item.due_at and item.due_at < today_iso() and item.status in OPEN_STATUSES]
        pool = overdue or actionable or rows
        if not pool:
            return None
        pool.sort(key=lambda item: (
            0 if item.status == "WAITING_OPERATOR" else 1 if item.status in {"READY", "IN_PROGRESS"} else 2,
            _priority_rank(item.priority),
            item.due_at or "9999",
        ))
        return pool[0]


def sync_operating_state(
    store: ContinuityStore,
    *,
    account_id: str,
    platform: str,
    **fields: Any,
) -> AccountOperatingState:
    current = store.get_operating_state(account_id)
    if current is None:
        current = AccountOperatingState(account_id=account_id, platform=platform)
    payload = {**current.__dict__, **{key: value for key, value in fields.items() if value is not None}, "updated_at": utcnow()}
    return store.save_operating_state(AccountOperatingState(**payload))
