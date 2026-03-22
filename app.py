from flask import Flask, render_template, request
import json
from pathlib import Path
from collections import defaultdict
from datetime import date as date_cls, timedelta
import re

PROJECTS_DIR = Path.home() / '.claude' / 'projects'

app = Flask(__name__)

def project_dir_to_name(dir_name: str) -> str:
    """Convert '-Users-hsun-Hsun-PEGAAi-2-0' to 'PEGAAi-2.0'"""
    # Strip leading '-Users-<username>-<intermediate-dir>-' prefix
    parts = dir_name.lstrip('-').split('-')

    # Skip: 'Users', the username (next part), and the intermediate directory (third part)
    # Pattern: -Users-<username>-<intermediate-dir>-<project-name-parts>...
    skip_count = 0
    if len(parts) > 0 and parts[0] == 'Users':
        skip_count = 3  # Skip 'Users', username, and intermediate dir

    # For edge cases like '-Users-hsun' with no further parts
    skip_count = min(skip_count, len(parts))

    result = parts[skip_count:]
    name = '-'.join(result)
    # Convert trailing digits with separator back (e.g. '2-0' -> '2.0')
    # Simple heuristic: replace '-' between digits with '.'
    name = re.sub(r'(\d)-(\d)', r'\1.\2', name)
    return name or dir_name

def load_usage_records():
    """
    Returns list of dicts:
    {
      'project': str,       # human-readable project name
      'model': str,         # e.g. 'claude-sonnet-4-6'
      'date': str,          # 'YYYY-MM-DD'
      'input_tokens': int,
      'output_tokens': int,
      'cache_read': int,
      'cache_create': int,
    }
    """
    records = []
    if not PROJECTS_DIR.exists():
        return records
    for proj_dir in PROJECTS_DIR.iterdir():
        if not proj_dir.is_dir():
            continue
        project_name = project_dir_to_name(proj_dir.name)
        for jf in proj_dir.glob('*.jsonl'):
            try:
                with open(jf, encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if d.get('type') != 'assistant':
                            continue
                        msg = d.get('message', {})
                        model = msg.get('model', '')
                        if not model or model == '<synthetic>':
                            continue
                        usage = msg.get('usage', {})
                        input_t = usage.get('input_tokens', 0) or 0
                        output_t = usage.get('output_tokens', 0) or 0
                        if input_t == 0 and output_t == 0:
                            continue
                        ts = d.get('timestamp', '')
                        date = ts[:10] if ts and len(ts) >= 10 else 'unknown'
                        hour = ts[11:13] if ts and len(ts) >= 13 else 'unknown'
                        records.append({
                            'project': project_name,
                            'model': model,
                            'date': date,
                            'hour': hour,
                            'input_tokens': input_t,
                            'output_tokens': output_t,
                            'cache_read': usage.get('cache_read_input_tokens', 0) or 0,
                            'cache_create': usage.get('cache_creation_input_tokens', 0) or 0,
                        })
            except Exception as e:
                app.logger.warning(f"Skipping {jf}: {e}")
                continue
    return records

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/projects')
def api_projects():
    records = load_usage_records()
    projects = sorted({r['project'] for r in records})
    return {'projects': projects}

@app.route('/api/stats')
def api_stats():
    project_filter = request.args.get('project', 'all')
    all_records = load_usage_records()
    records = all_records if project_filter == 'all' else [r for r in all_records if r['project'] == project_filter]

    # KPIs
    total_input = sum(r['input_tokens'] for r in records)
    total_output = sum(r['output_tokens'] for r in records)
    total_cache_read = sum(r['cache_read'] for r in records)
    total_cache_create = sum(r['cache_create'] for r in records)
    total_tokens = total_input + total_output + total_cache_read + total_cache_create
    models_used = list({r['model'] for r in records})

    # Count unique sessions (approximate via unique dates+project combos)
    sessions = len({(r['project'], r['date']) for r in records})

    # Daily breakdown — sorted by date
    daily = defaultdict(lambda: defaultdict(int))
    for r in records:
        if r['date'] == 'unknown':
            continue
        daily[r['date']]['input'] += r['input_tokens']
        daily[r['date']]['output'] += r['output_tokens']
        daily[r['date']]['cache_read'] += r['cache_read']
        daily[r['date']]['cache_create'] += r['cache_create']

    sorted_dates = sorted(daily.keys())
    daily_data = {
        'dates': sorted_dates,
        'input': [daily[d]['input'] for d in sorted_dates],
        'output': [daily[d]['output'] for d in sorted_dates],
        'cache_read': [daily[d]['cache_read'] for d in sorted_dates],
        'cache_create': [daily[d]['cache_create'] for d in sorted_dates],
    }

    # Model distribution
    # Note: cache tokens excluded from model distribution (less meaningful for model attribution)
    model_totals = defaultdict(int)
    for r in records:
        model_totals[r['model']] += r['input_tokens'] + r['output_tokens']
    model_dist = [{'model': m, 'tokens': t} for m, t in sorted(model_totals.items(), key=lambda x: -x[1])]

    # Per-project totals — optionally filtered by date range
    proj_range_days = int(request.args.get('proj_range', '0') or '0')
    if proj_range_days > 0:
        cutoff = (date_cls.today() - timedelta(days=proj_range_days)).isoformat()
        proj_records = [r for r in all_records if r['date'] != 'unknown' and r['date'] >= cutoff]
    else:
        proj_records = all_records

    proj_totals = defaultdict(lambda: {'output': 0, 'cache': 0, 'total': 0})
    for r in proj_records:
        proj_totals[r['project']]['output'] += r['output_tokens']
        proj_totals[r['project']]['cache'] += r['cache_read'] + r['cache_create']
        proj_totals[r['project']]['total'] += r['input_tokens'] + r['output_tokens'] + r['cache_read'] + r['cache_create']
    projects_ranked = sorted(
        [{'project': p, **v} for p, v in proj_totals.items()],
        key=lambda x: -x['total']
    )

    return {
        'kpi': {
            'total_tokens': total_tokens,
            'output_tokens': total_output,
            'sessions': sessions,
            'models_used': len(models_used),
        },
        'daily': daily_data,
        'model_dist': model_dist,
        'projects_ranked': projects_ranked,
    }

@app.route('/api/hourly')
def api_hourly():
    date_str = request.args.get('date')
    project_filter = request.args.get('project', 'all')
    if not date_str:
        return {'error': 'date required'}, 400

    all_records = load_usage_records()
    records = [r for r in all_records if r['date'] == date_str]
    if project_filter != 'all':
        records = [r for r in records if r['project'] == project_filter]

    hourly = defaultdict(lambda: defaultdict(int))
    for r in records:
        h = r['hour']
        if h == 'unknown':
            continue
        hourly[h]['input'] += r['input_tokens']
        hourly[h]['output'] += r['output_tokens']
        hourly[h]['cache_read'] += r['cache_read']
        hourly[h]['cache_create'] += r['cache_create']

    hours = [f'{i:02d}' for i in range(24)]
    return {
        'date': date_str,
        'hours': hours,
        'input': [hourly[h]['input'] for h in hours],
        'output': [hourly[h]['output'] for h in hours],
        'cache_read': [hourly[h]['cache_read'] for h in hours],
        'cache_create': [hourly[h]['cache_create'] for h in hours],
    }

if __name__ == '__main__':
    app.run(debug=True, port=5050)
