# Dark / Light Mode Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dark/light mode toggle to the Claude Stats dashboard, with "Cool Slate" light mode, a single icon button in the nav bar, and `localStorage` persistence.

**Architecture:** All colors are migrated from hardcoded hex values to CSS custom properties on `[data-theme]`. Chart.js colors (which don't read CSS at runtime) are managed via a `CHART_COLORS` JS object keyed by `currentTheme`. All changes are contained in `templates/index.html`.

**Tech Stack:** Plain HTML/CSS/JS, Chart.js 4.4, Canvas API (heatmap)

---

## File Map

| File | Change |
|---|---|
| `templates/index.html` | All changes — CSS vars, toggle button, JS theme logic, chart color updates |

---

### Task 1: Add CSS variable declarations for both themes

**Files:**
- Modify: `templates/index.html:8-67` (the `<style>` block)

- [ ] **Step 1: Add `[data-theme]` variable blocks at the top of `<style>`**

Insert immediately after the opening `<style>` tag (before `*, *::before`):

```css
[data-theme="dark"] {
  --bg: #0f1117;
  --surface: #1e2130;
  --surface-alt: #252840;
  --nav-bg: #1a1d2e;
  --input-bg: #252840;
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
  --text-tertiary: #64748b;
  --border: #2d3148;
  --border-strong: #3d4166;
  --accent: #a78bfa;
  --accent2: #6366f1;
  --accent-green: #34d399;
}
[data-theme="light"] {
  --bg: #f0f2f8;
  --surface: #ffffff;
  --surface-alt: #f5f6fc;
  --nav-bg: #e8ecf5;
  --input-bg: #dde2f0;
  --text-primary: #1a1f3a;
  --text-secondary: #6b7494;
  --text-tertiary: #9099b8;
  --border: #dde2f0;
  --border-strong: #c8cfea;
  --accent: #a78bfa;
  --accent2: #6366f1;
  --accent-green: #34d399;
}
```

- [ ] **Step 2: Verify file is syntactically valid**

Open `http://localhost:5050` — page should look identical to before (no `data-theme` on `<html>` yet, so variables aren't applied).

---

### Task 2: Replace hardcoded colors in CSS rules with CSS variables

**Files:**
- Modify: `templates/index.html:10-66` (CSS rules inside `<style>`)

Replace every hardcoded hex in the CSS rules. Full replacement map:

| Old value | New value |
|---|---|
| `background: #0f1117` | `background: var(--bg)` |
| `color: #e2e8f0` (body) | `color: var(--text-primary)` |
| `background: #1a1d2e` (.nav, .tabs) | `background: var(--nav-bg)` |
| `border-bottom: 1px solid #2d3148` | `border-bottom: 1px solid var(--border)` |
| `color: #a78bfa` (.nav-title) | `color: var(--accent)` |
| `background: #252840` (.project-select) | `background: var(--input-bg)` |
| `border: 1px solid #3d4166` (.project-select) | `border: 1px solid var(--border-strong)` |
| `color: #e2e8f0` (.project-select) | `color: var(--text-primary)` |
| `border-color: #a78bfa` (.project-select:focus) | `border-color: var(--accent)` |
| `color: #64748b` (.tab) | `color: var(--text-tertiary)` |
| `color: #94a3b8` (.tab:hover) | `color: var(--text-secondary)` |
| `color: #a78bfa` (.tab.active) | `color: var(--accent)` |
| `border-bottom-color: #a78bfa` (.tab.active) | `border-bottom-color: var(--accent)` |
| `background: #1e2130` (.kpi-card, .chart-card) | `background: var(--surface)` |
| `color: #fff` (.kpi-value) | `color: var(--text-primary)` |
| `color: #a78bfa` (.kpi-card.purple .kpi-label) | `color: var(--accent)` |
| `color: #64748b` (.chart-title) | `color: var(--text-tertiary)` |
| `background: #252840` (.range-btn) | `background: var(--input-bg)` |
| `border: 1px solid #3d4166` (.range-btn) | `border: 1px solid var(--border-strong)` |
| `color: #64748b` (.range-btn) | `color: var(--text-tertiary)` |
| `background: #a78bfa22` (.range-btn.active) | keep as-is (accent with alpha, looks fine both modes) |
| `border-color: #a78bfa` (.range-btn.active) | `border-color: var(--accent)` |
| `color: #a78bfa` (.range-btn.active) | `color: var(--accent)` |
| `color: #475569` (.drilldown-hint) | `color: var(--text-tertiary)` |
| `color: #64748b` (.heatmap-legend) | `color: var(--text-tertiary)` |

- [ ] **Step 3: Apply all replacements**

- [ ] **Step 4: Update inline `style` attributes in HTML** (these are outside the `<style>` block):

  - Line 91: `style="color:#94a3b8;font-size:12px"` → `style="color:var(--text-secondary);font-size:12px"`
  - Line 145 (back-arrow label): `style="color:#94a3b8;font-size:13px"` → `style="color:var(--text-secondary);font-size:13px"`
  - Line 145 (`#hourly-date`): `style="color:#a78bfa;font-weight:600"` → `style="color:var(--accent);font-weight:600"`

- [ ] **Step 5: Commit CSS variable migration**

```bash
git add templates/index.html
git commit -m "refactor: migrate CSS colors to custom properties for theme support"
```

---

### Task 3: Add toggle button to nav HTML

**Files:**
- Modify: `templates/index.html:70-77` (nav HTML)

- [ ] **Step 1: Add `#theme-toggle` button inside `.nav-controls`**

Replace:
```html
  <nav class="nav">
    <span class="nav-title">⚡ Claude Stats</span>
    <div class="nav-controls">
      <select class="project-select" id="projectSelect" onchange="onProjectChange()">
        <option value="all">All Projects</option>
      </select>
    </div>
  </nav>
```

With:
```html
  <nav class="nav">
    <span class="nav-title">⚡ Claude Stats</span>
    <div class="nav-controls">
      <select class="project-select" id="projectSelect" onchange="onProjectChange()">
        <option value="all">All Projects</option>
      </select>
      <button id="theme-toggle" onclick="toggleTheme()" title="Toggle theme">☀️</button>
    </div>
  </nav>
```

- [ ] **Step 2: Add button styles to `<style>` block**

Add after the `.project-select:focus` rule:
```css
#theme-toggle { background: var(--input-bg); border: 1px solid var(--border-strong); color: var(--text-primary); padding: 5px 9px; border-radius: 6px; font-size: 14px; cursor: pointer; line-height: 1; }
#theme-toggle:hover { border-color: var(--accent); }
```

- [ ] **Step 3: Verify button appears in nav**

Open `http://localhost:5050` — ☀️ button should appear to the right of the project dropdown, styled to match it. Clicking does nothing yet.

---

### Task 4: Add JS globals, `CHART_COLORS`, and `initTheme` / `toggleTheme`

**Files:**
- Modify: `templates/index.html` — JS section starting at line 172

- [ ] **Step 1: Add `currentTheme` to globals and `CHART_COLORS` constant**

After the existing globals block:
```js
let statsData = null;
let currentRange = 0;
let currentProject = 'all';
let projRange = 0;
let charts = {};
```

Add:
```js
let currentTheme = 'dark';

const CHART_COLORS = {
  dark: {
    output: '#a78bfa',
    input: '#6366f1',
    cacheRead: '#1e6a9f',  // matches existing hourly chart border color (#1e6a9f); daily bar chart previously used #1e3a5f — intentional unification
    cacheCreate: '#2d4a6e',
    cacheProjects: '#3d3166',
    legendColor: '#94a3b8',
    tickColor: '#64748b',
    gridColor: '#1e2130',
    modelPie: ['#a78bfa', '#6366f1', '#34d399', '#f59e0b', '#60a5fa'],
    modelDaily: ['#a78bfa','#34d399','#f59e0b','#60a5fa','#f472b6','#fb923c','#2dd4bf','#818cf8'],
    heatmap: ['#1e2130', '#2d2550', '#4a3a8a', '#7c5cbf', '#a78bfa'],
    heatmapLabel: '#64748b',
  },
  light: {
    output: '#a78bfa',
    input: '#6366f1',
    cacheRead: '#93c5fd',
    cacheCreate: '#bfdbfe',
    cacheProjects: '#c4b5fd',
    legendColor: '#6b7494',
    tickColor: '#9099b8',
    gridColor: '#e8ecf5',
    modelPie: ['#a78bfa', '#6366f1', '#34d399', '#f59e0b', '#60a5fa'],
    modelDaily: ['#a78bfa','#34d399','#f59e0b','#60a5fa','#f472b6','#fb923c','#2dd4bf','#818cf8'],
    heatmap: ['#e8ecf5', '#d4d0f5', '#b49ef580', '#7c5cbf', '#6366f1'],
    heatmapLabel: '#9099b8',
  },
};
```

- [ ] **Step 2: Add `initTheme()` and `toggleTheme()` functions**

Add before the `// Init` comment at the bottom of the script:

```js
function _applyTheme(theme) {
  currentTheme = theme;
  document.documentElement.setAttribute('data-theme', theme);
  document.getElementById('theme-toggle').textContent = theme === 'dark' ? '☀️' : '🌙';
}

function initTheme() {
  const saved = localStorage.getItem('theme');
  if (saved === 'dark' || saved === 'light') {
    _applyTheme(saved);
  } else {
    _applyTheme(window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }
}

async function toggleTheme() {
  const next = currentTheme === 'dark' ? 'light' : 'dark';
  _applyTheme(next);
  localStorage.setItem('theme', next);
  if (statsData) {
    if (document.getElementById('hourly-view').style.display !== 'none') {
      const date = document.getElementById('hourly-date').textContent;
      if (date) await showHourlyChart(date);
    }
    renderAll();
  }
}
```

- [ ] **Step 3: Call `initTheme()` before `loadStats` in the init block**

Replace:
```js
    // Init
    loadProjects();
    loadStats('all', currentRange);
```

With:
```js
    // Init
    initTheme();
    loadProjects();
    loadStats('all', currentRange);
```

- [ ] **Step 4: Verify theme initializes correctly**

Open `http://localhost:5050`:
- If system is dark mode: page loads in dark, button shows ☀️
- If system is light mode: page loads in light (Cool Slate), button shows 🌙
- Clicking the button switches theme visually (CSS vars kick in)
- Charts will still show old hardcoded colors — that's fixed in Task 5

- [ ] **Step 5: Commit**

```bash
git add templates/index.html
git commit -m "feat: add theme toggle button and initTheme/toggleTheme logic"
```

---

### Task 5: Update all chart render functions to use `CHART_COLORS[currentTheme]`

**Files:**
- Modify: `templates/index.html` — all `renderXxx` and `showHourlyChart` functions

Apply the following changes to each function. The pattern is the same throughout: replace hardcoded hex strings with `CHART_COLORS[currentTheme].<key>`.

- [ ] **Step 1: Remove `const MODEL_COLORS` constant (line 417)**

Delete:
```js
const MODEL_COLORS = ['#a78bfa','#34d399','#f59e0b','#60a5fa','#f472b6','#fb923c','#2dd4bf','#818cf8'];
```

(It is superseded by `CHART_COLORS[currentTheme].modelDaily`)

- [ ] **Step 2: Update `renderModelPie`**

Replace:
```js
    function renderModelPie() {
      destroyChart('modelPie');
      const dist = statsData.model_dist;
      const colors = ['#a78bfa', '#6366f1', '#34d399', '#f59e0b', '#60a5fa'];
      charts['modelPie'] = new Chart(document.getElementById('modelPieChart'), {
        type: 'doughnut',
        data: {
          labels: dist.map(d => fmtModel(d.model)),
          datasets: [{ data: dist.map(d => d.tokens), backgroundColor: colors, borderWidth: 0 }]
        },
        options: {
          plugins: { legend: { labels: { color: '#94a3b8', boxWidth: 12 } } },
          cutout: '60%'
        }
      });
    }
```

With:
```js
    function renderModelPie() {
      destroyChart('modelPie');
      const dist = statsData.model_dist;
      const c = CHART_COLORS[currentTheme];
      charts['modelPie'] = new Chart(document.getElementById('modelPieChart'), {
        type: 'doughnut',
        data: {
          labels: dist.map(d => fmtModel(d.model)),
          datasets: [{ data: dist.map(d => d.tokens), backgroundColor: c.modelPie, borderWidth: 0 }]
        },
        options: {
          plugins: { legend: { labels: { color: c.legendColor, boxWidth: 12 } } },
          cutout: '60%'
        }
      });
    }
```

- [ ] **Step 3: Update `renderTopProjects`**

Replace:
```js
      charts['topProj'] = new Chart(document.getElementById('topProjectsChart'), {
        type: 'bar',
        data: {
          labels: top.map(p => p.project),
          datasets: [
            { label: 'Output', data: top.map(p => p.output), backgroundColor: '#a78bfa' },
            { label: 'Cache', data: top.map(p => p.cache), backgroundColor: '#3d3166' },
          ]
        },
        options: {
          indexAxis: 'y',
          plugins: { legend: { labels: { color: '#94a3b8', boxWidth: 10 } } },
          scales: {
            x: { stacked: true, ticks: { color: '#64748b', callback: v => fmtNum(v) }, grid: { color: '#2d3148' } },
            y: { stacked: true, ticks: { color: '#94a3b8' }, grid: { display: false } }
          }
        }
      });
```

With:
```js
      const c = CHART_COLORS[currentTheme];
      charts['topProj'] = new Chart(document.getElementById('topProjectsChart'), {
        type: 'bar',
        data: {
          labels: top.map(p => p.project),
          datasets: [
            { label: 'Output', data: top.map(p => p.output), backgroundColor: c.output },
            { label: 'Cache', data: top.map(p => p.cache), backgroundColor: c.cacheProjects },
          ]
        },
        options: {
          indexAxis: 'y',
          plugins: { legend: { labels: { color: c.legendColor, boxWidth: 10 } } },
          scales: {
            x: { stacked: true, ticks: { color: c.tickColor, callback: v => fmtNum(v) }, grid: { color: c.gridColor } },
            y: { stacked: true, ticks: { color: c.legendColor }, grid: { display: false } }
          }
        }
      });
```

- [ ] **Step 4: Update `renderDailyChart`**

Replace the datasets and options hardcoded colors:
```js
      charts['daily'] = new Chart(document.getElementById('dailyTokenChart'), {
        type: 'bar',
        data: {
          labels: dates,
          datasets: [
            { label: 'Output', data: output, backgroundColor: '#a78bfa', stack: 'a' },
            { label: 'Input', data: input, backgroundColor: '#6366f1', stack: 'a' },
            { label: 'Cache Read', data: cache_read, backgroundColor: '#1e3a5f', stack: 'a' },
            { label: 'Cache Create', data: cache_create, backgroundColor: '#2d4a6e', stack: 'a' },
          ]
        },
        options: {
          onClick: (evt, elements) => {
            if (elements.length > 0) {
              const idx = elements[0].index;
              showHourlyChart(dates[idx]);
            }
          },
          plugins: { legend: { labels: { color: '#94a3b8', boxWidth: 10 } } },
          scales: {
            x: { ticks: { color: '#64748b', maxRotation: 45 }, grid: { color: '#2d3148' } },
            y: { ticks: { color: '#64748b', callback: v => fmtNum(v) }, grid: { color: '#2d3148' } }
          }
        }
      });
```

With:
```js
      const c = CHART_COLORS[currentTheme];
      charts['daily'] = new Chart(document.getElementById('dailyTokenChart'), {
        type: 'bar',
        data: {
          labels: dates,
          datasets: [
            { label: 'Output', data: output, backgroundColor: c.output, stack: 'a' },
            { label: 'Input', data: input, backgroundColor: c.input, stack: 'a' },
            { label: 'Cache Read', data: cache_read, backgroundColor: c.cacheRead, stack: 'a' },
            { label: 'Cache Create', data: cache_create, backgroundColor: c.cacheCreate, stack: 'a' },
          ]
        },
        options: {
          onClick: (evt, elements) => {
            if (elements.length > 0) {
              const idx = elements[0].index;
              showHourlyChart(dates[idx]);
            }
          },
          plugins: { legend: { labels: { color: c.legendColor, boxWidth: 10 } } },
          scales: {
            x: { ticks: { color: c.tickColor, maxRotation: 45 }, grid: { color: c.gridColor } },
            y: { ticks: { color: c.tickColor, callback: v => fmtNum(v) }, grid: { color: c.gridColor } }
          }
        }
      });
```

- [ ] **Step 5: Update `renderProjectsBar`**

Replace the datasets and options hardcoded colors:
```js
      charts['projBar'] = new Chart(document.getElementById('projectsBarChart'), {
        type: 'bar',
        data: {
          labels: ranked.map(p => p.project),
          datasets: [
            { label: 'Output', data: ranked.map(p => p.output), backgroundColor: '#a78bfa', stack: 'a' },
            { label: 'Cache', data: ranked.map(p => p.cache), backgroundColor: '#3d3166', stack: 'a' },
          ]
        },
        options: {
          indexAxis: 'y',
          plugins: { legend: { labels: { color: '#94a3b8', boxWidth: 10 } } },
          scales: {
            x: { stacked: true, ticks: { color: '#64748b', callback: v => fmtNum(v) }, grid: { color: '#2d3148' } },
            y: { stacked: true, ticks: { color: '#94a3b8', font: { size: 11 } }, grid: { display: false } }
          }
        }
      });
```

With:
```js
      const c = CHART_COLORS[currentTheme];
      charts['projBar'] = new Chart(document.getElementById('projectsBarChart'), {
        type: 'bar',
        data: {
          labels: ranked.map(p => p.project),
          datasets: [
            { label: 'Output', data: ranked.map(p => p.output), backgroundColor: c.output, stack: 'a' },
            { label: 'Cache', data: ranked.map(p => p.cache), backgroundColor: c.cacheProjects, stack: 'a' },
          ]
        },
        options: {
          indexAxis: 'y',
          plugins: { legend: { labels: { color: c.legendColor, boxWidth: 10 } } },
          scales: {
            x: { stacked: true, ticks: { color: c.tickColor, callback: v => fmtNum(v) }, grid: { color: c.gridColor } },
            y: { stacked: true, ticks: { color: c.legendColor, font: { size: 11 } }, grid: { display: false } }
          }
        }
      });
```

- [ ] **Step 6: Update `renderModelDaily`**

Replace:
```js
      charts['modelDaily'] = new Chart(document.getElementById('modelDailyChart'), {
        type: 'bar',
        data: {
          labels: dates,
          datasets: models.map((m, i) => ({
            label: fmtModel(m),
            data: series[m],
            backgroundColor: MODEL_COLORS[i % MODEL_COLORS.length],
            stack: 'a',
          }))
        },
        options: {
          plugins: { legend: { labels: { color: '#94a3b8', boxWidth: 10 } } },
          scales: {
            x: { ticks: { color: '#64748b', maxRotation: 45 }, grid: { color: '#2d3148' } },
            y: { ticks: { color: '#64748b', callback: v => fmtNum(v) }, grid: { color: '#2d3148' } }
          }
        }
      });
```

With:
```js
      const c = CHART_COLORS[currentTheme];
      charts['modelDaily'] = new Chart(document.getElementById('modelDailyChart'), {
        type: 'bar',
        data: {
          labels: dates,
          datasets: models.map((m, i) => ({
            label: fmtModel(m),
            data: series[m],
            backgroundColor: c.modelDaily[i % c.modelDaily.length],
            stack: 'a',
          }))
        },
        options: {
          plugins: { legend: { labels: { color: c.legendColor, boxWidth: 10 } } },
          scales: {
            x: { ticks: { color: c.tickColor, maxRotation: 45 }, grid: { color: c.gridColor } },
            y: { ticks: { color: c.tickColor, callback: v => fmtNum(v) }, grid: { color: c.gridColor } }
          }
        }
      });
```

- [ ] **Step 7: Update `showHourlyChart`**

Replace the hardcoded colors in dataset `borderColor` values and options:
```js
        charts['hourly'] = new Chart(document.getElementById('hourlyTokenChart'), {
          type: 'line',
          data: {
            labels: data.hours,
            datasets: [
              { label: 'Output', data: data.output, borderColor: '#a78bfa', backgroundColor: '#a78bfa18', fill: true, tension: 0.3, pointRadius: 3 },
              { label: 'Input', data: data.input, borderColor: '#6366f1', backgroundColor: '#6366f118', fill: true, tension: 0.3, pointRadius: 3 },
              { label: 'Cache Read', data: data.cache_read, borderColor: '#1e6a9f', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2 },
            ]
          },
          options: {
            plugins: { legend: { labels: { color: '#94a3b8', boxWidth: 10 } } },
            scales: {
              x: { ticks: { color: '#64748b' }, grid: { color: '#2d3148' } },
              y: { ticks: { color: '#64748b', callback: v => fmtNum(v) }, grid: { color: '#2d3148' } }
            }
          }
        });
```

With:
```js
        const c = CHART_COLORS[currentTheme];
        charts['hourly'] = new Chart(document.getElementById('hourlyTokenChart'), {
          type: 'line',
          data: {
            labels: data.hours,
            datasets: [
              { label: 'Output', data: data.output, borderColor: c.output, backgroundColor: c.output + '18', fill: true, tension: 0.3, pointRadius: 3 },
              { label: 'Input', data: data.input, borderColor: c.input, backgroundColor: c.input + '18', fill: true, tension: 0.3, pointRadius: 3 },
              { label: 'Cache Read', data: data.cache_read, borderColor: c.cacheRead, backgroundColor: 'transparent', tension: 0.3, pointRadius: 2 },
            ]
          },
          options: {
            plugins: { legend: { labels: { color: c.legendColor, boxWidth: 10 } } },
            scales: {
              x: { ticks: { color: c.tickColor }, grid: { color: c.gridColor } },
              y: { ticks: { color: c.tickColor, callback: v => fmtNum(v) }, grid: { color: c.gridColor } }
            }
          }
        });
```

- [ ] **Step 8: Update `renderHeatmap`**

Replace the local `COLORS` constant and all hardcoded `ctx.fillStyle` calls:

Replace:
```js
      const COLORS = ['#1e2130', '#2d2550', '#4a3a8a', '#7c5cbf', '#a78bfa'];
```
With:
```js
      const COLORS = CHART_COLORS[currentTheme].heatmap;
```

Replace both occurrences of `ctx.fillStyle = '#64748b';` in the month/day label sections:
```js
      ctx.fillStyle = '#64748b';
```
With:
```js
      ctx.fillStyle = CHART_COLORS[currentTheme].heatmapLabel;
```

Replace the legend rebuild:
```js
      legend.innerHTML = '<span>Less</span>';
      COLORS.forEach(c => {
        legend.innerHTML += `<span class="sq" style="background:${c}"></span>`;
      });
      legend.innerHTML += '<span>More</span>';
```
With:
```js
      const heatColors = CHART_COLORS[currentTheme].heatmap;
      legend.innerHTML = '<span>Less</span>';
      heatColors.forEach(c => {
        legend.innerHTML += `<span class="sq" style="background:${c}"></span>`;
      });
      legend.innerHTML += '<span>More</span>';
```

- [ ] **Step 9: Commit all chart color updates**

```bash
git add templates/index.html
git commit -m "feat: wire all charts to CHART_COLORS for theme-aware rendering"
```

---

### Task 6: End-to-end verification

- [ ] **Step 1: Rebuild Docker and test dark mode**

```bash
docker compose up -d --build
```

Open `http://localhost:5050`:
- Page loads in correct initial theme (matches system preference)
- All charts render with correct dark palette
- Heatmap colors and labels correct

- [ ] **Step 2: Switch to light mode**

Click ☀️ button:
- Background switches to `#f0f2f8` (Cool Slate)
- Nav becomes light blue-gray
- All charts redraw with light palette
- Heatmap redraws with light colors
- Button changes to 🌙

- [ ] **Step 3: Test hourly drilldown in light mode**

Click a bar in the Daily Token chart → hourly view opens with light-mode chart colors. Click ← Back. Toggle theme again — daily chart redraws correctly.

- [ ] **Step 4: Test persistence**

While in light mode, refresh the page → page loads in light mode (localStorage preserved). Open browser dev tools → Application → Local Storage → `theme` key should be `"light"`.

- [ ] **Step 5: Final commit**

```bash
git add templates/index.html
git commit -m "feat: complete dark/light mode toggle with Cool Slate light theme"
```
