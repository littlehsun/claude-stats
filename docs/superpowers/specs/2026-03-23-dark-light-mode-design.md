# Dark / Light Mode Toggle — Design Spec

**Date:** 2026-03-23
**Status:** Approved

---

## Overview

Add a dark/light mode toggle to the Claude Stats dashboard. The existing dark mode is preserved as-is; a new "Cool Slate" light mode is introduced. Users can switch between them via a single icon button in the nav bar. The preference is persisted in `localStorage` and defaults to the system's `prefers-color-scheme`.

---

## Color Tokens

All hardcoded hex values in the `<style>` block **and** HTML inline `style` attributes are replaced with CSS custom properties. Two theme sets are defined on `[data-theme="dark"]` and `[data-theme="light"]`.

| Variable | Dark | Light |
|---|---|---|
| `--bg` | `#0f1117` | `#f0f2f8` |
| `--surface` | `#1e2130` | `#ffffff` |
| `--surface-alt` | `#252840` | `#f5f6fc` |
| `--nav-bg` | `#1a1d2e` | `#e8ecf5` |
| `--input-bg` | `#252840` | `#dde2f0` |
| `--text-primary` | `#e2e8f0` | `#1a1f3a` |
| `--text-secondary` | `#94a3b8` | `#6b7494` |
| `--text-tertiary` | `#64748b` | `#9099b8` |
| `--border` | `#2d3148` | `#dde2f0` |
| `--border-strong` | `#3d4166` | `#c8cfea` |
| `--accent` | `#a78bfa` | `#a78bfa` |
| `--accent2` | `#6366f1` | `#6366f1` |
| `--accent-green` | `#34d399` | `#34d399` |

**Inline `style` attributes** in the HTML (outside the `<style>` block) must also be updated:
- `#heatmap-tooltip` inline style → `color: var(--text-secondary)`
- The back-arrow label span → `color: var(--text-secondary)`
- `#hourly-date` span → `color: var(--accent)`

---

## Toggle Button

- **Location:** Nav bar, right side, adjacent to the project dropdown
- **Dark mode appearance:** ☀️ icon (click to switch to light)
- **Light mode appearance:** 🌙 icon (click to switch to dark)
- **Markup:** A `<button id="theme-toggle">` styled to match the existing nav inputs

---

## Global State Variable

A module-level variable `let currentTheme = 'dark'` is declared alongside the other globals. All chart render functions read from `CHART_COLORS[currentTheme]`. `initTheme()` sets this variable on load; `toggleTheme()` flips it on each click.

---

## Theme Persistence & Initialization

On page load (before rendering), `initTheme()` runs:

1. Read `localStorage.getItem('theme')`
2. If set (`'dark'` or `'light'`), apply that value
3. If not set, check `window.matchMedia('(prefers-color-scheme: dark)').matches` — apply `'dark'` if true, `'light'` otherwise
4. Set `currentTheme` to the resolved value
5. Apply by calling `document.documentElement.setAttribute('data-theme', currentTheme)`
6. Update the toggle button icon accordingly

On toggle (`toggleTheme()`):

1. Flip `currentTheme` between `'dark'` and `'light'`
2. Update `data-theme` on `<html>`
3. Save to `localStorage.setItem('theme', currentTheme)`
4. Update toggle button icon
5. If the hourly view is currently visible, re-run `showHourlyChart` with the current date to redraw the hourly chart with new colors
6. Call `renderAll()` to redraw all other charts

---

## Chart Colors

All chart color values are defined in a `CHART_COLORS` object keyed by theme. No hardcoded colors remain in chart initialization code. Every `renderXxx` function reads from `CHART_COLORS[currentTheme]`.

```js
const CHART_COLORS = {
  dark: {
    output: '#a78bfa',
    input: '#6366f1',
    cacheRead: '#1e6a9f',
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

### Chart.js options

Every chart's `options` block reads legend/tick/grid colors from `CHART_COLORS[currentTheme]` at construction time (not CSS variables, since Chart.js does not re-read CSS at runtime):

```js
plugins: { legend: { labels: { color: CHART_COLORS[currentTheme].legendColor } } },
scales: {
  x: { ticks: { color: CHART_COLORS[currentTheme].tickColor }, grid: { color: CHART_COLORS[currentTheme].gridColor } },
  y: { ticks: { color: CHART_COLORS[currentTheme].tickColor }, grid: { color: CHART_COLORS[currentTheme].gridColor } },
}
```

### Heatmap canvas

`renderHeatmap` drops its local `const COLORS` and reads `CHART_COLORS[currentTheme].heatmap` instead. Canvas `ctx.fillStyle` calls for month/day labels read `CHART_COLORS[currentTheme].heatmapLabel`. The legend `innerHTML` reconstruction also reads from `CHART_COLORS[currentTheme].heatmap`.

---

## Hourly Chart on Theme Toggle

`showHourlyChart(date)` is not called by `renderAll()`. If the hourly view is visible when the user toggles the theme, `toggleTheme()` detects this by checking `document.getElementById('hourly-view').style.display !== 'none'` and re-calls `showHourlyChart` with the currently displayed date (read from `document.getElementById('hourly-date').textContent`).

---

## Implementation Scope

**Files changed:**
- `templates/index.html` — all changes are contained here

**Changes:**
1. Add `[data-theme="dark"]` and `[data-theme="light"]` CSS variable declarations to `<style>` block
2. Replace all hardcoded color values in CSS rules with `var(--token-name)`
3. Update the two inline `style` attributes in HTML to use `var(--token-name)`
4. Add `#theme-toggle` button to nav HTML
5. Declare `let currentTheme = 'dark'` alongside other globals
6. Add `CHART_COLORS` object with full dark/light palettes (as above)
7. Add `initTheme()` function — runs on page load before `renderAll()`
8. Add `toggleTheme()` function — updates state, localStorage, icon, and re-renders charts; handles hourly view case
9. Update all chart initialization functions to use `CHART_COLORS[currentTheme]` for colors and chart options — explicitly: `renderDailyChart`, `renderModelPie`, `renderModelDaily`, `renderTopProjects` (uses both `output` and `cacheProjects`), `renderProjectsBar`, `showHourlyChart`, `renderHeatmap`

**Out of scope:**
- No server-side changes
- No new files
- No changes to `app.py` or `docker-compose.yml`
