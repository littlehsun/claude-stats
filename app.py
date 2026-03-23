from flask import Flask, render_template, request
import json
from pathlib import Path
from collections import defaultdict
from datetime import date as date_cls, timedelta, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re

PROJECTS_DIR = Path.home() / '.claude' / 'projects'

# When running in Docker, $HOME is mounted at /host-home so we can do
# filesystem-based path reconstruction against the real host home.
_HOST_HOME = Path('/host-home') if Path('/host-home').is_dir() else Path.home()

app = Flask(__name__)

def _norm(s: str) -> str:
    """Normalize for fuzzy matching: lowercase, collapse non-alphanumeric to '-'."""
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


@lru_cache(maxsize=None)
def _encoded_home_prefix() -> str:
    """Infer the encoded home-directory prefix from the common prefix of all project dir_names.

    Works in Docker too: dir_names encode host paths, so we don't rely on
    Path.home() (which would return /root in Docker).
    """
    if not PROJECTS_DIR.exists():
        return ''
    names = [d.name for d in PROJECTS_DIR.iterdir() if d.is_dir()]
    if not names:
        return ''
    from os.path import commonprefix
    # Filter to dirs that look like encoded absolute home paths (≥2 dashes).
    # This excludes outliers like '-tmp' which would shorten the common prefix
    # to just '-' and break all path decoding.
    home_like = [n for n in names if n.count('-') >= 2]
    return commonprefix(home_like or names)  # e.g. '-home-michael-lin'


@lru_cache(maxsize=None)
def dir_name_to_path(dir_name: str) -> str:
    """Reconstruct the exact original path by fuzzy-matching against the filesystem.

    Uses backtracking to avoid false sibling matches. Hidden directories (dot-prefixed)
    are excluded to prevent ~/.claude etc. from being matched as path components.
    Falls back to single-step greedy advance for deleted/missing directories.
    """
    home_prefix = _encoded_home_prefix()
    if not home_prefix or not dir_name.startswith(home_prefix):
        return '/' + dir_name.lstrip('-')

    remainder = dir_name[len(home_prefix):].lstrip('-')  # e.g. 'Hsun-PegaAgentMVP'
    if not remainder:
        return '~'

    parts = _norm(remainder).split('-')
    orig_parts = remainder.split('-')

    def _match_child(current: Path, target: str):
        """Yield dirs under current whose normalized name equals target (no hidden dirs)."""
        try:
            for child in current.iterdir():
                if child.is_dir() and not child.name.startswith('.') and _norm(child.name) == target:
                    yield child
        except OSError:
            pass

    def _resolve(current: Path, i: int):
        """Backtracking resolve: returns Path if parts[i:] fully resolve, else None."""
        if i == len(parts):
            return current
        for j in range(len(parts), i, -1):
            target = '-'.join(parts[i:j])
            for child in _match_child(current, target):
                result = _resolve(child, j)
                if result is not None:
                    return result
        return None

    result = _resolve(_HOST_HOME, 0)
    if result is not None:
        return str(result).replace(str(_HOST_HOME), '~', 1)

    # Fallback for deleted/missing dirs: single-step greedy advance (one part at a time),
    # stopping at the first unresolvable segment and treating the rest as the project name.
    current = _HOST_HOME
    i = 0
    while i < len(parts):
        matched = False
        for child in _match_child(current, parts[i]):
            current = child
            i += 1
            matched = True
            break
        if not matched:
            break

    if i < len(parts):
        current = current / '-'.join(orig_parts[i:])

    return str(current).replace(str(_HOST_HOME), '~', 1)


def project_dir_to_name(dir_name: str) -> str:
    """Short display name = last component of the reconstructed path."""
    path = dir_name_to_path(dir_name)
    name = Path(path.replace('~', str(_HOST_HOME), 1)).name
    return name or dir_name

def _parse_tz(tz_name: str):
    """Return a ZoneInfo object for tz_name, falling back to local timezone."""
    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, KeyError):
            pass
    return datetime.now().astimezone().tzinfo


