"""Creator Task OS. ContinuityRuntime remains the composition root."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from content.models import (
    ALLOWED_TASK_TRANSITIONS,
    PRODUCTION_CHAIN,
    TASK_PRIORITIES,
    TASK_TRANSITION_PATHS,
    AccountOperatingState,
    ConfigurationBlocked,
    CreatorTask,
    IsolationError,
    LifecycleTransition,
    utcnow,
)
from content.store import ContinuityStore


OPEN_STATUSES = ("TODO", "READY", "IN_PROGRESS", "WAITING_OPERATOR", "WAITING_EXTERNAL", "BLOCKED")
OPERATOR_TYPES = {"CREATIVE_EXECUTION"}
CORE_PRODUCTION_TYPES = (
    "CONTENT_PLAN",
    "PROMPT_GENERATION",
    "CREATIVE_EXECUTION",
    "ASSET_IMPORT",
    "QA",
    "PACKAGE",
    "HANDOFF",
)


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


def classify_task(task: CreatorTask, *, today: str | None = None) -> str:
    today = today or today_iso()
    if task.status == "BLOCKED":
        return "BLOCKED"
    if task.status == "WAITING_OPERATOR":
        return "WAITING_OPERATOR"
    if task.status == "WAITING_EXTERNAL":
        return "WAITING_EXTERNAL"
    if task.status in {"DONE", "CANCELLED"}:
        return task.status
    due = (task.due_at or "")[:10]
    if due and due < today:
        return "OVERDUE"
    if due and due > today:
        return "UPCOMING"
    return "TODAY"


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
                    linked = self.store.save_task(CreatorTask(**{**parent.__dict__, "next_task_id": saved.task_id, "updated_at": utcnow()}))
                    if created:
                        created[-1] = linked
            created.append(saved)
            parent_id = saved.task_id
        return created

    def transition(
        self,
        task_id: str,
        *,
        to_status: str,
        notes: str = "",
        blocked_reason: str = "",
        reason: str = "",
        operator: str = "operator",
        reopen: bool = False,
    ) -> CreatorTask:
        task = self.store.get_task(task_id)
        if task is None:
            raise IsolationError(f"unknown task: {task_id}")
        if reopen:
            raise ConfigurationBlocked("REOPEN_REQUIRED", "reopen must create a new task, not mutate DONE history")
        allowed = ALLOWED_TASK_TRANSITIONS.get(task.status, frozenset())
        if to_status != task.status and to_status not in allowed:
            raise ConfigurationBlocked(
                "ILLEGAL_TASK_TRANSITION",
                f"{task.status} cannot become {to_status}",
            )
        completed = utcnow() if to_status == "DONE" else None
        saved = self.store.save_task(CreatorTask(**{
            **task.__dict__,
            "status": to_status,
            "operator_notes": notes or task.operator_notes,
            "blocked_reason": blocked_reason if to_status == "BLOCKED" else "",
            "completed_at": completed if to_status == "DONE" else task.completed_at,
            "updated_at": utcnow(),
        }))
        self.store.save_lifecycle(LifecycleTransition(
            transition_id=uuid4().hex,
            episode_id=saved.episode_id or saved.task_id,
            account_id=saved.account_id,
            from_status=task.status,
            to_status=to_status,
            owner="task-os",
            evidence_id=saved.task_id,
            task_id=saved.task_id,
            reason=reason or notes or blocked_reason,
            operator=operator,
        ))
        if to_status == "DONE" and saved.next_task_id:
            nxt = self.store.get_task(saved.next_task_id)
            if nxt is not None and nxt.status == "TODO":
                unlocked = self.transition(nxt.task_id, to_status="READY", reason=f"unlocked by {saved.task_type}", operator=operator)
                if unlocked.task_type in OPERATOR_TYPES:
                    self._move(unlocked.task_id, to_status="WAITING_OPERATOR", reason=f"operator after {saved.task_type}", operator=operator)
        return saved

    def _move(self, task_id: str, *, to_status: str, reason: str = "", operator: str = "operator", notes: str = "", blocked_reason: str = "") -> CreatorTask:
        task = self.store.get_task(task_id)
        if task is None:
            raise IsolationError(f"unknown task: {task_id}")
        if task.status == to_status:
            return task
        hops = TASK_TRANSITION_PATHS.get((task.status, to_status))
        if not hops:
            raise ConfigurationBlocked("ILLEGAL_TASK_TRANSITION", f"{task.status} cannot become {to_status}")
        current = task
        for hop in hops:
            current = self.transition(
                current.task_id,
                to_status=hop,
                reason=reason,
                operator=operator,
                notes=notes,
                blocked_reason=blocked_reason if hop == "BLOCKED" else "",
            )
        return current

    def complete_type(self, *, account_id: str, episode_id: str | None, task_type: str, **fields: Any) -> CreatorTask | None:
        tasks = self.store.list_tasks(account_id=account_id, episode_id=episode_id, open_only=True)
        match = next((item for item in tasks if item.task_type == task_type), None)
        if match is None:
            return None
        payload = {**match.__dict__, **{key: value for key, value in fields.items() if value is not None}, "status": match.status}
        self.store.save_task(CreatorTask(**payload))
        return self._move(match.task_id, to_status="DONE", reason=f"complete {task_type}")

    def waiting_operator(self, *, account_id: str, episode_id: str | None, task_type: str = "CREATIVE_EXECUTION") -> CreatorTask | None:
        tasks = self.store.list_tasks(account_id=account_id, episode_id=episode_id)
        match = next((item for item in tasks if item.task_type == task_type), None)
        if match is None:
            return None
        if match.status == "WAITING_OPERATOR":
            return match
        return self._move(match.task_id, to_status="WAITING_OPERATOR", reason="operator Lechuang")

    def reopen(self, task_id: str, *, reason: str, operator: str = "operator") -> CreatorTask:
        task = self.store.get_task(task_id)
        if task is None:
            raise IsolationError(f"unknown task: {task_id}")
        if task.status not in {"DONE", "CANCELLED"}:
            raise ConfigurationBlocked("REOPEN_NOT_CLOSED", "reopen only applies to DONE or CANCELLED tasks")
        replica = CreatorTask(**{
            **task.__dict__,
            "task_id": uuid4().hex,
            "status": "READY" if task.task_type not in OPERATOR_TYPES else "WAITING_OPERATOR",
            "parent_task_id": task.task_id,
            "operator_notes": f"REOPEN of {task.task_id}: {reason}",
            "blocked_reason": "",
            "completed_at": None,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        })
        saved = self.store.save_task(replica)
        self.store.save_lifecycle(LifecycleTransition(
            transition_id=uuid4().hex,
            episode_id=saved.episode_id or saved.task_id,
            account_id=saved.account_id,
            from_status=task.status,
            to_status=saved.status,
            owner="task-os",
            evidence_id=saved.task_id,
            task_id=saved.task_id,
            reason=f"REOPEN {task.task_id}: {reason}",
            operator=operator,
        ))
        return saved

    def get_today_tasks(self, *, account_id: str | None = None, platform: str | None = None) -> list[CreatorTask]:
        today = today_iso()
        rows = self.store.list_tasks(account_id=account_id, platform=platform, open_only=True)
        today_rows = []
        for item in rows:
            bucket = classify_task(item, today=today)
            if item.status == "TODO":
                continue
            if bucket in {"TODAY", "OVERDUE", "WAITING_OPERATOR"} and item.status in {"READY", "IN_PROGRESS", "WAITING_OPERATOR"}:
                today_rows.append(item)
        return today_rows

    def classify_open_tasks(self, *, account_id: str | None = None, platform: str | None = None) -> dict[str, list[CreatorTask]]:
        today = today_iso()
        rows = self.store.list_tasks(account_id=account_id, platform=platform, open_only=True)
        buckets = {
            "TODAY": [],
            "OVERDUE": [],
            "UPCOMING": [],
            "WAITING_OPERATOR": [],
            "WAITING_EXTERNAL": [],
            "BLOCKED": [],
        }
        for item in rows:
            bucket = classify_task(item, today=today)
            if bucket in buckets:
                buckets[bucket].append(item)
        return buckets

    def get_blocked_tasks(self, *, account_id: str | None = None, platform: str | None = None) -> list[CreatorTask]:
        return [item for item in self.store.list_tasks(account_id=account_id, platform=platform) if item.status == "BLOCKED"]

    def get_next_action(self, *, account_id: str | None = None, platform: str | None = None, episode_id: str | None = None) -> CreatorTask | None:
        rows = self.store.list_tasks(account_id=account_id, platform=platform, episode_id=episode_id, open_only=True)
        today = today_iso()
        ready_core = [
            item for item in rows
            if item.status == "READY" and item.task_type in CORE_PRODUCTION_TYPES
        ]
        waiting = [item for item in rows if item.status == "WAITING_OPERATOR"]
        in_progress = [item for item in rows if item.status == "IN_PROGRESS"]
        overdue = [item for item in rows if classify_task(item, today=today) == "OVERDUE" and item.status != "BLOCKED"]
        ready_chain = [
            item for item in rows
            if item.status == "READY" and item.task_type in PRODUCTION_CHAIN
        ]
        pool = ready_core or waiting or in_progress or overdue or ready_chain
        if not pool:
            return None
        pool.sort(key=lambda item: (
            0 if item.status == "READY" and item.task_type in CORE_PRODUCTION_TYPES else 1,
            0 if item.status == "WAITING_OPERATOR" else 1 if item.status == "IN_PROGRESS" else 2,
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
