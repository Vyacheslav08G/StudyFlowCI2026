"""Command line interface for StudyFlow."""

import argparse
from datetime import date
from pathlib import Path
from studyflow.planner import build_plan, load_tasks
from studyflow.report import write_report


def main():
    parser = argparse.ArgumentParser(description='Validate tasks or generate a study plan')
    parser.add_argument('command', choices=['validate', 'report'])
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--start', type=date.fromisoformat, default=date.today())
    parser.add_argument('--days', type=int, default=7)
    parser.add_argument('--capacity', type=int, default=120)
    parser.add_argument('--output', type=Path, default=Path('dist'))
    args = parser.parse_args()
    try:
        tasks = load_tasks(args.input)
        print(f'Validated {len(tasks)} tasks: schema, unique IDs, dates, minutes, priorities, statuses')
        if args.command == 'report':
            plan = build_plan(tasks, args.start, args.days, args.capacity)
            write_report(plan, args.output)
            print(f'Scheduled {plan["scheduled_minutes"]} min; unscheduled {plan["unscheduled_minutes"]} min; late {plan["late_minutes"]} min')
            print(f'Result: {args.output / "index.html"} and {args.output / "plan.json"}')
    except (ValueError, OSError) as exc:
        parser.exit(2, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
