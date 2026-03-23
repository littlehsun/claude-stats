# Claude Stats

[繁體中文](./README.zh-TW.md)

A local web dashboard to visualize your [Claude Code](https://claude.ai/code) usage — token consumption, model distribution, and per-project breakdown.

Reads data directly from `~/.claude/projects/` with no setup required beyond Docker (or Python).

![dark dashboard with token charts](https://img.shields.io/badge/theme-dark-1e2130?style=flat-square)
![python](https://img.shields.io/badge/python-3.12+-blue?style=flat-square)
![flask](https://img.shields.io/badge/flask-latest-green?style=flat-square)

## Features

- **Activity Heatmap** — GitHub-style 52-week calendar at the top of Overview; purple intensity shows daily token volume; hover to see exact date and count
- **Today's stats** — KPI cards for today's tokens, output, and active sessions updated on every load
- **Streak** — Consecutive days with any Claude usage, so the streak counter stays accurate even if today hasn't started yet
- **Overview** — 8 KPI cards (today + all-time), model distribution donut chart, top projects ranking
- **Tokens** — Daily stacked bar (input / output / cache read / cache create) + Output by Model breakdown, 7d/30d/All filter, click any bar to drill into 24-hour hourly view
- **Projects** — All projects ranked by token usage, with 1D/7D/30D/ALL time range filter
- **Project filter** — Nav dropdown to scope all charts to a single project
- **Automatic timezone** — All timestamps are converted to your browser's local timezone; works correctly for any timezone worldwide with no configuration needed

## Quick Start (Docker)

```bash
git clone https://github.com/littlehsun/claude-stats
cd claude-stats
./run.sh
```

The interactive menu lets you:

```
╔══════════════════════════════════╗
║        Claude Stats Runner       ║
╚══════════════════════════════════╝

  1) Start (default port 5050)
  2) Start on custom port
  3) Stop
  4) Rebuild & Start
  5) Exit
```

Press **Enter** to start on the default port 5050, then open **http://localhost:5050**.

> **Requirements:** [Docker](https://docs.docker.com/get-docker/) with the daemon running.

## Manual Setup (Python)

```bash
git clone https://github.com/littlehsun/claude-stats
cd claude-stats

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./start.sh
```

## Data Source

All data is read locally from `~/.claude/projects/`. Each subdirectory is a project, each `.jsonl` file is a conversation. The app parses `assistant` messages and extracts token usage fields:

| Field | Source |
|-------|--------|
| `input_tokens` | `message.usage.input_tokens` |
| `output_tokens` | `message.usage.output_tokens` |
| `cache_read` | `message.usage.cache_read_input_tokens` |
| `cache_create` | `message.usage.cache_creation_input_tokens` |

No data leaves your machine.

## Timezone

Timestamps in the raw data are stored in UTC. The dashboard automatically detects your browser's local timezone and converts all dates and hours accordingly — daily charts, the heatmap, hourly drilldowns, and today's stats all reflect your local time. No configuration is required.
