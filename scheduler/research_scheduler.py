"""Deterministic local scheduler, with no hidden background loop."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from scheduler.tasks import DEFAULT_TASKS, ScheduledTask
from storage.repositories import IntelligenceRepository

TaskHandler = Callable[[Mapping[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True)
class SchedulerRunResult:
    task_name: str
    status: str
    reason_codes: tuple[str, ...]
    payload: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_name": self.task_name,
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "payload": dict(self.payload),
            "can_execute_trades": False,
        }


class ResearchScheduler:
    def __init__(
        self,
        *,
        repository: IntelligenceRepository | None = None,
        tasks: Sequence[ScheduledTask] = DEFAULT_TASKS,
        handlers: Mapping[str, TaskHandler] | None = None,
    ) -> None:
        self.repository = repository
        self.tasks = tuple(tasks)
        self.handlers = dict(handlers or {})

    def due_tasks(
        self,
        *,
        now: datetime,
        last_runs: Mapping[str, datetime | None],
    ) -> tuple[ScheduledTask, ...]:
        return tuple(task for task in self.tasks if task.is_due(now=now, last_run_at=last_runs.get(task.name)))

    def run_due_tasks(
        self,
        *,
        now: datetime,
        context: Mapping[str, Any],
        last_runs: Mapping[str, datetime | None] | None = None,
    ) -> tuple[SchedulerRunResult, ...]:
        results: list[SchedulerRunResult] = []
        for task in self.due_tasks(now=now, last_runs=last_runs or {}):
            handler = self.handlers.get(task.name)
            if handler is None:
                result = SchedulerRunResult(
                    task.name,
                    "SKIPPED",
                    ("TASK_HANDLER_NOT_CONFIGURED",),
                    {"task_name": task.name},
                )
            else:
                try:
                    payload = dict(handler(context))
                except Exception:
                    result = SchedulerRunResult(
                        task.name,
                        "FAILED",
                        ("TASK_HANDLER_FAILED",),
                        {"task_name": task.name},
                    )
                else:
                    result = SchedulerRunResult(
                        task.name,
                        str(payload.get("status", "OK")),
                        tuple(payload.get("reason_codes", ("TASK_COMPLETED",))),
                        payload,
                    )
            if self.repository is not None:
                self.repository.record_scheduler_run(
                    task_name=task.name,
                    due_at=now,
                    status=result.status,
                    reason_codes=result.reason_codes,
                    payload=result.to_dict(),
                    recorded_at=now,
                )
            results.append(result)
        return tuple(results)
