# Dark / Light Mode Toggle — Design Spec

**Date:** 2026-03-23
**Status:** Approved

---

## Overview

Add a dark/light mode toggle to the Claude Stats dashboard. The existing dark mode is preserved as-is; a new "Cool Slate" light mode is introduced. Users can switch between them via a single icon button in the nav bar. The preference is persisted in `localStorage` and defaults to the system's `prefers-color-scheme`.

---

## Color Tokens

All hardcoded hex values in the `<style>` block are replaced with CSS custom properties. Two theme sets are defined on `[data-theme="dark"]` and `[data-theme="light"]`.

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

---

## Toggle Button

- **Location:** Nav bar, right side, adjacent to the project dropdown
- **Dark mode appearance:** ☀️ icon (click to switch to light)
- **Light mode appearance:** 🌙 icon (click to switch to dark)
- **Markup:** A `<button id="theme-toggle">` styled to match the existing nav inputs

---

## Theme Persistence & Initialization

On page load (before rendering):

1. Read `localStorage.getItem('theme')`
2. If set, apply that theme
3. If not set, check `window.matchMedia('(prefers-color-scheme: dark)')` and apply accordingly
4. Apply by setting `document.documentElement.setAttribute('data-theme', theme)`

On toggle:

1. Flip `data-theme` between `'dark'` and `'light'`
2. Save new value to `localStorage.setItem('theme', theme)`
3. Re-render all Chart.js charts with updated color palette

---

## Chart Colors

Chart colors are defined in a JS object keyed by theme. When the theme changes, all active charts are destroyed and re-initialized with the new palette.

```js
const CHART_COLORS = {
  dark: {
    output: '#a78bfa',
    input: '#6366f1',
    cacheRead: '#1e3a5f',
    cacheCreate: '#2d4a6e',
    heatmap: ['#1e2130', '#2d2550', '#4a3a8a', '#7c5cbf', '#a78bfa'],
  },
  light: {
    output: '#a78bfa',
    input: '#6366f1',
    cacheRead: '#93c5fd',
    cacheCreate: '#bfdbfe',
    heatmap: ['#e8ecf5', '#d4d0f5', '#a78bfa80', '#7c5cbf', '#6366f1'],
  },
};
```

---

## Implementation Scope

**Files changed:**
- `templates/index.html` — all changes are contained here

**Changes:**
1. Add CSS variable declarations for both themes to `<style>` block
2. Replace all hardcoded color values in CSS with `var(--token-name)`
3. Add `#theme-toggle` button to nav HTML
4. Add `initTheme()` function (runs on load)
5. Add `toggleTheme()` function (called by button)
6. Add `CHART_COLORS` object with dark/light palettes
7. Update all chart initialization to use `CHART_COLORS[currentTheme]`
8. Call `renderAll()` after theme toggle to redraw charts

**Out of scope:**
- No server-side changes
- No new files
- No changes to `app.py` or `docker-compose.yml`
