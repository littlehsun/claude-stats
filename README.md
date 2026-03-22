# Claude Stats

A local web dashboard to visualize your [Claude Code](https://claude.ai/code) usage — token consumption, model distribution, and per-project breakdown.

Reads data directly from `~/.claude/projects/` with no setup required beyond installing Flask.

![dark dashboard with token charts](https://img.shields.io/badge/theme-dark-1e2130?style=flat-square)
![python](https://img.shields.io/badge/python-3.8+-blue?style=flat-square)
![flask](https://img.shields.io/badge/flask-latest-green?style=flat-square)

## Features

- **Overview** — KPI cards (total tokens, output tokens, sessions, models used), model distribution donut chart, top projects ranking
- **Tokens** — Daily stacked bar chart (input / output / cache read / cache create), 7d/30d/All filter, click any bar to drill into 24-hour hourly breakdown
- **Projects** — All projects ranked by token usage, with 1D/7D/30D/ALL time range filter
- **Project filter** — Nav dropdown to filter all charts by a single project

## Requirements

- Python 3.8+
- Claude Code with usage data in `~/.claude/projects/`

## Setup

```bash
git clone https://github.com/littlehsun/claude-stats
cd claude-stats

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
./start.sh
```

Then open **http://localhost:5050** in your browser.

The `start.sh` script will:
1. Kill any existing instance on port 5050
2. Activate the virtual environment
3. Start the Flask server

## Data Source

All data is read locally from `~/.claude/projects/`. Each subdirectory is a project, each `.jsonl` file is a conversation. The app parses `assistant` messages and extracts token usage fields:

| Field | Source |
|-------|--------|
| `input_tokens` | `message.usage.input_tokens` |
| `output_tokens` | `message.usage.output_tokens` |
| `cache_read` | `message.usage.cache_read_input_tokens` |
| `cache_create` | `message.usage.cache_creation_input_tokens` |

No data leaves your machine.
