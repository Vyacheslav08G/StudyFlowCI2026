"""Generate a portable HTML dashboard and machine-readable JSON."""

import json
from html import escape
from pathlib import Path


def render_html(plan: dict) -> str:
    def e(value):
        return escape(str(value), quote=True)

    cards = ''.join(f'<article><small>{label}</small><strong>{e(plan[key])}</strong></article>'
                    for label, key in [('Задачи', 'total_tasks'), ('Выполнено', 'completed_tasks'),
                                       ('Запланировано, мин', 'scheduled_minutes'),
                                       ('Не помещается, мин', 'unscheduled_minutes'),
                                       ('После дедлайна, мин', 'late_minutes')])
    rows = ''.join('<tr>' + ''.join(f'<td>{e(t[key])}</td>' for key in
                   ('subject', 'title', 'deadline', 'priority', 'scheduled_minutes',
                    'unscheduled_minutes', 'late_minutes')) + '</tr>' for t in plan['tasks'])
    days = []
    for day in plan['timeline']:
        pct = round(100 * day['used_minutes'] / plan['daily_capacity'])
        items = ''.join(f'<li>{e(a["title"])} — {a["minutes"]} мин'
                        f'{" · после дедлайна" if a["late"] else ""}</li>'
                        for a in day['allocations']) or '<li>Свободный день</li>'
        days.append(f'<article><h3>{e(day["date"])}</h3><progress value="{pct}" max="100"></progress>'
                    f'<p>{day["used_minutes"]} / {plan["daily_capacity"]} мин</p><ul>{items}</ul></article>')
    return f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>StudyFlow — учебный план</title><style>
*{{box-sizing:border-box}} body{{margin:0;background:#eef2f7;color:#16243b;font:16px system-ui,sans-serif}}
main{{max-width:1180px;margin:auto;padding:32px 20px}} header{{background:#122847;color:white;padding:32px;border-radius:20px}}
h1{{font-size:clamp(28px,5vw,48px);margin:0}} h2{{margin-top:36px}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}}
article{{background:white;border:1px solid #dce4ee;border-radius:14px;padding:18px}} strong{{display:block;font-size:30px;margin-top:8px}}
.table{{overflow:auto;background:white;border-radius:14px}} table{{width:100%;border-collapse:collapse;text-align:left}} th,td{{padding:13px;border-bottom:1px solid #e2e8f0}} th{{background:#e3ebf7}} progress{{width:100%;accent-color:#2674bd}} li{{margin:6px 0}} footer{{color:#52627a;margin-top:36px}}
</style></head><body><main><header><p>STUDYFLOW / PLANNING ENGINE</p><h1>Учебная нагрузка</h1><p>Начало: {e(plan['start'])} · Горизонт: {plan['days']} дней · Лимит: {plan['daily_capacity']} мин/день</p></header>
<h2>Обзор</h2><section class="grid">{cards}</section><h2>Задачи и риски</h2><div class="table"><table><thead><tr><th>Предмет</th><th>Задача</th><th>Дедлайн</th><th>Приоритет</th><th>План, мин</th><th>Остаток, мин</th><th>Поздно, мин</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Календарь</h2><section class="grid">{''.join(days)}</section><footer>StudyFlow · План по ближайшему дедлайну, затем по приоритету. Отчёт не требует интернета.</footer></main></body></html>'''


def write_report(plan: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'index.html').write_text(render_html(plan), encoding='utf-8')
