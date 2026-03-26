from flask import Flask, render_template, request, send_file
import json
from pathlib import Path
from collections import defaultdict
from datetime import date as date_cls, timedelta, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re
import io
import shutil
import zipfile

PROJECTS_DIR = Path.home() / '.claude' / 'projects'
IMPORTS_DIR = Path.home() / '.claude-stats' / 'imports'
IMPORTED_PROJECTS_DIR = IMPORTS_DIR / 'projects'
IMPORT_MANIFEST_PATH = IMPORTS_DIR / 'manifest.json'

# When running in Docker, $HOME is mounted at /host-home so we can do
# filesystem-based path reconstruction against the real host home.
_HOST_HOME = Path('/host-home') if Path('/host-home').is_dir() else Path.home()

app = Flask(__name__)
_USAGE_RECORDS_CACHE = {
    'signature': None,
    'by_tz': {},
}

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


def _load_manifest(manifest_path: Path = IMPORT_MANIFEST_PATH) -> dict:
    if not manifest_path.is_file():
        return {}
    try:
        with open(manifest_path, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def iter_project_sources():
    if PROJECTS_DIR.exists():
        for proj_dir in PROJECTS_DIR.iterdir():
            if proj_dir.is_dir():
                yield proj_dir, None

    if IMPORTED_PROJECTS_DIR.exists():
        manifest = _load_manifest()
        path_map = manifest.get('path_map', {}) if isinstance(manifest.get('path_map', {}), dict) else {}
        for proj_dir in IMPORTED_PROJECTS_DIR.iterdir():
            if proj_dir.is_dir():
                yield proj_dir, path_map


def _source_signature():
    entries = []
    if PROJECTS_DIR.exists():
        for proj_dir in sorted(PROJECTS_DIR.iterdir()):
            if not proj_dir.is_dir():
                continue
            entries.append((str(proj_dir), 0, 0))
            for jf in sorted(proj_dir.glob('*.jsonl')):
                try:
                    st = jf.stat()
                    entries.append((str(jf), st.st_size, st.st_mtime_ns))
                except OSError:
                    entries.append((str(jf), -1, -1))
    if IMPORTED_PROJECTS_DIR.exists():
        for proj_dir in sorted(IMPORTED_PROJECTS_DIR.iterdir()):
            if not proj_dir.is_dir():
                continue
            entries.append((str(proj_dir), 0, 0))
            for jf in sorted(proj_dir.glob('*.jsonl')):
                try:
                    st = jf.stat()
                    entries.append((str(jf), st.st_size, st.st_mtime_ns))
                except OSError:
                    entries.append((str(jf), -1, -1))
    if IMPORT_MANIFEST_PATH.exists():
        try:
            st = IMPORT_MANIFEST_PATH.stat()
            entries.append((str(IMPORT_MANIFEST_PATH), st.st_size, st.st_mtime_ns))
        except OSError:
            entries.append((str(IMPORT_MANIFEST_PATH), -1, -1))
    return tuple(entries)


def project_dir_to_path(dir_name: str, path_map=None) -> str:
    if path_map and dir_name in path_map:
        return path_map[dir_name]
    return dir_name_to_path(dir_name)


def project_dir_to_display_name(dir_name: str, path_map=None) -> str:
    path = project_dir_to_path(dir_name, path_map)
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


def _fmt_dur(td):
    mins = int(td.total_seconds() / 60)
    h, m = divmod(mins, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def _merge_intervals(intervals):
    total = timedelta()
    if not intervals:
        return total
    intervals.sort()
    cur_start, cur_end = intervals[0]
    for s, e in intervals[1:]:
        if s <= cur_end:
            cur_end = max(cur_end, e)
        else:
            total += cur_end - cur_start
            cur_start, cur_end = s, e
    total += cur_end - cur_start
    return total


def _records_for_project(records, project_filter):
    return records if project_filter == 'all' else [r for r in records if r['project'] == project_filter]


def _cutoff_for_period(period, tz):
    today_str = datetime.now(tz).strftime('%Y-%m-%d')
    if period == 'week':
        return (date_cls.fromisoformat(today_str) - timedelta(days=7)).isoformat()
    if period == 'month':
        return (date_cls.fromisoformat(today_str) - timedelta(days=30)).isoformat()
    return None


def _record_identity(d: dict) -> str:
    return d.get('uuid') or '|'.join([
        d.get('sessionId', ''),
        d.get('parentUuid', ''),
        d.get('timestamp', ''),
        d.get('type', ''),
    ])


def _load_jsonl_objects(path: Path):
    objects = []
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    objects.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return objects


def _merge_jsonl_payload(dest_path: Path, payload_lines):
    existing = _load_jsonl_objects(dest_path) if dest_path.exists() else []
    seen_ids = {_record_identity(obj) for obj in existing}
    merged = list(existing)
    added = 0
    skipped = 0

    for raw_line in payload_lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        record_id = _record_identity(obj)
        if record_id in seen_ids:
            skipped += 1
            continue
        seen_ids.add(record_id)
        merged.append(obj)
        added += 1

    if added > 0 or not dest_path.exists():
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, 'w', encoding='utf-8') as f:
            for obj in merged:
                f.write(json.dumps(obj, ensure_ascii=False) + '\n')

    return added, skipped


def _save_import_manifest(manifest: dict):
    IMPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(IMPORT_MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def _parse_days_arg(raw_value) -> int:
    try:
        days = int(raw_value or '0')
    except (TypeError, ValueError):
        return 0
    return max(days, 0)


def _build_cutoff_date(days: int, tz) -> str | None:
    if days <= 0:
        return None
    today_str = datetime.now(tz).strftime('%Y-%m-%d')
    return (date_cls.fromisoformat(today_str) - timedelta(days=days)).isoformat()


def _parse_dt(ts, tz):
    if ts and len(ts) >= 10:
        try:
            return datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone(tz)
        except (ValueError, Exception):
            pass
    return None


def _object_date_str(obj: dict, tz) -> str:
    ts = obj.get('timestamp', '')
    dt_local = _parse_dt(ts, tz)
    if dt_local:
        return dt_local.strftime('%Y-%m-%d')
    return ts[:10] if ts else 'unknown'


def _filter_file_objects(raw_objects: list[dict], cutoff_date: str | None, tz):
    if cutoff_date is None:
        return raw_objects

    include_ids = set()
    include_indexes = set()
    for idx, obj in enumerate(raw_objects):
        if obj.get('type') != 'assistant':
            continue
        obj_date = _object_date_str(obj, tz)
        if obj_date == 'unknown' or obj_date < cutoff_date:
            continue
        include_indexes.add(idx)
        parent_uuid = obj.get('parentUuid')
        if parent_uuid:
            include_ids.add(parent_uuid)

    filtered = []
    for idx, obj in enumerate(raw_objects):
        if idx in include_indexes or obj.get('uuid') in include_ids:
            filtered.append(obj)
    return filtered


def _project_entries_from_zip(zf: zipfile.ZipFile, manifest: dict):
    path_map = manifest.get('path_map', {}) if isinstance(manifest.get('path_map', {}), dict) else {}
    seen = {}
    for name in zf.namelist():
        if not (name.startswith('projects/') and name.endswith('.jsonl')):
            continue
        rel_path = Path(name)
        if len(rel_path.parts) < 3:
            continue
        dir_name = rel_path.parts[1]
        if dir_name in seen:
            continue
        path = path_map.get(dir_name, '/' + dir_name.lstrip('-'))
        seen[dir_name] = {
            'key': dir_name,
            'name': Path(path.replace('~', str(_HOST_HOME), 1)).name or dir_name,
            'path': path,
        }
    return sorted(seen.values(), key=lambda item: item['name'].lower())


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
    if not PROJECTS_DIR.exists() and not IMPORTED_PROJECTS_DIR.exists():
        return records
    tz_key = getattr(tz, 'key', None) or str(tz)
    signature = _source_signature()
    if _USAGE_RECORDS_CACHE['signature'] != signature:
        _USAGE_RECORDS_CACHE['signature'] = signature
        _USAGE_RECORDS_CACHE['by_tz'] = {}
        _encoded_home_prefix.cache_clear()
        dir_name_to_path.cache_clear()
    cached = _USAGE_RECORDS_CACHE['by_tz'].get(tz_key)
    if cached is not None:
        return [dict(r) for r in cached]
    seen_record_ids = set()
    for proj_dir, path_map in iter_project_sources():
        project_name = project_dir_to_display_name(proj_dir.name, path_map)
        for jf in proj_dir.glob('*.jsonl'):
            try:
                raw_lines = []
                with open(jf, encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            raw_lines.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

                # First pass: build uuid → dt_local for all messages
                uuid_dt = {}
                for d in raw_lines:
                    uid = d.get('uuid')
                    ts = d.get('timestamp', '')
                    if uid and ts:
                        dt = _parse_dt(ts, tz)
                        if dt:
                            uuid_dt[uid] = dt

                # Second pass: collect assistant records with usage
                for d in raw_lines:
                    if d.get('type') != 'assistant':
                        continue
                    record_id = d.get('uuid') or '|'.join([
                        d.get('sessionId', ''),
                        d.get('parentUuid', ''),
                        d.get('timestamp', ''),
                    ])
                    if record_id in seen_record_ids:
                        continue
                    seen_record_ids.add(record_id)
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
                    dt_local = _parse_dt(ts, tz)
                    if dt_local:
                        date = dt_local.strftime('%Y-%m-%d')
                        hour = dt_local.strftime('%H')
                        minute = dt_local.strftime('%M')
                    else:
                        date = ts[:10] if ts else 'unknown'
                        hour = ts[11:13] if len(ts) >= 13 else 'unknown'
                        minute = ts[14:16] if len(ts) >= 16 else 'unknown'

                    # Request start = parent user message timestamp
                    parent_uuid = d.get('parentUuid')
                    dt_start = uuid_dt.get(parent_uuid) if parent_uuid else None

                    records.append({
                        'project': project_name,
                        'model': model,
                        'date': date,
                        'hour': hour,
                        'minute': minute,
                        'dt_local': dt_local,
                        'dt_start': dt_start,
                        'session_id': d.get('sessionId', ''),
                        'input_tokens': input_t,
                        'output_tokens': output_t,
                        'cache_read': usage.get('cache_read_input_tokens', 0) or 0,
                        'cache_create': usage.get('cache_creation_input_tokens', 0) or 0,
                    })
            except Exception as e:
                app.logger.warning(f"Skipping {jf}: {e}")
                continue
    _USAGE_RECORDS_CACHE['by_tz'][tz_key] = [dict(r) for r in records]
    return records

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/projects')
def api_projects():
    projects = []
    seen = set()
    for proj_dir, path_map in sorted(iter_project_sources(), key=lambda item: item[0].name):
        name = project_dir_to_display_name(proj_dir.name, path_map)
        if name not in seen:
            seen.add(name)
            projects.append({'name': name, 'path': project_dir_to_path(proj_dir.name, path_map)})
    return {'projects': projects}


@app.route('/api/export')
def api_export():
    project_filter = request.args.get('project', 'all')
    tz = _parse_tz(request.args.get('tz', ''))
    days = _parse_days_arg(request.args.get('days', '0'))
    cutoff_date = _build_cutoff_date(days, tz)
    buf = io.BytesIO()
    created_at = datetime.now().astimezone().isoformat()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        path_map = {}
        exported_projects = set()
        if PROJECTS_DIR.exists():
            for proj_dir in sorted(PROJECTS_DIR.iterdir()):
                if not proj_dir.is_dir():
                    continue
                project_path = dir_name_to_path(proj_dir.name)
                project_name = Path(project_path.replace('~', str(_HOST_HOME), 1)).name or proj_dir.name
                if project_filter != 'all' and project_filter != project_name:
                    continue
                for jf in sorted(proj_dir.glob('*.jsonl')):
                    raw_objects = _load_jsonl_objects(jf)
                    filtered_objects = _filter_file_objects(raw_objects, cutoff_date, tz)
                    if not filtered_objects:
                        continue
                    path_map[proj_dir.name] = project_path
                    exported_projects.add(proj_dir.name)
                    payload = ''.join(json.dumps(obj, ensure_ascii=False) + '\n' for obj in filtered_objects)
                    zf.writestr(f'projects/{proj_dir.name}/{jf.name}', payload)
        manifest = {
            'format_version': 1,
            'created_at': created_at,
            'source': 'claude-stats',
            'path_map': path_map,
            'filters': {
                'project': project_filter,
                'days': days,
            },
        }
        zf.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    buf.seek(0)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    return send_file(
        buf,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'claude-stats-export-{stamp}.zip',
    )


def _safe_zip_members(zf: zipfile.ZipFile):
    for member in zf.infolist():
        path = Path(member.filename)
        if path.is_absolute():
            return False
        if '..' in path.parts:
            return False
    return True


@app.route('/api/import/preview', methods=['POST'])
def api_import_preview():
    upload = request.files.get('file')
    if not upload or not upload.filename:
        return {'error': 'file required'}, 400

    try:
        payload = upload.read()
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            if not _safe_zip_members(zf):
                return {'error': 'invalid zip contents'}, 400
            manifest = {'path_map': {}}
            if 'manifest.json' in zf.namelist():
                with zf.open('manifest.json') as mf:
                    manifest = json.load(mf)
            projects = _project_entries_from_zip(zf, manifest)
            if not projects:
                return {'error': 'zip does not contain exported project data'}, 400
            return {'projects': projects}
    except zipfile.BadZipFile:
        return {'error': 'invalid zip file'}, 400
    except json.JSONDecodeError:
        return {'error': 'invalid manifest.json'}, 400


@app.route('/api/import', methods=['POST'])
def api_import():
    upload = request.files.get('file')
    if not upload or not upload.filename:
        return {'error': 'file required'}, 400

    project_filter = request.form.get('project', 'all')
    tz = _parse_tz(request.form.get('tz', ''))
    days = _parse_days_arg(request.form.get('days', '0'))
    cutoff_date = _build_cutoff_date(days, tz)

    try:
        payload = upload.read()
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            if not _safe_zip_members(zf):
                return {'error': 'invalid zip contents'}, 400
            incoming_manifest = {'path_map': {}}
            if 'manifest.json' in zf.namelist():
                with zf.open('manifest.json') as mf:
                    incoming_manifest = json.load(mf)
            if not any(name.startswith('projects/') and name.endswith('.jsonl') for name in zf.namelist()):
                return {'error': 'zip does not contain exported project data'}, 400

            IMPORTED_PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
            merged_manifest = _load_manifest()
            merged_path_map = merged_manifest.get('path_map', {}) if isinstance(merged_manifest.get('path_map', {}), dict) else {}
            incoming_path_map = incoming_manifest.get('path_map', {}) if isinstance(incoming_manifest.get('path_map', {}), dict) else {}

            imported_files = 0
            added_records = 0
            skipped_records = 0
            imported_projects = set()

            for name in sorted(zf.namelist()):
                if not (name.startswith('projects/') and name.endswith('.jsonl')):
                    continue
                rel_path = Path(name)
                if len(rel_path.parts) < 3:
                    continue
                project_dir_name = rel_path.parts[1]
                project_path = incoming_path_map.get(project_dir_name, '/' + project_dir_name.lstrip('-'))
                project_name = Path(project_path.replace('~', str(_HOST_HOME), 1)).name or project_dir_name
                if project_filter != 'all' and project_filter != project_name and project_filter != project_dir_name:
                    continue
                dest_path = IMPORTS_DIR.joinpath(*rel_path.parts)
                with zf.open(name) as src:
                    raw_objects = []
                    for line in src:
                        line = line.decode('utf-8', errors='ignore').strip()
                        if not line:
                            continue
                        try:
                            raw_objects.append(json.loads(line))
                        except json.JSONDecodeError:
                            skipped_records += 1
                filtered_objects = _filter_file_objects(raw_objects, cutoff_date, tz)
                if not filtered_objects:
                    continue
                payload_lines = [json.dumps(obj, ensure_ascii=False) for obj in filtered_objects]
                added, skipped = _merge_jsonl_payload(dest_path, payload_lines)
                imported_files += 1
                added_records += added
                skipped_records += skipped
                imported_projects.add(project_dir_name)
                if project_dir_name in incoming_path_map:
                    merged_path_map[project_dir_name] = incoming_path_map[project_dir_name]

            merged_manifest.update({
                'format_version': 1,
                'updated_at': datetime.now().astimezone().isoformat(),
                'source': 'claude-stats',
                'path_map': merged_path_map,
            })
            _save_import_manifest(merged_manifest)
    except zipfile.BadZipFile:
        return {'error': 'invalid zip file'}, 400
    except json.JSONDecodeError:
        return {'error': 'invalid manifest.json'}, 400
    except OSError as e:
        return {'error': str(e)}, 500

    return {
        'ok': True,
        'projects': len(imported_projects),
        'files': imported_files,
        'added_records': added_records,
        'skipped_records': skipped_records,
        'filters': {
            'project': project_filter,
            'days': days,
        },
    }


@app.route('/api/report')
def api_report():
    period = request.args.get('period', 'week')
    if period not in {'week', 'month'}:
        return {'error': 'period must be week or month'}, 400

    project_filter = request.args.get('project', 'all')
    tz = _parse_tz(request.args.get('tz', ''))
    all_records = load_usage_records(tz)
    filtered = _records_for_project(all_records, project_filter)
    cutoff = _cutoff_for_period(period, tz)
    records = [r for r in filtered if r['date'] != 'unknown' and (cutoff is None or r['date'] >= cutoff)]

    total_tokens = sum(r['input_tokens'] + r['output_tokens'] + r['cache_read'] + r['cache_create'] for r in records)
    total_output = sum(r['output_tokens'] for r in records)
    total_input = sum(r['input_tokens'] + r['cache_read'] + r['cache_create'] for r in records)
    sessions = len({r['session_id'] or (r['project'], r['date']) for r in records})
    models_used = len({r['model'] for r in records if r['model']})
    active_days = len({r['date'] for r in records if r['date'] != 'unknown'})
    daily_avg = total_tokens // active_days if active_days else 0

    intervals = [(r['dt_start'], r['dt_local']) for r in records if r['dt_start'] and r['dt_local'] and r['dt_local'] > r['dt_start']]
    active_time = _fmt_dur(_merge_intervals(intervals))

    by_day = defaultdict(int)
    by_model = defaultdict(int)
    by_project = defaultdict(int)
    for r in records:
        tokens = r['input_tokens'] + r['output_tokens'] + r['cache_read'] + r['cache_create']
        by_day[r['date']] += tokens
        by_model[r['model']] += tokens
        by_project[r['project']] += tokens

    top_days = sorted(by_day.items(), key=lambda item: (-item[1], item[0]))[:7]
    top_models = sorted(by_model.items(), key=lambda item: -item[1])[:7]
    top_projects = sorted(by_project.items(), key=lambda item: -item[1])[:7]

    period_label = 'Weekly' if period == 'week' else 'Monthly'
    scope_label = project_filter if project_filter != 'all' else 'All Projects'
    today_label = datetime.now(tz).strftime('%Y-%m-%d')

    def _rows(items, label_key):
        if not items:
            return '<tr><td colspan="2">No activity</td></tr>'
        return ''.join(
            f"<tr><td>{item[0]}</td><td>{item[1]:,}</td></tr>" if isinstance(item, tuple)
            else f"<tr><td>{item[label_key]}</td><td>{item['tokens']:,}</td></tr>"
            for item in items
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Claude Stats {period_label} Report</title>
  <style>
    :root {{
      --bg: #f4f6fb;
      --surface: #ffffff;
      --text: #1a1f3a;
      --muted: #6b7494;
      --border: #dde2f0;
      --accent: #7c5cbf;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); }}
    .page {{ max-width: 1040px; margin: 0 auto; padding: 32px 24px 48px; }}
    .hero {{ background: linear-gradient(135deg, #ffffff 0%, #f2edff 100%); border: 1px solid var(--border); border-radius: 18px; padding: 28px; margin-bottom: 20px; }}
    .eyebrow {{ color: var(--accent); font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }}
    h1 {{ margin: 10px 0 8px; font-size: 32px; }}
    .meta {{ color: var(--muted); font-size: 14px; display: flex; gap: 16px; flex-wrap: wrap; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }}
    .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 18px; }}
    .label {{ color: var(--muted); font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 10px; }}
    .value {{ font-size: 28px; font-weight: 700; }}
    .sections {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
    .section-title {{ margin: 0 0 14px; font-size: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 10px 0; border-bottom: 1px solid var(--border); font-size: 14px; }}
    th:last-child, td:last-child {{ text-align: right; }}
    th {{ color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; }}
    .footer {{ margin-top: 20px; color: var(--muted); font-size: 12px; }}
    @media print {{
      body {{ background: #fff; }}
      .page {{ max-width: none; padding: 16px; }}
      .hero, .card {{ break-inside: avoid; }}
    }}
    @media (max-width: 900px) {{
      .grid, .sections {{ grid-template-columns: 1fr 1fr; }}
    }}
    @media (max-width: 640px) {{
      .grid, .sections {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <div class="eyebrow">Claude Stats Report</div>
      <h1>{period_label} Report</h1>
      <div class="meta">
        <span>Generated: {today_label}</span>
        <span>Scope: {scope_label}</span>
        <span>Window: Last {'7' if period == 'week' else '30'} days</span>
      </div>
    </section>

    <section class="grid">
      <div class="card"><div class="label">Total Tokens</div><div class="value">{total_tokens:,}</div></div>
      <div class="card"><div class="label">Output Tokens</div><div class="value">{total_output:,}</div></div>
      <div class="card"><div class="label">Input-side Tokens</div><div class="value">{total_input:,}</div></div>
      <div class="card"><div class="label">Sessions</div><div class="value">{sessions:,}</div></div>
      <div class="card"><div class="label">Models Used</div><div class="value">{models_used}</div></div>
      <div class="card"><div class="label">Active Time</div><div class="value">{active_time}</div></div>
      <div class="card"><div class="label">Daily Average</div><div class="value">{daily_avg:,}</div></div>
      <div class="card"><div class="label">Active Days</div><div class="value">{active_days}</div></div>
    </section>

    <section class="sections">
      <div class="card">
        <h2 class="section-title">Top Days</h2>
        <table>
          <thead><tr><th>Day</th><th>Tokens</th></tr></thead>
          <tbody>{_rows(top_days, 'date')}</tbody>
        </table>
      </div>
      <div class="card">
        <h2 class="section-title">Top Models</h2>
        <table>
          <thead><tr><th>Model</th><th>Tokens</th></tr></thead>
          <tbody>{_rows(top_models, 'model')}</tbody>
        </table>
      </div>
      <div class="card">
        <h2 class="section-title">Top Projects</h2>
        <table>
          <thead><tr><th>Project</th><th>Tokens</th></tr></thead>
          <tbody>{_rows(top_projects, 'project')}</tbody>
        </table>
      </div>
    </section>

    <div class="footer">Open this file in a browser to view, print, or save as PDF.</div>
  </div>
</body>
</html>
"""
    buf = io.BytesIO(html.encode('utf-8'))
    return send_file(
        buf,
        mimetype='text/html; charset=utf-8',
        as_attachment=True,
        download_name=f"claude-stats-{period}-report-{today_label}.html",
    )


@app.route('/api/slot')
def api_slot():
    date_str = request.args.get('date')
    slot_raw = request.args.get('slot')
    project_filter = request.args.get('project', 'all')
    if not date_str or slot_raw is None:
        return {'error': 'date and slot required'}, 400
    try:
        slot = int(slot_raw)
    except ValueError:
        return {'error': 'slot must be an integer'}, 400
    if slot < 0 or slot > 95:
        return {'error': 'slot must be between 0 and 95'}, 400

    tz = _parse_tz(request.args.get('tz', ''))
    records = _records_for_project(load_usage_records(tz), project_filter)
    slot_records = []
    for r in records:
        if r['date'] != date_str or r['hour'] == 'unknown' or r['minute'] == 'unknown':
            continue
        record_slot = int(r['hour']) * 4 + int(r['minute']) // 15
        if record_slot == slot:
            slot_records.append(r)

    slot_label = f"{slot//4:02d}:{(slot%4)*15:02d}"
    total_tokens = sum(r['input_tokens'] + r['output_tokens'] + r['cache_read'] + r['cache_create'] for r in slot_records)
    output_tokens = sum(r['output_tokens'] for r in slot_records)
    input_tokens = sum(r['input_tokens'] + r['cache_read'] + r['cache_create'] for r in slot_records)
    sessions = len({r['session_id'] or (r['project'], r['hour'], r['minute']) for r in slot_records})
    models_used = len({r['model'] for r in slot_records if r['model']})
    active_time = _fmt_dur(_merge_intervals([
        (r['dt_start'], r['dt_local'])
        for r in slot_records
        if r['dt_start'] and r['dt_local'] and r['dt_local'] > r['dt_start']
    ]))

    project_totals = defaultdict(int)
    model_totals = defaultdict(int)
    session_rows = []
    for r in slot_records:
        tokens = r['input_tokens'] + r['output_tokens'] + r['cache_read'] + r['cache_create']
        project_totals[r['project']] += tokens
        model_totals[r['model']] += tokens
        session_rows.append({
            'session_id': r['session_id'] or '—',
            'project': r['project'],
            'model': r['model'],
            'time': r['dt_local'].strftime('%H:%M') if r['dt_local'] else f"{r['hour']}:{r['minute']}",
            'tokens': tokens,
            'output': r['output_tokens'],
            'input': r['input_tokens'] + r['cache_read'] + r['cache_create'],
        })
    session_rows.sort(key=lambda item: (-item['tokens'], item['time']))

    return {
        'date': date_str,
        'slot': slot,
        'slot_label': slot_label,
        'total_tokens': total_tokens,
        'output_tokens': output_tokens,
        'input_tokens': input_tokens,
        'sessions': sessions,
        'models_used': models_used,
        'active_time': active_time,
        'top_projects': [{'project': p, 'tokens': t} for p, t in sorted(project_totals.items(), key=lambda item: -item[1])[:6]],
        'top_models': [{'model': m, 'tokens': t} for m, t in sorted(model_totals.items(), key=lambda item: -item[1])[:6]],
        'sessions_rows': session_rows[:12],
    }

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

    # Weekly / monthly totals
    week_cutoff = (date_cls.fromisoformat(today_str) - timedelta(days=7)).isoformat()
    month_cutoff = (date_cls.fromisoformat(today_str) - timedelta(days=30)).isoformat()
    week_tokens = sum(r['input_tokens'] + r['output_tokens'] + r['cache_read'] + r['cache_create'] for r in records if r['date'] != 'unknown' and r['date'] >= week_cutoff)
    month_tokens = sum(r['input_tokens'] + r['output_tokens'] + r['cache_read'] + r['cache_create'] for r in records if r['date'] != 'unknown' and r['date'] >= month_cutoff)

    # Daily average (active days only)
    active_days = len({r['date'] for r in records if r['date'] != 'unknown'})
    daily_avg = total_tokens // active_days if active_days > 0 else 0

    # Cache hit rate (cache_read as % of all input-side tokens)
    input_side = total_input + total_cache_read + total_cache_create
    cache_hit_rate = round(total_cache_read / input_side * 100) if input_side > 0 else 0

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

    # Active time = union of [dt_start, dt_local] request intervals across all records
    # dt_start = parent user message timestamp, dt_local = assistant response timestamp
    # Union avoids double-counting parallel agents
    raw_intervals = []
    for r in all_records:
        if r['dt_start'] and r['dt_local'] and r['dt_local'] > r['dt_start']:
            raw_intervals.append((r['dt_start'], r['dt_local']))

    # Sort and merge overlapping intervals, attribute to date of interval start
    date_active = defaultdict(timedelta)
    if raw_intervals:
        raw_intervals.sort()
        cur_start, cur_end = raw_intervals[0]
        for s, e in raw_intervals[1:]:
            if s <= cur_end:
                cur_end = max(cur_end, e)
            else:
                date_active[cur_start.strftime('%Y-%m-%d')] += cur_end - cur_start
                cur_start, cur_end = s, e
        date_active[cur_start.strftime('%Y-%m-%d')] += cur_end - cur_start

    today_dur = date_active.get(today_str, timedelta())
    week_dur = sum(
        (dur for d, dur in date_active.items() if d >= week_cutoff),
        timedelta()
    )

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

    # Top model and project (now that model_totals and projects_ranked are computed)
    top_model = max(model_totals, key=model_totals.get) if model_totals else ''

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
            'today_duration': _fmt_dur(today_dur),
            'week_duration': _fmt_dur(week_dur),
            'streak': streak,
            'week_tokens': week_tokens,
            'month_tokens': month_tokens,
            'daily_avg': daily_avg,
            'cache_hit_rate': cache_hit_rate,
            'top_model': top_model,
            'top_project': projects_ranked[0]['project'] if projects_ranked else '',
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

    # 15-minute slots (96 total)
    quarter = defaultdict(lambda: defaultdict(int))
    for r in records:
        if r['hour'] == 'unknown' or r['minute'] == 'unknown':
            continue
        slot = int(r['hour']) * 4 + int(r['minute']) // 15
        quarter[slot]['input'] += r['input_tokens']
        quarter[slot]['output'] += r['output_tokens']

    slots = list(range(96))
    slot_labels = [f"{s//4:02d}:{(s%4)*15:02d}" for s in slots]

    hours = [f'{i:02d}' for i in range(24)]
    day_tokens = sum(r['input_tokens'] + r['output_tokens'] + r['cache_read'] + r['cache_create'] for r in records)
    day_output = sum(r['output_tokens'] for r in records)
    day_input = sum(r['input_tokens'] + r['cache_read'] + r['cache_create'] for r in records)
    day_sessions = len({r['project'] for r in records})
    day_models_used = len({r['model'] for r in records if r['model']})
    model_tok = defaultdict(int)
    proj_tok = defaultdict(int)
    for r in records:
        model_tok[r['model']] += r['input_tokens'] + r['output_tokens'] + r['cache_read'] + r['cache_create']
        proj_tok[r['project']] += r['input_tokens'] + r['output_tokens'] + r['cache_read'] + r['cache_create']
    day_top_model = max(model_tok, key=model_tok.get) if model_tok else ''
    day_top_project = max(proj_tok, key=proj_tok.get) if proj_tok else ''

    day_intervals = []
    for r in records:
        if r['dt_start'] and r['dt_local'] and r['dt_local'] > r['dt_start']:
            day_intervals.append((r['dt_start'], r['dt_local']))
    day_active = timedelta()
    if day_intervals:
        day_intervals.sort()
        cur_start, cur_end = day_intervals[0]
        for s, e in day_intervals[1:]:
            if s <= cur_end:
                cur_end = max(cur_end, e)
            else:
                day_active += cur_end - cur_start
                cur_start, cur_end = s, e
        day_active += cur_end - cur_start

    return {
        'date': date_str,
        'hours': hours,
        'input': [hourly[h]['input'] for h in hours],
        'output': [hourly[h]['output'] for h in hours],
        'cache_read': [hourly[h]['cache_read'] for h in hours],
        'cache_create': [hourly[h]['cache_create'] for h in hours],
        'slot_labels': slot_labels,
        'slot_output': [quarter[s]['output'] for s in slots],
        'slot_input': [quarter[s]['input'] for s in slots],
        'day_tokens': day_tokens,
        'day_output': day_output,
        'day_input': day_input,
        'day_sessions': day_sessions,
        'day_active_time': _fmt_dur(day_active),
        'day_models_used': day_models_used,
        'day_top_model': day_top_model,
        'day_top_project': day_top_project,
    }

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5050))
    app.run(debug=True, host='0.0.0.0', port=port)