def load_usage_records(tz=None):
    """
    Returns list of dicts:
    {
      'project': str,       # human-readable project name
      'model': str,         # e.g. 'claude-sonnet-4-6'
      'date': str,          # 'YYYY-MM-DD' in the given timezone
      'hour': str,          # 'HH' in the given timezone
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
                        if ts and len(ts) >= 10:
                            try:
                                dt_utc = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                                dt_local = dt_utc.astimezone(tz)
                                date = dt_local.strftime('%Y-%m-%d')
                                hour = dt_local.strftime('%H')
                            except (ValueError, Exception):
                                date = ts[:10]
                                hour = ts[11:13] if len(ts) >= 13 else 'unknown'
                        else:
                            date = 'unknown'
                            hour = 'unknown'
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
    projects = []
    seen = set()
    if PROJECTS_DIR.exists():
        for proj_dir in sorted(PROJECTS_DIR.iterdir()):
            if not proj_dir.is_dir():
                continue
            name = project_dir_to_name(proj_dir.name)
            if name not in seen:
                seen.add(name)
                projects.append({'name': name, 'path': dir_name_to_path(proj_dir.name)})
    return {'projects': projects}

@app.route('/api/stats')
def api_stats():
    project_filter = request.args.get('project', 'all')
    tz = _parse_tz(request.args.get('tz', ''))
    all_records = load_usage_records(tz)
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

    # Today's stats — use the same timezone as records
    today_str = datetime.now(tz).strftime('%Y-%m-%d')
    today_records = [r for r in records if r['date'] == today_str]
    today_tokens = sum(r['input_tokens'] + r['output_tokens'] + r['cache_read'] + r['cache_create'] for r in today_records)
    today_output = sum(r['output_tokens'] for r in today_records)
    today_sessions = len({r['project'] for r in today_records})

    # Streak — use unfiltered records so range selection doesn't break it
    all_dates_activity = {r['date'] for r in records if r['date'] != 'unknown'}
    streak = 0
    check = today_str
    while check in all_dates_activity:
        streak += 1
        check = (date_cls.fromisoformat(check) - timedelta(days=1)).isoformat()
    if streak == 0:
        check = (date_cls.fromisoformat(today_str) - timedelta(days=1)).isoformat()
        while check in all_dates_activity:
            streak += 1
            check = (date_cls.fromisoformat(check) - timedelta(days=1)).isoformat()

    # Daily breakdown — optionally filtered by date range
    daily_range_days = int(request.args.get('daily_range', '0') or '0')
    daily_cutoff = (date_cls.fromisoformat(today_str) - timedelta(days=daily_range_days)).isoformat() if daily_range_days > 0 else None

    daily = defaultdict(lambda: defaultdict(int))
    for r in records:
        if r['date'] == 'unknown':
            continue
        if daily_cutoff and r['date'] < daily_cutoff:
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

    # Daily breakdown by model (output tokens only, same date filter)
    model_daily = defaultdict(lambda: defaultdict(int))
    for r in records:
        if r['date'] == 'unknown':
            continue
        if daily_cutoff and r['date'] < daily_cutoff:
            continue
        model_daily[r['model']][r['date']] += r['output_tokens']
    daily_models = sorted(model_daily.keys())
    daily_by_model = {
        'models': daily_models,
        'dates': sorted_dates,
        'series': {m: [model_daily[m].get(d, 0) for d in sorted_dates] for m in daily_models},
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
        cutoff = (date_cls.fromisoformat(today_str) - timedelta(days=proj_range_days)).isoformat()
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

    # Heatmap — all projects, all time (ignore project/date filters)
    heatmap_totals = defaultdict(int)
    for r in all_records:
        if r['date'] != 'unknown':
            heatmap_totals[r['date']] += r['input_tokens'] + r['output_tokens'] + r['cache_read'] + r['cache_create']

    return {
        'kpi': {
            'total_tokens': total_tokens,
            'output_tokens': total_output,
            'sessions': sessions,
            'models_used': len(models_used),
            'today_tokens': today_tokens,
            'today_output': today_output,
            'today_sessions': today_sessions,
            'streak': streak,
        },
        'daily': daily_data,
        'daily_by_model': daily_by_model,
        'model_dist': model_dist,
        'projects_ranked': projects_ranked,
        'heatmap': dict(heatmap_totals),
    }

@app.route('/api/hourly')
def api_hourly():
    date_str = request.args.get('date')
    project_filter = request.args.get('project', 'all')
    if not date_str:
        return {'error': 'date required'}, 400

    tz = _parse_tz(request.args.get('tz', ''))
    all_records = load_usage_records(tz)
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
    import os
    port = int(os.environ.get('PORT', 5050))
    app.run(debug=True, host='0.0.0.0', port=port)
