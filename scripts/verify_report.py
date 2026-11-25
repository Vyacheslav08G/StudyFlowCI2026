"""Independently verify the generated report against its original CSV input."""
import argparse
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from studyflow.planner import load_tasks


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(source, output):
    tasks = load_tasks(source)
    pending = {t.id: t for t in tasks if t.status == 'todo'}
    plan = json.loads((output / 'plan.json').read_text(encoding='utf-8'))
    require(plan['total_tasks'] == len(tasks), 'total task count mismatch')
    require(plan['completed_tasks'] == len(tasks) - len(pending), 'completed count mismatch')
    require(len(plan['timeline']) == plan['days'], 'incorrect calendar length')
    allocated, late = Counter(), Counter()
    start = date.fromisoformat(plan['start'])
    for offset, day in enumerate(plan['timeline']):
        current = start + timedelta(days=offset)
        require(day['date'] == current.isoformat(), f'wrong date at day {offset}')
        used = 0
        for entry in day['allocations']:
            ident = entry['id']
            require(ident in pending, f'unknown or completed task: {ident}')
            amount = entry['minutes']
            require(type(amount) is int and amount > 0, f'invalid allocation: {ident}')
            require(entry['late'] == (current > pending[ident].deadline), f'wrong late flag: {ident}')
            used += amount
            allocated[ident] += amount
            if entry['late']:
                late[ident] += amount
        require(used == day['used_minutes'] <= plan['daily_capacity'], f'capacity mismatch: {day["date"]}')
    require(len(plan['tasks']) == len(pending) and {t['id'] for t in plan['tasks']} == set(pending), 'task list mismatch')
    for row in plan['tasks']:
        ident = row['id']
        task = pending[ident]
        require(0 <= allocated[ident] <= task.minutes, f'overallocated task: {ident}')
        require(row['scheduled_minutes'] == allocated[ident], f'wrong scheduled total: {ident}')
        require(row['unscheduled_minutes'] == task.minutes - allocated[ident], f'wrong remainder: {ident}')
        require(row['late_minutes'] == late[ident], f'wrong late total: {ident}')
    total = sum(t.minutes for t in pending.values())
    require(plan['pending_minutes'] == total, 'input total mismatch')
    require(plan['scheduled_minutes'] == sum(allocated.values()), 'scheduled total mismatch')
    require(plan['unscheduled_minutes'] == total - sum(allocated.values()), 'remaining total mismatch')
    require(plan['late_minutes'] == sum(late.values()), 'late total mismatch')
    html = (output / 'index.html').read_text(encoding='utf-8')
    require('<!doctype html>' in html and '</html>' in html, 'incomplete HTML report')
    print(f'Report integrity verified: {len(pending)} pending tasks, {len(plan["timeline"])} days, {total} input minutes; all allocations and totals match CSV.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        verify(args.input, args.output)
    except (ValueError, KeyError, OSError, TypeError) as exc:
        parser.exit(1, f'Report verification failed: {exc}\n')
