import csv
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from studyflow.planner import FIELDS, Task, build_plan, load_tasks
from studyflow.report import render_html, write_report

START = date(2026, 11, 25)


def task(id='A', minutes=80, deadline=START, priority='high', status='todo', title='Task'):
    return Task(id, 'Subject', title, deadline, minutes, priority, status)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'tasks.csv'

    def write(self, rows):
        with self.path.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream)
            writer.writerow(FIELDS)
            writer.writerows(rows)

    def test_valid_csv(self):
        self.write([['A', 'Math', 'Review', '2026-11-25', '45', 'high', 'todo']])
        self.assertEqual(load_tasks(self.path)[0].minutes, 45)

    def test_invalid_fields(self):
        baseline = ['A', 'Math', 'Review', '2026-11-25', '45', 'high', 'todo']
        for column, value in [(0, ''), (3, '2026-02-30'), (4, '0'), (4, '-1'),
                              (4, 'x'), (4, '10081'), (5, 'urgent'), (6, 'unknown')]:
            with self.subTest(column=column, value=value):
                row = baseline.copy()
                row[column] = value
                self.write([row])
                with self.assertRaisesRegex(ValueError, 'CSV line 2'):
                    load_tasks(self.path)

    def test_duplicate_id(self):
        row = ['A', 'Math', 'Review', '2026-11-25', '45', 'high', 'todo']
        self.write([row, row])
        with self.assertRaisesRegex(ValueError, 'duplicate task ID'):
            load_tasks(self.path)

    def test_empty_csv(self):
        self.write([])
        with self.assertRaisesRegex(ValueError, 'no tasks'):
            load_tasks(self.path)

    def test_wrong_header(self):
        self.path.write_text('wrong,header\n1,2\n')
        with self.assertRaisesRegex(ValueError, 'Expected CSV columns'):
            load_tasks(self.path)

    def test_extra_column(self):
        self.write([['A', 'Math', 'Review', '2026-11-25', '45', 'high', 'todo', 'extra']])
        with self.assertRaisesRegex(ValueError, 'extra fields'):
            load_tasks(self.path)


class PlannerTests(unittest.TestCase):
    def test_capacity_and_conservation(self):
        plan = build_plan([task('A', 160), task('B', 90)], START, 2, 100)
        self.assertEqual(plan['scheduled_minutes'], 200)
        self.assertEqual(plan['unscheduled_minutes'], 50)
        self.assertTrue(all(d['used_minutes'] <= 100 for d in plan['timeline']))
        self.assertEqual(sum(t['scheduled_minutes'] for t in plan['tasks']), 200)
        self.assertEqual(sum(t['unscheduled_minutes'] for t in plan['tasks']), 50)

    def test_deadline_first_priority_second(self):
        later = date(2026, 11, 26)
        tasks = [task('A', 20, later, 'high'), task('B', 20, START, 'low'),
                 task('C', 20, START, 'high')]
        plan = build_plan(tasks, START, 1, 40)
        self.assertEqual([a['id'] for a in plan['timeline'][0]['allocations']], ['C', 'B'])

    def test_overdue_and_late(self):
        plan = build_plan([task(minutes=120)], START, 2, 60)
        self.assertEqual(plan['late_minutes'], 60)
        self.assertFalse(plan['tasks'][0]['overdue'])
        plan = build_plan([task(deadline=date(2026, 11, 24))], START, 1, 100)
        self.assertTrue(plan['tasks'][0]['overdue'])
        self.assertEqual(plan['late_minutes'], 80)

    def test_completed_tasks_excluded(self):
        plan = build_plan([task(status='done')], START, 2, 60)
        self.assertEqual(plan['completed_tasks'], 1)
        self.assertEqual(plan['pending_minutes'], 0)
        self.assertEqual(plan['tasks'], [])

    def test_deterministic_tie(self):
        plan = build_plan([task('B'), task('A')], START, 1, 80)
        self.assertEqual(plan['timeline'][0]['allocations'][0]['id'], 'A')

    def test_bad_capacity_or_horizon(self):
        for days, capacity in [(0, 60), (91, 60), (1, 0), (1, 1441)]:
            with self.subTest(days=days, capacity=capacity), self.assertRaises(ValueError):
                build_plan([], START, days, capacity)

    def test_exact_deadline_is_not_late(self):
        self.assertEqual(build_plan([task()], START, 1, 80)['late_minutes'], 0)


class ReportTests(unittest.TestCase):
    def test_html_escapes_user_content(self):
        html = render_html(build_plan([task(title='<script>alert(1)</script>')], START, 1, 80))
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_outputs_roundtrip(self):
        plan = build_plan([task()], START, 1, 80)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            write_report(plan, path)
            self.assertEqual(json.loads((path / 'plan.json').read_text()), plan)
            self.assertIn('Учебная нагрузка', (path / 'index.html').read_text())

    def test_cli_invalid_input_returns_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.csv'
            path.write_text('invalid\n')
            result = subprocess.run([sys.executable, '-m', 'studyflow', 'validate', '--input', str(path)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('Expected CSV columns', result.stderr)


if __name__ == '__main__':
    unittest.main()
