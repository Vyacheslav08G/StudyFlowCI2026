"""Validate tasks and allocate study time by deadline and priority."""

import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

FIELDS = ('id', 'subject', 'title', 'deadline', 'minutes', 'priority', 'status')
PRIORITIES = {'high': 0, 'medium': 1, 'low': 2}


@dataclass(frozen=True)
class Task:
    id: str
    subject: str
    title: str
    deadline: date
    minutes: int
    priority: str
    status: str


def load_tasks(path: Path) -> list[Task]:
    tasks = []
    seen = set()
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError(f'Expected CSV columns: {", ".join(FIELDS)}')
        for line, row in enumerate(reader, 2):
            try:
                if None in row or any(v is None or not v.strip() for v in row.values()):
                    raise ValueError('missing or extra fields')
                values = {k: v.strip() for k, v in row.items()}
                if values['id'] in seen:
                    raise ValueError('duplicate task ID')
                deadline = date.fromisoformat(values['deadline'])
                if deadline.isoformat() != values['deadline']:
                    raise ValueError('deadline must use YYYY-MM-DD')
                minutes = int(values['minutes'])
                if not 1 <= minutes <= 10080:
                    raise ValueError('minutes must be 1–10080')
                if values['priority'] not in PRIORITIES:
                    raise ValueError('priority must be high, medium or low')
                if values['status'] not in ('todo', 'done'):
                    raise ValueError('status must be todo or done')
                tasks.append(Task(values['id'], values['subject'], values['title'],
                                  deadline, minutes, values['priority'], values['status']))
                seen.add(values['id'])
            except ValueError as exc:
                raise ValueError(f'CSV line {line}: {exc}') from exc
    if not tasks:
        raise ValueError('CSV contains no tasks')
    return tasks


def build_plan(tasks: list[Task], start: date, days: int, capacity: int) -> dict:
    if not 1 <= days <= 90 or not 1 <= capacity <= 1440:
        raise ValueError('days must be 1–90 and capacity 1–1440 minutes')
    pending = sorted((t for t in tasks if t.status == 'todo'),
                     key=lambda t: (t.deadline, PRIORITIES[t.priority], t.id))
    remaining = {t.id: t.minutes for t in pending}
    timeline = []
    late = {t.id: 0 for t in pending}
    for offset in range(days):
        day = start + timedelta(days=offset)
        free = capacity
        allocations = []
        for task in pending:
            amount = min(remaining[task.id], free)
            if amount:
                allocations.append({'id': task.id, 'title': task.title, 'minutes': amount,
                                    'late': day > task.deadline})
                remaining[task.id] -= amount
                free -= amount
                if day > task.deadline:
                    late[task.id] += amount
            if not free:
                break
        timeline.append({'date': day.isoformat(), 'used_minutes': capacity - free,
                         'allocations': allocations})
    details = []
    for task in pending:
        details.append({'id': task.id, 'subject': task.subject, 'title': task.title,
                        'deadline': task.deadline.isoformat(), 'priority': task.priority,
                        'minutes': task.minutes, 'scheduled_minutes': task.minutes - remaining[task.id],
                        'unscheduled_minutes': remaining[task.id], 'late_minutes': late[task.id],
                        'overdue': task.deadline < start})
    total = sum(t.minutes for t in pending)
    allocated = sum(day['used_minutes'] for day in timeline)
    return {'start': start.isoformat(), 'days': days, 'daily_capacity': capacity,
            'total_tasks': len(tasks), 'completed_tasks': len(tasks) - len(pending),
            'pending_minutes': total, 'scheduled_minutes': allocated,
            'unscheduled_minutes': total - allocated, 'late_minutes': sum(late.values()),
            'tasks': details, 'timeline': timeline}
