# Claude Stats

[English](./README.md)

本地網頁儀表板，視覺化呈現你的 [Claude Code](https://claude.ai/code) 使用狀況——Token 消耗、模型分佈、各專案明細。

直接讀取 `~/.claude/projects/` 的本地資料，除了 Docker（或 Python）之外不需要任何額外設定。

![dark and light theme](https://img.shields.io/badge/theme-dark%20%7C%20light-1e2130?style=flat-square)
![python](https://img.shields.io/badge/python-3.12+-blue?style=flat-square)
![flask](https://img.shields.io/badge/flask-latest-green?style=flat-square)

## 功能

- **活動熱力圖** — GitHub 風格的 52 週日曆，紫色深淺代表每日 Token 用量，hover 可看日期與確切數量
- **今日統計** — KPI 卡片即時顯示今日 Token 數、輸出量、活躍專案數
- **連續使用天數** — 計算連續有使用 Claude 的天數，即使當天尚未開始也能正確顯示
- **總覽** — 8 張 KPI 卡片（今日＋累計）、模型分佈圓餅圖、專案排行
- **Token 用量** — 每日堆疊長條圖（input / output / cache read / cache create）＋各模型輸出量，支援 7 天／30 天／全部篩選，點擊任一長條可展開 24 小時細項
- **專案** — 所有專案依 Token 用量排行，支援 1D／7D／30D／ALL 時間範圍篩選
- **專案篩選** — 導覽列下拉選單，可將所有圖表限縮至單一專案
- **自動時區** — 所有時間戳記自動轉換為瀏覽器的本地時區，全球任何時區皆可正確顯示，無需額外設定
- **深色／淺色模式** — 點擊導覽列的 ☀️/🌙 按鈕切換佈景主題，偏好設定儲存於 `localStorage`，預設跟隨系統設定

## 快速開始（Docker）

```bash
git clone https://github.com/littlehsun/claude-stats
cd claude-stats
./run.sh
```

互動式選單：

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

直接按 **Enter** 以預設 port 5050 啟動，然後開啟 **http://localhost:5050**。

> **需求：** 已安裝並執行 [Docker](https://docs.docker.com/get-docker/)。

## 手動安裝（Python）

```bash
git clone https://github.com/littlehsun/claude-stats
cd claude-stats

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./start.sh
```

## 資料來源

所有資料從本機 `~/.claude/projects/` 讀取，每個子目錄是一個專案，每個 `.jsonl` 檔案是一段對話。應用程式解析 `assistant` 訊息並擷取以下 Token 用量欄位：

| 欄位 | 來源 |
|------|------|
| `input_tokens` | `message.usage.input_tokens` |
| `output_tokens` | `message.usage.output_tokens` |
| `cache_read` | `message.usage.cache_read_input_tokens` |
| `cache_create` | `message.usage.cache_creation_input_tokens` |

所有資料都不會離開你的電腦。

## 時區

原始資料中的時間戳記以 UTC 儲存。儀表板會自動偵測瀏覽器的本地時區，並將所有日期與小時轉換為對應的本地時間——每日圖表、熱力圖、每小時細項及今日統計均反映你的當地時間，無需任何設定。
