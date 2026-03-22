from flask import Flask, render_template
import json
from pathlib import Path
from collections import defaultdict
import re

PROJECTS_DIR = Path.home() / '.claude' / 'projects'

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
                        date = ts[:10] if ts else 'unknown'
                        records.append({
                            'project': project_name,
                            'model': model,
                            'date': date,
                            'input_tokens': input_t,
                            'output_tokens': output_t,
                            'cache_read': usage.get('cache_read_input_tokens', 0) or 0,
                            'cache_create': usage.get('cache_creation_input_tokens', 0) or 0,
                        })
            except Exception as e:
                app.logger.warning(f"Skipping {jf}: {e}")
                continue
    return records

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/debug')
def debug():
    records = load_usage_records()
    return {'count': len(records), 'sample': records[:2]}

if __name__ == '__main__':
    app.run(debug=True, port=5050)
